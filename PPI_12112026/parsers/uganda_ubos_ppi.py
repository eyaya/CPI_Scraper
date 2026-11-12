"""Uganda -- UBOS producer price indices (Excel tables on ubos.org).

parse_mu -- "Producer Price Index - Manufacturing & Utilities (PPI-M&U)", the
    monthly Excel tables released with each press release. One workbook
    carries the WHOLE current series, July 2016 to the release month, in six
    sheets: indices per section/division, per class; annual (y/y) and monthly
    (m/m) % change per division, per class. Weights are per mille (the M&U
    total = 1000). The workbook prints no base period (the series starts
    July 2016 at ~98; UBOS's base is not stated in the file), so base_period
    stays blank rather than being inferred.
    Row layout is not column-aligned: some class rows carry an extra leading
    cell ("Division | Group | Class"), so each row is read from its RIGHT: the
    trailing run of numbers is weight + one value per date column, and must
    have exactly that length or the row is skipped. Labels come from the
    index sheets by ISIC code (the change sheets abbreviate them: "Food
    Products" for "MANUFACTURE OF FOOD PRODUCTS"); a class whose label repeats
    its division's (1200 = 12 tobacco) with identical values is kept once.

parse_m_annual -- the previous series, base July 2009 - June 2010 = 100:
    "PPI-M (Local|Export) / PPI-M&U (Combined) Annual Percentage Changes,
    Calendar Year 2015-2019". Annual average index (first row) and annual %
    changes by industry group, as printed. Local = domestic_market, Export =
    export, Combined = output. (The fiscal-year twins of these files are not
    read: a fiscal year July-June is not a calendar period of this schema.)

parse_hr -- "Producer Price Index - Hotels & Restaurants", Base Period = 2008,
    quarterly by UBOS fiscal quarter (FY Q1 = July-September). A fiscal
    quarter is re-labelled as the calendar quarter it IS (FY 2020/21 Quarter4
    = April-June 2021 = 2021-Q2) -- a relabelling of the period, not of any
    value. index_variant 'services'.
"""
from __future__ import annotations

import datetime as dt
import re

import pandas as pd

from . import _common as C

MU_NAME = "Producer Price Index - Manufacturing & Utilities (PPI-M&U)"
HR_NAME = "Producer Price Index - Hotels & Restaurants (PPI-H&R)"
_SHEETS = {"INDICES PER DIVISION": "index", "INDICES PER CLASS": "index",
           "ANNUAL INFLATION PER DIVISION": "inflation_yoy", "ANNUAL INFLATION PER CLASS": "inflation_yoy",
           "MONTHLY INFLATION PER DIVISION": "inflation_mom", "MONTHLY INFLATION PER CLASS": "inflation_mom"}


def _isnum(c) -> bool:
    return isinstance(c, (int, float)) and not isinstance(c, bool)


def _code(c) -> str:
    s = str(c).strip()
    if re.fullmatch(r"\d{2,4}|[A-U](?:\s*-\s*[A-U])?", s):
        return s.replace(" ", "")
    return ""


def _sheet_rows(ws):
    """(code, label, weight, {period: value}) per data row of one sheet."""
    rows = list(ws.iter_rows(values_only=True))
    out, dates = [], None
    for r in rows:
        cells = list(r)
        while cells and cells[-1] is None:
            cells.pop()
        ds = [c for c in cells if isinstance(c, dt.datetime)]
        if len(ds) >= 3:
            dates = [f"{d.year}-{d.month:02d}" for d in ds]
            continue
        if not dates or not cells:
            continue
        tail = []
        for c in reversed(cells):
            if _isnum(c):
                tail.append(float(c))
            else:
                break
        tail.reverse()
        if len(tail) != len(dates) + 1:
            continue
        head = cells[:len(cells) - len(tail)]
        labels = [str(c).strip() for c in head if isinstance(c, str) and str(c).strip() and not _code(c)]
        codes = [_code(c) for c in head if c is not None and _code(c)]
        if not labels:
            continue
        label = labels[-1]
        if label.lower() in ("division", "group", "class"):
            continue
        code = max(codes, key=len) if codes else ""
        out.append((code, label, tail[0], dict(zip(dates, tail[1:]))))
    return out


