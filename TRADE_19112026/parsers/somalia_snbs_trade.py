"""Parsers for Somalia SNBS merchandise trade (Tier 3 PDF).

SNBS publishes the Central Bank of Somalia's merchandise trade summaries (the
CBS compiles them from port/customs records; SNBS republishes them, so the
reports on nbs.gov.so are collected):

parse_qsb(path)       Quarterly Statistical Bulletin (2021 Q1-Q4, 2023 Q1 -
    2024 Q4). Table 2 "Summary of exports" (Livestock, Livestock Product
    (Meat), Fishery Export, Animal Skins, Crops & Vegetable Oil, Forest
    Products, Other + Total) and Table 3 "Summary of Imports" (14 categories,
    "Of which khat", Total), US dollars (cents printed), for the bulletin's
    quarter and the same quarter a year earlier. The quarter is the bulletin's
    own (file name / caption): some column headers are wrong ("2024 Q1" in the
    Q4-2024 bulletin, whose caption and text say October-December). The
    current-year column is the left one in every issue (checked against the
    printed growth rates).
    PDF cells are scattered (labels and figures on different text lines), so
    each figure is assigned to its column by x position and to its row by
    order; the row labels are matched in their fixed order. The table is
    emitted only if the number of figures in each column equals the number of
    rows found AND the categories (excluding "Of which khat") add up to the
    printed Total within 0.5 % in both columns -- a check, nothing is derived.

parse_abstract(path)  Statistical Abstract 2024, Tables 3.8 (imports) and 3.9
    (exports), "Summary of Import/Export for 2019-2022", Thousand USD (the
    table caption; the list of tables says "Millions", the figures are
    thousands: 2022 total imports 6,379,520 = USD 6.38 bn as in the QSBs).

parse_ff(path)        Facts & Figures: 2018 edition Table 2.9 "foreign Trade (US
    dollars, in million)" 2012-2017 (exports, imports); 2023 and 2024 editions
    Tables "Total import/export of <year> (Millions USD)": the annual "Total"
    column by category (the quarter headers of these tables are misprinted --
    the 2024 export table is headed 2023Q1..Q4 -- so only the annual total of
    the edition's year is taken).

Every label is the latest bulletin's spelling of the category (earlier issues
print "Oil" for "Oil & Gas", "Furniture" for "Furniture Utensils", "Animal
Skins Products" for "Animal Skins"); classification "national".
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ._common import row, to_number
from .tanzania_nbs_trade import _lines, _newest_wins

_EXPORTS = [("Livestock", r"^livestock$|^livestock\b(?!.*(product|meat))"),
            ("Livestock Product (Meat)", r"livestock\s+products?|meat"),
            ("Fishery Export", r"fish"),
            ("Animal Skins", r"skin"),
            ("Crops & Vegetable Oil", r"crops?"),
            ("Forest Products", r"forest"),
            ("Other", r"^others?$")]
_IMPORTS = [("Oil & Gas", r"^oil"),
            ("Cars & spare parts", r"cars"),
            ("Food", r"^food"),
            ("Beverages & Tobacco", r"beverage"),
            ("Clothes & Footwear", r"cloth"),
            ("Construction", r"construction"),
            ("Cosmetics", r"cosmetic"),
            ("Electronics & Electric Machines", r"electronic"),
            ("Furniture Utensils", r"furniture"),
            ("Medical product", r"medical"),
            ("Personal Care", r"personal"),
            ("Plant Industries", r"plant"),
            ("Stationary", r"stationar"),
            ("Others", r"^others?$"),
            ("Of which khat", r"khat")]
_MONTH_Q = {"jan": 1, "apr": 2, "jul": 3, "oct": 4, "sep": 4}
_BIG = re.compile(r"^\$?\d{1,3}(,\d{3})+(\.\d+)?$|^\d{5,}(\.\d+)?$")   # not a 4-digit year


def _bulletin_quarter(path):
    n = os.path.basename(path)
    m = re.search(r"Q([1-4])-(\d{4})", n)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.search(r"(March|June|September|December)-(\d{4})", n)
    q = {"March": 1, "June": 2, "September": 3, "December": 4}[m.group(1)]
    return int(m.group(2)), q


def _qsb_table(lines, cats, flow, year, q, series):
    """lines: the overlap-grouped lines between a caption and 'Source'."""
    words = [w for ln in lines for w in ln]
    nums = [w for w in words if _BIG.match(w[4])]
    if not nums:
        return []
    xs = sorted({round((w[0] + w[2]) / 2) for w in nums})
    # two columns: split at the largest gap between number centres
    gaps = [(xs[i + 1] - xs[i], i) for i in range(len(xs) - 1)]
    if not gaps:
        return []
    g, i = max(gaps)
    cut = (xs[i] + xs[i + 1]) / 2
    left = sorted([w for w in nums if (w[0] + w[2]) / 2 < cut], key=lambda w: w[1])
    right = sorted([w for w in nums if (w[0] + w[2]) / 2 >= cut], key=lambda w: w[1])
    # row labels in order of appearance (alphabetic text of each line)
    found = []
    for ln in lines:
        text = " ".join(w[4] for w in ln if re.search(r"[A-Za-z]", w[4])).strip()
        if not text:
            continue
        low = text.lower()
        low = re.sub(r"^(summary|category|s/n).*", "", low)
        for name, rx in cats:
            if name not in [f[0] for f in found] and re.search(rx, low):
                found.append((name, min(w[1] for w in ln)))
                break
        if re.match(r"^(grand\s+)?total\b", low):
            found.append(("Total", min(w[1] for w in ln)))
    names = [f[0] for f in found]
    if len(left) != len(names) or len(right) != len(names) or names[-1:] != ["Total"]:
        return []
    lv = [to_number(w[4].lstrip("$")) for w in left]
    rv = [to_number(w[4].lstrip("$")) for w in right]
    for vals in (lv, rv):
        comp = sum(v for n, v in zip(names, vals) if n not in ("Total", "Of which khat"))
        tot = vals[-1]
        if tot is None or abs(comp - tot) > 0.005 * tot:
            return []
    out = []
    for n, a, b in zip(names, lv, rv):
        for per, v in ((f"{year}-Q{q}", a), (f"{year - 1}-Q{q}", b)):
            out.append(row(tradeflow=flow, period=per, frequency="quarterly", value=v, unit="USD",
                           commodity=None if n == "Total" else n,
                           commodity_classification="" if n == "Total" else "national",
                           series_code=series))
    return out


def parse_qsb(path, extras=None):
    import fitz
    year, q = _bulletin_quarter(path)
    tag = f"QSB {year}-Q{q}"
    doc = fitz.open(path)
    out = []
    try:
        for pno in range(doc.page_count):
            lines = _lines(doc[pno])
            texts = [" ".join(w[4] for w in ln) for ln in lines]
            for i, t in enumerate(texts):
                m = re.match(r"^Table\s*([23])\s*:\s*Summary of (exports|imports)", t, re.I)
                if not m or re.search(r"\.{5,}", t):
                    continue
                j = next((k for k in range(i + 1, len(texts))
                          if re.match(r"^(Source|Figure|Table)\b", texts[k])), len(texts))
                exp = m.group(2).lower() == "exports"
                out += _qsb_table(lines[i + 1:j], _EXPORTS if exp else _IMPORTS,
                                  "export" if exp else "import", year, q, f"{tag} Table {m.group(1)}")
    finally:
        doc.close()
    return pd.DataFrame(out)


def _label_rows(lines, n):
    """(label, values) for lines ending in exactly n numbers; a label-only line
    just above is joined ('Electronics & Electric' / 'Machines 67,967 ...')."""
    rows, pending = [], ""
    for ln in lines:
        toks = [w[4] for w in ln]
        vals = []
        while toks and re.match(r"^\(?-?[\d,]*\.?\d+\)?$", toks[-1]):
            vals.insert(0, toks.pop())
        label = " ".join(toks).strip()
        if len(vals) == n:
            rows.append(((pending + " " + label).strip() if pending and not label[:1].isupper() or
                         (pending and not label) else label, vals))
            pending = ""
        elif not vals and label:
            pending = label
        else:
            pending = ""
    return rows


def _match(label, cats):
    low = label.lower()
    for name, rx in cats:
        if re.search(rx, low):
            return name
    return None


def parse_abstract(path, extras=None):
    import fitz
    doc = fitz.open(path)
    out = []
    try:
        for pno in range(doc.page_count):
            lines = _lines(doc[pno])
            texts = [" ".join(w[4] for w in ln) for ln in lines]
            for i, t in enumerate(texts):
                m = re.match(r"^Table\s*3\.(8|9)\s+Total\s+(import|export)\s+(\d{4})-(\d{4})\s*\((Thousand|Millions?)\s+USD\)", t, re.I)
                if not m:
                    continue
                mult = 1e3 if m.group(5).lower().startswith("thousand") else 1e6
                years = [str(y) for y in range(int(m.group(3)), int(m.group(4)) + 1)]
                j = next((k for k in range(i + 1, len(texts)) if texts[k].startswith("Source")), len(texts))
                flow = m.group(2).lower()
                cats = _EXPORTS if flow == "export" else _IMPORTS
                for label, vals in _label_rows(lines[i + 1:j], len(years) + 1):
                    name = "Total" if re.match(r"^total", label, re.I) else _match(label, cats)
                    if not name:
                        continue
                    for y, tok in zip(years, vals[:len(years)]):
                        v = to_number(tok)
                        if v is None:
                            continue
                        out.append(row(tradeflow=flow, period=y, frequency="annual", value=v, unit="USD",
                                       unit_multiplier=mult, commodity=None if name == "Total" else name,
                                       commodity_classification="" if name == "Total" else "national",
                                       series_code=f"Abstract 2024 Table 3.{m.group(1)}"))
    finally:
        doc.close()
    return pd.DataFrame(out)


def parse_ff(path, extras=None):
    import fitz
    ed = int(re.findall(r"(20\d{2})", os.path.basename(path))[-1])
    doc = fitz.open(path)
    out = []
    try:
        for pno in range(doc.page_count):
            lines = _lines(doc[pno])
            texts = [" ".join(w[4] for w in ln) for ln in lines]
            for i, t in enumerate(texts):
                if ed == 2018 and re.match(r"^Table\s*2\.9:\s*foreign Trade \(US dollars, in million\)", t, re.I):
                    # Year | Export | Import, one line per year
                    j = next((k for k in range(i + 1, len(texts)) if texts[k].startswith("Source")), len(texts))
                    for ln in lines[i + 2:j]:
                        tk = [w[4] for w in ln]
                        if len(tk) == 3 and re.fullmatch(r"20\d{2}", tk[0]):
                            for flow, tok in zip(("export", "import"), tk[1:]):
                                out.append(row(tradeflow=flow, period=tk[0], frequency="annual",
                                               value=to_number(tok), unit="USD", unit_multiplier=1e6,
                                               series_code="Facts & Figures 2018 Table 2.9"))
                    continue
                m = re.search(r"Total\s+(import|export)\s+of\s+\d+\s*\(Millions USD\)", t, re.I)
                if ed in (2023, 2024) and m:
                    flow = m.group(1).lower()
                    cats = _EXPORTS if flow == "export" else _IMPORTS
                    j = next((k for k in range(i + 1, len(texts)) if re.match(r"^(Source|Total\s+(import|export)\s+of)", texts[k], re.I)), len(texts))
                    for label, vals in _label_rows(lines[i + 1:j], 5):
                        name = "Total" if re.match(r"^(grand\s+)?total", label, re.I) else _match(label, cats)
                        if not name:
                            continue
                        v = to_number(vals[4])
                        if v is None:
                            continue
                        out.append(row(tradeflow=flow, period=str(ed), frequency="annual", value=v, unit="USD",
                                       unit_multiplier=1e6, commodity=None if name == "Total" else name,
                                       commodity_classification="" if name == "Total" else "national",
                                       series_code=f"Facts & Figures {ed} ({flow}s, annual total column)"))
    finally:
        doc.close()
    return pd.DataFrame(out)


def parse(path, extras=None):
    files = [path] + list(extras or [])
    frames = []
    for f in files:
        n = os.path.basename(f)
        if "Quarterly-Statistical-Bulletin" in n:
            frames.append(parse_qsb(f).to_dict("records"))
    return _newest_wins(sorted(frames, key=lambda fr: max((r["period"] for r in fr), default="")))
