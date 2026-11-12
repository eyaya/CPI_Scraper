"""South Africa -- Stats SA P0142.1 Producer Price Index time-series archives.

Stats SA's "timeseriesdata/Excel" zips, one per edition. Every member holds
one row per series in Stats SA's time-series layout:

    H01 P0142.1 | H02 Producer price index | H03 series code (PPC30000) |
    H04 index title | H05 product / industry | H17 Index | H18 base |
    H25 Monthly | MO012012 MO022012 ... (one column per month, MOmmYYYY)

Members are .xlsx (current editions) or the SAS "HTML saved as .xls" files of
the older editions (read with pandas.read_html). The parser reads EVERY member
of the archive (`unzip: false`), so a discontinued archive split by decade
(1970-79, 1980-89, 1990-99, 2000-12) comes through whole.

Index titles (H04) -> index_variant:
  PPI for final manufactured goods            final_goods
  PPI for intermediate manufactured goods     intermediate_goods
  PPI for electricity and water / for mining  output
  PPI for agriculture, forestry and fishing   agriculture
  Analytical series                           by H05 (final / intermediate / mining -> output)
  (to 2012) PPI for domestic output of South African industry groups   output
  (to 2012) Output of SA Industry groups - for SA consumption          domestic_market
  (to 2012) PPI for exported commodities according to groups           export
  (to 2012) PPI for imported commodities according to groups           import
  (to 2012) Commodities for South African consumption -- the HEADLINE PPI
      before 2012 (domestic output + imports for local consumption). Its kind
      is not in the schema's INDEX_VARIANTS yet; it is collected the moment a
      "domestic_consumption" variant exists, and skipped until then.
  (to 2012) PPI for selected materials / materials used in certain
      industries -- INPUT price indices, not producer output prices: skipped.

Values are taken as printed; nothing is rebased. A 0.0 cell is read as not
published (666 of them in the to-2012 archive, all in series that were not
compiled for those months). Each edition re-references
the whole history to its own base (2012=100, Dec 2016=100, Dec 2020=100,
Dec 2023=100), and base_period is in the merge key, so every edition's series
is kept beside the others.
"""
from __future__ import annotations

import io
import re
import zipfile

import pandas as pd

from . import _common as C
from ..schema import INDEX_VARIANTS

_MONTH = re.compile(r"^MO(\d{2})(\d{4})$")
_SKIP = ("selected materials", "materials used in certain industries")


def _variant(title: str, product: str) -> str | None:
    t, p = title.lower(), product.lower()
    if any(s in t for s in _SKIP):
        return None
    if t.startswith("commodities for south african consumption"):
        return "domestic_consumption" if "domestic_consumption" in INDEX_VARIANTS else None
    if "final manufactured" in t:
        return "final_goods"
    if "intermediate manufactured" in t:
        return "intermediate_goods"
    if "agriculture, forestry and fishing" in t:
        return "agriculture"
    if "electricity and water" in t or t == "ppi for mining":
        return "output"
    if "for sa consumption" in t:
        return "domestic_market"
    if "exported commodities" in t:
        return "export"
    if "imported commodities" in t:
        return "import"
    if "domestic output" in t:
        return "output"
    if t == "analytical series":
        if "final manufactured" in p:
            return "final_goods"
        if "intermediate manufactured" in p:
            return "intermediate_goods"
        if "mining" in p or "precious metals" in p:
            return "output"
    raise ValueError(f"unmapped Stats SA PPI index {title!r} / {product!r}")


def _frames(path: str):
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith("/"):
                continue
            b = z.read(name)
            if b[:2] == b"PK":                      # a real .xlsx
                yield name, pd.read_excel(io.BytesIO(b), dtype=object)
            elif b.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
                yield name, pd.read_html(io.BytesIO(b), encoding="windows-1252", thousands=None)[0]
            else:
                raise ValueError(f"{name}: neither xlsx nor SAS HTML")


def parse(path: str) -> pd.DataFrame:
    out = []
    for name, df in _frames(path):
        need = {"H03", "H04", "H05", "H17", "H18", "H25"}
        if need - set(df.columns):
            raise ValueError(f"{name}: layout changed, columns {list(df.columns)[:10]}")
        months = [(c, f"{m.group(2)}-{m.group(1)}") for c in df.columns
                  for m in [_MONTH.match(str(c))] if m]
        if not months:
            raise ValueError(f"{name}: no MOmmYYYY columns")
        for _, r in df.iterrows():
            title, product = str(r["H04"]).strip(), str(r["H05"]).strip().rstrip("'")
            if str(r["H17"]).strip().lower() != "index" or str(r["H25"]).strip().lower() != "monthly":
                raise ValueError(f"{name}: unexpected {r['H17']!r}/{r['H25']!r} for {product!r}")
            var = _variant(title, product)
            if var is None:
                continue
            for col, period in months:
                v = None if pd.isna(r[col]) else C.to_number(r[col])   # to_number passes NaN floats through
                # 0.0 fills months a discontinued series did not publish
                # (exported sugar cane 1999-2007, rubber and plastics 1970-73):
                # an index level of 0 is not a price, so the cell is empty.
                if v is None or v == 0:
                    continue
                out.append(C.row(index_name=title, index_variant=var, industry=product,
                                 industry_code_nso=str(r["H03"]).strip(), period=period,
                                 frequency="monthly", measure="index", value=v,
                                 base_period=str(r["H18"]).strip(),
                                 series_code=str(r["H03"]).strip()))
    if not out:
        raise ValueError(f"no rows read from {path}")
    df = pd.DataFrame(out)
    dup = df.duplicated(["index_name", "industry", "base_period", "period"]).sum()
    if dup:
        raise ValueError(f"{dup} duplicate index/industry/month rows -- two series share a label")
    return df