def parse_mu(path: str) -> pd.DataFrame:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    got = {}
    for ws in wb.worksheets:
        meas = _SHEETS.get(ws.title.strip().upper())
        if meas:
            got[ws.title.strip().upper()] = (meas, _sheet_rows(ws))
    wb.close()
    if not got:
        raise ValueError(f"{path}: none of the PPI-M&U sheets {sorted(_SHEETS)}")
    # Labels by code from the index sheets.
    name = {}
    for title, (meas, rows) in got.items():
        if meas == "index":
            for code, label, *_ in rows:
                if code and code not in name:
                    name[code] = re.sub(r"\s+", " ", label)
    recs = []
    for title, (meas, rows) in got.items():
        for code, label, w, vals in rows:
            lab = name.get(code) or re.sub(r"\s+", " ", label)
            if not code and lab.lower().startswith(("manufacturing & utilities", "manufacturing and utilities")):
                lab, code = "MANUFACTURING & UTILITIES", ""
            for p, v in vals.items():
                recs.append(dict(industry=lab, code=code, period=p, measure=meas, value=v))
            if meas == "index":
                # 1000.0000000000002: a float artefact of the workbook's sum, not a value.
                recs.append(dict(industry=lab, code=code, period=max(vals), measure="weight", value=round(w, 9)))
    df = pd.DataFrame(recs)
    # One row per (label, period, measure): an uncoded repeat of a coded row
    # ("Manufacturing" beside "C Manufacturing") and a class repeating its
    # division with identical values are the same series; a label shared by
    # two codes with DIFFERENT values keeps both, the code appended.
    df["clen"] = df.code.str.len().replace(0, 9)
    df = df.sort_values("clen")
    df["key"] = df.industry.str.lower().str.strip()
    out = []
    for (k, p, m), g in df.groupby(["key", "period", "measure"], sort=False):
        if g.value.round(6).nunique() == 1:
            out.append(g.iloc[0])
        else:
            for _, r in g.iterrows():
                r = r.copy()
                r["industry"] = f"{r.industry} [{r.code}]" if r.code else r.industry
                out.append(r)
    df = pd.DataFrame(out)
    rows = []
    for r in df.itertuples():
        unit = "per_mille" if r.measure == "weight" else None
        rows.append(C.row(index_name=MU_NAME, industry=r.industry, industry_code_nso=r.code,
                          period=r.period, frequency="monthly", measure=r.measure, value=r.value,
                          unit=unit))
    return pd.DataFrame(rows)


_VARIANT = {"local": ("domestic_market", "PPI-M (Local)"), "export": ("export", "PPI-M (Export)"),
            "combined": ("output", "PPI-M&U (Combined)")}


def parse_m_annual(path: str) -> pd.DataFrame:
    x = pd.read_excel(path, sheet_name=None, header=None)
    df = next(iter(x.values()))
    title = str(df.iat[0, 0])
    kind = next(k for k in _VARIANT if k in title.lower())
    variant, short = _VARIANT[kind]
    base = "July 2009 to June 2010=100"
    hdr = next(i for i in range(len(df)) if sum(isinstance(v, (int, float)) and 1990 < float(v) < 2100
                                                 for v in df.iloc[i].tolist() if v == v) >= 3)
    years = {j: str(int(float(v))) for j, v in enumerate(df.iloc[hdr].tolist())
             if isinstance(v, (int, float)) and v == v and 1990 < float(v) < 2100}
    out, section = [], "inflation_avg" if kind != "combined" else None
    for i in range(hdr + 1, len(df)):
        lab = df.iat[i, 0]
        if not isinstance(lab, str) or not lab.strip() or lab.startswith("Source"):
            continue
        lab = lab.strip()
        # Combined: an "Index" block, then an "Annual Percentage change" block.
        if lab.lower() == "index":
            section = "index"
            continue
        if lab.lower().startswith("annual percentage change"):
            section = "inflation_avg"
            continue
        core = re.sub(r"^PPI-|\s+(Indices|Changes?)$", "", lab, flags=re.I).strip()
        meas = ("index" if re.search(r"indices$", lab, re.I) else
                "inflation_avg" if re.search(r"changes?$", lab, re.I) else section or "inflation_avg")
        ind = ("All industries" if core.lower() in ("manufacturing and utilities", "m local", "m export")
               else core if lab.startswith("PPI-") else lab)
        for j, y in years.items():
            v = C.to_number(df.iat[i, j])
            if v is None or v != v:
                continue
            out.append(C.row(index_name=f"{short}, annual", index_variant=variant, industry=ind,
                             period=y, frequency="annual", measure=meas, value=v,
                             base_period=base))   # a change carries the base of its index
    if len(out) < 10:
        raise ValueError(f"{path}: only {len(out)} values")
    return pd.DataFrame(out)


