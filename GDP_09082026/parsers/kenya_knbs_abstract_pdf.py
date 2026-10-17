"""Annual back series for Kenya from older KNBS Statistical Abstract PDFs
(National Accounts chapter). Not a registry parser: `kenya_knbs_gdp.parse`
hands it any `KNBS_Statistical_Abstract_<year>.pdf` extra.

Each edition is its own vintage. Kenya rebased twice (2001 -> 2009 in 2014,
2009 -> 2016 in 2021) and every rebasing revised the CURRENT-price levels too,
so two editions print different figures for the same year. Nothing is chained
or spliced: `category_group` names the edition and table ('Statistical
Abstract 2018, Table 2.2: Gross Domestic Product by Activity') and constant-
price levels carry their own base ('constant 2009 prices').

Tables read (whatever their number in the edition): GDP by activity at current
prices, shares of GDP, constant prices and real growth; expenditure on GDP
(levels, shares, growth); gross fixed capital formation; GDP and gross national
income (incl. per capita). Not read: the production accounts and the
by-institutional-sector tables (their section structure is not stable across
editions).

TEXT LAYER QUIRK: the PDFs break some numbers into two touching words
('9' + '82,191', '2' + ',838,992'). Words whose gap is under a point are joined
before the numbers are read; the row must then carry exactly one value per
year column ('-' = nil, kept as a column but not emitted).
"""
from __future__ import annotations
import os
import re
import pdfplumber

UNIT = "KES million"
_YEAR = re.compile(r"^((?:19|20)\d\d)[⁺+*]?$")
_NUM = re.compile(r"^\(?-?(\d{1,3}(,\d{3})*|\d+)(\.\d+)?\)?$")
_TABLE = re.compile(r"Table\s*(\d+(?:\.\d+)?\s*(?:\([a-z]\))?)", re.I)


def _edition(path: str) -> str:
    """'Statistical Abstract 2018' / 'Economic Survey 2008' from the file name."""
    base = os.path.basename(path)
    m = re.search(r"(\d{4})", base)
    kind = "Economic Survey" if "economic_survey" in base.lower()         else "Statistical Abstract"
    return f"{kind} {m.group(1)}" if m else kind


_FRAG = re.compile(r"^[\d,.()\-]+$")


def _lines(page):
    words = page.extract_words(keep_blank_chars=False, x_tolerance=1.5)
    words.sort(key=lambda w: w["top"])
    groups, top = [], None
    for w in words:
        if top is None or abs(w["top"] - top) > 2.5:
            groups.append([])
            top = w["top"]
        groups[-1].append(w)
    lines = []
    for g in groups:
        cur = []
        for w in sorted(g, key=lambda w: w["x0"]):
            # a number broken into two touching words ('9' + '82,191')
            if (cur and -1 < w["x0"] - cur[-1]["x1"] < 0.8
                    and _FRAG.match(cur[-1]["text"]) and _FRAG.match(w["text"])):
                cur[-1] = {**cur[-1], "text": cur[-1]["text"] + w["text"],
                           "x1": w["x1"]}
            else:
                cur.append(dict(w))
        lines.append([w["text"] for w in cur])
    return lines


def _val(tok: str):
    t = tok.replace(",", "")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    v = float(t)
    return -v if neg else v


def _label(toks) -> str:
    s = " ".join(toks)
    s = re.sub(r"[.…]{2,}.*$", "", s)                # leaders
    return re.sub(r"\s+", " ", s).strip(" .")


def _spec(text: str):
    t = text.lower()
    if "expenditure" in t:
        approach = "expenditure"
    elif "capital formation" in t:
        approach = "expenditure"
    elif "national income" in t:
        approach = "income"
    else:
        approach = "production"
    base = re.search(r"constant\s*(\d{4})\s*prices", t)
    if "growth" in t or "percentage change" in t:
        return "growth_yoy", "constant", "percent", approach, ""
    if "contribution" in t or "share" in t or "per cent" in t or "percentage" in t:
        return "share", "current", "percent", approach, ""
    if "constant" in t:
        return ("level", "constant", UNIT, approach,
                f"constant {base.group(1)} prices" if base else "")
    return "level", "current", UNIT, approach, ""


def _wanted(text: str) -> bool:
    t = text.lower()
    if "sector" in t or "production account" in t or "disposable income and saving" in t:
        return False
    return any(k in t for k in ("domestic product by activity",
                                "expenditure on the gross domestic product",
                                "gross fixed capital formation",
                                "gross national income",
                                "growth of gross domestic product"))


_KEYS = ("domestic product by activity", "expenditure on the gross domestic product",
         "gross fixed capital formation", "gross national income",
         "growth of gross domestic product")


def _mentions(text: str) -> bool:
    t = re.sub(r"\s+", " ", text.lower())
    return "table" in t and any(k in t for k in _KEYS)


def _is_aggregate(label: str) -> bool:
    l = label.lower()
    return ("gdp at market" in l or "gross domestic product" in l
            or "gross national" in l or l.startswith("gdp"))


