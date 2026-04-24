#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable

from tally_compute_balances import clean_text, load_messages, parse_decimal, parse_quantity


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRANSACTIONS_JSON = REPO_ROOT / "migration" / "tally" / "raw" / "JSON" / "Transactions.json"
DEFAULT_ITEMS_CSV = REPO_ROOT / "migration" / "tally" / "output" / "items.csv"
DEFAULT_CUSTOMERS_CSV = REPO_ROOT / "migration" / "tally" / "output" / "customers.csv"
DEFAULT_SUPPLIERS_CSV = REPO_ROOT / "migration" / "tally" / "output" / "suppliers.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "migration" / "tally" / "output"
DEFAULT_REPORT_DIR = REPO_ROOT / "migration" / "tally" / "reports"

DEFAULT_FROM_DATE = "2025-04-01"
DEFAULT_TO_DATE = "2026-03-31"

TAX_RATE_BY_ITEM_GROUP = {
    "5% GOODS": Decimal("5"),
    "12% GOODS": Decimal("12"),
    "18% GOODS": Decimal("18"),
    "EXEMPTED GOODS": Decimal("0"),
}

SUPPORTED_VOUCHER_TYPES = {
    "Sales",
    "Purchase",
    "Receipt",
    "Payment",
    "Journal",
    "Credit Note",
}

BANK_OR_CASH_LEDGER_NAMES = {"Cash", "Punjab National Bank", "Punjab National Bank(3750)", "Indian Bank"}


