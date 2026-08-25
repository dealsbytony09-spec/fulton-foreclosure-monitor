# Fulton County Foreclosure Auction Monitor

Automated weekly monitor for Fulton County, GA foreclosure notices published in the Fulton Neighbor Newspapers / Georgia Public Notice.

## What it does
1. Scrapes recent foreclosure (Notice of Sale Under Power) notices
2. Extracts property address, owner/grantor, auction date, original principal (when available)
3. Looks up recent tax assessment values
4. Flags high-equity candidates in your target high-growth ZIP codes
5. Saves everything to a Google Sheet
6. Sends a Slack (or email) alert when a new match is found

## Quick Start

### 1. Secrets (GitHub Actions)
Go to **Settings → Secrets and variables → Actions** and add:
- `GOOGLE_SHEET_ID` – the ID from your Google Sheet URL
- `GOOGLE_SA_JSON` – the full JSON content of a Google service-account key that has edit access to the Sheet
- `SLACK_WEBHOOK` – (optional) Slack incoming webhook URL

### 2. Google Sheet
Create a new Google Sheet with these column headers in row 1:

```
Address | Owner | Sale Date | Original Principal | Parcel ID | Assessed Value | ZIP | High Equity Flag | Hash | Scraped At | Source URL
```

Share the sheet with the service-account email (Editor permission).

### 3. Customize
Edit `config.py`:
- `HIGH_GROWTH_ZIPS` – your list of target ZIP codes
- `MIN_ASSESSED_FOR_FLAG` – minimum assessed value to consider
- `EQUITY_RATIO_THRESHOLD` – assessed / original principal ratio

### 4. Run locally (optional)
```bash
pip install -r requirements.txt
python monitor.py
```

### 5. Automatic schedule
The included GitHub Action runs every Wednesday at 18:00 UTC (adjust in `.github/workflows/weekly.yml`).

## Important Notes
- Notices are public legal records.
- The parser uses regex on semi-structured legal text and will need occasional tuning.
- Tax assessment lookup is a placeholder – you must implement the actual Fulton County parcel search (or use a paid data provider).
- Equity is estimated only (original principal is often listed; current balance is not).

## License
MIT – use at your own risk. This is not legal, financial, or investment advice.
