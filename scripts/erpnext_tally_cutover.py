#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "migration" / "tally" / "output"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply the current Tally opening cutover pack into ERPNext."
    )
    parser.add_argument(
        "--site",
        default="",
        help="ERPNext site name. Defaults to business.<DOMAIN_NAME> or business.<DOMAIN> from .env.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Generated migration output directory. Default: {OUTPUT_DIR}",
    )
    parser.add_argument(
        "--company",
        default="Vara Lakshmi Agencies",
        help="ERPNext company name to target.",
    )
    parser.add_argument(
        "--posting-date",
        default="2026-04-01",
        help="Opening posting date in ERPNext.",
    )
    parser.add_argument(
        "--default-warehouse",
        default="Main Location - VLA",
        help="Default warehouse for opening stock reconciliation.",
    )
    parser.add_argument(
        "--stage",
        choices=["accounts", "journal", "stock", "clearance", "all"],
        default="all",
        help="Which stage to process. Default: all.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually create missing accounts and draft ERPNext documents. Without this, performs a dry run.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit created or existing draft documents for the selected stage(s).",
    )
    return parser.parse_args()


def env_value(key: str) -> str:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def default_site() -> str:
    domain = env_value("DOMAIN_NAME") or env_value("DOMAIN")
    if domain:
        return f"business.{domain}"
    return "business.manoharsolleti.com"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def load_payload(args: argparse.Namespace) -> dict[str, object]:
    output_dir = args.output_dir
    return {
        "company": args.company,
        "posting_date": args.posting_date,
        "default_warehouse": args.default_warehouse,
        "stage": args.stage,
        "accounts_to_create": read_csv(output_dir / "opening_accounts_to_create.csv"),
        "opening_journal_rows": read_csv(output_dir / "opening_journal_lines_review.csv"),
        "opening_stock_rows": read_csv(output_dir / "opening_stock_from_stksum_staging.csv"),
        "clearance_rows": read_csv(output_dir / "temporary_opening_clearance_entry.csv"),
    }


def server_code(site: str, payload: dict[str, object], apply: bool, submit: bool) -> str:
    payload_json = json.dumps(payload)
    return f"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

import frappe

SITE = {site!r}
APPLY = {apply!r}
SUBMIT = {submit!r}
PAYLOAD = json.loads({payload_json!r})

TEMP_OPENING_ACCOUNT = "Temporary Opening - VLA"
RESERVES_ACCOUNT = "Reserves and Surplus - VLA"
OPENING_JE_REMARK = f"Tally cutover opening entry on {{PAYLOAD['posting_date']}} [AUTO]"
CLEARANCE_JE_REMARK = f"Clear temporary opening after Tally cutover on {{PAYLOAD['posting_date']}} [AUTO]"
STOCK_POSTING_TIME = "06:00:00"


def clean(value):
    return str(value or "").strip()


def parse_decimal(value):
    text = clean(value).replace(",", "")
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def decimal_text(value):
    return format(value.normalize(), "f")


def report_type_for_root(root_type):
    return "Profit and Loss" if root_type in {{"Income", "Expense"}} else "Balance Sheet"


def target_stages():
    if PAYLOAD["stage"] == "all":
        return ["accounts", "journal", "stock", "clearance"]
    return [PAYLOAD["stage"]]


def ensure_single_name(doctype, filters, label):
    names = frappe.get_all(doctype, filters=filters, pluck="name")
    if len(names) > 1:
        raise SystemExit(f"found multiple {{label}} documents: {{names}}")
    return names[0] if names else None


def existing_opening_journal_name():
    return ensure_single_name(
        "Journal Entry",
        [
            ["company", "=", PAYLOAD["company"]],
            ["posting_date", "=", PAYLOAD["posting_date"]],
            ["voucher_type", "=", "Opening Entry"],
            ["user_remark", "=", OPENING_JE_REMARK],
            ["docstatus", "!=", 2],
        ],
        "opening journal entry",
    )


