#!/usr/bin/env python3
"""
Fulton County Foreclosure Monitor
Scrapes notices → parses → assesses equity → writes Google Sheet → alerts
"""

import os
import re
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
from dateutil import parser as date_parser

from config import (
    HIGH_GROWTH_ZIPS,
    MIN_ASSESSED_FOR_FLAG,
    EQUITY_RATIO_THRESHOLD,
    LOOKBACK_DAYS,
)

# ---------- Secrets (from env / GitHub Actions) ----------
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
GOOGLE_SA_JSON = os.environ.get("GOOGLE_SA_JSON", "{}")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK", "")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_sheet():
    """Authorize and return the first worksheet."""
    if not GOOGLE_SHEET_ID or GOOGLE_SA_JSON in ("", "{}"):
        raise RuntimeError("GOOGLE_SHEET_ID and GOOGLE_SA_JSON secrets are required")
    creds_info = json.loads(GOOGLE_SA_JSON)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(GOOGLE_SHEET_ID).sheet1


def fetch_recent_notices() -> list[dict]:
    """
    Fetch recent foreclosure notices.

    CURRENT IMPLEMENTATION IS A PLACEHOLDER.
    Replace this function with a real scraper for:
      - https://www.georgiapublicnotice.com/  (recommended – searchable)
      - or the weekly Fulton Neighbor e-edition PDFs

    Expected return format:
    [
      {
        "raw_text": "full notice text...",
        "source_url": "https://...",
        "pub_date": "2026-08-20",
      },
      ...
    ]
    """
    print("WARNING: Using placeholder fetch_recent_notices(). Implement real scraper.")
    # Example stub – delete when real scraper is ready
    return []


def parse_notice(text: str, source_url: str = "") -> Optional[dict]:
    """Extract key fields from a single legal notice using regex."""
    if not text:
        return None

    # Sale date – "first Tuesday in/of Month Year"
    sale_match = re.search(
        r"first Tuesday (?:in|of)\s+(\w+),?\s+(\d{4})",
        text,
        re.IGNORECASE,
    )

    # Commonly known as / property located at
    addr_match = re.search(
        r"(?:commonly known as|property (?:located )?at|known as)[:\s]+"
        r"([^\n]+?(?:GA|Georgia)?\s*\d{5}(?:-\d{4})?)",
        text,
        re.IGNORECASE,
    )

    # Grantor / borrower name
    owner_match = re.search(
        r"(?:executed by|Security Deed from|Grantor[:\s]+)"
        r"([A-Z][A-Za-z0-9\s,&\.\-']+?)(?:\s+to|\s+dated|,\s+hereinafter)",
        text,
    )

    # Original principal amount
    principal_match = re.search(
        r"original principal amount of[^\d$]*\$?([\d,]+\.?\d*)",
        text,
        re.IGNORECASE,
    )

    # Parcel / map / tax ID
    parcel_match = re.search(
        r"(?:Parcel|Map|Tax)[\s#ID:\-]*([0-9][0-9\- ]{5,20})",
        text,
        re.IGNORECASE,
    )

    address = addr_match.group(1).strip() if addr_match else None
    sale_date = None
    if sale_match:
        sale_date = f"{sale_match.group(1)} {sale_match.group(2)}"

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
    """
    Look up Fulton County tax assessment.

    PLACEHOLDER – you must implement this against the official
    Fulton County property search / qPublic / GIS endpoint.

    Return example:
    {
        "assessed_value": 385000.0,
        "market_value": 410000.0,
        "zip": "30318",
    }
    """
    print(f"WARNING: lookup_assessment is a placeholder for {address or parcel_id}")
    return {
        "assessed_value": None,
        "market_value": None,
        "zip": None,
    }


def is_high_equity_candidate(parsed: dict, assessment: dict) -> bool:
    """Apply your business rules."""
    zip_code = assessment.get("zip")
    if not zip_code or zip_code not in HIGH_GROWTH_ZIPS:
        return False

    assessed = assessment.get("assessed_value") or 0
    if assessed < MIN_ASSESSED_FOR_FLAG:
        return False

    principal = parsed.get("original_principal")
    if principal and principal > 0:
        ratio = assessed / principal
        if ratio >= EQUITY_RATIO_THRESHOLD:
            return True

    # Fallback: high assessed value in a target ZIP is enough for a first-pass alert
    return assessed >= MIN_ASSESSED_FOR_FLAG


def already_seen(sheet, raw_hash: str) -> bool:
    """Simple de-duplication by content hash."""
    try:
        records = sheet.get_all_records()
        return any(str(r.get("Hash", "")) == raw_hash for r in records)
    except Exception:
        return False


def send_slack_alert(row: dict):
    if not SLACK_WEBHOOK:
        return
    text = (
        f"*High-equity foreclosure candidate*\n"
        f"• Address: {row.get('address')}\n"
        f"• Sale: {row.get('sale_date')}\n"
        f"• Assessed: ${row.get('assessed_value') or 0:,.0f}\n"
        f"• ZIP: {row.get('zip')}\n"
        f"• Owner: {row.get('owner')}\n"
        f"• Source: {row.get('source_url')}"
    )
    try:
        requests.post(SLACK_WEBHOOK, json={"text": text}, timeout=10)
    except Exception as e:
        print(f"Slack alert failed: {e}")


def append_row(sheet, row: dict, flag: bool):
    sheet.append_row([
        row.get("address"),
        row.get("owner"),
        row.get("sale_date"),
        row.get("original_principal"),
        row.get("parcel_id"),
        row.get("assessed_value"),
        row.get("zip"),
        flag,
        row.get("raw_hash"),
        row.get("scraped_at"),
        row.get("source_url"),
    ])


def main():
    print(f"Starting monitor run at {datetime.utcnow().isoformat()}Z")
    sheet = get_sheet()

    notices = fetch_recent_notices()
    print(f"Fetched {len(notices)} raw notices")

    new_count = 0
    flagged_count = 0

    for n in notices:
        parsed = parse_notice(n.get("raw_text", ""), n.get("source_url", ""))
        if not parsed:
            continue
        if already_seen(sheet, parsed["raw_hash"]):
            continue

        assessment = lookup_assessment(
            parsed.get("address"), parsed.get("parcel_id")
        )
        parsed.update(assessment)

        flag = is_high_equity_candidate(parsed, assessment)
        append_row(sheet, parsed, flag)
        new_count += 1

        if flag:
            flagged_count += 1
            send_slack_alert(parsed)
            print(f"FLAGGED: {parsed.get('address')}")

    print(f"Done. New rows: {new_count}, Flagged: {flagged_count}")


if __name__ == "__main__":
    main()
