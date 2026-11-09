"""Self-verification. A source that fails these checks is not written; the last good data stays."""


def key(r):
    return (r["carrier"], r["segment"], r["plan_name"])


def validate_source(rows, src, settings, previous):
    """Returns (rows_to_write, issues, ok). previous maps key -> {"price": .., "source_id": ..} from the last good run."""
    src_id = f"{src['carrier']}|{src['segment']}|{src['url']}"
    issues, out, seen = [], [], set()
    lo, hi, pct = settings["min_price"], settings["max_price"], settings["max_day_change_pct"]
    for r in rows:
        r = dict(r)
        problems = []
        if not (r.get("carrier") and r.get("segment") and r.get("plan_name")):
            problems.append("missing carrier/segment/plan_name")
        p = r.get("price_cad")
        if not isinstance(p, (int, float)) or not (lo <= p <= hi):
            problems.append(f"price out of range: {p}")
        reg = r.get("regular_price_cad")
        if isinstance(p, (int, float)) and isinstance(reg, (int, float)) and reg < p:
            problems.append(f"regular price {reg} below price {p}")
        g = r.get("data_gb")
        if g is not None and (not isinstance(g, (int, float)) or g < 0 or g > 2000):
            problems.append(f"data_gb out of range: {g}")
        if r.get("unlimited_data") == "Y" and g is not None:
            problems.append("unlimited plan also has data_gb")
        k = key(r)
        if k in seen:
            problems.append("duplicate plan in same page")
        seen.add(k)
        old = (previous.get(k) or {}).get("price")
        if old and isinstance(p, (int, float)) and old > 0 and abs(p - old) / old * 100 > pct:
            problems.append(f"price moved {old} -> {p}")
        if problems:
            r["status"] = "Review"
            issues.append(f"{r.get('plan_name')}: " + "; ".join(problems))
        out.append(r)
    current_keys = {key(r) for r in out}
    for k, prev in previous.items():
        # only compare against plans this same page showed last time
        if prev.get("source_id") == src_id and k not in current_keys:
            issues.append(f"plan no longer seen: {k[2]}")
    # Count only plans of the segment this source is meant to show (guards against a tab click that did not switch).
    right = [r for r in out if r["status"] == "Captured" and (src["segment"] in ("Mixed", "Unknown") or r["segment"] == src["segment"])]
    ok = len(right) >= src.get("min_plans", 0) and (len(out) > 0 or src.get("min_plans", 0) == 0)
    if not ok:
        issues.insert(0, f"only {len(right)} usable {src['segment']} plans parsed, expected at least {src.get('min_plans')}")
    return out, issues, ok
