"""Gabon — Direction Générale de la Dette (DGD), monthly "Situation à fin
<mois> <année>" reports (dette.ga, "Rapport statistique"), January 2010 ..
November 2025.

Each report is mostly debt SERVICE (flows; not collected). The page read is
the DMFAS/SYGADE stock summary, titled
    "RESUME ENCOURS DE LA DETTE PUBLIQUE AU dd/mm/yyyy"   (most years)
    "RESUME ENCOURS AU dd/mm/yyyy"                        (2010)
    "DETAIL ENCOURS DE LA DETTE PUBLIQUE AU dd/mm/yyyy"   (2021)
in "monnaie nationale / xaf millions", at the month-end exchange rate. Many
reports (most non-quarter-end months of 2010-2017, one in 2016 and 2025)
carry no stock page; they give no row. The period is the date ON THE PAGE,
never the filename's: the file posted as May 2018 holds the 31/05/2020 page,
and the August 2018 report also reprints the 30/06/2018 page.

THE PAGE IS A LABEL / AMOUNT LIST, sometimes indented and sometimes flat (2010
prints every label at one x), and labels repeat under different parents
(PCOD, MULTILATERALE and COMMERCIALE sit under both GARANTIE and DIRECTE). The
hierarchy is therefore rebuilt from the section words, not from geometry:
    G.TOTAL
      EXTERIEURE
        GARANTIE | DIRECTE | NON GARANTIE        (section headers)
          <creditor class>                       (until the next header)
            Commerciale Assurée / Non Assurée    (under COMMERCIALE)
      INTERIEURE
        <instrument>
and VERIFIED arithmetically on every page: each node equals the sum of its
children (to 0,05 XAF million), G.TOTAL = EXTERIEURE + INTERIEURE. A page that
does not reconcile raises. `component` is the printed path, e.g.
"EXTERIEURE > DIRECTE > BILATERALE". A "-" cell is printed as nil: no row is
written for it (it counts as 0 in the checks).

Where a month is printed by more than one file, the later file wins (files are
read in filename-date order, the primary last).
"""
from __future__ import annotations

import os
import re

import fitz  # PyMuPDF
import pandas as pd

_TITLE = re.compile(r"(?:RESUME|DETAIL) ENCOURS (?:DE LA DETTE PUBLIQUE )?AU (\d\d)/(\d\d)/(\d{4})")
_VAL = re.compile(r"^(?:\d{1,3}(?: \d{3})*,\d{2}|-)$")
_SECTIONS_EXT = {"GARANTIE", "DIRECTE", "NON GARANTIE"}
_SERIES = "DGD Situation mensuelle: résumé encours (SYGADE)"
_TOL = 0.05
# PUBLISHED INCONSISTENCIES, kept and pinned: (period, node whose printed
# amount is not the sum of its printed parts).
_KNOWN = {
    # INTERIEURE printed 977 995,25; its four lines sum to 1 011 772,77 and
    # G.TOTAL 4 108 715,68 = EXTERIEURE + that sum.
    ("2017-06", "INTERIEURE"),
    ("2017-06", "G.TOTAL"),
    # Mar-Dec 2022: the "Commerciale Assurée / Non Assurée" lines do not add
    # to COMMERCIALE (in March both print 200 697,09 against 200 702,23).
    *{(f"2022-{m:02d}", "EXTERIEURE > DIRECTE > COMMERCIALE") for m in range(3, 13)},
}
_MAX_SUMMARY_ROWS = 30   # a longer page is the per-creditor DETAIL listing


class _Detailed(ValueError):
    pass


def _num(s: str) -> float:
    return 0.0 if s == "-" else float(s.replace(" ", "").replace(",", "."))


def _lines(page) -> list[tuple[float, float, str]]:
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            # Thousands are separated by U+0020, U+00A0 or U+202F by year.
            s = re.sub(r"[   ]", " ",
                       "".join(sp["text"] for sp in ln["spans"])).strip()
            if s:
                out.append((ln["bbox"][1], ln["bbox"][0], s))
    return out


