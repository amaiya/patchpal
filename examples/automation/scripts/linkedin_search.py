#!/usr/bin/env python
"""
LinkedIn Search Script for PatchPal

THIS SCRIPT IS A TEMPLATE - You need to intercept LinkedIn's API yourself!

This uses LinkedIn's internal API (not Selenium/Puppeteer).
Much faster, more reliable, and what the ClaudeClaw OP used successfully.

IMPORTANT: This script will NOT work out of the box.
You must follow the setup instructions below to intercept the API.

Setup (15 minutes):
==================

Step 1: Intercept the LinkedIn Search API
------------------------------------------
1. Log into LinkedIn in your browser
2. Open DevTools (F12 or Right-click → Inspect)
3. Go to Network tab
4. Perform a search (e.g., search for "AI startup founder")
5. Look for requests to /voyager/api/search/ in the Network tab
6. Click on the request, go to "Headers" tab
7. Copy:
   - Request URL (the endpoint)
   - Cookie header (your session)
   - csrf-token header
   - User-Agent header

Step 2: Store Credentials Securely
-----------------------------------
Create a file: ~/.patchpal/linkedin_config.json

{
  "endpoint": "https://www.linkedin.com/voyager/api/search/blended",
  "cookies": "your-cookie-string-here",
  "csrf_token": "your-csrf-token-here",
  "user_agent": "Mozilla/5.0..."
}

Make it read-only:
chmod 600 ~/.patchpal/linkedin_config.json

Step 3: Test the Script
------------------------
python ~/.patchpal/scripts/linkedin_search.py "test query"

If you see JSON output with results, it's working!

IMPORTANT NOTES:
================
- Use a SIDE ACCOUNT, not your main LinkedIn
- Cookies expire after a few weeks (you'll need to refresh)
- LinkedIn's API can change (rarely, but possible)
- This is for personal use only
- Rate limits: Don't spam requests

Why This Approach?
==================
From the ClaudeClaw Reddit thread:

"I'm using the direct search endpoint i intercepted from the browser's
network tab, throwing in a side account's cookies into an env and a
simple json caching system so it never duplicates posts"

This is:
- ✅ 10x faster than Selenium
- ✅ More reliable (no DOM changes)
- ✅ Lower resource usage
- ✅ What works in production
"""

import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print(
        json.dumps(
            {"error": "requests not installed", "message": "Install with: pip install requests"}
        )
    )
    sys.exit(1)

try:
    from patchpal.claw.cache import add_to_set, is_duplicate
except ImportError:
    print(
        json.dumps(
            {
                "error": "patchpal[claw] not installed",
                "message": "Install with: pip install patchpal[claw]",
            }
        )
    )
    sys.exit(1)


CONFIG_FILE = Path.home() / ".patchpal" / "linkedin_config.json"


def load_config():
    """Load LinkedIn API configuration."""
    if not CONFIG_FILE.exists():
        return {
            "error": "LinkedIn not configured",
            "message": f"Create config file: {CONFIG_FILE}",
            "setup": "See script header for detailed setup instructions",
        }

    try:
        config = json.loads(CONFIG_FILE.read_text())

        required = ["endpoint", "cookies", "csrf_token", "user_agent"]
        missing = [k for k in required if k not in config]

        if missing:
            return {
                "error": "Incomplete configuration",
                "missing": missing,
                "file": str(CONFIG_FILE),
            }

        return config

    except json.JSONDecodeError:
        return {"error": "Invalid JSON in config file", "file": str(CONFIG_FILE)}


def search_linkedin(query, limit=20):
    """
    Search LinkedIn using intercepted API.

    Args:
        query: Search query
        limit: Max results to return

    Returns:
        List of new profiles/posts (deduplicated)
    """
    config = load_config()

    if "error" in config:
        return config

    try:
        # Make API request with intercepted credentials
        response = requests.get(
            config["endpoint"],
            headers={
                "Cookie": config["cookies"],
                "csrf-token": config["csrf_token"],
                "User-Agent": config["user_agent"],
                "Accept": "application/vnd.linkedin.normalized+json+2.1",
            },
            params={
                "keywords": query,
                "origin": "GLOBAL_SEARCH_HEADER",
                "start": 0,
                "count": limit,
            },
            timeout=10,
        )

        response.raise_for_status()
        data = response.json()

        # Parse results (structure depends on LinkedIn's response)
        # You may need to adjust this based on the actual response
        results = []

        # Example parsing (adjust based on actual API response):
        elements = data.get("data", {}).get("elements", [])

        for element in elements:
            # Extract profile/post data
            item_id = element.get("entityUrn", "").split(":")[-1]

            if not item_id or is_duplicate("linkedin_seen", item_id):
                continue

            # Extract relevant fields (adjust based on actual structure)
            item = {
                "id": item_id,
                "type": element.get("type"),
                "title": element.get("title", {}).get("text", ""),
                "subtitle": element.get("primarySubtitle", {}).get("text", ""),
                "url": f"https://www.linkedin.com/in/{item_id}",  # Adjust as needed
                "query": query,
                "raw": element,  # Include raw data for Claude to analyze
            }

            results.append(item)
            add_to_set("linkedin_seen", item_id)

        return results

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return {
                "error": "Authentication failed",
                "message": "Cookies expired. Re-intercept from browser.",
                "status_code": 401,
            }
        return {"error": "HTTP error", "message": str(e), "status_code": e.response.status_code}

    except Exception as e:
        return {"error": "Request failed", "message": str(e)}


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: linkedin_search.py <query1> [query2]")
        print("Example: linkedin_search.py 'AI startup founder'")
        print("\nSetup required! See script header for instructions.")
        sys.exit(1)

    queries = sys.argv[1:]
    all_results = []

    for query in queries:
        results = search_linkedin(query)

        if isinstance(results, dict) and "error" in results:
            print(json.dumps(results, indent=2))
            sys.exit(1)

        all_results.extend(results)

    # Format output
    result = {
        "found": len(all_results),
        "queries": queries,
        "timestamp": datetime.now().isoformat(),
        "results": all_results,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
