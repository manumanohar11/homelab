#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_XML_DIR = REPO_ROOT / "migration" / "tally" / "raw" / "XML"
DEFAULT_MASTER_JSON = REPO_ROOT / "migration" / "tally" / "raw" / "JSON" / "Master.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "migration" / "tally" / "output"
DEFAULT_REPORT_DIR = REPO_ROOT / "migration" / "tally" / "reports"


# ERPNext v15 posts Stock Reconciliation through a 2-decimal valuation-rate path.
# For this specific VLA cutover, these 1-paisa rate nudges make the posted stock
# ledger land on both the Tally closing stock total and the expected stock-group
# totals from the Stock Summary XML.
ERPNEXT_STOCK_RATE_ADJUSTMENTS = {
    "AGNI TEA 1KG M360": Decimal("-0.01"),
    "AMBICA FRUIT 3 IN 1 100G": Decimal("0.01"),
    "AMBICA NITYA POOJA 12G M10": Decimal("0.01"),
    "BANSI RAVVA 500G": Decimal("0.01"),
    "CS DARK SOY SAUCE 90GM M25": Decimal("0.01"),
    "DR PHENYLE 450ML M90": Decimal("-0.01"),
    "GK AGARBATTI PO12 M15": Decimal("-0.01"),
    "GK COIL M45": Decimal("-0.02"),
    "GODREJ AER SPRAY": Decimal("-0.01"),
    "MTR SAMBAR 100G M80": Decimal("0.01"),
    "RAGI FLOUR 500G": Decimal("0.01"),
    "TATA SALT 1KG": Decimal("0.01"),
}


ASSET_GROUPS = {
    "Bank Accounts",
    "Cash-in-Hand",
    "Current Assets",
    "Deposits (Asset)",
    "Fixed Assets",
    "Sundry Debtors",
}
LIABILITY_GROUPS = {
    "Bank OD A/c",
    "Current Liabilities",
    "Duties & Taxes",
    "Loans (Liability)",
    "Secured Loans",
    "Sundry Creditors",
    "Unsecured Loans",
}
EQUITY_GROUPS = {
    "Capital Account",
}
PNL_GROUPS = {
    "Direct Expenses",
    "Direct Incomes",
    "Indirect Expenses",
    "Indirect Incomes",
    "Purchase Accounts",
    "Rents",
    "Salaries Account",
    "Sales Accounts",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build ERPNext cutover review files from Tally Trial Balance and Stock Summary XML exports."
    )
    parser.add_argument("--xml-dir", type=Path, default=DEFAULT_XML_DIR)
    parser.add_argument("--master-json", type=Path, default=DEFAULT_MASTER_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--warehouse", default="Main Location - VLA")
    return parser.parse_args()


def read_xml(path: Path) -> ET.Element:
    return ET.fromstring(path.read_text(encoding="utf-16"))


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\x04", " ")).strip()


def parse_decimal(value: str | None) -> Decimal:
    text = clean_text(value).replace(",", "")
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def parse_quantity(value: str | None) -> tuple[Decimal, str]:
    text = clean_text(value)
    if not text:
        return Decimal("0"), ""
    match = re.match(r"^(-?\d+(?:\.\d+)?)\s*(.*)$", text)
    if not match:
        return Decimal("0"), ""
    try:
        quantity = Decimal(match.group(1))
    except InvalidOperation:
        quantity = Decimal("0")
    return quantity, clean_text(match.group(2))


def decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: clean_text(str(row.get(field, ""))) for field in fieldnames})


