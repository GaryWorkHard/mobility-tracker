import csv
import os
from datetime import datetime, timezone

from .parsers import COLUMNS

LOG_COLUMNS = ["run_id", "run_at_utc", "carrier", "segment", "url", "fetch", "status", "plans_parsed", "plans_written", "issues"]


def _read(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def previous_prices(current_path):
    return {(r["carrier"], r["segment"], r["plan_name"]): {"price": _num(r["price_cad"]), "source_id": r.get("source_id", "")}
            for r in _read(current_path) if _num(r["price_cad"]) is not None}


def append_csv(path, rows, columns):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def write_current(path, fresh_rows, refreshed_sources):
    """Replace rows for sources that refreshed this run; keep last good rows for the rest."""
    refreshed = {f"{s['carrier']}|{s['segment']}|{s['url']}" for s in refreshed_sources}
    keep = [r for r in _read(path) if r.get("source_id", "") not in refreshed]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(keep + fresh_rows)


def push_to_sheets(sheet_id, sa_json_path, history_rows, current_rows, log_rows):
    """Appends to 'history' and 'run_log' tabs and rewrites 'current'. Needs a Google service account
    with edit access to the sheet (share the sheet with the service account's email)."""
    import gspread
    gc = gspread.service_account(filename=sa_json_path)
    sh = gc.open_by_key(sheet_id)

    def tab(name, cols):
        try:
            ws = sh.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(name, rows=1000, cols=len(cols))
            ws.append_row(cols)
        return ws

    tab("history", COLUMNS).append_rows([[r.get(c, "") for c in COLUMNS] for r in history_rows], value_input_option="RAW")
    cur = tab("current", COLUMNS)
    cur.clear()
    cur.append_rows([COLUMNS] + [[r.get(c, "") for c in COLUMNS] for r in current_rows], value_input_option="RAW")
    tab("run_log", LOG_COLUMNS).append_rows([[r.get(c, "") for c in LOG_COLUMNS] for r in log_rows], value_input_option="RAW")


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
