"""Liberia — LISGIS CPI from the dataset API (site rebuilt 2026).

LISGIS rebuilt lisgis.gov.lr as a single-page app over a JSON API. The page the
old newsletter parser scraped (pricestats.php) now answers 200 with the app's
HTML shell. The API serves the CPI as datasets built from LISGIS's monthly
CPI WORKBOOKS (Liberia_CPI_<Month>_<Year>.xlsx):

* `cpi-division-history` -- PRIMARY: the index for "Total" and the 12 COICOP
  divisions, monthly from 2006-01, base December 2005 = 100;
* `cpi-changes` -- EXTRA: the workbook's own REPORTED monthly and annual
  percentage changes, from 2018-12, for the same codes.

AN UPGRADE AS WELL AS A FIX. The newsletter printed divisions only as bar
charts, so the old output was the all-items series alone, 13 months at a time.
This carries all 12 divisions and twenty years of history.

Rates are the published ones; none is computed from the index. The all-items
code is "0" in the API and "00" here, as before, so the series continues under
the same merge key.

CONTINUITY CHECKED: the API's all-items index agrees with the newsletter's
one-decimal figures for 12 of the 13 months already held; February 2026 reads
815.434 against the newsletter's 815.2 -- a revision, and the merge takes the
current value.
"""
from __future__ import annotations

import json

import pandas as pd

BASE = "Dec 2005 = 100"
_KIND = {"monthly": "inflation_mom", "annual": "inflation_yoy"}


def _load(path: str, want: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("id") != want:
        raise ValueError(f"{path}: expected dataset {want!r}, got {doc.get('id')!r}")
    return doc


def _code(c: str) -> str:
    return "00" if str(c) == "0" else str(c).zfill(2)


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    hist = _load(local_path, "cpi-division-history")
    rows = pd.DataFrame(hist["rows"])
    codes = sorted(rows.coicop_code.unique())
    if codes != ["0"] + [f"{i:02d}" for i in range(1, 13)]:
        raise ValueError(f"unexpected CPI codes {codes}")
    labels = {_code(c): ("All items" if c == "0" else n)
              for c, n in zip(rows.coicop_code, rows.coicop_name)}
    # Continuity with the newsletter's base: the index starts just above 100
    # in January 2006 (Dec 2005 = 100).
    jan06 = rows[(rows.coicop_code == "0") & (rows.period == "2006-01")].index_value
    if jan06.empty or not 99 < float(jan06.iloc[0]) < 102:
        raise ValueError("all-items index is not on the Dec 2005 = 100 base")

    recs = [(_code(r.coicop_code), labels[_code(r.coicop_code)], r.period,
             "index", float(r.index_value), "Index", BASE)
            for r in rows.itertuples() if r.index_value is not None]

    for path in extras or []:
        chg = pd.DataFrame(_load(path, "cpi-changes")["rows"])
        chg = chg[chg.coicop_code.isin(rows.coicop_code.unique())
                  & chg.change_type.isin(_KIND) & chg.change_percent.notna()]
        # The same change can be listed twice (with and without a hierarchy
        # level); identical duplicates collapse, conflicting ones raise.
        chg = chg.drop_duplicates(["period", "coicop_code", "change_type",
                                   "change_percent"])
        dup = chg.duplicated(["period", "coicop_code", "change_type"], keep=False)
        if dup.any():
            raise ValueError(f"conflicting published changes: "
                             f"{chg[dup].head(4).to_dict('records')}")
        recs += [(_code(r.coicop_code), labels[_code(r.coicop_code)], r.period,
                  _KIND[r.change_type], float(r.change_percent), "percent", "")
                 for r in chg.itertuples()]

    out = pd.DataFrame.from_records(
        recs, columns=["coicop_code", "coicop_label", "period", "measure",
                       "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
