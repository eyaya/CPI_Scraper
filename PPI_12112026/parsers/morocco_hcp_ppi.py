"""Morocco -- HCP "Indice des prix à la production industrielle, énergétique et
minière" (IPPIEM / IPPI).

THREE GENERATIONS, all on hcp.ma:

1. BASE 2018 (from the January 2021 note): HCP's indicator workbooks
   (Google Sheets linked from the "Indicateurs IPPI" pages, the arrangement
   CPI Morocco uses): monthly 2019-01 .. latest by section (B, C excl.
   refining, D, E) and by branch (divisions 06-36), plus the annual average
   by section. `parse_workbooks`. The base-2018 monthly NOTES repeat these
   months under slightly different labels and are NOT read (one label per
   series).
2. BASE 2010 (ISIC Rev.4 sections B C D E, NMA 2010 divisions), the monthly
   notes from November 2013 to December 2020 (.docx; a few .pdf). Each note
   prints the previous and the current month and the % change between them.
   Most notes of November 2013 - May 2018 print "Base 100 : 2010" (title and
   text); those of January - April 2018 and June 2018 - December 2020 print
   no base -- same
   nomenclature, same series continuing (extractives 100,2 in both June 2018
   and December 2020), and the January 2021 note announces the move to base
   2018 -- so they are filed under the same printed base, "Base 100 : 2010".
3. OLD NOMENCLATURE (July 2007 - October 2013; .pdf, .doc, .docx): sections
   C = extractives, D = manufacturing, E = electricity and water, divisions
   11-41 (the pre-2010 NMA). These notes print NO base, so base_period is
   blank. Their section letters are NOT ISIC Rev.4 letters (C is mining
   here), so they go to `series_code` ("NMA:C"), never to industry_code_nso.

Each note: index for the previous month and the current month, and the
current month's % change ("-" = no change printed as a dash: not read).
Notes are read oldest first, so a later note's figure for a month wins.
Provisional figures carry "*" ("Indices provisoires"): read as published.
`.doc` notes (2011-2013) are read through antiword's table output.

CROSS-CHECK (verbatim): Sept 2026 C excl. refining 119,0, chemicals 141,3,
other manufacturing 217,1 (workbook = note); July 2014 refining 129,5,
manufacturing 108,6 (base 2010); Feb 2008 refining 300,2, chemicals 191,7,
manufacturing 145,5* (old); Dec 2012 refining 422,0 (old, .doc).
"""
from __future__ import annotations

import os
import re
import subprocess

import pandas as pd

from . import _common as C

INDEX_NAME = "Indice des prix à la production industrielle, énergétique et minière (IPPIEM)"
_NUM = r"-?\d{1,3}(?:[  ]\d{3})*,\d+\*?|-"


def _n(s):
    return C.to_number(str(s).replace("*", ""), decimal=",")


# ----------------------------------------------------------- workbooks ---

def parse_workbooks(paths) -> list[dict]:
    import openpyxl
    out = []
    for p in paths:
        wb = openpyxl.load_workbook(p, data_only=True)
        for ws in wb.worksheets:
            m = re.search(r"Base\s*100\s*(\d{4})", ws.title)
            # Sheet names are cut at 31 characters ("Mensuel (groupe 1) (Base 100  2"):
            # such a sheet's base is settled against the notes in `parse`.
            base = f"Base 100 : {m.group(1)}" if m else ("?" if re.search(r"Base\s*100", ws.title) else "")
            annual = "annuel" in ws.title.lower()
            rows = [r for r in ws.iter_rows(values_only=True)]
            hdr = next(i for i, r in enumerate(rows) if any(str(c).strip() in ("Mois", "Années") for c in r if c))
            cols = {j: re.sub(r"\s+", " ", str(c)).strip() for j, c in enumerate(rows[hdr])
                    if c and str(c).strip() not in ("Mois", "Années")}
            pc = next(j for j, c in enumerate(rows[hdr]) if c and str(c).strip() in ("Mois", "Années"))
            for r in rows[hdr + 1:]:
                k = r[pc]
                if k is None:
                    continue
                if annual:
                    if not re.fullmatch(r"\d{4}", str(k).strip()):
                        continue
                    period, freq = str(k).strip(), "annual"
                else:
                    period = (f"{k.year:04d}-{k.month:02d}" if hasattr(k, "year")
                              else C.month_period(str(k).strip()))
                    if not period:
                        continue
                    freq = "monthly"
                for j, label in cols.items():
                    v = C.to_number(r[j], decimal=",")
                    if v is None:
                        continue
                    out.append(C.row(index_name=INDEX_NAME, industry=label, period=period,
                                     frequency=freq, measure="index", value=v, base_period=base))
    return out


