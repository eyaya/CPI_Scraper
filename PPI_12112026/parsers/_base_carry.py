"""A % change carries the base of the index it is computed from (schema
convention, 2026-11-08). Parsers written before the convention emitted change
rows with a blank base_period; `carry_base` fills it from the SAME parse
output, and only where the answer is unambiguous:

  1. the index rows of the same index / industry / frequency at the change's
     own period carry exactly one base -> that base;
  2. else the index rows of that index / frequency carry exactly one base in
     the whole output (one bulletin, one base) -> that base; else the same at
     any frequency (Djibouti's annual-average change beside quarterly levels);
  3. else (an output spanning a rebase) a y/y change takes the one base whose
     own levels a year apart reproduce it (0.05 pt + rounding) -- never a guess
     between two bases that both fit;
  otherwise the base stays blank.

Nothing else is touched: values, periods and every other column stay as
parsed. Use as `parse = carry_base(parse)` at the end of a module.
"""
from __future__ import annotations

import functools

import pandas as pd

from ..schema import _lag


def fill_change_base(df) -> pd.DataFrame:
    df = pd.DataFrame(df)
    if df.empty or "base_period" not in df or "measure" not in df:
        return df
    bp = df["base_period"].fillna("").astype(str)
    blank = df["measure"].astype(str).str.startswith("inflation") & (bp == "")
    if not blank.any():
        return df
    for c in ("index_variant", "industry"):
        if c not in df:
            df[c] = ""
    lv = df[(df["measure"] == "index") & (bp != "")]
    exact, whole, anyfreq, level = {}, {}, {}, {}
    for r in lv.itertuples(index=False):
        k = (r.index_name, r.index_variant, r.frequency)
        exact.setdefault(k + (r.industry, r.period), set()).add(r.base_period)
        whole.setdefault(k, set()).add(r.base_period)
        anyfreq.setdefault((r.index_name, r.index_variant), set()).add(r.base_period)
        level[k + (r.industry, r.period, r.base_period)] = float(r.value)
    lag = {"monthly": 12, "quarterly": 4, "annual": 1}
    for i in df.index[blank]:
        r = df.loc[i]
        k = (r["index_name"], r["index_variant"], r["frequency"])
        cand = exact.get(k + (r["industry"], r["period"]), set())
        if len(cand) != 1:
            cand = whole.get(k, set()) if len(whole.get(k, set())) == 1 else set()
        if not cand and k not in whole:
            af = anyfreq.get(k[:2], set())
            cand = af if len(af) == 1 else set()
        if not cand and r["measure"] == "inflation_yoy" and r["frequency"] in lag:
            then = _lag(str(r["period"]), r["frequency"], lag[r["frequency"]])
            fits = set()
            for b in whole.get(k, set()):
                now = level.get(k + (r["industry"], r["period"], b))
                was = level.get(k + (r["industry"], then, b))
                if now and was and abs((now / was - 1) * 100 - float(r["value"])) <= 0.05 + 0.005 * abs(float(r["value"])):
                    fits.add(b)
            cand = fits if len(fits) == 1 else set()
        if len(cand) == 1:
            df.at[i, "base_period"] = next(iter(cand))
    return df


def carry_base(fn):
    @functools.wraps(fn)
    def wrapped(*a, **k):
        return fill_change_base(fn(*a, **k))
    return wrapped
