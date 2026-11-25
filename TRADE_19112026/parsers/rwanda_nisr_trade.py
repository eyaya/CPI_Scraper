"""Parser for NISR Rwanda "Formal External Trade in Goods" annex workbooks.

Two families, both in US$ million as stated on every table ("Value: US $
Million", "values in US$ million"):

QUARTERLY annex (`<YYYY>Q<n>_Trade_report_annexTables.xlsx`), a rolling window
of 14-16 quarters per report:
  Graph Overall          Exports / Imports / Re-Exports / Total Trade / Trade Balance (world)
  Graph EAC              the same five flows with the EAC (partner group "EAC")
  EAC                    each EAC partner state, by flow
  Regional blocks        CEPGL, COMESA, COMMON WEALTH, ECOWAS, SADC, EU (groups)
  Trade by continents    AFRICA, AMERICA, ASIA, EUROPE, OCEANIA (groups)
  Export/Import/ReexportsCountry   top-20 partner countries
  Exports/Imports/ReexportsCommodity  SITC sections (sitc1, code printed)
NISR's quarterly "Exports" are DOMESTIC exports: Total Trade = Exports +
Imports + Re-Exports and Trade Balance = Exports + Re-Exports - Imports, so the
flows are emitted as domestic_export / import / re_export / total / balance
(no all-exports row is printed in the quarterly tables). The WORLD lines of
"Trade by continents" and the "Total Estimates" lines of the partner sheets are
skipped: the world totals come from Graph Overall (the continents sheet's WORLD
line differs from it in older windows). Shares and growth-rate columns (the
second block of period headers) are not read.

MONTHLY annex (`<YYYYMM>_Trade_report_annexTables.xlsx`, `Tables_<Mon>_<YYYY>.xlsx`):
  1. Summary: Total Exports (f.o.b) = Domestic exports + Re-exports, Total
     Imports (c.i.f), Total External Trade, Trade Balance
  2-4. Domestic exports / imports / re-exports by SITC section
  5. Top-10 partners + "Rest of the World" for domestic exports (f.o.b.),
     re-exports (f.o.b.) and imports (c.i.f.)
Each table has three value columns: the report month a year earlier (revised),
the previous month and the report month. Their periods are read from the month
labels ("Aug(R)", "Jul", "Aug") anchored on the report year (the largest year
in the header row), never from the table titles (the January 2024 file's
partner caption says "December 2024").

Values are emitted exactly as stored in the workbook cells (unrounded floats).
Several files passed at once: the newest report wins a key (revised figures
replace provisional ones), as merge-on-write does across runs.
"""
from __future__ import annotations

import os
import re

import openpyxl
import pandas as pd

from ._common import row
from ..schema import KEY

UNIT, MULT = "USD", 1e6
_MON = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_QRX = re.compile(r"^(\d{4})Q([1-4])$")
_Q_FLOW = {"exports": "domestic_export", "export": "domestic_export", "imports": "import",
           "import": "import", "re-exports": "re_export", "re-export": "re_export",
           "reexports": "re_export", "total trade": "total", "trade balance": "balance"}
_GROUPS = {"eac", "cepgl", "comesa", "common wealth", "commonwealth", "ecowas", "sadc", "eu",
           "africa", "america", "asia", "europe", "oceania", "rest of the world", "others",
           "other countries", "unknown"}


