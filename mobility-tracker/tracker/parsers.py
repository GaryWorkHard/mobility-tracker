"""Parsers turn a page's visible text into plan rows.

Every parser takes (text, source) and returns a list of dicts using COLUMNS below.
Text is whitespace-collapsed first, so line breaks in the page do not matter.
"""
import re
from decimal import Decimal

COLUMNS = ["capture_date", "carrier", "segment", "plan_type", "plan_name", "price_cad",
           "regular_price_cad", "data_gb", "unlimited_data", "speed", "detail", "status",
           "source_url", "source_id", "run_id"]


def source_id(src):
    return f"{src['carrier']}|{src['segment']}|{src['url']}"


def norm(text):
    return re.sub(r"\s+", " ", text.replace(" ", " ")).strip()


def num(s):
    if s is None or s == "":
        return None
    d = Decimal(str(s).replace(",", "").replace(" ", ""))
    return int(d) if d == d.to_integral_value() else float(d)


def gb(value, unit="GB"):
    v = num(value)
    return v / 1000 if unit.upper() == "MB" else v


def row(src, name, price, reg=None, data=None, unlimited=False, speed="", detail="",
        plan_type="", segment=None, status="Captured"):
    return {"carrier": src["carrier"], "segment": segment or src["segment"], "plan_type": plan_type,
            "plan_name": name, "price_cad": num(price), "regular_price_cad": num(reg),
            "data_gb": data, "unlimited_data": "Y" if unlimited else "N", "speed": speed,
            "detail": norm(detail)[:240], "status": status, "source_url": src["url"], "source_id": source_id(src)}


def speed_of(s):
    m = re.search(r"up to (\d+(?:\.\d+)?) ?([GM]bps)", s, re.I)
    tier = "5G+" if "5G+" in s else ("5G" if "5G" in s else "")
    return f"{tier} up to {m.group(1)} {m.group(2)}".strip() if m else tier


def last_heading(pos, headings):
    cur = ""
    for p, h in headings:
        if p < pos:
            cur = h
    return cur


def telus(text, src):
    t = norm(text)
    heads = [(m.start(), m.group(1)) for m in re.finditer(r"(5G\+ Complete|5G\+ Select|5G\+ for Families|Talk & Text) (?:Enjoy|Stay|Blazing)", t)]
    heads += [(m.start(), "Talk & Text") for m in re.finditer(r"Talk & Text Enjoy nationwide", t)]
    pat = re.compile(r"(?:GREAT VALUE|BETTER VALUE|BEST VALUE|PROMOTION|VALUE PLAN) (?P<name>[A-Za-z0-9&+\- ]+?) "
                     r"\$(?P<reg>\d+) \$ (?P<price>\d+) per month\d* "
                     r"(?:(?P<gb>\d+) GB|Unlimited data|Pay-per-use data)(?=(?P<rest>.{0,420}))")
    rows = []
    for m in pat.finditer(t):
        group = last_heading(m.start(), heads) or "5G+"
        unl = "Unlimited data" in m.group(0)
        rows.append(row(src, f"{group} - {m.group('name').strip()}", m.group("price"), m.group("reg"),
                        data=num(m.group("gb")), unlimited=unl, speed=speed_of(m.group("rest")) or "5G+",
                        detail=m.group("rest"), plan_type="BYOD"))
    return rows