def load_item_metadata(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return {
            row["item_code"]: {
                "item_group": row["item_group"],
                "stock_uom": row["stock_uom"],
            }
            for row in csv.DictReader(file)
        }


def load_master_messages(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-16") as file:
        payload = json.load(file)
    messages = payload.get("tallymessage")
    if not isinstance(messages, list):
        raise ValueError(f"{path} does not have a tallymessage list")
    return [message for message in messages if isinstance(message, dict)]


def meta_block(message: dict) -> dict:
    metadata = message.get("metadata")
    if isinstance(metadata, list):
        for entry in metadata:
            if isinstance(entry, dict):
                return entry
        return {}
    if isinstance(metadata, dict):
        return metadata
    return {}


def meta_type(message: dict) -> str:
    return clean_text(meta_block(message).get("type"))


def meta_name(message: dict) -> str:
    return clean_text(meta_block(message).get("name"))


def load_ledger_groups(path: Path) -> dict[str, str]:
    ledger_groups: dict[str, str] = {}
    for message in load_master_messages(path):
        if meta_type(message) != "Ledger":
            continue
        name = meta_name(message)
        if not name:
            continue
        ledger_groups[name] = clean_text(message.get("parent"))
    return ledger_groups


def parse_stock_summary(stock_xml: Path) -> list[dict[str, str]]:
    root = read_xml(stock_xml)
    names = root.findall(".//DSPACCNAME")
    infos = root.findall(".//DSPSTKINFO")
    rows: list[dict[str, str]] = []
    for name_node, info_node in zip(names, infos, strict=True):
        item_code = clean_text(name_node.findtext("DSPDISPNAME"))
        closing_qty_text = clean_text(info_node.findtext(".//DSPCLQTY"))
        closing_rate_text = clean_text(info_node.findtext(".//DSPCLRATE"))
        closing_amount_text = clean_text(info_node.findtext(".//DSPCLAMTA"))
        rows.append(
            {
                "item_code": item_code,
                "closing_qty_text": closing_qty_text,
                "closing_rate_text": closing_rate_text,
                "closing_amount_text": closing_amount_text,
            }
        )
    return rows


def parse_trial_balance(trial_xml: Path) -> list[dict[str, str]]:
    root = read_xml(trial_xml)
    names = root.findall(".//DSPACCNAME")
    infos = root.findall(".//DSPACCINFO")
    rows: list[dict[str, str]] = []
    for name_node, info_node in zip(names, infos, strict=True):
        rows.append(
            {
                "ledger_name": clean_text(name_node.findtext("DSPDISPNAME")),
                "closing_debit": clean_text(info_node.findtext(".//DSPCLDRAMTA")),
                "closing_credit": clean_text(info_node.findtext(".//DSPCLCRAMTA")),
            }
        )
    return rows


def build_opening_stock_rows(
    stock_rows: list[dict[str, str]],
    item_metadata: dict[str, dict[str, str]],
    warehouse: str,
) -> list[dict[str, str]]:
    output_rows: list[dict[str, str]] = []
    for row in stock_rows:
        item_code = row["item_code"]
        quantity, quantity_uom = parse_quantity(row["closing_qty_text"])
        amount = abs(parse_decimal(row["closing_amount_text"]))
        metadata = item_metadata.get(item_code, {})
        uom = metadata.get("stock_uom") or quantity_uom
        if quantity == 0 and amount == 0:
            continue
        valuation_rate = Decimal("0")
        if quantity != 0:
            valuation_rate = amount / quantity
        erpnext_valuation_rate = valuation_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        erpnext_valuation_rate += ERPNEXT_STOCK_RATE_ADJUSTMENTS.get(item_code, Decimal("0"))
        output_rows.append(
            {
                "item_code": item_code,
                "warehouse": warehouse,
                "qty": decimal_text(quantity),
                "uom": uom,
                "valuation_rate": decimal_text(erpnext_valuation_rate),
                "amount": decimal_text(amount.quantize(Decimal("0.01"))),
                "tally_closing_qty": row["closing_qty_text"],
                "tally_closing_rate": row["closing_rate_text"],
                "tally_closing_value": row["closing_amount_text"],
                "stock_group": metadata.get("item_group", ""),
            }
        )
    return output_rows


def build_trial_balance_review_rows(
    trial_rows: list[dict[str, str]],
    ledger_groups: dict[str, str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in trial_rows:
        ledger_name = row["ledger_name"]
        debit = abs(parse_decimal(row["closing_debit"]))
        credit = abs(parse_decimal(row["closing_credit"]))
        parent_group = ledger_groups.get(ledger_name, "Opening Stock" if ledger_name == "Opening Stock" else "")
        classification = "Review"
        recommended_method = "Review"
        note = ""
        if ledger_name == "Opening Stock":
            classification = "Stock"
            recommended_method = "Use Stock Reconciliation"
            note = "Do not journal this row. Use Stock Summary closing stock instead."
        elif parent_group in ASSET_GROUPS | LIABILITY_GROUPS | EQUITY_GROUPS:
            classification = "Balance Sheet"
            if parent_group in {"Sundry Debtors", "Sundry Creditors"}:
                recommended_method = "Use Opening Invoice / net party opening"
                note = "Bill-wise data is not maintained, so use net opening per party."
            else:
                recommended_method = "Use Opening Journal Entry"
                note = "Carry this as of 1-Apr-2026."
        elif parent_group in PNL_GROUPS:
            classification = "P&L"
            recommended_method = "Do not carry as opening balance"
            note = "This is prior-year activity for 1-Apr-2025 to 31-Mar-2026."

        rows.append(
            {
                "ledger_name": ledger_name,
                "tally_parent_group": parent_group,
                "closing_debit": decimal_text(debit),
                "closing_credit": decimal_text(credit),
                "classification": classification,
                "recommended_posting_method": recommended_method,
                "note": note,
            }
        )
    return rows


def build_party_opening_rows(trial_review_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in trial_review_rows:
        parent_group = row["tally_parent_group"]
        if parent_group not in {"Sundry Debtors", "Sundry Creditors"}:
            continue

        debit = parse_decimal(row["closing_debit"])
        credit = parse_decimal(row["closing_credit"])
        if debit == 0 and credit == 0:
            continue

        party_type = "Customer" if parent_group == "Sundry Debtors" else "Supplier"
        balance_side = "Debit" if debit > 0 else "Credit"
        amount = debit if debit > 0 else credit
        interpretation = (
            "Normal receivable"
            if party_type == "Customer" and balance_side == "Debit"
            else "Customer credit / advance"
            if party_type == "Customer"
            else "Normal payable"
            if balance_side == "Credit"
            else "Supplier debit / advance"
        )

        rows.append(
            {
                "party_type": party_type,
                "party": row["ledger_name"],
                "tally_parent_group": parent_group,
                "balance_side": balance_side,
                "amount": decimal_text(amount),
                "recommended_posting_method": "Net opening with party specified",
                "note": f"Bill-wise data is not maintained. {interpretation}.",
            }
        )
    return rows


def build_non_party_balance_sheet_rows(trial_review_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in trial_review_rows:
        if row["classification"] != "Balance Sheet":
            continue
        if row["ledger_name"] == "Opening Stock":
            continue
        if row["tally_parent_group"] in {"Sundry Debtors", "Sundry Creditors"}:
            continue
        rows.append(
            {
                "ledger_name": row["ledger_name"],
                "tally_parent_group": row["tally_parent_group"],
                "debit": row["closing_debit"],
                "credit": row["closing_credit"],
                "recommended_posting_method": row["recommended_posting_method"],
                "note": row["note"],
            }
        )
    return rows


def build_stock_group_summary_rows(stock_output_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: defaultdict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {"row_count": 0, "total_qty": Decimal("0"), "total_amount": Decimal("0")}
    )
    for row in stock_output_rows:
        group = row["stock_group"]
        grouped[group]["row_count"] += 1
        grouped[group]["total_qty"] += parse_decimal(row["qty"])
        grouped[group]["total_amount"] += parse_decimal(row["amount"])

    rows: list[dict[str, str]] = []
    for group in sorted(grouped):
        values = grouped[group]
        rows.append(
            {
                "stock_group": group,
                "row_count": str(values["row_count"]),
                "total_qty": decimal_text(values["total_qty"]),
                "total_amount": decimal_text(values["total_amount"]),
            }
        )
    return rows


def opening_account_mapping() -> dict[str, dict[str, str]]:
    return {
        "Cash": {
            "erpnext_account": "Cash - VLA",
            "action": "Use existing",
            "parent_account": "Cash In Hand - VLA",
            "root_type": "Asset",
            "account_type": "Cash",
        },
        "CGST": {
            "erpnext_account": "CGST - VLA",
            "action": "Create first",
            "parent_account": "Duties and Taxes - VLA",
            "root_type": "Liability",
            "account_type": "Tax",
        },
        "Gadamsetty Venkateswara Rao": {
            "erpnext_account": "Gadamsetty Venkateswara Rao - VLA",
            "action": "Create first",
            "parent_account": "Capital Account - VLA",
            "root_type": "Liability",
            "account_type": "",
        },
        "Indian Bank": {
            "erpnext_account": "Indian Bank - VLA",
            "action": "Create first",
            "parent_account": "Bank Accounts - VLA",
            "root_type": "Asset",
            "account_type": "Bank",
        },
        "Investment in Venkata Syamala Agencies": {
            "erpnext_account": "Investment in Venkata Syamala Agencies - VLA",
            "action": "Create first",
            "parent_account": "Investments - VLA",
            "root_type": "Asset",
            "account_type": "",
        },
        "Provision for Gst": {
            "erpnext_account": "Provision for Gst - VLA",
            "action": "Create first",
            "parent_account": "Duties and Taxes - VLA",
            "root_type": "Liability",
            "account_type": "Tax",
        },
        "Punjab National Bank": {
            "erpnext_account": "Bank Overdraft Account - VLA",
            "action": "Use existing",
            "parent_account": "Loans (Liabilities) - VLA",
            "root_type": "Liability",
            "account_type": "",
        },
        "Punjab National Bank(3750)": {
            "erpnext_account": "Punjab National Bank 3750 - VLA",
            "action": "Create first",
            "parent_account": "Bank Accounts - VLA",
            "root_type": "Asset",
            "account_type": "Bank",
        },
        "SGST": {
            "erpnext_account": "SGST - VLA",
            "action": "Create first",
            "parent_account": "Duties and Taxes - VLA",
            "root_type": "Liability",
            "account_type": "Tax",
        },
        "Unavailed ITC": {
            "erpnext_account": "Unavailed ITC - VLA",
            "action": "Create first",
            "parent_account": "Tax Assets - VLA",
            "root_type": "Asset",
            "account_type": "",
        },
    }


def build_accounts_to_create_rows(non_party_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    mapping = opening_account_mapping()
    rows: list[dict[str, str]] = []
    for row in non_party_rows:
        config = mapping.get(row["ledger_name"])
        if not config or config["action"] != "Create first":
            continue
        rows.append(
            {
                "account_name": config["erpnext_account"].replace(" - VLA", ""),
                "full_account_name": config["erpnext_account"],
                "parent_account": config["parent_account"],
                "root_type": config["root_type"],
                "account_type": config["account_type"],
                "company": "Vara Lakshmi Agencies",
                "note": f"Needed for opening balance row from Tally ledger `{row['ledger_name']}`.",
            }
        )
    return rows


def build_opening_journal_rows(
    non_party_rows: list[dict[str, str]],
    party_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    mapping = opening_account_mapping()
    journal_rows: list[dict[str, str]] = []
    line_order = 10
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for row in non_party_rows:
        config = mapping[row["ledger_name"]]
        debit = parse_decimal(row["debit"])
        credit = parse_decimal(row["credit"])
        total_debit += debit
        total_credit += credit
        journal_rows.append(
            {
                "line_order": str(line_order),
                "source": "Non-party balance sheet",
                "erpnext_account": config["erpnext_account"],
                "party_type": "",
                "party": "",
                "debit": decimal_text(debit),
                "credit": decimal_text(credit),
                "create_account_first": "Yes" if config["action"] == "Create first" else "No",
                "note": row["note"],
            }
        )
        line_order += 10

    for row in party_rows:
        debit = parse_decimal(row["amount"]) if row["balance_side"] == "Debit" else Decimal("0")
        credit = parse_decimal(row["amount"]) if row["balance_side"] == "Credit" else Decimal("0")
        total_debit += debit
        total_credit += credit
        journal_rows.append(
            {
                "line_order": str(line_order),
                "source": "Party opening",
                "erpnext_account": "Debtors - VLA" if row["party_type"] == "Customer" else "Creditors - VLA",
                "party_type": row["party_type"],
                "party": row["party"],
                "debit": decimal_text(debit),
                "credit": decimal_text(credit),
                "create_account_first": "No",
                "note": row["note"],
            }
        )
        line_order += 10

    balancing_debit = total_credit - total_debit
    journal_rows.append(
        {
            "line_order": str(line_order),
            "source": "Balancing line",
            "erpnext_account": "Temporary Opening - VLA",
            "party_type": "",
            "party": "",
            "debit": decimal_text(balancing_debit),
            "credit": "0",
            "create_account_first": "No",
            "note": "This balances all non-stock opening rows. Stock Reconciliation should also use Temporary Opening - VLA as Difference Account.",
        }
    )
    return journal_rows


def build_temporary_opening_clearance_rows(stock_total: Decimal, opening_journal_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    temp_opening_debit = sum(parse_decimal(row["debit"]) for row in opening_journal_rows if row["erpnext_account"] == "Temporary Opening - VLA")
    remaining_credit = stock_total - temp_opening_debit
    return [
        {
            "line_order": "10",
            "erpnext_account": "Temporary Opening - VLA",
            "debit": decimal_text(remaining_credit),
            "credit": "0",
            "note": "Clear remaining balance after posting the opening stock reconciliation and opening journal entry.",
        },
        {
            "line_order": "20",
            "erpnext_account": "Reserves and Surplus - VLA",
            "debit": "0",
            "credit": decimal_text(remaining_credit),
            "note": "Carry accumulated opening difference / retained earnings into equity.",
        },
    ]


def write_report(
    path: Path,
    stock_rows: list[dict[str, str]],
    stock_output_rows: list[dict[str, str]],
    trial_review_rows: list[dict[str, str]],
    opening_journal_rows: list[dict[str, str]],
) -> None:
    stock_total = sum(abs(parse_decimal(row["closing_amount_text"])) for row in stock_rows)
    stock_by_group: defaultdict[str, Decimal] = defaultdict(Decimal)
    for row in stock_output_rows:
        stock_by_group[row["stock_group"]] += parse_decimal(row["amount"])

    balance_sheet_count = sum(1 for row in trial_review_rows if row["classification"] == "Balance Sheet")
    pnl_count = sum(1 for row in trial_review_rows if row["classification"] == "P&L")
    opening_stock_rows = [row for row in trial_review_rows if row["ledger_name"] == "Opening Stock"]
    non_party_rows = build_non_party_balance_sheet_rows(trial_review_rows)
    party_rows = build_party_opening_rows(trial_review_rows)
    total_debits = sum(parse_decimal(row["closing_debit"]) for row in trial_review_rows if row["classification"] == "Balance Sheet")
    total_credits = sum(parse_decimal(row["closing_credit"]) for row in trial_review_rows if row["classification"] == "Balance Sheet")
    stock_adjusted_debits = total_debits + stock_total
    balancing_credit = stock_adjusted_debits - total_credits

    lines = [
        "# XML Cutover Review",
        "",
        "Generated from:",
        "",
        "- `migration/tally/raw/XML/TrialBal.xml`",
        "- `migration/tally/raw/XML/StkSum.xml`",
        "",
        "## Stock Summary XML",
        "",
        f"- Non-zero stock rows written: {len(stock_output_rows)}",
        f"- Closing stock total from Stock Summary XML: {decimal_text(stock_total)}",
        "",
        "### Stock Total by Item Group",
        "",
    ]
    for group in ("12% GOODS", "18% GOODS", "5% GOODS", "EXEMPTED GOODS"):
        lines.append(f"- {group}: {decimal_text(stock_by_group[group])}")

    lines.extend(
        [
            "",
            "## Trial Balance XML",
            "",
            f"- Review rows: {len(trial_review_rows)}",
            f"- Balance sheet rows: {balance_sheet_count}",
            f"- P&L rows: {pnl_count}",
            f"- Party opening rows: {len(party_rows)}",
            f"- Non-party balance sheet rows: {len(non_party_rows)}",
            f"- Opening journal rows generated: {len(opening_journal_rows)}",
            "",
            "## Important Notes",
            "",
            "- `Opening Stock` in Trial Balance XML should not be posted through a Journal Entry if stock is posted through Stock Reconciliation.",
            "- Stock Summary XML is the safer source for opening stock on 1-Apr-2026.",
            "- Sales, purchases, indirect income, and indirect expenses from 1-Apr-2025 to 31-Mar-2026 are prior-year P&L rows and should not be carried as opening balances for 1-Apr-2026.",
            "- Because bill-wise receivables/payables are not maintained, party openings should be posted as net customer/supplier balances.",
            "- The generated `valuation_rate` values are ERPNext posting rates. A small item-specific adjustment map is applied so ERPNext's 2-decimal stock posting lands on both the Tally stock total and the XML stock-group totals.",
        ]
    )
    if opening_stock_rows:
        lines.extend(
            [
                "",
                "## Opening Stock Row in Trial Balance XML",
                "",
                f"- Trial Balance `Opening Stock` debit: {opening_stock_rows[0]['closing_debit']}",
                f"- Stock Summary XML total: {decimal_text(stock_total)}",
                f"- Difference to resolve during cutover: {decimal_text(parse_decimal(opening_stock_rows[0]['closing_debit']) - stock_total)}",
                "",
                "## Balance Check Using Stock Summary XML",
                "",
                f"- Balance sheet debit total after replacing Trial Balance opening stock with Stock Summary total: {decimal_text(stock_adjusted_debits)}",
                f"- Balance sheet credit total: {decimal_text(total_credits)}",
                f"- Remaining credit needed to balance opening position: {decimal_text(balancing_credit)}",
                "- This remaining credit is the accumulated result / opening difference that must be resolved during cutover.",
            ]
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()

    item_metadata = load_item_metadata(args.output_dir / "items.csv")
    ledger_groups = load_ledger_groups(args.master_json)

    stock_rows = parse_stock_summary(args.xml_dir / "StkSum.xml")
    trial_rows = parse_trial_balance(args.xml_dir / "TrialBal.xml")

    stock_output_rows = build_opening_stock_rows(stock_rows, item_metadata, args.warehouse)
    trial_review_rows = build_trial_balance_review_rows(trial_rows, ledger_groups)
    party_opening_rows = build_party_opening_rows(trial_review_rows)
    non_party_rows = build_non_party_balance_sheet_rows(trial_review_rows)
    stock_group_rows = build_stock_group_summary_rows(stock_output_rows)
    accounts_to_create_rows = build_accounts_to_create_rows(non_party_rows)
    opening_journal_rows = build_opening_journal_rows(non_party_rows, party_opening_rows)
    temporary_opening_clearance_rows = build_temporary_opening_clearance_rows(
        sum(abs(parse_decimal(row["closing_amount_text"])) for row in stock_rows),
        opening_journal_rows,
    )

    write_csv(
        args.output_dir / "opening_stock_from_stksum_staging.csv",
        [
            "item_code",
            "warehouse",
            "qty",
            "uom",
            "valuation_rate",
            "amount",
            "tally_closing_qty",
            "tally_closing_rate",
            "tally_closing_value",
            "stock_group",
        ],
        stock_output_rows,
    )
    write_csv(
        args.output_dir / "trial_balance_xml_review.csv",
        [
            "ledger_name",
            "tally_parent_group",
            "closing_debit",
            "closing_credit",
            "classification",
            "recommended_posting_method",
            "note",
        ],
        trial_review_rows,
    )
    write_csv(
        args.output_dir / "party_openings_from_trialbal.csv",
        [
            "party_type",
            "party",
            "tally_parent_group",
            "balance_side",
            "amount",
            "recommended_posting_method",
            "note",
        ],
        party_opening_rows,
    )
    write_csv(
        args.output_dir / "non_party_balance_sheet_from_trialbal.csv",
        [
            "ledger_name",
            "tally_parent_group",
            "debit",
            "credit",
            "recommended_posting_method",
            "note",
        ],
        non_party_rows,
    )
    write_csv(
        args.output_dir / "stock_group_summary_from_stksum.csv",
        ["stock_group", "row_count", "total_qty", "total_amount"],
        stock_group_rows,
    )
    write_csv(
        args.output_dir / "opening_accounts_to_create.csv",
        ["account_name", "full_account_name", "parent_account", "root_type", "account_type", "company", "note"],
        accounts_to_create_rows,
    )
    write_csv(
        args.output_dir / "opening_journal_lines_review.csv",
        ["line_order", "source", "erpnext_account", "party_type", "party", "debit", "credit", "create_account_first", "note"],
        opening_journal_rows,
    )
    write_csv(
        args.output_dir / "temporary_opening_clearance_entry.csv",
        ["line_order", "erpnext_account", "debit", "credit", "note"],
        temporary_opening_clearance_rows,
    )
    write_report(
        args.report_dir / "xml_cutover_review.md",
        stock_rows,
        stock_output_rows,
        trial_review_rows,
        opening_journal_rows,
    )

    print(f"wrote {args.output_dir / 'opening_stock_from_stksum_staging.csv'}")
    print(f"wrote {args.output_dir / 'trial_balance_xml_review.csv'}")
    print(f"wrote {args.output_dir / 'party_openings_from_trialbal.csv'}")
    print(f"wrote {args.output_dir / 'non_party_balance_sheet_from_trialbal.csv'}")
    print(f"wrote {args.output_dir / 'stock_group_summary_from_stksum.csv'}")
    print(f"wrote {args.output_dir / 'opening_accounts_to_create.csv'}")
    print(f"wrote {args.output_dir / 'opening_journal_lines_review.csv'}")
    print(f"wrote {args.output_dir / 'temporary_opening_clearance_entry.csv'}")
    print(f"wrote {args.report_dir / 'xml_cutover_review.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
