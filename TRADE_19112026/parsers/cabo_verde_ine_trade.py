"""Parser for INE Cabo Verde annual merchandise-trade workbooks ("Principais Quadros").

INE posts, under theme 37 "Comércio Externo" of its publication API
(bdmi.ine.cv/site_deploy_api/api/Publication?codeTheme=37, dissemination type
10 = Principais Quadros), one or more workbooks per year (.xls / .xlsx) whose
sheets are "Quadro n: <title>, <year>". Read, by title (values in thousand
escudos "( Mil ecv )", net weight in tons as printed):

  "... segundo as Secções e Capítulos do Sistema Harmonizado"  exports /
      imports by HS section (classification "national", code = the roman
      numeral printed after "Secção") and HS chapter (hs2); "Total Geral" =
      all products.
  "... por países de destino / pais de origem segundo as secções"  the
      country rows (each country's total line, the one without a section) =
      exports / imports by partner; "Total Geral" = all partners.
  "Reexportação de mercadorias por secção ..."  re-exports by section rows
      (the HS10 lines beneath are not read) and the total.
Not read: HS10 detail tables, the country x HS10 / country x section matrix
lines, BEC tables. The price basis is taken from each table's own value
header ("Valor FOB" / "Valor CIF"). Across workbooks the newest upload (the
timestamp INE puts in the stored file name) wins for a key.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ._common import row
from ..schema import KEY


def _t(c):
    return re.sub(r"\s+", " ", str(c)).strip() if c is not None and not (isinstance(c, float) and pd.isna(c)) else ""


def _n(c):
    if c is None or isinstance(c, str) or pd.isna(c):
        return None
    return float(c)


def _sheet(df, sc):
    title = next((_t(c) for c in df.iloc[:8, 0] if _t(c) and "mercadorias" in _t(c).lower()), "")
    m = re.search(r"(20\d{2})\s*$", title) or re.search(r",\s*(20\d{2})", title)
    if not m:
        return []
    year, tl = m.group(1), title.lower()
    if tl.lstrip().startswith(("quadro", "reexporta")) is False and "reexporta" not in tl:
        pass
    flow = ("re_export" if "reexporta" in tl else "export" if "exporta" in tl
            else "import" if "importa" in tl else None)
    if flow is None:
        return []
    if "secções e capítulos" in tl or "secções e capitulos" in tl:
        kind = "sections"
    elif ("países" in tl or "pais de" in tl) and "secç" in tl:
        kind = "partners"
    elif flow == "re_export" and "por secção" in tl:
        kind = "re_sections"
    else:
        return []
    # value / weight columns and price basis from the header rows
    hdr = " ".join(_t(c) for c in df.iloc[:8].values.ravel())
    basis = "fob" if "valor fob" in hdr.lower() else "cif" if "valor cif" in hdr.lower() else ""
    if "mil ecv" not in hdr.lower():
        return []
    out = []
    tab = f"{sc}:{_t(df.iloc[:8, 0].dropna().iloc[0])[:9]}"
    for r in df.itertuples(index=False):
        c0, c1 = _t(r[0]), _t(r[1])
        v, w = _n(r[2]), _n(r[3]) if len(r) > 3 else None
        if v is None:
            continue
        base = dict(tradeflow=flow, period=year, frequency="annual", unit_multiplier=1e3,
                    price_basis=basis, series_code=tab)
        key = None
        if c0.lower() == "total geral":
            key = {}
        elif kind in ("sections", "re_sections") and re.match(r"^Secção\s+([IVXL]+)$", c0):
            key = dict(commodity=c1, commodity_classification="national",
                       commodity_code_nso=c0.split()[-1])
        elif kind == "sections" and re.fullmatch(r"\d{2}", c0):
            key = dict(commodity=c1, commodity_classification="hs2", commodity_code_nso=c0)
        elif kind == "partners" and c0 and not c1 and not c0.startswith("Secção") \
                and not re.match(r"^(\(Continua|Países|Pais)", c0):
            key = dict(partner=c0, partner_type="country")
        if key is None:
            continue
        out.append(row(value=v, unit="CVE", **base, **key))
        if w is not None:
            out.append(row(value=w, unit="tonnes", measure="net_weight",
                           **{**base, "unit_multiplier": 1.0}, **key))
    return out


def parse_file(path):
    sc = os.path.basename(path)
    try:
        book = pd.read_excel(path, sheet_name=None, header=None)
    except ValueError:            # INE also stores 10 KB placeholder files
        return []
    out = []
    for df in book.values():
        if df.shape[1] >= 3:
            out += _sheet(df, sc)
    return out


def _stamp(path):
    m = re.search(r"_(\d{8}_\d{6})_", os.path.basename(path))
    return m.group(1) if m else ""


def parse(path, extras=None):
    frames, seen = [], set()
    for f in sorted({path, *(extras or [])}, key=_stamp, reverse=True):
        df = pd.DataFrame(parse_file(f))
        if df.empty:
            continue
        k = df[KEY].astype(str).agg("|".join, axis=1)
        frames.append(df.loc[~k.isin(seen)])
        seen |= set(k)
    return pd.concat(frames, ignore_index=True)
