"""Parser for the INSTAT Madagascar NIPC workbook (Tier 2, Excel behind a SPA).

INSTAT publishes the 'Nouvel Indice des Prix à la Consommation' as an .xlsx
(base 100 = moyenne 2016) linked from each monthly NIPC page. The 'IPC' sheet is
a wide monthly index series (2016-01 → latest); col0 is the label, col1 the
weight, and cols 2+ carry the index under a datetime period header (row 12).

Rows are grouped by classification axis (RIZ / ORIGINE / ENERGIE / PPN / SECTEUR
DE PRODUCTION / FONCTION / GEOGRAPHIE). We capture the official COICOP-1999
block — 'Ensemble' (all items) + the 12 'FONCTION' divisions — as the index,
emitting every reported month. The Madagascar-specific analytical aggregates and
the 7 city series are left in the retained source file.
"""
from __future__ import annotations
import re
import unicodedata
import pandas as pd

_BASE_PERIOD = "2016 = 100"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


# (code, canonical label, keyword) — keywords are unique to the FONCTION block,
# so the analytical / geography rows can never shadow a COICOP code.
_DIVS = [
    ("00", "Ensemble (All items)", "ensemble"),
    ("01", "Produits alimentaires et boissons non alcoolisés", "alimentaires et boissons"),
    ("02", "Boissons alcoolisées et tabacs", "boissons alcool"),
    ("03", "Articles d'habillement et articles chaussants", "habillement"),
    ("04", "Logement, eau, électricité, gaz et autres combustibles", "logement"),
    ("05", "Ameublement, équipement ménager et entretien courant", "ameublement"),
    ("06", "Santé", "sante"),
    ("07", "Transports", "transport"),
    ("08", "Communications", "communication"),
    ("09", "Loisirs et culture", "loisirs"),
    ("10", "Enseignement, Education", "enseignement"),
    ("11", "Hôtellerie, cafés, restauration", "restauration"),
    ("12", "Autres biens et services", "autres biens et services"),
]


def _period_header(df: pd.DataFrame):
    """Return {col_index: 'YYYY-MM'} from the row whose cells parse as dates."""
    for r in range(df.shape[0]):
        row = df.iloc[r]
        mapping = {}
        for c in range(2, df.shape[1]):
            v = row.iloc[c]
            ts = pd.to_datetime(v, errors="coerce")
            if pd.notna(ts):
                mapping[c] = ts.strftime("%Y-%m")
        if len(mapping) >= 12:
            return mapping
    raise ValueError("Madagascar NIPC: period header row not found")


def parse(xlsx_path: str) -> pd.DataFrame:
    df = pd.ExcelFile(xlsx_path).parse("IPC", header=None)
    periods = _period_header(df)

    records = []
    for code, label, kw in _DIVS:
        # first row in the sheet whose label matches this division's keyword
        hit = next((r for r in range(df.shape[0]) if kw in _norm(df.iloc[r, 0])), None)
        if hit is None:
            raise ValueError(f"Madagascar NIPC: missing division {code} ({kw})")
        for c, period in periods.items():
            v = df.iloc[hit, c]
            if pd.notna(v) and isinstance(v, (int, float)):
                records.append((code, label, period, "index", round(float(v), 4),
                                "Index", _BASE_PERIOD))

    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
