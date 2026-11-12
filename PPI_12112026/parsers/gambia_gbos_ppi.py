"""Gambia -- GBoS quarterly Producer Price Index reports (gbosdata.org downloads).

One report per quarter, 2012-Q1 onwards: 2012-13 as PDF, 2013-Q4..2021-Q1 as
Word (.docx, served as "application/octet-stream"), 2021-Q2 onwards as PDF.
Two bases, as printed: "2009 = 100" (to the September 2017 report) and
"September 2017 = 100" (from the March 2018 report).

THREE LAYOUTS of the main table, recognised by how many numbers the
"All items Index" row carries, and PROVED per report by its own printed
changes before a single value is kept:

  A  (2009=100)  [weight] M-12  M-3  M-2  M-1  M | 1-month  point-to-point  3-month
                 proof: 1-month = M/M-1, point-to-point = M/M-12, 3-month = M/M-3
  B  (Mar 2018)  weight  M-6 .. M (7 months) | quarterly inflation
                 proof: quarterly = mean(M-2..M) / mean(M-5..M-3)
  C  (2019-Q2+)  weight  M-12  M-5 .. M (6 months) | prev-quarter  this-quarter  point-to-point
                 proof: point-to-point = M/M-12, this-quarter = mean(M-2..M)/mean(M-5..M-3)
  D  (2018-Q3..2019-Q1)  as C without the previous-quarter column; same proof

Columns are mapped by this template, NOT by the printed month headers: GBoS's
headers carry typos (December 2020: "Dec 2019 | Jul | Aug | Sep | Oct | Dec |
Sept 2020", i.e. Nov and Dec mislabelled) while the printed changes prove the
template. A report whose All-items row fails its proof (tolerance 0.06 pp) is
dropped whole, and so is any row with the wrong count of numbers.

Kept: every industry/aggregate index for each month; the month's 1-month and
point-to-point changes (A); the quarter-on-quarter inflation columns (B, C);
the "Monthly changes" row (C, All items); the "Quarterly Index" row (C, All
items, checked against the three-month means); the weights (once per base,
annual period = base year); the yearly tables "Overall Annual Inflation Rate"
(A: y/y by month) and "PPI Quarterly Inflationary Trend" (C: q/q by quarter).
Not kept: the 3-month difference (an end-month ratio, no schema measure) and
the "12 Months moving averages" index row.

Overlapping months across reports: the NEWEST report's value wins.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from . import _common as C

INDEX_NAME = "Producer Price Index (PPI)"
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december"]
_NUM = re.compile(r"^-?\d+(?:\.\d+)?$")
_SKIP = re.compile(r"moving average|^weights?$|^index$", re.I)
TOL = 0.06


def _report_month(path: str) -> str:
    """Report month from the GBoS file name ('607-producer-price-index-september-2025')."""
    m = re.search(r"(" + "|".join(_MONTHS) + r")-(\d{4})", os.path.basename(path).lower())
    if not m:
        raise ValueError(f"no report month in {path}")
    return f"{m.group(2)}-{_MONTHS.index(m.group(1)) + 1:02d}"


def _shift(period: str, n: int) -> str:
    y, m = int(period[:4]), int(period[5:7])
    k = y * 12 + m - 1 - n
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


def _quarter(period: str) -> str:
    return f"{period[:4]}-Q{(int(period[5:7]) - 1) // 3 + 1}"


def _clean(label: str) -> str:
    s = re.sub(r"\s+", " ", label.replace(" ", " ")).strip()
    return re.sub(r"\s+,", ",", s)


# ------------------------------------------------------------------ reading ---
def _docx_rows(path):
    import docx
    d = docx.Document(path)
    text = "\n".join(p.text for p in d.paragraphs)
    rows, tables = [], []
    for t in d.tables:
        trs = []
        for r in t.rows:
            seen, cells = set(), []
            for c in r.cells:
                if id(c._tc) in seen:
                    continue
                seen.add(id(c._tc))
                cells.append(c.text.strip())
            trs.append(cells)
            text += "\n" + " | ".join(cells)
        tables.append(trs)
    for trs in tables:
        for cells in trs:
            if not cells:
                continue
            label = _clean(cells[0])
            nums = [C.to_number(x) for x in cells[1:]]
            if label and any(v is not None for v in nums):
                rows.append((label, nums, True))
    return text, rows, tables


def _pdf_rows(path):
    """Rows from pdfplumber's TABLE extraction (cell-aligned), not the text
    layer: in the text layer a wrapped label's lines and a row's numbers come
    out interleaved with the next row's (December 2024), so a label can land
    on the wrong numbers. A table drawn with spacer columns (None cells, 2012-13)
    is read by count -- spacers and blanks dropped; a regular grid (2021+) is
    read by position, a blank cell kept as a gap. A cell split over two lines
    ("162.6" / "2") is rejoined."""
    import pdfplumber
    rows, tables, text = [], [], ""
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            text += "\n" + (pg.extract_text() or "")
            for t in pg.extract_tables():
                spacer = any(c is None for r in t for c in r)
                tables.append([[_cell(c) for c in r] for r in t])
                for r in t:
                    li = next((k for k, c in enumerate(r) if c and C.to_number(_cell(c)) is None
                               and re.search(r"[A-Za-z]", c)), None)
                    if li is None:
                        continue
                    label = _clean(r[li].replace("\n", " "))
                    rest = r[li + 1:]
                    if spacer:
                        nums = [C.to_number(_cell(c)) for c in rest if c not in (None, "")]
                        positional = False
                    else:
                        nums = [C.to_number(_cell(c)) for c in rest]
                        positional = True
                    if any(v is not None for v in nums):
                        rows.append((label, nums, positional))
    return text, rows, tables


def _cell(c) -> str:
    """A numeric cell wrapped over two lines ('162.6\\n2') is one number; a
    text cell's line breaks are spaces."""
    c = c or ""
    if re.fullmatch(r"\s*-?[\d.,]+\s*\n\s*[\d.,]+\s*", c):
        return re.sub(r"\s+", "", c)
    return c.replace("\n", " ")


