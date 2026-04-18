#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MASTER_JSON = REPO_ROOT / "migration" / "tally" / "raw" / "JSON" / "Master.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "migration" / "tally" / "output"
DEFAULT_REPORT_DIR = REPO_ROOT / "migration" / "tally" / "reports"

INDIA_COUNTRY = "India"
DEFAULT_CUSTOMER_GROUP = "All Customer Groups"
DEFAULT_SUPPLIER_GROUP = "All Supplier Groups"
DEFAULT_TERRITORY = "All Territories"
DEFAULT_ITEM_GROUP = "All Item Groups"


@dataclass(frozen=True)
class PartyData:
    name: str
    parent: str
    mailing_name: str
    address_lines: list[str]
    state: str
    pincode: str
    country: str
    gstin: str
    gst_registration_type: str
    phone: str
    contact_name: str
    opening_balance: str
    opening_balance_value: Decimal | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Tally master JSON exports into ERPNext review/import CSVs."
    )
    parser.add_argument(
        "--master-json",
        type=Path,
        default=DEFAULT_MASTER_JSON,
        help=f"Path to Tally Master.json export. Default: {DEFAULT_MASTER_JSON}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for generated CSV files. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help=f"Directory for generated reports. Default: {DEFAULT_REPORT_DIR}",
    )
    parser.add_argument(
        "--company-name",
        default="",
        help="ERPNext company name to write into company-specific import rows, for example 'Vara Lakshmi Agencies'.",
    )
    parser.add_argument(
        "--company-abbr",
        default="",
        help="ERPNext company abbreviation, for example 'VLA'. Used to predict generated warehouse document names in staging files.",
    )
    parser.add_argument(
        "--warehouse-parent",
        default="",
        help="Existing ERPNext parent warehouse document name, for example 'All Warehouses - VLA'.",
    )
    return parser.parse_args()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    text = str(value)
    text = text.replace("\x04", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_tally_list_text(value: Any) -> list[str]:
    if isinstance(value, list):
        cleaned: list[str] = []
        for item in value:
            # Tally exports list metadata as {'metadata': True, 'type': 'String'}
            # before the actual values. It is not business data.
            if isinstance(item, dict) and item.get("metadata") is True:
                continue
            text = clean_text(item)
            if text:
                cleaned.append(text)
        return cleaned

    text = clean_text(value)
    return [text] if text else []


def first_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
        return {}
    if isinstance(value, dict):
        return value
    return {}


def list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def meta_name(message: dict[str, Any]) -> str:
    return clean_text(first_dict(message.get("metadata")).get("name"))


def meta_type(message: dict[str, Any]) -> str:
    return clean_text(first_dict(message.get("metadata")).get("type"))


def meta_reserved_name(message: dict[str, Any]) -> str:
    return clean_text(first_dict(message.get("metadata")).get("reservedname"))


def parse_tally_decimal(value: Any) -> Decimal | None:
    text = clean_text(value)
    if not text:
        return None

    sign = Decimal("-1") if re.search(r"\bCr\b", text, flags=re.IGNORECASE) else Decimal("1")
    if text.startswith("-"):
        sign *= Decimal("-1")

    match = re.search(r"-?\d+(?:,\d{2,3})*(?:\.\d+)?|-?\d+(?:\.\d+)?", text)
    if not match:
        return None

    number = match.group(0).replace(",", "")
    try:
        return Decimal(number).copy_abs() * sign
    except InvalidOperation:
        return None


def decimal_text(value: Decimal | None) -> str:
    if value is None:
        return ""
    normalized = value.normalize()
    return format(normalized, "f")


def parse_quantity_and_uom(value: Any) -> tuple[str, str]:
    text = clean_text(value)
    if not text:
        return "", ""
    match = re.match(r"^\s*(-?\d+(?:,\d{2,3})*(?:\.\d+)?|-?\d+(?:\.\d+)?)\s*(.*)$", text)
    if not match:
        return "", ""
    quantity = match.group(1).replace(",", "")
    uom = clean_text(match.group(2))
    return quantity, uom


def normalize_uom(name: str) -> str:
    cleaned = clean_text(name)
    if not cleaned:
        return "Nos"
    return cleaned


def load_tally_messages(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"missing Tally master export: {path}")

    # Tally JSON exports from this repo are UTF-16 LE. utf-16 also handles the BOM.
    with path.open("r", encoding="utf-16") as file:
        payload = json.load(file)

    messages = payload.get("tallymessage")
    if not isinstance(messages, list):
        raise ValueError("expected top-level 'tallymessage' array in Tally JSON export")
    return [message for message in messages if isinstance(message, dict)]


def party_from_ledger(message: dict[str, Any]) -> PartyData:
    mailing = first_dict(message.get("ledmailingdetails"))
    contact = first_dict(message.get("contactdetails"))
    gst = first_dict(message.get("ledgstregdetails"))

    address_value = mailing.get("address")
    address_lines = clean_tally_list_text(address_value)

    country = clean_text(mailing.get("country")) or clean_text(message.get("countryofresidence")) or INDIA_COUNTRY
    opening_balance = clean_text(message.get("openingbalance"))

    return PartyData(
        name=meta_name(message),
        parent=clean_text(message.get("parent")),
        mailing_name=clean_text(mailing.get("mailingname")) or meta_name(message),
        address_lines=address_lines,
        state=clean_text(mailing.get("state")) or clean_text(message.get("priorstatename")),
        pincode=clean_text(mailing.get("pincode")),
        country=country,
        gstin=clean_text(gst.get("gstin")) or clean_text(message.get("incometaxnumber")),
        gst_registration_type=clean_text(gst.get("gstregistrationtype")),
        phone=clean_text(contact.get("phonenumber")) or clean_text(message.get("ledgermobile")),
        contact_name=clean_text(contact.get("name")) or meta_name(message),
        opening_balance=opening_balance,
        opening_balance_value=parse_tally_decimal(opening_balance),
    )


def first_gst_rate(item: dict[str, Any]) -> str:
    for gst in list_of_dicts(item.get("gstdetails")):
        for statewise in list_of_dicts(gst.get("statewisedetails")):
            for rate_detail in list_of_dicts(statewise.get("ratedetails")):
                duty_head = clean_text(rate_detail.get("gstratedutyhead"))
                if duty_head and duty_head.lower() not in {"integrated tax", "central tax", "state tax", "cess"}:
                    continue
                rate = clean_text(rate_detail.get("gstrate"))
                if rate:
                    return rate
    return ""


def first_hsn_code(item: dict[str, Any]) -> str:
    for hsn in list_of_dicts(item.get("hsndetails")):
        code = clean_text(hsn.get("hsncode"))
        if code:
            return code
    return ""


def first_standard_rate(item: dict[str, Any]) -> str:
    rates: list[tuple[str, str]] = []
    for price in list_of_dicts(item.get("standardpricelist")):
        rate = clean_text(price.get("rate"))
        if rate:
            rates.append((clean_text(price.get("date")), rate))
    if not rates:
        return ""
    rates.sort(key=lambda row: row[0])
    return rates[-1][1]


def rows_to_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: clean_text(row.get(field, "")) for field in fieldnames})


