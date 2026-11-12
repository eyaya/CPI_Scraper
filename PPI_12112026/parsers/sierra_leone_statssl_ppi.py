"""Sierra Leone -- Stats SL quarterly Producers' Price Index press releases.

statistics.sl/index.php/ppi.html lists eight releases (2017 Q4 .. 2023 Q4).
Every table is a QUARTERLY time series, so each release republishes 5-10
quarters and the 2017 release the whole 2012 Q1 .. 2017 Q4 history.

TWO INDEXES, as Stats SL states (2023 Q4 release, 1.1): the composite PPI on
the 2011 base year (releases to 2022 Q2), replaced by the Geometric Mean (GM)
PPI on the 2022 base year (mining x manufacturing x utilities, each with its
own 2022 weights). Kept as two series: index_name "Producers' Price Index
(PPI)" base "2011", and "Geometric Mean (GM) PPI" base "2022".

Tables are read from pdfplumber's cell grid (labels wrap over lines; the text
layer interleaves them). Two shapes:
  * rows = activities, columns = quarters: the header gives year cells over
    quarter cells ("2022 | 2023" over "Q4 Q1 Q2 Q3 Q4") or combined cells
    ("2023 Q1 (%)"). Quarters are assigned in order, the year advancing when
    the quarter number falls (Q4 -> Q1) -- and the result must use exactly the
    printed years, or the table is dropped.
  * rows = quarters ("2012 Q1"), columns = activities (2017 release).
A row is kept only when its count of numbers equals the header's quarters
(plus one for a Weight column). Measure from the table title: "Annual ...
Inflation" / "(%)" growth tables are y/y; the 2017 release's "Quarterly ...
Inflation Series" is q/q; "Contributions" tables are skipped. 2022-base weight
tables ("2022 Weights", production values beside them) give the weights only.
Overlapping quarters: the newest release wins.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from . import _common as C

OLD = ("Producers' Price Index (PPI)", "2011")
GM = ("Geometric Mean (GM) PPI", "2022")
_Q = re.compile(r"Q\s*([1-4])")
_Y = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
_YQ = re.compile(r"(20\d{2})\s*Q\s*([1-4])")
NOTES: list[str] = []


def _txt(c) -> str:
    return re.sub(r"\s+", " ", (c or "").replace("\n", " ")).strip()


def _num(c):
    if c is None:
        return None
    s = _txt(c).replace("%", "").strip()
    return C.to_number(s)


def _release(path: str) -> str:
    """Release quarter from the file name (2017 release -> 2017 Q4; '2016-2018-Q1' -> 2018 Q1)."""
    b = os.path.basename(path)
    m = re.search(r"(20\d{2})[-_ ]?Q([1-4])(?!.*20\d{2}[-_ ]?Q)", b)
    if m:
        return f"{m.group(1)}-Q{m.group(2)}"
    m = re.search(r"(20\d{2})", b)
    return f"{m.group(1)}-Q4"


def _periods(header_rows: list[list]) -> list[str] | None:
    flat = " ".join(_txt(c) for r in header_rows for c in r)
    combined = _YQ.findall(flat)
    if combined and len(combined) >= 2 and not any(_Q.findall(_txt(c)) for r in header_rows for c in r
                                                   if not _YQ.search(_txt(c)) and _Q.fullmatch(_txt(c) or "x")):
        return [f"{y}-Q{q}" for y, q in combined]
    qrow = next((r for r in header_rows if sum(bool(_Q.fullmatch(_txt(c))) for c in r) >= 2), None)
    if qrow is None:
        return None
    qs = [int(_Q.fullmatch(_txt(c)).group(1)) for c in qrow if _Q.fullmatch(_txt(c))]
    yrow = next((r for r in header_rows if r is not qrow and _Y.search(" ".join(_txt(c) for c in r))), None)
    if yrow is None:
        return None
    years = [int(y) for c in yrow for y in _Y.findall(_txt(c))]
    if not years:
        return None
    y, out, prev = years[0], [], None
    for q in qs:
        if prev is not None and q <= prev:
            y += 1
        out.append(f"{y}-Q{q}")
        prev = q
    # the printed year cells must be exactly the years the sequence spans
    if sorted(set(int(p[:4]) for p in out)) != sorted(set(years)):
        return None
    return out


def _caption(pg, top: float) -> str:
    """The table's caption: the nearest line above it naming a table, an
    index or an inflation series (within 60 pt); "" for a continuation."""
    if top < 5:
        return ""
    above = pg.crop((0, max(0, top - 60), pg.width, top)).extract_text() or ""
    lines = [l.strip() for l in above.splitlines() if l.strip()]
    for l in reversed(lines):
        if re.search(r"^table\s*\d+|price index|ppi|inflation|growth rate", l, re.I):
            return l
    return ""


def _index_for(title: str, base_text: str) -> tuple[str, str]:
    return GM if base_text == "2022" else OLD


def _row_tables(pdf, rel: str, base_text: str):
    rows, last_growth = [], False
    for pg in pdf.pages:
        for tb in pg.find_tables():
            t = tb.extract()
            if len(t) < 3:
                continue
            head = [r for r in t[:4]]
            caption = _caption(pg, tb.bbox[1])
            title = caption + " | " + " ".join(_txt(c) for r in head for c in r)
            if re.search(r"contribution|components of", title, re.I):
                continue
            # the 2017 release: rows are quarters
            if re.match(r"quarters", _txt(t[0][0]) or "", re.I) or any(_txt(c) == "Quarters" for c in t[0]):
                rows += _transposed(t, title, base_text)
                continue
            weights_tab = re.search(r"production value", title, re.I) and re.search(r"weights?", title, re.I)
            if weights_tab:
                for r in t:
                    lab = next((_txt(c) for c in r if c and re.search(r"[A-Za-z]", c) and _num(c) is None), "")
                    vals = [_num(c) for c in r if c not in (None, "") and _num(c) is not None]
                    if lab and len(vals) == 2 and not re.search(r"production value|new leones", lab, re.I):
                        name, base = _index_for(title, base_text)
                        rows.append(C.row(index_name=name, industry=lab, period=base, frequency="annual",
                                          measure="weight", value=vals[1], unit="percent", base_period=base))
                continue
            k = next((i for i, r in enumerate(t[:5]) if sum(bool(_Q.search(_txt(c))) for c in r) >= 2), None)
            if k is None:
                continue
            periods = _periods(t[:k + 1])
            if not periods:
                NOTES.append(f"{rel}: header not read: {title[:80]}")
                continue
            # A table continued on the next page repeats only the year/quarter
            # header: it inherits the measure of the titled table before it.
            # A "(%)" header (2023 Q4 growth tables) is itself the measure.
            # The caption above the table (Table 4: Annual Growth Rate of Mining
            # PPI) names the measure; failing one, a "(%)" header does.
            if re.search(r"contd|continued", caption, re.I):
                caption, title = "", re.sub(r"^.*?\|", "", title)   # a continuation inherits
            titled = bool(caption) or bool(re.search(r"index|inflation|growth|PPI|\(%\)", title, re.I))
            growth = bool(re.search(r"inflation|growth|\(%\)", title, re.I)) if titled else last_growth
            last_growth = growth
            has_w = bool(re.search(r"\bweights?\b", title, re.I))
            name, base = _index_for(title, base_text)
            for r in t[k + 1:]:
                cells = [c for c in r if c not in (None, "")]
                if not cells:
                    continue
                first_num = next((i for i, c in enumerate(cells) if _num(c) is not None), None)
                if not first_num:
                    continue
                lab = _txt(cells[first_num - 1])
                if not re.search(r"[A-Za-z]", lab) or re.search(r"\(%\)", lab):
                    continue
                vals = [_num(c) for c in cells[first_num:]]
                if any(v is None for v in vals) or len(vals) != len(periods) + has_w:
                    NOTES.append(f"{rel}: skipped '{lab[:50]}' ({len(vals)} numbers for {len(periods)} quarters)")
                    continue
                if has_w:
                    vals = vals[1:]
                for per, v in zip(periods, vals):
                    rows.append(C.row(index_name=name, industry=lab, period=per, frequency="quarterly",
                                      measure="inflation_yoy" if growth else "index", value=v,
                                      base_period=base))
    return rows


def _transposed(t, title, base_text):
    head = t[0]
    cols = [(i, _txt(c)) for i, c in enumerate(head) if c and _txt(c) != "Quarters"]
    m = "index"
    if re.search(r"annual|year-on-year", title, re.I):
        m = "inflation_yoy"
    elif re.search(r"inflation", title, re.I):
        m = "inflation_qoq"
    name, base = _index_for(title, base_text)
    out = []
    for r in t[1:]:
        lab = next((_txt(c) for c in r if c and _YQ.fullmatch(_txt(c))), None)
        if not lab:
            continue
        y, q = _YQ.fullmatch(lab).groups()
        vals = [_num(c) for c in r if c not in (None, "") and not _YQ.fullmatch(_txt(c))]
        if not vals:
            continue
        if len(vals) != len(cols):
            NOTES.append(f"transposed {y}-Q{q}: {len(vals)} numbers for {len(cols)} columns")
            continue
        for (_, ind), v in zip(cols, vals):
            ind = re.sub(r"^Inflation\s*-?\s*", "", ind)
            ind = re.sub(r"\s*Inflation$", "", ind)
            ind = {"Manufacturi ng": "Manufacturing", "PPI Combined Index": "PPI Combined",
                   "PPI Combined": "PPI Combined"}.get(ind, ind)
            out.append(C.row(index_name=name, industry=ind, period=f"{y}-Q{q}", frequency="quarterly",
                             measure=m, value=v, base_period=base))
    return out


def _parse_one(path: str) -> list[dict]:
    import pdfplumber
    rel = _release(path)
    with pdfplumber.open(path) as pdf:
        text = " ".join((pg.extract_text() or "") for pg in pdf.pages)
        base_text = "2022" if re.search(r"2022 base year|2022 weights", text, re.I) else "2011"
        rows = _row_tables(pdf, rel, base_text)
    NOTES.append(f"{os.path.basename(path)}: release {rel}, base {base_text}, {len(rows)} rows")
    return rows


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = sorted({local_path, *(extras or [])}, key=_release)   # oldest first: newest wins
    NOTES.clear()
    rows = []
    for f in files:
        rows += _parse_one(f)
    if not rows:
        raise ValueError("sierra_leone_statssl_ppi: nothing read")
    df = pd.DataFrame(rows)
    key = ["index_name", "industry", "frequency", "measure", "base_period", "period"]
    return df.drop_duplicates(key, keep="last").reset_index(drop=True)
