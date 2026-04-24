#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "migration" / "tally" / "output"
REPORT_DIR = REPO_ROOT / "migration" / "tally" / "reports"

BANK_OR_CASH_LEDGER_NAMES = {"Cash", "Punjab National Bank", "Punjab National Bank(3750)", "Indian Bank"}


@dataclass
class InvoiceState:
    doctype: str
    party_type: str
    party: str
    posting_date: str
    voucher_key: str
    voucher_number: str
    external_reference: str
    total_amount: Decimal
    remaining: Decimal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze remaining ERPNext overdue invoices against staged Tally history artifacts."
    )
    parser.add_argument(
        "--site",
        default="business.manoharsolleti.com",
        help="ERPNext site name.",
    )
    parser.add_argument(
        "--company",
        default="Vara Lakshmi Agencies",
        help="ERPNext company name.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Generated migration output directory. Default: {OUTPUT_DIR}",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=REPORT_DIR,
        help=f"Generated migration report directory. Default: {REPORT_DIR}",
    )
    parser.add_argument(
        "--allocation-strategy",
        choices=["none", "exact_unique", "fifo"],
        default="fifo",
        help="Allocation strategy to replay locally for party settlements. Default: fifo.",
    )
    return parser.parse_args()


def clean(value: object) -> str:
    return str(value or "").strip()


def parse_decimal(value: object) -> Decimal:
    text = clean(value).replace(",", "")
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def decimal_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def safe_int(value: object) -> int:
    text = clean(value)
    try:
        return int(text)
    except ValueError:
        return 0


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def parse_tally_tag(remark: object) -> dict[str, str]:
    text = clean(remark)
    if not text.startswith("[") or not text.endswith("]"):
        return {}
    parts = text[1:-1].split("][")
    if len(parts) < 5 or parts[0] != "TALLY":
        return {}
    return {
        "kind": parts[1],
        "voucher_type": parts[2],
        "voucher_key": parts[3],
        "voucher_number": "][".join(parts[4:]),
    }


