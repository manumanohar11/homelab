#!/usr/bin/env python3
"""Batch-reconcile straightforward customer sales balances in ERPNext.

This script uses ERPNext's Payment Reconciliation doctype methods instead of
writing directly to the database. It only auto-processes parties where the
unreconciled screen contains:

- invoices: Sales Invoice only
- payments: Payment Entry only

Anything involving Journal Entries, return invoices, or other mixed rows is
reported and skipped.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


BENCH_SITES_DIR = Path(os.environ.get("ERP_BENCH_SITES_DIR", "/home/frappe/frappe-bench/sites"))
DEFAULT_SITE = "business.manoharsolleti.com"
DEFAULT_COMPANY = "Vara Lakshmi Agencies"
DEFAULT_PARTY_TYPE = "Customer"
DEFAULT_ACCOUNT = "Debtors - VLA"
DEFAULT_OUTPUT = Path(os.environ.get("ERP_RECON_OUTPUT", "/tmp/erpnext_auto_reconcile_sales.csv"))
DEFAULT_ALLOWED_INVOICE_TYPES = {"Sales Invoice", "Purchase Invoice"}
DEFAULT_ALLOWED_PAYMENT_TYPES = {"Payment Entry"}
MIXED_ALLOWED_INVOICE_TYPES = {"Sales Invoice", "Purchase Invoice", "Journal Entry", "Payment Entry"}
MIXED_ALLOWED_PAYMENT_TYPES = {"Payment Entry", "Journal Entry", "Sales Invoice", "Purchase Invoice"}


def load_frappe(site: str, sites_dir: Path):
    os.chdir(sites_dir)
    import frappe  # type: ignore

    frappe.init(site=site)
    frappe.connect()
    return frappe


def destroy_frappe(frappe_mod) -> None:
    try:
        frappe_mod.destroy()
    except Exception:
        pass


@dataclass
class PartyResult:
    party: str
    status: str
    invoice_types: str
    payment_types: str
    invoice_count_before: int
    payment_count_before: int
    invoice_total_before: float
    payment_total_before: float
    allocation_count: int
    invoice_count_after: int
    payment_count_after: int
    invoice_total_after: float
    payment_total_after: float
    note: str


def child_rows_to_dicts(rows: Iterable) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        out.append(row.as_dict(no_default_fields=True))
    return out


def sum_field(rows: Iterable, fieldname: str) -> float:
    return round(sum(float(getattr(row, fieldname, 0) or 0) for row in rows), 2)


def fetch_candidate_parties(frappe_mod, party_type: str) -> list[str]:
    if party_type == "Customer":
        doctype = "Sales Invoice"
        party_field = "customer"
    elif party_type == "Supplier":
        doctype = "Purchase Invoice"
        party_field = "supplier"
    else:
        raise ValueError(f"unsupported party type: {party_type}")

    rows = frappe_mod.db.sql(
        f"""
        select distinct {party_field}
        from `tab{doctype}`
        where docstatus = 1
          and outstanding_amount > 0.009
        order by {party_field}
        """,
        as_list=True,
    )
    return [row[0] for row in rows]


def build_pr_doc(frappe_mod, company: str, party_type: str, party: str, account: str):
    pr = frappe_mod.new_doc("Payment Reconciliation")
    pr.company = company
    pr.party_type = party_type
    pr.party = party
    pr.receivable_payable_account = account
    pr.get_unreconciled_entries()
    return pr


def reconcile_party(
    frappe_mod,
    company: str,
    party_type: str,
    party: str,
    account: str,
    apply_changes: bool,
) -> PartyResult:
    pr = build_pr_doc(frappe_mod, company, party_type, party, account)

    invoice_types = sorted({row.invoice_type for row in pr.invoices})
    payment_types = sorted({row.reference_type for row in pr.payments})

    before = PartyResult(
        party=party,
        status="skip",
        invoice_types=",".join(invoice_types),
        payment_types=",".join(payment_types),
        invoice_count_before=len(pr.invoices),
        payment_count_before=len(pr.payments),
        invoice_total_before=sum_field(pr.invoices, "outstanding_amount"),
        payment_total_before=sum_field(pr.payments, "amount"),
        allocation_count=0,
        invoice_count_after=len(pr.invoices),
        payment_count_after=len(pr.payments),
        invoice_total_after=sum_field(pr.invoices, "outstanding_amount"),
        payment_total_after=sum_field(pr.payments, "amount"),
        note="",
    )

    if not pr.invoices:
        before.note = "no_invoices"
        return before
    if not pr.payments:
        before.note = "no_payments"
        return before
    if set(invoice_types) - reconcile_party.allowed_invoice_types or set(payment_types) - reconcile_party.allowed_payment_types:
        before.note = "mixed_types"
        return before

    invoice_payload = child_rows_to_dicts(pr.invoices)
    payment_payload = child_rows_to_dicts(pr.payments)

    pr.allocate_entries({"invoices": invoice_payload, "payments": payment_payload})
    allocation_count = len(pr.allocation)
    if not allocation_count:
        before.note = "no_allocation_rows"
        return before

    before.status = "dry_run"
    before.allocation_count = allocation_count
    before.note = "ready"

    if not apply_changes:
        return before

    total_allocations = 0
    rounds = 0
    max_rounds = 20
    while rounds < max_rounds:
        rounds += 1
        if not pr.invoices or not pr.payments:
            break

        invoice_types = sorted({row.invoice_type for row in pr.invoices})
        payment_types = sorted({row.reference_type for row in pr.payments})
        if set(invoice_types) - reconcile_party.allowed_invoice_types or set(payment_types) - reconcile_party.allowed_payment_types:
            break

        invoice_payload = child_rows_to_dicts(pr.invoices)
        payment_payload = child_rows_to_dicts(pr.payments)
        pr.allocate_entries({"invoices": invoice_payload, "payments": payment_payload})
        round_allocations = len(pr.allocation)
        if not round_allocations:
            break

        total_allocations += round_allocations
        before_invoice_total = sum_field(pr.invoices, "outstanding_amount")
        pr.reconcile()
        frappe_mod.db.commit()
        after_invoice_total = sum_field(pr.invoices, "outstanding_amount")
        if after_invoice_total >= before_invoice_total:
            break

    after = PartyResult(
        party=party,
        status="applied",
        invoice_types=before.invoice_types,
        payment_types=before.payment_types,
        invoice_count_before=before.invoice_count_before,
        payment_count_before=before.payment_count_before,
        invoice_total_before=before.invoice_total_before,
        payment_total_before=before.payment_total_before,
        allocation_count=total_allocations,
        invoice_count_after=len(pr.invoices),
        payment_count_after=len(pr.payments),
        invoice_total_after=sum_field(pr.invoices, "outstanding_amount"),
        payment_total_after=sum_field(pr.payments, "amount"),
        note=f"reconciled_rounds={rounds}",
    )
    return after


def write_report(path: Path, results: list[PartyResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(results[0]).keys()) if results else list(PartyResult.__annotations__.keys()))
        writer.writeheader()
        for row in results:
            writer.writerow(asdict(row))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=DEFAULT_SITE)
    parser.add_argument("--company", default=DEFAULT_COMPANY)
    parser.add_argument("--party-type", default=DEFAULT_PARTY_TYPE, choices=["Customer", "Supplier"])
    parser.add_argument("--account", default=DEFAULT_ACCOUNT)
    parser.add_argument("--apply", action="store_true", help="Apply reconciliations. Default is dry run.")
    parser.add_argument("--sites-dir", default=str(BENCH_SITES_DIR))
    parser.add_argument(
        "--allow-mixed-types",
        action="store_true",
        help="Allow ERPNext-native mixed reconciliation rows involving Sales Invoice, Payment Entry, and Journal Entry.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N candidate parties.")
    parser.add_argument("--party", action="append", default=[], help="Restrict to specific party name(s).")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    try:
        frappe_mod = load_frappe(args.site, Path(args.sites_dir))
    except Exception as exc:
        print(f"failed_to_connect: {exc}", file=sys.stderr)
        return 2

    try:
        parties = args.party or fetch_candidate_parties(frappe_mod, args.party_type)
        if args.limit:
            parties = parties[: args.limit]

        if args.allow_mixed_types:
            reconcile_party.allowed_invoice_types = set(MIXED_ALLOWED_INVOICE_TYPES)
            reconcile_party.allowed_payment_types = set(MIXED_ALLOWED_PAYMENT_TYPES)
        else:
            reconcile_party.allowed_invoice_types = set(DEFAULT_ALLOWED_INVOICE_TYPES)
            reconcile_party.allowed_payment_types = set(DEFAULT_ALLOWED_PAYMENT_TYPES)

        results: list[PartyResult] = []
        for party in parties:
            try:
                result = reconcile_party(
                    frappe_mod=frappe_mod,
                    company=args.company,
                    party_type=args.party_type,
                    party=party,
                    account=args.account,
                    apply_changes=args.apply,
                )
                results.append(result)
                print(
                    json.dumps(
                        {
                            "party": result.party,
                            "status": result.status,
                            "invoice_before": result.invoice_total_before,
                            "payment_before": result.payment_total_before,
                            "invoice_after": result.invoice_total_after,
                            "payment_after": result.payment_total_after,
                            "note": result.note,
                        },
                        sort_keys=True,
                    )
                )
            except Exception as exc:
                frappe_mod.db.rollback()
                failure = PartyResult(
                    party=party,
                    status="error",
                    invoice_types="",
                    payment_types="",
                    invoice_count_before=0,
                    payment_count_before=0,
                    invoice_total_before=0.0,
                    payment_total_before=0.0,
                    allocation_count=0,
                    invoice_count_after=0,
                    payment_count_after=0,
                    invoice_total_after=0.0,
                    payment_total_after=0.0,
                    note=str(exc),
                )
                results.append(failure)
                print(json.dumps({"party": party, "status": "error", "note": str(exc)}, sort_keys=True))
                if args.apply:
                    break

        write_report(Path(args.output), results)
        print(f"wrote {args.output}")
        return 0
    finally:
        destroy_frappe(frappe_mod)


if __name__ == "__main__":
    raise SystemExit(main())