def existing_clearance_journal_name():
    return ensure_single_name(
        "Journal Entry",
        [
            ["company", "=", PAYLOAD["company"]],
            ["posting_date", "=", PAYLOAD["posting_date"]],
            ["voucher_type", "=", "Opening Entry"],
            ["user_remark", "=", CLEARANCE_JE_REMARK],
            ["docstatus", "!=", 2],
        ],
        "temporary opening clearance journal entry",
    )


def existing_stock_reconciliation_name():
    return ensure_single_name(
        "Stock Reconciliation",
        [
            ["company", "=", PAYLOAD["company"]],
            ["posting_date", "=", PAYLOAD["posting_date"]],
            ["posting_time", "=", STOCK_POSTING_TIME],
            ["purpose", "=", "Opening Stock"],
            ["set_warehouse", "=", PAYLOAD["default_warehouse"]],
            ["expense_account", "=", TEMP_OPENING_ACCOUNT],
            ["docstatus", "!=", 2],
        ],
        "opening stock reconciliation",
    )


def validate_payload(stats):
    accounts_to_create = PAYLOAD["accounts_to_create"]
    opening_journal_rows = PAYLOAD["opening_journal_rows"]
    opening_stock_rows = PAYLOAD["opening_stock_rows"]
    clearance_rows = PAYLOAD["clearance_rows"]

    if not frappe.db.exists("Company", PAYLOAD["company"]):
        raise SystemExit(f"missing company: {{PAYLOAD['company']}}")

    if not frappe.db.exists("Warehouse", PAYLOAD["default_warehouse"]):
        raise SystemExit(f"missing warehouse: {{PAYLOAD['default_warehouse']}}")

    for account_name in [TEMP_OPENING_ACCOUNT, RESERVES_ACCOUNT, "Debtors - VLA", "Creditors - VLA"]:
        if not frappe.db.exists("Account", account_name):
            raise SystemExit(f"missing required account: {{account_name}}")

    missing_parents = []
    for row in accounts_to_create:
        parent = clean(row.get("parent_account"))
        if parent and not frappe.db.exists("Account", parent):
            missing_parents.append(parent)
    if missing_parents:
        raise SystemExit(f"missing parent accounts: {{sorted(set(missing_parents))}}")

    creatable_accounts = {{
        clean(row.get("full_account_name")): row for row in accounts_to_create
    }}
    referenced_accounts = []
    for row in opening_journal_rows:
        account = clean(row.get("erpnext_account"))
        if account:
            referenced_accounts.append(account)
    for row in clearance_rows:
        account = clean(row.get("erpnext_account"))
        if account:
            referenced_accounts.append(account)
    missing_accounts = []
    for account in referenced_accounts:
        if frappe.db.exists("Account", account):
            continue
        if account in creatable_accounts:
            continue
        missing_accounts.append(account)
    if missing_accounts:
        raise SystemExit(f"missing journal accounts that are not in opening_accounts_to_create.csv: {{sorted(set(missing_accounts))}}")

    missing_parties = []
    for row in opening_journal_rows:
        party_type = clean(row.get("party_type"))
        party = clean(row.get("party"))
        if party_type and party and not frappe.db.exists(party_type, party):
            missing_parties.append(f"{{party_type}}:{{party}}")
    if missing_parties:
        raise SystemExit(f"missing party masters: {{sorted(set(missing_parties))}}")

    missing_items = []
    for row in opening_stock_rows:
        item_code = clean(row.get("item_code"))
        if item_code and not frappe.db.exists("Item", item_code):
            missing_items.append(item_code)
    if missing_items:
        raise SystemExit(f"missing items referenced by opening stock: {{sorted(set(missing_items))[:10]}}")

    journal_debit = sum(parse_decimal(row.get("debit")) for row in opening_journal_rows)
    journal_credit = sum(parse_decimal(row.get("credit")) for row in opening_journal_rows)
    if journal_debit != journal_credit:
        raise SystemExit(
            f"opening journal is not balanced: debit={{decimal_text(journal_debit)}} credit={{decimal_text(journal_credit)}}"
        )

    stock_total = sum(parse_decimal(row.get("amount")) for row in opening_stock_rows)
    clearance_debit = sum(parse_decimal(row.get("debit")) for row in clearance_rows)
    clearance_credit = sum(parse_decimal(row.get("credit")) for row in clearance_rows)
    if clearance_debit != clearance_credit:
        raise SystemExit(
            f"clearance journal is not balanced: debit={{decimal_text(clearance_debit)}} credit={{decimal_text(clearance_credit)}}"
        )

    temp_opening_debit = sum(
        parse_decimal(row.get("debit"))
        for row in opening_journal_rows
        if clean(row.get("erpnext_account")) == TEMP_OPENING_ACCOUNT
    )
    expected_remaining_credit = stock_total - temp_opening_debit
    if clearance_credit != expected_remaining_credit:
        raise SystemExit(
            "temporary opening clearance amount does not match stock total minus opening journal balancing debit"
        )

    stats["validations"] = {{
        "journal_row_count": len(opening_journal_rows),
        "journal_total_debit": decimal_text(journal_debit),
        "journal_total_credit": decimal_text(journal_credit),
        "stock_row_count": len(opening_stock_rows),
        "stock_total": decimal_text(stock_total),
        "clearance_total": decimal_text(clearance_credit),
        "expected_remaining_temp_opening_credit": decimal_text(expected_remaining_credit),
        "missing_accounts_to_create": [
            clean(row.get("full_account_name"))
            for row in accounts_to_create
            if clean(row.get("full_account_name")) and not frappe.db.exists("Account", clean(row.get("full_account_name")))
        ],
        "existing_opening_journal": existing_opening_journal_name(),
        "existing_stock_reconciliation": existing_stock_reconciliation_name(),
        "existing_clearance_journal": existing_clearance_journal_name(),
    }}


