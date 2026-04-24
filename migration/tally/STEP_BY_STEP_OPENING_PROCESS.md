# Step-by-Step Opening Process

This is the exact cutover process for the current ERPNext site and the current Tally exports.

- ERPNext site: `business.manoharsolleti.com`
- Company: `Vara Lakshmi Agencies`
- Opening date in ERPNext: `1-Apr-2026`
- Tally closing date used: `31-Mar-2026`

This process is written for a beginner.

## Automation Option

If you want the repo to perform the ERPNext cutover steps for you, use:

```bash
python3 scripts/erpnext_tally_cutover.py
```

Recommended sequence:

```bash
python3 scripts/erpnext_tally_cutover.py
python3 scripts/erpnext_tally_cutover.py --apply
python3 scripts/erpnext_tally_cutover.py --apply --submit
```

- dry run first
- then create missing accounts and draft documents
- then submit them after one more review

If you prefer to control one step at a time, use `--stage accounts`, `--stage journal`, `--stage stock`, or `--stage clearance`.

## 1. What Was Cleaned Up

These older generated files were removed because they are not the right source for this cutover:

- `computed_ledger_balances.csv`
- `computed_party_balances.csv`
- `computed_party_balances_nonzero.csv`
- `computed_stock_balances.csv`
- `computed_stock_balances_nonzero.csv`
- `opening_stock_staging.csv`
- `party_opening_balances_staging.csv`
- `balance_reconciliation.md`
- `computed_voucher_type_summary.csv`
- `unbalanced_voucher_examples.csv`

Those files were either:

- based on transaction expansion instead of the direct Tally closing reports, or
- based on old opening figures instead of the closing figures needed for `1-Apr-2026`.

## 2. Files You Should Use Now

Use only these files for cutover:

- `migration/tally/output/opening_accounts_to_create.csv`
- `migration/tally/output/opening_journal_lines_review.csv`
- `migration/tally/output/opening_stock_from_stksum_staging.csv`
- `migration/tally/output/party_openings_from_trialbal.csv`
- `migration/tally/output/non_party_balance_sheet_from_trialbal.csv`
- `migration/tally/output/stock_group_summary_from_stksum.csv`
- `migration/tally/output/trial_balance_xml_review.csv`
- `migration/tally/output/temporary_opening_clearance_entry.csv`
- `migration/tally/reports/xml_cutover_review.md`

## 3. Safety Status Right Now

The ERPNext site is still safe for cutover:

- contacts fixed
- no stock ledger entries posted
- no GL entries posted
- fiscal year `2026-2027` exists

A fresh ERPNext backup was created before this process:

- `business.manoharsolleti.com/private/backups/20260417_195335-business_manoharsolleti_com-database.sql.gz`
- `business.manoharsolleti.com/private/backups/20260417_195335-business_manoharsolleti_com-site_config_backup.json`

## 4. Big Rules Before You Start

1. Do not re-import customers, suppliers, items, addresses, or contacts.
2. Do not use the old removed files.
3. Do not carry FY 2025-26 sales, purchases, or expense ledgers into the new year opening.
4. Use `Temporary Opening - VLA` as the balancing account during cutover.
5. Use the stock summary XML totals, not the Trial Balance `Opening Stock` row.

This cutover creates opening balances as of `2026-04-01`.

It does **not** create historical ERPNext transaction documents for:

- Sales Invoices
- Purchase Invoices
- Receipts
- Payments
- Credit Notes
- Delivery/stock movement history

for the prior period `2025-04-01` to `2026-03-31`.

If you need those old documents visible inside ERPNext, that is a separate voucher-history migration phase.

## 5. Numbers You Should Expect

From the current XML reports:

- Stock total to open: `37,99,074.02`
- `12% GOODS`: `0`
- `18% GOODS`: `8,00,250.60`
- `5% GOODS`: `27,29,147.70`
- `EXEMPTED GOODS`: `2,69,675.72`

After the opening journal and opening stock are posted, `Temporary Opening - VLA` should still show a credit balance of:

- `9,83,185.39`

That remaining amount should then be moved to:

- `Reserves and Surplus - VLA`

using the final clearance entry.

## 6. Step A: Create Missing Accounts

Open ERPNext.

Go to:

- `Accounting`
- `Chart of Accounts`

Create the accounts listed in:

- `migration/tally/output/opening_accounts_to_create.csv`

Create only the ones that are still missing.

Before creating each one:

1. search the exact full account name in Chart of Accounts
2. if it already exists, do not create a duplicate
3. if it is missing, create it exactly as shown

The accounts to create are:

1. `CGST - VLA`
2. `Gadamsetty Venkateswara Rao - VLA`
3. `Indian Bank - VLA`
4. `Investment in Venkata Syamala Agencies - VLA`
5. `Provision for Gst - VLA`
6. `Punjab National Bank 3750 - VLA`
7. `SGST - VLA`
8. `Unavailed ITC - VLA`

When creating each account:

1. Set the parent account from `opening_accounts_to_create.csv`
2. Set the root type from `opening_accounts_to_create.csv`
3. Set the account type when the file gives one
4. Save the account

