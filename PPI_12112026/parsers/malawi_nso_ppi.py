"""Malawi -- NSO Producer Price Index (manufacturing, electricity and water).

Two series, both the NSO's own:

parse_annex  "Brief Release -- Annex Tables" workbooks (cms.nsomalawi.mw), base
    2019=100, monthly from January 2022 in the issues collected (2022-23, Jan-May
    2024, Jan-Sep 2024, Q4 2024, Q1 2025, Q1 2026). Sheets:
      indices by month ("Producer Price Indices (2019=100)"): 10 divisions /
        sections + total, with weights;
      rates sheets, ISIC section/division codes printed (C+D+E, C, D, E, D+E, 10,
        11, 12, 20, 22, 23), in blocks headed "Percentage change, latest month on
        same month a year ago" (m y/y), "... Month on Month", "... latest Quarter on
        same Quarter a year ago" / "Quartely change ( Year on Year)" (q y/y),
        "... latest Quarter on Previous Quarter" / "Quartely change ( Quarter on
        Quarter )" (q/q), "Average Percentage change, latest year on previous
        year" (annual average), and index blocks ("Detailed Indices", "Quartely
        Averages", "Annual averages", or unheaded at the top of the 2023 sheet).
    Every column is filed under the rates sheet's label and code, so the two
    sheet layouts ("Total index" / "Total ") give one series.
    CHECKS, not corrections: a quarterly (annual) index is kept only when it
    equals the mean of the same workbook's three (twelve) monthly indices to
    0.25 -- the Q4 2024 issue prints 2023's quarterly averages under 2024 and
    vice versa, so that block is dropped; a rate row with no year printed
    ("Q4" alone) is skipped.
parse_release_2016  "Producer Price Indices (2013 to 2016)", the first release
    (base 2012=100): Table 2, quarterly indices by division, 2013-Q1..2016-Q3.
    Prices are collected on 15 February/May/August/November; the table labels
    the quarters March/June/September/December -- the release itself calls them
    the first to fourth quarters. Table 1's percentage changes are collected too.

Values are rounded to each cell's display format (0.0 / 0.00).

Not collected: "PPI_brief_2022.pdf" (an image-only scan; no text layer).

CROSS-CHECK (verbatim): total index March 2026 385.6, February 374.0; total
y/y March 2026 14.6 (Q1 2026 issue); 2016 release total Sep-16 179.2,
Sep-13 173.0, food Mar-16 190.5, Sept 2016 vs Sept 2015 -12.8.
"""
from __future__ import annotations

import datetime as dt
import re

import pandas as pd

from . import _common as C

NAME = "Producer Price Index (PPI) - manufacturing, electricity and water"
BASE = "2019=100"
# The rates sheets' own labels, by the code they print.
LABEL = {"C+D+E": "Total", "C": "Manufacturing",
         "D": "Electricity, gas, steam and air conditioning supply",
         "E": "Water supply; sewerage, waste management and remediation activities",
         "D+E": "Electricity and Water", "10": "Manufacture of food products",
         "11": "Manufacture of beverages", "12": "Manufacture of tobacco products",
         "20": "Manufacture of chemicals and chemical products",
         "22": "Manufacture of rubber and plastics products",
         "23": "Manufacture of other non-metallic mineral products"}
# The index sheets print labels only; their meaning, by keyword (order matters).
_KEY = [("total index", "C+D+E"), ("total manufacturing", "C"), ("electricity and water", "D+E"),
        ("food", "10"), ("beverag", "11"), ("tobacco", "12"), ("chemical", "20"),
        ("rubber", "22"), ("non-metallic", "23"), ("electricity", "D"), ("water", "E")]
_MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
                                     "sep", "oct", "nov", "dec"], 1)}


def _heading(text: str):
    t = text.lower()
    if "contribution" in t:
        return "skip"
    if "month on month" in t:
        return ("inflation_mom", "monthly")
    if "latest month on same month" in t:
        return ("inflation_yoy", "monthly")
    if ("quarter" in t or "quartely" in t) and ("same quarter" in t or "year on year" in t):
        return ("inflation_yoy", "quarterly")
    if ("quarter" in t or "quartely" in t) and ("previous quarter" in t or "quarter on quarter" in t):
        return ("inflation_qoq", "quarterly")
    if "average percentage change" in t and "year" in t:
        return ("inflation_avg", "annual")
    if "detailed indices" in t:
        return ("index", "monthly")
    if "quartely averages" in t or "quaretly averages" in t or "quarterly averages" in t:
        return ("index", "quarterly")
    if "annual averages" in t:
        return ("index", "annual")
    return None


