"""Parsers for Tanzania NBS merchandise trade (Tier 2 Excel + Tier 3 PDF).

Three source families, all on www.nbs.go.tz (TLS verifies):

parse_hfd(path, extras)       "High Frequency Data" workbooks (NBS topic
    high-frequency-data). Sheets "Exports 2025" / "Imports 2025": every HS
    chapter + Total, quarterly (Jan-March ... Oct-Dec), US$, exports FOB /
    imports CIF. Sheets "Export 2024" / "Import 2024" (end-March-2025 issue
    only): annual 2024 by HS chapter, net weight (kg) and value (USD). A
    quarter column whose Total is blank or 0 is an unpublished placeholder and
    is skipped. Older issues (2021-2024) carry no trade sheet.

parse_abstract(path, extras)  Tanzania Statistical Abstract PDFs (2011-2025
    editions). Table X.1 "Value of Foreign Trade" (exports FOB, domestic
    exports, re-exports, imports CIF, total trade, balance; Mill. TZS, annual),
    Table X.6 "Domestic Exports by Country of Destination" and Table X.7
    "Direct Imports by Country of Origin" (Mill. TZS, annual, every printed
    country and region). The X.6/X.7 "Total" rows are NOT emitted: they do not
    always equal the X.1 headline of the same edition (X.6's Total is the
    TOTAL-exports figure from 2021 on although the table says domestic
    exports), and the headline comes from X.1. The 2024 edition's partner
    pages are not read: its X.6 continuation page is captioned "Table 9.7
    Direct Imports" although its figures are the X.6 export rows (they match
    the 2025 edition's X.6), so the pages cannot be attributed safely; the 2023
    and 2025 editions cover its years.

parse_fts(path)               "Foreign Trade Statistics 2013" (2007-2013):
    Table 1 headline, Table 2 domestic exports by SITC section (names only, no
    codes printed), Table 6 domestic exports top-20 destinations + Others,
    Table 10 direct imports by SITC section, Table 12 imports top-20 origins +
    Others. Mill. TZS. Totals again only from Table 1.

Several files in one call (extras): parsed oldest edition first; for one key
the NEWEST edition's figure is kept (revisions replace older prints), which is
what merge-on-write does across runs.

PDF layout: words are grouped into lines by vertical OVERLAP (the 2024/2025
editions set a row label ~6pt below its figures), a row is a label followed by
exactly as many value tokens as the header has years (else dropped).
Negatives: "-1,234", "(1,234)", "- 1,234" (a detached minus), and the 2011
edition's minus signs printed on their own line just above the balance row
(matched to the figure below by x position). A malformed figure ("-7,548398")
is skipped, never repaired.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ._common import row, to_number
from ..schema import KEY

_NUM = re.compile(r"^\(?-?[\d,]*\.?\d+\)?,?$")
_DASH = {"-", "–", "—"}


# ----------------------------------------------------------------- PDF lines
def _lines(page):
    """Words grouped into visual lines by vertical overlap."""
    ws = sorted(page.get_text("words"), key=lambda w: (w[1], w[0]))
    lines: list[dict] = []
    for w in ws:
        y0, y1 = w[1], w[3]
        h = max(y1 - y0, 1e-6)
        best = None
        for ln in lines[-4:]:
            ov = min(y1, ln["y1"]) - max(y0, ln["y0"])
            if ov >= 0.35 * h:
                best = ln
        if best is None:
            lines.append({"y0": y0, "y1": y1, "w": [w]})
        else:
            best["w"].append(w)
            best["y0"], best["y1"] = min(best["y0"], y0), max(best["y1"], y1)
    out = []
    for ln in sorted(lines, key=lambda l: l["y0"]):
        out.append(sorted(ln["w"], key=lambda w: w[0]))
    return out


def _split_row(words, n):
    """(label, [(x, token)...]) where the trailing tokens are numeric/dash."""
    toks = [(w[0], w[2], w[4]) for w in words]
    vals = []
    i = len(toks)
    while i > 0:
        x0, x1, t = toks[i - 1]
        if _NUM.match(t) or t in _DASH:
            vals.insert(0, ((x0 + x1) / 2, t))
            i -= 1
        else:
            break
    label = " ".join(t for _, _, t in toks[:i]).strip()
    # A detached minus: "- 8,299,008" -> one negative token.
    merged = []
    for k, (x, t) in enumerate(vals):
        if merged and merged[-1][1] in _DASH and _NUM.match(t) and not t.startswith(("-", "(")):
            merged[-1] = (x, "-" + t)
        else:
            merged.append((x, t))
    if len(merged) > n and all(t in _DASH for _, t in merged[:len(merged) - n]):
        # leading dashes that belong to the label ("Re - Export")
        extra = merged[:len(merged) - n]
        label = (label + " " + " ".join(t for _, t in extra)).strip()
        merged = merged[len(merged) - n:]
    return label, merged


def _num(t):
    t = t.rstrip(",")
    if t in _DASH:
        return None
    return to_number(t, negative_parens=True)


_YEAR = re.compile(r"^(19|20)\d{2}p?\*?$")


def _header_years(words):
    ys = [re.sub(r"[^\d]", "", w[4]) for w in words if _YEAR.match(w[4])]
    return ys


# ----------------------------------------------------------- generic reader
def _read_tables(doc, caption_rx, stop_rx=r"^(Table\s*\w*\s*\.?\s*\d|Source)"):
    """Yield (caption, years, [(label, [values...], line_words, prev_words)])
    for every table whose caption matches `caption_rx` (continuation pages
    included -- each page is read on its own)."""
    for pno in range(doc.page_count):
        raw = doc[pno].get_text()
        if not re.search(r"Table", raw) or not re.search(
                r"Foreign\s+Trade|Domestic\s+Exports|Direct\s+Imports|SITC", raw, re.I):
            continue
        lines = _lines(doc[pno])
        texts = [" ".join(w[4] for w in ln) for ln in lines]
        i = 0
        while i < len(lines):
            if not re.search(caption_rx, texts[i], re.I):
                i += 1
                continue
            caption = texts[i]
            # unit line(s) and the header of years within the next 6 lines
            years, j = [], i + 1
            unit_text = caption
            while j < min(i + 8, len(lines)):
                ys = _header_years(lines[j])
                if len(ys) >= 3:
                    years = ys
                    break
                unit_text += " " + texts[j]
                j += 1
            if not years:
                i += 1
                continue
            rows = []
            k = j + 1
            pending = ""          # a wrapped label ("Democratic Republic of" / "Congo 634,887 ...")
            while k < len(lines) and not re.match(stop_rx, texts[k]):
                label, vals = _split_row(lines[k], len(years))
                if not vals:
                    pending = (pending + " " + label).strip() if label else pending
                else:
                    if pending and label and label[:1].islower() or pending.endswith(" of"):
                        label = (pending + " " + label).strip()
                    pending = ""
                rows.append((label, vals, lines[k], lines[k - 1] if k > 0 else []))
                k += 1
            yield caption, unit_text, years, rows, pno + 1
            i = k


def _mult_from(text):
    t = text.lower()
    if re.search(r"mill|million", t):
        return 1e6
    if "billion" in t:
        return 1e9
    return None


# ------------------------------------------------------------ the headline
_HEAD_ORDER = ["export", "domestic_export", "re_export", "import", "total", "balance"]
_HEAD_LABEL = [r"export", r"domestic", r"re\s*[-–]?\s*export", r"import", r"total", r"balance"]


def _headline(doc, caption_rx, series, default_mult=None):
    out = []
    for caption, unit_text, years, rows, pno in _read_tables(doc, caption_rx):
        mult = _mult_from(unit_text) or default_mult
        if mult is None:
            continue                      # scale not printed: drop the table
        numeric = [(lab, vals, ln, prev) for lab, vals, ln, prev in rows if len(vals) == len(years)]
        # The rows come in a fixed order in every edition; labels are checked
        # where they sit on the same line (some editions wrap them).
        numeric = numeric[:7]
        if len(numeric) < 6:
            continue
        for idx, flow in enumerate(_HEAD_ORDER):
            lab, vals, ln, prev = numeric[idx]
            if lab and not re.search(_HEAD_LABEL[idx], lab, re.I) and not re.search(r"^table$|^a\.", lab, re.I):
                raise ValueError(f"tanzania_nbs_trade: headline row {idx} is {lab!r}, expected {flow}")
            signs = {}
            if flow == "balance":
                # minus signs printed on their own line just above (2011 edition)
                ptoks = [w for w in prev if w[4] in _DASH]
                if ptoks and len(ptoks) == len(prev):
                    for w in ptoks:
                        xc = (w[0] + w[2]) / 2
                        c = min(range(len(vals)), key=lambda q: abs(vals[q][0] - xc))
                        if abs(vals[c][0] - xc) < 45:
                            signs[c] = -1
            for c, (y, (_, tok)) in enumerate(zip(years, vals)):
                v = _num(tok)
                if v is None:
                    continue
                if signs.get(c) == -1 and v > 0:
                    v = -v
                pb = "fob" if flow == "export" and re.search(r"f\.?o\.?b", lab, re.I) else \
                     "cif" if flow == "import" and re.search(r"c\.?i\.?f", lab, re.I) else ""
                out.append(row(tradeflow=flow, period=y, frequency="annual", value=v, unit="TZS",
                               unit_multiplier=mult, price_basis=pb, series_code=f"{series} p{pno}"))
    return out


# ------------------------------------------------------------ partner/commodity tables
_GROUPS = {"western europe", "eastern europe", "northern america", "asia and oceania", "asia & oceania",
           "africa", "middle east", "south & central america", "south and central america",
           "others countries", "other countries", "others", "european union", "eac", "sadc",
           "rest of the world", "oceania", "asia", "europe", "far east"}
_FRAGMENTS = {"Central", "Kingdom", "North", "South", "America", "Republic of", "Asia Oceania and",
              "Republic of Congo",   # 2014 edition: "Democratic" lost in a wrap
              "Europe"}              # 2011/2012: "Western"/"Eastern" lost in a wrap


def _labelled(doc, caption_rx, flow, kind, series, default_mult=None, skip_pages=()):
    """A label printed twice in one table ("Netherlands" under Western Europe
    and again under South & Central America, with other figures) keeps its
    FIRST occurrence only: the second cannot be told apart by its label."""
    out = []
    seen: set = set()
    for caption, unit_text, years, rows, pno in _read_tables(doc, caption_rx):
        if pno in skip_pages:
            continue
        mult = _mult_from(unit_text) or default_mult
        if mult is None:
            continue
        for lab, vals, ln, prev in rows:
            lab = re.sub(r"\s+", " ", lab).strip(" .:")
            if not lab or len(vals) != len(years):
                continue
            if re.match(r"^(grand\s+)?total\b", lab, re.I) or re.match(r"^(country|commodity)$", lab, re.I):
                continue
            # a fragment of a label wrapped over lines that could not be rejoined
            if re.match(r"^[(a-z]", lab) or re.search(r"\b(of|and|&)$", lab) or lab in _FRAGMENTS:
                continue
            if lab.lower() in seen:
                continue
            seen.add(lab.lower())
            for y, (_, tok) in zip(years, vals):
                v = _num(tok)
                if v is None or v < 0:
                    continue
                if kind == "partner":
                    ptype = "group" if (lab.lower() in _GROUPS or lab.lower().startswith("other")) else "country"
                    out.append(row(tradeflow=flow, period=y, frequency="annual", value=v, unit="TZS",
                                   unit_multiplier=mult, partner=lab, partner_type=ptype,
                                   series_code=f"{series} p{pno}"))
                else:
                    out.append(row(tradeflow=flow, period=y, frequency="annual", value=v, unit="TZS",
                                   unit_multiplier=mult, commodity=lab, commodity_classification="national",
                                   series_code=f"{series} p{pno}"))
    return out


def _edition(path):
    m = re.findall(r"(20\d{2})", os.path.basename(path))
    return m[-1] if m else ""


def _open_pdf(path):
    """A PDF, or the PDF inside an NBS .zip (older editions are zipped)."""
    import fitz
    if path.lower().endswith(".zip"):
        import zipfile
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".pdf"))
            return fitz.open(stream=z.read(name), filetype="pdf")
    return fitz.open(path)


def _one_abstract(path):
    ed = _edition(path)
    doc = _open_pdf(path)
    try:
        rows = _headline(doc, r"^Table\s*\w+\s*\.?\s*1\s*:?\s*Value of Foreign Trade", f"Abstract {ed} T.1")
        if ed != "2024":
            rows += _labelled(doc, r"^Table\s*\w+\s*\.?\s*6\s*(\(ct\w*\))?\s*:?.*Domestic Exports by Country",
                              "domestic_export", "partner", f"Abstract {ed} T.6")
            rows += _labelled(doc, r"^Table\s*\w+\s*\.?\s*7\s*:?\s*(\(ct\w*\))?\s*:?.*Direct Imports by Country",
                              "import", "partner", f"Abstract {ed} T.7")
    finally:
        doc.close()
    return rows


def _newest_wins(frames):
    df = pd.DataFrame([r for f in frames for r in f])
    if df.empty:
        return df
    norm = df[[k for k in KEY if k in df.columns]].astype(str)
    return df.loc[~norm.duplicated(keep="last")].reset_index(drop=True)


def parse_abstract(path, extras=None):
    files = sorted([path] + list(extras or []), key=_edition)
    return _newest_wins([_one_abstract(f) for f in files])


def parse_fts(path, extras=None):
    import fitz
    doc = fitz.open(path)
    try:
        s = "FTS 2013"
        rows = _headline(doc, r"^Table\s*1\s*:\s*Value of Tanzania Foreign Trade", f"{s} T.1")
        rows += _labelled(doc, r"^Table\s*2\s*:\s*Value of Domestic Exports by Commodity \(SITC\)",
                          "domestic_export", "commodity", f"{s} T.2")
        rows += _labelled(doc, r"^Table\s*6\s*:\s*Domestic Exports by Country of Destination",
                          "domestic_export", "partner", f"{s} T.6")
        rows += _labelled(doc, r"^Table\s*10\s*:\s*Direct Imports by SITC",
                          "import", "commodity", f"{s} T.10")
        rows += _labelled(doc, r"^Table\s*12\s*:\s*Direct Imports by Country of Origin",
                          "import", "partner", f"{s} T.12")
    finally:
        doc.close()
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ HFD Excel
_Q = {"jan": 1, "apr": 2, "jul": 3, "oct": 4}


def _one_hfd(path):
    import xlrd
    b = xlrd.open_workbook(path)
    out = []
    for sh in b.sheets():
        name = sh.name.strip()
        m = re.match(r"^(Exports?|Imports?)\s+(\d{4})$", name)
        if not m:
            continue
        flow = "export" if m.group(1).lower().startswith("export") else "import"
        series = f"HFD {os.path.basename(path)[14:].rsplit('.', 1)[0]} / {name}"
        head0 = [str(c).strip() for c in sh.row_values(0)]
        if head0[:2] == ["HS2", "Descriptions"]:
            # annual sheet: HS2 | Descriptions | Net Weight (Kg) | Value USD
            year = m.group(2)
            for r in range(1, sh.nrows):
                v = sh.row_values(r)
                code, desc = str(v[0]).strip(), str(v[1]).strip()
                if code.lower() == "total":
                    val = to_number(v[3])
                    if val is not None:
                        out.append(row(tradeflow=flow, period=year, frequency="annual", value=val,
                                       unit="USD", series_code=series))
                    continue
                if not re.fullmatch(r"\d{2}", code):
                    continue
                for col, meas, unit in ((2, "net_weight", "kg"), (3, "value", "USD")):
                    val = to_number(v[col])
                    if val is None:
                        continue
                    out.append(row(tradeflow=flow, period=year, frequency="annual", value=val, unit=unit,
                                   measure=meas, commodity=desc, commodity_classification="hs2",
                                   commodity_code_nso=code, series_code=series))
            continue
        # quarterly sheet: "Commodity (FOB Value)" | Units | quarters (years on row 0)
        pb = "fob" if "fob" in head0[0].lower() else "cif" if "cif" in head0[0].lower() else ""
        q_row = [str(c).strip() for c in sh.row_values(1)]
        cols, year = {}, None
        for c in range(2, sh.ncols):
            y = head0[c]
            if y:
                year = str(int(float(y)))
            q = _Q.get(q_row[c][:3].lower())
            if year and q:
                cols[c] = f"{year}-Q{q}"
        # a column is published only when its Total is a positive number
        total_r = next(r for r in range(sh.nrows) if str(sh.cell_value(r, 0)).strip().lower() == "total")
        live = {c: p for c, p in cols.items() if (to_number(sh.cell_value(total_r, c)) or 0) > 0}
        for r in range(2, sh.nrows):
            lab = str(sh.cell_value(r, 0)).strip().replace("�", "'")
            unit = str(sh.cell_value(r, 1)).strip()
            if unit not in ("US$", "USD"):
                continue
            mm = re.match(r"^(\d{2})\s*-\s*(.+?)[:.]?$", lab)
            for c, per in live.items():
                val = to_number(sh.cell_value(r, c))
                if val is None:
                    continue
                if lab.lower() == "total":
                    out.append(row(tradeflow=flow, period=per, frequency="quarterly", value=val, unit="USD",
                                   price_basis=pb, series_code=series))
                elif mm:
                    out.append(row(tradeflow=flow, period=per, frequency="quarterly", value=val, unit="USD",
                                   price_basis=pb, commodity=mm.group(2).strip(),
                                   commodity_classification="hs2", commodity_code_nso=mm.group(1),
                                   series_code=series))
    return out


def _hfd_order(path):
    """Issue date from 'High Frequency Data end <Month> <Year>'."""
    import calendar
    n = os.path.basename(path).replace("_", " ")
    m = re.search(r"end\s+([A-Za-z]+)\s+(\d{4})", n)
    if not m:
        return (0, 0)
    mon = [x.lower() for x in calendar.month_name].index(m.group(1).lower()) \
        if m.group(1).lower() in [x.lower() for x in calendar.month_name] else 0
    return (int(m.group(2)), mon)


def parse_hfd(path, extras=None):
    files = sorted([path] + list(extras or []), key=_hfd_order)
    return _newest_wins([_one_hfd(f) for f in files])


parse = parse_hfd