def build_party_rows(parties: list[PartyData], party_type: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    master_rows: list[dict[str, Any]] = []
    address_rows: list[dict[str, Any]] = []
    contact_rows: list[dict[str, Any]] = []

    for party in parties:
        if party_type == "Customer":
            master_rows.append(
                {
                    "customer_name": party.name,
                    "customer_type": "Company",
                    "customer_group": DEFAULT_CUSTOMER_GROUP,
                    "territory": DEFAULT_TERRITORY,
                    "tax_id": party.gstin,
                    "tally_ledger_name": party.name,
                    "tally_parent_group": party.parent,
                    "tally_opening_balance": party.opening_balance,
                    "tally_opening_balance_value": decimal_text(party.opening_balance_value),
                }
            )
            link_doctype_key = "Customer"
        else:
            master_rows.append(
                {
                    "supplier_name": party.name,
                    "supplier_type": "Company",
                    "supplier_group": DEFAULT_SUPPLIER_GROUP,
                    "country": party.country,
                    "tax_id": party.gstin,
                    "tally_ledger_name": party.name,
                    "tally_parent_group": party.parent,
                    "tally_opening_balance": party.opening_balance,
                    "tally_opening_balance_value": decimal_text(party.opening_balance_value),
                }
            )
            link_doctype_key = "Supplier"

        address_line1 = party.address_lines[0] if party.address_lines else party.mailing_name
        address_line2 = ", ".join(party.address_lines[1:])
        address_rows.append(
            {
                "address_title": party.name,
                "address_type": "Billing",
                "address_line1": address_line1,
                "address_line2": address_line2,
                "city": party.state or "Unknown",
                "state": party.state,
                "pincode": party.pincode,
                "country": party.country,
                "is_primary_address": "1",
                "is_shipping_address": "1" if party_type == "Customer" else "0",
                "link_doctype": link_doctype_key,
                "link_name": party.name,
            }
        )

        if party.phone or party.contact_name:
            contact_rows.append(
                {
                    "first_name": party.contact_name or party.name,
                    "company_name": party.name,
                    "is_primary_contact": "1",
                    "phone": party.phone,
                    "mobile_no": party.phone,
                    "link_doctype": link_doctype_key,
                    "link_name": party.name,
                }
            )

    return master_rows, address_rows, contact_rows


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
        "Unsecured Loans": "Liability",
    }
    return mapping.get(parent_group, "Review")


