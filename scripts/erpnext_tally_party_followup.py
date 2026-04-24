#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "migration" / "tally" / "output"
REPORT_DIR = REPO_ROOT / "migration" / "tally" / "reports"

PRIORITY_ORDER = {
    "manual_complex_allocation": 0,
    "manual_receipt_payment_allocation": 1,
    "confirm_open_balance": 2,
    "clear_small_residual": 3,
}

PRIORITY_ACTIONS = {
    "manual_complex_allocation": (
        "Review skipped Tally party vouchers, then create or adjust Payment Entries or Journal Entries "
        "and allocate them against the listed invoices before treating any remainder as open."
    ),
    "manual_receipt_payment_allocation": (
        "Use the unmatched receipt or payment examples to allocate the settlement manually against the "
        "listed invoices."
    ),
    "confirm_open_balance": (
        "Confirm this overdue balance is genuinely still open in Tally as of 2026-03-31. If not, book "
        "the missing settlement, credit note, or correction entry."
    ),
    "clear_small_residual": (
        "Small residual balance. If approved, clear it with a write-off or rounding cleanup; otherwise trace "
        "the minor mismatch."
    ),
}

CLASSIFICATION_ORDER = [
    "complex_party_voucher_followup",
    "manual_allocation_followup",
    "likely_open_balance",
    "small_residual",
]


@dataclass
class PartySummary:
    party: str
    invoice_count: int = 0
    outstanding_total: Decimal = Decimal("0")
    predicted_remaining_total: Decimal = Decimal("0")
    oldest_invoice_date: str = ""
    newest_invoice_date: str = ""
    largest_invoice_name: str = ""
    largest_invoice_amount: Decimal = Decimal("0")
    classification_counts: Counter[str] = field(default_factory=Counter)
    invoice_examples: list[str] = field(default_factory=list)
    complex_voucher_example_total: Decimal = Decimal("0")
    complex_voucher_examples: list[str] = field(default_factory=list)
    unallocated_entry_example_total: Decimal = Decimal("0")
    unallocated_entry_examples: list[str] = field(default_factory=list)

    def add_row(self, row: dict[str, str]) -> None:
        posting_date = clean(row.get("posting_date"))
        outstanding_amount = parse_decimal(row.get("outstanding_amount"))
        predicted_remaining = parse_decimal(row.get("predicted_remaining"))
        classification = clean(row.get("classification"))
        invoice_name = clean(row.get("invoice_name"))

        self.invoice_count += 1
        self.outstanding_total += outstanding_amount
        self.predicted_remaining_total += predicted_remaining
        self.classification_counts[classification] += 1

        if not self.oldest_invoice_date or posting_date < self.oldest_invoice_date:
            self.oldest_invoice_date = posting_date
        if not self.newest_invoice_date or posting_date > self.newest_invoice_date:
            self.newest_invoice_date = posting_date
        if outstanding_amount > self.largest_invoice_amount:
            self.largest_invoice_amount = outstanding_amount
            self.largest_invoice_name = invoice_name

        invoice_example = f"{invoice_name} {decimal_text(outstanding_amount)}"
        append_unique_limited(self.invoice_examples, invoice_example)

        for example in split_examples(row.get("complex_party_voucher_examples")):
            if append_unique_limited(self.complex_voucher_examples, example):
                self.complex_voucher_example_total += example_amount(example)
        for example in split_examples(row.get("unallocated_party_examples")):
            if append_unique_limited(self.unallocated_entry_examples, example):
                self.unallocated_entry_example_total += example_amount(example)

    @property
    def priority_bucket(self) -> str:
        if self.classification_counts["complex_party_voucher_followup"] > 0:
            return "manual_complex_allocation"
        if self.classification_counts["manual_allocation_followup"] > 0:
            return "manual_receipt_payment_allocation"
        if self.classification_counts["likely_open_balance"] > 0:
            return "confirm_open_balance"
        return "clear_small_residual"

    @property
    def recommended_action(self) -> str:
        return PRIORITY_ACTIONS[self.priority_bucket]

    @property
    def delta_total(self) -> Decimal:
        return self.outstanding_total - self.predicted_remaining_total

    @property
    def classification_mix(self) -> str:
        parts: list[str] = []
        for key in CLASSIFICATION_ORDER:
            count = self.classification_counts.get(key, 0)
            if count:
                parts.append(f"{key}={count}")
        return "; ".join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a party-level follow-up queue from ERPNext overdue review CSV outputs."
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
        "--report-limit",
        type=int,
        default=12,
        help="Maximum parties to print per report section. Default: 12.",
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