def _dec(fmt):
    m = re.search(r"0\.(0+)", (fmt or "").split(";")[0])
    return len(m.group(1)) if m else None


def _year(v):
    if isinstance(v, (int, float)) and 1990 <= v <= 2100:
        return int(v)
    m = re.fullmatch(r"\s*((?:19|20)\d{2})\s*", str(v or ""))
    return int(m.group(1)) if m else None


def _sheet(ws, out, notes):
    rows = list(ws.iter_rows())
    cols = None
    for i, r in enumerate(rows[:8]):
        codes = {j: str(c.value).strip() for j, c in enumerate(r)
                 if c.value is not None and str(c.value).strip() in LABEL}
        if len(codes) >= 5:
            cols = codes
            break
    if cols is None:
        for r in rows[:8]:
            labs = {j: str(c.value).strip().lower() for j, c in enumerate(r)
                    if isinstance(c.value, str) and len(c.value.strip()) > 4}
            if len(labs) >= 5:
                cols = {}
                for j, lab in labs.items():
                    code = next((c for k, c in _KEY if k in lab), None)
                    if code is None:
                        raise ValueError(f"{ws.title}: unknown column label {lab!r}")
                    cols[j] = code
                break
    if cols is None:
        return
    if len(set(cols.values())) != len(cols):
        raise ValueError(f"{ws.title}: two columns read as one code {cols}")
    block, year = ("index", None), None
    for r in rows:
        c0 = r[0].value if r else None
        if isinstance(c0, str) and len(c0.strip()) > 12 and not c0.strip().lower().startswith(("table", "section")):
            h = _heading(c0)
            if h:
                block, year = h, None
            continue
        if block == "skip":
            continue
        y = _year(c0)
        year = y or year
        c1 = r[1].value if len(r) > 1 else None
        if isinstance(c1, dt.datetime):
            freq, per = "monthly", f"{c1.year}-{c1.month:02d}"
        elif isinstance(c1, str) and re.fullmatch(r"\s*Q[1-4]\s*", c1):
            if not year:
                notes.append(f"{ws.title}: {c1.strip()} without a year -- skipped")
                continue
            freq, per = "quarterly", f"{year}-{c1.strip()}"
        elif isinstance(c1, str) and c1.strip().lower()[:3] in _MON:
            if not year:
                continue
            freq, per = "monthly", f"{year}-{_MON[c1.strip().lower()[:3]]:02d}"
        elif c1 is None and y:
            freq, per = "annual", str(y)
        else:
            continue
        meas, bfreq = block
        if meas != "index" and bfreq != freq:
            notes.append(f"{ws.title}: {per} under a {bfreq} heading -- skipped")
            continue
        for j, code in cols.items():
            if j >= len(r) or not isinstance(r[j].value, (int, float)):
                continue
            n = _dec(r[j].number_format)
            v = round(float(r[j].value), n if n is not None else 2)
            out.append(dict(C.row(index_name=NAME, industry=LABEL[code], industry_code_nso=code,
                                  period=per, frequency=freq, measure=meas, value=v,
                                  base_period=BASE if meas == "index" else ""),
                            _sheet=ws.title, _block=f"{ws.title}|{meas}|{freq}"))


def parse_annex(path: str) -> pd.DataFrame:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    out, notes = [], []
    for ws in wb:
        _sheet(ws, out, notes)
    wb.close()
    df = pd.DataFrame(out)
    # Monthly indices: one per cell; two sheets printing it must agree.
    m = df[(df.measure == "index") & (df.frequency == "monthly")]
    g = m.groupby(["industry", "period"]).value
    if (g.max() - g.min()).gt(0.051).any():
        bad = (g.max() - g.min())[lambda s: s > 0.051]
        raise ValueError(f"monthly index printed twice with different values: {bad.head().to_dict()}")
    mon = m.groupby(["industry", "period"]).value.first()
    # Quarterly / annual index blocks: kept only if they are the mean of the months.
    # A block that is mostly wrong is mislabelled as a whole (dropped); a single
    # differing cell is dropped alone and named.
    drop, drop_rows = set(), set()
    for blk, sub in df[(df.measure == "index") & (df.frequency != "monthly")].groupby("_block"):
        n, bad = 0, []
        for ix, ind, per, v, fq in zip(sub.index, sub.industry, sub.period, sub.value, sub.frequency):
            months = ([f"{per[:4]}-{(int(per[-1]) - 1) * 3 + k:02d}" for k in (1, 2, 3)] if fq == "quarterly"
                      else [f"{per}-{k:02d}" for k in range(1, 13)])
            vals = [mon.get((ind, p)) for p in months]
            if all(x is not None for x in vals):
                n += 1
                if abs(sum(vals) / len(vals) - v) > 0.25:
                    bad.append((ix, ind, per, v, round(sum(vals) / len(vals), 2)))
        if n and len(bad) > 0.1 * n:
            drop.add(blk)
            notes.append(f"{blk}: {len(bad)}/{n} averages differ from the months printed -- block dropped")
        elif bad:
            drop_rows.update(b[0] for b in bad)
            notes.append(f"{blk}: dropped {[b[1:] for b in bad]} (printed vs mean of months)")
    df = df[~df._block.isin(drop) & ~df.index.isin(drop_rows)]
    df = df.drop_duplicates(["industry", "period", "frequency", "measure"])
    parse_annex.notes = notes
    return df.drop(columns=["_sheet", "_block"]).reset_index(drop=True)


