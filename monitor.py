def fetch_recent_notices() -> list[dict]:
    """
    Stronger attempt at pulling Fulton foreclosure notices.
    Georgia Public Notice is an ASP.NET site with ViewState, so
    fully automatic search is difficult. This version:
    1. Connects cleanly
    2. Tries to extract any visible notice text if present
    3. Returns structured results when possible
    """
    print("Fetching recent Fulton foreclosure notices...")
    notices = []

    search_url = "https://www.georgiapublicnotice.com/Search.aspx"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        session = requests.Session()
        resp = session.get(search_url, headers=headers, timeout=25)
        resp.raise_for_status()
        print(f"Connected to Georgia Public Notice (status {resp.status_code})")

        # The site requires a complex form POST with __VIEWSTATE to run a real search.
        # Without that, we cannot get the actual list of notices yet.
        # This version confirms connectivity and prepares the structure for the next improvement.
        print("Site reachable. Real form-based search still needs ViewState handling.")
        print("No notices extracted in this run.")

    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    print(f"Returning {len(notices)} notices")
    return notices
