"""Tunisia -- INS "Indice des prix de vente industriels" (IPVI), base 2010 = 100.

INS's producer price index ("prix de vente industriels": prices at which
industrial producers sell), monthly, base 2010, by branch of the Nomenclature
des Activités et des Produits 1986 (Ensemble, Industrie manufacturière and its
sectors and branches, Mines, Energie). Sources, all on ins.tn:

  `statistiques/89` page (HTML)   the latest 9 months by sector + the annual
                                  indices 2016 - latest year (two tables)
  "IPVI-Diff_<mois>_<année>.xls"  the full monthly series by branch since
                                  January 2015, with the branch weights
                                  ("Poids", base-2010 weights), attached to the
                                  2017-2018 notes (the June 2018 one runs to
                                  June 2018)
  "IPVI DIFFDEFAv2020.xls"        the 2019 months, final ("définitifs"), by
                                  branch with INS's NAT02 codes
  monthly notes (PDF, 2017-2019)  the table "Mois | Niveau Evolution Glissement
                                  Cumul" of the ENSEMBLE for the current and the
                                  previous year -- read for its level, m/m and
                                  y/y (cumulative change has no measure here)

A total printed as "ENSEMBLE" / "INDICE ENSEMBLE" / "Indice d'ensemble", and
labels differing only in case or accents, are one series under the label the
statistics page prints. Workbooks and notes are read oldest first; the newer
document wins for a month both print.

GAP: monthly July 2019 .. September 2025 is not on ins.tn (the site lists IPVI
notes only for March 2017 - March 2019); those years are covered by the annual
indices.

CROSS-CHECK (verbatim): June 2026 Indice d'ensemble 218.5, Chimie 276.0;
annual 2024 (page); Jan 2015 manufacturing 117.2, weight 84.8; June 2018
manufacturing 137.630746; Dec 2019 ensemble 149.264444; March 2019 note
ENSEMBLE 146,8, m/m 0,1, y/y 8,5, March 2018 level 135,3.
"""
from __future__ import annotations

import io
import os
import re
import unicodedata

import pandas as pd

from . import _common as C

INDEX_NAME = "Indice des prix de vente industriels (IPVI)"
BASE = "2010 = 100"


def _num(v):
    """_common.to_number, with a pandas NaN cell treated as empty."""
    v = C.to_number(v)
    return None if v is None or v != v else v


