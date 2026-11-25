"""Parser for Statistics Sierra Leone "Foreign Trade Statistics Bulletin" PDFs (annual).

Stats SL compiles merchandise trade from NRA-Customs (ASYCUDA) records. Two
bulletins with a text layer are read (values in million (old) leones, ISO SLL, as captioned;
net weight in metric tons):

  Bulletin 2011 (May 2012), statistical annex, 2000-2011 annual:
    Table 5  total exports / total imports, customs value + net weight.
    Table 2  major domestic exports by product (diamonds ... others),
             domestic exports, re-exports, total exports -- CUSTOMVAL rows
             only, and only rows printing all 16 cells ("-" holds a place).
    Table 3/4 imports by country of origin, ECOWAS / European Union -- rows
             printing all 12 year cells.
    Table 1 (imports by SITC) is NOT read: its column headers are garbled in
    the text layer and the order cannot be told from it.
  Bulletin 2013 (Nov 2014), 2011-2013 annual:
    Table 3.1 imports by SITC section (row numbers are list positions, not
             SITC codes -> code blank); its Total = all-products imports.
    Table 3.2 / 3.3 imports / exports with each ECOWAS country.
    Table 3.2.1 exports of major domestic products (national list; the
             "Total" of that list is not total exports and is not read).
    Table 3.2.2 imports by region (groups).
    Table 6.x imports by country of origin (value + net mass pairs).
  Each row's first value cells are read; growth and share columns that
  follow are ignored. The 2013 bulletin revises 2011 (imports 14,985,853 vs
  41,520,048 in the 2011 bulletin): the newer bulletin wins for a key.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

from ._common import row
from ..schema import KEY

_TOK = re.compile(r"^(-?\d{1,3}(,\d{3})+(\.\d+)?|-?\d+(\.\d+)?|[-‐‑‒–]|NA)$")


def _num(tok):
    if tok in ("-", "NA") or re.fullmatch(r"[‐-–]", tok):
        return None
    return float(tok.replace(",", ""))


def _split(line, n):
    """(label, first n value tokens) for a line ending in value tokens; else None."""
    toks = line.split()
    k = len(toks)
    while k > 0 and _TOK.match(toks[k - 1]):
        k -= 1
    vals = toks[k:]
    if len(vals) < n or k == 0:
        return None
    return " ".join(toks[:k]), vals[:n]


def _clean(label):
    return re.sub(r"^(\d+(\.\d+)?\)?\s+)", "", label).strip()


def _page_text(pdf, rx):
    for pg in pdf.pages:
        t = pg.extract_text() or ""
        if re.search(rx, t, re.I):
            yield t


def _year(tok):
    m = re.fullmatch(r"((?:19|20)\d{2})[PR]?", tok)
    return m.group(1) if m else None


def _b2011(pdf, sc):
    out = []
    for t in _page_text(pdf, r"Table 5: Total Imports and Exports"):
        if "million leones" not in t.lower():
            continue
        for line in t.splitlines():
            toks = line.split()
            if len(toks) == 5 and _year(toks[0]) and all(_TOK.match(x) for x in toks[1:]):
                y = _year(toks[0])
                for fl, tok, meas in (("export", toks[1], "value"), ("export", toks[2], "net_weight"),
                                      ("import", toks[3], "value"), ("import", toks[4], "net_weight")):
                    v = _num(tok)
                    if v is not None:
                        out.append(row(tradeflow=fl, period=y, frequency="annual", value=v,
                                       unit="SLL" if meas == "value" else "tonnes",
                                       unit_multiplier=1e6 if meas == "value" else 1, measure=meas,
                                       series_code=f"{sc}:Table 5"))
    prods = ["Diamonds", "Bauxite", "Rutile", "Gold", "Ilmenite", "Iron Ore", "Zircon", "Coffee", "Cocoa",
             "Piassava", "Fish and Shrimps", "Tobacco", "Others"]
    for t in _page_text(pdf, r"Table 2:\s+Major Domestic Exports Value"):
        if "list of tables" in t.lower():
            continue
        for line in t.splitlines():
            toks = line.split()
            if len(toks) != 18 or not _year(toks[0]) or toks[1] != "CUSTOMVAL":
                continue
            if not all(_TOK.match(x) for x in toks[2:]):
                continue
            y, vals = _year(toks[0]), toks[2:]
            for lab, tok in zip(prods, vals[:13]):
                v = _num(tok)
                if v is not None:
                    out.append(row(tradeflow="domestic_export", period=y, frequency="annual", value=v,
                                   unit="SLL", unit_multiplier=1e6, commodity=lab,
                                   commodity_classification="national", series_code=f"{sc}:Table 2"))
            for fl, tok in (("domestic_export", vals[13]), ("re_export", vals[14]), ("export", vals[15])):
                v = _num(tok)
                if v is not None:
                    out.append(row(tradeflow=fl, period=y, frequency="annual", value=v, unit="SLL",
                                   unit_multiplier=1e6, series_code=f"{sc}:Table 2"))
        break
    for rx, tab in ((r"Table 3: Imports Value \(Million Leones\) by Country of Origin: ECOWAS", "Table 3"),
                    (r"Table 4: Imports Value \(Million Leones\) by Country of origin: European", "Table 4")):
        for t in _page_text(pdf, rx):
            lines = t.splitlines()
            start = next((i for i, l in enumerate(lines) if re.search(rx, l, re.I)), None)
            if start is None or "list of tables" in t.lower():
                continue
            years = None
            for line in lines[start + 1:]:
                if line.startswith("Source") or (years and line.startswith("Table")):
                    break
                ys = [_year(x) for x in line.split()]
                if years is None and sum(1 for y in ys if y) >= 10:
                    years = [y for y in ys if y]
                    continue
                if not years:
                    continue
                got = _split(line, len(years))
                if not got or len(line.split()) - len(got[0].split()) != len(years):
                    continue
                for y, tok in zip(years, got[1]):
                    v = _num(tok)
                    if v is not None:
                        out.append(row(tradeflow="import", period=y, frequency="annual", value=v, unit="SLL",
                                       unit_multiplier=1e6, partner=got[0], partner_type="country",
                                       series_code=f"{sc}:{tab}"))
    return out


def _b2013(pdf, sc):
    out = []
    years = ["2011", "2012", "2013"]

    def block(rx, emit, stop=r"^(Data Source|Source)"):
        for t in _page_text(pdf, rx):
            lines = t.splitlines()
            i0 = next((i for i, l in enumerate(lines) if re.search(rx, l, re.I)), None)
            if i0 is None:
                continue
            for line in lines[i0 + 1:]:
                if re.search(stop, line):
                    break
                got = _split(line, 3)
                if got:
                    emit(got[0], got[1])

    def put(fl, lab_kw, vals, tab, **kw):
        for y, tok in zip(years, vals):
            v = _num(tok)
            if v is not None:
                out.append(row(tradeflow=fl, period=y, frequency="annual", value=v, unit="SLL",
                               unit_multiplier=1e6, series_code=f"{sc}:{tab}", **lab_kw, **kw))

    def sitc(label, vals):
        if label.strip().lower() == "total":
            put("import", {}, vals, "Table 3.1")
        elif re.match(r"^\d+\s", label):
            put("import", dict(commodity=_clean(label), commodity_classification="sitc1"), vals, "Table 3.1")
    block(r"^Table 3.1: Import Value \(Million Leones\) by SITC", sitc)

    def ecow(fl, tab):
        def f(label, vals):
            if re.match(r"^\d+\s", label):
                put(fl, dict(partner=_clean(label), partner_type="country"), vals, tab)
        return f
    block(r"^Table 3.2: Import Value \(Million Leones\) by country of origin: ECOWAS", ecow("import", "Table 3.2"))
    block(r"^Table 3.3: Export Value \(Million Leones\) by country of destination: ECOWAS", ecow("export", "Table 3.3"))

    def prod(label, vals):
        if re.match(r"^\d+(\.\d+|\))\s", label):
            put("domestic_export", dict(commodity=_clean(label), commodity_classification="national"),
                vals, "Table 3.2.1")
    block(r"^Table 3.2.1: Export Value for Major Domestic products", prod)

    def region(label, vals):
        if re.match(r"^\d+(\.\d+|\))\s", label):
            put("import", dict(partner=_clean(label), partner_type="group"), vals, "Table 3.2.2")
    block(r"^Table 3.2.2: Import value by region", region)

    # Table 6.x: value / net-mass pairs per year
    for t in _page_text(pdf, r"Table 6\.\d"):
        m = re.search(r"Table (6\.\d)", t)
        tab = f"Table {m.group(1)}"
        for line in t.splitlines():
            got = _split(line, 6)
            if not got or len(line.split()) - len(got[0].split()) != 6 or not got[0].isupper():
                continue
            vals = got[1]
            for k, y in enumerate(years):
                for tok, meas in ((vals[2 * k], "value"), (vals[2 * k + 1], "net_weight")):
                    v = _num(tok)
                    if v is not None:
                        out.append(row(tradeflow="import", period=y, frequency="annual", value=v,
                                       unit="SLL" if meas == "value" else "tonnes",
                                       unit_multiplier=1e6 if meas == "value" else 1, measure=meas,
                                       partner=re.sub(r"^[A-Z]{2}:", "", got[0]).strip(),
                                       partner_type="country", series_code=f"{sc}:{tab}"))
    return out


def parse_file(path):
    base = os.path.basename(path)
    sc = os.path.splitext(base)[0]
    with pdfplumber.open(path) as pdf:
        if "2011" in base:
            return _b2011(pdf, sc)
        if "2013" in base and "bulletin" in base:
            return _b2013(pdf, sc)
    raise ValueError(f"sierra_leone_statssl_trade: unknown file {base}")


def _order(path):
    m = re.search(r"(20\d{2})", os.path.basename(path))
    return int(m.group(1)) if m else 0


def parse(path, extras=None):
    """Newest bulletin first; an older bulletin contributes only keys the newer
    ones do not print (within one bulletin, repeats are left to the validator)."""
    frames, seen = [], set()
    for f in sorted({path, *(extras or [])}, key=_order, reverse=True):
        df = pd.DataFrame(parse_file(f))
        k = df[KEY].astype(str).agg("|".join, axis=1)
        frames.append(df.loc[~k.isin(seen)])
        seen |= set(k)
    return pd.concat(frames, ignore_index=True)
