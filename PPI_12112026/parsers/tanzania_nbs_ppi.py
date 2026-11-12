"""Tanzania -- NBS quarterly "Producer Price Indices" release (one PDF per quarter).

Table 1 "Producer Price Indices by Sectors (Sub-sectors) and Major Groups":
ISIC Rev.4 divisions (07 .. 36), sections B / C, Utilities (35&36) and the
Overall Index, with weights (from 2014) and the index for 3-6 quarters; since
2020 also two % change columns (quarter on quarter, and on the same quarter a
year earlier).

Bases, as each release's own Table 1 caption prints them: March 2013 = 100
(2014 - 2018 releases), Dec 2018 = 100 (2019 Q1 -; NBS: "2018Q4=100"). The
2019+ releases say the new series is linked back to 2013 for the top-level
aggregates; the linked back-series itself is "accessed through the provided
link", not printed, so it is not collected.

READ BY GEOMETRY, NOT BY TEXT FLOW. From 2019 the table is set as a rotated
form whose glyphs pdfplumber marks non-upright, so extract_text() returns
it one letter per line; and a long label wraps over 2-3 lines with its code
and numbers on the middle line and a "0.0" cell sometimes a line lower. So
the table is rebuilt from glyph positions: glyphs are joined into tokens by
adjacency (x gap < 1 pt; spaces ignored), columns are the x-centres of the
Overall Index row's numbers, a data row is anchored on its token in the
FIRST numeric column, and every other token joins the nearest anchor row by
vertical distance. Index columns are dated from the header above each column
(quarter from the month range "Jul-Sept", year from "2014Q3" / "2026"; the
2014 Q3 release prints "2014Q2" twice, and its month row says Jul-Sept); the
% change columns are those without a date, and which is q/q and which y/y is
settled against the indices printed in the same table, as in Kenya.

Never OCR, never computed.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

INDEX_NAME = "Producer Price Index (PPI)"
_MSTART = {"jan": 1, "apr": 2, "jul": 3, "oct": 4}
_NUMTOK = re.compile(r"^\(?-?\d+(?:\.\d+)?\)?$")


def _tokens(page):
    chars = [c for c in page.chars if c["text"].strip()]
    lines = {}
    for c in sorted(chars, key=lambda c: (c["top"], c["x0"])):
        key = next((k for k in lines if abs(k - c["top"]) < 2.0), None)
        lines.setdefault(key if key is not None else c["top"], []).append(c)
    toks = []
    for top, cs in lines.items():
        cs.sort(key=lambda c: c["x0"])
        cur = [cs[0]]
        for c in cs[1:]:
            # "( 0.01)": the opening parenthesis of a negative sits a space away
            if c["x0"] - cur[-1]["x1"] < 1.0 or (cur[-1]["text"] == "(" and c["x0"] - cur[-1]["x1"] < 8):
                cur.append(c)
            else:
                toks.extend(_split_glued(cur, top))
                cur = [c]
        toks.extend(_split_glued(cur, top))
    return toks


def _split_glued(cs, top):
    """'n.e.c.0.0': a narrow weight cell set flush against its label -- split
    the trailing number off as its own token (at its own glyphs' position)."""
    text = "".join(c["text"] for c in cs)
    m = re.match(r"^(.*[A-Za-z.,)])(\d+\.\d+)$", text)
    if m and len(m.group(1)) >= 2 and not re.fullmatch(r"[\d.]+", m.group(1)):
        k = len(m.group(1))
        return [_tok(cs[:k], top), _tok(cs[k:], top)]
    return [_tok(cs, top)]


def _tok(cs, top):
    return {"text": "".join(c["text"] for c in cs), "x0": cs[0]["x0"], "x1": cs[-1]["x1"],
            "xc": (cs[0]["x0"] + cs[-1]["x1"]) / 2, "top": top}


def _num(t: str):
    neg = t.startswith("(") and t.endswith(")")
    v = C.to_number(t.strip("()"))
    return None if v is None else (-v if neg else v)


def _overall_top(toks):
    """The line of the Overall Index ROW: 'Overall' with >= 3 numbers beside it
    (the prose below the table also says 'Overall index recorded ...')."""
    for t in sorted(toks, key=lambda t: t["top"]):
        if re.match(r"(?i)overall$|total$", t["text"]):
            n = sum(1 for u in toks if abs(u["top"] - t["top"]) < 4 and _NUMTOK.match(u["text"]))
            if n >= 2:
                return t["top"]
    return None


def _find_page(pdf):
    for pg in pdf.pages:
        t = pg.extract_text() or ""
        if re.search(r"Table\s*1\b", t) and re.search(r"Producer Price Ind", t):
            toks = _tokens(pg)
            if _overall_top(toks) is not None:
                return pg, toks
    return None, None


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        doc = "\n".join((p.extract_text() or "") for p in pdf.pages)
        pg, toks = _find_page(pdf)
        if pg is None:
            raise ValueError(f"{path}: no Table 1 page")
    # Base: the Table 1 caption / its 'Index (...)' header, as printed.
    cap = " ".join(t["text"] for t in sorted(toks, key=lambda t: (t["top"], t["x0"])))
    m = (re.search(r"\(?((?:March|Dec(?:ember)?)\s*\d{4})\s*=\s*100\)?", cap)
         or re.search(r"\(?((?:March|Dec(?:ember)?)\s*\d{4})\s*=\s*100\)?", doc))
    if not m:
        raise ValueError(f"{path}: no base printed")
    base = re.sub(r"\s+", " ", m.group(1)) + "=100"

    # The Overall Index row fixes the numeric columns.
    ovtop = _overall_top(toks)
    cols = sorted(t["xc"] for t in toks if abs(t["top"] - ovtop) < 4 and _NUMTOK.match(t["text"]))
    if len(cols) < 2:
        raise ValueError(f"{path}: Overall row has {len(cols)} numbers")
    half = min(b - a for a, b in zip(cols, cols[1:])) / 2

    def col_of(t):
        j = min(range(len(cols)), key=lambda j: abs(cols[j] - t["xc"]))
        return j if abs(cols[j] - t["xc"]) <= half else None

    # Header: the lines above the first data row. Each column's date.
    nums = [t for t in toks if _NUMTOK.match(t["text"]) and col_of(t) == 0 and t["top"] <= ovtop + 1]
    first_top = min(t["top"] for t in nums)
    head0 = [t for t in toks if first_top - 70 < t["top"] < first_top - 1]
    has_w = any(t["text"].lower().startswith("weight") for t in head0)
    # Only the column-header lines date a column -- not the caption above
    # ("(March 2013 = 100)", "Index (Dec 2018=100)"): a line with "=" or "100)" is
    # a caption. Each header token belongs to its NEAREST column (a month range
    # "Apr - June" sits between the weight and the first index column).
    by_line = {}
    for t in head0:
        by_line.setdefault(round(t["top"]), []).append(t)
    head = [t for ts in by_line.values() if not any("=" in u["text"] or "100)" in u["text"] or
                                                    u["text"].lower() == "table" for u in ts) for t in ts]
    # "2019 Q3" printed as two tokens: join a lone Qn to the year just left of it.
    for t in head:
        if re.fullmatch(r"Q[1-4]", t["text"]):
            yl = [u for u in head if u["top"] == t["top"] and re.fullmatch(r"(?:19|20)\d{2}", u["text"])
                  and 0 <= t["x0"] - u["x1"] < 8]
            if yl:
                t["text"] = yl[0]["text"] + t["text"]
                yl[0]["text"] = ""
    owner = {}
    for t in head0:
        j0 = min(range(len(cols)), key=lambda k: abs(cols[k] - t["xc"]))
        if abs(cols[j0] - t["xc"]) <= half * 1.6:
            owner.setdefault(j0, []).append(t)
    dates = {}
    month = re.compile(r"(?i)^(jan|apr|jul|oct)")
    any_month = any(month.match(t["text"]) for t in head)
    for j in range(len(cols)):
        mine = owner.get(j, [])
        near = [t for t in mine if t in head]
        # Where the header prints month ranges (every release), an index column
        # is one that owns a month range; the % change columns carry only
        # "2026Q2 vs 2026Q1" (set left of their numbers, so a "vs" can fall
        # nearer the last index column -- it is not used to decide).
        if any_month and not any(month.match(t["text"]) for t in near):
            continue
        q = y = None
        for t in near:
            mm = re.match(r"^(\d{4})\s*Q([1-4])$", t["text"])
            if mm:
                y = y or mm.group(1)
                q = q or int(mm.group(2))
        for t in near:      # the month range, when printed, decides the quarter
            mm = re.match(r"^(jan|apr|jul|oct)", t["text"].lower())
            if mm:
                q = _MSTART[mm.group(1)]
            if re.fullmatch(r"(?:19|20)\d{2}", t["text"]):
                y = t["text"]
        if q and y:
            dates[j] = f"{y}-Q{q}"
    idx_cols = sorted(dates)
    if not idx_cols:
        raise ValueError(f"{path}: no dated index column")
    wcol = 0 if has_w and 0 not in dates else None
    pct_cols = [j for j in range(len(cols)) if j not in dates and j != wcol]

    # Rows: anchors in the first numeric column; others join the nearest anchor.
    body = [t for t in toks if first_top - 12 < t["top"] < ovtop + 4]
    # A data row is a line with >= 2 numeric cells (a dash weight "-" still
    # leaves the indices); a lone "0.0" a line below its row is not a row.
    cnt = {}
    for t in body:
        if _NUMTOK.match(t["text"]) and col_of(t) in dates:
            cnt[t["top"]] = cnt.get(t["top"], 0) + 1
    # One row's cells can sit 2 pt apart ("127.6 128.4 128.9" above "100.0 126.9").
    anchors, acc = [], []
    for k in sorted(cnt):
        if acc and k - acc[-1][0] > 4:
            if sum(n for _, n in acc) >= min(2, len(idx_cols)):
                anchors.append(sum(t for t, _ in acc) / len(acc))
            acc = []
        acc.append((k, cnt[k]))
    if acc and sum(n for _, n in acc) >= min(2, len(idx_cols)):
        anchors.append(sum(t for t, _ in acc) / len(acc))
    if not anchors:
        raise ValueError(f"{path}: no data rows")
    rows = {a: {"code": [], "label": [], "vals": {}} for a in anchors}
    label_x1 = cols[0] - half
    isic = [t for t in head0 if t["text"].upper().startswith("ISIC")]
    code_x = isic[0]["xc"] if isic else None

    def nearest(top):
        a = min(anchors, key=lambda a: abs(a - top))
        return a if abs(a - top) <= 16 else None

    label_lines = {}
    for t in body:
        if _NUMTOK.match(t["text"]) and t["x0"] > label_x1:
            j, a = col_of(t), nearest(t["top"])
            if j is not None and a is not None:
                rows[a]["vals"][j] = t["text"]
        elif t["x1"] <= label_x1 + 2:
            if (re.fullmatch(r"\d{1,2}(?:&\d{2})?|[A-U]", t["text"])
                    and (code_x is None or abs(t["xc"] - code_x) < 25 or t["x1"] < t["x0"] + 20 and t["x0"] < 110)):
                a = nearest(t["top"])
                if a is not None:
                    rows[a]["code"].append(t["text"])
            else:
                label_lines.setdefault(round(t["top"]), []).append(t)
    # Label blocks: a wrapped label continues on lines that start lower-case
    # ("Manufacture of tobacco" / "products"); each block goes to the row
    # nearest its middle.
    blocks = []
    for k in sorted(label_lines):
        ts = sorted(label_lines[k], key=lambda t: t["x0"])
        if blocks and ts[0]["text"][:1].islower() and k - blocks[-1]["last"] < 16:
            blocks[-1]["toks"] += ts
            blocks[-1]["last"] = k
        else:
            blocks.append({"toks": list(ts), "first": k, "last": k})
    for b in blocks:
        a = nearest((b["first"] + b["last"]) / 2)
        if a is not None:
            rows[a]["label"] += b["toks"]
    # 2016: a wrapped row prints its cells on TWO lines a line apart
    # ("Manufacture of tobacco 142.2 158.0 161.4 153.2" / "12 5.1 132.6 158.3"):
    # two neighbouring anchors whose cells fill DISJOINT columns are one row.
    merged = []
    for a in anchors:
        if merged and a - merged[-1] <= 14 and not (set(rows[a]["vals"]) & set(rows[merged[-1]]["vals"])):
            p = rows[merged[-1]]
            p["vals"].update(rows[a]["vals"])
            p["code"] += rows[a]["code"]
            p["label"] += rows[a]["label"]
            del rows[a]
        else:
            merged.append(a)
    anchors = merged
    out, level = [], {}
    release = max(dates.values())
    for a in anchors:
        r = rows[a]
        label = " ".join(t["text"] for t in sorted(r["label"], key=lambda t: (t["top"], t["x0"])))
        label = re.sub(r"\s+", " ", label).strip(" *")
        # The table header's "Rev4" can sit on the first row's line; a word
        # hyphenated across a wrap ("semi- trailers", "non- metallic") is rejoined.
        label = re.sub(r"^Rev\.?4\s+", "", label)
        label = re.sub(r"(?<=[a-z])- (?=[a-z])", "-", label)
        code = r["code"][0].zfill(2) if r["code"] and r["code"][0].isdigit() else (r["code"][0] if r["code"] else "")
        if not label:
            continue
        ind = "Overall Index" if re.match(r"(?i)overall|total manufacturing$", label) else label
        for j in idx_cols:
            v = _num(r["vals"].get(j, "")) if j in r["vals"] else None
            if v is not None:
                level[(ind, dates[j])] = v
                out.append(C.row(index_name=INDEX_NAME, industry=ind, industry_code_nso=code,
                                 period=dates[j], frequency="quarterly", measure="index",
                                 value=v, base_period=base))
        if wcol is not None and wcol in r["vals"]:
            w = _num(r["vals"][wcol])
            if w is not None:
                out.append(C.row(index_name=INDEX_NAME, industry=ind, industry_code_nso=code,
                                 period=release, frequency="quarterly", measure="weight",
                                 value=w, unit="percent", base_period=base))
        r["ind"], r["code1"] = ind, code
    # % change columns: settle q/q vs y/y against the printed indices.
    if len(pct_cols) == 2:
        def lag(q, k):
            yy, n = int(q[:4]), int(q[-1])
            kk = yy * 4 + n - 1 - k
            return f"{kk // 4}-Q{kk % 4 + 1}"
        score, cand = [0, 0], []
        for a in anchors:
            r = rows[a]
            if "ind" not in r:
                continue
            now, p1, p4 = (level.get((r["ind"], release)), level.get((r["ind"], lag(release, 1))),
                           level.get((r["ind"], lag(release, 4))))
            va, vb = (_num(r["vals"][j]) if j in r["vals"] else None for j in pct_cols)
            cand.append((r, va, vb))
            if None in (now, p1, p4, va, vb) or not p1 or not p4:
                continue
            iq, iy = (now / p1 - 1) * 100, (now / p4 - 1) * 100
            score[0] += abs(va - iq) <= 0.06 and abs(vb - iy) <= 0.06
            score[1] += abs(va - iy) <= 0.06 and abs(vb - iq) <= 0.06
        order = 0 if score[0] >= score[1] else 1
        if max(score) >= 5:
            for r, va, vb in cand:
                for meas, v in zip(("inflation_qoq", "inflation_yoy") if order == 0 else
                                   ("inflation_yoy", "inflation_qoq"), (va, vb)):
                    if v is not None:
                        out.append(C.row(index_name=INDEX_NAME, industry=r["ind"],
                                         industry_code_nso=r["code1"], period=release,
                                         frequency="quarterly", measure=meas, value=v))
    if len(out) < 20:
        raise ValueError(f"{path}: only {len(out)} values")
    return pd.DataFrame(out)


# A % change carries the base of its index (set from this output; see _base_carry).
# The 2025 Q2-Q4 releases print no ISIC codes. Each of these labels carries
# ONE code in every NBS release that prints codes (2013-2025 Q1, 2026), so the
# same series keeps its code; "Utility" is left blank (printed as "D" in some
# releases and "35&36" in others).
_CODE_FOR_LABEL = {
    'Electricity, gas, steam and air conditioning supply': '35',
    'Manufacture of basic metals': '24',
    'Manufacture of beverages': '11',
    'Manufacture of chemicals and chemical products': '20',
    'Manufacture of coke and refined petroleum products': '19',
    'Manufacture of computer, electronic and optical products': '26',
    'Manufacture of electrical equipment': '27',
    'Manufacture of fabricated metal products, except machinery and equipment': '25',
    'Manufacture of food products': '10',
    'Manufacture of furniture': '31',
    'Manufacture of leather and related products': '15',
    'Manufacture of machinery and equipment': '28',
    'Manufacture of machinery and equipment n.e.c.': '28',
    'Manufacture of motor vehicles, trailers and semi-trailers': '29',
    'Manufacture of other non-metallic mineral products': '23',
    'Manufacture of paper and paper products': '17',
    'Manufacture of pharmaceuticals, medicinal chemical and botanical products': '21',
    'Manufacture of rubber and plastics products': '22',
    'Manufacture of textiles': '13',
    'Manufacture of tobacco products': '12',
    'Manufacture of wearing apparel': '14',
    'Manufacture of wood and of products of wood and cork, except furniture; manufacture of articles of straw and plaiting materials': '16',
    'Manufacturing': 'C',
    'Mining and Quarrying': 'B',
    'Mining of metal ores': '07',
    'Other manufacturing': '32',
    'Other mining and quarrying': '08',
    'Printing and reproduction of recorded media': '18',
    'Repair and installation of machinery and equipment': '33',
    'Water collection, treatment and supply': '36',
}


def _with_codes(fn):
    def wrapped(path, *a, **k):
        df = fn(path, *a, **k)
        blank = df["industry_code_nso"].fillna("").eq("")
        df.loc[blank, "industry_code_nso"] = df.loc[blank, "industry"].map(_CODE_FOR_LABEL).fillna("")
        return df
    return wrapped


from ._base_carry import carry_base  # noqa: E402
parse = carry_base(_with_codes(parse))
