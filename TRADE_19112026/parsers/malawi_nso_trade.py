"""Parser for Malawi merchandise trade -- National Statistical Office (NSO),
"Malawi International Merchandise Trade Statistics" Excel releases
(cms.nsomalawi.mw/api/download/...).

  Bulletin workbooks, Table 2.1 "Value of Total Imports and Total Exports for
      Malawi" (US$ or Malawi Kwacha, unit 1): annual rows (2021 ...) and the
      months of each year: imports, re-imports, total imports, domestic exports,
      re-exports, total exports, trade balance. Taken: total imports (flow
      import), domestic exports, re-exports, total exports, balance. A row whose
      TOTAL IMPORTS is not IMPORTS + RE-IMPORTS (the 2021 rows of the December
      2024 US$ workbook carry re-imports in that column) loses its total imports
      and balance (a check; nothing is recomputed). "Selected imports/exports"
      tables (quantities and values of chosen products) are not taken.
  BEC workbooks: Table 1/2 imports (CIF) / exports (FOB) by Broad Economic
      Category, sections ("Food & Beverages") and groups ("11:Food and
      beverages; primary"), monthly (columns "April 2026p" ...), US$.
  DOTS workbooks: Table 2 domestic exports by destination and Table 5 imports
      by source country, for the release month, US$ (partner cut).
"""
from __future__ import annotations

import os
import re
import warnings

import pandas as pd

from ._common import row

_MON = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
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


def _table21(df, base) -> list[dict]:
    rows = []
    cap = " ".join(str(v) for v in df.iloc[:3, 0].tolist()).upper()
    cur = "USD" if "US$" in cap else "MWK" if "KWACHA" in cap else None
    if cur is None:
        return rows
    hi = next(i for i in range(8) if str(df.iat[i, 0]).strip().upper().startswith("YEAR"))
    hdr = [" ".join(str(c).upper().split()) for c in df.iloc[hi]]
    ix = {h: j for j, h in enumerate(hdr)}
    year = None
    for i in range(hi + 1, len(df)):
        lab = df.iat[i, 0]
        s = str(lab).strip().lower()
        m = re.match(r"^(\d{4})\s*p?$", s.replace(".0", ""))
        if isinstance(lab, (int, float)) and not pd.isna(lab):
            m = re.match(r"^(\d{4})$", str(int(lab)))
        if m:
            year = int(m.group(1))
            per, freq = str(year), "annual"
        elif s[:3] in _MON and year:
            per, freq = f"{year}-{_MON.index(s[:3]) + 1:02d}", "monthly"
        else:
            continue
        g = lambda name: _num(df.iat[i, ix[name]]) if name in ix else None
        if freq == "monthly" and not any(g(h) for h in ("IMPORTS", "TOTAL EXPORTS", "DOMESTIC EXPORTS")):
            continue          # months after the release month are printed as 0: not data
        imp, reimp, timp = g("IMPORTS"), g("RE-IMPORTS"), g("TOTAL IMPORTS")
        ok_imp = None not in (imp, reimp, timp) and abs(imp + reimp - timp) <= 1 + 1e-6 * timp
        vals = [("domestic_export", g("DOMESTIC EXPORTS")), ("re_export", g("RE-EXPORTS")),
                ("export", g("TOTAL EXPORTS"))]
        if ok_imp:
            vals += [("import", timp), ("balance", g("TRADE BALANCE"))]
        for fl, v in vals:
            if v is None or (v < 0 and fl != "balance"):
                continue
            rows.append(row(tradeflow=fl, period=per, frequency=freq, value=v, unit=cur,
                            price_basis="cif" if fl == "import" else "fob" if fl != "balance" else "",
                            series_code=f"{base}: Table 2.1"))
    # the current year's row ("2026p") is year-to-date: kept only for complete years
    nmonths = {}
    for r in rows:
        if r["frequency"] == "monthly" and r["tradeflow"] == "export":
            nmonths[r["period"][:4]] = nmonths.get(r["period"][:4], 0) + 1
    return [r for r in rows if r["frequency"] != "annual" or nmonths.get(r["period"], 0) == 12]


