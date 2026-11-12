"""Mali -- INSTAT, Indice de Prix des Produits Agricoles à la Production (IPPAP), base 100 = 2015.

"BULLETIN TRIMESTRIEL DE PUBLICATION N° 000 -- IPPAP Base 100 = 2015 -- 2015-
2020" (juin 2022; instat-mali.org .../shares/pub/ippap000_pub.pdf), an
AGRICULTURAL producer price index (index_variant "agriculture": 134 farm-gate
products, Laspeyres, weights = 2015 value added; NOPEMA rev1-derived codes).

Tables (each followed by a chart whose axis labels reach the text layer as
lone numbers -- ignored, a data row always prints its weight AND every period):
  p.5   sous-secteurs, T1-16..T4-17        p.7  postes, T1-16..T4-17
  p.6   sous-secteurs, T1-18..T4-19        p.10 postes, T1-18..T4-19
  p.13  sous-secteurs, annual 2015..2019   p.14 postes, annual 2015..2019
  p.4   summary: sous-secteurs and postes, T1-19 | T4-19 | T1-20 | T1-20/T4-19 |
        T1-20/T1-19 -- the only T1-2020 indices, and the % changes on the
        previous quarter (inflation_qoq) and a year earlier (inflation_yoy).
        Its Ensemble (T1-19 106,8; T4-19 128,9; T1-20 126,3) is the correct
        one (see below); p.6 repeats its other T1-19/T4-19 values.
Header: "... Pondérations <periods>"; a row: codes, label, weight (per 100 000),
one index per period. Labels wrap around their row ("Produits de l'élevage
de / 02.01 02.01.01 01.41p 20381,4 ... / bovins"): a text line before the row
opens the label, a lower-case line after it continues it; code-only lines
("01-04", "01.31 & 01.34-", "01.44p, 01.45p") are dropped. INSTAT's ad hoc
code (sous-secteur "01".."04", "01-04" for Ensemble; poste "01.01.01") goes
to industry_code_nso.

NOT EMITTED, with reasons:
  * the "Ensemble" row of p.6 (T1-18..T4-19): it repeats p.5's 2016-17 values
    digit for digit (109,5 93,1 93,5 100,6 111,2 98,6 98,3 105,9) -- a
    copy error. The weighted sub-sectors give 106,8 for T1-19, the figure the
    bulletin's own text states ("106,8 au 1er trimestre 2019"), and reproduce
    p.5's Ensemble (T1-16: 109,5). The p.6 sub-sector rows are genuine.
  * an index of 0,0 (Fruits, out of season) -- not a price level.
  * the annex of average producer prices in FCFA (prices, not indices).
TAKEN SINCE 2026-11-08: the weights as printed -- IPPAP per 100 000
(per_hundred_thousand), IPPI per 10 000 (per_ten_thousand) -- under the base year.
  NOTE: the text says the Ensemble fell "0,2%" on the previous quarter; p.4
  prints -2,0% (128,9 -> 126,3 is -2,0%); the table is kept.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

INDEX_NAME = "Indice de Prix des Produits Agricoles à la Production (IPPAP)"
_NUM = re.compile(r"-?\d+,\d%?|-")
_CODE = re.compile(r"^(?:\d{2}(?:\.\d{1,2}){0,3}p?,?|\d{2}\.\d{2}-\d{2}\.\d{2}|\d{2}-\d{2}|&|\d{2}\.\d{2}-)$")
_QPER = re.compile(r"\bT([1-4])-(\d{2})\b")
_YPER = re.compile(r"\b(20\d{2})\b")
_COPY_ERROR = [109.5, 93.1, 93.5, 100.6, 111.2, 98.6, 98.3, 105.9]


def _strip_codes(text: str):
    toks = text.split()
    codes = [t for t in toks if _CODE.match(t)]
    words = [t for t in toks if not _CODE.match(t)]
    return " ".join(words), codes


def _columns(header: str):
    """(period, measure) per column; a ratio header "T1-20/T4-19" is the %
    change of its numerator quarter on the denominator (p.4 summary)."""
    cols = []
    for tok in header.split():
        r = re.fullmatch(r"T([1-4])-(\d{2})/T([1-4])-(\d{2})", tok)
        m = re.fullmatch(r"T([1-4])-(\d{2})", tok)
        if r:
            a = (2000 + int(r.group(2))) * 4 + int(r.group(1))
            b = (2000 + int(r.group(4))) * 4 + int(r.group(3))
            cols.append((f"{2000 + int(r.group(2))}-Q{r.group(1)}", {1: "inflation_qoq", 4: "inflation_yoy"}[a - b]))
        elif m:
            cols.append((f"{2000 + int(m.group(2))}-Q{m.group(1)}", "index"))
        elif re.fullmatch(r"20\d{2}", tok):
            cols.append((tok, "index"))
    return cols


_SKIP = re.compile(r"agrégés \d rev1|Ensemble l'Agriculture|hoc Postes|Codes Ad.*|Code Ad hoc.*|hoc")


def _table(path, pno, header, body, level, base, out, seen, debug=False):
    periods = _columns(header)
    if len(periods) < 3:
        raise ValueError(f"{path} p.{pno}: no periods in header {header!r}")
    freq = "quarterly" if "-Q" in periods[0][0] else "annual"
    rows, pending = [], []
    for ln in body:
        if _SKIP.fullmatch(ln) or not re.search(r"[A-Za-zé]", ln) and len(ln.split()) < len(periods):
            continue                      # header fragments; chart axis values
        toks = ln.split()
        j = len(toks)
        while j > 0 and _NUM.fullmatch(toks[j - 1]):
            j -= 1
        nums = toks[j:]
        text, codes = _strip_codes(" ".join(toks[:j]))
        if len(nums) == len(periods) + 1:
            rows.append([" ".join(pending + ([text] if text else [])), codes, nums])
            pending = []
        elif nums:
            break                         # a chart / the end of the table
        elif not text:
            continue                      # a code-only line
        elif rows and not pending and (text[:1].islower() or text[:1] == "("):
            rows[-1][0] += " " + text
        else:
            pending.append(text)
    if not rows:
        raise ValueError(f"{path} p.{pno}: header but no rows")
    for label, codes, nums in rows:
        label = re.sub(r"\s+", " ", label).strip()
        if debug:
            print(pno, level, codes, "|", label, "|", nums[:3])
        vals = [C.to_number(x, decimal=",") for x in nums[1:]]
        wt = C.to_number(nums[0], decimal=",")
        if label == "Ensemble" and vals == _COPY_ERROR and periods[0][0] == "2018-Q1":
            continue                      # p.6 copy error (docstring)
        # INSTAT's ad hoc code: the poste code (01.01.01) or the sous-secteur code (01)
        adhoc = [c for c in codes if re.fullmatch(r"\d{2}(?:\.\d{2}){0,2}|\d{2}-\d{2}", c)]
        nso = (adhoc[1] if level == "POSTES" and len(adhoc) > 1 else adhoc[0]) if adhoc else ""
        by = re.search(r"\d{4}", base).group(0) if base else ""
        if wt is not None and by and (label, by, "annual", "weight") not in seen:
            # the weight, per 100 000 as printed, filed under the base year
            seen.add((label, by, "annual", "weight"))
            out.append(C.row(index_name=INDEX_NAME, index_variant="agriculture", industry=label,
                             industry_code_nso=nso, period=by, frequency="annual", measure="weight",
                             value=wt, unit="per_hundred_thousand", base_period=base, series_code=level))
        for (p, meas), v in zip(periods, vals):
            if v is None or (v == 0 and meas == "index"):
                continue
            key = (label, p, freq, meas)
            if key in seen:                # p.4's T1-19/T4-19 repeat p.6 (same values)
                continue
            seen.add(key)
            out.append(C.row(index_name=INDEX_NAME, index_variant="agriculture", industry=label,
                             industry_code_nso=nso, period=p, frequency=freq, measure=meas,
                             value=v, base_period=base, series_code=level))


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    out, seen = [], set()
    with pdfplumber.open(path) as pdf:
        base_m = re.search(r"Base\s+100\s*=\s*(\d{4})", pdf.pages[0].extract_text() or "")
        base = f"{base_m.group(1)}=100" if base_m else ""
        for pno, page in enumerate(pdf.pages, 1):
            lines = [l.strip() for l in (page.extract_text() or "").splitlines()]
            heads = [i for i, l in enumerate(lines) if "Pondérations" in l]
            for n, hdr in enumerate(heads):
                stop = heads[n + 1] if n + 1 < len(heads) else len(lines)
                # the next table's header block starts at its "Codes Ad" line
                stop = next((k for k in range(hdr + 1, stop) if lines[k].startswith("Codes Ad")), stop)
                start = heads[n - 1] + 1 if n else 0
                level = "SOUS_SECTEURS" if any("Sous-secteurs" in l for l in lines[start:hdr + 1]) else "POSTES"
                _table(path, pno, lines[hdr], lines[hdr + 1:stop], level, base, out, seen)
    if not out:
        raise ValueError(f"{path}: no IPPAP table found")
    return pd.DataFrame(out)


# ---------------------------------------------------------------- IPPI ----
IPPI_NAME = "Indices des Prix de Production dans l'Industrie (IPPI)"
_IDX = re.compile(r"-?\d+,\d")                 # an index / % change: ONE decimal
_W = re.compile(r"\d+,\d\d")                    # a weight: TWO decimals ("6 968,52")
_IPPI_CODE = re.compile(r"^(\d{2}(?:-\d{2})?)\s+(.*)$")
_HDR_JUNK = re.compile(r"^(?:Codes(?: Type)?|Divisions|d'industries|NAEMA(?: rev1)?|rev1|Codes Type Variation|"
                       r"année année|en %|NAEMA \d{4} \d{4} \d{4} / \d{4}|.*Pondérations.*|"
                       r"Libellé.*|.*\d{4} / \d{4}|\d{4} \d{4}|NAEMA rev1 en %|.*année année.*|Evolution .*)$")


def _ippi_columns(line: str):
    toks = line.split()
    months = [C.month_period(t) for t in toks]
    if sum(m is not None for m in months) >= 6:
        ms = [m for m in months if m]
        # "janv-14 févr-14 mars-14 avr-13 mai-14" (p.4): a month out of sequence
        # is a header typo -- the column is read by POSITION (p.7 prints the same
        # values under "avr-14").
        y0, m0 = int(ms[0][:4]), int(ms[0][5:])
        return [(f"{y0 + (m0 - 1 + i) // 12:04d}-{(m0 - 1 + i) % 12 + 1:02d}", "index") for i in range(len(ms))], "monthly"
    q = re.findall(r"\bT([1-4])-(\d{2})\b", line)
    if len(q) >= 4:
        return [(f"{2000 + int(y)}-Q{n}", "index") for n, y in q], "quarterly"
    return None, None


def parse_ippi(path: str) -> pd.DataFrame:
    """IPPI base 100 = 2013 (bulletin n°000, 2013-2014): monthly, quarterly and
    annual indices by type d'industrie and NAEMA rev1 division + INDICE GLOBAL.

    Rows: "<NAEMA code> <LABEL> <weight> <index ...>", weights on 10 000 with a
    space thousands separator. Labels are UPPER-CASE and wrap: a text line opens
    the next label when the line after it is a bare number row or a coded row,
    and otherwise continues the row above; a code printed on a continuation
    line ("15 ET DE CHAUSSURES") belongs to the row above it.

    The annual tables (A, B: 2013 | 2014 | variation 2014/2013 en %) give the
    annual indices and their % change (inflation_yoy, annual).
    """
    import pdfplumber
    out, seen = [], set()
    with pdfplumber.open(path) as pdf:
        lines = [l.strip() for pg in pdf.pages for l in (pg.extract_text() or "").splitlines()]
    i = 0
    while i < len(lines):
        cols, freq = _ippi_columns(lines[i])
        annual = re.fullmatch(r".*année année.*", lines[i])
        if annual and cols is None:
            cols, freq = [("2013", "index"), ("2014", "index"), ("2014", "inflation_yoy")], "annual"
        if cols is None:
            i += 1
            continue
        level = "TYPE" if any("Type" in l for l in lines[max(0, i - 3):i + 2]) else "DIVISIONS"
        body, k = [], i + 1
        while k < len(lines) and _ippi_columns(lines[k])[0] is None and not lines[k].startswith(("A-", "B-", "C-", "D-")) \
                and not re.fullmatch(r"[\d,]+", lines[k]) and not re.fullmatch(r".*année année.*", lines[k]) \
                and not lines[k].startswith("Evolution "):
            body.append(lines[k])
            k += 1
        rows, pending = [], []
        parsed = []
        for ln in body:
            if _HDR_JUNK.match(ln) or re.fullmatch(r"\d+", ln):
                parsed.append(("junk", ln))
                continue
            toks = ln.split()
            j = len(toks)
            while j > 0 and _IDX.fullmatch(toks[j - 1]):
                j -= 1
            idx = toks[j:]
            if idx and j > 0 and _W.fullmatch(toks[j - 1]):
                w_end = j - 1
                if w_end > 0 and re.fullmatch(r"\d{1,3}", toks[w_end - 1]):
                    w_end -= 1                     # "6 968,52"
                parsed.append(("row", " ".join(toks[:w_end]), idx, " ".join(toks[w_end:j])))
            elif idx:
                parsed.append(("stop", ln))        # a chart / something else
            else:
                parsed.append(("text", ln))
        n_cols = len(cols)
        for t, item in enumerate(parsed):
            kind = item[0]
            if kind == "stop":
                break
            if kind == "junk":
                continue
            if kind == "row":
                text, idx = item[1], item[2]
                if len(idx) != n_cols:
                    raise ValueError(f"{path}: {len(idx)} values for {n_cols} columns: {item}")
                m = _IPPI_CODE.match(text)
                code, label = (m.group(1), m.group(2)) if m else ("", text)
                rows.append([code, " ".join(pending + ([label] if label else [])), idx, item[3]])
                pending = []
                continue
            text = item[1]
            m = _IPPI_CODE.match(text)
            nxt = next((p for p in parsed[t + 1:] if p[0] != "junk"), None)
            if m and rows and not rows[-1][0] and not pending:
                rows[-1][0] = m.group(1)           # "15 ET DE CHAUSSURES"
                rows[-1][1] += " " + m.group(2)
            elif nxt and nxt[0] == "row" and (not nxt[1] or _IPPI_CODE.match(nxt[1])):
                pending.append(text)               # opens the next label
            elif rows and not pending:
                rows[-1][1] += " " + text          # "GAZ ET D'EAU"
            else:
                pending.append(text)
        for code, label, idx, wtxt in rows:
            label = re.sub(r"\s+", " ", label).strip()
            wt = C.to_number(wtxt, decimal=",")
            if wt is not None and (label, "2013", "annual", "weight") not in seen:
                # the weight, per 10 000 as printed ("6 968,52"), filed under the base year
                seen.add((label, "2013", "annual", "weight"))
                out.append(C.row(index_name=IPPI_NAME, industry=label, industry_code_nso=code,
                                 period="2013", frequency="annual", measure="weight", value=wt,
                                 unit="per_ten_thousand", base_period="2013=100", series_code=level))
            for (p, meas), v in zip(cols, [C.to_number(x, decimal=",") for x in idx]):
                key = (label, p, freq, meas)
                if v is None or key in seen:
                    continue
                seen.add(key)
                out.append(C.row(index_name=IPPI_NAME, industry=label, industry_code_nso=code,
                                 period=p, frequency=freq, measure=meas, value=v,
                                 base_period="2013=100", series_code=level))
        i = k
    if not out:
        raise ValueError(f"{path}: no IPPI table found")
    return pd.DataFrame(out)
