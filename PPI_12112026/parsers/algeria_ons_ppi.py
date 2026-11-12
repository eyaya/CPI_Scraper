"""Algeria -- ONS "Indice des prix à la production industrielle" (IPPI).

A Laspeyres index, base and reference 1989 (price TTC), computed QUARTERLY
from ONS's survey of PUBLIC-sector industrial enterprises ("secteur Public
National"); older notes add an indicative PRIVATE-sector index ("donnés à
titre indicatif car le taux de réponse est faible") -- a separate index here.
Aggregates: "Industries hors hydrocarbures", "Industries manufacturières",
sectors NSA 02-14 and branches NAPR (ONS nomenclature, not ISIC: the codes
go to series_code "NSA:02" / "NAPR:07", never to industry_code_nso).

`parse_note` -- a quarterly note ("Les prix à la production industrielle au
Ne trimestre YYYY"; ons.dz, 1998 - latest). Each prints, per row, [the 1989
weight], the four quarters and the annual average of the previous year, the
quarters of the current year to date, then variations whose headers pair a
numerator and a denominator ("2T25/1T25", "2T25/2T24", "1S25/1S24"). Read:
the indices (quarterly / annual) and the q/q and y/y quarterly changes;
semester and nine-month changes have no measure here and are not read. The
header's period tokens are taken from the page, and a row is kept only when
it prints exactly as many numbers as the header has columns. Notes WITHOUT
NSA/NAPR codes (1998 - mid 2012: wrapped labels, no codes) are not read --
their quarters are republished by the coded notes and the compilations only
from 2001 / 2011 on; see SKIPPED.

`parse_compilation` -- "Collections Statistiques, Série E: Indice des prix
à la production industrielle <Y1> - <Y2>" (annual, ten-year windows, the
annex "INDICES (Y1-Y2)" and "VARIATIONS (Y1-Y2)" tables by NSA and NAPR).

Notes and compilations are read oldest first; a newer document's figure for
the same period wins.

CROSS-CHECK (verbatim): 2T25 hors hydrocarbures 1 777,9 (1T25 1 761,9,
AN24 1 784,0, q/q 0,9, y/y 0,1); 2T25 NAPR 20 phosphate 30 652,6; 3T12
manufacturières 1159,1, weight 72,40; annual 2022 hors hydrocarbures
1 785,1, y/y 13,3; 2022 NSA 05 mines 11 286,0 (+95,9).
"""
from __future__ import annotations

import os
import re
import unicodedata

import pandas as pd

from . import _common as C

BASE = "Base et référence 1989"
NAMES = {"public": "Indice des prix à la production industrielle - secteur public national",
         "private": "Indice des prix à la production industrielle - secteur privé"}
_NUM = r"-?\d{1,3}(?: \d{3})+,\d+|-?\d+,\d+|-?\d+\.\d+"
SKIPPED: list[tuple[str, str]] = []
_TOK = r"(?:[1-4]T0?\d{2}|AN0?\d{2})"
_VTOK = r"(?:[1-4]T0?\d{2}|[12]S0?\d{2}|9[Mm]0?\d{2}|12[Mm]0?\d{2})"


def _yy(s: str) -> int:
    y = int(s)
    return y + (2000 if y < 50 else 1900) if y < 100 else y


def _period(tok: str):
    """'2T25' / '1T010' -> ('2025-Q2', 'quarterly'); 'AN24' -> ('2024', 'annual')."""
    m = re.fullmatch(r"([1-4])T(\d{2,4})", tok, re.I)
    if m:
        return f"{_yy(m.group(2)):04d}-Q{m.group(1)}", "quarterly"
    m = re.fullmatch(r"AN(\d{2,4})", tok, re.I)
    if m:
        return f"{_yy(m.group(1)):04d}", "annual"
    if re.fullmatch(r"(?:19|20)\d{2}", tok):
        return tok, "annual"
    return None, None


def _row_label(line: str):
    """(series_code, label, rest) for 'NSA 02 ENERGIE 1 410,9 ...' / 'NSA02 ...' /
    'INDUSTRIES HORS ... 1 774,9'."""
    m = re.match(r"^(NSA|NAPR)\s*(\d{2})\s+(.*)$", line)
    code = ""
    if m:
        code, line = f"{m.group(1)}:{m.group(2)}", m.group(3)
    m = re.search(r"\s(" + _NUM + r")(?:\s|$)", " " + line)
    if not m:
        return None
    label = line[: m.start(1) - 1].strip(" .")
    if not label or re.search(r"\d", label[-1:]):
        return None
    return code, label, line[m.start(1) - 1:]