@dataclass(frozen=True)
class ItemContext:
    item_code: str
    item_group: str
    stock_uom: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a reusable Tally voucher-history pack for ERPNext staging and reconciliation."
    )
    parser.add_argument("--transactions-json", type=Path, default=DEFAULT_TRANSACTIONS_JSON)
    parser.add_argument("--items-csv", type=Path, default=DEFAULT_ITEMS_CSV)
    parser.add_argument("--customers-csv", type=Path, default=DEFAULT_CUSTOMERS_CSV)
    parser.add_argument("--suppliers-csv", type=Path, default=DEFAULT_SUPPLIERS_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument(
        "--from-date",
        default=DEFAULT_FROM_DATE,
        help=f"First posting date to include, in YYYY-MM-DD. Default: {DEFAULT_FROM_DATE}",
    )
    parser.add_argument(
        "--to-date",
        default=DEFAULT_TO_DATE,
        help=f"Last posting date to include, in YYYY-MM-DD. Default: {DEFAULT_TO_DATE}",
    )
    parser.add_argument(
        "--company",
        default="Vara Lakshmi Agencies",
        help="Company name to stamp into staging files.",
    )
    parser.add_argument(
        "--company-abbr",
        default="VLA",
        help="Company abbreviation used in ERPNext account and warehouse names.",
    )
    parser.add_argument(
        "--default-sales-income-account",
        default="Sales - VLA",
        help="Income account hint for staged sales invoice items.",
    )
    parser.add_argument(
        "--default-purchase-expense-account",
        default="Cost of Goods Sold - VLA",
        help="Expense account hint for staged purchase invoice items.",
    )
    parser.add_argument(
        "--default-warehouse",
        default="Main Location - VLA",
        help="ERPNext warehouse hint for stock vouchers.",
    )
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def iso_date(tally_date: str) -> str:
    text = clean_text(tally_date)
    if not text:
        return ""
    return datetime.strptime(text, "%Y%m%d").strftime("%Y-%m-%d")


def tally_date(iso_value: str) -> str:
    return datetime.strptime(iso_value, "%Y-%m-%d").strftime("%Y%m%d")


def decimal_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def integer_text(value: Decimal) -> str:
    normalized = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return format(normalized, "f")


def bool_text(value: object) -> str:
    return "1" if bool(value) else "0"


def metadata_type(message: dict[str, object]) -> str:
    metadata = message.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    return clean_text(metadata.get("type"))


def should_include_voucher(message: dict[str, object], date_from: str, date_to: str) -> bool:
    if metadata_type(message) != "Voucher":
        return False
    if clean_text(message.get("vouchertypename")) not in SUPPORTED_VOUCHER_TYPES:
        return False
    voucher_date = clean_text(message.get("date"))
    if not voucher_date or voucher_date < date_from or voucher_date > date_to:
        return False
    if bool(message.get("iscancelled")) or bool(message.get("isdeleted")) or bool(message.get("isoptional")):
        return False
    return True


def load_item_context(path: Path) -> dict[str, ItemContext]:
    rows = read_csv_rows(path)
    return {
        clean_text(row.get("item_code")): ItemContext(
            item_code=clean_text(row.get("item_code")),
            item_group=clean_text(row.get("item_group")),
            stock_uom=clean_text(row.get("stock_uom")),
        )
        for row in rows
        if clean_text(row.get("item_code"))
    }


def load_party_names(path: Path, fieldname: str) -> set[str]:
    return {clean_text(row.get(fieldname)) for row in read_csv_rows(path) if clean_text(row.get(fieldname))}


def party_type_for(name: str, customers: set[str], suppliers: set[str]) -> str:
    if name in customers:
        return "Customer"
    if name in suppliers:
        return "Supplier"
    return ""


def stock_rows(voucher: dict[str, object]) -> list[dict[str, object]]:
    return [row for row in (voucher.get("allinventoryentries") or []) if isinstance(row, dict)]


def ledger_rows(voucher: dict[str, object]) -> list[dict[str, object]]:
    return [row for row in (voucher.get("allledgerentries") or []) if isinstance(row, dict)]


def first_godown_name(inventory_row: dict[str, object]) -> str:
    for batch in inventory_row.get("batchallocations") or []:
        if isinstance(batch, dict):
            name = clean_text(batch.get("godownname"))
            if name:
                return name
    return ""


def tax_rate_for_item_group(item_group: str) -> Decimal:
    return TAX_RATE_BY_ITEM_GROUP.get(item_group, Decimal("0"))


def suggested_tax_template(rate: Decimal, company_abbr: str) -> str:
    if rate == 0:
        return f"GST Exempt In-State - {company_abbr}"
    return f"GST In-State {integer_text(rate)}% - {company_abbr}"


def build_sales_like_rows(
    voucher: dict[str, object],
    voucher_type: str,
    items_by_code: dict[str, ItemContext],
    customers: set[str],
    suppliers: set[str],
    args: argparse.Namespace,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    party = clean_text(voucher.get("partyledgername"))
    party_type = party_type_for(party, customers, suppliers)
    posting_date = iso_date(clean_text(voucher.get("date")))
    voucher_number = clean_text(voucher.get("vouchernumber"))
    voucher_key = clean_text(voucher.get("voucherkey"))

    total_base = Decimal("0")
    tax_bases: defaultdict[Decimal, Decimal] = defaultdict(Decimal)
    item_rows: list[dict[str, object]] = []
    source_godowns: Counter[str] = Counter()

    for line_no, inventory_row in enumerate(stock_rows(voucher), start=1):
        item_code = clean_text(inventory_row.get("stockitemname"))
        item_context = items_by_code.get(
            item_code,
            ItemContext(item_code=item_code, item_group="", stock_uom=""),
        )
        qty, parsed_uom = parse_quantity(inventory_row.get("actualqty") or inventory_row.get("billedqty"))
        rate_text = clean_text(inventory_row.get("rate"))
        base_amount = abs(parse_decimal(inventory_row.get("amount")))
        tax_rate = tax_rate_for_item_group(item_context.item_group)
        total_base += base_amount
        tax_bases[tax_rate] += base_amount

        source_godown = first_godown_name(inventory_row)
        if source_godown:
            source_godowns[source_godown] += 1

        item_rows.append(
            {
                "voucher_type": voucher_type,
                "posting_date": posting_date,
                "voucher_number": voucher_number,
                "voucher_key": voucher_key,
                "party_type": party_type,
                "party": party,
                "line_no": line_no,
                "item_code": item_code,
                "item_group": item_context.item_group,
                "qty": decimal_text(abs(qty)),
                "uom": item_context.stock_uom or parsed_uom,
                "rate": rate_text,
                "base_amount": decimal_text(base_amount),
                "tax_rate": decimal_text(tax_rate),
                "suggested_item_tax_template": suggested_tax_template(tax_rate, args.company_abbr),
                "source_godown": source_godown,
                "erpnext_warehouse": args.default_warehouse,
                "income_or_expense_account": (
                    args.default_sales_income_account if voucher_type in {"Sales", "Credit Note"} else args.default_purchase_expense_account
                ),
            }
        )

    total_tax = Decimal("0")
    for rate, base in tax_bases.items():
        total_tax += (base * rate) / Decimal("100")
    grand_total = total_base + total_tax
    rounded_grand_total = grand_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    round_off_amount = rounded_grand_total - grand_total

    tax_base_columns = {
        Decimal("0"): "taxable_value_0",
        Decimal("5"): "taxable_value_5",
        Decimal("12"): "taxable_value_12",
        Decimal("18"): "taxable_value_18",
    }
    header: dict[str, object] = {
        "voucher_type": voucher_type,
        "posting_date": posting_date,
        "voucher_number": voucher_number,
        "voucher_key": voucher_key,
        "external_reference": clean_text(voucher.get("reference")),
        "party_type": party_type,
        "party": party,
        "company": args.company,
        "is_return": bool_text(voucher_type == "Credit Note"),
        "update_stock": "1",
        "source_godown": source_godowns.most_common(1)[0][0] if source_godowns else "",
        "erpnext_warehouse": args.default_warehouse,
        "line_count": len(item_rows),
        "base_total": decimal_text(total_base),
        "total_tax": decimal_text(total_tax),
        "grand_total": decimal_text(grand_total),
        "rounded_grand_total": decimal_text(rounded_grand_total),
        "round_off_amount": decimal_text(round_off_amount),
        "cgst_total": decimal_text(total_tax / Decimal("2")),
        "sgst_total": decimal_text(total_tax / Decimal("2")),
        "tax_mode": "In-State GST",
        "company_gst_state": clean_text(voucher.get("cmpgststate")),
        "party_gst_registration": clean_text(voucher.get("gstregistration")),
    }
    for rate, column in tax_base_columns.items():
        header[column] = decimal_text(tax_bases[rate])

    return header, item_rows


def build_payment_rows(
    voucher: dict[str, object],
    voucher_type: str,
    customers: set[str],
    suppliers: set[str],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    rows = ledger_rows(voucher)
    posting_date = iso_date(clean_text(voucher.get("date")))
    voucher_number = clean_text(voucher.get("vouchernumber"))
    voucher_key = clean_text(voucher.get("voucherkey"))
    party = clean_text(voucher.get("partyledgername"))
    party_type = party_type_for(party, customers, suppliers)

    party_row = next((row for row in rows if clean_text(row.get("ledgername")) == party), None)
    counter_rows = [row for row in rows if clean_text(row.get("ledgername")) != party]

    paid_amount = abs(parse_decimal(party_row.get("amount"))) if party_row else Decimal("0")
    counter_account = clean_text(counter_rows[0].get("ledgername")) if counter_rows else ""

    header = {
        "voucher_type": voucher_type,
        "posting_date": posting_date,
        "voucher_number": voucher_number,
        "voucher_key": voucher_key,
        "party_type": party_type,
        "party": party,
        "counter_account": counter_account,
        "paid_amount": decimal_text(paid_amount),
        "line_count": len(rows),
        "remarks": clean_text(voucher.get("narration")),
    }

    references: list[dict[str, object]] = []
    if party_row:
        for line_no, bill in enumerate(party_row.get("billallocations") or [], start=1):
            if not isinstance(bill, dict):
                continue
            references.append(
                {
                    "voucher_type": voucher_type,
                    "posting_date": posting_date,
                    "voucher_number": voucher_number,
                    "voucher_key": voucher_key,
                    "line_no": line_no,
                    "party_type": party_type,
                    "party": party,
                    "reference_name": clean_text(bill.get("name")),
                    "reference_type": clean_text(bill.get("billtype")),
                    "allocated_amount": decimal_text(abs(parse_decimal(bill.get("amount")))),
                }
            )

    payment_lines: list[dict[str, object]] = []
    for line_no, row in enumerate(rows, start=1):
        ledger_name = clean_text(row.get("ledgername"))
        line_party_type = party_type_for(ledger_name, customers, suppliers)
        amount = parse_decimal(row.get("amount"))
        payment_lines.append(
            {
                "voucher_type": voucher_type,
                "posting_date": posting_date,
                "voucher_number": voucher_number,
                "voucher_key": voucher_key,
                "line_no": line_no,
                "ledger_name": ledger_name,
                "party_type": line_party_type,
                "amount": decimal_text(amount),
                "is_bank_row": bool_text(ledger_name in BANK_OR_CASH_LEDGER_NAMES),
                "is_party_ledger": bool_text(bool(line_party_type)),
                "is_header_party": bool_text(ledger_name == party),
            }
        )

    return header, references, payment_lines


def build_journal_rows(voucher: dict[str, object], customers: set[str], suppliers: set[str]) -> list[dict[str, object]]:
    posting_date = iso_date(clean_text(voucher.get("date")))
    voucher_number = clean_text(voucher.get("vouchernumber"))
    voucher_key = clean_text(voucher.get("voucherkey"))

    lines: list[dict[str, object]] = []
    for line_no, row in enumerate(ledger_rows(voucher), start=1):
        ledger_name = clean_text(row.get("ledgername"))
        amount = parse_decimal(row.get("amount"))
        lines.append(
            {
                "posting_date": posting_date,
                "voucher_number": voucher_number,
                "voucher_key": voucher_key,
                "line_no": line_no,
                "ledger_name": ledger_name,
                "party_type": party_type_for(ledger_name, customers, suppliers),
                "debit": decimal_text(abs(amount)) if amount < 0 else "0.00",
                "credit": decimal_text(abs(amount)) if amount > 0 else "0.00",
                "narration": clean_text(voucher.get("narration")),
            }
        )
    return lines


def write_summary(
    path: Path,
    *,
    args: argparse.Namespace,
    totals_by_voucher_type: Counter[str],
    sales_headers: list[dict[str, object]],
    purchase_headers: list[dict[str, object]],
    receipt_headers: list[dict[str, object]],
    payment_headers: list[dict[str, object]],
    credit_note_headers: list[dict[str, object]],
    journal_lines: list[dict[str, object]],
) -> None:
    def sum_decimal(rows: list[dict[str, object]], fieldname: str) -> Decimal:
        return sum(Decimal(str(row.get(fieldname) or "0")) for row in rows)

    party_receipts = [row for row in receipt_headers if clean_text(row.get("party_type"))]
    non_party_receipts = [row for row in receipt_headers if not clean_text(row.get("party_type"))]
    party_payments = [row for row in payment_headers if clean_text(row.get("party_type"))]
    non_party_payments = [row for row in payment_headers if not clean_text(row.get("party_type"))]

    lines = [
        "# Tally Voucher History Import Review",
        "",
        f"- Date range: `{args.from_date}` to `{args.to_date}`",
        f"- Company: `{args.company}`",
        f"- Default warehouse hint: `{args.default_warehouse}`",
        "",
        "## Critical Rule",
        "",
        "This pack is for full voucher-history migration.",
        "",
        "Do not load these vouchers on top of the already-posted `2026-04-01` opening cutover in the live site.",
        "",
        "If you want last year's invoices, receipts, purchases, and payments inside ERPNext, rebuild from the pre-cutover backup or a fresh site, then import:",
        "",
        "1. masters",
        "2. `2025-04-01` opening balances from the Tally master export",
        "3. historical vouchers for the selected date range",
        "",
        "## Voucher Counts",
        "",
    ]
    for voucher_type in sorted(totals_by_voucher_type):
        lines.append(f"- {voucher_type}: {totals_by_voucher_type[voucher_type]}")

    lines.extend(
        [
            "",
            "## Sales-Like Totals",
            "",
            f"- Sales invoices staged: {len(sales_headers)}",
            f"- Sales base total: `{decimal_text(sum_decimal(sales_headers, 'base_total'))}`",
            f"- Sales gross total: `{decimal_text(sum_decimal(sales_headers, 'grand_total'))}`",
            f"- Purchase invoices staged: {len(purchase_headers)}",
            f"- Purchase base total: `{decimal_text(sum_decimal(purchase_headers, 'base_total'))}`",
            f"- Purchase gross total: `{decimal_text(sum_decimal(purchase_headers, 'grand_total'))}`",
            f"- Credit notes staged: {len(credit_note_headers)}",
            f"- Credit note gross total: `{decimal_text(sum_decimal(credit_note_headers, 'grand_total'))}`",
            "",
            "## Payment-Like Totals",
            "",
            f"- Receipts staged: {len(receipt_headers)}",
            f"- Receipt total: `{decimal_text(sum_decimal(receipt_headers, 'paid_amount'))}`",
            f"- Party receipts suited to Payment Entry import: {len(party_receipts)}",
            f"- Non-party receipts that should be treated as journals/cash movements: {len(non_party_receipts)}",
            f"- Payments staged: {len(payment_headers)}",
            f"- Payment total: `{decimal_text(sum_decimal(payment_headers, 'paid_amount'))}`",
            f"- Party payments suited to Payment Entry import: {len(party_payments)}",
            f"- Non-party payments that should be treated as journals/cash movements: {len(non_party_payments)}",
            f"- Journal lines staged: {len(journal_lines)}",
            "",
            "## Next Safe Step",
            "",
            "Use this generated history pack as the basis for the ERPNext importer.",
            "",
            "The same script can be rerun later for the current financial year, for example from `2026-04-01` to today, once the prior-year rebuild path is finalized.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    date_from = tally_date(args.from_date)
    date_to = tally_date(args.to_date)

    items_by_code = load_item_context(args.items_csv)
    customers = load_party_names(args.customers_csv, "customer_name")
    suppliers = load_party_names(args.suppliers_csv, "supplier_name")
    transaction_messages = load_messages(args.transactions_json)

    sales_headers: list[dict[str, object]] = []
    sales_items: list[dict[str, object]] = []
    purchase_headers: list[dict[str, object]] = []
    purchase_items: list[dict[str, object]] = []
    credit_note_headers: list[dict[str, object]] = []
    credit_note_items: list[dict[str, object]] = []
    receipt_headers: list[dict[str, object]] = []
    receipt_refs: list[dict[str, object]] = []
    payment_headers: list[dict[str, object]] = []
    payment_refs: list[dict[str, object]] = []
    settlement_lines: list[dict[str, object]] = []
    journal_lines: list[dict[str, object]] = []
    totals_by_voucher_type: Counter[str] = Counter()

    for message in transaction_messages:
        if not should_include_voucher(message, date_from, date_to):
            continue

        voucher_type = clean_text(message.get("vouchertypename"))
        totals_by_voucher_type[voucher_type] += 1

        if voucher_type == "Sales":
            header, items = build_sales_like_rows(message, voucher_type, items_by_code, customers, suppliers, args)
            sales_headers.append(header)
            sales_items.extend(items)
        elif voucher_type == "Purchase":
            header, items = build_sales_like_rows(message, voucher_type, items_by_code, customers, suppliers, args)
            purchase_headers.append(header)
            purchase_items.extend(items)
        elif voucher_type == "Credit Note":
            header, items = build_sales_like_rows(message, voucher_type, items_by_code, customers, suppliers, args)
            credit_note_headers.append(header)
            credit_note_items.extend(items)
        elif voucher_type == "Receipt":
            header, refs, lines = build_payment_rows(message, voucher_type, customers, suppliers)
            receipt_headers.append(header)
            receipt_refs.extend(refs)
            settlement_lines.extend(lines)
        elif voucher_type == "Payment":
            header, refs, lines = build_payment_rows(message, voucher_type, customers, suppliers)
            payment_headers.append(header)
            payment_refs.extend(refs)
            settlement_lines.extend(lines)
        elif voucher_type == "Journal":
            journal_lines.extend(build_journal_rows(message, customers, suppliers))

    write_csv(
        args.output_dir / "historical_sales_invoices.csv",
        [
            "voucher_type",
            "posting_date",
            "voucher_number",
            "voucher_key",
            "external_reference",
            "party_type",
            "party",
            "company",
            "is_return",
            "update_stock",
            "source_godown",
            "erpnext_warehouse",
            "line_count",
            "base_total",
            "taxable_value_0",
            "taxable_value_5",
            "taxable_value_12",
            "taxable_value_18",
            "cgst_total",
            "sgst_total",
            "total_tax",
            "grand_total",
            "rounded_grand_total",
            "round_off_amount",
            "tax_mode",
            "company_gst_state",
            "party_gst_registration",
        ],
        sales_headers,
    )
    write_csv(
        args.output_dir / "historical_sales_invoice_items.csv",
        [
            "voucher_type",
            "posting_date",
            "voucher_number",
            "voucher_key",
            "party_type",
            "party",
            "line_no",
            "item_code",
            "item_group",
            "qty",
            "uom",
            "rate",
            "base_amount",
            "tax_rate",
            "suggested_item_tax_template",
            "source_godown",
            "erpnext_warehouse",
            "income_or_expense_account",
        ],
        sales_items,
    )
    write_csv(
        args.output_dir / "historical_purchase_invoices.csv",
        [
            "voucher_type",
            "posting_date",
            "voucher_number",
            "voucher_key",
            "external_reference",
            "party_type",
            "party",
            "company",
            "is_return",
            "update_stock",
            "source_godown",
            "erpnext_warehouse",
            "line_count",
            "base_total",
            "taxable_value_0",
            "taxable_value_5",
            "taxable_value_12",
            "taxable_value_18",
            "cgst_total",
            "sgst_total",
            "total_tax",
            "grand_total",
            "rounded_grand_total",
            "round_off_amount",
            "tax_mode",
            "company_gst_state",
            "party_gst_registration",
        ],
        purchase_headers,
    )
    write_csv(
        args.output_dir / "historical_purchase_invoice_items.csv",
        [
            "voucher_type",
            "posting_date",
            "voucher_number",
            "voucher_key",
            "party_type",
            "party",
            "line_no",
            "item_code",
            "item_group",
            "qty",
            "uom",
            "rate",
            "base_amount",
            "tax_rate",
            "suggested_item_tax_template",
            "source_godown",
            "erpnext_warehouse",
            "income_or_expense_account",
        ],
        purchase_items,
    )
    write_csv(
        args.output_dir / "historical_credit_notes.csv",
        [
            "voucher_type",
            "posting_date",
            "voucher_number",
            "voucher_key",
            "external_reference",
            "party_type",
            "party",
            "company",
            "is_return",
            "update_stock",
            "source_godown",
            "erpnext_warehouse",
            "line_count",
            "base_total",
            "taxable_value_0",
            "taxable_value_5",
            "taxable_value_12",
            "taxable_value_18",
            "cgst_total",
            "sgst_total",
            "total_tax",
            "grand_total",
            "rounded_grand_total",
            "round_off_amount",
            "tax_mode",
            "company_gst_state",
            "party_gst_registration",
        ],
        credit_note_headers,
    )
    write_csv(
        args.output_dir / "historical_credit_note_items.csv",
        [
            "voucher_type",
            "posting_date",
            "voucher_number",
            "voucher_key",
            "party_type",
            "party",
            "line_no",
            "item_code",
            "item_group",
            "qty",
            "uom",
            "rate",
            "base_amount",
            "tax_rate",
            "suggested_item_tax_template",
            "source_godown",
            "erpnext_warehouse",
            "income_or_expense_account",
        ],
        credit_note_items,
    )
    write_csv(
        args.output_dir / "historical_receipts.csv",
        [
            "voucher_type",
            "posting_date",
            "voucher_number",
            "voucher_key",
            "party_type",
            "party",
            "counter_account",
            "paid_amount",
            "line_count",
            "remarks",
        ],
        receipt_headers,
    )
    write_csv(
        args.output_dir / "historical_receipt_references.csv",
        [
            "voucher_type",
            "posting_date",
            "voucher_number",
            "voucher_key",
            "line_no",
            "party_type",
            "party",
            "reference_name",
            "reference_type",
            "allocated_amount",
        ],
        receipt_refs,
    )
    write_csv(
        args.output_dir / "historical_payments.csv",
        [
            "voucher_type",
            "posting_date",
            "voucher_number",
            "voucher_key",
            "party_type",
            "party",
            "counter_account",
            "paid_amount",
            "line_count",
            "remarks",
        ],
        payment_headers,
    )
    write_csv(
        args.output_dir / "historical_payment_references.csv",
        [
            "voucher_type",
            "posting_date",
            "voucher_number",
            "voucher_key",
            "line_no",
            "party_type",
            "party",
            "reference_name",
            "reference_type",
            "allocated_amount",
        ],
        payment_refs,
    )
    write_csv(
        args.output_dir / "historical_settlement_lines.csv",
        [
            "voucher_type",
            "posting_date",
            "voucher_number",
            "voucher_key",
            "line_no",
            "ledger_name",
            "party_type",
            "amount",
            "is_bank_row",
            "is_party_ledger",
            "is_header_party",
        ],
        settlement_lines,
    )
    write_csv(
        args.output_dir / "historical_journal_lines.csv",
        [
            "posting_date",
            "voucher_number",
            "voucher_key",
            "line_no",
            "ledger_name",
            "party_type",
            "debit",
            "credit",
            "narration",
        ],
        journal_lines,
    )
    write_csv(
        args.output_dir / "historical_voucher_summary.csv",
        ["voucher_type", "voucher_count"],
        [{"voucher_type": key, "voucher_count": value} for key, value in sorted(totals_by_voucher_type.items())],
    )

    write_summary(
        args.report_dir / "history_import_review.md",
        args=args,
        totals_by_voucher_type=totals_by_voucher_type,
        sales_headers=sales_headers,
        purchase_headers=purchase_headers,
        receipt_headers=receipt_headers,
        payment_headers=payment_headers,
        credit_note_headers=credit_note_headers,
        journal_lines=journal_lines,
    )

    print(f"built history pack for {args.from_date} to {args.to_date}")
    print(f"sales invoices: {len(sales_headers)}")
    print(f"purchase invoices: {len(purchase_headers)}")
    print(f"credit notes: {len(credit_note_headers)}")
    print(f"receipts: {len(receipt_headers)}")
    print(f"payments: {len(payment_headers)}")
    print(f"journal vouchers: {totals_by_voucher_type['Journal']}")
    print(f"wrote files to {args.output_dir}")
    print(f"wrote report to {args.report_dir / 'history_import_review.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
