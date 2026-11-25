"""Parser for Office des Changes (Morocco) "Rapport annuel -- Commerce extérieur du Maroc" (PDF).

The Office des Changes is the OFFICIAL COMPILER of Morocco's foreign-trade
statistics (HCP, the NSO, does not compile them). Each annual report prints
three-year tables in millions of dirhams (MDH), with "." as the thousands
separator ("89.620" = 89 620 MDH):
  T1-1  imports by groupement d'utilisation (product groups + sub-groups + Total)
  T1-2  imports by principal products
  T2-1  exports by product group (+ Total)
  T2-2  exports by principal products
Each row reads: label, three yearly values, share %, change in value, change in
% (6 tokens). A row whose tokens are not exactly that shape -- e.g. a figure
split by a stray space in the PDF ("7 5.624") -- is dropped, never repaired.
The "Total" rows are the all-products imports / exports.
Not read: the partner tables (T4-x: most figures are split by stray spaces in
the text layer), the ATPA regime tables (T3-x), the product-by-partner tables.
"""
from __future__ import annotations

import re

import pandas as pd

from ._common import row

_VAL = re.compile(r"^\d{1,3}(?:\.\d{3})*$")
_SIGNED = re.compile(r"^(?:[+-]?\d{1,3}(?:\.\d{3})*(?:,\d+)?|-)$")
_TABLES = {"T1-1": ("import", "national"), "T1-2": ("import", "national"),
           "T2-1": ("export", "national"), "T2-2": ("export", "national")}


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    import pdfplumber
    from ..schema import KEY
    files = list(dict.fromkeys([*(extras or []), path]))
    frames = []
    for p in files:
        out = []
        with pdfplumber.open(p) as pdf:
            tid, years, seen_total = None, None, False
            # Chapters 1-2 (imports, exports by product) sit on pages ~23-43.
            for page in pdf.pages[18:46]:
                for ln in (page.extract_text() or "").split("\n"):
                    ln = ln.strip()
                    m = re.match(r"^(T\d-\d+)\b", ln)
                    if m:
                        if m.group(1) in _TABLES:
                            tid, seen_total = m.group(1), False
                        elif not (tid in ("T1-1", "T2-1") and seen_total):
                            tid = None
                        years = None
                        continue
                    if tid is None:
                        continue
                    if re.match(r"^Commerce extérieur 20\d\d", ln) or ln.startswith("RAPPORT ANNUEL"):
                        continue
                    ym = re.match(r"^(20\d\d) (20\d\d) (20\d\d)\b", ln)
                    if ym:
                        # T1-2 / T2-2 are often printed with no title line of their
                        # own before the next table's title: a new year header after
                        # a group table's Total starts the principal-products table.
                        if tid in ("T1-1", "T2-1") and seen_total:
                            tid, seen_total = tid[:3] + "2", False
                        years = [ym.group(1), ym.group(2), ym.group(3)]
                        continue
                    if years is None:
                        continue
                    toks = ln.split()
                    nums = []
                    while toks and _SIGNED.match(toks[-1]):
                        nums.insert(0, toks.pop())
                    label = " ".join(toks).strip()
                    if not label or len(nums) != 6 or not all(_VAL.match(t) for t in nums[:3]):
                        continue
                    if re.search(r"\d", label):
                        continue              # a figure split into the label: unreadable
                    flow, cls = _TABLES[tid]
                    if label.lower() == "total":
                        seen_total = True
                    for y, t in zip(years, nums[:3]):
                        v = float(t.replace(".", ""))
                        kw = dict(tradeflow=flow, period=y, frequency="annual", value=v, unit="MAD",
                                  unit_multiplier=1e6, series_code=tid)
                        if label.lower().startswith(("total", "sous total", "autres produits")):
                            if tid in ("T1-1", "T2-1") and label.lower() == "total":
                                out.append(row(**kw))
                        else:
                            out.append(row(**kw, commodity=label, commodity_classification=cls))
        if out:
            df = pd.DataFrame(out)
            frames.append((df["period"].max(), df))
    frames.sort(key=lambda t: t[0])
    df = pd.concat([f for _, f in frames], ignore_index=True)
    return df.drop_duplicates(KEY, keep="last").reset_index(drop=True)