def parse_hr(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, header=None)
    title = " ".join(str(v) for v in df.iloc[:3, 0].tolist() if v == v)
    m = re.search(r"Base Period\s*=\s*(\d{4})", title)
    base = f"{m.group(1)}=100" if m else ""
    hdr = next(i for i in range(len(df)) if any(isinstance(v, str) and re.match(r"Quarter\s*\d", v)
                                                 for v in df.iloc[i].tolist()))
    fy_row = df.iloc[hdr - 1].tolist()
    cols, fy = {}, None
    for j, v in enumerate(df.iloc[hdr].tolist()):
        if isinstance(fy_row[j], str) and re.search(r"FY\s*(\d{4})/(\d{2})", fy_row[j]):
            fy = re.search(r"FY\s*(\d{4})/(\d{2})", fy_row[j]).group(1)
        if isinstance(v, str) and re.match(r"Quarter\s*(\d)", v) and fy:
            q = int(re.match(r"Quarter\s*(\d)", v).group(1))
            y = int(fy) + (1 if q >= 3 else 0)
            cols[j] = f"{y}-Q{(q + 1) % 4 + 1}"
    out, seen = [], set()
    for i in range(hdr + 1, len(df)):
        lab = df.iat[i, 0]
        if not isinstance(lab, str) or not lab.strip() or re.match(r"Table|Source|Note", lab.strip()):
            if out and isinstance(lab, str) and lab.strip().startswith("Table"):
                break
            continue
        lab = lab.strip()
        if lab.lower() in seen:            # the sub-group blocks repeat their heading rows
            continue
        seen.add(lab.lower())
        # Weights are printed per ten thousand (total 10000), a unit the schema
        # does not carry -- not collected rather than rescaled.
        for j, q in cols.items():
            v = C.to_number(df.iat[i, j])
            if v is not None and v == v:
                out.append(C.row(index_name=HR_NAME, index_variant="services",
                                 industry="All hotels & restaurants" if lab.lower() == "hotels & restaurants" else lab,
                                 period=q, frequency="quarterly", measure="index", value=v, base_period=base))
    if len(out) < 10:
        raise ValueError(f"{path}: only {len(out)} values")
    return pd.DataFrame(out)


def parse_yoy_2019(path: str) -> pd.DataFrame:
    """'Annual Changes in Producer Price Index-Manufacturing and Utilities
    (PPI-M&U) December 2018 to December 2019' and the 'Monthly Changes ...'
    block below it -- the last 13 months of the July 2009 - June 2010 = 100
    series: y/y and m/m % change for the combined index, utilities and
    manufacturing. The measure is taken from each block's own title."""
    df = pd.read_excel(path, sheet_name=0, header=None)
    ind = {"PPI-Manufacturing & Utilities Combined": "All industries", "PPI-Utilities": "Utilities",
           "PPI-Manufacturing": "Manufacturing"}
    out, meas, names = [], None, {}
    for i in range(len(df)):
        c0 = df.iat[i, 0]
        if isinstance(c0, str) and re.match(r"(Annual|Monthly) Changes", c0.strip()):
            meas = "inflation_yoy" if c0.strip().startswith("Annual") else "inflation_mom"
            continue
        if isinstance(c0, str) and c0.strip().upper() == "MONTHS":
            names = {j: str(v).strip() for j, v in enumerate(df.iloc[i].tolist()) if j and isinstance(v, str)}
            continue
        if not isinstance(c0, (dt.datetime, pd.Timestamp)) or not meas:
            continue
        for j, n in names.items():
            v = C.to_number(df.iat[i, j])
            if v is not None and v == v and n in ind:
                out.append(C.row(index_name="PPI-M&U (Combined)", industry=ind[n],
                                 period=f"{c0.year}-{c0.month:02d}", frequency="monthly",
                                 measure=meas, value=v, base_period="July 2009 to June 2010=100"))
    if len(out) < 60:
        raise ValueError(f"{path}: only {len(out)} values")
    return pd.DataFrame(out)
