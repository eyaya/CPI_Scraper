"""Comoros — Ministère des Finances et du Budget, Direction de la Dette
Publique (DDP), ANNUAL "Bulletin de la dette" (2022, 2024 editions), annex
"Indicateurs et statistiques de la Dette", millions FC (KMF million).

ROUTE. finances.gouv.km did not answer on 2026-10-14; these are Wayback `id_`
copies of the ministry's own uploads. The 2023 edition is not read (its text
layer drops most cells of the creditor tables); the June 2024 capture is
truncated at 1 MiB.

READ: four-year tables of year-end outstanding debt, by creditor --
  Tableau 1 multilatéraux (FMI, FAD, IDA, BID, FIDA, BADEA, OPEP, TDB, Total)
  Tableau 1 bilatéraux (BPI France, F. Saoud, Koweït, Exim Bank Inde, Total)
  Tableau 3 dette garantie extérieure / intérieure       (coverage: guarantees)
  Tableau 4 instruments de trésorerie, Tableau 5 dette bancaire intérieure
Coverage per row: the creditor, treasury and bank tables are central
government debt; the guarantee tables are the State's guarantees.

A TABLE IS READ ONLY IF IT IS COMPLETE AND ADDS UP. Thousands are grouped with
spaces ("8 358 12 000 11 770"), so a row's text can split several ways; every
split into exactly four numbers (a 1-3 digit head followed by 3-digit groups)
is enumerated, and the one combination of row splits for which every column
sums to the printed Total (to 2, rounding) is kept -- it must be unique.
A table with an empty cell (a row with fewer than four numbers: "Bon du
trésor 700 700 1 000"), a non-year column ("juin-22") or no unique
reconciliation is skipped whole, never partly guessed.

Each edition keeps its own series code; the editions revise (bilateral 2021:
38 425 in 2022, 38 426 in 2024).
"""
from __future__ import annotations

import itertools
import os
import re

import pandas as pd
import pdfplumber

_TABLES = [
    # (caption regex, first-header word, component prefix, coverage)
    (r"Tableau ?1 ?: ?Évolution ?de ?l’encours ?par ?créanciers ?multilatéraux",
     "Multilatéraux", "Dette multilatérale", "cg"),
    (r"Tableau ?1 ?: ?Évolution ?de ?l’encours ?par ?créanciers ?bilatéraux",
     "Bilatéraux", "Dette bilatérale", "cg"),
    (r"Dette Garantie extérieure", "Dette Garantie extérieure", "Dette garantie extérieure", "gar"),
    (r"Dette Garantie intérieure", "Dette Garantie intérieure", "Dette garantie intérieure", "gar"),
    (r"Tableau ?4 ?: ?Évolution ?des ?instruments ?de ?trésorerie",
     "Instruments de trésorerie", "Instruments de trésorerie", "cg"),
    (r"Tableau ?5 ?: ?Dette ?bancaire", "Dettes bancaires", "Dette bancaire intérieure", "cg"),
]
_COV = {"cg": "Central government debt (administration centrale), external and domestic",
        "gar": "Dette garantie par l'Etat (guarantees; not central-government debt)"}


def _splits(tokens: list[str], n: int) -> list[list[float]]:
    """Every way to read `tokens` as exactly n space-grouped numbers."""
    out = []

    def rec(i, acc):
        if len(acc) == n:
            if i == len(tokens):
                out.append(acc)
            return
        if i >= len(tokens) or not re.fullmatch(r"\d+", tokens[i]):
            return
        if len(tokens[i]) > 3:                      # ungrouped ("39035")
            rec(i + 1, acc + [float(tokens[i])])
            return
        j = i + 1
        rec(j, acc + [float(tokens[i])])
        while j < len(tokens) and re.fullmatch(r"\d{3}", tokens[j]):
            j += 1
            rec(j, acc + [float("".join(tokens[i:j]))])
    rec(0, [])
    return out


def _table(lines: list[str], head: str):
    i = next((k for k, l in enumerate(lines) if l.startswith(head + " ")), None)
    if i is None:
        return None
    years = lines[i][len(head):].split()
    if len(years) != 4 or not all(re.fullmatch(r"20\d\d", y) for y in years):
        return None
    rows = []
    for l in lines[i + 1:]:
        if l.startswith("Source") or l.startswith("Figure") or l.startswith("Tableau"):
            break
        if re.fullmatch(r"\s*\d{1,3}\s*", l):
            continue                                 # a page number (table spans a page)
        m = re.match(r"^([^\d]+?)\s+([\d ]+)$", l.strip())
        if not m:
            if re.search(r"\d", l) and not re.match(r"^\(", l.strip()):
                return None                          # a row we cannot read
            continue
        rows.append((m.group(1).strip(), m.group(2).split()))
    if not rows or rows[-1][0] != "Total":
        return None
    cands = [_splits(toks, 4) for _, toks in rows]
    if any(not c for c in cands):
        return None                                  # an incomplete row
    good = []
    for combo in itertools.product(*cands):
        parts, total = combo[:-1], combo[-1]
        if all(abs(sum(p[j] for p in parts) - total[j]) <= 2 for j in range(4)):
            good.append(combo)
            if len(good) > 1:
                return None
    if len(good) != 1:
        return None
    return years, [(lab, vals) for (lab, _), vals in zip(rows, good[0])]


def _read(path: str) -> list[dict]:
    m = re.search(r"(20\d\d)", os.path.basename(path))
    edition = m.group(1) if m else "?"
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    lines = text.splitlines()
    out, read = [], []
    for cap, head, prefix, cov in _TABLES:
        if not re.search(cap, text):
            continue
        t = _table(lines, head)
        if t is None:
            print(f"  [comoros annual {edition}] {prefix}: incomplete or ambiguous -- skipped")
            continue
        read.append(prefix)
        years, rows = t
        for lab, vals in rows:
            comp = prefix if lab == "Total" else f"{prefix}: {lab}"
            out += [{"coverage": _COV[cov], "component": comp, "period": y,
                     "frequency": "annual", "measure": "stock", "value": v,
                     "unit": "KMF million",
                     "series_code": f"DDP Bulletin de la dette {edition} (annexes)"}
                    for y, v in zip(years, vals)]
    if not read:
        raise ValueError(f"DDP Comores: no readable annex table in {path}")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        rows += _read(p)
    return pd.DataFrame(rows)
