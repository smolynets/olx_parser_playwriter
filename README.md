# OLX Parser

OLX real-estate listings parser written in Python using Playwright, BeautifulSoup, and MongoDB Atlas.

## `--first-page-only` flag

Use this flag for **local testing** on Ubuntu 26.04 (or similar systems where Playwright cannot download its own Chromium browser):

```bash
poetry run python main.py --first-page-only
```

What it does:

1. **Processes only the first page** of the OLX listings (stops after page 1 instead of iterating through all pages with yesterday's date).
2. **Uses the system Chromium** at `/usr/bin/chromium-browser` instead of Playwright's bundled browser. This is required on Ubuntu 26.04 because `playwright install chromium` fails on that OS version.

Without `--first-page-only`, the script runs normally: it iterates all listing pages until yesterday's ads are exhausted, using Playwright's default browser resolution (works on GitHub Actions / Ubuntu where Playwright can install Chromium).

## Prerequisites for local testing on Ubuntu 26.04

```bash
sudo apt update
sudo apt install chromium-browser
```

Then:

```bash
poetry install --no-root
poetry run python main.py --first-page-only
```

## Comments added for local testing (all in English)

- `# commented out for local testing` — MongoDB import and instance disabled locally.
- `# stub for local testing without MongoDB` — `get_update_mongo_atlas()` returns `None` instead of writing to MongoDB Atlas.
- `# System Chromium only for local testing on Ubuntu 26.04 (flag --first-page-only)` — `executable_path` is passed to Playwright only when `--first-page-only` is set.
- `print("🧪 Test mode: processing only first page, stopping.")` — log message printed when stopping after page 1.