def ensure_accounts(stats):
    created = []
    existing = []
    for row in PAYLOAD["accounts_to_create"]:
        full_name = clean(row.get("full_account_name"))
        if frappe.db.exists("Account", full_name):
            existing.append(full_name)
            continue
        if not APPLY:
            created.append(full_name)
            continue
        doc = frappe.get_doc(
            {{
                "doctype": "Account",
                "account_name": clean(row.get("account_name")),
                "company": clean(row.get("company")),
                "parent_account": clean(row.get("parent_account")),
                "root_type": clean(row.get("root_type")),
                "report_type": report_type_for_root(clean(row.get("root_type"))),
                "account_type": clean(row.get("account_type")),
                "is_group": 0,
            }}
        )
        doc.insert(ignore_permissions=True)
        created.append(doc.name)
    stats["accounts"] = {{
        "existing": existing,
        "created_or_pending": created,
    }}


def upsert_opening_journal(stats):
    name = existing_opening_journal_name()
    if name:
        doc = frappe.get_doc("Journal Entry", name)
        stats["opening_journal"] = {{
            "name": doc.name,
            "docstatus": doc.docstatus,
            "created": False,
            "submitted": False,
        }}
    else:
        if not APPLY:
            stats["opening_journal"] = {{
                "name": None,
                "docstatus": 0,
                "created": False,
                "submitted": False,
                "pending_create": True,
            }}
            return

        rows = []
        for row in PAYLOAD["opening_journal_rows"]:
            rows.append(
                {{
                    "account": clean(row.get("erpnext_account")),
                    "party_type": clean(row.get("party_type")),
                    "party": clean(row.get("party")),
                    "debit_in_account_currency": parse_decimal(row.get("debit")),
                    "credit_in_account_currency": parse_decimal(row.get("credit")),
                    "user_remark": clean(row.get("note")),
                }}
            )
        doc = frappe.get_doc(
            {{
                "doctype": "Journal Entry",
                "voucher_type": "Opening Entry",
                "company": PAYLOAD["company"],
                "posting_date": PAYLOAD["posting_date"],
                "user_remark": OPENING_JE_REMARK,
                "remark": OPENING_JE_REMARK,
                "title": "Tally Opening Cutover",
                "accounts": rows,
            }}
        )
        doc.insert(ignore_permissions=True)
        stats["opening_journal"] = {{
            "name": doc.name,
            "docstatus": doc.docstatus,
            "created": True,
            "submitted": False,
        }}

    if SUBMIT:
        doc = frappe.get_doc("Journal Entry", stats["opening_journal"]["name"])
        if doc.docstatus == 0:
            doc.submit()
            doc.reload()
            stats["opening_journal"]["submitted"] = True
            stats["opening_journal"]["docstatus"] = doc.docstatus