def koodo(text, src):
    t = norm(text)
    split = t.find("Starter Plans")
    rows = []
    pat = re.compile(r"(?P<tag>Promotion|Kids plan)? ?\$(?P<reg>\d+) \$ (?P<price>\d+(?: ?\.\d+)?) per month\d? "
                     r"(?:(?P<gb>\d+) GB at (?P<spd>\dG) Speed|Pay-per-use data)(?=(?P<rest>.{0,260}))")
    for m in pat.finditer(t):
        starter = split != -1 and m.start() > split
        g = num(m.group("gb"))
        rest = m.group("rest").split("Add now")[0]  # stop at the end of this card
        name = ("Starter - Pay-per-use data" if g is None else
                f"Kids plan {g}GB" if m.group("tag") == "Kids plan" else f"Mobility {g}GB")
        if g is not None and "Canada-US-Mexico" in rest:
            name += " Canada-US-Mexico"
        rows.append(row(src, name, m.group("price"), m.group("reg"), data=g, speed=(m.group("spd") or ""),
                        detail=rest, plan_type="Starter" if starter else "BYOD"))
    pat2 = re.compile(r"(?<!\$\d\d )(?<!\$\d\d\d )\$ (?P<price>\d+)(?: ?\.(?P<dec>\d+))? per month\d? (?P<gb>\d+) (?P<u>GB|MB) at (?P<spd>\dG) Speed(?=(?P<rest>.{0,200}))")
    for m in pat2.finditer(t):
        price = f"{m.group('price')}.{m.group('dec')}" if m.group("dec") else m.group("price")
        g = gb(m.group("gb"), m.group("u"))
        rows.append(row(src, f"Starter {m.group('gb')}{m.group('u')} {m.group('spd')}", price, data=g,
                        speed=m.group("spd"), detail=m.group("rest"), plan_type="Starter"))
    return rows


def koodo_prepaid(text, src):
    t = norm(text)
    rows = []
    pat = re.compile(r"\$ (?P<price>\d+) per 30 days Unlimited Canada-wide Calling (?P<body>.*?)(?= \$ \d+ per 30 days| Buy a Koodo|$)")
    for m in pat.finditer(t):
        body = m.group("body")
        base = re.search(r"(\d+) GB at 4G speed without Automatic Top-Up", body, re.I)
        atu = re.search(r"(\d+) GB at 4G speed with Automatic Top-Up", body, re.I)
        detail = (f"{base.group(1)}GB without Auto Top-up; {atu.group(1)}GB with Auto Top-up" if base and atu
                  else body)
        rows.append(row(src, f"Prepaid ${m.group('price')}", m.group("price"),
                        data=num(base.group(1)) if base else None, speed="4G", detail=detail,
                        plan_type="4G base plan (per 30 days)"))
    return rows


def freedom(text, src):
    t = norm(text)
    rows = []
    pat = re.compile(r"Total Freedom plan (?:\$\d+ extra value! )?(?P<gb>\d+)GB 5G\+\S* \$ (?P<price>\d+) / mo\.(?P<rest>.{0,500}?)(?:Choose This Plan)")
    for m in pat.finditer(t):
        roam = re.search(r"(\d+)GB data in 120\+ Roam Beyond", m.group("rest"))
        d = f"{m.group('gb')}GB Canada-US-Mexico; {roam.group(1)}GB Roam Beyond" if roam else m.group("rest")
        rows.append(row(src, f"Total Freedom {m.group('gb')}GB ${m.group('price')}", m.group("price"),
                        data=num(m.group("gb")), speed="5G+", detail=d, plan_type="BYOD" if src["segment"] == "Postpaid" else "Prepaid by the month"))
    return rows


def virgin(text, src):
    t = norm(text)
    starts = [(m.start(), m) for m in re.finditer(
        r"Canada-wide 5G Talk and text|Canada-wide 5G (\d+)GB data, talk & text|Canada-U\.S\.-Mexico 5G (\d+)GB data, talk & text|(?<!5G )(\d+)(MB|GB) data, talk & text", t)]
    rows = []
    for i, (pos, m) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(t)
        chunk = t[pos:end]
        p = re.search(r"\$(\d+(?:\.\d+)?)/MO", chunk)
        if not p:
            continue
        s = m.group(0)
        if "Talk and text" in s:
            name, g, ptype = "Talk and text", None, "Talk & Text"
        elif s.startswith("Canada-U.S."):
            name, g, ptype = f"Canada-U.S.-Mexico 5G {m.group(2)}GB", num(m.group(2)), "BYOD"
        elif s.startswith("Canada-wide"):
            name, g, ptype = f"Canada-wide 5G {m.group(1)}GB", num(m.group(1)), "BYOD"
        else:
            name, g, ptype = f"{m.group(3)}{m.group(4)} data, talk & text", gb(m.group(3), m.group(4)), "Basic"
        rows.append(row(src, name, p.group(1), data=g, speed="3G" if ptype == "Basic" else "5G",
                        detail=chunk[:240], plan_type=ptype))
    return rows


