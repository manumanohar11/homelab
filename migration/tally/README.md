# Tally to ERPNext Migration

This folder is for local Tally export files and generated ERPNext import files.

The business data folders are gitignored:

```text
migration/tally/raw/
migration/tally/output/
migration/tally/reports/
```

## Expected Raw Files

Export from Tally as JSON and place files here:

```text
migration/tally/raw/JSON/Master.json
migration/tally/raw/JSON/Transactions.json
```

The first converter phase uses `Master.json`.

## Generate ERPNext Master Import CSVs

From the repo root:

```bash
python3 scripts/tally_to_erpnext.py
```

For the current ERPNext company in this stack, use:

```bash
python3 scripts/tally_to_erpnext.py \
  --company-name "Vara Lakshmi Agencies" \
  --company-abbr "VLA" \
  --warehouse-parent "All Warehouses - VLA"
```

The script writes CSVs under:

```text
migration/tally/output/
```

And review reports under:

```text
migration/tally/reports/
```

Review the generated files before importing anything into ERPNext.

## First Import Order

Use this order in ERPNext Data Import:

1. `uoms.csv`
2. `item_groups.csv`
3. `warehouses.csv`
4. `customers.csv`
5. `suppliers.csv`
6. `items.csv`
7. `addresses.csv` and `contacts.csv` only after deciding how to link them to parties

Do not import these as normal DocTypes:

```text
customer_master_review.csv
supplier_master_review.csv
item_master_review.csv
address_links_staging.csv
contact_links_staging.csv
```

They preserve Tally/source metadata for review and later automation.

Use `opening_stock_staging.csv` only after reviewing stock valuation and choosing the ERPNext opening-stock method.

## Link Addresses and Contacts

After customers and suppliers exist in ERPNext, run a dry run:

```bash
python3 scripts/erpnext_import_party_contacts.py
```

If the dry run looks correct, create/update linked Address and Contact records:

```bash
python3 scripts/erpnext_import_party_contacts.py --apply
```

This uses:

```text
addresses.csv
contacts.csv
address_links_staging.csv
contact_links_staging.csv
```

For Warehouse import, `parent_warehouse` must be the existing ERPNext Warehouse document name. In this stack that is currently:

```text
All Warehouses - VLA
```

`All Warehouses` without the company suffix will fail because that exact Warehouse record does not exist.

Use these staging files for accountant/cutover review before posting balances:

```text
opening_stock_staging.csv
party_opening_balances_staging.csv
ledger_accounts_staging.csv
```

## Compute Closing Balances

After the master import is complete, compute review balances from the Tally master and transaction exports:

```bash
python3 scripts/tally_compute_balances.py
```

This reads:

```text
migration/tally/raw/JSON/Master.json
migration/tally/raw/JSON/Transactions.json
```

And writes:

```text
migration/tally/output/computed_ledger_balances.csv
migration/tally/output/computed_party_balances.csv
migration/tally/output/computed_stock_balances.csv
migration/tally/reports/balance_reconciliation.md
```

These are review files. Confirm them against Tally Trial Balance and Stock Summary before creating opening entries in ERPNext.
