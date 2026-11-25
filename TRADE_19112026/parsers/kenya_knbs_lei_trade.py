"""Parser for KNBS "Leading Economic Indicators" (LEI) trade tables (Tier 3 PDF).

KNBS (www.knbs.or.ke) publishes the LEI monthly; the trade tables come from the
Kenya Revenue Authority's customs records ("Source: Kenya Revenue Authority"),
KSh million, excluding electricity and informal cross-border trade:

  Table 12  External Trade -- by month: Domestic Exports, Re-Exports, Total
            Exports, Total Imports, Total Trade (and "Volume of Home use
            Imports", not collected: the schema's import flow is the total).
            ~30 months per issue.
  Table 13(a) Major Destinations of Domestic Exports -- by month, the top ~11
            partner countries (columns).
  Table 13(b) Domestic Exports by Broad Economic Category -- 12 months, BEC
            groups + Total (the "Percentage Shares" block is not collected).
  Table 14(a) Major Origins of Imports -- by month, top partner countries.
  Table 14(b) Imports by Broad Economic Category -- 12 months, BEC + Total.

The trade table numbers have moved between issues (older issues number them
differently), so tables are found by their titles. Partner names in 13(a)/14(a)
headers are assigned to value columns by x position. A row is kept only with
exactly one figure per column. An asterisk on a year ("2026*") marks
provisional figures (newer issues revise them; the newest issue wins).
"""
from __future__ import annotations

import calendar
import os
import re

import pandas as pd

from ._common import row, to_number
from .tanzania_nbs_trade import _lines, _newest_wins

_MON = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MON.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
_MON["sept"] = 9
_NUM = re.compile(r"^-?\d{1,3}(,\d{3})*(\.\d+)?$|^-?\d+(\.\d+)?$")
_YEAR = re.compile(r"^((?:19|20)\d{2})\*?$")

_T12 = {"domestic": "domestic_export", "re": "re_export", "total exports": "export",
        "total imports": "import", "total trade": "total"}


def _words(ln):
    return [(w[0], w[2], w[4]) for w in ln]


def _vals_tail(ln):
    toks = _words(ln)
    vals = []
    while toks and (_NUM.match(toks[-1][2]) or toks[-1][2] in ("-", "–")):
        vals.insert(0, toks.pop())
    return re.sub(r"\.{2,}$", "", " ".join(t[2] for t in toks).strip()).strip(), vals


def _issue_date(path):
    n = os.path.basename(path)
    m = re.search(r"([A-Za-z]+)-(\d{4})", n.replace("Leading-Economic-Indicators-", ""))
    if m and m.group(1).lower() in _MON:
        return int(m.group(2)), _MON[m.group(1).lower()]
    return (0, 0)


def _table_lines(doc, title_rx):
    """(page number, lines from the caption to 'Source')."""
    for pno in range(doc.page_count):
        raw = doc[pno].get_text()
        if not re.search(title_rx, raw, re.I):
            continue
        lines = _lines(doc[pno])
        texts = [" ".join(w[4] for w in ln) for ln in lines]
        for i, t in enumerate(texts):
            if re.search(title_rx, t, re.I) and not re.search(r"\.{6,}", t):
                j = next((k for k in range(i + 1, len(texts))
                          if texts[k].startswith("Source") or re.match(r"^Table\s*\d", texts[k])), len(texts))
                if j - i > 6:          # not a contents-page entry
                    return pno + 1, lines[i:j], texts[i:j]
    return None, [], []


def _mult(texts):
    t = " ".join(texts[:3]).lower()
    return 1e6 if "million" in t else 1e9 if "billion" in t else None


def _monthly_rows(lines, n):
    """Yield (period, values) for 'Month v1 .. vn' lines under year lines."""
    year = None
    for ln in lines:
        toks = [w[4] for w in ln]
        if len(toks) == 1 and _YEAR.match(toks[0]):
            year = int(_YEAR.match(toks[0]).group(1))
            continue
        label, vals = _vals_tail(ln)
        mon = _MON.get(label.lower().rstrip("*"))
        if year and mon and len(vals) == n:
            yield f"{year}-{mon:02d}", vals


def _t12(doc, tag):
    pno, lines, texts = _table_lines(doc, r"Table\s*\d+\s*:\s*External Trade")
    if not lines:
        return []
    mult = _mult(texts)
    head = " ".join(texts[1:4]).lower()
    # the column order printed in every issue seen: Domestic, Re-, Total Exports, Total Imports,
    # Total Trade, Volume of Home use Imports
    # older issues set the header words in a different reading order; the
    # column order itself (Domestic, Re-, Total Exports, Total Imports, Total
    # Trade, Home use) is the same in every issue checked (2019-2026)
    if not (mult and all(k in head for k in ("domestic", "re-", "total", "home"))):
        return []
    flows = ["domestic_export", "re_export", "export", "import", "total", None]
    out = []
    for per, vals in _monthly_rows(lines, 6):
        for fl, (_, _, tok) in zip(flows, vals):
            v = to_number(tok)
            if fl and v is not None:
                out.append(row(tradeflow=fl, period=per, frequency="monthly", value=v, unit="KES",
                               unit_multiplier=mult, series_code=f"{tag} T12 p{pno}"))
    return out


