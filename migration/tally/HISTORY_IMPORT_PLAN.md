# Tally Historical Voucher Migration Plan

This file is for the case where you want old Tally transactions to appear as real ERPNext documents, not just as opening balances.

For `Vara Lakshmi Agencies`, that means:

1. bring in the opening state on `2025-04-01`
2. import voucher history from `2025-04-01` to `2026-03-31`
3. later import `2026-04-01` onward in date order

ERPNext can hold multiple fiscal years at the same time.

For this migration, the target site can and should contain both:

- `2025-2026`
- `2026-2027`

If last year's invoices are missing, that is not because ERPNext only allows one fiscal year. It means the site currently has only opening balances and not the prior-year vouchers.

## Critical Rule

Do not load historical invoices, purchases, receipts, payments, or journals on top of the already-posted `2026-04-01` opening cutover.

That would double count:

- receivables
- payables
- stock
- cash and bank balances
- profit and loss

If you want full history inside ERPNext, the final target should be:

1. a fresh site, or
2. a restore from the pre-history-import state before the `2026-04-01` opening cutover was posted

## Source Data

### Opening state as of `2025-04-01`

Use:

- `migration/tally/raw/JSON/Master.json`
- `scripts/tally_to_erpnext.py`

This produces the master import files plus the `2025-04-01` opening review/staging files such as:

- `opening_stock_staging.csv`
- `party_opening_balances_staging.csv`
- `ledger_accounts_staging.csv`

### Historical voucher history

Use:

- `migration/tally/raw/JSON/Transactions.json`
- `scripts/tally_build_history_pack.py`

For the previous financial year:

```bash
python3 scripts/tally_build_history_pack.py \
  --from-date 2025-04-01 \
  --to-date 2026-03-31
```

For the current financial year up to today, rerun it with a different range, for example:

```bash
python3 scripts/tally_build_history_pack.py \
  --from-date 2026-04-01 \
  --to-date 2026-04-18
```

## Generated Files

The history pack writes staging files under `migration/tally/output/`:

- `historical_sales_invoices.csv`
- `historical_sales_invoice_items.csv`
- `historical_purchase_invoices.csv`
- `historical_purchase_invoice_items.csv`
- `historical_credit_notes.csv`
- `historical_credit_note_items.csv`
- `historical_receipts.csv`
- `historical_receipt_references.csv`
- `historical_payments.csv`
- `historical_payment_references.csv`
- `historical_journal_lines.csv`
- `historical_voucher_summary.csv`

And a review report:

- `migration/tally/reports/history_import_review.md`

For purchase vouchers, `historical_purchase_invoices.csv` now also carries
the supplier-facing Tally `reference` value. The ERPNext history importer uses
that to backfill `Purchase Invoice.bill_no` before applying supplier payment
references.

## What The History Pack Gives You

It does not post anything to ERPNext by itself.

It gives you:

1. filtered voucher history for a selected date range
2. invoice-level totals
3. item-level lines
4. GST-rate split by item group
5. receipt and payment bill-reference hints
6. journal line staging
7. a clean base for the ERPNext posting script

## Practical Import Order For Full History

On the target ERPNext site:

1. import masters
2. link addresses and contacts
3. post the `2025-04-01` opening state from the Tally master export
4. import historical purchases
5. import historical sales
6. import credit notes and returns
7. import receipts and payments
8. import journal vouchers
9. reconcile closing balances to `31-Mar-2026`
10. only then move on to `2026-04-01` onward

## ERPNext Importer Stages

`scripts/erpnext_tally_full_history.py` now supports:

1. `setup`
2. `opening`
3. `invoices`
4. `settlements`

The `settlements` stage does three things:

1. backfills `Purchase Invoice.bill_no` from staged Tally purchase references
2. creates party-side Payment Entries for receipts and payments
3. creates Journal Entries for Tally Journal vouchers and non-party cash/bank movements

## Unreferenced Settlement Allocation

Many Tally receipts and payments do not carry explicit bill allocations.

The importer supports these strategies through `--allocation-strategy`:

- `none`: keep unreferenced party vouchers fully unallocated
- `exact_unique`: allocate only when one same-party invoice on or before the voucher date matches the amount exactly
- `fifo`: after exact unique matches, allocate the remaining amount oldest-first across same-party open invoices on or before the voucher date

For this migration, `fifo` is the practical option when you want ERPNext invoice
statuses to look usable after history import. Any leftover amount that does not
fit a historical invoice stays as an unallocated advance or payment.

## Current Rebuild Notes

For the current repo automation:

- the full-history invoice stage temporarily enables ERPNext `Allow Negative Stock` during voucher backfill and restores the prior setting afterward
- this is needed because at least one item (`PC RIG 250ML M127`) is sold before its first recorded purchase in the FY 2025-2026 transaction history
- a small number of staged "purchase" vouchers have no item rows and zero totals; those are not real stock purchase invoices and should be handled later in the receipts/payments/journal phase, not in the invoice phase
- a small number of receipt/payment vouchers are still too complex for the current auto-import path, especially multi-party receipts with more than two ledger lines; those stay in the skipped bucket and need manual review or a later ledger-line importer

## Current Repo State

The repo already has a successful `2026-04-01` opening-balance cutover path.

That path is still valid if you only want to start ERPNext fresh from `1-Apr-2026`.

If you want last year's documents inside ERPNext, use this history-import track instead.
