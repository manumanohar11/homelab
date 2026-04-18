#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MASTER_JSON = REPO_ROOT / "migration" / "tally" / "raw" / "JSON" / "Master.json"
DEFAULT_TRANSACTIONS_JSON = REPO_ROOT / "migration" / "tally" / "raw" / "JSON" / "Transactions.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "migration" / "tally" / "output"
DEFAULT_REPORT_DIR = REPO_ROOT / "migration" / "tally" / "reports"


@dataclass
class LedgerBalance:
    ledger_name: str
    parent_group: str
    opening: Decimal = Decimal("0")
    movement: Decimal = Decimal("0")
    movement_count: int = 0

    @property
    def closing(self) -> Decimal:
        return self.opening + self.movement


@dataclass
class StockBalance:
    item_code: str
    base_uom: str
    opening_qty: Decimal = Decimal("0")
    opening_value: Decimal = Decimal("0")
    movement_qty: Decimal = Decimal("0")
    movement_value: Decimal = Decimal("0")
    movement_count: int = 0

    @property
    def closing_qty(self) -> Decimal:
        return self.opening_qty + self.movement_qty

    @property
    def closing_value(self) -> Decimal:
        return self.opening_value + self.movement_value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute closing ledger, party, and stock balances from Tally master + transaction JSON exports."
    )
    parser.add_argument("--master-json", type=Path, default=DEFAULT_MASTER_JSON)
    parser.add_argument("--transactions-json", type=Path, default=DEFAULT_TRANSACTIONS_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    text = str(value).replace("\x04", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def metadata(message: dict[str, Any]) -> dict[str, Any]:
    meta = message.get("metadata")
    return meta if isinstance(meta, dict) else {}


def meta_name(message: dict[str, Any]) -> str:
    return clean_text(metadata(message).get("name"))


def meta_type(message: dict[str, Any]) -> str:
    return clean_text(metadata(message).get("type"))


def parse_decimal(value: Any) -> Decimal:
    text = clean_text(value)
    if not text:
        return Decimal("0")

    sign = Decimal("-1") if re.search(r"\bCr\b", text, flags=re.IGNORECASE) else Decimal("1")
    if re.search(r"\bDr\b", text, flags=re.IGNORECASE):
        sign = Decimal("1")

    match = re.search(r"-?\d+(?:,\d{2,3})*(?:\.\d+)?|-?\d+(?:\.\d+)?", text)
    if not match:
        return Decimal("0")

    number_text = match.group(0).replace(",", "")
    try:
        number = Decimal(number_text)
    except InvalidOperation:
        return Decimal("0")

    if "Dr" in text or "Cr" in text:
        return abs(number) * sign
    return number


def parse_quantity(value: Any) -> tuple[Decimal, str]:
    text = clean_text(value)
    if not text:
        return Decimal("0"), ""
    match = re.match(r"^\s*(-?\d+(?:,\d{2,3})*(?:\.\d+)?|-?\d+(?:\.\d+)?)\s*(.*)$", text)
    if not match:
        return Decimal("0"), ""
    try:
        quantity = Decimal(match.group(1).replace(",", ""))
    except InvalidOperation:
        quantity = Decimal("0")
    return quantity, clean_text(match.group(2))


def dec_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def dr_cr(value: Decimal) -> str:
    if value > 0:
        return "Dr"
    if value < 0:
        return "Cr"
    return ""


def load_messages(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-16") as file:
        payload = json.load(file)
    messages = payload.get("tallymessage")
    if not isinstance(messages, list):
        raise ValueError(f"{path} does not have a tallymessage list")
    return [message for message in messages if isinstance(message, dict)]


def suggested_account_type(parent_group: str) -> str:
    mapping = {
        "Bank Accounts": "Bank",
        "Bank OD A/c": "Bank",
        "Cash-in-Hand": "Cash",
        "Capital Account": "Equity",
        "Current Assets": "Asset",
        "Current Liabilities": "Liability",
        "Deposits (Asset)": "Asset",
        "Direct Expenses": "Expense Account",
        "Direct Incomes": "Income Account",
        "Duties & Taxes": "Tax",
        "Fixed Assets": "Fixed Asset",
        "Indirect Expenses": "Expense Account",
        "Indirect Incomes": "Income Account",
        "Loans (Liability)": "Liability",
        "Purchase Accounts": "Expense Account",
        "Sales Accounts": "Income Account",
        "Secured Loans": "Liability",
        "Sundry Creditors": "Payable",
        "Sundry Debtors": "Receivable",
        "Unsecured Loans": "Liability",
    }
    return mapping.get(parent_group, "Review")


def iter_ledger_movements(voucher: dict[str, Any]) -> list[tuple[str, str, Decimal]]:
    rows: list[tuple[str, str, Decimal]] = []
    for entry in voucher.get("allledgerentries") or []:
        if isinstance(entry, dict):
            rows.append(("allledgerentries", clean_text(entry.get("ledgername")), parse_decimal(entry.get("amount"))))

    for entry in voucher.get("ledgerentries") or []:
        if isinstance(entry, dict):
            rows.append(("ledgerentries", clean_text(entry.get("ledgername")), parse_decimal(entry.get("amount"))))

    for inventory_entry in voucher.get("allinventoryentries") or []:
        if not isinstance(inventory_entry, dict):
            continue
        for allocation in inventory_entry.get("accountingallocations") or []:
            if isinstance(allocation, dict):
                rows.append(
                    (
                        "accountingallocations",
                        clean_text(allocation.get("ledgername")),
                        parse_decimal(allocation.get("amount")),
                    )
                )
    return [(source, ledger, amount) for source, ledger, amount in rows if ledger]


def iter_stock_movements(voucher: dict[str, Any]) -> list[tuple[str, Decimal, Decimal, str]]:
    rows: list[tuple[str, Decimal, Decimal, str]] = []
    for inventory_entry in voucher.get("allinventoryentries") or []:
        if not isinstance(inventory_entry, dict):
            continue
        item = clean_text(inventory_entry.get("stockitemname"))
        if not item:
            continue
        qty, uom_text = parse_quantity(inventory_entry.get("actualqty") or inventory_entry.get("billedqty"))
        amount = parse_decimal(inventory_entry.get("amount"))
        rows.append((item, qty, amount, uom_text))
    return rows


def build_master_balances(master_messages: list[dict[str, Any]]) -> tuple[dict[str, LedgerBalance], dict[str, StockBalance]]:
    ledgers: dict[str, LedgerBalance] = {}
    stock: dict[str, StockBalance] = {}

    for message in master_messages:
        message_type = meta_type(message)
        if message_type == "Ledger":
            name = meta_name(message)
            if not name:
                continue
            ledgers[name] = LedgerBalance(
                ledger_name=name,
                parent_group=clean_text(message.get("parent")),
                opening=parse_decimal(message.get("openingbalance")),
            )
        elif message_type == "Stock Item":
            name = meta_name(message)
            if not name:
                continue
            opening_qty, opening_uom = parse_quantity(message.get("openingbalance"))
            stock[name] = StockBalance(
                item_code=name,
                base_uom=clean_text(message.get("baseunits")) or opening_uom,
                opening_qty=opening_qty,
                opening_value=parse_decimal(message.get("openingvalue")),
            )

    return ledgers, stock


def compute_balances(
    ledger_balances: dict[str, LedgerBalance],
    stock_balances: dict[str, StockBalance],
    transaction_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    voucher_type_counts: Counter[str] = Counter()
    voucher_type_ledger_sum: defaultdict[str, Decimal] = defaultdict(Decimal)
    voucher_type_inventory_sum: defaultdict[str, Decimal] = defaultdict(Decimal)
    unbalanced_count = 0
    unbalanced_examples: list[dict[str, str]] = []
    first_date = ""
    last_date = ""

    for message in transaction_messages:
        if meta_type(message) != "Voucher":
            continue
        voucher_type = clean_text(message.get("vouchertypename")) or "Unknown"
        voucher_date = clean_text(message.get("date"))
        if voucher_date:
            first_date = voucher_date if not first_date else min(first_date, voucher_date)
            last_date = voucher_date if not last_date else max(last_date, voucher_date)

        voucher_type_counts[voucher_type] += 1

        ledger_rows = iter_ledger_movements(message)
        voucher_total = Decimal("0")
        for _source, ledger_name, amount in ledger_rows:
            balance = ledger_balances.setdefault(
                ledger_name,
                LedgerBalance(ledger_name=ledger_name, parent_group=""),
            )
            balance.movement += amount
            balance.movement_count += 1
            voucher_total += amount
            voucher_type_ledger_sum[voucher_type] += amount

        if voucher_total != 0:
            unbalanced_count += 1
            if len(unbalanced_examples) < 20:
                unbalanced_examples.append(
                    {
                        "date": voucher_date,
                        "voucher_type": voucher_type,
                        "voucher_number": clean_text(message.get("vouchernumber")),
                        "ledger_movement_total": dec_text(voucher_total),
                    }
                )

        for item_code, quantity, amount, uom_text in iter_stock_movements(message):
            stock = stock_balances.setdefault(item_code, StockBalance(item_code=item_code, base_uom=uom_text))
            stock.movement_qty += quantity
            stock.movement_value += amount
            stock.movement_count += 1
            voucher_type_inventory_sum[voucher_type] += amount

    return {
        "voucher_type_counts": voucher_type_counts,
        "voucher_type_ledger_sum": voucher_type_ledger_sum,
        "voucher_type_inventory_sum": voucher_type_inventory_sum,
        "unbalanced_count": unbalanced_count,
        "unbalanced_examples": unbalanced_examples,
        "first_date": first_date,
        "last_date": last_date,
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: clean_text(row.get(field, "")) for field in fieldnames})


def output_rows(ledger_balances: dict[str, LedgerBalance], stock_balances: dict[str, StockBalance]) -> dict[str, list[dict[str, Any]]]:
    ledger_rows: list[dict[str, Any]] = []
    party_rows: list[dict[str, Any]] = []
    for balance in sorted(ledger_balances.values(), key=lambda row: (row.parent_group, row.ledger_name)):
        row = {
            "ledger_name": balance.ledger_name,
            "tally_parent_group": balance.parent_group,
            "suggested_erpnext_account_type": suggested_account_type(balance.parent_group),
            "opening_balance": dec_text(balance.opening),
            "transaction_movement": dec_text(balance.movement),
            "computed_closing_balance": dec_text(balance.closing),
            "closing_dr_cr": dr_cr(balance.closing),
            "transaction_entry_count": balance.movement_count,
        }
        ledger_rows.append(row)
        if balance.parent_group in {"Sundry Debtors", "Sundry Creditors"}:
            party_rows.append(
                {
                    "party_type": "Customer" if balance.parent_group == "Sundry Debtors" else "Supplier",
                    "party": balance.ledger_name,
                    "tally_parent_group": balance.parent_group,
                    "opening_balance": dec_text(balance.opening),
                    "transaction_movement": dec_text(balance.movement),
                    "computed_closing_balance": dec_text(balance.closing),
                    "closing_dr_cr": dr_cr(balance.closing),
                    "recommended_erpnext_tool": "Opening Invoice Creation Tool",
                    "notes": "Review before creating opening invoice.",
                }
            )

    stock_rows: list[dict[str, Any]] = []
    for stock in sorted(stock_balances.values(), key=lambda row: row.item_code):
        stock_rows.append(
            {
                "item_code": stock.item_code,
                "base_uom": stock.base_uom,
                "opening_qty": dec_text(stock.opening_qty),
                "transaction_qty": dec_text(stock.movement_qty),
                "computed_closing_qty": dec_text(stock.closing_qty),
                "opening_value": dec_text(stock.opening_value),
                "transaction_value": dec_text(stock.movement_value),
                "computed_closing_value": dec_text(stock.closing_value),
                "transaction_entry_count": stock.movement_count,
                "notes": "Review UOM conversions and valuation before opening stock import.",
            }
        )

    return {
        "computed_ledger_balances": ledger_rows,
        "computed_party_balances": party_rows,
        "computed_stock_balances": stock_rows,
    }


def write_outputs(
    output_dir: Path,
    report_dir: Path,
    ledger_balances: dict[str, LedgerBalance],
    stock_balances: dict[str, StockBalance],
    stats: dict[str, Any],
) -> None:
    rows = output_rows(ledger_balances, stock_balances)
    write_csv(
        output_dir / "computed_ledger_balances.csv",
        [
            "ledger_name",
            "tally_parent_group",
            "suggested_erpnext_account_type",
            "opening_balance",
            "transaction_movement",
            "computed_closing_balance",
            "closing_dr_cr",
            "transaction_entry_count",
        ],
        rows["computed_ledger_balances"],
    )
    write_csv(
        output_dir / "computed_party_balances.csv",
        [
            "party_type",
            "party",
            "tally_parent_group",
            "opening_balance",
            "transaction_movement",
            "computed_closing_balance",
            "closing_dr_cr",
            "recommended_erpnext_tool",
            "notes",
        ],
        rows["computed_party_balances"],
    )
    write_csv(
        output_dir / "computed_party_balances_nonzero.csv",
        [
            "party_type",
            "party",
            "tally_parent_group",
            "opening_balance",
            "transaction_movement",
            "computed_closing_balance",
            "closing_dr_cr",
            "recommended_erpnext_tool",
            "notes",
        ],
        [row for row in rows["computed_party_balances"] if parse_decimal(row.get("computed_closing_balance")) != 0],
    )
    write_csv(
        output_dir / "computed_stock_balances.csv",
        [
            "item_code",
            "base_uom",
            "opening_qty",
            "transaction_qty",
            "computed_closing_qty",
            "opening_value",
            "transaction_value",
            "computed_closing_value",
            "transaction_entry_count",
            "notes",
        ],
        rows["computed_stock_balances"],
    )
    write_csv(
        output_dir / "computed_stock_balances_nonzero.csv",
        [
            "item_code",
            "base_uom",
            "opening_qty",
            "transaction_qty",
            "computed_closing_qty",
            "opening_value",
            "transaction_value",
            "computed_closing_value",
            "transaction_entry_count",
            "notes",
        ],
        [
            row
            for row in rows["computed_stock_balances"]
            if parse_decimal(row.get("computed_closing_qty")) != 0
            or parse_decimal(row.get("computed_closing_value")) != 0
        ],
    )

    voucher_rows: list[dict[str, Any]] = []
    for voucher_type in sorted(stats["voucher_type_counts"]):
        voucher_rows.append(
            {
                "voucher_type": voucher_type,
                "voucher_count": stats["voucher_type_counts"][voucher_type],
                "ledger_movement_total": dec_text(stats["voucher_type_ledger_sum"].get(voucher_type, Decimal("0"))),
                "inventory_movement_total": dec_text(stats["voucher_type_inventory_sum"].get(voucher_type, Decimal("0"))),
            }
        )
    write_csv(
        report_dir / "computed_voucher_type_summary.csv",
        ["voucher_type", "voucher_count", "ledger_movement_total", "inventory_movement_total"],
        voucher_rows,
    )
    write_csv(
        report_dir / "unbalanced_voucher_examples.csv",
        ["date", "voucher_type", "voucher_number", "ledger_movement_total"],
        stats["unbalanced_examples"],
    )
    write_reconciliation_report(report_dir / "balance_reconciliation.md", rows, stats)


def count_non_zero(rows: list[dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if parse_decimal(row.get(field)) != 0)


def sum_field(rows: list[dict[str, Any]], field: str) -> Decimal:
    total = Decimal("0")
    for row in rows:
        total += parse_decimal(row.get(field))
    return total


def write_reconciliation_report(path: Path, rows: dict[str, list[dict[str, Any]]], stats: dict[str, Any]) -> None:
    ledger_rows = rows["computed_ledger_balances"]
    party_rows = rows["computed_party_balances"]
    stock_rows = rows["computed_stock_balances"]

    lines = [
        "# Tally Balance Reconciliation",
        "",
        f"Transaction date range: `{stats['first_date']}` to `{stats['last_date']}`",
        "",
        "## Output Files",
        "",
        "- `computed_ledger_balances.csv`",
        "- `computed_party_balances.csv`",
        "- `computed_party_balances_nonzero.csv`",
        "- `computed_stock_balances.csv`",
        "- `computed_stock_balances_nonzero.csv`",
        "- `computed_voucher_type_summary.csv`",
        "- `unbalanced_voucher_examples.csv`",
        "",
        "## Counts",
        "",
        f"- Ledger rows: {len(ledger_rows)}",
        f"- Party rows: {len(party_rows)}",
        f"- Stock rows: {len(stock_rows)}",
        f"- Voucher rows: {sum(stats['voucher_type_counts'].values())}",
        f"- Unbalanced vouchers after ledger/allocation expansion: {stats['unbalanced_count']}",
        "",
        "## Totals",
        "",
        f"- Ledger opening total: {dec_text(sum_field(ledger_rows, 'opening_balance'))}",
        f"- Ledger transaction movement total: {dec_text(sum_field(ledger_rows, 'transaction_movement'))}",
        f"- Ledger computed closing total: {dec_text(sum_field(ledger_rows, 'computed_closing_balance'))}",
        f"- Party computed closing total: {dec_text(sum_field(party_rows, 'computed_closing_balance'))}",
        f"- Stock computed closing value total: {dec_text(sum_field(stock_rows, 'computed_closing_value'))}",
        "",
        "## Non-zero Rows",
        "",
        f"- Ledgers with non-zero closing balance: {count_non_zero(ledger_rows, 'computed_closing_balance')}",
        f"- Parties with non-zero closing balance: {count_non_zero(party_rows, 'computed_closing_balance')}",
        f"- Items with non-zero closing quantity: {count_non_zero(stock_rows, 'computed_closing_qty')}",
        f"- Items with non-zero closing value: {count_non_zero(stock_rows, 'computed_closing_value')}",
        "",
        "## Review Notes",
        "",
        "- These files are computed review files, not direct ERPNext import files.",
        "- Positive party balances are usually receivables/debits; negative party balances are usually credits/payables.",
        "- Confirm these totals against Tally Trial Balance and Stock Summary before creating opening entries.",
        "- Stock quantities use the leading quantity in Tally's UOM text. Compound UOM conversions still need review.",
        "- Do not post opening balances in ERPNext until your accountant confirms the cutover totals.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    master_messages = load_messages(args.master_json)
    transaction_messages = load_messages(args.transactions_json)
    ledger_balances, stock_balances = build_master_balances(master_messages)
    stats = compute_balances(ledger_balances, stock_balances, transaction_messages)
    write_outputs(args.output_dir, args.report_dir, ledger_balances, stock_balances, stats)

    print(f"read master messages: {len(master_messages)}")
    print(f"read transaction messages: {len(transaction_messages)}")
    print(f"voucher rows: {sum(stats['voucher_type_counts'].values())}")
    print(f"unbalanced vouchers: {stats['unbalanced_count']}")
    print(f"wrote computed balances to {args.output_dir}")
    print(f"wrote reconciliation report to {args.report_dir / 'balance_reconciliation.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
