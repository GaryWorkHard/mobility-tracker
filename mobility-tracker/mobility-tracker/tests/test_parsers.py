"""Checks each parser reproduces the plan values captured from the live sites on 2026-11-07.
Run: python -m unittest discover -s tests -v"""
import os
import sys
import unittest

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from tracker.parsers import PARSERS  # noqa: E402
from tracker.validate import validate_source  # noqa: E402

CFG = yaml.safe_load(open(os.path.join(HERE, "..", "config", "carriers.yaml"), encoding="utf-8"))
SETTINGS = CFG["settings"]


def source(carrier, segment, parser):
    return next(s for s in CFG["sources"] if s["carrier"] == carrier and s["segment"] == segment and s["parser"] == parser)


def parse(carrier, segment, parser):
    src = source(carrier, segment, parser)
    name = f"{carrier}_{segment}_{parser}".lower().replace(" ", "_") + ".txt"
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as f:
        text = f.read()
    return src, PARSERS[parser](text, src)


# (price, regular price, data GB) per plan, from the captured sheet
EXPECTED = {
    ("TELUS", "Postpaid", "telus"): [(75, 85, 100), (90, 100, None), (100, 110, None), (70, 80, 60), (60, 70, 15), (30, 40, None)],
    ("Bell", "Postpaid", "bell"): [(60, 85, 100), (75, 100, None), (85, 110, None)],
    ("Rogers", "Postpaid", "rogers"): [(60, 85, 100), (75, 100, None), (85, 115, None), (55, 80, 60)],
    ("Fido", "Postpaid", "fido"): [(45, 50, 20), (50, 55, 60), (55, 60, 60), (19, None, 0.25)],
    ("Koodo", "Postpaid", "koodo"): [(45, 55, 20), (50, 60, 60), (40, 50, 10), (55, 65, 60), (60, 70, 100), (25, 35, None),
                                      (15, None, 0.25), (35, None, 3), (37.5, None, 2)],
    ("Koodo", "Prepaid", "koodo_prepaid"): [(22, None, None), (25, None, 4), (30, None, 10), (35, None, 25), (40, None, 40)],
    ("Freedom", "Postpaid", "freedom"): [(p, None, g) for p, g in [(35, 10), (40, 70), (45, 125), (50, 175), (60, 250), (70, 250), (80, 250), (90, 250), (100, 250)]],
    ("Freedom", "Prepaid", "freedom"): [(p, None, g) for p, g in [(35, 10), (40, 70), (45, 125), (50, 175), (60, 250), (70, 250)]],
    ("Virgin Plus", "Postpaid", "virgin"): [(45, None, 20), (50, None, 60), (55, None, 60), (25, None, None), (19, None, 0.25), (39, None, 3)],
    ("Kini Mobile", "Prepaid", "kini"): [(25, None, 5), (30, None, 15), (35, None, 30)],  # direct HTTP GET text; see README note
    ("CTExcel", "Prepaid", "ctexcel"): [(22, None, 0.5), (25, None, 5), (30, None, 15), (35, None, 30), (39, None, 75)],
    ("CTExcel", "Postpaid", "ctexcel"): [(45, None, 20), (55, None, 60), (60, None, 100)],
    ("PhoneBox", "Postpaid", "phonebox"): [(35, None, 30), (40, None, 60), (45, None, 80), (50, None, 120)],
    ("PhoneBox", "Prepaid", "phonebox"): [(35, None, 25), (45, None, 75)],
}