def fido(text, src):
    t = norm(text)
    rows = []
    pat = re.compile(r"(?P<name>CANADA-WIDE 5G(?: & US-MEXICO ROAM)?) (?P<gb>\d+)GB, Talk & Text - BYOP Plan "
                     r"\$(?P<price>\d+)\.\d+ per mo\. \$ ?\d+ \.\d+ /mo\.(?: \$(?P<reg>\d+)\.\d+)?(?=(?P<rest>.{0,300}))")
    for m in pat.finditer(t):
        rows.append(row(src, f"{m.group('name').title()} {m.group('gb')}GB", m.group("price"), m.group("reg"),
                        data=num(m.group("gb")), speed="5G up to 1 Gbps", detail=m.group("rest"), plan_type="BYOD"))
    for m in re.finditer(r"(\d+)MB Basic Plan - BYOP Plan \$(\d+)\.\d+ per mo\.(?=(?P<rest>.{0,200}))", t):
        rows.append(row(src, f"{m.group(1)}MB Basic Plan", m.group(2), data=gb(m.group(1), "MB"),
                        speed="3 Mbps cap", detail=m.group("rest"), plan_type="Basic"))
    return rows


def bell(text, src):
    t = norm(text)
    rows = []
    pat = re.compile(r"(?P<name>Select - (?P<gb>\d+) GB with U\.S\. roaming|Ultra Unlimited with [A-Za-z./ ]+?roaming)"
                     r"(?P<body>.*?)(?:Price with eligible streaming )?\$(?P<price>\d+)/mo\. dollars per month.*?\$(?P<reg>\d+)/mo\.")
    for m in pat.finditer(t):
        unl = m.group("gb") is None
        rows.append(row(src, m.group("name"), m.group("price"), m.group("reg"), data=num(m.group("gb")),
                        unlimited=unl, speed=speed_of(m.group("body")) or "5G+", detail=m.group("body"),
                        plan_type="BYOD"))
    return rows


def rogers(text, src):
    t = norm(text)
    rows = []
    pat = re.compile(r"(?P<name>5G\+ (?:Lite|Essentials|Popular|Ultimate)) ~*\s?Price before incentives \$(?P<reg>\d+)/mo ?\$\d+/mo ?~*\s?"
                     r"\$ ?(?P<price>\d+) ?\.\d+ ?/mo\S* (?=(?P<rest>.{0,420}))")
    for m in pat.finditer(t):
        rest = re.split(r"5G\+ (?:Lite|Essentials|Popular|Ultimate) ~*", m.group("rest"))[0]  # stop at the next card
        d = re.search(r"(\d+) GB of High-Speed Data", rest)
        rows.append(row(src, m.group("name"), m.group("price"), m.group("reg"), data=num(d.group(1)) if d else None,
                        unlimited=d is None and "Unlimited High-Speed Data" in rest,
                        speed=speed_of(rest) or "5G+", detail=rest, plan_type="BYOD"))
    return rows


def kini(text, src):
    t = norm(text)
    rows = []
    for m in re.finditer(r"(\d+) ?GB Data (?:[^$]{0,40}?)\$ ?(\d+(?:\.\d+)?) per month(?=(?P<rest>.{0,200}))", t):
        rows.append(row(src, f"{m.group(1)}GB Data", m.group(2), data=num(m.group(1)), detail=m.group("rest"),
                        plan_type="Monthly prepaid"))
    return rows


