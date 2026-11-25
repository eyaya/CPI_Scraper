"""Parser for Zimbabwe merchandise trade -- Zimbabwe National Statistics
Agency (ZimStat), External Trade page (zimstat.co.zw/external-trade/), Excel.

  Exports_/Imports_Classified_by_Country_<mm>_<yyyy>.xlsx (Eurotrace extract,
      "Flow TotalExports / Imports, Indicators Value USD"): every partner x every
      month since January 2021, in US dollars (unit 1). "World" is the
      all-partner total (headline exports / imports); "Country Unkown Code"
      is a group.
  Trade_Summary_BEC_<mm>_<yyyy>.xlsx: Table 1 Summary of External Trade --
      domestic exports, re-exports, total exports, imports, trade balance by
      month (US$); Tables 2/3 exports / imports by Broad Economic Category,
      every BEC level printed ("1:Food and beverages", "11:Primary", ...;
      classification bec, the printed code as commodity_code_nso).
  Trade_Statistics_1985_to_2005.xlsx (Table 7.12 Summary of External Trade,
      $ million): annual exports (fob, excluding gold sales), domestic exports,
      re-exports and imports (cif). "Total Exports *" and "Trade Balance *"
      include gold sales and are not taken (they would not be exports minus
      imports of the same definition); growth rates and shares are not taken.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import warnings

import pandas as pd

from ._common import row

_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december"]


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def _country(df, base) -> list[dict]:
    rows = []
    flow = None
    for i in range(min(12, len(df))):
        if str(df.iat[i, 0]).strip().lower() == "flow":
            f = str(df.iat[i, 1]).strip().lower()
            flow = "export" if "export" in f else "import" if "import" in f else None
        if str(df.iat[i, 0]).strip().lower() == "indicators" and "usd" not in str(df.iat[i, 1]).lower():
            return rows
    yi = next((i for i in range(len(df)) if str(df.iat[i, 0]).strip().lower() == "year"), None)
    if flow is None or yi is None:
        return rows
    hi = yi + 1
    periods, year = {}, None
    for j in range(1, len(df.columns)):
        y = _num(df.iat[yi, j])
        if y and 1990 < y < 2100:
            year = int(y)
        mname = str(df.iat[hi, j]).strip().lower()
        if year and mname in _MONTHS:
            periods[j] = f"{year}-{_MONTHS.index(mname) + 1:02d}"
    for i in range(hi + 1, len(df)):
        name = df.iat[i, 0]
        if not isinstance(name, str) or not name.strip():
            continue
        name = " ".join(name.split())
        if name.lower() == "world":
            kw = {}
        else:
            kw = dict(partner=name, partner_type="group" if "unkown" in name.lower() or "unknown" in name.lower()
                      else "country")
        for j, per in periods.items():
            v = _num(df.iat[i, j])
            if v is None or v < 0:
                continue
            rows.append(row(tradeflow=flow, period=per, frequency="monthly", value=v, unit="USD",
                            trade_system="general", series_code=f"{base}", **kw))
    return rows


def _month(v):
    if isinstance(v, (dt.datetime, dt.date, pd.Timestamp)):
        return f"{v.year}-{v.month:02d}"
    return None


def _summary(xl, base) -> list[dict]:
    rows = []
    s = xl.parse("Summary", header=None)
    hi = next(i for i in range(10) if str(s.iat[i, 0]).strip().lower().startswith("month"))
    cols = {}
    for j, h in enumerate(s.iloc[hi]):
        h = " ".join(str(h).lower().split())
        cols[j] = {"domestic exports": "domestic_export", "re-exports": "re_export", "total exports": "export",
                   "imports": "import", "trade balance": "balance"}.get(h)
    for i in range(hi + 1, len(s)):
        per = _month(s.iat[i, 0])
        if not per:
            continue
        for j, fl in cols.items():
            if not fl:
                continue
            v = _num(s.iat[i, j])
            if v is None or (v < 0 and fl != "balance"):
                continue
            rows.append(row(tradeflow=fl, period=per, frequency="monthly", value=v, unit="USD",
                            trade_system="general", series_code=f"{base}: Table 1"))
    for sh, fl in (("ExportsByBEC", "export"), ("ImportsByBEC", "import")):
        b = xl.parse(sh, header=None)
        hi = next(i for i in range(10) if str(b.iat[i, 0]).strip().lower().startswith("bec"))
        pcols = {j: _month(v) for j, v in enumerate(b.iloc[hi]) if _month(v)}
        for i in range(hi + 1, len(b)):
            lab = b.iat[i, 0]
            if not isinstance(lab, str):
                continue
            m = re.match(r"^(\d{1,3})\s*:\s*(.+)$", lab.strip())
            if not m:
                continue
            for j, per in pcols.items():
                v = _num(b.iat[i, j])
                if v is None or v < 0:
                    continue
                rows.append(row(tradeflow=fl, period=per, frequency="monthly", value=v, unit="USD",
                                commodity=lab.strip(), commodity_classification="bec",
                                commodity_code_nso=m.group(1), trade_system="general",
                                series_code=f"{base}: {sh}"))
    return rows


def _hist(df, base) -> list[dict]:
    rows = []
    cap = str(df.iat[0, 0])
    if "$ million" not in cap.lower():
        return rows
    years = {j: int(v) for j, v in enumerate(df.iloc[1]) if _num(v) and 1900 < _num(v) < 2100}
    want = {"exports (fob)": ("export", "fob"), "domestic": ("domestic_export", "fob"),
            "re-exports": ("re_export", "fob"), "imports (cif)": ("import", "cif")}
    for i in range(2, len(df)):
        lab = " ".join(str(df.iat[i, 0]).lower().split())
        if lab.startswith("b.") or "growth" in lab:
            break
        if lab not in want:
            continue
        fl, basis = want[lab]
        for j, y in years.items():
            v = _num(df.iat[i, j])
            if v is None or v < 0:
                continue
            # "$ million" in this ZimStat table is the Zimbabwe dollar (Z$; values
            # run from 1 596 in 1985 to 38 690 250 in 2005 with the inflation),
            # ISO 4217 ZWD (the pre-2006 code).
            rows.append(row(tradeflow=fl, period=str(y), frequency="annual", value=v, unit="ZWD",
                            unit_multiplier=1e6, price_basis=basis, series_code=f"{base}: Table 7.12"))
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    paths = sorted(set([path] + [p for p in (extras or []) if p.lower().endswith((".xls", ".xlsx"))]))
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for p in paths:
            base = os.path.basename(p)
            low = base.lower()
            if "summary" in low and "bec" in low:
                xl = pd.ExcelFile(p)
                rows += _summary(xl, base)
                xl.close()
            elif "classified_by_country" in low.replace(" ", "_"):
                rows += _country(pd.read_excel(p, header=None), base)
            elif "1985_to_2005" in low:
                rows += _hist(pd.read_excel(p, header=None), base)
    if not rows:
        raise ValueError("zimbabwe_zimstat: no rows decoded")
    df = pd.DataFrame.from_records(rows)
    key = ["tradeflow", "commodity", "partner", "frequency", "period", "price_basis"]
    return df.drop_duplicates(key, keep="last").reset_index(drop=True)