class ParserTests(unittest.TestCase):
    def test_each_parser_matches_captured_values(self):
        for (carrier, segment, parser), want in EXPECTED.items():
            with self.subTest(carrier=carrier, segment=segment):
                _, rows = parse(carrier, segment, parser)
                got = [(r["price_cad"], r["regular_price_cad"], r["data_gb"]) for r in rows]
                self.assertEqual(got, want)

    def test_live_http_fixtures_match(self):
        """Text saved from real HTTP GETs (not browser text) must parse to the same plans."""
        for key in [("Rogers", "Postpaid", "rogers"), ("PhoneBox", "Postpaid", "phonebox"), ("PhoneBox", "Prepaid", "phonebox")]:
            carrier, segment, parser = key
            src = source(carrier, segment, parser)
            name = "live_" + f"{carrier}_{segment}_{parser}".lower().replace(" ", "_") + ".txt"
            with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as f:
                rows = PARSERS[parser](f.read(), src)
            self.assertEqual([(r["price_cad"], r["regular_price_cad"], r["data_gb"]) for r in rows], EXPECTED[key])

    def test_unlimited_flag(self):
        _, rows = parse("TELUS", "Postpaid", "telus")
        self.assertEqual([r["unlimited_data"] for r in rows], ["N", "Y", "Y", "N", "N", "N"])

    def test_gophonebox_segments(self):
        src, rows = parse("PhoneBox", "Mixed", "gophonebox")
        got = [(r["segment"], r["price_cad"], r["data_gb"]) for r in rows]
        self.assertEqual(got, [("Postpaid", 40, 75), ("Postpaid", 50, 85), ("Postpaid", 35, 50), ("Postpaid", 60, 100),
                               ("Prepaid", 35, 20), ("Prepaid", 45, 50), ("Prepaid", 55, 70), ("Prepaid", 9, 3),
                               ("Prepaid", 19, 10), ("Prepaid", 100, 100)])

    def test_validation_passes_clean_data(self):
        for (carrier, segment, parser) in EXPECTED:
            src, rows = parse(carrier, segment, parser)
            _, issues, ok = validate_source(rows, src, SETTINGS, {})
            self.assertTrue(ok, f"{carrier} {segment}: {issues}")
            self.assertEqual(issues, [], f"{carrier} {segment}: {issues}")

    def test_validation_catches_bad_data(self):
        src, rows = parse("Koodo", "Postpaid", "koodo")
        rows[0]["price_cad"] = 4500           # wrong magnitude
        rows[1]["regular_price_cad"] = 10     # below price
        _, issues, _ = validate_source(rows, src, SETTINGS, {})
        self.assertTrue(any("out of range" in i for i in issues))
        self.assertTrue(any("below price" in i for i in issues))

    def test_missing_plan_only_flagged_for_same_source(self):
        src, rows = parse("CTExcel", "Postpaid", "ctexcel")
        other = {"CTExcel|Prepaid|" + src["url"]}
        prev = {("CTExcel", "Prepaid", "500MB 4G Canada-wide"): {"price": 22, "source_id": next(iter(other))}}
        _, issues, _ = validate_source(rows, src, SETTINGS, prev)
        self.assertEqual(issues, [])  # a prepaid plan is not "missing" from the postpaid read

    def test_empty_page_fails_source(self):
        src = source("Koodo", "Postpaid", "koodo")
        rows = PARSERS["koodo"]("Page not found", src)
        _, _, ok = validate_source(rows, src, SETTINGS, {})
        self.assertFalse(ok)

    def test_day_over_day_flag(self):
        src, rows = parse("Koodo", "Postpaid", "koodo")
        prev = {(r["carrier"], r["segment"], r["plan_name"]): {"price": r["price_cad"], "source_id": r["source_id"]} for r in rows}
        prev[(rows[0]["carrier"], rows[0]["segment"], rows[0]["plan_name"])]["price"] = 20  # 45 vs 20 = +125%
        out, issues, ok = validate_source(rows, src, SETTINGS, prev)
        self.assertTrue(ok)
        self.assertEqual(out[0]["status"], "Review")
        self.assertTrue(any("moved" in i for i in issues))

    def test_generic_flags_review(self):
        src = {"carrier": "NewCo", "segment": "Unknown", "url": "https://example.com/plans", "parser": "generic"}
        rows = PARSERS["generic"]("Plan A 50GB data only $30 per month", src)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "Review")


if __name__ == "__main__":
    unittest.main()
