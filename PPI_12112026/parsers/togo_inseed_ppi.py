"""Togo -- INSEED, Indice de Prix de Production de l'Industrie (IPPI), base 100 en 2015.

INSEED's IPPI page (inseed.tg/indice-de-prix-de-production-de-lindustrie-ippi/)
publishes, beside the monthly "IPPI Info" notes, two WORKBOOKS that carry the
whole series since the base year, re-issued each quarter:

  "Indice mensuel de Prix de Production de l'Industrie (IPPI) de janvier 2015
   à <mois> <année>"  -- sheet "IPPI chaînés mensuels"
  "Indice trimestriel ... des Trimestres ..." -- sheet "IPPI chainés_trimestriels"

Each sheet stacks four blocks under a caption "INDICES MENSUELS|TRIMESTRIELS
CHAINES - BASE 100 EN 2015 - <level>": ENSEMBLE, TYPE D'INDUSTRIES, DIVISIONS
REGROUPEES, DIVISIONS. The header row ("Libellé ...") holds the periods
(datetimes for months, "T1-15" for quarters); one row per industry follows,
until a blank row. Values are the workbook's stored values (unrounded chained
indices), emitted as stored; "-" is a missing cell, and so is a 0 (the leather
division, CUIR..., reads 0 for every month of 2024 -- not a price level).

A label printed in two blocks (INDUSTRIES EXTRACTIVES as a type and as a
grouped division; electricity/water and "environnementales" likewise) is the
same aggregate with the same values; it is emitted once, from its first block.
The level a row comes from is kept in series_code (ENSEMBLE / TYPE /
DIVISIONS_REGROUPEES / DIVISIONS).
"""
from __future__ import annotations

import datetime as dt
import re

import pandas as pd

from . import _common as C

INDEX_NAME = "Indice de Prix de Production de l'Industrie (IPPI)"
_CAPTION = re.compile(r"INDICES\s+(MENSUELS|TRIMESTRIELS)\s+CHAIN[EÉ]S\s*-\s*BASE\s+100\s+EN\s+(\d{4})\s*-\s*(.+)$", re.I)
_LEVEL = {"ENSEMBLE": "ENSEMBLE", "TYPE D'INDUSTRIES": "TYPE",
          "DIVISIONS REGROUPEES": "DIVISIONS_REGROUPEES", "DIVISIONS": "DIVISIONS"}


def _clean(label) -> str:
    return re.sub(r"\s+", " ", str(label)).strip()


def _period(cell, freq):
    if freq == "monthly":
        if isinstance(cell, (dt.datetime, dt.date)):
            return f"{cell.year:04d}-{cell.month:02d}"
        return C.month_period(cell)
    m = re.fullmatch(r"T([1-4])-(\d{2})", str(cell).strip())
    return f"{2000 + int(m.group(2))}-Q{m.group(1)}" if m else C.quarter_period(cell)


def parse(path: str) -> pd.DataFrame:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out, seen = [], set()
    for ws in wb:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        i = 0
        while i < len(rows):
            a = rows[i][0] if rows[i] else None
            m = _CAPTION.match(_clean(a)) if a else None
            if not m:
                i += 1
                continue
            freq = "monthly" if m.group(1).upper() == "MENSUELS" else "quarterly"
            base = f"{m.group(2)}=100"
            level = _LEVEL.get(_clean(m.group(3)).upper(), _clean(m.group(3)).upper())
            # header row: the first row after the caption whose first cell starts "Libell"
            j = i + 1
            while j < len(rows) and not str(rows[j][0] or "").startswith("Libell"):
                j += 1
            if j >= len(rows):
                raise ValueError(f"{path}: no header after caption {a!r}")
            periods = [_period(c, freq) if c is not None else None for c in rows[j][1:]]
            if sum(p is not None for p in periods) < 4:
                raise ValueError(f"{path}: header after {a!r} has no periods: {rows[j][:6]}")
            k = j + 1
            while k < len(rows) and rows[k] and rows[k][0] not in (None, ""):
                label = _clean(rows[k][0])
                key = (freq, label.upper())
                if key not in seen:
                    seen.add(key)
                    for p, v in zip(periods, rows[k][1:]):
                        x = C.to_number(v)
                        # An index of 0 is not a price level: INSEED prints 0 for the
                        # leather division through 2024 (no reporting unit), then 100.
                        if p is None or x is None or x == 0:
                            continue
                        out.append(C.row(index_name=INDEX_NAME, industry=label, period=p,
                                         frequency=freq, measure="index", value=x,
                                         base_period=base, series_code=level))
                k += 1
            i = k
    wb.close()
    if not out:
        raise ValueError(f"{path}: no IPPI block found")
    return pd.DataFrame(out)
