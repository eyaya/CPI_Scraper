"""Mauritius -- poverty statistics (Statistics Mauritius).

PRIMARY: the "Data series on Poverty Statistics" workbook
(HS_Poverty_Oct26-20102026.xlsx), six Household Budget Survey rounds
1996/97, 2001/02, 2006/07, 2012, 2017, 2023:
  Table 1  RELATIVE poverty: line = half the median monthly household INCOME
           per adult equivalent (Rs); households and persons in poverty
           (number, %); poverty gap ratio (%).
  Table 2  ABSOLUTE thresholds: US$3.00 / $4.20 / $8.30 a day (2021 PPP),
           per-capita CONSUMPTION incl. imputed rent, % of poor persons; and the
           1996/97 and 2023 relative lines held FIXED in real terms (income).
EXTRA: the Poverty Analysis Report 2023, Table 25 -- the relative line specific
to the Island of Rodrigues, households and persons in poverty.

The workbook's COUNTS are revised to the 2022 Census base, so they differ from
the 2023 report's (Census 2011 base: 29,800 households vs 27,200). The
workbook is the NSO's later word and is taken; the report's Table 1 is not
read. Mauritius has NO official absolute line, hence relative + fixed
thresholds. "Income gap ratio" (mean shortfall of the POOR) is not an FGT
measure and is not collected; "Poverty gap ratio" is P1 over households.
'< 1' cells (US$3.00, 2017 and 2023) are skipped, never read as 1.

CROSS-CHECK (workbook): RPL 2023 Rs 12,378; households 7.3% (27,200);
persons 8.4% (101,200); PGR 1.8; $8.30 line 11.4%; 1996/97 fixed 1.2%.
Rodrigues 2023 (report T25): RPL Rs 9,719, households 17.4%, persons 19.3%.
"""
from __future__ import annotations

import re

import pandas as pd

ROUNDS = [("1996", "1996/97"), ("2001", "2001/02"), ("2006", "2006/07"),
          ("2012", "2012"), ("2017", "2017"), ("2023", "2023")]
RPL = "Relative poverty line (half the median monthly household income per adult equivalent)"
RPL_UNIT = "MUR per adult equivalent per month"

LAYOUT = {   # for check_registry: the default line of this source
    "survey": "HBS", "welfare_aggregate": "income", "unit_of_analysis": "person",
    "line_type": "relative", "line_level": "other", "line_name": RPL,
    "period": "2023", "frequency": "ad_hoc", "tables": [],
}


def _row(metric, value, period, ref, **kw):
    r = dict(survey=f"HBS {ref}", welfare_aggregate="income", unit_of_analysis="person",
             line_type="relative", line_level="other", line_name=RPL, line_value="",
             line_unit="", metric=metric, topic="total", characteristic="Total",
             sex="total", age_group="Total", geography="Total country", locality="all",
             locality_label="Total", period=period, reference_period=ref,
             frequency="ad_hoc", value=value, unit="percent", series_code="")
    r.update(kw)
    return r


def _sheet(path, name):
    df = pd.read_excel(path, sheet_name=name, header=None, dtype=object)
    out = []
    for _, r in df.iterrows():
        cells = [c for c in r.tolist() if not (isinstance(c, float) and pd.isna(c))]
        if cells:
            out.append(cells)
    return out


def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    return None          # '< 1', '…' -> no value


def _vals(cells):
    """The six round values after the label, or raise if the row is short."""
    vals = cells[1:]
    if len(vals) != 6:
        raise ValueError(f"expected 6 round values, got {cells!r}")
    return vals


