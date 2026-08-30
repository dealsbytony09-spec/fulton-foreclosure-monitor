#!/usr/bin/env python3
"""
Fulton County Foreclosure Monitor
Writes results to Notion + optional Slack alerts
"""

import os
import re
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
    Reads notices from two places:
    1. Automatic website attempt (still limited)
    2. notices.txt file (this is how you feed real notices)
    """
    print("Fetching recent Fulton foreclosure notices...")
    notices = []

    # --- 1. Try the website (still limited) ---
    search_url = "https://www.georgiapublicnotice.com/Search.aspx"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        session = requests.Session()
        resp = session.get(search_url, headers=headers, timeout=20)
        resp.raise_for_status()
        print(f"Website reachable (status {resp.status_code})")
        print("NOTE: Automatic website extraction is still limited.")
    except Exception as e:
        print(f"Website error: {e}")

    # --- 2. Read from notices.txt (practical way) ---
    try:
        with open("notices.txt", "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()

        if content:
            raw_notices = [n.strip() for n in content.split("---") if n.strip()]
            for raw in raw_notices:
                notices.append({
                    "raw_text": raw,
                    "source_url": "manual/notices.txt"
                })
            print(f"Loaded {len(raw_notices)} notice(s) from notices.txt")
        else:
            print("notices.txt is empty – no manual notices to process")
    except FileNotFoundError:
        print("notices.txt not found")
    except Exception as e:
        print(f"Error reading notices.txt: {e}")

    print(f"Total notices ready to process: {len(notices)}")
    return notices


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

    new_count = flagged_count = skipped_count = 0
    today = datetime.utcnow().date()

    for n in notices:
        parsed = parse_notice(n.get("raw_text", ""), n.get("source_url", ""))
        if not parsed or already_seen(parsed["raw_hash"]):
            continue

        # --- 4-day filter ---
        sale_date_str = parsed.get("sale_date")
        if sale_date_str:
            try:
                # Simple parsing for formats like "October 2026" or "October 6, 2026"
                months = {
                    "january": 1, "february": 2, "march": 3, "april": 4,
                    "may": 5, "june": 6, "july": 7, "august": 8,
                    "september": 9, "october": 10, "november": 11, "december": 12
                }
                parts = sale_date_str.lower().replace(",", "").split()
                month = months.get(parts[0])
                year = int(parts[-1]) if parts[-1].isdigit() else None
                day = 1
                if len(parts) >= 2 and parts[1].isdigit():
                    day = int(parts[1])

                if month and year:
                    sale_dt = datetime(year, month, day).date()
                    days_until = (sale_dt - today).days
                    if days_until < 4:
                        print(f"Skipping (less than 4 days away): {parsed.get('address')} – {sale_date_str}")
                        skipped_count += 1
                        continue
            except Exception as e:
                print(f"Could not parse sale date '{sale_date_str}': {e}")

        assessment = lookup_assessment(parsed.get("address"), parsed.get("parcel_id"))
        parsed.update(assessment)
        flag = is_high_equity_candidate(parsed, assessment)

        create_notion_page(parsed, flag)
        new_count += 1

        if flag:
            flagged_count += 1
            send_slack_alert(parsed)

    print(f"Done. New: {new_count}, Flagged: {flagged_count}, Skipped (<4 days): {skipped_count}")