def _page_rows(page) -> list[tuple[str, str]]:
    """(label, value-text) in reading order, between MONTANT and the footer."""
    lines = _lines(page)
    top = next((y for y, x, s in lines if s == "MONTANT"), None)
    if top is None:
        raise ValueError("no MONTANT header")
    body = [(y, x, s) for y, x, s in lines if y > top + 1 and y < 790
            and not _TITLE.search(s) and not s.startswith("(")]
    vals = [(y, x, s) for y, x, s in body if _VAL.match(s)]
    labs = sorted([(y, x, s) for y, x, s in body if not _VAL.match(s)
                   and not re.match(r"^(SYGADE|DGCP|DGD/|PAGE|Page|EDITE|Edit)", s)])
    # Each amount belongs to the NEAREST label to its left (amounts sit a point
    # or two off their label's baseline in some years, and a wrapped label --
    # "Commerciale Non" / "Assurée" -- straddles its amount). A label that
    # receives no amount continues the label above it.
    owner: dict[int, list[str]] = {}
    for vy, vx, vs in vals:
        cand = [(abs(vy - y), i) for i, (y, x, _) in enumerate(labs) if x < vx and abs(vy - y) <= 8]
        if not cand:
            raise ValueError(f"amount {vs!r} has no label")
        owner.setdefault(min(cand)[1], []).append(vs)
    rows = []
    for i, (y, x, s) in enumerate(labs):
        v = owner.get(i)
        if v is None:
            if not rows:
                raise ValueError(f"label without amount: {s!r}")
            rows[-1] = (rows[-1][0] + " " + s, rows[-1][1])
            continue
        if len(v) != 1:
            raise ValueError(f"{s!r}: {len(v)} amounts {v}")
        rows.append((s, v[0]))
    return rows


def _tree(rows: list[tuple[str, str]], period: str) -> list[tuple[str, str, str]]:
    """-> (path, parent_path, value-text), checked to reconcile."""
    if len(rows) > _MAX_SUMMARY_ROWS:
        raise _Detailed(f"{len(rows)} rows: a per-creditor listing, not the summary")
    out, ext_sec, last_comm = [], None, None
    block = None
    for lab, v in rows:
        if lab == "G.TOTAL":
            path, parent = "G.TOTAL", None
        elif lab in ("EXTERIEURE", "INTERIEURE"):
            block, ext_sec, last_comm = lab, None, None
            path, parent = lab, "G.TOTAL"
        elif block == "EXTERIEURE" and lab in _SECTIONS_EXT:
            ext_sec, last_comm = f"EXTERIEURE > {lab}", None
            path, parent = ext_sec, "EXTERIEURE"
        elif lab.startswith("Commerciale ") and last_comm:
            path, parent = f"{last_comm} > {lab}", last_comm
        elif block == "EXTERIEURE" and ext_sec:
            path, parent = f"{ext_sec} > {lab}", ext_sec
            last_comm = path if lab == "COMMERCIALE" else None
        elif block == "INTERIEURE":
            path, parent = f"INTERIEURE > {lab}", "INTERIEURE"
        else:
            raise ValueError(f"cannot place {lab!r}")
        out.append((path, parent, v))
    paths = [p for p, _, _ in out]
    if len(set(paths)) != len(paths) or "G.TOTAL" not in paths:
        raise ValueError(f"duplicate or missing nodes: {paths}")
    val = {p: _num(v) for p, _, v in out}
    for node in val:
        kids = [p for p, par, _ in out if par == node]
        off = bool(kids) and abs(sum(val[k] for k in kids) - val[node]) > _TOL
        if off != ((period, node) in _KNOWN) and (off or (period, node) in _KNOWN):
            if not off:
                raise ValueError(f"pinned inconsistency {node} no longer present")
            raise ValueError(f"{node} {val[node]:.2f} != sum of {len(kids)} parts "
                             f"{sum(val[k] for k in kids):.2f}")
    return out


def _read(path: str) -> list[dict]:
    """Every stock-summary page in the file, one per date: some reports print
    it twice (the second copy with English number formatting, 2019-09), and
    the first copy that reads is used."""
    rows, done, fails = [], set(), {}
    with fitz.open(path) as doc:
        for page in doc:
            m = _TITLE.search(page.get_text())
            if not m:
                continue
            dd, mm, yyyy = m.groups()
            period = f"{yyyy}-{mm}"
            if period in done:
                continue
            try:
                tree = _tree(_page_rows(page), period)
            except _Detailed as e:
                print(f"  [DGD Gabon] {os.path.basename(path)} {period}: {e} -- skipped")
                done.add(period)
                continue
            except ValueError as e:
                fails[period] = e
                continue
            done.add(period)
            fails.pop(period, None)
            for comp, _, v in tree:
                if v == "-":
                    continue
                rows.append({"component": comp, "period": period,
                             "frequency": "monthly", "measure": "stock",
                             "value": _num(v), "unit": "XAF million",
                             "series_code": _SERIES})
    for period, e in fails.items():
        if period not in done:
            raise ValueError(f"DGD Gabon {os.path.basename(path)} ({period}): {e}")
    return rows


def _order(path: str) -> tuple:
    m = re.search(r"(20\d\d)_(\d\d)", os.path.basename(path))
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = sorted(set(extras or []) - {path}, key=_order) + [path]
    rows = []
    for f in files:
        rows += _read(f)
    if not rows:
        raise ValueError("DGD Gabon: no stock summary page in any report")
    df = pd.DataFrame(rows)
    df = df.drop_duplicates(["component", "period"], keep="last")
    return df.reset_index(drop=True)
