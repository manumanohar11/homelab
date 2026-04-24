# ERPNext Business Setup

[Back to README](../README.md)

ERPNext is the business management system in the `apps` bundle. Use it for customers, items or services, sales invoices, purchase invoices, accounts, stock, projects, CRM, HR, and reports.

This guide is written for normal business use, not for Docker experts.

## Open ERPNext

If you are on the same machine running Docker:

```text
http://localhost:8087
```

If you are opening it from another device on your home or office network:

```text
http://your-server-ip:8087
```

If your domain and reverse proxy are working:

```text
https://business.${DOMAIN_NAME}
```

In this stack the public URL is controlled by these `.env` values:

```text
DOMAIN_NAME=your-domain.com
ERPNEXT_SUBDOMAIN=business
ERPNEXT_BASE_URL=https://business.${DOMAIN_NAME}
ERPNEXT_HTTP_PORT=8087
```

Do not commit `.env`; it contains passwords.

## Login

The first administrator login is:

```text
Username: Administrator
Password: value of ERPNEXT_ADMIN_PASSWORD in .env
```

Do not paste the password into chat, tickets, docs, or commits.

After the first login, create named user accounts for real people instead of sharing `Administrator`.

## What `make` Means

`make` is only a shortcut runner. It reads the repo's `Makefile` and expands short commands into longer Docker Compose commands.

For example:

```bash
make up BUNDLES="apps"
```

means "start the starter stack plus the optional apps bundle".

You can still use ERPNext without understanding `make` deeply. The commands below are the ones you are most likely to need.

## Start ERPNext

From the repo folder:

```bash
cd /mnt/g/docker
make up BUNDLES="apps"
```

This starts the apps bundle, including ERPNext and other apps in that bundle.

To start only the main ERPNext long-running services:

```bash
make up BUNDLES="apps" SERVICE="erpnext-frontend erpnext-websocket erpnext-queue-short erpnext-queue-long erpnext-scheduler"
```

ERPNext also needs its database and Redis containers. Compose starts those automatically when needed.

## Check Status

```bash
cd /mnt/g/docker
docker compose -f docker-compose.yml -f docker-compose.apps.yml ps erpnext-frontend erpnext-backend erpnext-db erpnext-redis-cache erpnext-redis-queue
```

Healthy web containers should show:

```text
erpnext-backend    healthy
erpnext-frontend   healthy
```

Quick browser/API check:

```bash
curl http://localhost:8087/api/method/ping
```

Expected response:

```json
{"message":"pong"}
```

## Stop or Restart

Restart ERPNext web services:

```bash
cd /mnt/g/docker
docker compose -f docker-compose.yml -f docker-compose.apps.yml restart erpnext-frontend erpnext-backend erpnext-websocket erpnext-queue-short erpnext-queue-long erpnext-scheduler
```

Stop ERPNext services:

```bash
cd /mnt/g/docker
docker compose -f docker-compose.yml -f docker-compose.apps.yml stop erpnext-frontend erpnext-backend erpnext-websocket erpnext-queue-short erpnext-queue-long erpnext-scheduler
```

## First Business Setup

After logging in for the first time, ERPNext will show a setup wizard. Fill this carefully because it affects accounting and invoices.

Recommended order:

1. Set the correct country.
2. Set the correct timezone.
3. Set your main currency.
4. Enter your legal company name.
5. Set the fiscal year your accountant uses.
6. Use the standard chart of accounts unless your accountant gives you a custom one.
7. Create named user accounts for people who will use ERPNext.
8. Add taxes before sending real invoices.
9. Add your products or services as Items.
10. Add customers and suppliers.

Good first modules to learn:

```text
Customers
Suppliers
Items
Sales Invoice
Purchase Invoice
Payment Entry
Chart of Accounts
Bank Account
Taxes
Users
```

## Daily Business Flow

Simple service business flow:

1. Create or import customers.
2. Create Items for the services you sell.
3. Create Sales Invoices.
4. Record Payment Entries when customers pay.
5. Review Accounts Receivable.
6. Export or share reports with your accountant.

Simple inventory business flow:

1. Create Items.
2. Create Suppliers.
3. Create Purchase Invoices or Purchase Receipts.
4. Create Customers.
5. Create Sales Orders or Sales Invoices.
6. Review Stock Ledger and accounting reports.

Do not send real invoices until your company, taxes, invoice numbering, and chart of accounts have been reviewed.

## Tally Migration

This repo includes a first-pass Tally master converter:

```bash
cd /mnt/g/docker
python3 scripts/tally_to_erpnext.py
```

It reads:

```text
migration/tally/raw/JSON/Master.json
```

And writes review/import files under:

```text
migration/tally/output/
migration/tally/reports/
```

Use the generated customer, supplier, item, UOM, item group, warehouse, address, and contact CSVs for the first migration phase. Treat opening balance and ledger-account CSVs as staging files for review with your accountant before posting them in ERPNext.

See [Tally to ERPNext Migration](../migration/tally/README.md).

For the current `Vara Lakshmi Agencies` cutover on `1-Apr-2026`, use the XML-based opening pack generated by `scripts/tally_cutover_from_xml_reports.py` and follow [Step-by-Step Opening Process](../migration/tally/STEP_BY_STEP_OPENING_PROCESS.md). Do not use the older transaction-derived computed balance files as the final source if the XML cutover files are present.

ERPNext can keep multiple fiscal years in one site. If you want to open FY `2025-2026` reports and old invoices inside ERPNext, you must import the historical vouchers for that year. An opening-balance-only migration to `1-Apr-2026` will not show last year's invoice documents even if the fiscal year exists.

## Backups

ERPNext data lives under:

```text
${DOCKER_BASE_DIR}/erpnext
```

The repo has a backup helper:

```bash
cd /mnt/g/docker
./scripts/erpnext-backup.sh
```

Backup files are created under the ERPNext sites tree:

```text
${DOCKER_BASE_DIR}/erpnext/sites/<site>/private/backups
```

Also back up `.env`, because it contains the database and administrator passwords needed to recover cleanly.

## Troubleshooting

View frontend logs:

```bash
cd /mnt/g/docker
make logs BUNDLES="apps" SERVICE=erpnext-frontend
```

View backend logs:

```bash
cd /mnt/g/docker
make logs BUNDLES="apps" SERVICE=erpnext-backend
```

If `localhost:8087` does not open:

1. Check that `erpnext-frontend` is running and healthy.
2. Check that `erpnext-backend` is running and healthy.
3. Check logs for `erpnext-backend`.
4. Confirm the port in `.env`: `ERPNEXT_HTTP_PORT=8087`.
5. Try `curl http://localhost:8087/api/method/ping`.

If the domain URL does not open but `localhost:8087` works, ERPNext is probably fine and the issue is DNS, Pangolin, or reverse proxy routing.

## Safety Notes

- Do not expose ERPNext directly to the public internet without HTTPS and access controls.
- Do not share the `Administrator` account.
- Do not commit `.env`.
- Review backups before using ERPNext for real invoices.
- Make a test invoice first and confirm the PDF, tax, company address, and numbering are correct.
