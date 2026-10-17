"""Annual back series for Chad: INSEED's own annual national accounts, all SNA
2008 / base 2017. Not a registry parser: `chad_inseed_gdp.parse` hands it the
PDFs as extras. Each report is its own vintage (INSEED revises: the 2023
report's 2022 current-price sectors differ from the 2019-2022 report's), so
`category_group` names the report and table, and nothing is chained.

* 'Rétropolation des comptes nationaux de 2005 à 2017 sous le SCN 2008 avec
  l'année de base 2017' -- annex Tableaux 1/3 (GDP by branch, current /
  constant 2017 prices) and 2/4 (goods-and-services account, current /
  constant), 2005-2017, XAF billion. Read from word positions: the text layer
  prints thousands with a space ('4 492,1'), which is joined back only when
  the two fragments touch (gap under 6 pt; columns are 20+ pt apart).
* 'Comptes nationaux des années 2019 à 2022 ... (Base 2017)' and 'Comptes
  nationaux provisoires de 2023 (Base 2017)' -- Tableaux 3-10: uses of GDP
  (current), their volume growth, contributions to growth and price change;
  GDP by the production approach (value / chained volume); GDP by sector at
  current prices, real growth and chained volume (2017 prices).

Not read: Tableau 1 (secondary sector narrative table), Tableau 2 (a mixed
summary of ratios and per-head figures that repeats the tables read),
Tableaux 11-16 (products and the income/capital accounts). Percent cells
('4,1%') are read as the percent printed. Everything as published.
"""
from __future__ import annotations
import os
import re
import pdfplumber

UNIT = "XAF billion"
CHAINED = "chained volume, base 2017"
_NUMCELL = re.compile(r"^-?\d{1,3}(?: \d{3})*(?:,\d+)?%?$|^-?\d+(?:,\d+)?%?$")
_CAP = re.compile(r"Tableau\s*(\d+)\s*:\s*([^\n]+)")


def _num(s: str) -> float:
    return float(s.replace("%", "").replace(" ", "").replace(",", "."))


def _year(s: str):
    t = re.sub(r"\s+", "", s or "")
    return t if re.fullmatch(r"(19|20)\d\d", t) else None


def _title(path: str) -> str:
    b = os.path.basename(path).lower()
    if "retropolation" in b:
        return "Rétropolation 2005-2017 (SCN 2008, base 2017)"
    m = re.search(r"(\d{4}-\d{4}|\d{4})", b)
    if "provisoires" in b:
        return f"Comptes nationaux provisoires {m.group(1)} (base 2017)"
    return f"Comptes nationaux {m.group(1)} (base 2017)"


def _spec(caption: str):
    """(approach, basis, measure, unit, base) or None to skip."""
    c = caption.lower()
    if "emplois du pib" in c:
        return "expenditure", "current", "level", UNIT, ""
    if "volumes des emplois" in c:
        return "expenditure", "constant", "growth_yoy", "percent", ""
    if "contributions à la croissance" in c:
        return "expenditure", "constant", "contribution", "percentage points", ""
    if "prix des emplois" in c:
        return "expenditure", "not_applicable", "growth_yoy", "percent", ""
    if "optique production" in c:
        return "production", "current", "level", UNIT, ""      # sections switch
    if "secteurs d" in c and "prix courants" in c:
        return "production", "current", "level", UNIT, ""
    if "secteurs d" in c and "évolution en volume" in c:
        return "production", "constant", "growth_yoy", "percent", ""
    if "secteurs d" in c and "volume chain" in c:
        return "production", "constant", "level", UNIT, CHAINED
    return None


def _rec(approach, cat, group, year, basis, measure, value, unit, base, code):
    agg = cat.upper().startswith("PIB") or "PRODUIT INTERIEUR BRUT" in cat.upper()
    return {"approach": "aggregate" if agg else approach,
            "category": cat, "category_group": group, "series_code": code,
            "geography": "National", "period": year, "frequency": "annual",
            "price_basis": basis, "seasonal_adjustment": "not_applicable",
            "measure": measure, "value": value, "unit": unit, "base_period": base}


def _report(path: str) -> list[dict]:
    title = _title(path)
    # Pair every table with the caption printed above it: captions and
    # tables are ordered by page and vertical position, and a table belongs
    # to the latest caption before it (a table continued on the next page,
    # or printed on the page after its caption, keeps that caption).
    events = []
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            for m in _CAP.finditer(text):
                hits = page.search(f"Tableau {m.group(1)}") or                     page.search(f"Tableau{m.group(1)}") or [{"top": 0}]
                events.append((pno, hits[0]["top"], 0, (m.group(1), m.group(2))))
            for t in page.find_tables():
                rows = t.extract()
                if len(rows) >= 2:
                    events.append((pno, t.bbox[1], 1, rows))
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    rows_out, cap, years = [], None, None
    for _, _, kind, obj in events:
        if kind == 0:
            cap, years = obj, None
            continue
        if not cap:
            continue
        tno, ctext = cap
        spec = _spec(ctext)
        if not spec:
            continue
        rows_out.extend(_table(obj, title, tno, ctext.strip(), spec, years))
        years = _table.last_years
    return rows_out