def upsert_stock_reconciliation(stats):
    name = existing_stock_reconciliation_name()
    if name:
        doc = frappe.get_doc("Stock Reconciliation", name)
        stats["opening_stock"] = {{
            "name": doc.name,
            "docstatus": doc.docstatus,
            "created": False,
            "submitted": False,
            "item_count": len(doc.items),
        }}
    else:
        if not APPLY:
            stats["opening_stock"] = {{
                "name": None,
                "docstatus": 0,
                "created": False,
                "submitted": False,
                "pending_create": True,
                "item_count": len(PAYLOAD["opening_stock_rows"]),
            }}
            return

        items = []
        for row in PAYLOAD["opening_stock_rows"]:
            valuation_rate = parse_decimal(row.get("valuation_rate"))
            items.append(
                {{
                    "item_code": clean(row.get("item_code")),
                    "warehouse": clean(row.get("warehouse")) or PAYLOAD["default_warehouse"],
                    "qty": parse_decimal(row.get("qty")),
                    "valuation_rate": valuation_rate,
                    "allow_zero_valuation_rate": 1 if valuation_rate == 0 else 0,
                }}
            )
        doc = frappe.get_doc(
            {{
                "doctype": "Stock Reconciliation",
                "company": PAYLOAD["company"],
                "purpose": "Opening Stock",
                "posting_date": PAYLOAD["posting_date"],
                "posting_time": STOCK_POSTING_TIME,
                "set_posting_time": 1,
                "set_warehouse": PAYLOAD["default_warehouse"],
                "expense_account": TEMP_OPENING_ACCOUNT,
                "items": items,
            }}
        )
        doc.insert(ignore_permissions=True)
        stats["opening_stock"] = {{
            "name": doc.name,
            "docstatus": doc.docstatus,
            "created": True,
            "submitted": False,
            "item_count": len(doc.items),
        }}

    if SUBMIT:
        doc = frappe.get_doc("Stock Reconciliation", stats["opening_stock"]["name"])
        if doc.docstatus == 0:
            doc.submit()
            doc.reload()
            stats["opening_stock"]["submitted"] = True
    fresh_doc = frappe.get_doc("Stock Reconciliation", stats["opening_stock"]["name"])
    stats["opening_stock"]["docstatus"] = fresh_doc.docstatus
    stats["opening_stock"]["difference_amount"] = decimal_text(parse_decimal(fresh_doc.difference_amount))
    stats["opening_stock"]["item_count"] = len(fresh_doc.items)