def split_examples(value: object) -> list[str]:
    text = clean(value)
    if not text:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def append_unique_limited(items: list[str], value: str, *, limit: int = 5) -> bool:
    if not value or value in items or len(items) >= limit:
        return False
    items.append(value)
    return True


def example_amount(value: str) -> Decimal:
    parts = clean(value).split()
    if not parts:
        return Decimal("0")
    return parse_decimal(parts[-1])


def build_party_summaries(rows: list[dict[str, str]]) -> list[PartySummary]:
    grouped: dict[str, PartySummary] = {}
    for row in rows:
        party = clean(row.get("party"))
        if not party:
            continue
        summary = grouped.setdefault(party, PartySummary(party=party))
        summary.add_row(row)
    return sorted(
        grouped.values(),
        key=lambda summary: (
            PRIORITY_ORDER[summary.priority_bucket],
            -summary.outstanding_total,
            summary.party.lower(),
        ),
    )


def summary_rows(doctype_label: str, summaries: list[PartySummary]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, summary in enumerate(summaries, start=1):
        rows.append(
            {
                "queue_rank": index,
                "doctype_group": doctype_label,
                "priority_bucket": summary.priority_bucket,
                "recommended_action": summary.recommended_action,
                "party": summary.party,
                "invoice_count": summary.invoice_count,
                "oldest_invoice_date": summary.oldest_invoice_date,
                "newest_invoice_date": summary.newest_invoice_date,
                "outstanding_total": decimal_text(summary.outstanding_total),
                "predicted_remaining_total": decimal_text(summary.predicted_remaining_total),
                "live_vs_replay_delta_total": decimal_text(summary.delta_total),
                "largest_invoice_name": summary.largest_invoice_name,
                "largest_invoice_amount": decimal_text(summary.largest_invoice_amount),
                "classification_mix": summary.classification_mix,
                "invoice_examples": "; ".join(summary.invoice_examples),
                "complex_voucher_example_total": decimal_text(summary.complex_voucher_example_total),
                "complex_voucher_examples": "; ".join(summary.complex_voucher_examples),
                "unallocated_entry_example_total": decimal_text(summary.unallocated_entry_example_total),
                "unallocated_entry_examples": "; ".join(summary.unallocated_entry_examples),
            }
        )
    return rows


def priority_totals(summaries: list[PartySummary]) -> list[tuple[str, int, Decimal]]:
    counts: dict[str, int] = defaultdict(int)
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for summary in summaries:
        counts[summary.priority_bucket] += 1
        totals[summary.priority_bucket] += summary.outstanding_total
    return [
        (bucket, counts[bucket], totals[bucket])
        for bucket in PRIORITY_ORDER
        if counts[bucket]
    ]


def section_lines(
    title: str,
    bucket: str,
    summaries: list[PartySummary],
    report_limit: int,
) -> list[str]:
    matching = [summary for summary in summaries if summary.priority_bucket == bucket]
    if not matching:
        return [f"## {title}", "", "- None.", ""]

    lines = [f"## {title}", ""]
    for summary in matching[:report_limit]:
        lines.append(
            f"- `{summary.party}`: `{decimal_text(summary.outstanding_total)}` across "
            f"`{summary.invoice_count}` invoices."
        )
        lines.append(f"  Action: {summary.recommended_action}")
        lines.append(f"  Mix: `{summary.classification_mix}`")
        lines.append(f"  Invoice examples: `{'; '.join(summary.invoice_examples)}`")
        if summary.complex_voucher_examples:
            lines.append(f"  Voucher clues: `{'; '.join(summary.complex_voucher_examples)}`")
        if summary.unallocated_entry_examples:
            lines.append(f"  Unallocated clues: `{'; '.join(summary.unallocated_entry_examples)}`")
    lines.append("")
    return lines


def write_report(
    path: Path,
    *,
    sales_summaries: list[PartySummary],
    purchase_summaries: list[PartySummary],
    report_limit: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# ERPNext Overdue Party Follow-up",
        "",
        "Queue ordering: `manual_complex_allocation`, `manual_receipt_payment_allocation`, "
        "`confirm_open_balance`, then `clear_small_residual`. Within each queue, larger balances come first.",
        "",
        "## Sales Queue Summary",
        "",
    ]

    for bucket, count, total in priority_totals(sales_summaries):
        lines.append(f"- {bucket}: `{count}` parties / `{decimal_text(total)}`")

    lines.extend(["", "## Purchase Queue Summary", ""])
    for bucket, count, total in priority_totals(purchase_summaries):
        lines.append(f"- {bucket}: `{count}` parties / `{decimal_text(total)}`")

    lines.append("")
    lines.extend(section_lines("Sales Manual Complex Allocation", "manual_complex_allocation", sales_summaries, report_limit))
    lines.extend(
        section_lines(
            "Sales Manual Receipt or Payment Allocation",
            "manual_receipt_payment_allocation",
            sales_summaries,
            report_limit,
        )
    )
    lines.extend(section_lines("Sales Open Balance Confirmation", "confirm_open_balance", sales_summaries, report_limit))
    lines.extend(section_lines("Sales Small Residual Cleanup", "clear_small_residual", sales_summaries, report_limit))
    lines.extend(section_lines("Purchase Open Balance Confirmation", "confirm_open_balance", purchase_summaries, report_limit))
    lines.extend(section_lines("Purchase Small Residual Cleanup", "clear_small_residual", purchase_summaries, report_limit))

    lines.extend(
        [
            "## Operator Notes",
            "",
            "- Use the party-level CSVs for the full queue and the invoice-level overdue review CSVs for invoice detail.",
            "- `live_vs_replay_delta_total` close to zero means the Tally replay agrees with the live ERPNext outstanding balance.",
            "- Purchase overdue items currently have no staged complex or unallocated settlement clues, so they mostly need confirmation as genuine open payables or separate missing-settlement investigation.",
        ]
    )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()

    sales_review = read_csv(args.output_dir / "erpnext_sales_overdue_review.csv")
    purchase_review = read_csv(args.output_dir / "erpnext_purchase_overdue_review.csv")

    sales_summaries = build_party_summaries(sales_review)
    purchase_summaries = build_party_summaries(purchase_review)

    write_csv(
        args.output_dir / "erpnext_sales_party_followup.csv",
        [
            "queue_rank",
            "doctype_group",
            "priority_bucket",
            "recommended_action",
            "party",
            "invoice_count",
            "oldest_invoice_date",
            "newest_invoice_date",
            "outstanding_total",
            "predicted_remaining_total",
            "live_vs_replay_delta_total",
            "largest_invoice_name",
            "largest_invoice_amount",
            "classification_mix",
            "invoice_examples",
            "complex_voucher_example_total",
            "complex_voucher_examples",
            "unallocated_entry_example_total",
            "unallocated_entry_examples",
        ],
        summary_rows("sales", sales_summaries),
    )
    write_csv(
        args.output_dir / "erpnext_purchase_party_followup.csv",
        [
            "queue_rank",
            "doctype_group",
            "priority_bucket",
            "recommended_action",
            "party",
            "invoice_count",
            "oldest_invoice_date",
            "newest_invoice_date",
            "outstanding_total",
            "predicted_remaining_total",
            "live_vs_replay_delta_total",
            "largest_invoice_name",
            "largest_invoice_amount",
            "classification_mix",
            "invoice_examples",
            "complex_voucher_example_total",
            "complex_voucher_examples",
            "unallocated_entry_example_total",
            "unallocated_entry_examples",
        ],
        summary_rows("purchase", purchase_summaries),
    )
    write_report(
        args.report_dir / "overdue_party_followup.md",
        sales_summaries=sales_summaries,
        purchase_summaries=purchase_summaries,
        report_limit=args.report_limit,
    )

    print(f"wrote {args.output_dir / 'erpnext_sales_party_followup.csv'}")
    print(f"wrote {args.output_dir / 'erpnext_purchase_party_followup.csv'}")
    print(f"wrote {args.report_dir / 'overdue_party_followup.md'}")
    print(f"sales parties queued: {len(sales_summaries)}")
    print(f"purchase parties queued: {len(purchase_summaries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
