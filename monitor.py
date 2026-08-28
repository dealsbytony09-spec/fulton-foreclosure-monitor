def fetch_recent_notices() -> list[dict]:
    """
    Improved first real attempt at pulling Fulton foreclosure notices.
    Georgia Public Notice is an ASP.NET site (uses ViewState), so full
    automatic searching is fragile. This version reaches the site cleanly
    and is structured so we can add the form submission next.
    """
    print("Fetching recent Fulton foreclosure notices...")
    notices = []

    search_url = "https://www.georgiapublicnotice.com/Search.aspx"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        session = requests.Session()
        resp = session.get(search_url, headers=headers, timeout=25)
        resp.raise_for_status()
        print(f"Successfully connected to Georgia Public Notice (status {resp.status_code})")

        # The site requires a form POST with __VIEWSTATE and other hidden fields
        # to actually run a search. We will add that in the next update.
        # For now we confirm connectivity and return an empty list.
        print("Site is reachable. Form-based search (with ViewState) comes next.")

    except requests.exceptions.RequestException as e:
        print(f"Network/scraper error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    print(f"Returning {len(notices)} notices this run")
    return notices