# --------------------------------------------------------------- notes ---

def _note_rows_docx(path):
    import docx
    d = docx.Document(path)
    text = "\n".join(p.text for p in d.paragraphs)
    for t in d.tables:
        head = [c.text.strip() for c in t.rows[0].cells]
        if not head or head[0] != "Code":
            continue
        months = [C.month_period(" ".join(h.split("\n")[:2])) for h in head[2:4]]
        rows = []
        for r in t.rows[1:]:
            c = [x.text.strip() for x in r.cells]
            if len(c) >= 5 and re.fullmatch(r"[A-E]|\d{2}", c[0]):
                rows.append((c[0], re.sub(r"\s+", " ", c[1]), c[2], c[3], c[4]))
        return text, months, rows
    raise ValueError(f"{os.path.basename(path)}: no 'Code | Sections et Branches' table")


def _note_rows_rtf(path):
    """Some '.doc' notes (2011-2012) are RTF files: striprtf renders the table
    as '|'-separated cells, one row per '|\n'."""
    from striprtf.striprtf import rtf_to_text
    text = rtf_to_text(open(path, encoding="cp1252", errors="replace").read())
    i = text.find("Code|")
    rows_raw = [r.split("|") for r in text[i:].split("|\n")]
    head = rows_raw[0]
    months = [C.month_period(" ".join(h.strip().split("\n")[:2])) for h in head[2:4]]
    rows = []
    for c in rows_raw[1:]:
        c = [x.strip() for x in c]
        if len(c) >= 5 and re.fullmatch(r"[A-E]|\d{2}", c[0]):
            rows.append((c[0], re.sub(r"\s+", " ", c[1]), c[2], c[3], c[4]))
    return text, months, rows


def _note_rows_doc(path):
    with open(path, "rb") as f:
        if f.read(5) == b"{\\rtf":
            return _note_rows_rtf(path)
    out = subprocess.run(["antiword", "-m", "UTF-8.txt", "-w", "0", path],
                         capture_output=True, check=True).stdout.decode("utf-8", "replace")
    lines = [l for l in out.splitlines() if l.startswith("|")]
    cells = [[c.strip() for c in l.strip("|").split("|")] for l in lines]
    hi = next(i for i, c in enumerate(cells) if c and c[0] == "Code")
    months = [C.month_period(f"{cells[hi][k]} {cells[hi + 1][k]}") for k in (2, 3)]
    rows, cur = [], None
    for c in cells[hi + 1:]:
        if len(c) < 5:
            continue
        if re.fullmatch(r"[A-E]|\d{2}", c[0]):
            cur = [c[0], c[1], c[2], c[3], c[4]]
            rows.append(cur)
        elif cur and not c[0] and c[1] and not c[2]:
            cur[1] += " " + c[1]                      # wrapped label
    return out, months, [(a, re.sub(r"\s+", " ", b), x, y, z) for a, b, x, y, z in rows]