def _s(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""


def _num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        # a spreadsheet residual such as -1.25e-13 is the 0.00 the cell displays
        return 0.0 if abs(v) < 1e-9 else float(v)
    return None


def _ptype(label: str) -> str:
    return "group" if label.lower() in _GROUPS else "country"


# ----------------------------------------------------------------- quarterly
def _period_cols(rows):
    """(header row index, [(col, period)]) -- the FIRST contiguous run of
    YYYYQn headers (a second run is the shares block)."""
    for i, r in enumerate(rows[:12]):
        cols, started = [], False
        for j, c in enumerate(r):
            m = _QRX.match(_s(c))
            if m and any(p == f"{m.group(1)}-Q{m.group(2)}" for _, p in cols):
                break                       # the shares block repeats the periods
            if m:
                cols.append((j, f"{m.group(1)}-Q{m.group(2)}"))
                started = True
            elif started:
                break
        if len(cols) >= 4:
            return i, cols
    return None, []


def _label_cols(rows, hdr, first_val):
    """Text cells left of the values: [(col)] that hold labels."""
    return list(range(first_val))


def _quarterly_sheet(ws, kind: str, sheet: str) -> list[dict]:
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    hdr, pcols = _period_cols(rows)
    if hdr is None:
        return []
    first = pcols[0][0]
    out, flow = [], None
    for r in rows[hdr + 1:]:
        labels = [_s(c) for c in r[:first]]
        if any(l.lower().startswith("source") for l in labels):
            break
        texts = [l for l in labels if l]
        if not texts:
            continue
        if kind in ("overall", "eac_total"):
            flow = _Q_FLOW.get(texts[-1].lower())
            if flow is None:
                continue
            partner = None if kind == "overall" else "EAC"
            ptype = "world" if kind == "overall" else "group"
            com = dict(commodity=None)
        elif kind in ("flow_partner", "partner_flow"):
            # EAC / continents: flow then partner; blocks: partner then flow
            if kind == "flow_partner":
                f_lab = next((l for l in labels if l.lower() in _Q_FLOW), "")
                p_lab = texts[-1]
                if f_lab:
                    flow = _Q_FLOW[f_lab.lower()]
            else:
                f_lab = texts[-1]
                flow = _Q_FLOW.get(f_lab.lower())
                p_cand = [l for l in labels if l and l.lower() not in _Q_FLOW]
                if p_cand:
                    _quarterly_sheet.partner = p_cand[0]
                p_lab = getattr(_quarterly_sheet, "partner", "")
            if flow is None or not p_lab or p_lab.lower() in _Q_FLOW:
                continue
            if p_lab.upper() == "WORLD" or p_lab.lower().startswith("total"):
                continue
            partner, ptype = p_lab, _ptype(p_lab)
            com = dict(commodity=None)
        elif kind.startswith("country_"):
            flow = kind.split("_", 1)[1]
            lab = texts[-1]
            if lab.lower().startswith(("total", "year and period")):
                continue
            partner, ptype = lab, _ptype(lab)
            com = dict(commodity=None)
        elif kind.startswith("commodity_"):
            flow = kind.split("_", 1)[1]
            code = next((l for l in labels if re.fullmatch(r"\d", l)), "")
            lab = texts[-1]
            if not code or lab == code:
                continue
            partner, ptype = None, "world"
            com = dict(commodity=lab, commodity_classification="sitc1", commodity_code_nso=code)
        else:
            continue
        for j, per in pcols:
            v = _num(r[j]) if j < len(r) else None
            if v is None:
                continue
            out.append(row(tradeflow=flow, period=per, frequency="quarterly", value=v, unit=UNIT,
                           unit_multiplier=MULT, partner=partner, partner_type=ptype,
                           series_code=f"Q:{sheet}", **com))
    return out


_Q_SHEETS = {"graph overall": "overall", "graph eac": "eac_total", "eac": "flow_partner",
             "trade by continents": "flow_partner", "regional blocks": "partner_flow",
             "exportcountry": "country_domestic_export", "importcountry": "country_import",
             "reexportscountry": "country_re_export",
             "exportscommodity": "commodity_domestic_export",
             "importscommodity": "commodity_import", "reexportscommodity": "commodity_re_export"}


def parse_quarterly(path: str) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = []
        for ws in wb.worksheets:
            kind = _Q_SHEETS.get(ws.title.strip().lower())
            if kind:
                _quarterly_sheet.partner = ""
                rows += _quarterly_sheet(ws, kind, ws.title.strip())
    finally:
        wb.close()
    if not rows:
        raise ValueError(f"rwanda_nisr_trade: no quarterly rows in {os.path.basename(path)}")
    df = pd.DataFrame.from_records(rows)
    # The EAC sheet and the top-20 partner sheets disagree for some EAC states
    # (the partner sheets carry NISR's revisions, e.g. tea and coffee
    # destinations). Keep the partner-sheet figure; the EAC sheet supplies only
    # the (flow, partner, quarter) cells the partner sheets do not print.
    k = ["tradeflow", "partner", "period"]
    ctry = df[df["series_code"].str.endswith("Country")][k].drop_duplicates()
    eac = df["series_code"] == "Q:EAC"
    alias = {"DRC": "Congo, The Democratic Republic Of", "Tanzania": "Tanzania, United Republic Of"}
    e = df[eac].reset_index()
    e["partner"] = e["partner"].replace(alias)        # for matching only; labels stay as printed
    hit = e.merge(ctry, on=k)["index"]
    return df.drop(index=hit).reset_index(drop=True)


# ------------------------------------------------------------------- monthly
_M_SUMMARY = {"a. total exports (f.o.b)": ("export", "fob"), "domestic exports": ("domestic_export", ""),
              "re-exports": ("re_export", ""), "b. total imports (c.i.f)": ("import", "cif"),
              "total external trade (a+b)": ("total", ""), "trade balance (a-b)": ("balance", "")}
_M_SECTION = (("total domestic exports of goods by s.i.t.c", "domestic_export"),
              ("total imports of goods by s.i.t.c", "import"),
              ("total re-exports of goods by s.i.t.c", "re_export"))
_M_PARTNER = (("re-exports (f.o.b", "re_export", "fob"), ("exports (f.o.b", "domestic_export", "fob"),
              ("imports (c.i.f", "import", "cif"))


def _month_periods(label_row, year_row):
    """Value columns -> periods, from the first three month labels."""
    years = [int(c) for c in year_row if isinstance(c, (int, float)) and 1990 < c < 2100]
    labs = []
    for j, c in enumerate(label_row):
        m = re.match(r"\s*([A-Za-z]{3})", _s(c))
        if m and m.group(1).lower() in _MON:
            labs.append((j, _MON[m.group(1).lower()]))
        if len(labs) == 3:
            break
    if len(labs) != 3 or not years:
        return []
    ry = max(years)
    (j0, m0), (j1, m1), (j2, m2) = labs
    if m0 != m2:
        raise ValueError(f"rwanda_nisr_trade: unexpected month columns {labs}")
    y1 = ry if m1 < m2 else ry - 1
    return [(j0, f"{ry - 1}-{m0:02d}"), (j1, f"{y1}-{m1:02d}"), (j2, f"{ry}-{m2:02d}")]


def parse_monthly(path: str) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows_ = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    finally:
        wb.close()
    out = []
    mode = None          # ("summary"|"sitc"|"partner", flow, basis)
    pcols = []
    for i, r in enumerate(rows_):
        texts = [_s(c) for c in r if _s(c)]
        if not texts:
            continue
        low = " ".join(texts).lower()
        # month-label row: sets the value columns of the table above it
        if re.search(r"\(r\)", low) and i > 0 and any(isinstance(c, (int, float)) for c in rows_[i - 1]):
            pcols = _month_periods(r, rows_[i - 1])
            continue
        if low.startswith("1. summary"):
            mode = ("summary", None, "")
            continue
        sec = next((f for t, f in _M_SECTION if t in low), None)
        if sec:
            mode = ("sitc", sec, "")
            continue
        par = next(((f, b) for t, f, b in _M_PARTNER if t in low and texts[0].lower() == "rank"), None)
        if par:
            mode = ("partner", par[0], par[1])
            pcols = []
            continue
        if mode is None or not pcols:
            continue
        lab = None
        if mode[0] == "summary":
            k = texts[0].lower()
            if k in _M_SUMMARY:
                flow, basis = _M_SUMMARY[k]
                kw = dict(commodity=None, partner=None, price_basis=basis)
            else:
                continue
        elif mode[0] == "sitc":
            m = re.match(r"^(\d)\s*-\s*(.+)$", texts[0])
            if not m:
                continue
            flow = mode[1]
            kw = dict(commodity=m.group(2).strip(), commodity_classification="sitc1",
                      commodity_code_nso=m.group(1), partner=None)
        else:
            flow = mode[1]
            lab = next((_s(c) for c in r[:3] if isinstance(c, str) and _s(c)), "")
            if not lab or lab.lower().startswith("total") or lab.lower().startswith("("):
                continue
            if lab.lower().startswith(("1preliminary", "rank")):
                continue
            kw = dict(commodity=None, partner=lab, partner_type=_ptype(lab), price_basis=mode[2])
        for j, per in pcols:
            v = _num(r[j]) if j < len(r) else None
            if v is None:
                continue
            out.append(row(tradeflow=flow, period=per, frequency="monthly", value=v, unit=UNIT,
                           unit_multiplier=MULT, series_code=f"M:{mode[0]}", **kw))
    if not out:
        raise ValueError(f"rwanda_nisr_trade: no monthly rows in {os.path.basename(path)}")
    return pd.DataFrame.from_records(out)


# --------------------------------------------------------------------- entry
def report_key(path: str) -> str:
    """Sortable report period of a file name (YYYY-MM or YYYY-Qn)."""
    b = os.path.basename(path)
    m = re.match(r"(?:wb_)?(\d{4})Q([1-4])", b)
    if m:
        return f"{m.group(1)}-Q{m.group(2)}"
    m = re.match(r"(\d{4})(\d{2})_", b)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"([A-Za-z]{3})[A-Za-z]*[ _](\d{4})", b)
    if m and m.group(1).lower() in _MON:
        return f"{m.group(2)}-{_MON[m.group(1).lower()]:02d}"
    return b


def parse_file(path: str) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, read_only=True)
    names = [s.strip().lower() for s in wb.sheetnames]
    wb.close()
    return parse_quarterly(path) if "graph overall" in names else parse_monthly(path)


def parse(path: str, extras=None) -> pd.DataFrame:
    files = sorted({path, *(extras or [])}, key=report_key)
    frames = [parse_file(f) for f in files if f.lower().endswith((".xlsx", ".xls"))]
    df = pd.concat(frames, ignore_index=True)
    # newest report wins a key (files are in report order)
    return df.drop_duplicates([k for k in KEY if k in df.columns], keep="last").reset_index(drop=True)
