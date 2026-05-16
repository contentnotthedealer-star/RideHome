# Tech Brew Ride Home — Longreads Scraper

Automatically scrapes the **Longreads** section from the weekly Tech Brew Ride Home podcast episode and appends the articles to a Google Sheet. Runs every Friday afternoon via GitHub Actions.

---

## What it does

Every Friday at 6pm UTC, the workflow:
1. Fetches the RSS feed at `https://feeds.megaphone.fm/ridehome`
2. Grabs the latest episode description
3. Extracts the **Longreads** section
4. Appends each article as a row to your Google Sheet with columns:
   `Date | Episode Title | Article Title | Source | Episode URL`

---

## One-time setup

### 1. Create a Google Sheet

- Create a new Google Sheet at [sheets.google.com](https://sheets.google.com)
- Copy the **Spreadsheet ID** from the URL:
  `https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID_HERE/edit`

### 2. Set up a Google Cloud Service Account

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Enable the **Google Sheets API**:
   - Navigate to **APIs & Services → Library**
   - Search for "Google Sheets API" and click **Enable**
4. Create a Service Account:
   - Navigate to **APIs & Services → Credentials**
   - Click **Create Credentials → Service Account**
   - Give it any name (e.g. `longreads-scraper`)
   - Skip optional role/user steps and click **Done**
5. Generate a JSON key:
   - Click your new service account in the list
   - Go to the **Keys** tab → **Add Key → Create new key → JSON**
   - Download the JSON file — keep it safe, you'll need its contents shortly

### 3. Share your Google Sheet with the service account

- Open the downloaded JSON file and copy the `client_email` value
  (it looks like `longreads-scraper@your-project.iam.gserviceaccount.com`)
- Open your Google Sheet → click **Share**
- Paste the service account email and give it **Editor** access

### 4. Create a GitHub repository

- Create a new repo at [github.com](https://github.com) (can be private)
- Push this project's files into it:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 5. Add GitHub Actions secrets

In your GitHub repo, go to **Settings → Secrets and variables → Actions → New repository secret** and add two secrets:

| Secret name          | Value                                                      |
|----------------------|------------------------------------------------------------|
| `GOOGLE_CREDENTIALS` | The entire contents of the service account JSON key file   |
| `SPREADSHEET_ID`     | Your Google Sheet ID (the string from the URL in step 1)   |

---

## Testing it manually

Once set up, you can trigger the workflow immediately without waiting for Friday:

1. Go to your repo on GitHub
2. Click the **Actions** tab
3. Click **Scrape Longreads** in the left sidebar
4. Click **Run workflow → Run workflow**

Check the run logs to confirm it worked, then look at your Google Sheet.

---

## Adjusting the schedule

The cron expression in `.github/workflows/longreads.yml` is:

```
0 18 * * 5   →   Every Friday at 6:00 PM UTC
```

Convert to your timezone:
- **Eastern**: `0 21 * * 5` = 5pm ET (UTC-4 in summer)
- **Pacific**: `0 0 * * 6` = 5pm PT (UTC-7 in summer, rolls to Saturday UTC)
- Use [crontab.guru](https://crontab.guru) to experiment

---

## File structure

```
.
├── .github/
│   └── workflows/
│       └── longreads.yml   # GitHub Actions schedule
├── scraper.py              # Main script
├── requirements.txt        # Python dependencies
└── README.md
```
