# Tally to ERPNext Cutover Checklist

This checklist is for the current site:

- Company: `Vara Lakshmi Agencies`
- ERPNext site: `business.manoharsolleti.com`
- Tally period checked: `1-Apr-2025` to `31-Mar-2026`

Use this when you want ERPNext opening balances on `1-Apr-2026` to match Tally closing balances on `31-Mar-2026`.

## What Is Already Done

- Customers imported
- Suppliers imported
- Items imported
- Addresses imported and linked
- Contacts imported and linked
- Contact mobile numbers fixed in ERPNext
- No accounting entries posted yet
- No stock entries posted yet

That means the ERPNext site is still clean for cutover posting.

## What Still Needs Your Tally Export

You still need these exact Tally reports from the same closing date, `31-Mar-2026`:

1. Ledger-wise Trial Balance
2. Item-wise Stock Summary with closing quantity and closing value
3. Bill-wise receivables and payables outstanding

Without those, stock and party parity can only be partial.

## Step-by-Step Plan

### Step 1: Take a Backup

Before posting any opening balances, take a backup of the ERPNext site.

This is your clean restore point.

### Step 2: Do Not Re-import Masters

Do not re-import:

- Customers
- Suppliers
- Items
- Addresses
- Contacts

Those are already present in ERPNext.

### Step 3: Export the Missing Tally Reports

From Tally, export:

1. Trial Balance as of `31-Mar-2026`
2. Stock Summary as of `31-Mar-2026`
3. Outstanding receivables/payables as of `31-Mar-2026`

Place them under `migration/tally/raw/` and keep the filenames obvious.

### Step 4: Confirm the Target Date Rule

Use this rule everywhere:

- Tally closing date: `31-Mar-2026`
- ERPNext opening date: `1-Apr-2026`

Do not mix dates between reports.

### Step 5: Post Party Openings

Create the opening receivables and payables first.

Use:

- `migration/tally/output/party_opening_balances_staging.csv`

If you want only total parity, one opening amount per party is enough.

If you want exact aging parity, use the Tally bill-wise outstanding export and create invoice-level openings.

### Step 6: Post Stock Opening

Do not use:

- `computed_stock_balances.csv`

That file uses transaction amounts and does not reconcile to Tally stock valuation.

Use Stock Reconciliation in ERPNext with the final item-wise Tally stock summary instead.

This is the file that still needs to be rebuilt from a detailed Tally stock export.

### Step 7: Post Non-party Ledger Openings

After party openings and stock opening are ready, post the remaining balances through one opening Journal Entry.

Use:

- `migration/tally/output/computed_ledger_balances.csv`
- `migration/tally/output/ledger_accounts_staging.csv`
- `migration/tally/output/trial_balance_xml_review.csv`

This covers balance sheet balances such as:

- Capital
- Bank
- Cash
- Duties and taxes

Do not carry prior-year profit and loss rows as opening balances on `1-Apr-2026`.

That means do not post opening entries for:

- Sales
- Purchases
- Indirect income
- Indirect expenses
- Other FY 2025-26 income or expense rows

Those belong to the year that ended on `31-Mar-2026`, not the new year opening.

### Step 8: Reconcile After Every Layer

Check parity in this order:

1. Stock totals match Tally stock summary
2. Customer and supplier totals match Tally outstanding
3. ERPNext Trial Balance matches Tally closing Trial Balance

Do not post the next layer until the current one matches.

## Important Warnings

- `computed_stock_balances.csv` is not suitable for final stock valuation posting.
- `opening_stock_staging.csv` has the correct total stock value, but the group breakup does not match the Tally stock summary screenshot.
- `opening_stock_from_stksum_staging.csv` is the better source for stock opening from the XML Stock Summary.
- No GL or stock entries have been posted yet, so now is the right time to finish the cutover correctly.

## Current Known Good Checks

These already match the Tally screenshot:

- Capital Account
- Loans (Liability)
- Current Liabilities
- Current Assets total
- Sales Accounts
- Purchase Accounts
- Indirect Income
- Indirect Expenses

## When You Have the Missing Tally Reports

Once the detailed Tally reports are placed in `migration/tally/raw/`, the next work is:

1. Rebuild the stock opening file
2. Prepare the final opening posting pack
3. Verify ERPNext parity against the Tally closing reports