Do not create party accounts for customers or suppliers. Those will use:

- `Debtors - VLA`
- `Creditors - VLA`

## 7. Step B: Post the Opening Journal Entry

This entry covers:

- non-stock balance sheet lines
- customer net openings
- supplier net openings

It does **not** cover stock.

Use:

- `migration/tally/output/opening_journal_lines_review.csv`

### Create the Journal Entry

Go to:

- `Accounting`
- `Journal Entry`
- `New`

Set:

1. `Posting Date` = `2026-04-01`
2. `Voucher Type` = `Opening Entry`
3. `Company` = `Vara Lakshmi Agencies`
4. Add a remark like `Tally cutover opening entry on 1-Apr-2026`

### Enter the Rows

Enter the rows exactly from:

- `opening_journal_lines_review.csv`

Important row rules:

- For normal non-party rows, use the `erpnext_account`, `debit`, and `credit` columns.
- For party rows, also fill:
  - `Party Type`
  - `Party`
- For the last balancing row, use:
  - `Temporary Opening - VLA`

### Important Notes for This Journal Entry

1. The row for `Tata Consumer Products Limited` is a supplier row with a **debit** balance. Enter it exactly that way.
2. The last row in the file is the balancing line:
   - `Temporary Opening - VLA`
   - debit `28,15,888.63`
3. Do not add stock lines to this journal entry.

### Before Submitting

Check that:

1. total debit equals total credit
2. all party rows have `Party Type` and `Party` filled
3. no row uses the wrong account name

Save.

Submit only after checking the totals.

## 8. Step C: Post Opening Stock

Use:

- `migration/tally/output/opening_stock_from_stksum_staging.csv`

and

- `migration/tally/output/stock_group_summary_from_stksum.csv`

### Create the Stock Reconciliation

Go to:

- `Stock`
- `Stock Reconciliation`
- `New`

Set these fields:

1. `Purpose` = `Opening Stock`
2. `Posting Date` = `2026-04-01`
3. `Default Warehouse` = `Main Location - VLA`
4. `Difference Account` = `Temporary Opening - VLA`

That `Difference Account` choice is important.  
Do **not** use `Stock Adjustment - VLA` for the opening cutover.

### Load the Stock Rows

Use the rows from:

- `opening_stock_from_stksum_staging.csv`

For each row use:

1. `Item Code`
2. `Warehouse`
3. `Quantity`
4. `Valuation Rate`

You do not need to type the old Tally text columns into ERPNext. They are there only for checking.

### 12% Goods Rule

Your stock summary says:

- `12% GOODS` total value = `0`

If you truly do not have any 12% stock physically, you may remove the zero-value 12% line before importing the stock rows.

### Before Submitting

Use:

- `stock_group_summary_from_stksum.csv`

to verify the totals you entered.

After the rows are loaded, confirm the total value matches:

- `37,99,074.02`

Then save and submit the Stock Reconciliation.

## 9. Step D: Check Temporary Opening

After:

- the opening Journal Entry is submitted, and
- the Stock Reconciliation is submitted,

go to the account:

- `Temporary Opening - VLA`

It should show a remaining **credit** balance of:

- `9,83,185.39`

If it does not, stop and re-check the previous two steps before going further.

## 10. Step E: Clear Temporary Opening

Now create one final Journal Entry.

Use:

- `migration/tally/output/temporary_opening_clearance_entry.csv`

Create a new Journal Entry with:

1. `Posting Date` = `2026-04-01`
2. `Voucher Type` = `Opening Entry`
3. `Company` = `Vara Lakshmi Agencies`
4. Remark like `Clear temporary opening after Tally cutover`

Enter these two rows:

1. Debit `Temporary Opening - VLA` = `9,83,185.39`
2. Credit `Reserves and Surplus - VLA` = `9,83,185.39`

Save and submit.

## 11. Step F: Final Checks

After all three postings are done:

1. open Trial Balance in ERPNext
2. run it for `2026-04-01`
3. confirm balance sheet accounts match the cutover files
4. check `Temporary Opening - VLA` is now zero
5. check `Stock In Hand - VLA` reflects the opening stock
6. check customer balances under `Debtors - VLA`
7. check supplier balances under `Creditors - VLA`

## 12. If Something Looks Wrong

If a total does not match:

1. do not keep posting more entries
2. check the exact row in the helper CSV
3. compare the posted document against:
   - `opening_journal_lines_review.csv`
   - `opening_stock_from_stksum_staging.csv`
   - `temporary_opening_clearance_entry.csv`
4. if needed, restore from the backup created before cutover

## 13. Short Version

If you want the shortest possible sequence:

1. create missing accounts
2. post `opening_journal_lines_review.csv`
3. post stock using `opening_stock_from_stksum_staging.csv` with `Temporary Opening - VLA`
4. confirm `Temporary Opening - VLA` = credit `9,83,185.39`
5. post `temporary_opening_clearance_entry.csv`
6. check final Trial Balance
