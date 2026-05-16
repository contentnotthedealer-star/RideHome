#!/usr/bin/env python3
"""
Tech Brew Ride Home — Longreads Scraper
Fetches the latest episode from the RSS feed, extracts the Longreads section,
and appends the results to a Google Sheet.
"""

import os
import re
import json
import datetime
import feedparser
from html import unescape
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ── Configuration ────────────────────────────────────────────────────────────

RSS_FEED_URL = "https://feeds.megaphone.fm/ridehome"

# Set this to your Google Sheet ID (the long string in the sheet URL)
# e.g. https://docs.google.com/spreadsheets/d/THIS_PART/edit
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]

# The tab/sheet name to write to
SHEET_NAME = "Longreads"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# ── Google Sheets client ─────────────────────────────────────────────────────

def get_sheets_client():
    """Build an authenticated Google Sheets client from the service account JSON."""
    creds_json = os.environ["GOOGLE_CREDENTIALS"]
    creds_info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    return service.spreadsheets()


# ── RSS parsing ───────────────────────────────────────────────────────────────

def fetch_latest_episode():
    """Return the most recent entry from the RSS feed."""
    feed = feedparser.parse(RSS_FEED_URL)
    if not feed.entries:
        raise RuntimeError("RSS feed returned no entries.")
    return feed.entries[0]


def extract_longreads(episode):
    """
    Parse the episode description HTML and extract the Longreads articles.

    Returns a list of dicts: {title, source, url}
    """
    # feedparser gives us the raw HTML in .summary or .content
    raw = episode.get("summary", "") or ""

    # Unescape HTML entities
    text = unescape(raw)

    # Strip all HTML tags to get plain text
    plain = re.sub(r"<[^>]+>", "", text)

    # Find the Longreads block — everything after "Longreads" up to
    # "Learn more" footer or end of string
    match = re.search(
        r"Longreads\s*\n(.*?)(?=Learn more about your ad|$)",
        plain,
        re.DOTALL | re.IGNORECASE,
    )

    if not match:
        print("⚠️  No Longreads section found in this episode.")
        return []

    block = match.group(1).strip()

    # Each longread is a bullet line like:
    # ⁠Article title here⁠ (Source Name)
    # or plain lines without bullets
    articles = []
    for line in block.splitlines():
        line = line.strip().lstrip("•·⁠​-– ").strip()
        if not line:
            continue

        # Try to split "Title (Source)"
        source_match = re.match(r"^(.+?)\s+\(([^)]+)\)\s*$", line)
        if source_match:
            title = source_match.group(1).strip()
            source = source_match.group(2).strip()
        else:
            title = line
            source = ""

        if title:
            articles.append({"title": title, "source": source})

    return articles


# ── Google Sheets writer ──────────────────────────────────────────────────────

def ensure_header(sheets, spreadsheet_id, sheet_name):
    """Add header row if the sheet is empty."""
    result = (
        sheets.values()
        .get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A1:E1")
        .execute()
    )
    if not result.get("values"):
        header = [["Date", "Episode Title", "Article Title", "Source", "Episode URL"]]
        sheets.values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": header},
        ).execute()
        print("✅ Header row written.")


def append_rows(sheets, spreadsheet_id, sheet_name, rows):
    """Append rows to the sheet."""
    sheets.values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("📡 Fetching RSS feed...")
    episode = fetch_latest_episode()

    episode_title = episode.get("title", "Unknown Episode")
    episode_url = episode.get("link", "")
    pub_date = episode.get("published", "")

    # Normalise date to YYYY-MM-DD
    try:
        parsed_date = datetime.datetime(*episode.published_parsed[:6])
        date_str = parsed_date.strftime("%Y-%m-%d")
    except Exception:
        date_str = datetime.date.today().isoformat()

    print(f"📰 Episode: {episode_title} ({date_str})")

    articles = extract_longreads(episode)

    if not articles:
        print("Nothing to write — exiting.")
        return

    print(f"✅ Found {len(articles)} longread(s):")
    for a in articles:
        print(f"   • {a['title']} ({a['source']})")

    # Build rows: [Date, Episode Title, Article Title, Source, Episode URL]
    rows = [
        [date_str, episode_title, a["title"], a["source"], episode_url]
        for a in articles
    ]

    print("📊 Writing to Google Sheets...")
    sheets = get_sheets_client()
    ensure_header(sheets, SPREADSHEET_ID, SHEET_NAME)
    append_rows(sheets, SPREADSHEET_ID, SHEET_NAME, rows)

    print(f"✅ Done — {len(rows)} row(s) appended to '{SHEET_NAME}'.")


if __name__ == "__main__":
    main()