def upsert_clearance_journal(stats):
    name = existing_clearance_journal_name()
    if name:
        doc = frappe.get_doc("Journal Entry", name)
        stats["clearance_journal"] = {{
            "name": doc.name,
            "docstatus": doc.docstatus,
            "created": False,
            "submitted": False,
        }}
    else:
        if not APPLY:
            stats["clearance_journal"] = {{
                "name": None,
                "docstatus": 0,
                "created": False,
                "submitted": False,
                "pending_create": True,
            }}
            return

        rows = []
        for row in PAYLOAD["clearance_rows"]:
            rows.append(
                {{
                    "account": clean(row.get("erpnext_account")),
                    "debit_in_account_currency": parse_decimal(row.get("debit")),
                    "credit_in_account_currency": parse_decimal(row.get("credit")),
                    "user_remark": clean(row.get("note")),
                }}
            )
        doc = frappe.get_doc(
            {{
                "doctype": "Journal Entry",
                "voucher_type": "Opening Entry",
                "company": PAYLOAD["company"],
                "posting_date": PAYLOAD["posting_date"],
                "user_remark": CLEARANCE_JE_REMARK,
                "remark": CLEARANCE_JE_REMARK,
                "title": "Temporary Opening Clearance",
                "accounts": rows,
            }}
        )
        doc.insert(ignore_permissions=True)
        stats["clearance_journal"] = {{
            "name": doc.name,
            "docstatus": doc.docstatus,
            "created": True,
            "submitted": False,
        }}

    if SUBMIT:
        doc = frappe.get_doc("Journal Entry", stats["clearance_journal"]["name"])
        if doc.docstatus == 0:
            doc.submit()
            doc.reload()
            stats["clearance_journal"]["submitted"] = True
            stats["clearance_journal"]["docstatus"] = doc.docstatus


def current_temp_opening_balance():
    row = frappe.db.sql(
        \"\"\"
        select
            coalesce(sum(debit), 0) as debit,
            coalesce(sum(credit), 0) as credit
        from `tabGL Entry`
        where company = %s
          and account = %s
          and is_cancelled = 0
          and posting_date <= %s
        \"\"\",
        (PAYLOAD["company"], TEMP_OPENING_ACCOUNT, PAYLOAD["posting_date"]),
        as_dict=True,
    )[0]
    debit = parse_decimal(row["debit"])
    credit = parse_decimal(row["credit"])
    return {{
        "debit": decimal_text(debit),
        "credit": decimal_text(credit),
        "net_credit": decimal_text(credit - debit),
    }}


stats = {{
    "site": SITE,
    "company": PAYLOAD["company"],
    "posting_date": PAYLOAD["posting_date"],
    "stage": PAYLOAD["stage"],
    "apply": APPLY,
    "submit": SUBMIT,
}}

frappe.init(site=SITE, sites_path=".")
frappe.connect()
frappe.set_user("Administrator")
try:
    validate_payload(stats)
    for stage in target_stages():
        if stage == "accounts":
            ensure_accounts(stats)
        elif stage == "journal":
            ensure_accounts(stats)
            upsert_opening_journal(stats)
        elif stage == "stock":
            upsert_stock_reconciliation(stats)
        elif stage == "clearance":
            upsert_clearance_journal(stats)

    if APPLY:
        frappe.db.commit()

    stats["temporary_opening_balance"] = current_temp_opening_balance()
finally:
    frappe.destroy()

print(json.dumps(stats, indent=2, sort_keys=True))
"""


def run_in_container(site: str, payload: dict[str, object], apply: bool, submit: bool) -> None:
    code = server_code(site, payload, apply, submit)
    cmd = [
        "docker",
        "compose",
        "-f",
        "docker-compose.yml",
        "-f",
        "docker-compose.apps.yml",
        "exec",
        "-T",
        "erpnext-backend",
        "bash",
        "-lc",
        "mkdir -p /home/frappe/logs && cd /home/frappe/frappe-bench/sites && ../env/bin/python -",
    ]
    subprocess.run(cmd, cwd=REPO_ROOT, input=code, text=True, check=True)


def main() -> int:
    args = parse_args()
    site = args.site or default_site()
    payload = load_payload(args)
    run_in_container(site, payload, args.apply, args.submit)
    if not args.apply:
        print("Dry run only. Re-run with --apply to create missing accounts and draft documents.")
    elif args.apply and not args.submit:
        print("Created missing accounts and draft documents only. Re-run with --submit to submit the selected stage(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