def _header(lines):
    """(row index after the header, index periods, variation roles, weight?) or None.

    Two layouts. Coded notes from 2009: one line of period tokens ("1T24 2T24
    3T24 4T24 AN24 1T25"), variation numerators ("1T25/") on a line above and
    denominators on a line below. Notes of 2001-2008: "1°Tri 2°Tri ... Année
    1°Tri" with the years on the next line, numerators on the same line."""
    tri = next((i for i, l in enumerate(lines) if len(re.findall(r"[1-4]\s*°\s*Tri", l)) >= 3), None)
    hi = None if tri is not None else next(
        (i for i, l in enumerate(lines) if "/" not in l and len(re.findall(r"\b" + _TOK + r"\b", l)) >= 3), None)
    if hi is not None:
        # a bare year on the period line is that year's annual average (4T13 notes: "2012 1T13 .. 2013")
        idx_tok = [x for x in re.findall(r"\b(?:" + _TOK + r"|(?:19|20)\d{2})\b", lines[hi]) if x != "1989"]
        bi = next((i for i in range(hi - 1, max(-1, hi - 4), -1) if "/" in lines[i]), None)
        before = lines[bi] if bi is not None else ""
        nums = re.findall(r"\b(" + _VTOK + r")\s?/", before)
        dens, start = [], hi + 1
        for j in range(hi + 1, min(len(lines), hi + 4)):
            dens = re.findall(r"\b(" + _VTOK + r")\b", lines[j])
            if len(dens) >= len(nums) and dens:
                start = j + 1
                break
        weight = "Poids" in before + lines[hi]
        periods = [_period(x) for x in idx_tok]
    else:
        hi = tri
        if hi is None or hi + 1 >= len(lines):
            return None
        heads = re.findall(r"([1-4])\s*°\s*Tri|(Ann[ée]e)", lines[hi])
        years = [y for y in re.findall(r"\b((?:19|20)\d{2})\b", lines[hi + 1]) if y != "1989"]
        if len(years) < len(heads):
            return None
        periods = [(f"{y}-Q{q}", "quarterly") if q else (y, "annual") for (q, a), y in zip(heads, years)]
        nums = re.findall(r"\b(" + _VTOK + r")\s?/", lines[hi])
        dens = re.findall(r"\b(" + _VTOK + r")\b", lines[hi + 1])
        weight = "Poids" in lines[hi]
        start = hi + 2
    if len(nums) != len(dens) or None in [p for p, _ in periods]:
        raise ValueError(f"variation header {nums} / {dens}, index {periods}")
    roles = []
    for n, d in zip(nums, dens):
        pn, _ = _period(n)
        pd_, _ = _period(d)
        k = None
        if pn and pd_ and pn[5:6] == "Q" and pd_[5:6] == "Q":
            k = (int(pn[:4]) * 4 + int(pn[-1])) - (int(pd_[:4]) * 4 + int(pd_[-1]))
        roles.append((pn, {1: "inflation_qoq", 4: "inflation_yoy"}.get(k)))
    return start, periods, roles, weight


def parse_note(path) -> list[dict]:
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        pages = [pg.extract_text() or "" for pg in pdf.pages]
    if not any(re.search(r"^(NSA|NAPR)\s*\d{2}\s", t, re.M) for t in pages):
        SKIPPED.append((os.path.basename(path), "no NSA/NAPR-coded table (1998-2000 layout)"))
        return out
    sector = "public"
    for t in pages:
        # titles are sometimes set with every letter doubled ("PPrriivvéé")
        if re.search(r"p{1,2}r{1,2}i{1,2}v{1,2}[eé]{1,2}", t, re.I):
            sector = "private"
        elif re.search(r"p{1,2}u{1,2}b{1,2}l{1,2}i{1,2}c{1,2}\s+n{1,2}a{1,2}t{1,2}i{1,2}o{1,2}n{1,2}a{1,2}l", t, re.I):
            sector = "public"
        lines = [l.strip() for l in t.splitlines()]
        # GUARD: "Indice Général" is the PRIVATE table's total (the public one
        # is "Industries hors hydrocarbures"); seen under "public" it means the
        # page's sector was misread, and the page is not read.
        if sector == "public" and re.search(r"^Indice\s+G[ée]n[ée]ral\s", t, re.M | re.I):
            SKIPPED.append((os.path.basename(path), "page with 'Indice Général' but no sector title"))
            continue
        try:
            h = _header(lines)
        except ValueError as e:
            raise ValueError(f"{os.path.basename(path)}: {e}")
        if h is None:
            continue
        start, periods, roles, weight = h
        ncol = int(weight) + len(periods) + len(roles)
        for l in lines[start:]:
            r = _row_label(l)
            if not r:
                continue
            code, label, rest = r
            toks = re.findall(_NUM, rest.replace(" ", " "))
            dec = "." if toks and all("." in x and "," not in x for x in toks) else ","
            vals = [C.to_number(x, decimal=dec) for x in toks]
            if len(vals) != ncol or None in vals:
                continue
            kw = dict(index_name=NAMES[sector], industry=label, base_period=BASE, series_code=code,
                      ownership=sector)
            i = 0
            if weight:
                out.append(C.row(period="1989", frequency="annual", measure="weight", value=vals[0],
                                 unit="percent", **kw))
                i = 1
            for (per, fq), v in zip(periods, vals[i:i + len(periods)]):
                out.append(C.row(period=per, frequency=fq, measure="index", value=v, **kw))
            for (per, role), v in zip(roles, vals[i + len(periods):]):
                if role:
                    out.append(C.row(period=per, frequency="quarterly", measure=role, value=v, **kw))
    return out


