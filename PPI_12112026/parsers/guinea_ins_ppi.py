"""Guinea -- INS "Publication des indices des prix à la production industrielle (IPPI)".

INS (Sous-direction des statistiques des entreprises) publishes the IPPI as one
cumulative PDF per quarter, each carrying the WHOLE series since the base
("Base 100 en 2019", provisional base year; Laspeyres, 227 products of 44
firms, computed with AFRISTAT):
  Tableau 1  monthly,   Ensemble + three types d'industries (B, C, D-E)
  Tableau 2  monthly,   Ensemble + divisions
  Tableau 3  quarterly, Ensemble + types d'industries
  Tableau 4  quarterly, Ensemble + divisions
  Tableau 5  annual,    Ensemble + types d'industries
  Tableau 6  annual,    Ensemble + divisions
Each table is split into one block per year (or two). Read from pdfplumber's
cell grid: periods come from the block's header cells ("Janv-19", "Août-\\n19",
"T1-19", "2019"; a header cell broken over two rows -- "Avril-" / "25" -- is
rejoined) and values are matched to them IN ORDER; a row whose count of values
differs from the header's periods is skipped and noted. Labels are kept as
printed except for case ("Industries Extractives" in the 2025 block is the
"Industries extractives" of the others). Comma decimals; a few cells print a
point (115.3), read the same.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

from . import _common as C

INDEX_NAME = "Indice des prix à la production industrielle (IPPI)"
BASE = "2019=100"
NOTES: list[str] = []


def _txt(c) -> str:
    return re.sub(r"\s+", " ", (c or "").replace("\n", " ")).strip()


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _period(cell: str):
    c = (cell or "").replace("\n", "").replace(" ", "")
    if re.fullmatch(r"(?:19|20)\d{2}", c):
        return c, "annual"
    q = C.quarter_period(c)
    if q:
        return q, "quarterly"
    m = C.month_period(c)
    if m:
        return m, "monthly"
    return None


def _header(t):
    """(index of the header row, [(period, frequency)]) or None."""
    for i, r in enumerate(t[:2]):
        cells = list(r)
        if i + 1 < len(t):          # "Avril-" over "25": rejoin
            nxt = t[i + 1]
            cells = [(c or "") + ((nxt[k] or "") if (c or "").strip().endswith("-") and k < len(nxt) else "")
                     for k, c in enumerate(cells)]
        ps = [p for p in (_period(c) for c in cells if c) if p]
        if len(ps) >= 3:
            return i, ps
    return None


def parse(local_path: str) -> pd.DataFrame:
    import pdfplumber
    NOTES.clear()
    rows, canon = [], {}
    with pdfplumber.open(local_path) as pdf:
        text = " ".join((pg.extract_text() or "") for pg in pdf.pages[:3])
        if not re.search(r"Base 100 en 2019", text):
            raise ValueError("base 'Base 100 en 2019' not printed -- check for a rebasing")
        for pno, pg in enumerate(pdf.pages, 1):
            for t in pg.extract_tables():
                h = _header(t)
                if not h:
                    continue
                hi, periods = h
                for r in t[hi + 1:]:
                    lab = next((_txt(c) for c in r if c and re.search(r"[A-Za-z]", c)), "")
                    if not lab:
                        continue
                    vals = [C.to_number(_txt(c), decimal=",") for c in r
                            if c not in (None, "") and not re.search(r"[A-Za-z]", c)]
                    if len(vals) != len(periods) or any(v is None for v in vals):
                        NOTES.append(f"p{pno}: skipped '{lab[:40]}' ({len(vals)} values, {len(periods)} periods)")
                        continue
                    lab = canon.setdefault(_fold(lab), lab)
                    for (per, freq), v in zip(periods, vals):
                        rows.append(C.row(index_name=INDEX_NAME, industry=lab, period=per,
                                          frequency=freq, measure="index", value=v, base_period=BASE))
    if not rows:
        raise ValueError("guinea_ins_ppi: nothing read")
    df = pd.DataFrame(rows)
    key = ["industry", "frequency", "period"]
    dup = df[df.duplicated(key, keep=False)]
    # The same series printed by two tables of one publication (Ensemble in
    # Tableaux 1 and 2, 3 and 4, 5 and 6): a rounding difference (<= 0.05)
    # keeps the later table's figure; a real difference (2024-Q1: 109.42 in
    # Tableau 3, 109.1 in Tableau 4) leaves the value ambiguous and BOTH are
    # dropped.
    spread = dup.groupby(key)["value"].agg(lambda x: x.max() - x.min())
    bad = set(spread[spread > 0.051].index)
    for k in sorted(bad):
        NOTES.append(f"dropped {k}: tables print different values")
    df = df[[tuple(x) not in bad for x in df[key].values]]
    return df.drop_duplicates(key, keep="last").reset_index(drop=True)