# ------------------------------------------------------------ 2016 release ---
_DIV16 = ["Manufacture of food products", "Manufacture of Beverages",
          "Processing of Tobacco (Stemming and re-drying)",
          "Manufacture of chemicals and chemical products", "Manufacture of rubber and plastics products",
          "Manufacture of other non-metallic mineral products", "Manufacture of fabricated metal products",
          "Electricity and Water", "Total Index"]
_CODE16 = ["10", "11", "12", "20", "22", "23", "25", "D+E", "C+D+E"]
_Q16 = {"march": 1, "june": 2, "september": 3, "december": 4}
NAME16 = "Producer Price Indices (first release, 2012=100)"


def parse_release_2016(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        text = "\n".join(pg.extract_text() or "" for pg in pdf.pages)
    out = []
    t2 = text[text.index("Table 2: Producer Price Indices at Division Level"):]
    t2 = t2[:t2.index("Source:")]
    w = re.search(r"Weights((?:\s+\d+\.\d+){9})", t2)
    for code, lab, v in zip(_CODE16, _DIV16, w.group(1).split()):
        out.append(C.row(index_name=NAME16, industry=lab, industry_code_nso=code, period="2012",
                         frequency="annual", measure="weight", value=float(v), base_period="2012=100"))
    year = None
    for line in t2.splitlines():
        line = line.strip()
        if re.fullmatch(r"20\d{2}", line):
            year = int(line)
            continue
        m = re.fullmatch(r"(March|June|September|December)((?:\s+\d+\.\d+){9})", line)
        if m and year:
            q = _Q16[m.group(1).lower()]
            for code, lab, v in zip(_CODE16, _DIV16, m.group(2).split()):
                out.append(C.row(index_name=NAME16, industry=lab, industry_code_nso=code,
                                 period=f"{year}-Q{q}", frequency="quarterly", measure="index",
                                 value=float(v), base_period="2012=100"))
    # Table 1: Sept 2016 vs June 2016 (q/q) and Sept vs Sept a year earlier (y/y).
    t1 = text[text.index("Table 1: Key figures"):text.index("Table 2:")]
    names1 = {"Manufacture of food products": 0, "Manufacture of Beverages": 1,
              "Processing of Tobacco": 2, "Manufacture of chemicals and chemical": 3,
              "Water and Electricity": 7, "Total Index": 8}
    for line in t1.splitlines():
        for start, k in names1.items():
            if line.startswith(start):
                nums = re.findall(r"-?\d+\.\d+", line)
                if len(nums) != 10:
                    raise ValueError(f"Table 1 row not 10 numbers: {line}")
                _w, *idx, qq, y16, y15, y14 = nums
                for per, meas, v in (("2016-Q3", "inflation_qoq", qq), ("2016-Q3", "inflation_yoy", y16),
                                     ("2015-Q3", "inflation_yoy", y15), ("2014-Q3", "inflation_yoy", y14)):
                    out.append(C.row(index_name=NAME16, industry=_DIV16[k], industry_code_nso=_CODE16[k],
                                     period=per, frequency="quarterly", measure=meas, value=float(v)))
    if len([r for r in out if r["measure"] == "index"]) != 15 * 9:
        raise ValueError("Table 2: expected 15 quarters x 9 columns")
    return pd.DataFrame(out)


# A % change carries the base of its index (set from this output; see _base_carry).
from ._base_carry import carry_base  # noqa: E402
parse_annex = carry_base(parse_annex)
parse_release_2016 = carry_base(parse_release_2016)
