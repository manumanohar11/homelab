#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "migration" / "tally" / "output"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create ERPNext Address and Contact records from generated Tally migration CSVs."
    )
    parser.add_argument(
        "--site",
        default="",
        help="ERPNext site name. Defaults to business.${DOMAIN_NAME} from .env.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Generated migration output directory. Default: {OUTPUT_DIR}",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write Address and Contact records. Without this, performs a dry run.",
    )
    return parser.parse_args()


def env_value(key: str) -> str:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def default_site() -> str:
    domain = env_value("DOMAIN_NAME")
    if not domain:
        raise SystemExit("DOMAIN_NAME is missing from .env; pass --site explicitly")
    return f"business.{domain}"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def paired_rows(data_rows: list[dict[str, str]], link_rows: list[dict[str, str]], kind: str) -> list[dict[str, str]]:
    if len(data_rows) != len(link_rows):
        raise SystemExit(
            f"{kind} row mismatch: data has {len(data_rows)} rows, links has {len(link_rows)} rows"
        )
    combined: list[dict[str, str]] = []
    for data, link in zip(data_rows, link_rows, strict=True):
        row = dict(data)
        row.update(
            {
                "link_doctype": link.get("link_doctype", ""),
                "link_name": link.get("link_name", ""),
            }
        )
        combined.append(row)
    return combined


def load_payload(output_dir: Path) -> dict[str, list[dict[str, str]]]:
    addresses = paired_rows(
        read_csv(output_dir / "addresses.csv"),
        read_csv(output_dir / "address_links_staging.csv"),
        "address",
    )
    contacts = paired_rows(
        read_csv(output_dir / "contacts.csv"),
        read_csv(output_dir / "contact_links_staging.csv"),
        "contact",
    )
    return {"addresses": addresses, "contacts": contacts}