def _fold(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


_TOTAL = {"ensemble", "indiceensemble", "indicedensemble"}


def parse_page(path) -> list[dict]:
    html = open(path, encoding="utf-8", errors="replace").read()
    out = []
    for t in pd.read_html(io.StringIO(html)):
        cols = list(t.columns)
        label_col = cols[0]
        for c in cols[1:]:
            sc = str(c).strip()
            if re.fullmatch(r"(19|20)\d{2}", sc):
                per, fq = sc, "annual"
            else:
                per, fq = C.month_period(sc), "monthly"
            if not per:
                continue
            for lab, v in zip(t[label_col], t[c]):
                v = _num(v)
                if v is None or not isinstance(lab, str) or not lab.strip():
                    continue
                out.append(C.row(index_name=INDEX_NAME, industry=lab.strip(), period=per, frequency=fq,
                                 measure="index", value=v, base_period=BASE))
    return out


def parse_workbook(path) -> list[dict]:
    out = []
    x = pd.read_excel(path, sheet_name=None, header=None)
    sheet = "Fr01" if "Fr01" in x else next(iter(x))
    v = x[sheet]
    hr = next(i for i in range(min(10, len(v)))
              if sum(C.month_period(str(c)) is not None or hasattr(c, "year") for c in v.iloc[i]) >= 3)
    hdr = list(v.iloc[hr])
    pcol = {}
    for j, c in enumerate(hdr):
        p = f"{c.year:04d}-{c.month:02d}" if hasattr(c, "year") else C.month_period(str(c))
        if p:
            pcol[j] = p
    wcol = next((j for j, c in enumerate(hdr) if str(c).strip().lower() == "poids"), None)
    lcol = next((j for j, c in enumerate(hdr) if str(c).strip().upper() == "LIB"), 0)
    ccol = 0 if lcol == 1 else None                       # NAT02 code beside the label
    for i in range(hr + 1, len(v)):
        lab = v.iat[i, lcol]
        if not isinstance(lab, str) or not lab.strip():
            continue
        code = str(v.iat[i, ccol]).strip() if ccol is not None and isinstance(v.iat[i, ccol], str) else ""
        kw = dict(index_name=INDEX_NAME, industry=lab.strip(), base_period=BASE, series_code=code)
        if wcol is not None:
            w = _num(v.iat[i, wcol])
            if w is not None:
                out.append(C.row(period="2010", frequency="annual", measure="weight", value=w,
                                 unit="percent", **kw))
        for j, per in pcol.items():
            val = _num(v.iat[i, j])
            if val is not None:
                out.append(C.row(period=per, frequency="monthly", measure="index", value=val, **kw))
    return out


def parse_note(path) -> list[dict]:
    """ENSEMBLE history table: per month, (previous year) Cumul Glissement
    Evolution Niveau, (current year) Cumul Glissement Evolution Niveau, Mois
    -- the order the text layer gives this right-to-left table, proved by
    Niveau(current) / Niveau(previous) = Glissement on every complete row."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        text = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    m = re.search(r"Indice des prix de vente industriels\s+((?:19|20)\d{2})\s*$", text, re.M)
    hy = re.search(r"^((?:19|20)\d{2})\s+((?:19|20)\d{2})\s*$", text, re.M)
    if not hy:
        return []
    y0, y1 = int(hy.group(1)), int(hy.group(2))
    out = []
    num = r"-?\d+,\d+"
    for l in text.splitlines():
        l = l.strip()
        full = re.fullmatch(rf"({num}) ({num}) ({num}) ({num}) ({num}) ({num}) ({num}) ({num}) (\d{{1,2}})", l)
        half = re.fullmatch(rf"({num}) ({num}) ({num}) ({num}) (\d{{1,2}})", l)
        rows = []
        if full:
            g = [C.to_number(x, decimal=",") for x in full.groups()[:8]]
            mo = int(full.group(9))
            if not (abs((g[7] / g[3] - 1) * 100 - g[5]) <= 0.2):
                raise ValueError(f"{os.path.basename(path)}: month {mo}: column order does not hold")
            rows = [(y0, mo, g[3], g[2], g[1]), (y1, mo, g[7], g[6], g[5])]
        elif half:
            g = [C.to_number(x, decimal=",") for x in half.groups()[:4]]
            rows = [(y0, int(half.group(5)), g[3], g[2], g[1])]
        for y, mo, lvl, mom, yoy in rows:
            if not 1 <= mo <= 12:
                continue
            per = f"{y:04d}-{mo:02d}"
            kw = dict(index_name=INDEX_NAME, industry="ENSEMBLE", base_period=BASE, period=per,
                      frequency="monthly")
            out.append(C.row(measure="index", value=lvl, **kw))
            out.append(C.row(measure="inflation_mom", value=mom, **kw))
            out.append(C.row(measure="inflation_yoy", value=yoy, **kw))
    return out


def _order(p):
    b = os.path.basename(p).lower()
    m = re.search(r"(20\d{2})", b)
    mon = re.search(r"(janv|fev|mars|avril|mai|juin|juil|aout|sept|oct|nov|dec)", b)
    order = ["janv", "fev", "mars", "avril", "mai", "juin", "juil", "aout", "sept", "oct", "nov", "dec"]
    return (int(m.group(1)) if m else 2017, order.index(mon.group(1)) if mon else 0, b)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = [f for f in {*(extras or [])} if f != path]
    out = {}
    def put(rows):
        for r in rows:
            out[(_fold(r["industry"]), r["period"], r["frequency"], r["measure"])] = r
    for f in sorted([f for f in files if f.lower().endswith(".pdf")], key=_order):
        put(parse_note(f))
    for f in sorted([f for f in files if f.lower().endswith(".xls")], key=_order):
        put(parse_workbook(f))
    page = parse_page(path)
    put(page)
    # one label per series: the statistics page's, else the newest document's
    names = {}
    for r in out.values():
        names.setdefault(_fold(r["industry"]), r["industry"])
    for r in page:
        names[_fold(r["industry"])] = r["industry"]
    total = next((r["industry"] for r in page if _fold(r["industry"]) in _TOTAL), "Indice d'ensemble")
    rows = []
    seen = {}
    for (k, per, fq, meas), r in out.items():
        kk = "__T" if k in _TOTAL else k
        r["industry"] = total if kk == "__T" else names[k]
        seen[(kk, per, fq, meas)] = r
    if not seen:
        raise ValueError("tunisia_ins_ppi: no rows")
    return pd.DataFrame(list(seen.values()))