def _bec(df, flow, base) -> list[dict]:
    rows = []
    hi = next(i for i in range(8) if any(str(c).strip().lower() == "period" for c in df.iloc[i]))
    pcols = {}
    for j, v in enumerate(df.iloc[hi]):
        m = re.match(r"^([a-z]+)\s+(\d{4})", str(v).strip().lower())
        if m and m.group(1) in _MONTHS:
            pcols[j] = f"{m.group(2)}-{_MONTHS.index(m.group(1)) + 1:02d}"
    sec = None
    for i in range(hi + 2, len(df)):
        code0, lab = df.iat[i, 0], df.iat[i, 1]
        if not isinstance(lab, str) or not lab.strip():
            continue
        lab = " ".join(lab.split())
        if lab.lower().startswith("total"):
            continue
        m = re.match(r"^(\d{1,3})\s*:", lab)
        if m:
            code = m.group(1)
        elif _num(code0) is not None:
            code = str(int(_num(code0)))
        else:
            continue
        for j, per in pcols.items():
            v = _num(df.iat[i, j])
            if v is None or v < 0:
                continue
            rows.append(row(tradeflow=flow, period=per, frequency="monthly", value=v, unit="USD",
                            commodity=lab, commodity_classification="bec", commodity_code_nso=code,
                            price_basis="cif" if flow == "import" else "fob", series_code=f"{base}: BEC"))
    return rows


def _dots(df, flow, base) -> list[dict]:
    rows = []
    hi = next(i for i in range(8) if str(df.iat[i, 0]).strip().lower() in ("destination", "source country",
                                                                          "country", "source"))
    pcols = {}
    for j, v in enumerate(df.iloc[hi]):
        m = re.match(r"^([a-z]+)\s+(\d{4})", str(v).strip().lower())
        if m and m.group(1) in _MONTHS:
            pcols[j] = f"{m.group(2)}-{_MONTHS.index(m.group(1)) + 1:02d}"
    for i in range(hi + 1, len(df)):
        name = df.iat[i, 0]
        if not isinstance(name, str) or not name.strip():
            continue
        name = " ".join(name.split())
        kw = {} if name.lower() in ("total", "world", "grand total") else dict(
            partner=name, partner_type="group" if name.lower() in ("others", "other", "unknown") else "country")
        for j, per in pcols.items():
            v = _num(df.iat[i, j])
            if v is None or v < 0:
                continue
            rows.append(row(tradeflow=flow, period=per, frequency="monthly", value=v, unit="USD",
                            price_basis="cif" if flow == "import" else "fob", series_code=f"{base}: DOTS", **kw))
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    paths = sorted(set([path] + [p for p in (extras or []) if p.lower().endswith((".xls", ".xlsx"))]))
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for p in paths:
            base = os.path.basename(p)
            xl = pd.ExcelFile(p)
            for sh in xl.sheet_names:
                s = sh.lower()
                df = xl.parse(sh, header=None)
                if s.startswith("table 2.1"):
                    rows += _table21(df, base)
                elif "bec_imports" in s.replace(" ", "_"):
                    rows += _bec(df, "import", base)
                elif "bec_exports" in s.replace(" ", "_"):
                    rows += _bec(df, "export", base)
                elif s == "exp earnings by destination":
                    rows += _dots(df, "domestic_export", base)
                elif s == "imp by source country":
                    rows += _dots(df, "import", base)
            xl.close()
    if not rows:
        raise ValueError("malawi_nso: no rows decoded")
    df = pd.DataFrame.from_records(rows)
    key = ["tradeflow", "commodity", "commodity_code_nso", "partner", "frequency", "period", "unit"]
    return df.drop_duplicates(key, keep="last").reset_index(drop=True)