def warehouse_docname(warehouse_name: str, company_abbr: str) -> str:
    if not warehouse_name or not company_abbr:
        return warehouse_name
    suffix = f" - {company_abbr}"
    if warehouse_name.endswith(suffix):
        return warehouse_name
    return f"{warehouse_name}{suffix}"


def build_outputs(
    messages: list[dict[str, Any]],
    *,
    company_name: str = "",
    company_abbr: str = "",
    warehouse_parent: str = "",
) -> dict[str, list[dict[str, Any]]]:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for message in messages:
        by_type.setdefault(meta_type(message), []).append(message)

    units = sorted({normalize_uom(meta_name(message)) for message in by_type.get("Unit", []) if meta_name(message)})
    stock_groups = sorted({meta_name(message) for message in by_type.get("Stock Group", []) if meta_name(message)})
    stock_categories = sorted({meta_name(message) for message in by_type.get("Stock Category", []) if meta_name(message)})
    item_groups = sorted(set(stock_groups + stock_categories + [DEFAULT_ITEM_GROUP]))

    warehouses = sorted({meta_name(message) for message in by_type.get("Godown", []) if meta_name(message)})
    warehouse_names_for_links = [warehouse_docname(warehouse, company_abbr) for warehouse in warehouses]
    ledgers = by_type.get("Ledger", [])
    customers = [party_from_ledger(message) for message in ledgers if clean_text(message.get("parent")) == "Sundry Debtors"]
    suppliers = [party_from_ledger(message) for message in ledgers if clean_text(message.get("parent")) == "Sundry Creditors"]

    customer_rows, customer_address_rows, customer_contact_rows = build_party_rows(customers, "Customer")
    supplier_rows, supplier_address_rows, supplier_contact_rows = build_party_rows(suppliers, "Supplier")
    party_opening_rows = [
        {
            "party_type": "Customer",
            "party": party.name,
            "tally_parent_group": party.parent,
            "tally_opening_balance": party.opening_balance,
            "tally_opening_balance_value": decimal_text(party.opening_balance_value),
            "recommended_erpnext_tool": "Opening Invoice Creation Tool",
            "notes": "Review as opening receivable before import.",
        }
        for party in customers
        if party.opening_balance
    ] + [
        {
            "party_type": "Supplier",
            "party": party.name,
            "tally_parent_group": party.parent,
            "tally_opening_balance": party.opening_balance,
            "tally_opening_balance_value": decimal_text(party.opening_balance_value),
            "recommended_erpnext_tool": "Opening Invoice Creation Tool",
            "notes": "Review as opening payable before import.",
        }
        for party in suppliers
        if party.opening_balance
    ]

    ledger_account_rows = []
    party_parent_groups = {"Sundry Debtors", "Sundry Creditors"}
    for ledger in ledgers:
        parent = clean_text(ledger.get("parent"))
        if parent in party_parent_groups:
            continue
        opening_balance = clean_text(ledger.get("openingbalance"))
        opening_balance_value = parse_tally_decimal(opening_balance)
        ledger_account_rows.append(
            {
                "ledger_name": meta_name(ledger),
                "tally_parent_group": parent,
                "suggested_erpnext_account_type": suggested_account_type(parent),
                "tally_opening_balance": opening_balance,
                "tally_opening_balance_value": decimal_text(opening_balance_value),
                "notes": "Review account mapping before Chart of Accounts import or opening journal entry.",
            }
        )

    item_rows: list[dict[str, Any]] = []
    item_review_rows: list[dict[str, Any]] = []
    opening_stock_rows: list[dict[str, Any]] = []
    for item in by_type.get("Stock Item", []):
        item_name = meta_name(item)
        if not item_name:
            continue

        base_uom = normalize_uom(clean_text(item.get("baseunits")))
        parent_group = clean_text(item.get("parent")) or clean_text(item.get("category")) or DEFAULT_ITEM_GROUP
        if parent_group not in item_groups:
            parent_group = DEFAULT_ITEM_GROUP

        opening_qty, opening_uom = parse_quantity_and_uom(item.get("openingbalance"))
        opening_value = parse_tally_decimal(item.get("openingvalue"))
        opening_rate = parse_tally_decimal(item.get("openingrate"))
        standard_rate = first_standard_rate(item)

        item_rows.append(
            {
                "item_code": item_name,
                "item_name": item_name,
                "item_group": parent_group,
                "stock_uom": base_uom,
                "is_stock_item": "1",
                "include_item_in_manufacturing": "0",
                "standard_rate": standard_rate,
                "valuation_rate": decimal_text(opening_rate),
                "description": item_name,
            }
        )
        item_review_rows.append(
            {
                "item_code": item_name,
                "gst_hsn_code": first_hsn_code(item),
                "tally_gst_rate": first_gst_rate(item),
                "tally_category": clean_text(item.get("category")),
                "tally_parent_group": clean_text(item.get("parent")),
                "tally_opening_balance": clean_text(item.get("openingbalance")),
                "tally_opening_value": clean_text(item.get("openingvalue")),
                "tally_opening_rate": clean_text(item.get("openingrate")),
            }
        )

        if opening_qty or opening_value is not None:
            opening_stock_rows.append(
                {
                    "item_code": item_name,
                    "warehouse": warehouse_names_for_links[0] if warehouse_names_for_links else "",
                    "qty": opening_qty,
                    "uom": opening_uom or base_uom,
                    "valuation_rate": decimal_text(opening_rate),
                    "amount": decimal_text(opening_value),
                    "tally_opening_balance": clean_text(item.get("openingbalance")),
                    "tally_opening_value": clean_text(item.get("openingvalue")),
                    "tally_opening_rate": clean_text(item.get("openingrate")),
                }
            )

    return {
        "uoms": [{"uom_name": unit, "enabled": "1"} for unit in units],
        "item_groups": [{"item_group_name": group, "parent_item_group": DEFAULT_ITEM_GROUP if group != DEFAULT_ITEM_GROUP else "", "is_group": "0"} for group in item_groups],
        "warehouses": [
            {
                "warehouse_name": warehouse,
                "parent_warehouse": warehouse_parent,
                "company": company_name,
                "is_group": "0",
            }
            for warehouse in warehouses
        ],
        "customers": customer_rows,
        "suppliers": supplier_rows,
        "addresses": customer_address_rows + supplier_address_rows,
        "contacts": customer_contact_rows + supplier_contact_rows,
        "items": item_rows,
        "item_master_review": item_review_rows,
        "opening_stock_staging": opening_stock_rows,
        "party_opening_balances_staging": party_opening_rows,
        "ledger_accounts_staging": ledger_account_rows,
        "_ledger_summary": [
            {
                "parent_group": group,
                "ledger_count": count,
            }
            for group, count in sorted(Counter(clean_text(message.get("parent")) for message in ledgers).items())
        ],
        "_type_summary": [
            {
                "type": type_name,
                "count": len(rows),
            }
            for type_name, rows in sorted(by_type.items())
        ],
    }


