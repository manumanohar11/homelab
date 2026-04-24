# Tally to ERPNext Cutover Checklist

This checklist is for the current live cutover only.

- Company: `Vara Lakshmi Agencies`
- ERPNext site: `business.manoharsolleti.com`
- Tally closing date: `31-Mar-2026`
- ERPNext opening date: `1-Apr-2026`

Use this together with [`STEP_BY_STEP_OPENING_PROCESS.md`](STEP_BY_STEP_OPENING_PROCESS.md).

## Current State

From the repo and the current cutover pack:

- customers imported
- suppliers imported
- items imported
- addresses imported and linked
- contacts imported and linked
- contact mobile numbers fixed
- fiscal year `2026-2027` exists
- no GL entries posted yet
- no stock ledger entries posted yet

That means the site is still clean for opening cutover posting.

## Backup Status

A fresh backup was taken before cutover:

- `business.manoharsolleti.com/private/backups/20260417_195335-business_manoharsolleti_com-database.sql.gz`
- `business.manoharsolleti.com/private/backups/20260417_195335-business_manoharsolleti_com-site_config_backup.json`

Do not post opening entries without keeping that restore point available.

## Current Source of Truth

Use these as the final cutover source of truth:

1. `scripts/tally_cutover_from_xml_reports.py`
2. `migration/tally/output/opening_accounts_to_create.csv`
3. `migration/tally/output/opening_journal_lines_review.csv`
4. `migration/tally/output/opening_stock_from_stksum_staging.csv`
5. `migration/tally/output/party_openings_from_trialbal.csv`
6. `migration/tally/output/non_party_balance_sheet_from_trialbal.csv`
7. `migration/tally/output/stock_group_summary_from_stksum.csv`
8. `migration/tally/output/trial_balance_xml_review.csv`
9. `migration/tally/output/temporary_opening_clearance_entry.csv`
10. `migration/tally/reports/xml_cutover_review.md`

Do not use the older transaction-derived computed files as the final source for this opening.

## Expected Numbers

From the current XML-based cutover pack:

- opening journal rows: `24`
- opening journal total debit: `37,48,653.17`
- opening journal total credit: `37,48,653.17`
- opening stock rows: `333`
- opening stock total: `37,99,074.02`
- remaining `Temporary Opening - VLA` credit after journal plus stock: `9,83,185.39`
- final clearance target: `Reserves and Surplus - VLA`

Stock group totals from `stock_group_summary_from_stksum.csv`:

- `12% GOODS`: `0`
- `18% GOODS`: `8,00,250.60`
- `5% GOODS`: `27,29,147.70`
- `EXEMPTED GOODS`: `2,69,675.72`

## Rules Before Posting

1. Do not re-import customers, suppliers, items, addresses, or contacts.
2. Do not use `Opening Stock` from Trial Balance as a journal row.
3. Do use stock from `opening_stock_from_stksum_staging.csv`.
4. Do use `Temporary Opening - VLA` as the balancing account for both the opening journal and stock reconciliation flow.
5. Do not carry FY `2025-2026` P&L rows into the `1-Apr-2026` opening.

## Next Exact Action

Your next action is:

1. open ERPNext
2. go to `Accounting > Chart of Accounts`
3. create any missing accounts listed in `migration/tally/output/opening_accounts_to_create.csv`

The current list is:

1. `CGST - VLA`
2. `Gadamsetty Venkateswara Rao - VLA`
3. `Indian Bank - VLA`
4. `Investment in Venkata Syamala Agencies - VLA`
5. `Provision for Gst - VLA`
6. `Punjab National Bank 3750 - VLA`
7. `SGST - VLA`
8. `Unavailed ITC - VLA`

For each account:

1. search the exact full account name first
2. if it already exists, do not create a duplicate
3. if it is missing, create it using the parent account, root type, and account type from `opening_accounts_to_create.csv`

## Posting Order After That

After the missing accounts are in place:

1. post `opening_journal_lines_review.csv` as one Opening Entry Journal Entry dated `2026-04-01`
2. post `opening_stock_from_stksum_staging.csv` through Stock Reconciliation dated `2026-04-01` with `Difference Account = Temporary Opening - VLA`
3. verify `Temporary Opening - VLA` shows credit `9,83,185.39`
4. post `temporary_opening_clearance_entry.csv`
5. verify `Temporary Opening - VLA` is zero

## Stop Conditions

Stop and review before proceeding if any of these happen:

- the opening journal does not balance to `37,48,653.17`
- stock total does not match `37,99,074.02`
- `Temporary Opening - VLA` is not credit `9,83,185.39` after journal plus stock
- ERPNext Trial Balance starts showing FY `2025-2026` income or expense ledgers as opening balances
