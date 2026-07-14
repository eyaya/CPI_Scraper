"""Parser for the Tunisia INS IPC data table (Tier 2, HTML).

INS Tunisia publishes the monthly 'Indice mensuel des prix à la consommation
familiale' (base 2015 = 100) as a server-rendered HTML table on its statistics
page — divisions down the rows, the most recent months across the columns:

  (label)                                   | octobre 2025 | … | juin 2026
  Produits alimentaires et boissons …       | 209.3        | … | 217.9
  …
  Ensemble                                  | …            | … | 195.8

We read the table with pandas, map each French COICOP-1999 group label to a code
(Ensemble = All items, 00), parse each 'mois année' column header to a period and
emit the index. The page shows a rolling window of recent months; history
accumulates across runs. Labels kept as published (French).
"""
from __future__ import annotations
import re
import unicodedata
import pandas as pd

_BASE_PERIOD = "2015 = 100"
# (code, label, keyword on the accent-stripped label) — 'ensemble' first
_GROUPS = [
    ("00", "Ensemble", "ensemble"),
    ("01", "Produits alimentaires et boissons non alcoolisées", "aliment"),
    ("02", "Boissons alcoolisées et tabac", "tabac"),
    ("03", "Articles d'habillement et chaussures", "habillement"),
    ("04", "Logement, eau, gaz, électricité et autres combustibles", "logement"),
    ("05", "Meubles, articles de ménage et entretien courant du foyer", "meubles"),
    ("06", "Santé", "sante"),
    ("07", "Transports", "transport"),
    ("08", "Communications", "communication"),
    ("09", "Loisirs et culture", "loisirs"),
    ("10", "Enseignement", "enseignement"),
    ("11", "Restaurants et hôtels", "restaurant"),
    ("12", "Biens et services divers", "biens et services divers"),
]
_MONTHS = {"janvier": "01", "fevrier": "02", "mars": "03", "avril": "04",
           "mai": "05", "juin": "06", "juillet": "07", "aout": "08",
           "septembre": "09", "octobre": "10", "novembre": "11", "decembre": "12"}
_COL = re.compile(r"([a-zûéèêàâäîïôùç]+)\s+(20\d\d)", re.IGNORECASE)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _code(label: str) -> tuple[str, str] | None:
    n = _norm(label)
    for code, clabel, kw in _GROUPS:
        if kw in n:
            return code, clabel
    return None


def _period(col) -> str | None:
    m = _COL.search(str(col))
    if not m:
        return None
    mon = _MONTHS.get(_norm(m.group(1)))
    return f"{m.group(2)}-{mon}" if mon else None


def parse(html_path: str) -> pd.DataFrame:
    for tb in pd.read_html(html_path):
        flat = _norm(" ".join(str(c) for c in tb.astype(str).values.flatten()))
        if "transport" not in flat or "ensemble" not in flat or "aliment" not in flat:
            continue
        pcols = {c: p for c in tb.columns if (p := _period(c))}
        if not pcols:
            continue
        label_col = tb.columns[0]
        records = []
        for _, row in tb.iterrows():
            cl = _code(str(row[label_col]))
            if cl is None:
                continue
            code, label = cl
            for c, period in pcols.items():
                v = pd.to_numeric(row[c], errors="coerce")
                if pd.notna(v):
                    records.append((code, label, period, round(float(v), 4)))
        if len({c for c, *_ in records if c != "00"}) >= 12:
            out = pd.DataFrame.from_records(
                records, columns=["coicop_code", "coicop_label", "period", "value"])
            out = out.drop_duplicates(["coicop_code", "period"])
            out["geography"] = "National"
            out["measure"] = "index"
            out["unit"] = "Index"
            out["base_period"] = _BASE_PERIOD
            out["frequency"] = "monthly"
            return out

    raise ValueError("Tunisia IPC-by-group table not found in page")
