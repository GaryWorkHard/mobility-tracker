#!/usr/bin/env python3
"""Daily price tracker.  python run.py                 -> all sources, writes data/*.csv
                       python run.py --only Koodo     -> one carrier
                       python run.py --fixtures tests/fixtures --dry-run   -> parse saved text, no network
Set SHEET_ID and GOOGLE_SA_JSON (path to service-account key) to also push to Google Sheets."""
import argparse
import os
import sys
import time
from datetime import date

import yaml

from tracker.fetch import fetch_text
from tracker.parsers import COLUMNS, PARSERS
from tracker.sinks import (LOG_COLUMNS, append_csv, now_utc, previous_prices, push_to_sheets, write_current)
from tracker.validate import validate_source

HERE = os.path.dirname(os.path.abspath(__file__))


def fixture_name(src):
    return f"{src['carrier']}_{src['segment']}_{src['parser']}".lower().replace(" ", "_") + ".txt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "config", "carriers.yaml"))
    ap.add_argument("--data-dir", default=os.path.join(HERE, "data"))
    ap.add_argument("--only")
    ap.add_argument("--fixtures", help="read page text from files instead of the network")
    ap.add_argument("--dry-run", action="store_true", help="parse and validate, write nothing to history/current/sheet")
    ap.add_argument("--save-text", metavar="DIR", help="save each page's fetched text here (for debugging parsers)")
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    settings = cfg["settings"]
    os.makedirs(a.data_dir, exist_ok=True)
    current_path = os.path.join(a.data_dir, "current.csv")
    prev = previous_prices(current_path)
    run_id = time.strftime("%Y%m%dT%H%M%S")
    today = date.today().isoformat()
    fresh, refreshed, log = [], [], []

    for src in cfg["sources"]:
        if a.only and a.only.lower() not in src["carrier"].lower():
            continue
        entry = {"run_id": run_id, "run_at_utc": now_utc(), "carrier": src["carrier"], "segment": src["segment"],
                 "url": src["url"], "fetch": "fixture" if a.fixtures else src["fetch"], "plans_parsed": 0, "plans_written": 0}
        try:
            attempts = 1 if a.fixtures else 3
            for attempt in range(attempts):
                if a.fixtures:
                    with open(os.path.join(a.fixtures, fixture_name(src)), encoding="utf-8") as f:
                        text = f.read()
                else:
                    # a slow or half-rendered page is retried with a longer wait before giving up
                    tries = dict(src, wait_ms=int(src.get("wait_ms", 6000) * (1 + 0.8 * attempt)))
                    text = fetch_text(tries, settings)
                if a.save_text:
                    os.makedirs(a.save_text, exist_ok=True)
                    with open(os.path.join(a.save_text, fixture_name(src)), "w", encoding="utf-8") as f:
                        f.write(text)
                rows = PARSERS[src["parser"]](text, src)
                for r in rows:
                    r.update(capture_date=today, run_id=run_id)
                rows, issues, ok = validate_source(rows, src, settings, prev)
                if ok:
                    break
            entry.update(plans_parsed=len(rows), issues=" | ".join(issues)[:900])
            if attempt:
                entry["issues"] = (f"needed {attempt + 1} attempts | " + entry["issues"])[:900]
            if ok:
                entry.update(status="OK" if not issues else "OK with review flags", plans_written=len(rows))
                fresh += rows
                refreshed.append(src)
            else:
                entry["status"] = "FAILED - kept previous data"
        except Exception as e:  # noqa: BLE001
            entry.update(status="FAILED - kept previous data", issues=str(e)[:900])
        log.append(entry)
        print(f"{entry['carrier']:<12} {entry['segment']:<9} {entry['status']:<28} parsed={entry['plans_parsed']:<3} {entry.get('issues','')[:120]}")
        if not a.fixtures:
            time.sleep(settings["delay_between_sources_s"])

    seen, unique = set(), []
    for r in fresh:  # two pages can list the same plan (e.g. Kini home and Kini plans); keep the first
        k = (r["carrier"], r["segment"], r["plan_name"])
        if k not in seen:
            seen.add(k)
            unique.append(r)
    fresh = unique

    if not a.dry_run:
        append_csv(os.path.join(a.data_dir, "history.csv"), fresh, COLUMNS)
        write_current(current_path, fresh, refreshed)
        append_csv(os.path.join(a.data_dir, "run_log.csv"), log, LOG_COLUMNS)
        if os.environ.get("SHEET_ID", "").strip() and not os.environ["SHEET_ID"].startswith("PASTE") and os.environ.get("GOOGLE_SA_JSON"):
            import csv
            cur = list(csv.DictReader(open(current_path, encoding="utf-8")))
            push_to_sheets(os.environ["SHEET_ID"], os.environ["GOOGLE_SA_JSON"], fresh, cur, log)
            print("pushed to Google Sheets")
    return 1 if any(l["status"].startswith("FAILED") for l in log) else 0


if __name__ == "__main__":
    sys.exit(main())