def parse_compilation(path) -> list[dict]:
    """The ANNEX tables only (header 'INTITULE AGREGATION' + years): indices
    or variations by NSA / NAPR, public and (N° 175) private sector; the
    1989 weight column is read when printed ("Poids")."""
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        pages = [pg.extract_text() or "" for pg in pdf.pages]
    sector = "public"
    for t in pages:
        if re.search(r"p{1,2}r{1,2}i{1,2}v{1,2}[ée]{1,2}", t, re.I):
            sector = "private"
        elif re.search(r"p{1,2}u{1,2}b{1,2}l{1,2}i{1,2}c{1,2}\s+n{1,2}a{1,2}t{1,2}i{1,2}o{1,2}n{1,2}a{1,2}l", t, re.I):
            sector = "public"
        lines = [l.strip() for l in t.splitlines()]
        h = next((i for i, l in enumerate(lines) if re.search(r"INTITULE\s+AGREGATION", l, re.I)), None)
        if h is None:
            continue
        window = " ".join(lines[max(0, h - 1): h + 2])
        nums = [re.sub(r"\s", "", y) for y in re.findall(r"((?:19|20)\s?\d\s?\d)\s?/", window)]
        weight = "Poids" in window
        if nums:
            kind, years = "inflation_yoy", nums
        else:
            kind = "index"
            years = [y for y in re.findall(r"\b(?:19|20)\d{2}\b", lines[h]) if y != "1989"]
        if len(years) < 5:
            continue
        for l in lines[h + 1:]:
            r = _row_label(l)
            if not r:
                continue
            code, label, rest = r
            vals = [C.to_number(x, decimal=",") for x in re.findall(_NUM, rest)]
            if len(vals) != len(years) + int(weight):
                continue
            kw = dict(index_name=NAMES[sector], industry=label, base_period=BASE, series_code=code,
                      ownership=sector)
            if weight:
                if kind == "index":
                    out.append(C.row(period="1989", frequency="annual", measure="weight",
                                     value=vals[0], unit="percent", **kw))
                vals = vals[1:]
            for y, v in zip(years, vals):
                out.append(C.row(period=y, frequency="annual", measure=kind, value=v, **kw))
    if not out:
        SKIPPED.append((os.path.basename(path), "no annex INDICES / VARIATIONS table read"))
    return out


def _is_compilation(p):
    b = os.path.basename(p).lower()
    return bool(re.search(r"\d{4}[-_]\d{4}|ippi0\d-1\d|csippi|collection", b))


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    SKIPPED.clear()
    files = sorted({path, *(extras or [])}, key=lambda p: os.path.basename(p).lower())
    comps = [f for f in files if _is_compilation(f) and f.lower().endswith(".pdf")]
    notes = [f for f in files if f not in comps and f.lower().endswith(".pdf")
             and re.search(r"ipp|tab", os.path.basename(f), re.I)]
    out = {}
    # compilations oldest window first, then notes in date order: newer wins
    def note_key(f):
        b = os.path.basename(f).lower()
        m = re.search(r"([1-4])t[-_]?(\d{2,4})", b)
        if not m:
            return (0, b)
        y = int(m.group(2)[-2:]) if len(m.group(2)) in (2, 3) else int(m.group(2)) % 100
        y = y + (2000 if y < 50 else 1900)
        return (y * 10 + int(m.group(1)), b)
    for f in sorted(comps, key=lambda f: re.findall(r"\d{2,4}", os.path.basename(f))[-1:]):
        for r in parse_compilation(f):
            out[(r["index_name"], r["series_code"], r["industry"], r["period"], r["frequency"], r["measure"])] = r
    for f in sorted(notes, key=note_key):
        try:
            rows = parse_note(f)
        except ValueError as e:
            SKIPPED.append((os.path.basename(f), str(e)[:160]))
            continue
        for r in rows:
            out[(r["index_name"], r["series_code"], r["industry"], r["period"], r["frequency"], r["measure"])] = r
    if not out:
        raise ValueError("algeria_ons_ppi: no rows")
    # ONE LABEL PER SERIES: ONS rewords labels between documents ("IND.AGRO-
    # ALIMENT.TABACS, ALUM." -> "INDUSTRIES AGRO-ALIMENTAIRES"); a coded row is
    # identified by its NSA / NAPR code, an aggregate by its label (case and
    # punctuation aside), and carries the NEWEST document's label.
    def ident(r):
        folded = unicodedata.normalize("NFKD", r["industry"]).encode("ascii", "ignore").decode().lower()
        return (r["index_name"], r["series_code"] or re.sub(r"[^a-z]", "", folded))
    latest = {}
    for r in out.values():                      # oldest document first
        latest[ident(r)] = r["industry"]
    final = {}
    for r in out.values():
        r["industry"] = latest[ident(r)]
        final[(ident(r), r["period"], r["frequency"], r["measure"])] = r
    return pd.DataFrame(list(final.values()))