def _note_rows_pdf(path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        text = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    m = re.search(r"DU MOIS (?:DE |D['’])\s*([A-ZÉÛÈ]+)\s+(\d{4})", text.upper())
    cur = C.month_period(f"{m.group(1)} {m.group(2)}")
    y, mo = int(cur[:4]), int(cur[5:])
    prev = f"{y - (mo == 1):04d}-{(mo - 2) % 12 + 1:02d}"
    mi = re.search(r"INDICES? DES PRIX A LA PRODUCTION PAR SECTION", text)
    i = mi.start() if mi else 0
    rows, pending = [], None
    rx = re.compile(r"^([A-E]|\d{2})(?:\s+\1)?\s+(.*?)\s*(" + _NUM + r")\s+(" + _NUM + r")\s+(" + _NUM + r")(?:\s.*)?$")
    num_only = re.compile(r"^(?:([A-E]|\d{2})\s+)?([^\d]*?)\s*(" + _NUM + r")\s+(" + _NUM + r")\s+(" + _NUM + r")(?:\s.*)?$")
    for l in text[i:].splitlines()[1:]:
        l = l.strip()
        m = rx.match(l)
        if m and m.group(1) and (m.group(3) != "-" or m.group(4) != "-"):
            rows.append([m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)])
            pending = None
            continue
        mc = re.match(r"^([A-E]|\d{2})(?=\s|$)(?:\s+\1)?(?:\s+([A-Za-zÀ-ÿ’'].*?))?\s*(?:[؀-ۿﭐ-﻿].*)?$", l)
        if mc and not re.search(r"\d,\d", l):
            pending = [mc.group(1), mc.group(2) or ""]
            continue
        mn = num_only.match(l)
        if mn and pending and not mn.group(1):
            rows.append([pending[0], (pending[1] + " " + mn.group(2)).strip(), mn.group(3), mn.group(4), mn.group(5)])
            pending = None
        if l.startswith("* Indices") or l.startswith("Source"):
            break
    return text, [prev, cur], [tuple(r) for r in rows]


def _note(path):
    ext = path.lower().rsplit(".", 1)[-1]
    text, months, rows = {"docx": _note_rows_docx, "doc": _note_rows_doc,
                          "pdf": _note_rows_pdf}[ext](path)
    if not rows or None in months:
        raise ValueError(f"{os.path.basename(path)}: no rows / months ({months})")
    secs = {}
    for code, label, *_ in rows:
        if code.isalpha():
            secs.setdefault(code, label)
    old = re.search(r"extractiv", secs.get("C", ""), re.I) is not None
    printed = re.search(r"BASE\s*100\s*:\s*(\d{4})", text, re.I)
    if old:
        base = ""
    elif printed:
        base = f"Base 100 : {printed.group(1)}"
    elif "2013-10" <= months[1] <= "2020-12":
        base = "Base 100 : 2010"     # June 2018 - December 2020: see the docstring
    elif months[1] >= "2021-01":
        base = "Base 100 : 2018"     # notes after the January 2021 rebasing
    else:
        base = ""
    return months, rows, base, old


SKIPPED: list[tuple[str, str]] = []      # (file, reason) of notes not read, filled by parse_notes
B18: dict = {}                           # (label, period) -> value printed by the base-2018 notes


def _narrow(label: str) -> bool:
    """A label that EXCLUDES something ("Industries manufacturières hors
    raffinage de pétrole", printed for C from 2016) is a different series from
    the full section under the same code."""
    return bool(re.search(r"\bhors\b|exclu|sauf", str(label), re.I))


def _words(label: str) -> set:
    t = re.sub(r"\(cid:\d+\)", " ", str(label).lower())
    return set(re.findall(r"[a-zà-ÿ]{4,}", t))