def write_outputs(outputs: dict[str, list[dict[str, Any]]], output_dir: Path, report_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    csv_specs = {
        "uoms.csv": ("uoms", ["uom_name", "enabled"]),
        "item_groups.csv": ("item_groups", ["item_group_name", "parent_item_group", "is_group"]),
        "warehouses.csv": (
            "warehouses",
            ["warehouse_name", "parent_warehouse", "company", "is_group"],
        ),
        "customers.csv": (
            "customers",
            [
                "customer_name",
                "customer_type",
                "customer_group",
                "territory",
                "tax_id",
            ],
        ),
        "customer_master_review.csv": (
            "customers",
            [
                "customer_name",
                "tax_id",
                "tally_ledger_name",
                "tally_parent_group",
                "tally_opening_balance",
                "tally_opening_balance_value",
            ],
        ),
        "suppliers.csv": (
            "suppliers",
            [
                "supplier_name",
                "supplier_type",
                "supplier_group",
                "country",
                "tax_id",
            ],
        ),
        "supplier_master_review.csv": (
            "suppliers",
            [
                "supplier_name",
                "tax_id",
                "tally_ledger_name",
                "tally_parent_group",
                "tally_opening_balance",
                "tally_opening_balance_value",
            ],
        ),
        "addresses.csv": (
            "addresses",
            [
                "address_title",
                "address_type",
                "address_line1",
                "address_line2",
                "city",
                "state",
                "pincode",
                "country",
                "is_primary_address",
                "is_shipping_address",
            ],
        ),
        "address_links_staging.csv": ("addresses", ["address_title", "link_doctype", "link_name"]),
        "contacts.csv": (
            "contacts",
            ["first_name", "company_name", "is_primary_contact", "phone", "mobile_no"],
        ),
        "contact_links_staging.csv": ("contacts", ["first_name", "company_name", "link_doctype", "link_name"]),
        "items.csv": (
            "items",
            [
                "item_code",
                "item_name",
                "item_group",
                "stock_uom",
                "is_stock_item",
                "include_item_in_manufacturing",
                "standard_rate",
                "valuation_rate",
                "description",
            ],
        ),
        "item_master_review.csv": (
            "item_master_review",
            [
                "item_code",
                "gst_hsn_code",
                "tally_gst_rate",
                "tally_category",
                "tally_parent_group",
                "tally_opening_balance",
                "tally_opening_value",
                "tally_opening_rate",
            ],
        ),
        "opening_stock_staging.csv": (
            "opening_stock_staging",
            [
                "item_code",
                "warehouse",
                "qty",
                "uom",
                "valuation_rate",
                "amount",
                "tally_opening_balance",
                "tally_opening_value",
                "tally_opening_rate",
            ],
        ),
        "party_opening_balances_staging.csv": (
            "party_opening_balances_staging",
            [
                "party_type",
                "party",
                "tally_parent_group",
                "tally_opening_balance",
                "tally_opening_balance_value",
                "recommended_erpnext_tool",
                "notes",
            ],
        ),
        "ledger_accounts_staging.csv": (
            "ledger_accounts_staging",
            [
                "ledger_name",
                "tally_parent_group",
                "suggested_erpnext_account_type",
                "tally_opening_balance",
                "tally_opening_balance_value",
                "notes",
            ],
        ),
    }

    for filename, (key, fields) in csv_specs.items():
        rows_to_csv(output_dir / filename, fields, outputs[key])

    rows_to_csv(report_dir / "ledger_group_summary.csv", ["parent_group", "ledger_count"], outputs["_ledger_summary"])
    rows_to_csv(report_dir / "tally_type_summary.csv", ["type", "count"], outputs["_type_summary"])
    write_summary(report_dir / "migration_summary.md", outputs)


def count_non_empty(rows: list[dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if clean_text(row.get(field)))


def write_summary(path: Path, outputs: dict[str, list[dict[str, Any]]]) -> None:
    customers = outputs["customers"]
    suppliers = outputs["suppliers"]
    contacts = outputs["contacts"]
    items = outputs["items"]
    item_review = outputs["item_master_review"]
    opening_stock = outputs["opening_stock_staging"]
    party_opening = outputs["party_opening_balances_staging"]
    ledger_accounts = outputs["ledger_accounts_staging"]

    lines = [
        "# Tally to ERPNext Migration Summary",
        "",
        "Generated from `migration/tally/raw/JSON/Master.json`.",
        "",
        "## Generated CSVs",
        "",
        f"- UOMs: {len(outputs['uoms'])}",
        f"- Item groups: {len(outputs['item_groups'])}",
        f"- Warehouses: {len(outputs['warehouses'])}",
        f"- Customers: {len(customers)}",
        f"- Suppliers: {len(suppliers)}",
        f"- Addresses: {len(outputs['addresses'])}",
        f"- Contacts: {len(outputs['contacts'])}",
        f"- Items: {len(items)}",
        f"- Opening stock staging rows: {len(opening_stock)}",
        f"- Party opening balance staging rows: {len(party_opening)}",
        f"- Non-party ledger account staging rows: {len(ledger_accounts)}",
        "",
        "## Data Coverage",
        "",
        f"- Customers with Tax ID value: {count_non_empty(customers, 'tax_id')} / {len(customers)}",
        f"- Contacts with mobile number: {count_non_empty(contacts, 'mobile_no')} / {len(contacts)}",
        f"- Customers with Tally opening balance: {count_non_empty(customers, 'tally_opening_balance')} / {len(customers)}",
        f"- Suppliers with Tax ID value: {count_non_empty(suppliers, 'tax_id')} / {len(suppliers)}",
        f"- Suppliers with Tally opening balance: {count_non_empty(suppliers, 'tally_opening_balance')} / {len(suppliers)}",
        f"- Items with HSN: {count_non_empty(item_review, 'gst_hsn_code')} / {len(items)}",
        f"- Items with standard rate: {count_non_empty(items, 'standard_rate')} / {len(items)}",
        f"- Items with valuation rate: {count_non_empty(items, 'valuation_rate')} / {len(items)}",
        "",
        "## Review Before Import",
        "",
        "- Confirm customer and supplier names are acceptable as ERPNext names.",
        "- Confirm tax IDs/GSTIN values in the review CSVs before using real invoices.",
        "- Confirm item groups and warehouses exist or import them first.",
        "- For Warehouse import, `parent_warehouse` must be an existing ERPNext Warehouse document name such as `All Warehouses - VLA`, not just `All Warehouses`.",
        "- Treat `opening_stock_staging.csv` as a review file, not a direct final posting.",
        "- Treat `party_opening_balances_staging.csv` as source data for ERPNext's Opening Invoice Creation Tool.",
        "- Treat `ledger_accounts_staging.csv` as accountant review material for chart/opening journal mapping.",
        "- `address_links_staging.csv` and `contact_links_staging.csv` preserve party-link targets; do not import those as normal DocTypes.",
        "- Do not import old transactions until masters and opening balances reconcile.",
        "",
        "## Suggested Import Order",
        "",
        "1. `uoms.csv`",
        "2. `item_groups.csv`",
        "3. `warehouses.csv`",
        "4. `customers.csv`",
        "5. `suppliers.csv`",
        "6. `items.csv`",
        "7. `addresses.csv` and `contacts.csv` only after deciding how to link them to parties.",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    messages = load_tally_messages(args.master_json)
    outputs = build_outputs(
        messages,
        company_name=args.company_name,
        company_abbr=args.company_abbr,
        warehouse_parent=args.warehouse_parent,
    )
    write_outputs(outputs, args.output_dir, args.report_dir)

    print(f"read {len(messages)} Tally master messages")
    print(f"wrote CSVs to {args.output_dir}")
    print(f"wrote reports to {args.report_dir}")
    print(f"customers: {len(outputs['customers'])}")
    print(f"suppliers: {len(outputs['suppliers'])}")
    print(f"items: {len(outputs['items'])}")
    print(f"opening stock staging rows: {len(outputs['opening_stock_staging'])}")
    print(f"party opening balance staging rows: {len(outputs['party_opening_balances_staging'])}")
    print(f"non-party ledger account staging rows: {len(outputs['ledger_accounts_staging'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