def server_code(site: str, payload: dict[str, list[dict[str, str]]], apply: bool) -> str:
    payload_json = json.dumps(payload)
    return f"""
from __future__ import annotations

import json
import frappe

SITE = {site!r}
APPLY = {apply!r}
PAYLOAD = json.loads({payload_json!r})


def clean(value):
    return str(value or "").strip()


def target_exists(link_doctype, link_name):
    return bool(link_doctype and link_name and frappe.db.exists(link_doctype, link_name))


def has_link(doc, link_doctype, link_name):
    return any(
        clean(row.link_doctype) == link_doctype and clean(row.link_name) == link_name
        for row in doc.get("links", [])
    )


def address_match(row):
    link_doctype = clean(row.get("link_doctype"))
    link_name = clean(row.get("link_name"))
    if link_doctype and link_name:
        linked = frappe.get_all(
            "Dynamic Link",
            filters={{
                "parenttype": "Address",
                "link_doctype": link_doctype,
                "link_name": link_name,
            }},
            pluck="parent",
            limit_page_length=1,
        )
        if linked:
            return linked[0]

    filters = {{
        "address_title": clean(row.get("address_title")),
        "address_type": clean(row.get("address_type")),
        "address_line1": clean(row.get("address_line1")),
        "pincode": clean(row.get("pincode")),
    }}
    filters = {{key: value for key, value in filters.items() if value}}
    if not filters:
        return None
    matches = frappe.get_all("Address", filters=filters, pluck="name", limit_page_length=1)
    return matches[0] if matches else None


def contact_match(row):
    link_doctype = clean(row.get("link_doctype"))
    link_name = clean(row.get("link_name"))
    if link_doctype and link_name:
        linked = frappe.get_all(
            "Dynamic Link",
            filters={{
                "parenttype": "Contact",
                "link_doctype": link_doctype,
                "link_name": link_name,
            }},
            pluck="parent",
            limit_page_length=1,
        )
        if linked:
            return linked[0]

    filters = {{
        "first_name": clean(row.get("first_name")),
        "company_name": clean(row.get("company_name")),
        "mobile_no": clean(row.get("mobile_no")),
    }}
    filters = {{key: value for key, value in filters.items() if value}}
    if not filters:
        return None
    matches = frappe.get_all("Contact", filters=filters, pluck="name", limit_page_length=1)
    return matches[0] if matches else None


def sync_contact_phone_rows(doc, phone, mobile_no):
    desired_rows = []
    if phone and mobile_no and phone == mobile_no:
        desired_rows.append(
            {{
                "phone": phone,
                "is_primary_phone": 1,
                "is_primary_mobile_no": 1,
            }}
        )
    else:
        if phone:
            desired_rows.append(
                {{
                    "phone": phone,
                    "is_primary_phone": 1,
                    "is_primary_mobile_no": 0,
                }}
            )
        if mobile_no:
            desired_rows.append(
                {{
                    "phone": mobile_no,
                    "is_primary_phone": 0,
                    "is_primary_mobile_no": 1,
                }}
            )

    if not desired_rows:
        return False

    changed = False
    existing_rows = {{
        clean(phone_row.phone): phone_row
        for phone_row in doc.get("phone_nos", [])
        if clean(phone_row.phone)
    }}

    desired_numbers = {{row["phone"] for row in desired_rows}}
    for phone_row in doc.get("phone_nos", []):
        row_phone = clean(phone_row.phone)
        target = next((row for row in desired_rows if row["phone"] == row_phone), None)
        target_phone_flag = target["is_primary_phone"] if target else 0
        target_mobile_flag = target["is_primary_mobile_no"] if target else 0
        if (
            int(phone_row.is_primary_phone or 0) != target_phone_flag
            or int(phone_row.is_primary_mobile_no or 0) != target_mobile_flag
        ):
            phone_row.is_primary_phone = target_phone_flag
            phone_row.is_primary_mobile_no = target_mobile_flag
            changed = True

    for target in desired_rows:
        existing = existing_rows.get(target["phone"])
        if existing:
            continue
        doc.append("phone_nos", target)
        changed = True

    return changed


def upsert_address(row, stats):
    link_doctype = clean(row.get("link_doctype"))
    link_name = clean(row.get("link_name"))
    if not target_exists(link_doctype, link_name):
        stats["missing_address_targets"] += 1
        return

    existing = address_match(row)
    if existing:
        doc = frappe.get_doc("Address", existing)
        stats["existing_addresses"] += 1
        updates = {{
            "address_title": clean(row.get("address_title")),
            "address_type": clean(row.get("address_type")) or "Billing",
            "address_line1": clean(row.get("address_line1")) or clean(row.get("address_title")),
            "address_line2": clean(row.get("address_line2")),
            "city": clean(row.get("city")) or clean(row.get("state")) or "Unknown",
            "state": clean(row.get("state")),
            "pincode": clean(row.get("pincode")),
            "country": clean(row.get("country")) or "India",
            "is_primary_address": 1 if clean(row.get("is_primary_address")) in {{"1", "true", "True"}} else 0,
            "is_shipping_address": 1 if clean(row.get("is_shipping_address")) in {{"1", "true", "True"}} else 0,
        }}
        if any(clean(doc.get(field)) != clean(value) for field, value in updates.items()):
            for field, value in updates.items():
                doc.set(field, value)
            stats["addresses_updated"] += 1
    else:
        doc = frappe.get_doc({{
            "doctype": "Address",
            "address_title": clean(row.get("address_title")),
            "address_type": clean(row.get("address_type")) or "Billing",
            "address_line1": clean(row.get("address_line1")) or clean(row.get("address_title")),
            "address_line2": clean(row.get("address_line2")),
            "city": clean(row.get("city")) or clean(row.get("state")) or "Unknown",
            "state": clean(row.get("state")),
            "pincode": clean(row.get("pincode")),
            "country": clean(row.get("country")) or "India",
            "is_primary_address": 1 if clean(row.get("is_primary_address")) in {{"1", "true", "True"}} else 0,
            "is_shipping_address": 1 if clean(row.get("is_shipping_address")) in {{"1", "true", "True"}} else 0,
        }})
        stats["new_addresses"] += 1

    if not has_link(doc, link_doctype, link_name):
        doc.append("links", {{"link_doctype": link_doctype, "link_name": link_name}})
        stats["address_links_added"] += 1

    if APPLY:
        if existing:
            doc.save(ignore_permissions=True)
        else:
            doc.insert(ignore_permissions=True)


def upsert_contact(row, stats):
    link_doctype = clean(row.get("link_doctype"))
    link_name = clean(row.get("link_name"))
    if not target_exists(link_doctype, link_name):
        stats["missing_contact_targets"] += 1
        return

    phone = clean(row.get("phone"))
    mobile_no = clean(row.get("mobile_no"))
    updates = {{
        "first_name": clean(row.get("first_name")) or clean(row.get("company_name")) or link_name,
        "company_name": clean(row.get("company_name")),
        "is_primary_contact": 1 if clean(row.get("is_primary_contact")) in {{"1", "true", "True"}} else 0,
    }}

    existing = contact_match(row)
    if existing:
        doc = frappe.get_doc("Contact", existing)
        stats["existing_contacts"] += 1
        updated = False
        for field, value in updates.items():
            if clean(doc.get(field)) != clean(value):
                doc.set(field, value)
                updated = True
    else:
        doc = frappe.get_doc({{
            "doctype": "Contact",
            **updates,
        }})
        stats["new_contacts"] += 1
        updated = True

    if sync_contact_phone_rows(doc, phone, mobile_no):
        updated = True

    if not has_link(doc, link_doctype, link_name):
        doc.append("links", {{"link_doctype": link_doctype, "link_name": link_name}})
        stats["contact_links_added"] += 1
        updated = True

    if updated:
        stats["contacts_updated"] += 1

    if APPLY:
        if existing:
            doc.save(ignore_permissions=True)
        else:
            doc.insert(ignore_permissions=True)


stats = {{
    "mode": "apply" if APPLY else "dry-run",
    "address_rows": len(PAYLOAD["addresses"]),
    "contact_rows": len(PAYLOAD["contacts"]),
    "new_addresses": 0,
    "existing_addresses": 0,
    "addresses_updated": 0,
    "address_links_added": 0,
    "missing_address_targets": 0,
    "new_contacts": 0,
    "existing_contacts": 0,
    "contacts_updated": 0,
    "contact_links_added": 0,
    "missing_contact_targets": 0,
}}

frappe.init(site=SITE, sites_path=".")
frappe.connect()
try:
    for row in PAYLOAD["addresses"]:
        upsert_address(row, stats)
    for row in PAYLOAD["contacts"]:
        upsert_contact(row, stats)
    if APPLY:
        frappe.db.commit()
finally:
    frappe.destroy()

print(json.dumps(stats, indent=2, sort_keys=True))
"""


def run_in_container(site: str, payload: dict[str, list[dict[str, str]]], apply: bool) -> None:
    code = server_code(site, payload, apply)
    cmd = [
        "docker",
        "compose",
        "-f",
        "docker-compose.yml",
        "-f",
        "docker-compose.apps.yml",
        "exec",
        "-T",
        "erpnext-backend",
        "bash",
        "-lc",
        "mkdir -p /home/frappe/logs && cd /home/frappe/frappe-bench/sites && ../env/bin/python -",
    ]
    subprocess.run(cmd, cwd=REPO_ROOT, input=code, text=True, check=True)


def main() -> int:
    args = parse_args()
    site = args.site or default_site()
    payload = load_payload(args.output_dir)
    run_in_container(site, payload, args.apply)
    if not args.apply:
        print("Dry run only. Re-run with --apply to write Address and Contact records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