def _table(tb, title, tno, ctext, spec, years):
    approach, basis, measure, unit, base = spec
    group = f"{title}, Tableau {tno}: {ctext}"
    code = f"INSEED {title.split(' (')[0]} T{tno}"
    sect = (basis, measure, unit, base)
    optique = "optique production" in ctext.lower()
    out, parent = [], ""
    for r in tb:
        cells = [re.sub(r"\s+", " ", (c or "")).strip() for c in r]
        ys = [_year(c) for c in cells if _year(c)]
        if len(ys) >= 4:
            years = ys
            continue
        texts = [c for c in cells if c and not _NUMCELL.match(c)]
        nums = [c for c in cells if c and _NUMCELL.match(c)]
        label = " ".join(texts).strip()
        if not nums:
            low = label.lower()
            if optique and low.startswith("en valeur"):
                sect = ("current", "level", UNIT, "")
            elif optique and low.startswith("en volume"):
                sect = ("constant", "level", UNIT, CHAINED)
            continue
        if not years or not label or len(nums) != len(years):
            continue
        if label.lower().startswith("source"):
            continue
        if label.lower().startswith("dont") and parent:
            label = f"{parent}: {label}"
        else:
            parent = label
        b, m, un, bp = sect
        big = max(abs(_num(n)) for n in nums)
        for y, n in zip(years, nums):
            # A wrapped cell whose second line the text layer lost ('11' for
            # '11 120,7' in the 2019-2022 report's Tableau 8): not emitted.
            if re.fullmatch(r"\d{1,2}", n) and big >= 1000:
                continue
            out.append(_rec(approach, label, group, y, b, m, _num(n), un,
                            bp if m == "level" else "", code))
    _table.last_years = years
    return out


# --- the retropolation: word positions ------------------------------------

_FRAG_L = re.compile(r"^-?\d{1,3}$")
_FRAG_R = re.compile(r"^\d{3}(?:,\d+)?$")
_NUMW = re.compile(r"^-?\d+(?:,\d+)?$")


def _lines(page):
    words = sorted(page.extract_words(x_tolerance=1), key=lambda w: w["top"])
    groups, top = [], None
    for w in words:
        if top is None or abs(w["top"] - top) > 3:
            groups.append([])
            top = w["top"]
        groups[-1].append(w)
    out = []
    for g in groups:
        cur = []
        for w in sorted(g, key=lambda w: w["x0"]):
            if (cur and w["x0"] - cur[-1]["x1"] < 6 and _FRAG_L.match(cur[-1]["text"])
                    and _FRAG_R.match(w["text"])):
                cur[-1] = {**cur[-1], "text": cur[-1]["text"] + " " + w["text"],
                           "x1": w["x1"]}
            else:
                cur.append(dict(w))
        out.append([w["text"] for w in cur])
    return out


def _retro(path: str) -> list[dict]:
    title = _title(path)
    rows = []
    with pdfplumber.open(path) as pdf:
        spec, years, parent = None, None, ""
        for page in pdf.pages:
            text = page.extract_text() or ""
            m = _CAP.search(text)
            if m:
                tno, cap = m.group(1), m.group(2).strip()
                c = (cap + " " + text[m.end(): m.end() + 120]).lower()
                basis = "constant" if "constants" in c else "current"
                appr = "expenditure" if "biens et services" in c else "production"
                spec = (tno, cap, basis, appr)
                years, parent = None, ""
            if not spec:
                continue
            # a continuation page repeats neither caption nor header: the
            # table's last header carries over
            tno, cap, basis, appr = spec
            group = f"{title}, Tableau {tno}: {cap}"
            for toks in _lines(page):
                # the header ends in a run of years ('... de 2017 2 005 2 006 ...')
                run = []
                for t in reversed(toks):
                    # stop at a non-year, or at a year out of sequence (the
                    # caption's own 'de 2017' just before '2 005 ...')
                    if not _year(t) or (run and int(_year(t)) >= int(run[0])):
                        break
                    run.insert(0, _year(t))
                if len(run) >= 5:
                    years = run
                    parent = ""
                    continue
                if not years:
                    continue
                k = len(years)
                tail = toks[-k:]
                if len(toks) <= k or not all(_NUMW.match(t.replace(" ", "")) for t in tail):
                    continue
                label = re.sub(r"^[+=]\s*", "", " ".join(toks[:-k])).strip()
                if not label or _NUMW.match(label.replace(" ", "")):
                    continue
                # an indented lower-case item ('publique', 'non marchande')
                # belongs to the last capitalised line above it
                if label[0].islower() and parent:
                    label = f"{parent}: {label}"
                elif label[0].isupper():
                    parent = label
                for y, t in zip(years, tail):
                    rows.append(_rec(appr, label, group, y, basis, "level", _num(t),
                                     UNIT, "constant 2017 prices" if basis == "constant"
                                     else "", f"INSEED retropolation T{tno}"))
    return rows


def parse_annual(path: str) -> list[dict]:
    rows = _retro(path) if "retropolation" in os.path.basename(path).lower() \
        else _report(path)
    if not rows:
        raise ValueError(f"no national-accounts rows read from {path}")
    return rows