def _partner(doc, title_rx, flow, tag, tab):
    pno, lines, texts = _table_lines(doc, title_rx)
    if not lines:
        return []
    mult = _mult(texts)
    if not mult:
        return []
    # value columns from the first monthly row
    first = next((ln for ln in lines if _MON.get(_vals_tail(ln)[0].lower().rstrip("*")) and _vals_tail(ln)[1]), None)
    if first is None:
        return []
    cols = [(x0 + x1) / 2 for x0, x1, _ in _vals_tail(first)[1]]
    n = len(cols)
    label_right = min(x0 for x0, _, _ in _vals_tail(first)[1]) - 2
    names = [[] for _ in cols]
    for ln in lines[1:]:
        toks = [w[4] for w in ln]
        if len(toks) == 1 and _YEAR.match(toks[0]):
            break
        for w in ln:
            x0, y0, x1, t = w[0], w[1], w[2], w[4]
            if x1 < label_right or re.search(r"KSh|Million|^1$|Period|Country/?|Countries", t):
                continue
            c = min(range(n), key=lambda k: abs(cols[k] - (x0 + x1) / 2))
            names[c].append((round(y0), x0, t))
    names = [" ".join(t for _, _, t in sorted(nm)).strip() for nm in names]
    if any(not nm for nm in names):
        return []
    out = []
    for per, vals in _monthly_rows(lines, n):
        for nm, (_, _, tok) in zip(names, vals):
            v = to_number(tok)
            if v is None:
                continue
            ptype = "group" if re.search(r"^(all )?others?\b|rest of|EU\b|COMESA|EAC\b", nm, re.I) \
                else "country"
            if re.match(r"^total", nm, re.I):
                continue
            out.append(row(tradeflow=flow, period=per, frequency="monthly", value=v, unit="KES",
                           unit_multiplier=mult, partner=nm, partner_type=ptype,
                           series_code=f"{tag} T{tab} p{pno}"))
    return out


def _bec(doc, title_rx, flow, tag, tab):
    pno, lines, texts = _table_lines(doc, title_rx)
    if not lines:
        return []
    mult = _mult(texts)
    if not mult:
        return []
    # year tokens, then a line of month abbreviations
    years, months, k0 = [], [], None
    for k, ln in enumerate(lines[1:8], start=1):
        toks = [w[4] for w in ln]
        ys = [int(_YEAR.match(t).group(1)) for t in toks if _YEAR.match(t)]
        ms = [_MON.get(t.lower().rstrip(".")) for t in toks]
        if ys:
            years = ys
        if sum(1 for m in ms if m) >= 6:
            months, k0 = [m for m in ms if m], k
            break
    if not years or not months:
        return []
    periods, y, prev = [], years[0], None
    for m in months:
        if prev is not None and m < prev:
            y += 1
        periods.append(f"{y}-{m:02d}")
        prev = m
    if int(periods[-1][:4]) != years[-1]:
        return []                   # the year labels do not match the month run
    n = len(periods)
    out = []
    for ln in lines[k0 + 1:]:
        label, vals = _vals_tail(ln)
        if re.match(r"^percentage", label, re.I):
            break
        if len(vals) != n or not label:
            continue
        total = re.match(r"^total$", label, re.I)
        if total:
            continue        # the headline comes from Table 12 (Dec-2019's BEC Totals differ from it)
        for per, (_, _, tok) in zip(periods, vals):
            v = to_number(tok)
            if v is None:
                continue
            out.append(row(tradeflow=flow, period=per, frequency="monthly", value=v, unit="KES",
                           unit_multiplier=mult, commodity=None if total else label,
                           commodity_classification="" if total else "bec",
                           series_code=f"{tag} T{tab} p{pno}"))
    return out


def parse_one(path):
    import fitz
    y, m = _issue_date(path)
    tag = f"LEI {y}-{m:02d}"
    doc = fitz.open(path)
    try:
        out = _t12(doc, tag)
        out += _partner(doc, r"Major Destinations of Domestic Exports", "domestic_export", tag, "13(a)")
        out += _bec(doc, r"Domestic Exports by Broad Economic Category", "domestic_export", tag, "13(b)")
        out += _partner(doc, r"Major Origins of Imports", "import", tag, "14(a)")
        out += _bec(doc, r"Imports by Broad Economic Category", "import", tag, "14(b)")
    finally:
        doc.close()
    return out


def parse(path, extras=None):
    files = sorted([path] + list(extras or []), key=_issue_date)
    return _newest_wins([parse_one(f) for f in files])