def load_live_overdue(site: str, company: str) -> dict[str, list[dict[str, object]]]:
    code = f"""
from __future__ import annotations

import json

import frappe

SITE = {site!r}
COMPANY = {company!r}

frappe.init(site=SITE, sites_path=".")
frappe.connect()
try:
    payload = {{
        "sales": frappe.get_all(
            "Sales Invoice",
            filters={{"company": COMPANY, "docstatus": 1, "is_return": 0, "status": "Overdue"}},
            fields=["name", "posting_date", "customer", "outstanding_amount", "status", "remarks"],
            order_by="posting_date asc, creation asc",
            limit_page_length=0,
        ),
        "purchase": frappe.get_all(
            "Purchase Invoice",
            filters={{"company": COMPANY, "docstatus": 1, "status": "Overdue"}},
            fields=["name", "posting_date", "supplier", "bill_no", "outstanding_amount", "status", "remarks"],
            order_by="posting_date asc, creation asc",
            limit_page_length=0,
        ),
    }}
    print(json.dumps(payload, default=str))
finally:
    frappe.destroy()
"""
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
        "cd /home/frappe/frappe-bench/sites && ../env/bin/python -",
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, input=code, text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def grouped_rows(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[clean(row.get("voucher_key"))].append(row)
    return grouped


def build_invoice_states(output_dir: Path) -> tuple[dict[str, InvoiceState], dict[str, list[InvoiceState]], dict[tuple[str, str], InvoiceState], dict[tuple[str, str], InvoiceState]]:
    sales_headers = read_csv(output_dir / "historical_sales_invoices.csv")
    sales_items = grouped_rows(read_csv(output_dir / "historical_sales_invoice_items.csv"))
    purchase_headers = read_csv(output_dir / "historical_purchase_invoices.csv")
    purchase_items = grouped_rows(read_csv(output_dir / "historical_purchase_invoice_items.csv"))

    by_key: dict[str, InvoiceState] = {}
    by_party: dict[str, list[InvoiceState]] = defaultdict(list)
    sales_lookup: dict[tuple[str, str], InvoiceState] = {}
    purchase_lookup: dict[tuple[str, str], InvoiceState] = {}

    for row in sales_headers:
        voucher_key = clean(row.get("voucher_key"))
        if not sales_items.get(voucher_key):
            continue
        state = InvoiceState(
            doctype="Sales Invoice",
            party_type="Customer",
            party=clean(row.get("party")),
            posting_date=clean(row.get("posting_date")),
            voucher_key=voucher_key,
            voucher_number=clean(row.get("voucher_number")),
            external_reference="",
            total_amount=parse_decimal(row.get("rounded_grand_total") or row.get("grand_total")),
            remaining=parse_decimal(row.get("rounded_grand_total") or row.get("grand_total")),
        )
        by_key[f"sales:{voucher_key}"] = state
        by_party[f"Customer::{state.party}"].append(state)
        sales_lookup[(state.party, state.voucher_number)] = state

    for row in purchase_headers:
        voucher_key = clean(row.get("voucher_key"))
        if not purchase_items.get(voucher_key):
            continue
        state = InvoiceState(
            doctype="Purchase Invoice",
            party_type="Supplier",
            party=clean(row.get("party")),
            posting_date=clean(row.get("posting_date")),
            voucher_key=voucher_key,
            voucher_number=clean(row.get("voucher_number")),
            external_reference=clean(row.get("external_reference")),
            total_amount=parse_decimal(row.get("rounded_grand_total") or row.get("grand_total")),
            remaining=parse_decimal(row.get("rounded_grand_total") or row.get("grand_total")),
        )
        by_key[f"purchase:{voucher_key}"] = state
        by_party[f"Supplier::{state.party}"].append(state)
        if state.external_reference:
            purchase_lookup[(state.party, state.external_reference)] = state
        purchase_lookup[(state.party, state.voucher_number)] = state

    for party_key in by_party:
        by_party[party_key].sort(key=lambda row: (row.posting_date, row.voucher_key, row.voucher_number))

    return by_key, by_party, sales_lookup, purchase_lookup


def allocate_to_invoice(invoice: InvoiceState, amount: Decimal) -> Decimal:
    allocated = min(amount, invoice.remaining)
    if allocated <= 0:
        return Decimal("0")
    invoice.remaining -= allocated
    if abs(invoice.remaining) < Decimal("0.005"):
        invoice.remaining = Decimal("0")
    return allocated


def find_candidates(by_party: dict[str, list[InvoiceState]], party_type: str, party: str, posting_date: str) -> list[InvoiceState]:
    return [
        invoice
        for invoice in by_party.get(f"{party_type}::{party}", [])
        if invoice.posting_date <= posting_date and invoice.remaining > 0
    ]


def replay_allocations(
    output_dir: Path,
    by_party: dict[str, list[InvoiceState]],
    sales_lookup: dict[tuple[str, str], InvoiceState],
    purchase_lookup: dict[tuple[str, str], InvoiceState],
    allocation_strategy: str,
) -> tuple[dict[str, list[dict[str, object]]], dict[str, list[dict[str, object]]]]:
    receipt_headers = read_csv(output_dir / "historical_receipts.csv")
    receipt_refs = grouped_rows(read_csv(output_dir / "historical_receipt_references.csv"))
    payment_headers = read_csv(output_dir / "historical_payments.csv")
    payment_refs = grouped_rows(read_csv(output_dir / "historical_payment_references.csv"))

    complex_by_party: dict[str, list[dict[str, object]]] = defaultdict(list)
    unallocated_by_party: dict[str, list[dict[str, object]]] = defaultdict(list)

    def reference_invoice(party_type: str, party: str, reference_name: str) -> InvoiceState | None:
        if party_type == "Customer":
            return sales_lookup.get((party, reference_name))
        return purchase_lookup.get((party, reference_name))

    def process_header(header: dict[str, str], ref_rows: list[dict[str, str]]) -> None:
        party_type = clean(header.get("party_type"))
        if party_type not in {"Customer", "Supplier"}:
            return
        party = clean(header.get("party"))
        voucher_type = clean(header.get("voucher_type"))
        voucher_number = clean(header.get("voucher_number"))
        posting_date = clean(header.get("posting_date"))
        counter_account = clean(header.get("counter_account"))
        line_count = safe_int(header.get("line_count"))
        party_key = f"{party_type}::{party}"

        if counter_account not in BANK_OR_CASH_LEDGER_NAMES or line_count != 2:
            complex_by_party[party_key].append(
                {
                    "voucher_type": voucher_type,
                    "voucher_number": voucher_number,
                    "posting_date": posting_date,
                    "counter_account": counter_account,
                    "paid_amount": decimal_text(abs(parse_decimal(header.get("paid_amount")))),
                }
            )
            return

        remaining = abs(parse_decimal(header.get("paid_amount")))
        for ref_row in ref_rows:
            if remaining <= 0:
                break
            invoice = reference_invoice(party_type, party, clean(ref_row.get("reference_name")))
            if not invoice:
                continue
            allocated = allocate_to_invoice(invoice, min(abs(parse_decimal(ref_row.get("allocated_amount"))), remaining))
            remaining -= allocated

        if remaining > 0 and allocation_strategy != "none":
            candidates = find_candidates(by_party, party_type, party, posting_date)
            exact = [invoice for invoice in candidates if invoice.remaining == remaining]
            if len(exact) == 1:
                remaining -= allocate_to_invoice(exact[0], remaining)
            elif allocation_strategy == "fifo":
                for invoice in candidates:
                    if remaining <= 0:
                        break
                    remaining -= allocate_to_invoice(invoice, remaining)

        if remaining > 0:
            unallocated_by_party[party_key].append(
                {
                    "voucher_type": voucher_type,
                    "voucher_number": voucher_number,
                    "posting_date": posting_date,
                    "counter_account": counter_account,
                    "remaining_amount": decimal_text(remaining),
                    "remarks": clean(header.get("remarks")),
                }
            )

    for header in receipt_headers:
        process_header(header, receipt_refs.get(clean(header.get("voucher_key")), []))
    for header in payment_headers:
        process_header(header, payment_refs.get(clean(header.get("voucher_key")), []))

    return complex_by_party, unallocated_by_party


def review_bucket(outstanding_amount: Decimal, complex_rows: list[dict[str, object]], unallocated_rows: list[dict[str, object]]) -> str:
    if outstanding_amount <= Decimal("1000"):
        return "small_residual"
    if complex_rows:
        return "complex_party_voucher_followup"
    if unallocated_rows:
        return "manual_allocation_followup"
    return "likely_open_balance"


def summarize_examples(rows: list[dict[str, object]], amount_key: str) -> tuple[str, Decimal]:
    total = Decimal("0")
    examples: list[str] = []
    for row in rows:
        total += parse_decimal(row.get(amount_key))
        if len(examples) < 3:
            examples.append(f"{row['posting_date']} {row['voucher_type']} {row['voucher_number']} {decimal_text(parse_decimal(row.get(amount_key)))}")
    return "; ".join(examples), total


def build_review_rows(
    overdue_rows: list[dict[str, object]],
    party_type: str,
    invoice_key_prefix: str,
    complex_by_party: dict[str, list[dict[str, object]]],
    unallocated_by_party: dict[str, list[dict[str, object]]],
    invoice_states: dict[str, InvoiceState],
) -> list[dict[str, object]]:
    review_rows: list[dict[str, object]] = []
    for row in overdue_rows:
        tag = parse_tally_tag(row.get("remarks"))
        voucher_key = clean(tag.get("voucher_key"))
        invoice_state = invoice_states.get(f"{invoice_key_prefix}:{voucher_key}")
        party = clean(row.get("customer") or row.get("supplier"))
        posting_date = clean(row.get("posting_date"))
        party_key = f"{party_type}::{party}"
        complex_rows = [
            item for item in complex_by_party.get(party_key, [])
            if clean(item.get("posting_date")) >= posting_date
        ]
        unallocated_rows = [
            item for item in unallocated_by_party.get(party_key, [])
            if clean(item.get("posting_date")) >= posting_date
        ]
        complex_examples, complex_total = summarize_examples(complex_rows, "paid_amount")
        unallocated_examples, unallocated_total = summarize_examples(unallocated_rows, "remaining_amount")
        outstanding_amount = parse_decimal(row.get("outstanding_amount"))
        review_rows.append(
            {
                "invoice_name": clean(row.get("name")),
                "posting_date": posting_date,
                "party": party,
                "bill_no": clean(row.get("bill_no")),
                "tally_voucher_number": clean(tag.get("voucher_number")),
                "tally_voucher_key": voucher_key,
                "outstanding_amount": decimal_text(outstanding_amount),
                "predicted_remaining": decimal_text(invoice_state.remaining if invoice_state else Decimal("0")),
                "classification": review_bucket(outstanding_amount, complex_rows, unallocated_rows),
                "complex_party_voucher_count": len(complex_rows),
                "complex_party_voucher_total": decimal_text(complex_total),
                "complex_party_voucher_examples": complex_examples,
                "unallocated_party_entry_count": len(unallocated_rows),
                "unallocated_party_total": decimal_text(unallocated_total),
                "unallocated_party_examples": unallocated_examples,
            }
        )
    return review_rows


def write_report(
    path: Path,
    *,
    sales_rows: list[dict[str, object]],
    purchase_rows: list[dict[str, object]],
    allocation_strategy: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def category_counts(rows: list[dict[str, object]]) -> Counter[str]:
        counter: Counter[str] = Counter()
        for row in rows:
            counter[clean(row.get("classification"))] += 1
        return counter

    def overdue_total(rows: list[dict[str, object]]) -> Decimal:
        total = Decimal("0")
        for row in rows:
            total += parse_decimal(row.get("outstanding_amount"))
        return total

    def top_parties(rows: list[dict[str, object]]) -> list[tuple[str, Decimal]]:
        amounts: dict[str, Decimal] = defaultdict(Decimal)
        for row in rows:
            amounts[clean(row.get("party"))] += parse_decimal(row.get("outstanding_amount"))
        return sorted(amounts.items(), key=lambda item: item[1], reverse=True)[:10]

    lines = [
        "# ERPNext Remaining Overdue Review",
        "",
        f"- Allocation strategy replayed: `{allocation_strategy}`",
        f"- Remaining overdue Sales Invoices: `{len(sales_rows)}`",
        f"- Remaining overdue Sales total: `{decimal_text(overdue_total(sales_rows))}`",
        f"- Remaining overdue Purchase Invoices: `{len(purchase_rows)}`",
        f"- Remaining overdue Purchase total: `{decimal_text(overdue_total(purchase_rows))}`",
        "",
        "## Sales Buckets",
        "",
    ]
    for bucket, count in sorted(category_counts(sales_rows).items()):
        lines.append(f"- {bucket}: {count}")

    lines.extend(["", "## Purchase Buckets", ""])
    for bucket, count in sorted(category_counts(purchase_rows).items()):
        lines.append(f"- {bucket}: {count}")

    lines.extend(["", "## Top Remaining Sales Parties", ""])
    for party, amount in top_parties(sales_rows):
        lines.append(f"- {party}: `{decimal_text(amount)}`")

    lines.extend(["", "## Top Remaining Purchase Parties", ""])
    for party, amount in top_parties(purchase_rows):
        lines.append(f"- {party}: `{decimal_text(amount)}`")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `small_residual` usually means leftover rounding or a small partial difference after receipt/payment allocation.",
            "- `complex_party_voucher_followup` means the same party has staged receipt/payment vouchers that were too complex for the current importer path.",
            "- `manual_allocation_followup` means the same party still has eligible receipts/payments that could not be matched safely to invoices even after FIFO.",
            "- `likely_open_balance` means no obvious skipped or unmatched settlement artifact was found for that overdue invoice.",
        ]
    )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()

    overdue = load_live_overdue(args.site, args.company)
    invoice_states, by_party, sales_lookup, purchase_lookup = build_invoice_states(args.output_dir)
    complex_by_party, unallocated_by_party = replay_allocations(
        args.output_dir,
        by_party,
        sales_lookup,
        purchase_lookup,
        args.allocation_strategy,
    )

    sales_rows = build_review_rows(
        overdue_rows=overdue["sales"],
        party_type="Customer",
        invoice_key_prefix="sales",
        complex_by_party=complex_by_party,
        unallocated_by_party=unallocated_by_party,
        invoice_states=invoice_states,
    )
    purchase_rows = build_review_rows(
        overdue_rows=overdue["purchase"],
        party_type="Supplier",
        invoice_key_prefix="purchase",
        complex_by_party=complex_by_party,
        unallocated_by_party=unallocated_by_party,
        invoice_states=invoice_states,
    )

    write_csv(
        args.output_dir / "erpnext_sales_overdue_review.csv",
        [
            "invoice_name",
            "posting_date",
            "party",
            "bill_no",
            "tally_voucher_number",
            "tally_voucher_key",
            "outstanding_amount",
            "predicted_remaining",
            "classification",
            "complex_party_voucher_count",
            "complex_party_voucher_total",
            "complex_party_voucher_examples",
            "unallocated_party_entry_count",
            "unallocated_party_total",
            "unallocated_party_examples",
        ],
        sales_rows,
    )
    write_csv(
        args.output_dir / "erpnext_purchase_overdue_review.csv",
        [
            "invoice_name",
            "posting_date",
            "party",
            "bill_no",
            "tally_voucher_number",
            "tally_voucher_key",
            "outstanding_amount",
            "predicted_remaining",
            "classification",
            "complex_party_voucher_count",
            "complex_party_voucher_total",
            "complex_party_voucher_examples",
            "unallocated_party_entry_count",
            "unallocated_party_total",
            "unallocated_party_examples",
        ],
        purchase_rows,
    )
    write_report(
        args.report_dir / "overdue_history_review.md",
        sales_rows=sales_rows,
        purchase_rows=purchase_rows,
        allocation_strategy=args.allocation_strategy,
    )

    print(f"wrote {args.output_dir / 'erpnext_sales_overdue_review.csv'}")
    print(f"wrote {args.output_dir / 'erpnext_purchase_overdue_review.csv'}")
    print(f"wrote {args.report_dir / 'overdue_history_review.md'}")
    print(f"remaining overdue sales: {len(sales_rows)}")
    print(f"remaining overdue purchases: {len(purchase_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