# ------------------------------------------------------------------ layouts ---
def _pct(a, b):
    return (a / b - 1) * 100


def _close(a, b):
    return a is not None and abs(a - b) <= TOL + 0.005 * abs(b)


_COUNT = {("A", False): 8, ("A", True): 9, ("B", True): 9, ("C", True): 11, ("C-", True): 11, ("D", True): 10}


def _proves(name: str, hw: bool, v: list) -> bool:
    """The report's own printed changes reproduce from its index columns."""
    x = v[1:] if hw else v
    try:
        if name == "A":
            i12, i3, i2, i1, i0, mom, p2p, m3 = x
            return _close(mom, _pct(i0, i1)) and _close(p2p, _pct(i0, i12)) and _close(m3, _pct(i0, i3))
        if name == "B":
            lv, q = x[:7], x[7]
            return _close(q, _pct(sum(lv[4:]) / 3, sum(lv[1:4]) / 3))
        if name in ("C", "C-"):
            i12, lv, qc, p2p = x[0], x[1:7], x[8], x[9]
            ok_q = _close(qc, _pct(sum(lv[3:]) / 3, sum(lv[:3]) / 3))
            return ok_q and (name == "C-" or _close(p2p, _pct(lv[-1], i12)))
        if name == "D":
            i12, lv, qc, p2p = x[0], x[1:7], x[7], x[8]
            return _close(p2p, _pct(lv[-1], i12)) and _close(qc, _pct(sum(lv[3:]) / 3, sum(lv[:3]) / 3))
    except (TypeError, ZeroDivisionError, ValueError):
        return False
    return False


def _months(name: str, M: str) -> list:
    if name == "A":
        return [_shift(M, 12), _shift(M, 3), _shift(M, 2), _shift(M, 1), M]
    if name == "B":
        return [_shift(M, k) for k in range(6, -1, -1)]
    if name == "C-":           # the M-12 column is not proved: its period is withheld
        return [None] + [_shift(M, k) for k in range(5, -1, -1)]
    return [_shift(M, 12)] + [_shift(M, k) for k in range(5, -1, -1)]