def parse_abstract(path: str) -> list[dict]:
    ed = _edition(path)
    rows = []
    # Page selection with PyMuPDF (fast); tables are read with pdfplumber.
    import fitz
    with fitz.open(path) as doc:
        texts = {i: pg.get_text() for i, pg in enumerate(doc)}
    # Candidate pages: any that mention a wanted table; each table block is
    # then filtered on its own caption (_wanted).
    idx = [i for i, t in texts.items() if _mentions(t)]
    # The edition's constant-price base, as its activity table prints it;
    # used where a section says only 'Constant Prices' (the GDP/GNI table).
    bases = {m.group(1) for i in idx for m in re.finditer(
        r"constant\s*(\d{4})\s*prices", texts[i].lower())}
    ed_base = f"constant {bases.pop()} prices" if len(bases) == 1 else ""
    with pdfplumber.open(path) as pdf:
        for page in (pdf.pages[i] for i in idx):
            lines = _lines(page)
            # A page may hold two tables; split at each 'Table N' line.
            blocks, cur = [], []
            for i, l in enumerate(lines):
                if l and l[0].lower() == "table" and cur and any(
                        len([t for t in x if _YEAR.match(t)]) >= 4 for x in cur):
                    blocks.append(cur)
                    # the 2013 layout prints the caption on the line ABOVE
                    # 'Table N'; move it into the new block
                    cur = [cur.pop()] if cur and not any(
                        _NUM.match(t) and not _YEAR.match(t)
                        for t in cur[-1]) else []
                cur.append(l)
            if cur:
                blocks.append(cur)
            for blk in blocks:
                rows.extend(_read_block(blk, ed, ed_base))
    if not rows:
        raise ValueError(f"no national-accounts rows read from {path}")
    return rows


def _join_split_years(l):
    """The 2018 abstract's Table 2.2 header prints '2,011 2,012 2013⁺ ...': a
    year with a thousands comma (one token, or two: '2' ',011'). Read as is,
    only 2013-2017 count as years and the 2011-2012 columns of EVERY row in
    the table were dropped. Rejoin only when the result is a year."""
    out, i = [], 0
    while i < len(l):
        if re.fullmatch(r"\d,\d{3}[⁺+*]?", l[i]) and _YEAR.match(l[i].replace(",", "")):
            out.append(l[i].replace(",", ""))
            i += 1
        elif (i + 1 < len(l) and re.fullmatch(r"\d", l[i])
                and re.fullmatch(r",\d{3}[⁺+*]?", l[i + 1])
                and _YEAR.match(l[i] + l[i + 1][1:])):
            out.append(l[i] + l[i + 1][1:])
            i += 2
        else:
            out.append(l[i])
            i += 1
    return out


def _read_block(blk, ed, ed_base=""):
    # Only a line already carrying plain years is a header: a DATA row's
    # "2,011" is a value, and four such joined would read as a header line.
    blk = [_join_split_years(l) if sum(bool(_YEAR.match(t)) for t in l) >= 2 else l
           for l in blk]
    yi = next((i for i, l in enumerate(blk)
               if len([t for t in l if _YEAR.match(t)]) >= 4), None)
    if yi is None:
        return []
    header = " ".join(" ".join(l) for l in blk[:yi])
    m = _TABLE.search(header)
    if not m or not _wanted(header):
        return []
    tno = re.sub(r"\s+", "", m.group(1))
    cap = re.sub(r"\s+", " ", header)
    title = re.search(r"((?:Growth of )?Gross Domestic Product[^,]*|Expenditure on the "
                      r"Gross Domestic Product|(?:Share of )?Gross Fixed Capital "
                      r"Formation|Gross Domestic Product and Gross National Income)",
                      cap, re.I)
    group = (f"{ed}, Table {tno}: "
             f"{title.group(1).strip() if title else ''}").strip()
    measure, basis, unit, approach, base = _spec(cap)
    years = [_YEAR.match(t).group(1) for t in blk[yi] if _YEAR.match(t)]
    n = len(years)
    out = []
    parent = ""
    section_basis, section_base = basis, base
    for l in blk[yi + 1:]:
        if len([t for t in l if _YEAR.match(t)]) >= 4:
            continue
        k = n
        tail = l[-k:] if len(l) > k else []
        ok = tail and all(_NUM.match(t) or t in ("-", "–") for t in tail)
        label = _label(l[:-k]) if ok else _label(l)
        if not ok:
            low = label.lower()
            if "constant prices" in low:
                parent = ""
                section_basis = "constant"
                b = re.search(r"(\d{4})", low)
                section_base = f"constant {b.group(1)} prices" if b else section_base
            elif label and not low.startswith(("*", "+", "1 ", "table", "source")):
                parent = label
            continue
        if not label or label.lower().startswith(("*", "+")):
            continue
        # A "label" with no letters is surplus numbers from a line whose words
        # wrapped onto the lines around it (2018 Table 2.2's FISIM row was
        # published as category "(90,687) (111,574)"). Skip rather than invent.
        if not re.search(r"[A-Za-z]", label):
            continue
        cat, appr, meas, un, b, bp = label, approach, measure, unit, section_basis, ""
        low = label.lower()
        if approach == "income":
            if low.startswith(("receivable", "payable")):
                cat = f"{parent}: {label}"
            if "percentage change" in low:
                meas, un = "growth_yoy", "percent"
            elif "per capita" in low or parent.lower().startswith("per capita"):
                meas, un = "per_capita", "KES"
        if _is_aggregate(label):
            appr = "aggregate"
        if b == "constant" and meas in ("level", "per_capita"):
            bp = section_base or base or ed_base
        for y, t in zip(years, tail):
            if t in ("-", "–"):
                continue
            out.append({"approach": appr, "category": cat, "category_group": group,
                        "series_code": "", "geography": "National", "period": y,
                        "frequency": "annual", "price_basis": b,
                        "seasonal_adjustment": "not_applicable", "measure": meas,
                        "value": _val(t), "unit": un, "base_period": bp})
    return out
