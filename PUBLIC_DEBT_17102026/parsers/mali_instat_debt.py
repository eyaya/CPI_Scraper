"""Mali — INSTAT "Annuaire statistique du Mali", chapter "Dette publique",
Tableau "Statistiques de la dette publique" (source: DGDP, Direction Générale
des Dettes Publiques).

THE ROUTE. The Ministry of Finance's hosts (finances.gouv.ml, dgdp.finances.gouv.ml,
www.dgdp.ml, dgtcp.gouv.ml) give no response (checked 2026-10-08 and
2026-10-12). INSTAT's yearbook reprints the DGDP's stocks, credited table by
table ("Sources: DGDP"), so the publisher recorded is INSTAT and the figures
are the DGDP's.

COLLECTED (2024 edition, 2020-2024, FCFA milliards): public debt at end of
period, external debt outstanding, domestic debt outstanding. Debt SERVICE
rows are flows, not stocks, and the schema holds stocks only; the IMF-sourced
"tirages" row is not a national figure. Both are left out.

PUBLISHED INCONSISTENCY KEPT: for 2024 the external and domestic stocks sum to
6 799,3 against a printed total of 6 809,3. 2020-2023 add up exactly. The gap
is pinned (`_KNOWN_GAPS`); any other gap raises.

OLDER EDITIONS NOT USED. The 2021 edition prints 2015-2016 external debt equal
to total debt, 2019 external as "38011", and a 2018 total below its own
external stock; the 2014/2017 editions carry a Treasury (DNTCP) series whose
2015 and 2017 values are INSTAT estimates. None can be read as published
without choosing which printed figure is wrong.

CROSS-CHECK: end-2024 total 6 809,3; external 3 514,6; domestic 3 284,7;
end-2020 total 4 756,9949.
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd

_CAPTION = re.compile(r"Tableau \d+ ?: ?Statistiques de la dette publique")
_ROWS = [  # printed label start -> component
    ("Dette publique en fin de", "Public debt, end of period"),
    ("Encours de la dette extérieure", "External debt outstanding"),
    ("Encours de la dette intérieure", "Domestic debt outstanding"),
]
_NUM = re.compile(r"^\d{1,3}(?: \d{3})*(?:,\d+)?$")
_KNOWN_GAPS = {"2024": 10.0}       # total - (external + domestic), as printed


def _num(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def parse(path: str, extras=None) -> pd.DataFrame:
    doc = fitz.open(path)
    page = next((p for p in doc if _CAPTION.search(p.get_text())
                 and "Encours de la dette" in p.get_text()
                 and "....." not in p.get_text()), None)
    if page is None:
        raise ValueError("INSTAT Mali: debt table not found")
    # Some cells are padded with NO-BREAK spaces (" 5 918,9 ").
    text = page.get_text().replace("\xa0", " ").replace("\u202f", " ")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines() if ln.strip()]
    i = next(k for k, ln in enumerate(lines) if _CAPTION.search(ln))
    years = []
    for ln in lines[i + 1:]:
        if re.fullmatch(r"20\d\d", ln):
            years.append(ln)
        elif years:
            break
    if len(years) < 3:
        raise ValueError(f"INSTAT Mali: header years {years}")

    values = {}
    for label, comp in _ROWS:
        k = next(j for j, ln in enumerate(lines) if ln.startswith(label))
        nums = []
        for ln in lines[k + 1:]:
            if _NUM.match(ln):
                nums.append(_num(ln))
                if len(nums) == len(years):
                    break
            elif ln.startswith(("Encours", "Service", "Dette")):
                break
        if len(nums) != len(years):
            raise ValueError(f"INSTAT Mali: {comp} reads {nums}")
        values[comp] = dict(zip(years, nums))

    tot, ext, dom = (values[c] for _, c in _ROWS)
    for y in years:
        gap = round(tot[y] - ext[y] - dom[y], 4)
        if abs(gap - _KNOWN_GAPS.get(y, 0.0)) > 0.02:
            raise ValueError(f"INSTAT Mali {y}: total - (external + domestic) = "
                             f"{gap}, expected {_KNOWN_GAPS.get(y, 0.0)}")

    rows = [{"component": comp, "period": y, "frequency": "annual",
             "measure": "stock", "value": v, "unit": "FCFA milliards",
             "series_code": "INSTAT Annuaire T80 (DGDP)"}
            for comp, by_year in values.items() for y, v in by_year.items()]
    return pd.DataFrame(rows)
