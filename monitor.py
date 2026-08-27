#!/usr/bin/env python3
"""
Fulton County Foreclosure Monitor
Writes results to Notion + optional Slack alerts
"""

import os
import re
import json
import hashlib
from datetime import datetime
from typing import Optional

import requests

from config import (
    HIGH_GROWTH_ZIPS,
    MIN_ASSESSED_FOR_FLAG,
    EQUITY_RATIO_THRESHOLD,
)

# ---------- Secrets (from GitHub Actions) ----------
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "8d25a71707d4446ebcdf9b28f8abce23")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK", "")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def fetch_recent_notices() -> list[dict]:
    """
    PLACEHOLDER – replace this later with real scraping from
    Georgia Public Notice or Fulton Neighbor.
    """
    print("WARNING: Using placeholder fetch_recent_notices(). No real notices yet.")
    return []


def parse_notice(text: str, source_url: str = "") -> Optional[dict]:
    if not text:
        return None

    sale_match = re.search(
        r"first Tuesday (?:in|of)\s+(\w+),?\s+(\d{4})",
        text,
        re.IGNORECASE,
    )
    addr_match = re.search(
        r"(?:commonly known as|property (?:located )?at|known as)[:\s]+"
        r"([^\n]+?(?:GA|Georgia)?\s*\d{5}(?:-\d{4})?)",
        text,
        re.IGNORECASE,
    )
    owner_match = re.search(
        r"(?:executed by|Security Deed from|Grantor[:\s]+)"
        r"([A-Z][A-Za-z0-9\s,&\.\-']+?)(?:\s+to|\s+dated|,\s+hereinafter)",
        text,
    )
    principal_match = re.search(
        r"original principal amount of[^\d$]*\$?([\d,]+\.?\d*)",
        text,
        re.IGNORECASE,
    )
    parcel_match = re.search(
        r"(?:Parcel|Map|Tax)[\s#ID:\-]*([0-9][0-9\- ]{5,20})",
        text,
        re.IGNORECASE,
    )

    address = addr_match.group(1).strip() if addr_match else None
    sale_date = f"{sale_match.group(1)} {sale_match.group(2)}" if sale_match else None

    if not address and not sale_date:
        return None

    principal = None
    if principal_match:
        try:
            principal = float(principal_match.group(1).replace(",", ""))
        except ValueError:
            pass

    return {
        "address": address,
        "owner": owner_match.group(1).strip() if owner_match else None,
        "sale_date": sale_date,
        "original_principal": principal,
        "parcel_id": parcel_match.group(1).strip() if parcel_match else None,
        "raw_hash": hashlib.sha256(text[:3000].encode("utf-8", errors="ignore")).hexdigest()[:16],
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "source_url": source_url,
    }


def lookup_assessment(address: str = None, parcel_id: str = None) -> dict:
    """PLACEHOLDER – implement Fulton County tax lookup later."""
    print(f"WARNING: lookup_assessment is a placeholder for {address or parcel_id}")
    return {"assessed_value": None, "market_value": None, "zip": None}


def is_high_equity_candidate(parsed: dict, assessment: dict) -> bool:
    zip_code = assessment.get("zip")
    if not zip_code or zip_code not in HIGH_GROWTH_ZIPS:
        return False
    assessed = assessment.get("assessed_value") or 0
    if assessed < MIN_ASSESSED_FOR_FLAG:
        return False
    principal = parsed.get("original_principal")
    if principal and principal > 0 and assessed / principal >= EQUITY_RATIO_THRESHOLD:
        return True
    return assessed >= MIN_ASSESSED_FOR_FLAG


def already_seen(raw_hash: str) -> bool:
    """Simple check – can be improved later."""
    return False


def create_notion_page(row: dict, flag: bool):
    if not NOTION_TOKEN:
        print("No NOTION_TOKEN – skipping Notion write")
        return

    properties = {
        "Address": {"title": [{"text": {"content": row.get("address") or "Unknown"}}]},
        "Owner": {"rich_text": [{"text": {"content": row.get("owner") or ""}}]},
        "Sale Date": {"rich_text": [{"text": {"content": row.get("sale_date") or ""}}]},
        "Parcel ID": {"rich_text": [{"text": {"content": row.get("parcel_id") or ""}}]},
        "ZIP": {"rich_text": [{"text": {"content": row.get("zip") or ""}}]},
        "Hash": {"rich_text": [{"text": {"content": row.get("raw_hash") or ""}}]},
        "Scraped At": {"rich_text": [{"text": {"content": row.get("scraped_at") or ""}}]},
        "High Equity Flag": {"checkbox": flag},
    }

    if row.get("original_principal") is not None:
        properties["Original Principal"] = {"number": row["original_principal"]}
    if row.get("assessed_value") is not None:
        properties["Assessed Value"] = {"number": row["assessed_value"]}
    if row.get("source_url"):
        properties["Source URL"] = {"url": row["source_url"]}

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=NOTION_HEADERS,
        json=payload,
        timeout=15,
    )
    if resp.status_code >= 400:
        print(f"Notion error: {resp.status_code} – {resp.text}")
    else:
        print(f"Added to Notion: {row.get('address')}")


def send_slack_alert(row: dict):
    if not SLACK_WEBHOOK:
        return
    text = (
        f"*High-equity foreclosure candidate*\n"
        f"• Address: {row.get('address')}\n"
        f"• Sale: {row.get('sale_date')}\n"
        f"• Assessed: ${row.get('assessed_value') or 0:,.0f}\n"
        f"• ZIP: {row.get('zip')}\n"
        f"• Owner: {row.get('owner')}"
    )
    try:
        requests.post(SLACK_WEBHOOK, json={"text": text}, timeout=10)
    except Exception as e:
        print(f"Slack failed: {e}")


def main():
    print(f"Starting monitor at {datetime.utcnow().isoformat()}Z")
    notices = fetch_recent_notices()
    print(f"Fetched {len(notices)} notices")

    new_count = flagged_count = 0
    for n in notices:
        parsed = parse_notice(n.get("raw_text", ""), n.get("source_url", ""))
        if not parsed or already_seen(parsed["raw_hash"]):
            continue

        assessment = lookup_assessment(parsed.get("address"), parsed.get("parcel_id"))
        parsed.update(assessment)
        flag = is_high_equity_candidate(parsed, assessment)

        create_notion_page(parsed, flag)
        new_count += 1

        if flag:
            flagged_count += 1
            send_slack_alert(parsed)

    print(f"Done. New: {new_count}, Flagged: {flagged_count}")


if __name__ == "__main__":
    main()
