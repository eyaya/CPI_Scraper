"""Annual series for Comoros: the data workbooks INSEED attaches to its
'Note sur les comptes nationaux définitifs N et provisoires N+1' (Strapi CMS,
/backend/uploads/national_accounts_data_*.xlsx). Not a registry parser:
`comoros_inseed_gdp.parse` hands it the `.xlsx` extras.

Four editions are read (definitive 2021 .. 2024, provisional 2022 .. 2025);
the 2021 edition carries the series back to 2007. Each edition is its own
vintage -- INSEED revises earlier years from one note to the next -- so
`category_group` names the edition and table, and nothing is chained.

Sheets (six per edition, same content, names vary): GDP by production at
current prices and GDP and its uses at current prices (millions of KMF);
real growth by sector and of the uses; change of the deflator by sector and
of the uses. The 2024 edition's 'Révision 2024' sheet (provisional vs
definitive) is not read. Percent cells are stored as fractions with a percent
number format and are read as the percent displayed. A '*' after a year marks
it provisional. Some cells print a thousands break as a line break ('482\\n957')
and are read as one number. Everything as published; nothing derived.
"""
from __future__ import annotations
import os
import re
import openpyxl

UNIT = "KMF million"


def _year(v):
    m = re.fullmatch(r"\s*((?:19|20)\d\d)\s*\*?\s*", str(v)) if v is not None else None
    return m.group(1) if m else None


def _num(c):
    v = c.value
    if isinstance(v, (int, float)):
        return v * 100 if "%" in (c.number_format or "") else v
    if isinstance(v, str) and re.fullmatch(r"-?\d{1,3}(?:\s+\d{3})+", v.strip()):
        return float(re.sub(r"\s+", "", v))
    return None


def _spec(title: str):
    t = title.lower()
    emplois = "emplois" in t
    if "révision" in t or "revision" in t:
        return None
    if "croissance" in t:
        return ("expenditure" if emplois else "production", "constant",
                "growth_yoy", "percent")
    if "déflateur" in t or "deflateur" in t:
        return ("expenditure" if emplois else "production", "not_applicable",
                "growth_yoy", "percent")
    if "courant" in t or "millions" in t:
        return ("expenditure" if (emplois or "demande" in t) else "production",
                "current", "level", UNIT)
    return None


def _edition(path: str) -> str:
    m = re.search(r"def(\d{4})_prov(\d{4})", os.path.basename(path))
    return (f"Comptes nationaux définitifs {m.group(1)} et provisoires {m.group(2)}"
            if m else "Comptes nationaux")


def parse_workbook(path: str) -> list[dict]:
    ed = _edition(path)
    wb = openpyxl.load_workbook(path, data_only=True)
    rows = []
    for ws in wb.worksheets:
        grid = list(ws.iter_rows())
        title = next((str(c.value).strip() for r in grid[:3] for c in r
                      if isinstance(c.value, str) and c.value.strip().lower()
                      .startswith("tableau")), "")
        spec = _spec(title)
        if not spec:
            continue
        approach, basis, measure, unit = spec
        title = re.sub(r"\s+", " ", title.replace("\xa0", " "))
        group = f"{ed}, {title}"
        years = None
        for r in grid:
            yrs = {c.column: _year(c.value) for c in r if _year(c.value)}
            if len(yrs) >= 4:
                years = yrs
                continue
            if not years:
                continue
            lab = next((c.value for c in r if isinstance(c.value, str)
                        and c.value.strip() and c.column < min(years)), None)
            if not lab:
                continue
            lab = re.sub(r"\s+", " ", lab).strip()
            appr = "aggregate" if lab.upper().startswith(("PIB", "PRODUIT INT")) \
                else approach
            for c in r:
                if c.column not in years:
                    continue
                v = _num(c)
                if v is None:
                    continue
                rows.append({"approach": appr, "category": lab,
                             "category_group": group, "series_code": "",
                             "geography": "National", "period": years[c.column],
                             "frequency": "annual", "price_basis": basis,
                             "seasonal_adjustment": "nsa", "measure": measure,
                             "value": float(v), "unit": unit, "base_period": ""})
    if not rows:
        raise ValueError(f"no national-accounts rows read from {path}")
    return rows
