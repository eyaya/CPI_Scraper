"""Benin -- INStaD, Indice de Prix de Production de l'Industrie (IPPI), chained to base 2015.

"PUBLICATION DES INDICES DE PRIX DE PRODUCTION DE L'INDUSTRIE (IPPI) DES ANNEES
DE REFERENCES ET CHAINES A L'ANNEE DE BASE 2015", quarterly (n°2026-03 =
2ème trimestre 2026, file "Publication IPPI_T2-2026.pdf"). Three tables:

  Tableau 1 : IPPI trimestriels - Type d'industries chainés à l'année de base 2015
  Tableau 2 : IPPI trimestriels - Divisions regroupées ...
  Tableau 3 : IPPI trimestriels - Divisions ...

Header: "Base | <level> T1-22 T2-22 ... T2-26" with "2015=100" under "Base";
each row prints the base column (100,0 by definition -- not emitted) then one
index per quarter. Comma decimals.

LABEL WRAPPING. A long label wraps around its own numbers ("Fabrication de
produits / 100,0 ... / alimentaires"; "Industries de production et de /
distribution d'électricité, de gaz 100,0 ... / et d'eau"). A text line before
a number line opens the label; a line starting LOWER-CASE after it continues
it; a line starting upper-case opens the next one. The number of cells must
equal 1 + the number of quarters in the header, or the row is refused.

A label printed in two tables (Ensemble, Industries extractives, electricity
and environmental industries appear at two or three levels with identical
values) is emitted once per quarter, from its first table; the level is in
series_code. A table continued under "(suite)" with later quarters is read
like any other.

Older issues (Publication IPPI Provisoire T4 2019 ...) first print section I,
"IPPI trimestriels - <level> de <année> - Année de référence <année-1>": each
year's indices on the PREVIOUS year = 100, the computation step before
chaining. Those captions do not match (no "chain") and are not emitted; the
chained section II is the published series.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

INDEX_NAME = "Indice de Prix de Production de l'Industrie (IPPI)"
_CAPTION = re.compile(r"Tableau\s+\d+\s*:\s*IPPI\s+(trimestriels|mensuels)\s*[–-]\s*(.+?)\s+chain", re.I)
_PER = re.compile(r"\bT([1-4])-(\d{2})\b")
_NUM = re.compile(r"-?\d+,\d")
_LEVEL = {"type d'industries": "TYPE", "type d’industries": "TYPE",
          "divisions regroupées": "DIVISIONS_REGROUPEES", "divisions": "DIVISIONS"}


def _split(line: str):
    """(label prefix, numbers) when the line ends in a run of numbers, else None."""
    toks = line.split()
    j = len(toks)
    while j > 0 and _NUM.fullmatch(toks[j - 1]):
        j -= 1
    if j == len(toks):
        return None
    return " ".join(toks[:j]), [C.to_number(t, decimal=",") for t in toks[j:]]


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        lines = [l.strip() for pg in pdf.pages for l in (pg.extract_text() or "").splitlines()]
    base_m = re.search(r"(\d{4})\s*=\s*100", " ".join(lines))
    base = f"{base_m.group(1)}=100" if base_m else ""
    out, seen = [], set()
    i = 0
    while i < len(lines):
        cap = _CAPTION.search(lines[i])
        if not cap:
            i += 1
            continue
        freq = "quarterly" if cap.group(1).lower().startswith("trim") else "monthly"
        level = _LEVEL.get(cap.group(2).strip().lower(), cap.group(2).strip().upper())
        j = i + 1
        while j < len(lines) and len(_PER.findall(lines[j])) < 4:
            j += 1
        periods = [f"{2000 + int(y)}-Q{q}" for q, y in _PER.findall(lines[j])]
        # A row's cells may also split across two lines (T4 2019: "imprimerie
        # et reproduction 100,0" / "100,0 100,0 ..."): numbers ACCUMULATE until
        # the row has 1 + len(periods) of them; text met meanwhile is its label.
        need = len(periods) + 1
        k, pending, rows, nums = j + 1, [], [], []
        while k < len(lines) and not _CAPTION.search(lines[k]):
            ln = lines[k]
            k += 1
            if re.fullmatch(r"\d{4}\s*=\s*100|\d+|Base|Citation recommandée.*|Benin, Publication.*|"
                            r"Source\s*:.*|II?\.\s.*", ln):
                continue
            sp = _split(ln)
            if sp:
                prefix, got = sp
                if prefix:
                    pending.append(prefix)
                nums += got
                if len(nums) > need:
                    raise ValueError(f"{path}: {len(nums)} cells for {len(periods)} quarters + base at {ln!r}")
                if len(nums) == need:
                    rows.append([" ".join(pending), nums])
                    pending, nums = [], []
            elif rows and not nums and not pending and ln[:1].islower():
                rows[-1][0] += " " + ln          # continuation of the row above
            else:
                pending.append(ln)               # opens (or, mid-row, continues) the next label
        if nums:
            raise ValueError(f"{path}: an unfinished row ({len(nums)} of {need} cells) in {cap.group(0)!r}")
        for label, nums in rows:
            label = re.sub(r"\s+;", ";", re.sub(r"\s+", " ", label)).strip()   # "déchets ; r" = "déchets; r"
            label = re.sub(r"(\w)- (\w)", r"\1-\2", label)          # "agro- alimentaires" (T2 2024)
            # a wrapped header ("Type / d'industries ... / 2015=100") left in front of the first row
            label = re.sub(r"^.*?\d{4}\s*=\s*100\s+", "", label)
            if not label:
                raise ValueError(f"{path}: a row without a label in {cap.group(0)!r}")
            for p, v in zip(periods, nums[1:]):
                if (freq, label.lower(), p) in seen:
                    continue
                seen.add((freq, label.lower(), p))
                if v is not None:
                    out.append(C.row(index_name=INDEX_NAME, industry=label, period=p, frequency=freq,
                                     measure="index", value=v, base_period=base, series_code=level))
        i = k
    if not out:
        raise ValueError(f"{path}: no IPPI table found")
    return pd.DataFrame(out)
