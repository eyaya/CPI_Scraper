"""Djibouti -- INSTAD Annuaire statistique, Tableau 6.2.1 "Encours de la dette
extérieure publique" (Millions de FDJ), sourced to the Direction de la Dette
Publique (Ministère de l'Économie et des Finances).

PUBLISHER: INSTAD, the statistics office, reprinting the Debt Directorate's
figures with a credit line. COVERAGE as the table states it: EXTERNAL public
debt only -- "Dette Directe (ETAT)" (the State's own borrowing) plus "Dette
avalisée (Etablissements publics)" (debt of public establishments guaranteed by
the State). No domestic debt is published in the yearbook.

Components, annual stocks: Dette Directe (ETAT) and its bilateral / multilateral
split; Dette avalisée (Etablissements publics) and its bilateral / multilateral
split; Total. "Bilatérale" and "Multilatérale" appear under BOTH blocks, so each
is prefixed with its block ("Dette directe (ETAT): Bilatérale"). The
"Variation" column is a computed percentage change and is not collected.

EDITIONS: each yearbook prints five years -- 2025: 2020-2024; 2024: 2019-2023;
2023: 2018-2022; 2022: 2017-2021; 2018 (published by DISED, INSTAD's
predecessor): 2013-2017. Together 2013-2024. The primary file is the newest
edition; older editions arrive as extras IN NEWEST-FIRST ORDER, and the newer
edition wins each year two print. One revision is visible: the 2018 edition's
2017 direct debt 99 053 (multilateral 59 255) is 99 318 (59 520) in the 2022
edition, which is what is kept.

NOT COLLECTED: Tableau 6.2.2 "Service de la dette extérieure publique" -- debt
SERVICE is a flow, and this indicator holds stocks and stock ratios only.

CHECKS: bilateral + multilateral = block, and the two blocks = Total, each to
within 1 (FDJ million rounding: 2019 guaranteed 251 402 + 45 103 = 296 505
against a printed 296 506).

CROSS-CHECK (2025 edition): Total 2024 508 887; Dette directe 2024 118 040;
Dette avalisée 2020 326 903 (bilateral 278 824). 2024 edition: Total 2019
383 206.
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd

# The caption sometimes carries its year span ("... publique (2013-2017)").
_CAPTION = re.compile(r"Tableau 6\.2\.1 : Encours de la dette ext.rieure publique[^\n]*\n"
                      r"\s*Unit. : Millions de FDJ")
_NUM = re.compile(r"^-?\d{1,3}(?: \d{3})*$")
_PCT = re.compile(r"^-?\d+(?:,\d+)?\s*%?$")
# Private-use glyphs (arrows after each Variation cell, 2025 edition).
_GLYPHS = re.compile("^[\ue000-\uf8ff\s]+$")
_BLOCKS = ("Dette Directe (ETAT)", "Dette avalisée (Etablissements publics)")


def _edition(path: str) -> list[tuple[str, str, float]]:
    with fitz.open(path) as doc:
        text = next((p.get_text() for p in doc if _CAPTION.search(p.get_text())), None)
    if text is None:
        raise ValueError(f"INSTAD 6.2.1 not found in {path}")
    # Thousands are separated by a NARROW NO-BREAK SPACE (U+202F) in recent
    # editions, and each Variation cell is followed by an arrow glyph in the
    # private-use area on a line of its own -- dropped, it carries no value.
    body = (text[_CAPTION.search(text).end():]
            .replace("\u202f", " ").replace("\xa0", " "))
    # ... or on the Variation cell's own line (2022 edition: "5,0% <arrow>").
    body = re.sub("[\ue000-\uf8ff]", "", body)
    lines = [ln.strip() for ln in body.splitlines()
             if ln.strip() and not _GLYPHS.match(ln)]
    years = []
    i = 0
    while re.fullmatch(r"20\d\d", lines[i]):
        years.append(lines[i])
        i += 1
    if len(years) != 5:
        raise ValueError(f"INSTAD 6.2.1 header: {years}")
    # Editions from 2022 add a computed "Variation" column; 2018 (DISED) has none.
    has_var = lines[i].startswith("Variation")
    while not lines[i].startswith(_BLOCKS[0][:12]):
        i += 1
    out, label, block = [], "", None
    while i < len(lines) and not lines[i].startswith("Source"):
        ln = lines[i]
        if _NUM.match(ln):
            vals = lines[i:i + 5]
            if not all(_NUM.match(v) for v in vals):
                raise ValueError(f"INSTAD 6.2.1 {label!r}: {vals}")
            lab = re.sub(r"\s+", " ", label).strip()
            if lab.startswith("Dette Directe"):
                block, comp = _BLOCKS[0], _BLOCKS[0]
            elif lab.startswith("Dette avalisée"):
                block, comp = _BLOCKS[1], _BLOCKS[1]
            elif lab in ("Bilatérale", "Multilatérale"):
                comp = f"{block}: {lab}"
            elif lab == "Total":
                comp = "Total"
            else:
                raise ValueError(f"INSTAD 6.2.1: unexpected row {lab!r}")
            for y, v in zip(years, vals):
                out.append((comp, y, float(v.replace(" ", ""))))
            i += 5                          # the five years
            if has_var:
                if not _PCT.match(lines[i]):
                    raise ValueError(f"INSTAD 6.2.1 {lab!r}: no Variation cell "
                                     f"after the values ({lines[i]!r})")
                i += 1                      # the Variation cell, not collected
            label = ""
            continue
        label = f"{label} {ln}"
        i += 1
    got = {(c, y): v for c, y, v in out}
    for y in years:
        for b in _BLOCKS:
            parts = got[(f"{b}: Bilatérale", y)] + got[(f"{b}: Multilatérale", y)]
            if abs(parts - got[(b, y)]) > 1:
                raise ValueError(f"INSTAD 6.2.1 {y}: {b} parts sum to {parts}")
        if abs(got[(_BLOCKS[0], y)] + got[(_BLOCKS[1], y)] - got[("Total", y)]) > 1:
            raise ValueError(f"INSTAD 6.2.1 {y}: blocks do not sum to Total")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    # Newest edition first: a year it prints is never overwritten by an older one.
    seen, rows = set(), []
    for p in [path, *(extras or [])]:
        for comp, y, v in _edition(p):
            if (comp, y) in seen:
                continue
            seen.add((comp, y))
            rows.append({"component": comp, "period": y, "frequency": "annual",
                         "measure": "stock", "value": v, "unit": "FDJ million",
                         "series_code": "INSTAD Annuaire T6.2.1"})
    return pd.DataFrame(rows)
