import csv, os, sys, tempfile, unittest
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tracker.parsers import COLUMNS
from tracker.sinks import fix_capture_dates


class DateFix(unittest.TestCase):
    def test_utc_evening_run_gets_local_date(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "history.csv")
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=COLUMNS); w.writeheader()
                w.writerow({"capture_date": "2026-11-09", "run_id": "20261109T030908", "carrier": "A"})  # 10:09pm ET Nov 8
                w.writerow({"capture_date": "2026-11-10", "run_id": "20261110T111700", "carrier": "A"})  # 6:17am ET Nov 10
            fix_capture_dates(p, ZoneInfo("America/Toronto"))
            fix_capture_dates(p, ZoneInfo("America/Toronto"))  # repeat is harmless
            rows = list(csv.DictReader(open(p, encoding="utf-8")))
            self.assertEqual([r["capture_date"] for r in rows], ["2026-11-08", "2026-11-10"])


if __name__ == "__main__":
    unittest.main()