def _layout(allrow, rows, M: str):
    """(name, has_weight, periods of the index columns, how proved).

    Proved on the All-items row; when there is no usable All-items row
    (September 2012 prints the header "ALL ITEMS (NEW SERIES; 2009=100)" in
    its place), on >= 80 % of the industry rows. "C-" is layout C whose
    point-to-point column does NOT reproduce (December 2024 prints 0.05 for
    All items where its index columns give 4.87): the quarter proof still
    fixes the six months, but the year-ago column and the point-to-point
    change are not kept."""
    order = [("A", False), ("A", True), ("B", True), ("C", True), ("D", True), ("C-", True)]
    if allrow is not None:
        v = [x for x in allrow if x is not None]
        for name, hw in order:
            if len(v) == _COUNT[(name, hw)] and _proves(name, hw, v):
                return name, hw, _months(name, M), "All items"
    vs = [[x for x in n if x is not None] for l, n, _ in rows if not re.match(r"all items", l, re.I)]
    for name, hw in order[:-1]:
        cand = [v for v in vs if len(v) == _COUNT[(name, hw)]]
        if len(cand) >= 10 and sum(_proves(name, hw, v) for v in cand) >= 0.8 * len(cand):
            return name, hw, _months(name, M), f"{sum(_proves(name, hw, v) for v in cand)}/{len(cand)} rows"
    return None


def _base(text: str) -> str:
    t = re.sub(r"\s+", " ", text)
    if re.search(r"september\s*2017\s*=\s*100", t, re.I):
        return "September 2017=100"
    if re.search(r"2009\s*=\s*100", t):
        return "2009=100"
    raise ValueError("no base printed")


