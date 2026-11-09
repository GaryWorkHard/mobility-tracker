# Canada mobility price tracker

Reads public plan pages for 10 sources, checks the data, and writes it to CSV and (optionally) a Google Sheet.
Runs without a VPN or Claude session: `python run.py`.

## Setup
    pip install -r requirements.txt
    playwright install chromium        # only needed for sources marked fetch: headless
    python run.py                       # writes data/current.csv, history.csv, run_log.csv

To also write to Google Sheets: create a Google service account, download its JSON key, share your
sheet with the service account's email (Editor), then set `SHEET_ID` and `GOOGLE_SA_JSON` (path to the key).
The script appends to `history` and `run_log` tabs and rewrites `current` (tabs are created if missing).

## Scheduling
Any scheduler works: cron (`0 9 * * *  cd /path && python run.py`), GitHub Actions, or Workflow Studio calling the
same command. The exit code is 1 if any source failed, so the scheduler can alert.

## How it verifies itself
- Each page's text is parsed into plans, then checked: required fields, price range ($5-$200), regular price not
  below the price, data amounts sane, no duplicate plans, and price moves over 25% since the last good run.
- Rows that fail a check are written with status `Review`, not dropped.
- A source that returns fewer plans than `min_plans` (page changed, blocked, or empty) is marked
  `FAILED - kept previous data`. Its last good rows stay in `current.csv`, and the failure is in `run_log.csv`.
- Plans that disappear from a page are listed in the run log.

## Adding a carrier
Add an entry to `config/carriers.yaml` with carrier, segment, url and `parser: generic`. The generic parser pairs
"N GB" with a nearby price and marks every row `Review` until you write a specific parser in `tracker/parsers.py`.
Add a text fixture to `tests/fixtures/` named `<carrier>_<segment>_<parser>.txt` and a case in `tests/test_parsers.py`.

## Tests
    python -m unittest discover -s tests -v
Parsers are checked against page text saved from the live sites on 2026-11-07 (and `live_*` files saved from plain
HTTP requests). `python run.py --fixtures tests/fixtures --dry-run` runs the whole pipeline offline.

## What has and has not been verified
- Verified on 2026-11-08: a live run of all 16 source pages (plain HTTP and headless Chromium on Linux) parsed
  to the same plans captured earlier, and the unit tests (page text saved from those runs) pass.
- Not yet run: the Google Sheets write (needs a service-account key), and a run on Windows. Run
  `python run.py --dry-run` once on your machine and compare with `data/current.csv` from the live run.
- Fido: the "View more plans" click is attempted but only four plans have ever been seen; check for more.
- Kini Mobile: one fetch showed 50GB $27 / 75GB $30 / 100GB $35, later requests showed 5GB $25 / 15GB $30 /
  30GB $35. Offers may vary by visitor or time; the tracker records what each run sees.
- Prices are advertised new-activation, bring-your-own-phone prices after autopay and bundle credits; they differ by
  carrier and region (TELUS and Virgin Plus were read in British Columbia). `detail` keeps the card text.
- CTExcel's page is in Chinese; its parser reads the prepaid tab and clicks the postpaid tab.

## Faster feeds (optional, later)
TELUS and Koodo load plans from `POST /shop/api/proxyRatePlanSelectionBff/getEligibleRatePlans` (JSON). Freedom
embeds plan data in its page's Next.js payload. Either could replace headless rendering for those sources once the
request details are captured.

## Windows quick start
1. Unzip, double-click `setup.bat` once.
2. Double-click `run_daily.bat` to run it. Results are in the `data` folder.
3. Schedule `run_daily.bat` in Windows Task Scheduler (daily trigger, "Start a program").

## Running part of the list
`python run.py --only Koodo` runs every source whose carrier name contains "Koodo". Use `--save-text DIR` to keep the
page text each run saw, which is the first thing to look at when a source starts failing.

## Daily cloud run
See `SETUP-GITHUB.md` for running this on GitHub Actions with results linked into Google Sheets.
