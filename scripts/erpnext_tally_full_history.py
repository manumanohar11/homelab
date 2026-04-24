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
        description="Rebuild ERPNext from Tally masters, 2025 opening state, and historical vouchers."
    )
    parser.add_argument(
        "--site",
        default="business.manoharsolleti.com",
        help="ERPNext site name.",
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
        "--opening-date",
        default="2025-04-01",
        help="Opening posting date for the full-history rebuild.",
    )
    parser.add_argument(
        "--default-warehouse",
        default="Main Location - VLA",
        help="Default warehouse for stock postings.",
    )
    parser.add_argument(
        "--stage",
        choices=["setup", "opening", "invoices", "settlements", "all"],
        default="all",
        help="Which stage to process. Default: all.",
    )
    parser.add_argument(
        "--allocation-strategy",
        choices=["none", "exact_unique", "fifo"],
        default="exact_unique",
        help=(
            "How to allocate unreferenced customer receipts and supplier payments "
            "to invoices. Default: exact_unique."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually create or submit ERPNext documents. Without this, performs a dry run.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def load_payload(args: argparse.Namespace) -> dict[str, object]:
    output_dir = args.output_dir
    stage = args.stage
    payload: dict[str, object] = {
        "company": args.company,
        "opening_date": args.opening_date,
        "default_warehouse": args.default_warehouse,
        "stage": stage,
        "allocation_strategy": args.allocation_strategy,
        "ledger_rows": read_csv(output_dir / "ledger_accounts_staging.csv"),
    }

    if stage in {"opening", "invoices", "all"}:
        payload["opening_stock_rows"] = read_csv(output_dir / "opening_stock_staging.csv")

    if stage in {"opening", "all"}:
        payload["party_opening_rows"] = read_csv(output_dir / "party_opening_balances_staging.csv")

    if stage in {"invoices", "settlements", "all"}:
        payload["sales_headers"] = read_csv(output_dir / "historical_sales_invoices.csv")
        payload["sales_items"] = read_csv(output_dir / "historical_sales_invoice_items.csv")
        payload["purchase_headers"] = read_csv(output_dir / "historical_purchase_invoices.csv")
        payload["purchase_items"] = read_csv(output_dir / "historical_purchase_invoice_items.csv")
        payload["credit_headers"] = read_csv(output_dir / "historical_credit_notes.csv")
        payload["credit_items"] = read_csv(output_dir / "historical_credit_note_items.csv")

    if stage in {"settlements", "all"}:
        payload["receipt_headers"] = read_csv(output_dir / "historical_receipts.csv")
        payload["receipt_refs"] = read_csv(output_dir / "historical_receipt_references.csv")
        payload["payment_headers"] = read_csv(output_dir / "historical_payments.csv")
        payload["payment_refs"] = read_csv(output_dir / "historical_payment_references.csv")
        payload["settlement_lines"] = read_csv(output_dir / "historical_settlement_lines.csv")
        payload["journal_lines"] = read_csv(output_dir / "historical_journal_lines.csv")

    return payload


def server_code(site: str, payload: dict[str, object], apply: bool) -> str:
    payload_json = json.dumps(payload)
    return f"""
from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation

import frappe

SITE = {site!r}
APPLY = {apply!r}
PAYLOAD = json.loads({payload_json!r})

TEMP_OPENING_ACCOUNT = "Temporary Opening - VLA"
RESERVES_ACCOUNT = "Reserves and Surplus - VLA"
CGST_ACCOUNT = "CGST - VLA"
SGST_ACCOUNT = "SGST - VLA"
ROUND_OFF_ACCOUNT = "Rounded Off - VLA"
DEBTORS_ACCOUNT = "Debtors - VLA"
CREDITORS_ACCOUNT = "Creditors - VLA"
CASH_ACCOUNT = "Cash - VLA"
BANK_OR_CASH_LEDGER_NAMES = {{"Cash", "Punjab National Bank", "Punjab National Bank(3750)", "Indian Bank"}}
OPENING_JE_REMARK = f"[TALLY OPENING][{{PAYLOAD['opening_date']}}][JE]"
OPENING_CLEARANCE_REMARK = f"[TALLY OPENING][{{PAYLOAD['opening_date']}}][CLEARANCE]"
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
    return format(value.quantize(Decimal("0.01")), "f")


def bool_text(value):
    return "1" if value else "0"


def record_result(stats, key, value, limit=10):
    count_key = f"{{key}}_count"
    sample_key = f"{{key}}_examples"
    stats[count_key] = stats.get(count_key, 0) + 1
    samples = stats.setdefault(sample_key, [])
    if value and len(samples) < limit:
        samples.append(value)


def maybe_commit_progress(stats, processed, total, batch_size=100, commit_enabled=True):
    if not APPLY:
        return
    if processed % batch_size == 0:
        if commit_enabled:
            frappe.db.commit()
        print(
            json.dumps(
                {{
                    "progress": {{
                        "processed": processed,
                        "total": total,
                    }}
                }}
            ),
            flush=True,
        )


def report_type_for_root(root_type):
    return "Profit and Loss" if root_type in {{"Income", "Expense"}} else "Balance Sheet"


LEDGER_PARENT_GROUP = {{
    clean(row.get("ledger_name")): clean(row.get("tally_parent_group"))
    for row in PAYLOAD.get("ledger_rows", [])
}}

GROUP_META = {{
    "Bank Accounts": {{"parent_account": "Bank Accounts - VLA", "root_type": "Asset", "account_type": "Bank"}},
    "Bank OD A/c": {{"parent_account": "Loans (Liabilities) - VLA", "root_type": "Liability", "account_type": ""}},
    "Capital Account": {{"parent_account": "Capital Account - VLA", "root_type": "Liability", "account_type": "Equity"}},
    "Cash-in-Hand": {{"parent_account": "Cash In Hand - VLA", "root_type": "Asset", "account_type": "Cash"}},
    "Current Assets": {{"parent_account": "Current Assets - VLA", "root_type": "Asset", "account_type": ""}},
    "Current Liabilities": {{"parent_account": "Current Liabilities - VLA", "root_type": "Liability", "account_type": ""}},
    "Duties & Taxes": {{"parent_account": "Duties and Taxes - VLA", "root_type": "Liability", "account_type": "Tax"}},
    "Indirect Expenses": {{"parent_account": "Indirect Expenses - VLA", "root_type": "Expense", "account_type": "Expense Account"}},
    "Indirect Incomes": {{"parent_account": "Indirect Income - VLA", "root_type": "Income", "account_type": "Income Account"}},
    "Purchase Accounts": {{"parent_account": "Stock Expenses - VLA", "root_type": "Expense", "account_type": "Expense Account"}},
    "Rents": {{"parent_account": "Indirect Expenses - VLA", "root_type": "Expense", "account_type": "Expense Account"}},
    "Salaries Account": {{"parent_account": "Indirect Expenses - VLA", "root_type": "Expense", "account_type": "Expense Account"}},
    "Sales Accounts": {{"parent_account": "Direct Income - VLA", "root_type": "Income", "account_type": "Income Account"}},
    "Unsecured Loans": {{"parent_account": "Loans (Liabilities) - VLA", "root_type": "Liability", "account_type": ""}},
}}

ACCOUNT_ALIASES = {{
    "Cash": "Cash - VLA",
    "SALES": "Sales - VLA",
    "PURCHASES": "Expenses Included In Valuation - VLA",
    "Freight Charges": "Freight Charges - VLA",
    "Freight@5%": "Freight@5% - VLA",
    "Hamali Charges": "Hamali Charges - VLA",
    "Sadar": "Sadar - VLA",
    "Punjab National Bank": "Punjab National Bank - VLA",
    "Punjab National Bank(3750)": "Punjab National Bank(3750) - VLA",
    "Indian Bank": "Indian Bank - VLA",
    "CGST": CGST_ACCOUNT,
    "SGST": SGST_ACCOUNT,
    "ROUND OFF": ROUND_OFF_ACCOUNT,
    "Unavailed ITC": "Unavailed ITC - VLA",
    "Provision for Gst": "Provision for Gst - VLA",
    "Gadamsetty Venkateswara Rao": "Gadamsetty Venkateswara Rao - VLA",
    "Investment in Venkata Syamala Agencies": "Investment in Venkata Syamala Agencies - VLA",
}}


def stage_targets():
    if PAYLOAD["stage"] == "all":
        return ["setup", "opening", "invoices", "settlements"]
    return [PAYLOAD["stage"]]


def invoice_tag(kind, voucher_type, voucher_key, voucher_number):
    return f"[TALLY][{{kind}}][{{voucher_type}}][{{voucher_key}}][{{voucher_number}}]"


def ensure_single_name(doctype, filters, label):
    names = frappe.get_all(doctype, filters=filters, pluck="name")
    if len(names) > 1:
        raise SystemExit(f"found multiple {{label}} documents: {{names[:10]}}")
    return names[0] if names else None


def ensure_fiscal_year():
    if frappe.db.exists("Fiscal Year", "2025-2026"):
        return "2025-2026"
    if not APPLY:
        return "2025-2026"
    doc = frappe.get_doc(
        {{
            "doctype": "Fiscal Year",
            "year": "2025-2026",
            "year_start_date": "2025-04-01",
            "year_end_date": "2026-03-31",
        }}
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def ensure_party(doctype, name):
    if frappe.db.exists(doctype, name):
        return name
    if not APPLY:
        return name
    if doctype == "Customer":
        doc = frappe.get_doc(
            {{
                "doctype": "Customer",
                "customer_name": name,
                "customer_type": "Company",
                "customer_group": "All Customer Groups",
                "territory": "All Territories",
            }}
        )
    else:
        doc = frappe.get_doc(
            {{
                "doctype": "Supplier",
                "supplier_name": name,
                "supplier_group": "All Supplier Groups",
                "supplier_type": "Company",
            }}
        )
    doc.insert(ignore_permissions=True)
    return doc.name


def account_full_name_for_ledger(ledger_name):
    if ledger_name in ACCOUNT_ALIASES:
        return ACCOUNT_ALIASES[ledger_name]
    return f"{{ledger_name}} - VLA"


def ensure_account_for_ledger(ledger_name):
    ledger_name = clean(ledger_name)
    if not ledger_name:
        return ""

    full_name = account_full_name_for_ledger(ledger_name)
    if frappe.db.exists("Account", full_name):
        return full_name

    parent_group = LEDGER_PARENT_GROUP.get(ledger_name, "")
    meta = GROUP_META.get(parent_group)
    if not meta:
        raise SystemExit(f"no ERPNext account mapping metadata for Tally parent group: {{parent_group}} (ledger {{ledger_name}})")

    if not frappe.db.exists("Account", meta["parent_account"]):
        raise SystemExit(f"missing parent account {{meta['parent_account']}} for ledger {{ledger_name}}")

    if not APPLY:
        return full_name

    doc = frappe.get_doc(
        {{
            "doctype": "Account",
            "account_name": ledger_name,
            "company": PAYLOAD["company"],
            "parent_account": meta["parent_account"],
            "root_type": meta["root_type"],
            "report_type": report_type_for_root(meta["root_type"]),
            "account_type": meta["account_type"],
            "is_group": 0,
        }}
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def ensure_base_setup():
    ensure_fiscal_year()
    for account_name in [TEMP_OPENING_ACCOUNT, RESERVES_ACCOUNT, DEBTORS_ACCOUNT, CREDITORS_ACCOUNT, CASH_ACCOUNT, ROUND_OFF_ACCOUNT]:
        if not frappe.db.exists("Account", account_name):
            raise SystemExit(f"missing required base account: {{account_name}}")

    ledger_names = {{
        clean(row.get("ledger_name"))
        for row in PAYLOAD.get("ledger_rows", [])
        if clean(row.get("ledger_name")) and clean(row.get("ledger_name")) != "Profit & Loss A/c"
    }}
    for header_key in ["sales_headers", "purchase_headers", "credit_headers"]:
        for row in PAYLOAD.get(header_key, []):
            if clean(row.get("party")) == "Cash":
                ensure_party("Customer", "Cash")

    for row in PAYLOAD.get("purchase_headers", []):
        party = clean(row.get("party"))
        if party:
            ensure_party("Supplier", party)

    for row in PAYLOAD.get("sales_headers", []):
        party = clean(row.get("party"))
        if party and party != "Cash":
            ensure_party("Customer", party)

    for row in PAYLOAD.get("credit_headers", []):
        party = clean(row.get("party"))
        if party:
            ensure_party("Customer", party)

    for row in PAYLOAD.get("receipt_headers", []):
        if clean(row.get("party_type")) == "Customer":
            ensure_party("Customer", clean(row.get("party")))

    for row in PAYLOAD.get("payment_headers", []):
        if clean(row.get("party_type")) == "Supplier":
            ensure_party("Supplier", clean(row.get("party")))

    for row in PAYLOAD.get("receipt_headers", []):
        ledger_name = clean(row.get("counter_account"))
        if ledger_name and (ledger_name in BANK_OR_CASH_LEDGER_NAMES or ledger_name in LEDGER_PARENT_GROUP or ledger_name in ACCOUNT_ALIASES):
            ledger_names.add(ledger_name)

    for row in PAYLOAD.get("payment_headers", []):
        ledger_name = clean(row.get("counter_account"))
        if ledger_name and (ledger_name in BANK_OR_CASH_LEDGER_NAMES or ledger_name in LEDGER_PARENT_GROUP or ledger_name in ACCOUNT_ALIASES):
            ledger_names.add(ledger_name)

    for ledger_name in sorted(ledger_names):
        ensure_account_for_ledger(ledger_name)

    extra_accounts = {{
        CGST_ACCOUNT: ("CGST", "Duties & Taxes"),
        SGST_ACCOUNT: ("SGST", "Duties & Taxes"),
        "Punjab National Bank - VLA": ("Punjab National Bank", "Bank OD A/c"),
        "Punjab National Bank(3750) - VLA": ("Punjab National Bank(3750)", "Bank Accounts"),
        "Indian Bank - VLA": ("Indian Bank", "Bank Accounts"),
    }}
    for full_name, (ledger_name, parent_group) in extra_accounts.items():
        if frappe.db.exists("Account", full_name):
            continue
        LEDGER_PARENT_GROUP.setdefault(ledger_name, parent_group)
        ensure_account_for_ledger(ledger_name)


def opening_je_name():
    return ensure_single_name(
        "Journal Entry",
        [
            ["company", "=", PAYLOAD["company"]],
            ["posting_date", "=", PAYLOAD["opening_date"]],
            ["user_remark", "=", OPENING_JE_REMARK],
            ["docstatus", "!=", 2],
        ],
        "2025 opening journal entry",
    )


def opening_clearance_name():
    return ensure_single_name(
        "Journal Entry",
        [
            ["company", "=", PAYLOAD["company"]],
            ["posting_date", "=", PAYLOAD["opening_date"]],
            ["user_remark", "=", OPENING_CLEARANCE_REMARK],
            ["docstatus", "!=", 2],
        ],
        "2025 opening clearance journal entry",
    )


def opening_stock_name():
    return ensure_single_name(
        "Stock Reconciliation",
        [
            ["company", "=", PAYLOAD["company"]],
            ["posting_date", "=", PAYLOAD["opening_date"]],
            ["posting_time", "=", STOCK_POSTING_TIME],
            ["purpose", "=", "Opening Stock"],
            ["set_warehouse", "=", PAYLOAD["default_warehouse"]],
            ["expense_account", "=", TEMP_OPENING_ACCOUNT],
            ["docstatus", "!=", 2],
        ],
        "2025 opening stock reconciliation",
    )


def opening_row_from_raw(raw_value):
    amount = parse_decimal(raw_value)
    if amount < 0:
        return abs(amount), Decimal("0")
    if amount > 0:
        return Decimal("0"), abs(amount)
    return Decimal("0"), Decimal("0")


def build_opening_journal_rows():
    rows = []
    raw_total = Decimal("0")

    for row in PAYLOAD.get("ledger_rows", []):
        ledger_name = clean(row.get("ledger_name"))
        if not ledger_name or ledger_name == "Profit & Loss A/c":
            continue
        raw_value = parse_decimal(row.get("tally_opening_balance_value"))
        if raw_value == 0:
            continue
        debit, credit = opening_row_from_raw(raw_value)
        rows.append(
            {{
                "account": ensure_account_for_ledger(ledger_name),
                "debit_in_account_currency": debit,
                "credit_in_account_currency": credit,
                "user_remark": f"Tally opening ledger: {{ledger_name}}",
            }}
        )
        raw_total += raw_value

    for row in PAYLOAD.get("party_opening_rows", []):
        party_type = clean(row.get("party_type"))
        party = clean(row.get("party"))
        raw_value = parse_decimal(row.get("tally_opening_balance_value"))
        if not party or raw_value == 0:
            continue
        if party_type == "Customer":
            account = "Debtors - VLA"
            ensure_party("Customer", party)
        else:
            account = "Creditors - VLA"
            ensure_party("Supplier", party)
        debit, credit = opening_row_from_raw(raw_value)
        rows.append(
            {{
                "account": account,
                "party_type": party_type,
                "party": party,
                "debit_in_account_currency": debit,
                "credit_in_account_currency": credit,
                "user_remark": f"Tally opening party: {{party_type}} {{party}}",
            }}
        )
        raw_total += raw_value

    balance_debit, balance_credit = opening_row_from_raw(-raw_total)
    rows.append(
        {{
            "account": TEMP_OPENING_ACCOUNT,
            "debit_in_account_currency": balance_debit,
            "credit_in_account_currency": balance_credit,
            "user_remark": "Balance Tally opening journal against Temporary Opening",
        }}
    )
    return rows, raw_total


def build_opening_stock_items():
    items = []
    raw_stock_total = Decimal("0")
    for row in PAYLOAD.get("opening_stock_rows", []):
        qty = abs(parse_decimal(row.get("qty")))
        valuation_rate = abs(parse_decimal(row.get("valuation_rate")))
        if qty == 0:
            continue
        items.append(
            {{
                "item_code": clean(row.get("item_code")),
                "warehouse": clean(row.get("warehouse")) or PAYLOAD["default_warehouse"],
                "qty": qty,
                "valuation_rate": valuation_rate,
                "allow_zero_valuation_rate": 1 if valuation_rate == 0 else 0,
            }}
        )
        raw_stock_total += parse_decimal(row.get("amount") or row.get("tally_opening_value"))
    return items, raw_stock_total


def fallback_valuation_rates_from_history():
    opening_qty_by_item = defaultdict(Decimal)
    purchase_rate_by_item = {{}}
    movement_rows_by_item = defaultdict(list)

    for row in PAYLOAD.get("opening_stock_rows", []):
        item_code = clean(row.get("item_code"))
        qty = abs(parse_decimal(row.get("qty")))
        if item_code and qty:
            opening_qty_by_item[item_code] += qty

    for row in PAYLOAD.get("purchase_items", []):
        item_code = clean(row.get("item_code"))
        qty = abs(parse_decimal(row.get("qty")))
        amount = abs(parse_decimal(row.get("base_amount")))
        rate = Decimal("0") if qty == 0 else (amount / qty)
        if not item_code or qty == 0:
            continue
        movement_rows_by_item[item_code].append(
            (
                clean(row.get("posting_date")),
                int(clean(row.get("voucher_key")) or "0"),
                "Purchase",
                qty,
            )
        )
        if rate and item_code not in purchase_rate_by_item:
            purchase_rate_by_item[item_code] = rate

    for row in PAYLOAD.get("sales_items", []):
        item_code = clean(row.get("item_code"))
        qty = abs(parse_decimal(row.get("qty")))
        if not item_code or qty == 0:
            continue
        movement_rows_by_item[item_code].append(
            (
                clean(row.get("posting_date")),
                int(clean(row.get("voucher_key")) or "0"),
                "Sales",
                -qty,
            )
        )

    for row in PAYLOAD.get("credit_items", []):
        item_code = clean(row.get("item_code"))
        qty = abs(parse_decimal(row.get("qty")))
        if not item_code or qty == 0:
            continue
        movement_rows_by_item[item_code].append(
            (
                clean(row.get("posting_date")),
                int(clean(row.get("voucher_key")) or "0"),
                "Credit Note",
                qty,
            )
        )

    fallback_rates = {{}}
    for item_code, movement_rows in movement_rows_by_item.items():
        if opening_qty_by_item.get(item_code):
            continue

        movement_rows.sort(key=lambda row: (row[0], row[1], row[2]))
        seen_incoming_qty = False
        for _posting_date, _voucher_key, voucher_type, qty in movement_rows:
            if qty > 0:
                seen_incoming_qty = True
                break
            if qty < 0 and not seen_incoming_qty:
                fallback_rate = purchase_rate_by_item.get(item_code)
                if fallback_rate:
                    fallback_rates[item_code] = fallback_rate
                break

    return fallback_rates


def ensure_item_fallback_valuation_rates(stats):
    fallback_rates = fallback_valuation_rates_from_history()
    stats["fallback_item_rates_needed_count"] = len(fallback_rates)
    stats["fallback_item_rates_updated_count"] = 0
    stats["fallback_item_rates_existing_count"] = 0
    stats["fallback_item_rates_examples"] = []

    for item_code, fallback_rate in sorted(fallback_rates.items()):
        current_rate = parse_decimal(frappe.db.get_value("Item", item_code, "valuation_rate"))
        if current_rate > 0:
            stats["fallback_item_rates_existing_count"] += 1
            continue
        if APPLY:
            item_doc = frappe.get_doc("Item", item_code)
            item_doc.valuation_rate = float(fallback_rate)
            item_doc.save(ignore_permissions=True)
        stats["fallback_item_rates_updated_count"] += 1
        if len(stats["fallback_item_rates_examples"]) < 10:
            stats["fallback_item_rates_examples"].append(
                {{
                    "item_code": item_code,
                    "valuation_rate": decimal_text(fallback_rate),
                }}
            )


def upsert_opening_documents(stats):
    journal_rows, raw_opening_total = build_opening_journal_rows()
    stock_items, raw_stock_total = build_opening_stock_items()
    combined_raw = raw_opening_total + raw_stock_total

    name = opening_je_name()
    if not name and APPLY:
        doc = frappe.get_doc(
            {{
                "doctype": "Journal Entry",
                "voucher_type": "Opening Entry",
                "company": PAYLOAD["company"],
                "posting_date": PAYLOAD["opening_date"],
                "user_remark": OPENING_JE_REMARK,
                "remark": OPENING_JE_REMARK,
                "title": "Tally FY2025 Opening",
                "accounts": journal_rows,
            }}
        )
        doc.insert(ignore_permissions=True)
        doc.submit()
        name = doc.name

    stock_name = opening_stock_name()
    if not stock_name and APPLY:
        doc = frappe.get_doc(
            {{
                "doctype": "Stock Reconciliation",
                "company": PAYLOAD["company"],
                "purpose": "Opening Stock",
                "posting_date": PAYLOAD["opening_date"],
                "posting_time": STOCK_POSTING_TIME,
                "set_posting_time": 1,
                "set_warehouse": PAYLOAD["default_warehouse"],
                "expense_account": TEMP_OPENING_ACCOUNT,
                "items": stock_items,
            }}
        )
        doc.insert(ignore_permissions=True)
        doc.submit()
        stock_name = doc.name

    clearance_name = opening_clearance_name()
    if not clearance_name and APPLY and combined_raw != 0:
        temp_debit, temp_credit = opening_row_from_raw(combined_raw)
        reserve_debit, reserve_credit = opening_row_from_raw(-combined_raw)
        doc = frappe.get_doc(
            {{
                "doctype": "Journal Entry",
                "voucher_type": "Opening Entry",
                "company": PAYLOAD["company"],
                "posting_date": PAYLOAD["opening_date"],
                "user_remark": OPENING_CLEARANCE_REMARK,
                "remark": OPENING_CLEARANCE_REMARK,
                "title": "Tally FY2025 Opening Clearance",
                "accounts": [
                    {{
                        "account": TEMP_OPENING_ACCOUNT,
                        "debit_in_account_currency": temp_debit,
                        "credit_in_account_currency": temp_credit,
                    }},
                    {{
                        "account": RESERVES_ACCOUNT,
                        "debit_in_account_currency": reserve_debit,
                        "credit_in_account_currency": reserve_credit,
                    }},
                ],
            }}
        )
        doc.insert(ignore_permissions=True)
        doc.submit()
        clearance_name = doc.name

    stats["opening"] = {{
        "journal_name": name,
        "stock_name": stock_name,
        "clearance_name": clearance_name,
        "raw_opening_total": decimal_text(raw_opening_total),
        "raw_stock_total": decimal_text(raw_stock_total),
        "combined_raw": decimal_text(combined_raw),
        "journal_line_count": len(journal_rows),
        "stock_item_count": len(stock_items),
    }}


def existing_doc_by_remark(doctype, remark):
    return ensure_single_name(
        doctype,
        [
            ["company", "=", PAYLOAD["company"]],
            ["remarks", "=", remark],
            ["docstatus", "!=", 2],
        ],
        f"{{doctype}} tagged {{remark}}",
    )


def current_allow_negative_stock():
    return int(frappe.db.get_single_value("Stock Settings", "allow_negative_stock") or 0)


def set_allow_negative_stock(enabled):
    settings = frappe.get_single("Stock Settings")
    settings.allow_negative_stock = 1 if enabled else 0
    settings.save(ignore_permissions=True)
    frappe.clear_cache()


def ensure_invoice_party(voucher_type, party_name):
    if voucher_type == "Purchase":
        return ensure_party("Supplier", party_name), "Supplier"
    return ensure_party("Customer", party_name), "Customer"


def grouped_items(item_rows):
    rows_by_key = defaultdict(list)
    for row in item_rows:
        rows_by_key[clean(row.get("voucher_key"))].append(row)
    return rows_by_key


def grouped_rows(rows):
    rows_by_key = defaultdict(list)
    for row in rows:
        rows_by_key[clean(row.get("voucher_key"))].append(row)
    return rows_by_key


def safe_int(value):
    text = clean(value)
    try:
        return int(text)
    except ValueError:
        return 0


def parse_tally_tag(remark):
    text = clean(remark)
    if not text.startswith("[") or not text.endswith("]"):
        return {{}}
    parts = text[1:-1].split("][")
    if len(parts) < 5 or parts[0] != "TALLY":
        return {{}}
    return {{
        "kind": parts[1],
        "voucher_type": parts[2],
        "voucher_key": parts[3],
        "voucher_number": "][".join(parts[4:]),
    }}


def existing_journal_by_user_remark(remark):
    return ensure_single_name(
        "Journal Entry",
        [
            ["company", "=", PAYLOAD["company"]],
            ["user_remark", "=", remark],
            ["docstatus", "!=", 2],
        ],
        f"Journal Entry tagged {{remark}}",
    )


def purchase_invoice_bill_no(header):
    return clean(header.get("external_reference"))


def sync_purchase_invoice_metadata(name, header, stats):
    bill_no = purchase_invoice_bill_no(header)
    if not bill_no:
        return
    current_bill_no = clean(frappe.db.get_value("Purchase Invoice", name, "bill_no"))
    if current_bill_no == bill_no:
        record_result(stats, "purchase_bill_no_existing", name)
        return
    if current_bill_no and current_bill_no != bill_no:
        record_result(stats, "purchase_bill_no_conflicts", f"{{name}}:{{current_bill_no}}!= {{bill_no}}")
        return
    if not APPLY:
        record_result(stats, "purchase_bill_no_pending", f"{{name}} -> {{bill_no}}")
        return
    frappe.db.set_value("Purchase Invoice", name, "bill_no", bill_no, update_modified=False)
    record_result(stats, "purchase_bill_no_updated", f"{{name}} -> {{bill_no}}")


def sync_existing_purchase_invoice_metadata(stats):
    headers_by_key = {{
        clean(row.get("voucher_key")): row
        for row in PAYLOAD.get("purchase_headers", [])
        if clean(row.get("voucher_key"))
    }}
    if not headers_by_key:
        return
    for key in [
        "purchase_bill_no_existing",
        "purchase_bill_no_pending",
        "purchase_bill_no_updated",
        "purchase_bill_no_conflicts",
    ]:
        stats.setdefault(f"{{key}}_count", 0)
        stats.setdefault(f"{{key}}_examples", [])
    docs = frappe.get_all(
        "Purchase Invoice",
        filters=[["company", "=", PAYLOAD["company"]], ["docstatus", "=", 1]],
        fields=["name", "remarks"],
        limit_page_length=0,
    )
    for doc in docs:
        tag = parse_tally_tag(doc.get("remarks"))
        if tag.get("kind") != "purchase-invoice":
            continue
        header = headers_by_key.get(tag.get("voucher_key"))
        if not header:
            continue
        sync_purchase_invoice_metadata(doc["name"], header, stats)


def build_invoice_registry():
    purchase_headers_by_key = {{
        clean(row.get("voucher_key")): row
        for row in PAYLOAD.get("purchase_headers", [])
        if clean(row.get("voucher_key"))
    }}
    registry = {{
        "sales_by_party": defaultdict(list),
        "purchase_by_party": defaultdict(list),
        "sales_by_tally_number": {{}},
        "purchase_by_bill_no": {{}},
        "sales_by_tally_number_global": defaultdict(list),
        "purchase_by_bill_no_global": defaultdict(list),
        "purchase_by_tally_number": {{}},
        "purchase_by_tally_number_global": defaultdict(list),
    }}

    sales_docs = frappe.get_all(
        "Sales Invoice",
        filters=[["company", "=", PAYLOAD["company"]], ["docstatus", "=", 1], ["is_return", "=", 0]],
        fields=["name", "posting_date", "customer", "remarks", "outstanding_amount"],
        limit_page_length=0,
    )
    for doc in sales_docs:
        tag = parse_tally_tag(doc.get("remarks"))
        invoice = {{
            "doctype": "Sales Invoice",
            "name": doc["name"],
            "party": clean(doc.get("customer")),
            "posting_date": clean(doc.get("posting_date")),
            "remaining": abs(parse_decimal(doc.get("outstanding_amount"))),
            "tally_voucher_number": clean(tag.get("voucher_number")),
            "bill_no": "",
        }}
        registry["sales_by_party"][invoice["party"]].append(invoice)
        if invoice["tally_voucher_number"]:
            registry["sales_by_tally_number"][(invoice["party"], invoice["tally_voucher_number"])] = invoice
            registry["sales_by_tally_number_global"][invoice["tally_voucher_number"]].append(invoice)

    purchase_docs = frappe.get_all(
        "Purchase Invoice",
        filters=[["company", "=", PAYLOAD["company"]], ["docstatus", "=", 1]],
        fields=["name", "posting_date", "supplier", "remarks", "bill_no", "outstanding_amount"],
        limit_page_length=0,
    )
    for doc in purchase_docs:
        tag = parse_tally_tag(doc.get("remarks"))
        staged_header = purchase_headers_by_key.get(clean(tag.get("voucher_key")))
        bill_no = clean(doc.get("bill_no")) or purchase_invoice_bill_no(staged_header or {{}})
        invoice = {{
            "doctype": "Purchase Invoice",
            "name": doc["name"],
            "party": clean(doc.get("supplier")),
            "posting_date": clean(doc.get("posting_date")),
            "remaining": abs(parse_decimal(doc.get("outstanding_amount"))),
            "tally_voucher_number": clean(tag.get("voucher_number")),
            "bill_no": bill_no,
        }}
        registry["purchase_by_party"][invoice["party"]].append(invoice)
        if invoice["tally_voucher_number"]:
            registry["purchase_by_tally_number"][(invoice["party"], invoice["tally_voucher_number"])] = invoice
            registry["purchase_by_tally_number_global"][invoice["tally_voucher_number"]].append(invoice)
        if invoice["bill_no"]:
            registry["purchase_by_bill_no"][(invoice["party"], invoice["bill_no"])] = invoice
            registry["purchase_by_bill_no_global"][invoice["bill_no"]].append(invoice)

    for key in ["sales_by_party", "purchase_by_party"]:
        for party, invoices in registry[key].items():
            invoices.sort(key=lambda row: (row["posting_date"], row["name"]))

    return registry


def reference_invoice(registry, party_type, party, reference_name):
    ref_name = clean(reference_name)
    if not ref_name:
        return None
    if party_type == "Customer":
        invoice = registry["sales_by_tally_number"].get((party, ref_name))
        if invoice:
            return invoice
        matches = registry["sales_by_tally_number_global"].get(ref_name, [])
        return matches[0] if len(matches) == 1 else None
    invoice = registry["purchase_by_bill_no"].get((party, ref_name))
    if invoice:
        return invoice
    matches = registry["purchase_by_bill_no_global"].get(ref_name, [])
    if len(matches) == 1:
        return matches[0]
    invoice = registry["purchase_by_tally_number"].get((party, ref_name))
    if invoice:
        return invoice
    matches = registry["purchase_by_tally_number_global"].get(ref_name, [])
    return matches[0] if len(matches) == 1 else None


def invoice_candidates(registry, party_type, party, posting_date):
    key = "sales_by_party" if party_type == "Customer" else "purchase_by_party"
    return [
        invoice
        for invoice in registry[key].get(party, [])
        if invoice["posting_date"] <= posting_date and invoice["remaining"] > 0
    ]


def payment_reference_row(invoice, allocated_amount):
    row = {{
        "reference_doctype": invoice["doctype"],
        "reference_name": invoice["name"],
        "allocated_amount": allocated_amount,
    }}
    if invoice.get("bill_no"):
        row["bill_no"] = invoice["bill_no"]
    return row


def allocate_to_invoice(invoice, amount):
    allocated = min(amount, invoice["remaining"])
    if allocated <= 0:
        return Decimal("0")
    invoice["remaining"] -= allocated
    if abs(invoice["remaining"]) < Decimal("0.005"):
        invoice["remaining"] = Decimal("0")
    return allocated


def allocation_strategy():
    strategy = clean(PAYLOAD.get("allocation_strategy"))
    return strategy or "exact_unique"


def allocate_unreferenced_amount(registry, party_type, party, posting_date, amount, stats, voucher_number):
    references = []
    strategy = allocation_strategy()
    if amount <= 0 or strategy == "none":
        return references, amount

    candidates = invoice_candidates(registry, party_type, party, posting_date)
    exact = [invoice for invoice in candidates if invoice["remaining"] == amount]
    if len(exact) == 1:
        allocated = allocate_to_invoice(exact[0], amount)
        if allocated:
            references.append(payment_reference_row(exact[0], allocated))
            record_result(stats, "settlement_exact_unique_allocations", f"{{voucher_number}} -> {{exact[0]['name']}}")
            return references, amount - allocated
    if strategy != "fifo":
        return references, amount

    remaining = amount
    for invoice in candidates:
        if remaining <= 0:
            break
        allocated = allocate_to_invoice(invoice, remaining)
        if not allocated:
            continue
        references.append(payment_reference_row(invoice, allocated))
        record_result(
            stats,
            "settlement_fifo_allocations",
            f"{{voucher_number}} -> {{invoice['name']}}:{{decimal_text(allocated)}}",
        )
        remaining -= allocated
    return references, remaining


def invoice_items_payload(item_rows, is_return=False):
    items = []
    for row in item_rows:
        qty = abs(parse_decimal(row.get("qty")))
        amount = abs(parse_decimal(row.get("base_amount")))
        rate = Decimal("0") if qty == 0 else (amount / qty)
        if is_return:
            qty = -qty
        payload = {{
            "item_code": clean(row.get("item_code")),
            "description": clean(row.get("item_code")),
            "qty": qty,
            "rate": rate,
            "warehouse": clean(row.get("erpnext_warehouse")) or PAYLOAD["default_warehouse"],
        }}
        if is_return:
            payload["allow_zero_valuation_rate"] = 1
        income_or_expense = clean(row.get("income_or_expense_account"))
        if income_or_expense:
            payload["income_account" if not is_return else "income_account"] = income_or_expense
            payload["expense_account"] = "Stock Adjustment - VLA"
        items.append(payload)
    return items


def tax_rows(header, sign=1):
    rows = []
    cgst_total = parse_decimal(header.get("cgst_total")) * sign
    sgst_total = parse_decimal(header.get("sgst_total")) * sign
    round_off = parse_decimal(header.get("round_off_amount")) * sign
    if cgst_total:
        rows.append({{"charge_type": "Actual", "account_head": CGST_ACCOUNT, "tax_amount": cgst_total, "description": "CGST"}})
    if sgst_total:
        rows.append({{"charge_type": "Actual", "account_head": SGST_ACCOUNT, "tax_amount": sgst_total, "description": "SGST"}})
    if round_off:
        rows.append({{"charge_type": "Actual", "account_head": ROUND_OFF_ACCOUNT, "tax_amount": round_off, "description": "Round Off"}})
    return rows


def create_cash_sale_receipt(invoice_doc, header):
    remark = invoice_tag("cash-sale-receipt", "Receipt", clean(header.get("voucher_key")), clean(header.get("voucher_number")))
    existing = existing_doc_by_remark("Payment Entry", remark)
    if existing:
        return existing
    if not APPLY:
        return None

    amount = abs(parse_decimal(header.get("rounded_grand_total") or header.get("grand_total")))
    doc = frappe.get_doc(
        {{
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "company": PAYLOAD["company"],
            "posting_date": clean(header.get("posting_date")),
            "party_type": "Customer",
            "party": "Cash",
            "paid_from": "Debtors - VLA",
            "paid_to": "Cash - VLA",
            "paid_amount": amount,
            "received_amount": amount,
            "remarks": remark,
            "mode_of_payment": "Cash",
            "references": [
                {{
                    "reference_doctype": "Sales Invoice",
                    "reference_name": invoice_doc.name,
                    "allocated_amount": amount,
                }}
            ],
        }}
    )
    try:
        doc.insert(ignore_permissions=True)
        doc.submit()
    except Exception as exc:
        raise RuntimeError(
            f"Failed cash sale receipt for Sales Invoice {{invoice_doc.name}} "
            f"(voucher {{clean(header.get('voucher_number'))}} / {{clean(header.get('voucher_key'))}})"
        ) from exc
    return doc.name


def create_sales_invoice(header, item_rows, stats, is_return=False):
    voucher_key = clean(header.get("voucher_key"))
    voucher_number = clean(header.get("voucher_number"))
    remark = invoice_tag("sales-invoice", clean(header.get("voucher_type")), voucher_key, voucher_number)
    existing = existing_doc_by_remark("Sales Invoice", remark)
    if existing:
        record_result(stats, "sales_existing", existing)
        return existing

    party = clean(header.get("party"))
    if party == "Cash":
        party = "Cash"
    if not item_rows:
        record_result(stats, "sales_skipped_without_items", voucher_number)
        return None
    ensure_party("Customer", party)
    if not APPLY:
        record_result(stats, "sales_pending", voucher_number)
        return None

    doc = frappe.get_doc(
        {{
            "doctype": "Sales Invoice",
            "company": PAYLOAD["company"],
            "posting_date": clean(header.get("posting_date")),
            "due_date": clean(header.get("posting_date")),
            "set_posting_time": 1,
            "customer": party,
            "debit_to": "Debtors - VLA",
            "update_stock": 1,
            "is_return": 1 if is_return else 0,
            "remarks": remark,
            "items": invoice_items_payload(item_rows, is_return=is_return),
            "taxes": tax_rows(header, sign=-1 if is_return else 1),
        }}
    )
    try:
        doc.insert(ignore_permissions=True)
        doc.submit()
    except Exception as exc:
        invoice_kind = "Credit Note" if is_return else "Sales Invoice"
        raise RuntimeError(
            f"Failed {{invoice_kind}} {{voucher_number}} "
            f"(voucher_key={{voucher_key}}, posting_date={{clean(header.get('posting_date'))}}, party={{party}})"
        ) from exc
    record_result(stats, "sales_created", doc.name)
    if clean(header.get("party")) == "Cash" and not is_return:
        cash_receipt_name = create_cash_sale_receipt(doc, header)
        if cash_receipt_name:
            record_result(stats, "cash_sale_receipts", cash_receipt_name)
    return doc.name


def create_purchase_invoice(header, item_rows, stats):
    voucher_key = clean(header.get("voucher_key"))
    voucher_number = clean(header.get("voucher_number"))
    remark = invoice_tag("purchase-invoice", clean(header.get("voucher_type")), voucher_key, voucher_number)
    existing = existing_doc_by_remark("Purchase Invoice", remark)
    if existing:
        sync_purchase_invoice_metadata(existing, header, stats)
        record_result(stats, "purchase_existing", existing)
        return existing

    party = clean(header.get("party"))
    if not item_rows:
        record_result(stats, "purchase_skipped_without_items", voucher_number)
        return None
    ensure_party("Supplier", party)
    if not APPLY:
        record_result(stats, "purchase_pending", voucher_number)
        return None

    items = []
    for row in item_rows:
        qty = abs(parse_decimal(row.get("qty")))
        amount = abs(parse_decimal(row.get("base_amount")))
        rate = Decimal("0") if qty == 0 else (amount / qty)
        items.append(
            {{
                "item_code": clean(row.get("item_code")),
                "description": clean(row.get("item_code")),
                "qty": qty,
                "rate": rate,
                "warehouse": clean(row.get("erpnext_warehouse")) or PAYLOAD["default_warehouse"],
                "expense_account": "Stock Adjustment - VLA",
            }}
        )

    doc = frappe.get_doc(
        {{
            "doctype": "Purchase Invoice",
            "company": PAYLOAD["company"],
            "posting_date": clean(header.get("posting_date")),
            "due_date": clean(header.get("posting_date")),
            "set_posting_time": 1,
            "supplier": party,
            "credit_to": "Creditors - VLA",
            "update_stock": 1,
            "bill_no": purchase_invoice_bill_no(header),
            "remarks": remark,
            "items": items,
            "taxes": tax_rows(header, sign=1),
        }}
    )
    try:
        doc.insert(ignore_permissions=True)
        doc.submit()
    except Exception as exc:
        raise RuntimeError(
            f"Failed Purchase Invoice {{voucher_number}} "
            f"(voucher_key={{voucher_key}}, posting_date={{clean(header.get('posting_date'))}}, party={{party}})"
        ) from exc
    record_result(stats, "purchase_created", doc.name)
    return doc.name


def mode_of_payment_for_account(account_name):
    if account_name == CASH_ACCOUNT:
        return "Cash"
    return ""


def bank_reference_no(header):
    remarks = clean(header.get("remarks"))
    if remarks:
        return remarks[:140]
    voucher_key = clean(header.get("voucher_key"))
    if voucher_key:
        return voucher_key[:140]
    return clean(header.get("voucher_number"))[:140]


def can_use_payment_entry(header):
    return (
        clean(header.get("party_type")) in {{"Customer", "Supplier"}}
        and clean(header.get("counter_account")) in BANK_OR_CASH_LEDGER_NAMES
        and safe_int(header.get("line_count")) == 2
    )


def split_party_payment_groups(header, settlement_lines):
    voucher_type = clean(header.get("voucher_type"))
    lines = sorted(settlement_lines, key=lambda row: safe_int(row.get("line_no")))
    if not lines:
        return []

    bank_lines = [row for row in lines if clean(row.get("is_bank_row")) == "1"]
    if len(bank_lines) != 1:
        return []

    money_ledger = clean(bank_lines[0].get("ledger_name"))
    if money_ledger not in BANK_OR_CASH_LEDGER_NAMES:
        return []

    bank_total = abs(parse_decimal(bank_lines[0].get("amount")))
    party_totals = defaultdict(Decimal)
    party_order = []
    non_bank_total = Decimal("0")

    for row in lines:
        if clean(row.get("is_bank_row")) == "1":
            continue
        party_type = clean(row.get("party_type"))
        party = clean(row.get("ledger_name"))
        amount = parse_decimal(row.get("amount"))
        if party_type not in {{"Customer", "Supplier"}} or not party or amount == 0:
            return []
        if voucher_type == "Receipt" and amount < 0:
            return []
        if voucher_type == "Payment" and amount > 0:
            return []
        key = (party_type, party)
        if key not in party_totals:
            party_order.append(key)
        party_totals[key] += abs(amount)
        non_bank_total += abs(amount)

    if not party_totals or abs(non_bank_total - bank_total) >= Decimal("0.01"):
        return []

    groups = []
    voucher_number = clean(header.get("voucher_number"))
    for index, (party_type, party) in enumerate(party_order, start=1):
        groups.append(
            {{
                "party_type": party_type,
                "party": party,
                "amount": party_totals[(party_type, party)],
                "money_ledger": money_ledger,
                "remark_token": f"{{voucher_number}}|split|{{index}}|{{party}}",
            }}
        )
    return groups


def existing_payment_entry_by_signature(posting_date, party_type, party, payment_type, paid_from, paid_to, amount, reference_no=""):
    filters = [
        ["company", "=", PAYLOAD["company"]],
        ["docstatus", "!=", 2],
        ["posting_date", "=", posting_date],
        ["party_type", "=", party_type],
        ["party", "=", party],
        ["payment_type", "=", payment_type],
        ["paid_from", "=", paid_from],
        ["paid_to", "=", paid_to],
        ["paid_amount", "=", amount],
        ["received_amount", "=", amount],
    ]
    if reference_no:
        filters.append(["reference_no", "=", reference_no])
    names = frappe.get_all("Payment Entry", filters=filters, pluck="name")
    return names[0] if len(names) == 1 else None


def create_payment_entry_for_party(header, reference_rows, stats, registry, *, party_type, party, money_ledger, amount, remark_token):
    voucher_type = clean(header.get("voucher_type"))
    voucher_key = clean(header.get("voucher_key"))
    voucher_number = clean(header.get("voucher_number"))
    kind = "party-receipt" if voucher_type == "Receipt" else "party-payment"
    remark = invoice_tag(kind, voucher_type, voucher_key, remark_token)

    ensure_party("Customer" if party_type == "Customer" else "Supplier", party)
    money_account = ensure_account_for_ledger(money_ledger)
    party_account = DEBTORS_ACCOUNT if party_type == "Customer" else CREDITORS_ACCOUNT
    payment_type = "Receive" if voucher_type == "Receipt" else "Pay"
    paid_from = party_account if voucher_type == "Receipt" else money_account
    paid_to = money_account if voucher_type == "Receipt" else party_account
    reference_no = bank_reference_no(header) if money_account != CASH_ACCOUNT else ""

    existing = existing_doc_by_remark("Payment Entry", remark) or existing_payment_entry_by_signature(
        clean(header.get("posting_date")),
        party_type,
        party,
        payment_type,
        paid_from,
        paid_to,
        amount,
        reference_no,
    )
    if existing:
        record_result(stats, "settlement_payment_existing", existing)
        return existing

    references = []
    remaining = amount

    for ref_row in reference_rows:
        if remaining <= 0:
            break
        reference_name = clean(ref_row.get("reference_name"))
        invoice = reference_invoice(registry, party_type, party, reference_name)
        if not invoice:
            record_result(
                stats,
                "settlement_unresolved_references",
                f"{{voucher_type}} {{voucher_number}} {{party}} -> {{reference_name}}",
            )
            continue
        allocated = allocate_to_invoice(invoice, min(abs(parse_decimal(ref_row.get("allocated_amount"))), remaining))
        if not allocated:
            continue
        references.append(payment_reference_row(invoice, allocated))
        remaining -= allocated
        if remaining < 0:
            remaining = Decimal("0")
        record_result(
            stats,
            "settlement_explicit_reference_allocations",
            f"{{voucher_number}} -> {{invoice['name']}}:{{decimal_text(allocated)}}",
        )

    extra_refs, remaining = allocate_unreferenced_amount(
        registry,
        party_type,
        party,
        clean(header.get("posting_date")),
        remaining,
        stats,
        voucher_number,
    )
    references.extend(extra_refs)
    if remaining < Decimal("0.005"):
        remaining = Decimal("0")
    if remaining > 0:
        record_result(
            stats,
            "settlement_unallocated_entries",
            f"{{voucher_type}} {{voucher_number}} {{party}}:{{decimal_text(remaining)}}",
        )

    payload = {{
        "doctype": "Payment Entry",
        "company": PAYLOAD["company"],
        "posting_date": clean(header.get("posting_date")),
        "party_type": party_type,
        "party": party,
        "paid_amount": amount,
        "received_amount": amount,
        "remarks": remark,
    }}
    payload["payment_type"] = payment_type
    payload["paid_from"] = paid_from
    payload["paid_to"] = paid_to
    mode_of_payment = mode_of_payment_for_account(money_account)
    if mode_of_payment:
        payload["mode_of_payment"] = mode_of_payment
    if money_account != CASH_ACCOUNT:
        payload["reference_no"] = reference_no
        payload["reference_date"] = clean(header.get("posting_date"))
    if references:
        payload["references"] = references

    if not APPLY:
        record_result(stats, "settlement_payment_pending", remark_token)
        return None

    doc = frappe.get_doc(payload)
    try:
        doc.insert(ignore_permissions=True)
        doc.submit()
    except Exception as exc:
        raise RuntimeError(
            f"Failed {{voucher_type}} Payment Entry {{voucher_number}} "
            f"(voucher_key={{voucher_key}}, party={{party}}, account={{money_account}})"
        ) from exc
    record_result(stats, "settlement_payment_created", doc.name)
    return doc.name


def create_party_payment_entry(header, reference_rows, settlement_lines, stats, registry):
    voucher_type = clean(header.get("voucher_type"))
    voucher_number = clean(header.get("voucher_number"))
    party_type = clean(header.get("party_type"))
    party = clean(header.get("party"))
    money_ledger = clean(header.get("counter_account"))
    amount = abs(parse_decimal(header.get("paid_amount")))

    if can_use_payment_entry(header):
        return create_payment_entry_for_party(
            header,
            reference_rows,
            stats,
            registry,
            party_type=party_type,
            party=party,
            money_ledger=money_ledger,
            amount=amount,
            remark_token=voucher_number,
        )

    split_groups = split_party_payment_groups(header, settlement_lines)
    if split_groups:
        record_result(
            stats,
            "settlement_split_party_headers_processed",
            f"{{voucher_type}} {{voucher_number}} -> {{len(split_groups)}} splits",
        )
        last_result = None
        for group in split_groups:
            group_reference_rows = (
                reference_rows
                if clean(group.get("party_type")) == party_type and clean(group.get("party")) == party
                else []
            )
            last_result = create_payment_entry_for_party(
                header,
                group_reference_rows,
                stats,
                registry,
                party_type=clean(group.get("party_type")),
                party=clean(group.get("party")),
                money_ledger=clean(group.get("money_ledger")),
                amount=abs(parse_decimal(group.get("amount"))),
                remark_token=clean(group.get("remark_token")),
            )
        return last_result

    record_result(
        stats,
        "settlement_complex_party_headers_skipped",
        f"{{voucher_type}} {{voucher_number}} {{party}} -> {{money_ledger}}",
    )
    return None


def journal_account_row(account_name, debit, credit, party_type="", party=""):
    row = {{
        "account": account_name,
        "debit_in_account_currency": debit,
        "credit_in_account_currency": credit,
    }}
    if party_type and party:
        row["party_type"] = party_type
        row["party"] = party
    return row


def journal_row_for_ledger(ledger_name, party_type, debit, credit):
    party_type = clean(party_type)
    ledger_name = clean(ledger_name)
    if party_type == "Customer":
        ensure_party("Customer", ledger_name)
        return journal_account_row(DEBTORS_ACCOUNT, debit, credit, "Customer", ledger_name)
    if party_type == "Supplier":
        ensure_party("Supplier", ledger_name)
        return journal_account_row(CREDITORS_ACCOUNT, debit, credit, "Supplier", ledger_name)
    return journal_account_row(ensure_account_for_ledger(ledger_name), debit, credit)


def upsert_journal_entry(remark, posting_date, accounts, title, stats_prefix, stats, sample_value):
    debit_total = sum(parse_decimal(row.get("debit_in_account_currency")) for row in accounts)
    credit_total = sum(parse_decimal(row.get("credit_in_account_currency")) for row in accounts)
    if not accounts:
        record_result(stats, f"{{stats_prefix}}_skipped_without_lines", sample_value)
        return None
    if debit_total != credit_total:
        record_result(
            stats,
            f"{{stats_prefix}}_unbalanced",
            f"{{sample_value}}:{{decimal_text(debit_total)}}!= {{decimal_text(credit_total)}}",
        )
        return None

    existing = existing_journal_by_user_remark(remark)
    if existing:
        record_result(stats, f"{{stats_prefix}}_existing", existing)
        return existing
    if not APPLY:
        record_result(stats, f"{{stats_prefix}}_pending", sample_value)
        return None

    doc = frappe.get_doc(
        {{
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "company": PAYLOAD["company"],
            "posting_date": posting_date,
            "user_remark": remark,
            "remark": remark,
            "title": title[:140],
            "accounts": accounts,
        }}
    )
    try:
        doc.insert(ignore_permissions=True)
        doc.submit()
    except Exception as exc:
        raise RuntimeError(f"Failed Journal Entry {{sample_value}}") from exc
    record_result(stats, f"{{stats_prefix}}_created", doc.name)
    return doc.name


def create_non_party_money_journal(header, stats):
    voucher_type = clean(header.get("voucher_type"))
    voucher_key = clean(header.get("voucher_key"))
    voucher_number = clean(header.get("voucher_number"))
    party_ledger = clean(header.get("party"))
    counter_ledger = clean(header.get("counter_account"))
    amount = abs(parse_decimal(header.get("paid_amount")))
    if not party_ledger or not counter_ledger or not amount or party_ledger == counter_ledger:
        record_result(stats, "settlement_non_party_headers_skipped", voucher_number)
        return None

    party_account = ensure_account_for_ledger(party_ledger)
    counter_account = ensure_account_for_ledger(counter_ledger)
    if voucher_type == "Receipt":
        accounts = [
            journal_account_row(party_account, amount, Decimal("0")),
            journal_account_row(counter_account, Decimal("0"), amount),
        ]
    else:
        accounts = [
            journal_account_row(counter_account, amount, Decimal("0")),
            journal_account_row(party_account, Decimal("0"), amount),
        ]

    remark = invoice_tag("money-journal", voucher_type, voucher_key, voucher_number)
    return upsert_journal_entry(
        remark,
        clean(header.get("posting_date")),
        accounts,
        f"Tally {{voucher_type}} {{voucher_number}}",
        "settlement_non_party_journal",
        stats,
        voucher_number,
    )


def create_journal_voucher(lines, stats):
    lines = sorted(lines, key=lambda row: safe_int(row.get("line_no")))
    sample = lines[0] if lines else {{}}
    voucher_key = clean(sample.get("voucher_key"))
    voucher_number = clean(sample.get("voucher_number"))
    posting_date = clean(sample.get("posting_date"))
    accounts = []
    for line in lines:
        debit = abs(parse_decimal(line.get("debit")))
        credit = abs(parse_decimal(line.get("credit")))
        if debit == 0 and credit == 0:
            continue
        accounts.append(journal_row_for_ledger(clean(line.get("ledger_name")), clean(line.get("party_type")), debit, credit))

    remark = invoice_tag("journal-entry", "Journal", voucher_key, voucher_number)
    return upsert_journal_entry(
        remark,
        posting_date,
        accounts,
        f"Tally Journal {{voucher_number}}",
        "settlement_journal",
        stats,
        voucher_number,
    )


def upsert_invoice_history(stats):
    sales_items_by_key = grouped_items(PAYLOAD.get("sales_items", []))
    purchase_items_by_key = grouped_items(PAYLOAD.get("purchase_items", []))
    credit_items_by_key = grouped_items(PAYLOAD.get("credit_items", []))

    stock_vouchers = []
    for row in PAYLOAD.get("purchase_headers", []):
        stock_vouchers.append(("Purchase", clean(row.get("posting_date")), int(clean(row.get("voucher_key")) or "0"), row))
    for row in PAYLOAD.get("sales_headers", []):
        stock_vouchers.append(("Sales", clean(row.get("posting_date")), int(clean(row.get("voucher_key")) or "0"), row))
    for row in PAYLOAD.get("credit_headers", []):
        stock_vouchers.append(("Credit Note", clean(row.get("posting_date")), int(clean(row.get("voucher_key")) or "0"), row))
    stock_vouchers.sort(key=lambda row: (row[1], row[2], row[0]))

    for key in [
        "sales_created",
        "sales_existing",
        "sales_pending",
        "sales_skipped_without_items",
        "cash_sale_receipts",
        "purchase_created",
        "purchase_existing",
        "purchase_pending",
        "purchase_skipped_without_items",
    ]:
        stats[f"{{key}}_count"] = 0
        stats[f"{{key}}_examples"] = []

    total_vouchers = len(stock_vouchers)
    stats["invoice_history_total_vouchers"] = total_vouchers
    stats["invoice_history_processed_vouchers"] = 0

    for voucher_type, _posting_date, _voucher_key_int, header in stock_vouchers:
        voucher_key = clean(header.get("voucher_key"))
        if voucher_type == "Purchase":
            create_purchase_invoice(header, purchase_items_by_key[voucher_key], stats)
        elif voucher_type == "Sales":
            create_sales_invoice(header, sales_items_by_key[voucher_key], stats, is_return=False)
        else:
            create_sales_invoice(header, credit_items_by_key[voucher_key], stats, is_return=True)
        stats["invoice_history_processed_vouchers"] += 1
        maybe_commit_progress(
            stats,
            processed=stats["invoice_history_processed_vouchers"],
            total=total_vouchers,
        )


def upsert_settlements(stats):
    for key in [
        "settlement_payment_created",
        "settlement_payment_existing",
        "settlement_payment_pending",
        "settlement_split_party_headers_processed",
        "settlement_unallocated_entries",
        "settlement_explicit_reference_allocations",
        "settlement_unresolved_references",
        "settlement_exact_unique_allocations",
        "settlement_fifo_allocations",
        "settlement_complex_party_headers_skipped",
        "settlement_non_party_journal_created",
        "settlement_non_party_journal_existing",
        "settlement_non_party_journal_pending",
        "settlement_non_party_headers_skipped",
        "settlement_non_party_journal_unbalanced",
        "settlement_non_party_journal_skipped_without_lines",
        "settlement_journal_created",
        "settlement_journal_existing",
        "settlement_journal_pending",
        "settlement_journal_unbalanced",
        "settlement_journal_skipped_without_lines",
    ]:
        stats[f"{{key}}_count"] = 0
        stats[f"{{key}}_examples"] = []

    sync_existing_purchase_invoice_metadata(stats)
    registry = build_invoice_registry()
    receipt_refs_by_key = grouped_rows(PAYLOAD.get("receipt_refs", []))
    payment_refs_by_key = grouped_rows(PAYLOAD.get("payment_refs", []))
    settlement_lines_by_key = grouped_rows(PAYLOAD.get("settlement_lines", []))
    journal_lines_by_key = grouped_rows(PAYLOAD.get("journal_lines", []))

    money_vouchers = []
    for row in PAYLOAD.get("receipt_headers", []):
        money_vouchers.append((clean(row.get("posting_date")), safe_int(row.get("voucher_key")), "Receipt", row))
    for row in PAYLOAD.get("payment_headers", []):
        money_vouchers.append((clean(row.get("posting_date")), safe_int(row.get("voucher_key")), "Payment", row))
    money_vouchers.sort(key=lambda row: (row[0], row[1], row[2]))

    journal_vouchers = []
    for voucher_key, lines in journal_lines_by_key.items():
        sample = lines[0] if lines else {{}}
        journal_vouchers.append((clean(sample.get("posting_date")), safe_int(voucher_key), voucher_key, lines))
    journal_vouchers.sort(key=lambda row: (row[0], row[1], row[2]))

    total_vouchers = len(money_vouchers) + len(journal_vouchers)
    stats["settlement_allocation_strategy"] = allocation_strategy()
    stats["settlement_total_vouchers"] = total_vouchers
    stats["settlement_processed_vouchers"] = 0

    for _posting_date, _voucher_key_int, voucher_type, header in money_vouchers:
        party_type = clean(header.get("party_type"))
        if party_type in {{"Customer", "Supplier"}}:
            refs_by_key = receipt_refs_by_key if voucher_type == "Receipt" else payment_refs_by_key
            create_party_payment_entry(
                header,
                refs_by_key.get(clean(header.get("voucher_key")), []),
                settlement_lines_by_key.get(clean(header.get("voucher_key")), []),
                stats,
                registry,
            )
        else:
            create_non_party_money_journal(header, stats)
        stats["settlement_processed_vouchers"] += 1
        maybe_commit_progress(
            stats,
            processed=stats["settlement_processed_vouchers"],
            total=total_vouchers,
        )

    for _posting_date, _voucher_key_int, _voucher_key, lines in journal_vouchers:
        create_journal_voucher(lines, stats)
        stats["settlement_processed_vouchers"] += 1
        maybe_commit_progress(
            stats,
            processed=stats["settlement_processed_vouchers"],
            total=total_vouchers,
        )


stats = {{
    "site": SITE,
    "company": PAYLOAD["company"],
    "opening_date": PAYLOAD["opening_date"],
    "stage": PAYLOAD["stage"],
    "apply": APPLY,
}}

frappe.init(site=SITE, sites_path=".")
frappe.connect()
frappe.set_user("Administrator")
temporarily_enabled_negative_stock = False
try:
    ensure_base_setup()
    stages = stage_targets()
    if "invoices" in stages:
        original_allow_negative_stock = current_allow_negative_stock()
        stats["invoice_stock_policy"] = {{
            "allow_negative_stock_before_import": bool_text(bool(original_allow_negative_stock)),
            "temporarily_enabled_for_history_import": "0",
        }}
        ensure_item_fallback_valuation_rates(stats)
        if APPLY and not original_allow_negative_stock:
            set_allow_negative_stock(True)
            frappe.db.commit()
            temporarily_enabled_negative_stock = True
            stats["invoice_stock_policy"]["temporarily_enabled_for_history_import"] = "1"

    for stage in stages:
        if stage == "setup":
            stats["setup"] = {{
                "fiscal_year": "2025-2026",
            }}
        elif stage == "opening":
            upsert_opening_documents(stats)
        elif stage == "invoices":
            upsert_invoice_history(stats)
        elif stage == "settlements":
            upsert_settlements(stats)

    if APPLY:
        frappe.db.commit()

    stats["summary"] = {{
        "sales_invoice_count": frappe.db.count("Sales Invoice"),
        "purchase_invoice_count": frappe.db.count("Purchase Invoice"),
        "payment_entry_count": frappe.db.count("Payment Entry"),
        "journal_entry_count": frappe.db.count("Journal Entry"),
        "stock_reconciliation_count": frappe.db.count("Stock Reconciliation"),
        "gl_entry_count": frappe.db.count("GL Entry"),
        "stock_ledger_entry_count": frappe.db.count("Stock Ledger Entry"),
    }}
except Exception:
    if APPLY:
        frappe.db.rollback()
    raise
finally:
    try:
        if APPLY and temporarily_enabled_negative_stock:
            set_allow_negative_stock(False)
            frappe.db.commit()
    finally:
        frappe.destroy()

print(json.dumps(stats, indent=2, sort_keys=True))
"""


def run_in_container(site: str, payload: dict[str, object], apply: bool) -> None:
    code = server_code(site, payload, apply)
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
    payload = load_payload(args)
    run_in_container(args.site, payload, args.apply)
    if not args.apply:
        print("Dry run only. Re-run with --apply to create and submit ERPNext documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