def _parse_one(path: str) -> tuple[list[dict], str]:
    M = _report_month(path)
    text, rows, tables = (_docx_rows if path.lower().endswith(".docx") else _pdf_rows)(path)
    base = _base(text)
    allrow = next((n for l, n, _ in rows if re.match(r"all items", l, re.I)), None)
    # A label printed twice with DIFFERENT values (Sep 2024 labels the food
    # aggregate "Non-food items" as well as the non-food one) is ambiguous:
    # both rows are dropped, never one picked.
    vals_by = {}
    for l, n, _ in rows:
        vals_by.setdefault(l.lower(), set()).add(tuple(n))
    ambiguous = {k for k, v in vals_by.items() if len(v) > 1 and not k.startswith("all items")}
    lay = _layout(allrow, rows, M)
    if lay is None:
        return [], f"{os.path.basename(path)}: no layout proved (All items row: {allrow})"
    name, hw, months, proof = lay
    kw = dict(index_name=INDEX_NAME, base_period=base)
    out, seen, dropped, dlabels = [], set(), 0, []
    nidx = len(months)
    for label, nums, positional in rows:
        if _SKIP.search(label) or re.fullmatch(r"(?:19|20)\d{2}", label):
            continue
        v = [x for x in nums if x is not None]
        if re.match(r"monthly changes|quarterly index|quarterly inflation", label, re.I) and name != "C":
            continue                       # only layout C's are proved positionally
        if re.match(r"monthly changes", label, re.I) and name == "C":
            if len(v) == 7 and not positional or positional and len(nums) >= 7:
                vals = nums[1:8] if positional and len(nums) > 7 else v[:7]
                for per, x in zip(months, vals):
                    if x is not None:
                        out.append(C.row(industry="All items", period=per, frequency="monthly",
                                         measure="inflation_mom", value=x, **kw))
            continue
        if re.match(r"quarterly index", label, re.I) and name == "C":
            if len(v) == 3:
                yq, pq, cq = v
                lv = next(n for l, n, _ in rows if re.match(r"all items", l, re.I))
                lv = [x for x in lv if x is not None][2:8]
                if _close(cq, sum(lv[3:]) / 3) and _close(pq, sum(lv[:3]) / 3):
                    for per, x in ((_quarter(_shift(M, 12)), yq), (_quarter(_shift(M, 3)), pq), (_quarter(M), cq)):
                        out.append(C.row(industry="All items", period=per, frequency="quarterly",
                                         measure="index", value=x, **kw))
            continue
        if re.match(r"overall$", label, re.I):
            continue                       # repeats All items (A layout)
        need = nidx + (1 if hw else 0) + {"A": 3, "B": 1, "C": 3, "C-": 3, "D": 2}[name]
        if positional:
            cells = nums[:need] if len(nums) >= need else None
            if cells is None or any(c is None for c in cells[(1 if hw else 0):(1 if hw else 0) + nidx]):
                dropped += 1
                dlabels.append(label)
                continue
        else:
            if len(v) != need:
                if not (name == "A" and not hw and len(v) == need + 1):
                    dropped += 1
                    dlabels.append(f"{label} ({len(v)})")
                    continue
                v = v[1:]
            cells = v
        if label.lower() in ambiguous:
            dropped += 1
            dlabels.append(label + " (ambiguous)")
            continue
        ind = re.sub(r"^all items index$", "All items", label, flags=re.I)
        key = ind.lower()
        if key in seen:
            continue                       # the table prints All items twice
        seen.add(key)
        off = 1 if hw else 0
        w = None
        if hw and cells[0] is not None:
            # 2009=100 prints weights per TEN THOUSAND (All items 10000.00),
            # kept on that scale; September 2017=100 prints percent.
            w, unit = cells[0], ("per_ten_thousand" if base == "2009=100" else "percent")
        if hw and cells[0] is not None and w is not None:
            out.append(C.row(industry=ind, period=re.search(r"(\d{4})", base).group(1), frequency="annual",
                             measure="weight", value=round(w, 4), unit=unit, **kw))
        for per, x in zip(months, cells[off:off + nidx]):
            if x is not None and per is not None:
                out.append(C.row(industry=ind, period=per, frequency="monthly", measure="index", value=x, **kw))
        tail = cells[off + nidx:]
        if name == "A":
            if tail[0] is not None:
                out.append(C.row(industry=ind, period=M, frequency="monthly", measure="inflation_mom", value=tail[0], **kw))
            if tail[1] is not None:
                out.append(C.row(industry=ind, period=M, frequency="monthly", measure="inflation_yoy", value=tail[1], **kw))
        elif name == "D":
            if tail[0] is not None:
                out.append(C.row(industry=ind, period=_quarter(M), frequency="quarterly", measure="inflation_qoq", value=tail[0], **kw))
            if tail[1] is not None:
                out.append(C.row(industry=ind, period=M, frequency="monthly", measure="inflation_yoy", value=tail[1], **kw))
        elif name == "B":
            if tail[0] is not None:
                out.append(C.row(industry=ind, period=_quarter(M), frequency="quarterly", measure="inflation_qoq", value=tail[0], **kw))
        else:
            for per, x in ((_quarter(_shift(M, 3)), tail[0]), (_quarter(M), tail[1])):
                if x is not None:
                    out.append(C.row(industry=ind, period=per, frequency="quarterly", measure="inflation_qoq", value=x, **kw))
            if tail[2] is not None and name == "C":
                out.append(C.row(industry=ind, period=M, frequency="monthly", measure="inflation_yoy", value=tail[2], **kw))
    out += _year_tables(text, rows, tables, name, kw)
    note = f"{os.path.basename(path)}: layout {name} (proved on {proof}), {base}, {len(out)} rows" + (f", {dropped} row(s) dropped: {dlabels}" if dropped else "")
    return out, note


