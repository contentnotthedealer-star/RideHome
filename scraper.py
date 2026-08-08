#!/usr/bin/env python3
"""
Tech Brew Ride Home — Longreads Scraper
Fetches the latest episode from the RSS feed, extracts the Longreads section,
and appends the results to a Google Sheet (skipping duplicates).
"""

import os
import re
import json
import datetime
from urllib.parse import quote
from html import unescape
from html.parser import HTMLParser

import feedparser
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ── Configuration ────────────────────────────────────────────────────────────

RSS_FEED_URL = "https://feeds.megaphone.fm/ridehome"
APPLE_PODCAST_ID = "1355212895"  # Tech Brew Ride Home Apple Podcasts ID

SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
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


class LinkExtractor(HTMLParser):
    """Collects (link_text, href) pairs from HTML content."""

    def __init__(self):
        super().__init__()
        self.links = []
        self._current_href = None
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            self._current_href = attrs_dict.get("href", "")
            self._current_text = []

    def handle_endtag(self, tag):
        if tag == "a" and self._current_href is not None:
            link_text = "".join(self._current_text).strip()
            self.links.append((link_text, self._current_href))
            self._current_href = None
            self._current_text = []

    def handle_data(self, data):
        if self._current_href is not None:
            self._current_text.append(data)


def extract_longreads(episode):
    """
    Parse the episode description HTML and extract the Longreads articles.

    Returns a list of dicts: {title, source, url}
    """
    raw = episode.get("summary", "") or ""
    text = unescape(raw)

    # Extract any hyperlinks present in the HTML (usually none for this feed,
    # but kept in case the feed adds them in the future).
    extractor = LinkExtractor()
    extractor.feed(text)
    link_map = {link_text: href for link_text, href in extractor.links if link_text}
    print(f"Found {len(link_map)} links in episode HTML")

    # Strip HTML tags to get plain text
    plain = re.sub(r"<[^>]+>", "", text)

    match = re.search(
        r"Longreads\s*\n(.*?)(?=Learn more about your ad|$)",
        plain,
        re.DOTALL | re.IGNORECASE,
    )

    if not match:
        print("No Longreads section found in this episode.")
        return []

    block = match.group(1).strip()

    articles = []
    for line in block.splitlines():
        line = line.strip().lstrip("•·⁠​-– ").strip()
        if not line:
            continue

        source_match = re.match(r"^(.+?)\s+\(([^)]+)\)\s*$", line)
        if source_match:
            title = source_match.group(1).strip()
            source = source_match.group(2).strip()
        else:
            title = line
            source = ""

        clean_title = title.strip("⁠​").strip()

        # Prefer a real hyperlink from the feed if one exists; otherwise
        # fall back to a Google search link for the article.
        url = ""
        for link_text, href in link_map.items():
            if clean_title in link_text or link_text in clean_title:
                url = href
                break
        if not url:
            url = f"https://www.google.com/search?q={quote(clean_title + ' ' + source)}"

        if title:
            articles.append({"title": title, "source": source, "url": url})

    return articles


# ── Google Sheets writer ──────────────────────────────────────────────────────

def ensure_header(sheets, spreadsheet_id, sheet_name):
    """Add header row if the sheet is empty."""
    result = (
        sheets.values()
        .get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A1:F1")
        .execute()
    )
    if not result.get("values"):
        header = [["Date", "Episode Title", "Article Title", "Source", "Article URL", "Episode URL"]]
        sheets.values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": header},
        ).execute()
        print("Header row written.")


def get_existing_keys(sheets, spreadsheet_id, sheet_name):
    """Return a set of (date, article_title) tuples already in the sheet."""
    result = (
        sheets.values()
        .get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A:C")
        .execute()
    )
    rows = result.get("values", [])
    return {(row[0], row[2]) for row in rows[1:] if len(row) >= 3}


def append_rows(sheets, spreadsheet_id, sheet_name, rows):
    """Append rows to the sheet, skipping duplicates."""
    existing = get_existing_keys(sheets, spreadsheet_id, sheet_name)
    new_rows = [r for r in rows if (r[0], r[2]) not in existing]

    if not new_rows:
        print("All articles already in sheet — nothing to append.")
        return

    if len(new_rows) < len(rows):
        print(f"Skipping {len(rows) - len(new_rows)} duplicate(s).")

    sheets.values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": new_rows},
    ).execute()
    print(f"Appended {len(new_rows)} new row(s).")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Fetching RSS feed...")
    episode = fetch_latest_episode()

    episode_title = episode.get("title", "Unknown Episode")

    # This feed has no link field — construct the Apple Podcasts URL from the GUID
    guid = episode.get("id", "") or episode.get("guid", "")
    episode_url = (
        f"https://podcasts.apple.com/us/podcast/tech-brew-ride-home/id{APPLE_PODCAST_ID}?i={guid}"
        if guid
        else ""
    )

    try:
        parsed_date = datetime.datetime(*episode.published_parsed[:6])
        date_str = parsed_date.strftime("%Y-%m-%d")
    except Exception:
        date_str = datetime.date.today().isoformat()

    print(f"Episode: {episode_title} ({date_str})")

    articles = extract_longreads(episode)

    if not articles:
        print("Nothing to write — exiting.")
        return

    print(f"Found {len(articles)} longread(s):")
    for a in articles:
        print(f"   - {a['title']} ({a['source']})")

    rows = [
        [date_str, episode_title, a["title"], a["source"], a["url"], episode_url]
        for a in articles
    ]

    print("Writing to Google Sheets...")
    sheets = get_sheets_client()
    ensure_header(sheets, SPREADSHEET_ID, SHEET_NAME)
    append_rows(sheets, SPREADSHEET_ID, SHEET_NAME, rows)

    # Write a timestamp file so the workflow can commit it — keeps the repo
    # "active" so GitHub doesn't auto-disable the scheduled workflow after
    # 60 days of no activity.
    with open("last_run.txt", "w") as f:
        f.write(f"Last successful run: {datetime.datetime.now().isoformat()}\n")

    print("Done.")


if __name__ == "__main__":
    main()
