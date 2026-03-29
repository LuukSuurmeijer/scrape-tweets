# X Profile Scraper

As many do, I wanted to stop using Twitter. My Twitter contained a bit of my personal history. Intersting interactions I've had with people, thoughts I had 7 years ago about things that were relevant in my life at the time. I wanted to save these things. Since the twitter API is no longer publically available, I took matters into my own hands. A small Python script that logs into X (Twitter) and scrolls through a user's profile to collect their tweets. It uses Selenium to drive a Chrome browser and BeautifulSoup to parse the resulting HTML. Collected tweets are saved to a JSON file.

## What it collects

For each tweet it finds: the username, tweet text, any attached image URL, the tweet permalink, and the profile type label. Quoted tweets are captured recursively.

## Setup

You'll need Python 3.10+ and Chrome installed.

```bash
pip install selenium beautifulsoup4 requests python-dotenv
```

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

If you'd rather not use a `.env` file, the script will prompt you for the missing values at runtime.

## Usage

```bash
python main.py
```

The script logs in, navigates to the target profile, and scrolls until it hits either the `MAX_TWEETS` limit or the `STOP_AT_TWEET` text (if set). Results are written to `tweets_dump.json` by default.

## Configuration

All options can be set via `.env` or environment variables:

| Variable          | Description                        | Default            |
| ----------------- | ---------------------------------- | ------------------ |
| `LOGIN_USERNAME`  | X account to log in with           | prompted           |
| `LOGIN_PASSWORD`  | Password for the login account     | prompted           |
| `TARGET_USERNAME` | Profile to scrape                  | prompted           |
| `STOP_AT_TWEET`   | Stop when this tweet text is found | (disabled)         |
| `MAX_TWEETS`      | Maximum tweets to collect          | `2000`             |
| `OUTPUT_FILE`     | Output file path                   | `tweets_dump.json` |

## Notes

This script relies on X's internal CSS class names and `data-testid` attributes to locate elements, which means it may break if X updates their frontend. It also requires a valid X account to log in with. Scraping without authentication isn't supported.

Since the functionality depends on Selenium literally scrolling down on your profile, you may need to fiddle around with the `scroll_amount`.