def _year_tables(text, rows, tables, name, kw):
    """'Overall Annual Inflation Rate' (y/y by month, A) and 'PPI Quarterly
    Inflationary Trend' (q/q by quarter, C), All items."""
    out = []
    if tables:
        for trs in tables:
            head = " ".join(" ".join(r) for r in trs[:2]).lower()
            if "annual inflation" in head:
                for r in trs:
                    if r and re.fullmatch(r"(?:19|20)\d{2}", r[0].strip()):
                        vals = [C.to_number(x) for x in r[1:] if not re.fullmatch(r"(?:19|20)\d{2}", x.strip())]
                        for mi, x in enumerate(vals[:12]):
                            if x is not None:
                                out.append(C.row(industry="All items", period=f"{r[0].strip()}-{mi + 1:02d}",
                                                 frequency="monthly", measure="inflation_yoy", value=x, **kw))
            elif trs and [c.lower() for c in trs[0][:2]] == ["year", "quarter 1"]:
                for r in trs[1:]:
                    if r and re.fullmatch(r"(?:19|20)\d{2}", r[0].strip()):
                        for qi, x in enumerate(r[1:5]):
                            x = C.to_number(x)
                            if x is not None:
                                out.append(C.row(industry="All items", period=f"{r[0].strip()}-Q{qi + 1}",
                                                 frequency="quarterly", measure="inflation_qoq", value=x, **kw))
        return out
    if "Quarterly Inflationary Trend" in text and name in ("C", "D"):
        part = text.split("Quarterly Inflationary Trend", 1)[1]
        for line in part.splitlines():
            t = line.split()
            if len(t) == 5 and re.fullmatch(r"(?:19|20)\d{2}", t[0]):
                for qi, x in enumerate(t[1:]):
                    v = C.to_number(x)
                    if v is not None and _NUM.match(x):
                        out.append(C.row(industry="All items", period=f"{t[0]}-Q{qi + 1}",
                                         frequency="quarterly", measure="inflation_qoq", value=v, **kw))
            elif re.fullmatch(r"(?:19|20)\d{2}(?:\s+-?\d+\.\d+){1,3}\s+-", line.strip()):
                t = t[:-1]                 # the current year: "2025 1.02 1.17 1.34 -"
                for qi, x in enumerate(t[1:]):
                    out.append(C.row(industry="All items", period=f"{t[0]}-Q{qi + 1}",
                                     frequency="quarterly", measure="inflation_qoq", value=float(x), **kw))
    return out


NOTES: list[str] = []


def _disagreeing(a: pd.DataFrame, b: pd.DataFrame) -> int:
    """Industries whose monthly index differs by > 1 % between two reports on
    a month both print."""
    if a.empty or b.empty:
        return 0
    k = ["base_period", "industry", "period"]
    x = a[a.measure == "index"].set_index(k)["value"].to_frame("a").join(
        b[b.measure == "index"].set_index(k)["value"].to_frame("b"), how="inner").dropna()
    bad = (x["a"] - x["b"]).abs() > 0.01 * x["b"].abs()
    return x[bad].index.get_level_values("industry").nunique()


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """CROSS-REPORT CHECK. A report whose rows are shifted against their labels
    still proves on All items (December 2021: from "Leather" down every row
    carries the next row's numbers). So every report's monthly indices are
    compared with its neighbours' on the months both print, and a report that
    disagrees with BOTH neighbours (or its only one) on more than three
    industries is dropped whole. Isolated one-industry differences are
    revisions and the newest report wins."""
    files = [local_path] + list(extras or [])
    files = [f for f in files if re.search(r"producer-price-index-[a-z]+-\d{4}|ppi-[a-z]+-\d{4}", os.path.basename(f))]
    files = sorted(set(files), key=_report_month)        # oldest first: the newest report wins
    NOTES.clear()
    parts = []
    for f in files:
        got, note = _parse_one(f)
        NOTES.append(note)
        if got:
            parts.append((f, pd.DataFrame(got)))
    keep = []
    for i, (f, d) in enumerate(parts):
        nb = [parts[j][1] for j in (i - 1, i + 1) if 0 <= j < len(parts)]
        n = [_disagreeing(d, o) for o in nb]
        if nb and all(k > 3 for k in n):
            NOTES.append(f"DROPPED {os.path.basename(f)}: disagrees with its neighbouring reports on {n} industries")
            continue
        keep.append(d)
    if not keep:
        raise ValueError("gambia_gbos_ppi: nothing read")
    df = pd.concat(keep, ignore_index=True)
    key = ["index_name", "industry", "frequency", "measure", "base_period", "period"]
    return df.drop_duplicates(key, keep="last").reset_index(drop=True)
