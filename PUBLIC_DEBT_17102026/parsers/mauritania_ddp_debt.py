"""Mauritania — Ministère des Affaires Economiques et des Finances, Direction de
la Dette Publique (DDP), quarterly "Bulletin Statistique" of the public debt,
Tableau 1 "Encours de la dette publique, Tirages / Emissions et Service de la
dette".

PUBLISHER: the DDP (data from its SYGADE debt-management system, domestic
Treasury securities reconciled with the DGTCP and the BCM).

COVERAGE, as the bulletin states it (section I, "Champ de couverture"): the
domestic and external debt of the PUBLIC SECTOR made up of the central
administration, the Banque Centrale de Mauritanie (BCM) and the SNIM
(state mining company); stocks at nominal value, EXCLUDING the IMF SDR
allocations; guarantees are contingent liabilities, not debt.

WHAT ONE ISSUE GIVES: the stock lines of Tableau 1 -- Dette Totale, Dette
Extérieure, Dette Intérieure -- for the four previous year-ends (annual) and
the current quarter-end ("30 septembre 2025" -> quarterly 2025-Q3), each in
USD million AND MRU million (stocks converted at the end-of-period rate, as the
bulletin states). The flow lines (drawings/issues, debt service, principal,
interest) are not stocks and are not collected. Checked every issue: external
+ domestic = total, in both currencies, in every column (to 0.02).

NUMBERS: thousands are space-separated and every value carries two decimals
("182 553,42"), so each value ends at its ",dd" -- read by that pattern.

NOT COLLECTED: Tableaux 2-12 (projections, flows, and the creditor / currency
/ rate breakdowns, whose text layer is the chart's garbled letter-spacing).

CROSS-CHECK (T4-2025 issue): total public debt at 31 December 2025
196 333,95 MRU million (4 924,35 USD million); external 161 973,37; domestic
34 360,59; end-2021 total 182 553,42 MRU million.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_MONTHS = {"janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5,
           "juin": 6, "juillet": 7, "août": 8, "septembre": 9, "octobre": 10,
           "novembre": 11, "décembre": 12}
_VAL = re.compile(r"\d{1,3}(?: \d{3})*,\d{2}")
_ROWS = ["Dette Totale", "Dette Extérieure", "Dette Intérieure"]


def _parse_one(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        text = next((t for p in pdf.pages if (t := p.extract_text() or "")
                     and "Tableau 1" in t and "Dette Totale" in t
                     and "USD MRU" in t), None)
    if text is None:
        raise ValueError("Mauritania DDP: Tableau 1 not found")
    lines = text.splitlines()
    hdr = next(l for l in lines if re.match(r"\s*20\d\d 20\d\d", l))
    years = re.findall(r"\b(20\d\d)\b", hdr)
    m = re.search(r"(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|"
                  r"septembre|octobre|novembre|décembre)\s+(20\d\d)", hdr)
    if not m:
        raise ValueError(f"Mauritania DDP: no quarter-end date in header {hdr!r}")
    q = (_MONTHS[m.group(2)] - 1) // 3 + 1
    cols = [("annual", y) for y in years[:-1]] + [("quarterly", f"{m.group(3)}-Q{q}")]
    if years[-1] != m.group(3) or len(cols) != 5:
        raise ValueError(f"Mauritania DDP: unexpected header {hdr!r}")

    got = {}
    for name in _ROWS:
        line = next(l for l in lines if l.startswith(name + " "))
        vals = [float(v.replace(" ", "").replace(",", ".")) for v in _VAL.findall(line)]
        if len(vals) != 10:
            raise ValueError(f"Mauritania DDP: {name} reads {len(vals)} values")
        got[name] = vals
    for i in range(10):
        if abs(got["Dette Extérieure"][i] + got["Dette Intérieure"][i]
               - got["Dette Totale"][i]) > 0.02:
            raise ValueError(f"Mauritania DDP: external + domestic != total (col {i})")

    rows = []
    for name, vals in got.items():
        for k, (freq, period) in enumerate(cols):
            for j, unit in enumerate(("USD million", "MRU million")):
                rows.append({"component": name, "period": period, "frequency": freq,
                             "measure": "stock", "value": vals[2 * k + j],
                             "unit": unit, "series_code": "DDP Bulletin Statistique, Tableau 1"})
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = _parse_one(path)
    for p in extras or []:
        try:
            rows += _parse_one(p)
        except (ValueError, StopIteration) as e:
            print(f"[mauritania_ddp_debt] skipped {p}: {e}")
    df = pd.DataFrame(rows)
    # Each issue repeats the past year-ends; the primary (newest) issue is
    # read first and wins on any revision.
    key = ["component", "period", "frequency", "unit"]
    return df.drop_duplicates(key, keep="first").reset_index(drop=True)
