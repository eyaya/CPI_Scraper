"""Kenya -- KNBS quarterly Producer Price Indices release (one PDF per quarter).

Every release since 2013 carries:
  * "Producer Price Indices at Division level" (Table 2 to 2022, Table 5 since
    2023): ISIC Rev.4 2-digit divisions x the last 5 (to 2014: 8-9) quarters,
    with the division WEIGHTS, ending in a Total row. Column headers are
    "Mar-13", "Jun-25", "Sept-24" -- prices are collected mid-quarter, so a
    March column is the first quarter (period YYYY-Q1).
  * "Percentage changes over a Quarter and a Year ago" (Table 1 to 2022, Table 4
    since 2023): per division, weight + the q/q and y/y % change for the
    release quarter. KNBS swaps the two columns' ORDER between editions (2013:
    year-on-year first; 2026: quarter first), so the order is not trusted from
    the header: it is settled against the index table printed in the SAME
    release (index t / t-1 and t / t-4). If neither order reproduces the
    printed indices for most rows, the change table is dropped.

Bases: June 2011 = 100 (2013 - 2019 releases), March 2019 = 100 (rebased in
2020, "Kenya Producer Price Index Rebased Report 2020", whose Table 6.1 /
6.2 give division and class indices for 2019). The base is read from the
release's own text. Weights are filed at the release quarter: KNBS re-adjusted
them in 2016 after the closure of the Kenya Petroleum Refineries (marked **),
so they are a series, not a constant.

Releases whose text layer is empty (scanned: 2020 Q2, 2021 Q4, 2022 Q2-Q4) or
whose tables are images (2014 Q2, Q3) yield nothing; their quarters are
covered by the 5-quarter window of the following releases.

Read from the text layer only: never OCR, never computed.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

INDEX_NAME = "Producer Price Indices (PPI)"
_MON = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12}
_MTOK = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)[a-z]*\.?[-‐ ]?(\d{2})\b")
_NUM = r"-?[\d]+(?:\.\d+)?|‐?[\d]+(?:\.\d+)?|-"
_ROW = re.compile(r"^(?:(\d{1,4})\s+)?(.*?)\s*((?:(?:" + _NUM + r")\s+)*(?:" + _NUM + r"))\s*$")


def _q(mon: int, yy: str) -> str:
    y = 2000 + int(yy)
    return f"{y}-Q{(mon - 1) // 3 + 1}"


def _num(tok: str):
    return C.to_number(tok.replace("‐", "-"))


def _base(text: str) -> str:
    m = re.search(r"(June|March)\s+(2011|2019)\s*=\s*100", text)
    return f"{m.group(1)} {m.group(2)}=100" if m else ""


def _lines(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [ln for pg in pdf.pages for ln in (pg.extract_text() or "").split("\n")]


def _split(line: str):
    """(code, label, numbers) for a data line; None when it carries no numbers."""
    line = re.sub(r"^(\d{2})(?=[A-Za-z])", r"\1 ", line.strip())
    m = _ROW.match(line)
    if not m or not m.group(3):
        return None
    nums = m.group(3).split()
    # A trailing year in a label ("... 2016") is not data: need >= 2 numbers.
    if len(nums) < 2:
        return None
    return m.group(1) or "", m.group(2).strip(" .-‐*"), nums


def _table(lines: list[str], start: int, ncol: int):
    """Rows after a header at `start`: (code, label, numbers) up to and
    including the Total row, joining wrapped labels. Three wrap styles occur:
      2013  "Manufacture of wood and of products of wood and" / "16cork except furniture 2.02 ..."
      2017  "25 Manufacture of fabricated metal" / "products except ..." / "3.31456 93.95 ..."
      2026  "Manufacture of wood andof ..." / "16 1.02 104.02 ..." / "cork except furniture"
    """
    rows, pending, pcode, lone, last_from_pending = [], [], "", "", False
    for ln in lines[start + 1:]:
        s = ln.strip()
        if re.fullmatch(r"\d{1,2}", s):
            lone = s              # a code printed on a line of its own -- or a page number
            continue
        if not s or re.fullmatch(r"-\s*\d+\s*-", s) or s.startswith((
                "Kenya National Bureau", "Producer Price Ind", "ISIC", "2-Digit", "2- ",
                "Source", "*", "Macdonald", "DIRECTOR")):
            continue
        sp = _split(s)
        if sp is None:
            if re.match(r"^(Table|TABLE|As shown|The |Between|During|On a |Overall)", s):
                if rows:
                    break
                continue
            if s[:1].islower() and not pending and rows:
                code, label, nums = rows[-1]
                rows[-1] = (code, f"{label} {s}", nums)
                last_from_pending = False
                continue
            m = re.match(r"^(\d{2})\s*([A-Za-z].*)$", s)
            if m:
                pending, pcode = [m.group(2)], m.group(1)
            else:
                pending.append(s)
            continue
        code, label, nums = sp
        code = code or ("" if pending else lone)
        if (not label or label[:1].islower()) and pending:
            label = " ".join(pending + ([label] if label else []))
            code = code or pcode
            last_from_pending = True
        else:
            last_from_pending = False
        pending, pcode, lone = [], "", ""
        rows.append((code, re.sub(r"\s+", " ", label), nums))
        if label.lower().startswith("total"):
            break
    return [r for r in rows if len(r[2]) >= ncol and r[1]]


def _index_tables(lines, release_q, base):
    """Every division-index table in the release: header with >= 3 month tokens."""
    out = []
    for i, ln in enumerate(lines):
        toks = _MTOK.findall(ln)
        if len(toks) < 3 or "%" in ln.split(toks[0][0])[0]:
            continue
        cols = [_q(_MON[m.lower()], y) for m, y in toks]
        # Consecutive quarters, ending where the header ends; fill an unread
        # token ("Dec-15 16 Jun-16") only where the run of quarters proves it.
        last = cols[-1]
        head = ln.split("%")[0]
        rest = _MTOK.sub(" ", head.split("Weight")[-1])
        n = len(cols) + len(re.findall(r"(?<![\d.])\d{2}(?![\d.])", rest))
        y, q = int(last[:4]), int(last[-1])
        seq = []
        for k in range(n - 1, -1, -1):
            kk = y * 4 + q - 1 - k
            seq.append(f"{kk // 4}-Q{kk % 4 + 1}")
        if [c for c in seq if c in cols] != cols:
            continue
        has_w = any("eight" in x for x in lines[max(0, i - 2):i + 1])   # "Weights-**" may sit a line above
        rows = _table(lines, i, n + (1 if has_w else 0))
        for code, label, nums in rows:
            vals = nums[:n + 1] if has_w else nums[:n]
            if has_w:
                w, vals = vals[0], vals[1:]
            else:
                w = None
            out.append((code, label, w, dict(zip(seq, vals))))
    return out


def _change_table(lines, idx):
    """Table 1/4: per division weight + two % changes for the release quarter;
    returns rows of (code, label, a, b)."""
    for i, ln in enumerate(lines):
        if re.search(r"Percentage changes? (?:of PPI )?over|% Change over|Percentage changes over", ln, re.I) \
                and "Table" in ln:
            rows = _table(lines, i, 3)
            if len(rows) >= 5:
                return [(c, l, n[-2], n[-1]) for c, l, n in rows]
    return []


_OV_A = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-‐ ](\d{2})\s+(-?[\d.]+)\s+([-‐]?[\d.]+)$")
_OV_B = re.compile(r"^(?:(20\d{2})\s+)?(March|June|September|December)\s+(-?[\d.]+)\s+([-‐]?[\d.]+)$")


def _overall(lines):
    """The overall-PPI history table (Table 3 'PPI indices and inflation rates',
    2016-; Table 1 'Overall PPI and Inflation Rates', 2023-): one line per
    quarter, the overall index and its year-on-year change. Only runs of >= 4
    consecutive matching lines count (a chart axis never matches)."""
    runs, cur, year = [], [], None
    for ln in lines + [""]:
        s = ln.strip()
        a, b = _OV_A.match(s), _OV_B.match(s)
        if a:
            cur.append((_q(_MON[a.group(1).lower()], a.group(2)), a.group(3), a.group(4)))
            continue
        if b and (b.group(1) or year):
            year = b.group(1) or year
            mon = {"March": 3, "June": 6, "September": 9, "December": 12}[b.group(2)]
            cur.append((_q(mon, year[2:]), b.group(3), b.group(4)))
            continue
        if len(cur) >= 4:
            runs.append(cur)
        cur = []
        year = None
    return [r for run in runs for r in run]


# The 2023+ text layer drops some word spaces; repaired so one division keeps
# one label across releases (labels only -- never a value).
_GLUED = [("Manufactureofpharmaceuticals,medicinalchemical", "Manufacture of pharmaceuticals, medicinal chemical"),
          ("Manufactureof", "Manufacture of"), ("productsof", "products of"), ("andof", "and of"),
          ("woodand", "wood and")]


def _label(label: str, code: str) -> tuple[str, str]:
    """(label, code): repaired spacing, a code glued to the label split off,
    a one-digit code zero-padded ('7' -> '07', as KNBS prints it elsewhere)."""
    m = re.match(r"^(\d{2})\s*([A-Za-z].*)$", label)
    if m and not code:
        code, label = m.group(1), m.group(2)
    for a, b in _GLUED:
        label = label.replace(a, b)
    code = code.zfill(2) if len(code) == 1 else code
    label = re.sub(r"\s+", " ", label).strip()
    return ("Total" if label.lower().startswith("total") else label), code


def parse(path: str) -> pd.DataFrame:
    lines = _lines(path)
    text = "\n".join(lines)
    base = _base(text)
    if not base:
        raise ValueError(f"{path}: no base period printed")
    idx = _index_tables(lines, None, base)
    ov = _overall(lines)
    if not idx and not ov:
        raise ValueError(f"{path}: no division index table in the text layer (scanned or image)")
    out, level = [], {}
    release_q = max([q for *_, d in idx for q in d] + [q for q, *_ in ov])
    for code, label, w, d in idx:
        ind, code = _label(label, code)
        for q, tok in d.items():
            v = _num(tok)
            if v is None:
                continue
            level[(code, ind, q)] = v
            out.append(C.row(index_name=INDEX_NAME, industry=ind, industry_code_nso=code,
                             period=q, frequency="quarterly", measure="index", value=v,
                             base_period=base))
        wv = _num(w) if w is not None else None
        if wv is not None and ind != "Total":
            out.append(C.row(index_name=INDEX_NAME, industry=ind, industry_code_nso=code,
                             period=release_q, frequency="quarterly", measure="weight",
                             value=wv, unit="percent", base_period=base))

    ch = _change_table(lines, idx)
    if ch:
        def lag(q, k):
            y, n = int(q[:4]), int(q[-1])
            kk = y * 4 + n - 1 - k
            return f"{kk // 4}-Q{kk % 4 + 1}"
        score = {"qy": 0, "yq": 0}
        rows = []
        for code, label, a, b in ch:
            ind, code = _label(label, code)
            now = level.get((code, ind, release_q))
            p1, p4 = level.get((code, ind, lag(release_q, 1))), level.get((code, ind, lag(release_q, 4)))
            av, bv = _num(a), _num(b)
            if None in (now, p1, p4, av, bv) or not p1 or not p4:
                continue
            iq, iy = (now / p1 - 1) * 100, (now / p4 - 1) * 100
            score["qy"] += abs(av - iq) <= 0.15 and abs(bv - iy) <= 0.15
            score["yq"] += abs(av - iy) <= 0.15 and abs(bv - iq) <= 0.15
            rows.append((code, ind, av, bv))
        order = max(score, key=score.get)
        if rows and score[order] >= 0.7 * len(rows):
            for code, ind, av, bv in rows:
                qq, yy = (av, bv) if order == "qy" else (bv, av)
                for meas, v in (("inflation_qoq", qq), ("inflation_yoy", yy)):
                    out.append(C.row(index_name=INDEX_NAME, industry=ind, industry_code_nso=code,
                                     period=release_q, frequency="quarterly", measure=meas, value=v))
    # The overall-PPI history: index + y/y for every quarter it lists (fills
    # quarters whose own release is a scan, e.g. 2017).
    for q, lv, yy in ov:
        for meas, tok, unit, bp in (("index", lv, "index", base), ("inflation_yoy", yy, "percent", "")):
            v = _num(tok)
            if v is not None:
                out.append(C.row(index_name=INDEX_NAME, industry="Total", period=q,
                                 frequency="quarterly", measure=meas, value=v, unit=unit,
                                 base_period=bp))
    df = pd.DataFrame(out)
    # The rebased report prints the division table and the class table; a
    # label can appear in both with the same values -- keep one.
    return df.drop_duplicates(["industry", "industry_code_nso", "period", "measure", "base_period"], keep="first")


# A % change carries the base of its index (set from this output; see _base_carry).
from ._base_carry import carry_base  # noqa: E402
parse = carry_base(parse)