def phonebox(text, src):
    t = norm(text)
    rows = []
    for m in re.finditer(r"(\d+) ?GB \$ ?(\d+) ?CAD ?/ ?(month|30 days) (?P<kind>Monthly|Prepaid ?30 days)", t):
        seg = "Prepaid" if m.group("kind").startswith("Prepaid") else "Postpaid"
        rows.append(row(src, f"{m.group(1)}GB {m.group('kind')}", m.group(2), data=num(m.group(1)),
                        detail=f"/{m.group(3)}", plan_type=m.group("kind"), segment=seg))
    return rows


def gophonebox(text, src):
    t = norm(text)
    heads = [(m.start(), h) for m, h in
             [(m, "Postpaid/Monthly") for m in re.finditer(r"Monthly Plans", t)] +
             [(m, "Prepaid") for m in re.finditer(r"Prepaid Plans", t)] +
             [(m, "Prepaid weekly") for m in re.finditer(r"Weekly Plans", t)] +
             [(m, "Prepaid 90-day") for m in re.finditer(r"90-day Plan", t)]]
    rows = []
    for m in re.finditer(r"\$ ?(\d+) ?/ ?(month|week|90 days)\s*\**(\d+) ?GB", t):
        h = last_heading(m.start(), heads) or "Unknown"
        seg = "Postpaid" if h.startswith("Postpaid") else "Prepaid"
        rows.append(row(src, f"{m.group(3)}GB per {m.group(2)}", m.group(1), data=num(m.group(3)),
                        detail=f"Landing page section: {h}", plan_type=h, segment=seg))
    return rows


def ctexcel(text, src):
    """CTExcel's page is in Chinese. Prepaid cards end '/ 30天', postpaid cards end '/ 月'."""
    t = norm(text)
    rows = []
    pat = re.compile(r"(?P<net>[45]G)网速套餐 (?P<area>全加拿大套餐|美加墨套餐) (?P<n>\d+)(?P<u>MB|GB)(?P<mid>.{0,160}?)"
                     r"C\$ ?(?P<price>\d+(?:\.\d+)?) ?/ ?(?P<per>30天|月)")
    for m in pat.finditer(t):
        region = "Canada-US-Mexico" if m.group("area") == "美加墨套餐" else "Canada-wide"
        seg = "Prepaid" if m.group("per") == "30天" else "Postpaid"
        rows.append(row(src, f"{m.group('n')}{m.group('u')} {m.group('net')} {region}", m.group("price"),
                        data=gb(m.group("n"), m.group("u")), speed=m.group("net"), detail=m.group(0),
                        plan_type=f"{region} ({'per 30 days' if seg == 'Prepaid' else 'monthly'})", segment=seg))
    return rows


def generic(text, src):
    """Fallback for a new carrier. Pairs 'N GB' with a nearby price. Always flagged for review."""
    t = norm(text)
    rows, seen = [], set()
    for m in re.finditer(r"(\d+)\s*GB[^$]{0,120}?\$\s*(\d+(?:\.\d+)?)|\$\s*(\d+(?:\.\d+)?)[^$]{0,120}?(\d+)\s*GB", t):
        g, p = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        if (g, p) in seen:
            continue
        seen.add((g, p))
        rows.append(row(src, f"{g}GB ${p}", p, data=num(g), detail=m.group(0), plan_type="Unclassified",
                        status="Review"))
    return rows


PARSERS = {"telus": telus, "koodo": koodo, "koodo_prepaid": koodo_prepaid, "freedom": freedom,
           "virgin": virgin, "fido": fido, "bell": bell, "rogers": rogers, "kini": kini,
           "phonebox": phonebox, "gophonebox": gophonebox, "ctexcel": ctexcel, "generic": generic}