def parse_notes(paths) -> list[dict]:
    """Table notes (.docx / .doc) first, then PDF notes. A PDF's text layer can
    interleave a wrapped label with its neighbour's numbers (July 2007 files
    "25 ... plastiques Fabrication d'autres produits minéraux 116,1 ..."), so
    a PDF row is kept only when every word of its label belongs to the label
    the table notes print for that code (same base); a PDF with
    more than three mismatching rows is not read at all (SKIPPED)."""
    SKIPPED.clear()
    notes = []
    for p in sorted(paths, key=lambda f: os.path.basename(f)):
        try:
            notes.append((p, *_note(p)))
        except ValueError as e:
            SKIPPED.append((os.path.basename(p), str(e)[:160]))
    canon = {}
    for p, (prev, cur), rows, base, old in sorted(notes, key=lambda n: n[1][1]):
        if not p.lower().endswith(".pdf"):
            for code, label, *_ in rows:
                canon[(old, base, code, _narrow(label))] = label
    out = {}
    B18.clear()
    for p, (prev, cur), rows, base, old in notes:
        if base.endswith("2018"):
            # base 2018 comes from the workbooks; the notes only VERIFY them
            for code, label, a, b, var in rows:
                for per, v in ((prev, _n(a)), (cur, _n(b))):
                    if v is not None:
                        B18[(re.sub(r"\W+", "", label.lower()), per)] = v
            continue
        if p.lower().endswith(".pdf"):
            keep, miss = [], 0
            for r in rows:
                c = (canon.get((old, base, r[0], _narrow(r[1])))
                     or canon.get((old, base, r[0], False)))
                # every word of the PDF's (possibly partial) label must belong
                # to the code's label -- a neighbour's words mean misalignment
                if c is None or not _words(r[1]) <= _words(c):
                    miss += 1
                else:
                    keep.append(r)
            if miss > 3:
                SKIPPED.append((os.path.basename(p), f"{miss} rows' labels do not match their codes"))
                continue
            rows = keep
        ok = bad = 0
        recs = []
        for code, label, a, b, var in rows:
            va, vb, vv = _n(a), _n(b), _n(var)
            kw = dict(index_name=INDEX_NAME, industry=canon.get((old, base, code, _narrow(label)), label),
                      frequency="monthly",
                      base_period=base, industry_code_nso="" if old else code,
                      series_code=f"NMA:{code}" if old else "")
            if va is not None:
                recs.append(C.row(period=prev, measure="index", value=va, **kw))
            if vb is not None:
                recs.append(C.row(period=cur, measure="index", value=vb, **kw))
            if vv is not None:
                recs.append(C.row(period=cur, measure="inflation_mom", value=vv, **kw))
                if va and vb:
                    ok += abs((vb / va - 1) * 100 - vv) <= 0.15
                    bad += abs((vb / va - 1) * 100 - vv) > 0.15
        # COLUMN ORDER PROOF: previous, current, change -- the change must fit.
        if bad > max(1, ok // 5):
            SKIPPED.append((os.path.basename(p), f"{bad} rows' % change does not fit (previous, current)"))
            continue
        for r in recs:
            out[(r["industry_code_nso"], r["series_code"], _narrow(r["industry"]), r["period"],
                 r["measure"], r["base_period"])] = r
    # ONE LABEL PER SERIES: the label the newest TABLE note prints for the code.
    return list(out.values())


# ---------------------------------------------------------------- entry ---

def _is_fr_note(p: str) -> bool:
    b = os.path.basename(p).lower()
    return (b.endswith((".pdf", ".doc", ".docx")) and not re.search(r"(_ar_?|\dar\d?)\.(pdf|docx?)$", b)
            and "communique" not in b)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = {path, *(extras or [])}
    wbs = sorted(f for f in files if f.lower().endswith(".xlsx"))
    notes = [f for f in files if _is_fr_note(f)]
    notes_rows = parse_notes(notes)
    wb_rows = parse_workbooks(wbs)
    # A truncated sheet name hides the base: it is the base 2018 only if the
    # sheet's figures ARE the base-2018 notes' figures (same label, same month).
    unk = [r for r in wb_rows if r["base_period"] == "?"]
    if unk:
        hit = miss = 0
        for r in unk:
            v = B18.get((re.sub(r"\W+", "", r["industry"].lower()), r["period"]))
            if v is not None:
                hit += abs(v - r["value"]) < 1e-9
                miss += abs(v - r["value"]) >= 1e-9
        if hit < 20 or miss > hit / 20:
            raise ValueError(f"truncated-base sheets: {hit} values equal the base-2018 notes, {miss} differ")
        for r in unk:
            r["base_period"] = "Base 100 : 2018"
    rows = wb_rows + notes_rows
    if not rows:
        raise ValueError("morocco_hcp_ppi: no rows")
    return pd.DataFrame(rows)


# A % change carries the base of its index (set from this output; see _base_carry).
from ._base_carry import carry_base  # noqa: E402
parse = carry_base(parse)