def _workbook(path):
    rows = []
    t1 = _sheet(path, "Table 1")
    hdr = [c for c in t1 if len(c) == 6]
    if not hdr or [str(x).strip() for x in hdr[0]] != [r for _, r in ROUNDS]:
        raise ValueError(f"Table 1 round header changed: {hdr[:1]}")
    lines = {}
    for c in t1:
        lab = str(c[0]).lower()
        if lab.startswith("relative poverty"):
            lines = dict(zip([p for p, _ in ROUNDS], _vals(c)))
    if not lines:
        raise ValueError("Table 1: no relative poverty line row")
    spec = [("estimated number of households", "poor_count", "households", "household"),
            ("proportion of households", "headcount", "percent", "household"),
            ("estimated number of persons", "poor_count", "persons", "person"),
            ("proportion of persons", "headcount", "percent", "person"),
            ("poverty gap ratio", "gap", "percent", "household")]
    for c in t1:
        lab = str(c[0]).lower()
        for key, metric, unit, ua in spec:
            if lab.startswith(key):
                for (p, ref), v in zip(ROUNDS, _vals(c)):
                    x = _num(v)
                    if x is not None:
                        rows.append(_row(metric, x, p, ref, unit=unit, unit_of_analysis=ua,
                                         line_value=float(lines[p]), line_unit=RPL_UNIT))
    # Table 2 -- absolute thresholds, block by block
    t2 = _sheet(path, "Table 2")
    block = None
    for c in t2:
        lab = str(c[0]).strip()
        low = lab.lower()
        m = re.match(r"poverty line of us \$(\d+\.\d+) per person", low)
        if m:
            block = {"kind": "intl", "usd": m.group(1)}
            continue
        m = re.match(r"poverty line - using (\d{4}(?:/\d{2})?) relative poverty line as a 'fixed threshold'", low)
        if m:
            block = {"kind": "fixed", "base": m.group(1), "line": dict(zip([p for p, _ in ROUNDS], _vals(c)))}
            continue
        if block is None or len(c) != 7:
            continue
        if block["kind"] == "intl":
            name = f"US${block['usd']} a day (2021 PPP), per capita consumption incl. imputed rent"
            if low.startswith("- per person per month"):
                block["line"] = dict(zip([p for p, _ in ROUNDS], _vals(c)))
            elif low.startswith("proportion of poor persons"):
                for (p, ref), v in zip(ROUNDS, _vals(c)):
                    x = _num(v)
                    if x is not None:
                        rows.append(_row("headcount", x, p, ref, welfare_aggregate="consumption",
                                         line_type="international", line_level="other", line_name=name,
                                         line_value=float(block["line"][p]),
                                         line_unit="MUR per person per month"))
        else:
            name = (f"Fixed threshold: {block['base']} relative poverty line held constant in "
                    f"real terms")
            spec2 = [("estimated number of poor households", "poor_count", "households", "household"),
                     ("proportion of poor households", "headcount", "percent", "household"),
                     ("estimated number of poor persons", "poor_count", "persons", "person"),
                     ("proportion of poor persons", "headcount", "percent", "person")]
            for key, metric, unit, ua in spec2:
                if low.startswith(key):
                    for (p, ref), v in zip(ROUNDS, _vals(c)):
                        x = _num(v)
                        if x is not None:
                            rows.append(_row(metric, x, p, ref, unit=unit, unit_of_analysis=ua,
                                             line_type="national", line_level="other", line_name=name,
                                             line_value=float(block["line"][p]), line_unit=RPL_UNIT))
    return rows


def _rodrigues(pdf_path):
    """Report Table 25: three wrapped rows, six rounds each (verbatim layout:
    the label wraps around its own numbers, so the numbers line is matched)."""
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        text = next((p.extract_text() or "" for p in pdf.pages
                     if "Table 25 - Poverty indicators based on Relative Poverty Line specific"
                     in (p.extract_text() or "")), "")
    if not text:
        raise ValueError("report: Table 25 not found")
    lines = text.splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith("Table 25"))
    nums = []
    for l in lines[i:i + 14]:
        toks = l.replace(",", "").split()
        if len(toks) == 6 and all(re.fullmatch(r"\d+(?:\.\d+)?", t) for t in toks):
            nums.append([float(t) for t in toks])
    # header years row, then line, households %, persons %
    nums = [n for n in nums if n != [1996.0, 2001.0, 2006.0, 2012.0, 2017.0, 2023.0]]
    if len(nums) != 3:
        raise ValueError(f"report Table 25: expected 3 numeric rows, got {nums}")
    line, hh, pp = nums
    name = "Relative poverty line specific to the Island of Rodrigues"
    rows = []
    for (p, ref), lv, h, q in zip(ROUNDS, line, hh, pp):
        common = dict(geography="Island of Rodrigues", line_name=name, line_value=lv,
                      line_unit=RPL_UNIT)
        rows.append(_row("headcount", h, p, ref, unit_of_analysis="household", **common))
        rows.append(_row("headcount", q, p, ref, unit_of_analysis="person", **common))
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = _workbook(path)
    for ex in extras or []:
        if ex.lower().endswith(".pdf") and "poverty_analysis" in ex.lower():
            rows += _rodrigues(ex)
    return pd.DataFrame(rows)
