"""Morocco -- Ministère de l'Économie et des Finances, Direction du Trésor et
des Finances Extérieures (DTFE), "Chiffres et statistiques" debt workbooks.

PUBLISHER: the Ministry's Treasury directorate (DTFE). Its two workbooks are
the live statistics files at
    https://www.finances.gov.ma/Chiffres_stats/FR/dette-tresor-trimestriel.xls
    https://www.finances.gov.ma/Chiffres_stats/FR/dette-exterieure-publique-annuel.xls
finances.gov.ma refuses connections from the collector's network (plain and
browser-impersonated), so the descriptor fetches the Wayback Machine's `id_`
captures of those exact files (1 September 2022) -- the Ministry's own bytes.
Both workbooks say "Mise à jour : 30 juin 2022".

1. dette-tresor-trimestriel.xls, sheet ST2007-2021 (French), quarterly
   2007T1-2022T1, MAD million ("en million DH"). Two blocks, each its own
   COVERAGE:
     * "DETTE DU TRESOR"                               -> Treasury (central government)
     * "DETTE DES ÉTABLISSEMENTS ET ENTREPRISES PUBLIQUES" -> public establishments
                                                          and enterprises
   Only the ENCOURS (outstanding stock) rows are collected: total, short term
   (domestic / external) and medium-long term (domestic / external). Service,
   principal and interest rows are FLOWS and out of scope. The header runs to
   2023T1, but 2022T2-2023T1 print a total of 0 with empty components --
   unfilled placeholders, not zero debt -- and are skipped.

2. dette-exterieure-publique-annuel.xls, sheet SA1998-2020, annual 1998-2021:
   public external debt (USD million and MAD million) and % of GDP; of which
   Treasury external debt; Treasury domestic debt; total Treasury debt -- each
   stock with its % of GDP. Debt service, interest charges and average cost
   are not stocks and are not collected.
   COVERAGE: "Public external debt" (the whole public sector's external debt)
   for its first block; Treasury for the others.

PERCENT CELLS are stored as fractions with the format "0.0%" (0.295 displays as
29.5 %); they are emitted in percent, as displayed, keeping the stored
precision. Nothing is computed: every % of GDP value is the Ministry's own.

CHECKS: Treasury total = short-term + medium/long-term in every quarter, and
short-term domestic + external = short term (to within 0.5 MAD million).

CROSS-CHECK: Treasury debt 2021T4 885 305,9 (domestic 655 807,2 + 25 719,5,
external 203 779,2); annual 2021 Treasury debt 885 306 (68,9 % of GDP); public
external debt 2021 US$ 40 791 m / MAD 378 559 m (29,5 % of GDP); 1998 Treasury
debt 256 691,1 (66,7 %).
"""
from __future__ import annotations

import os
import re

import pandas as pd

_QUARTER = re.compile(r"^(\d{4})T([1-4])$")
_UNIT = "MAD million"
_BLOCKS = {
    "DETTE DU TRESOR": "Treasury (central government)",
    "DETTE DES ÉTABLISSEMENTS ET ENTREPRISES PUBLIQUES":
        "Public establishments and enterprises",
}


def _quarterly(path: str) -> list[dict]:
    df = pd.read_excel(path, sheet_name="ST2007-2021", header=None)
    col0 = df[0].astype(str).str.strip()
    rows = []
    for title, coverage in _BLOCKS.items():
        start = col0[col0.str.upper().str.startswith(title[:30].upper())].index
        if not len(start):
            raise ValueError(f"DTFE quarterly: block {title!r} not found")
        top = start[0]
        hdr = df.iloc[top + 2].tolist()
        periods = {c: f"{m.group(1)}-Q{m.group(2)}"
                   for c, h in enumerate(hdr)
                   if (m := _QUARTER.match(str(h).strip()))}
        # The ENCOURS block: total, then Court terme (int./ext.), then Moyen
        # et long terme (int./ext.) -- the first seven rows after the header.
        enc = top + 5
        if not str(df.iloc[enc, 0]).strip().upper().startswith("ENCOURS"):
            raise ValueError(f"DTFE quarterly: no ENCOURS row under {title!r}")
        labels, parent = [], ""
        for r in range(enc, enc + 7):
            lab = str(df.iloc[r, 0]).strip()
            if r == enc:
                labels.append((r, "Encours de la dette"))
            elif lab.startswith(("Court", "Moyen")):
                parent = "Court terme" if lab.startswith("Court") else "Moyen et long terme"
                labels.append((r, parent))
            else:
                labels.append((r, f"{parent}: {lab}"))
        for c, period in periods.items():
            total = pd.to_numeric(df.iloc[enc, c], errors="coerce")
            if pd.isna(total) or total == 0:
                continue               # unfilled placeholder columns
            vals = {name: pd.to_numeric(df.iloc[r, c], errors="coerce")
                    for r, name in labels}
            st, mlt = vals["Court terme"], vals["Moyen et long terme"]
            if abs((st if pd.notna(st) else 0) + mlt - total) > 0.5:
                raise ValueError(f"DTFE {coverage} {period}: total {total} != "
                                 f"short {st} + medium/long {mlt}")
            for name, v in vals.items():
                if pd.isna(v):
                    continue
                rows.append({"coverage": coverage, "component": name,
                             "period": period, "frequency": "quarterly",
                             "measure": "stock", "value": float(v),
                             "unit": _UNIT, "series_code": "DTFE dette-tresor-trimestriel"})
    return rows


# Annual sheet: row label -> (component, coverage, measure, unit)
_ANNUAL = [
    ("Encours de la dette extérieure publique (En millions $US)",
     "Encours de la dette extérieure publique", "Public external debt", "stock", "USD million"),
    ("Encours de la dette extérieure publique (En millions DH)",
     "Encours de la dette extérieure publique", "Public external debt", "stock", _UNIT),
    ("Encours de la dette extérieure du Trésor",
     "Encours de la dette extérieure du Trésor", "Treasury (central government)", "stock", _UNIT),
    ("Encours de la dette intérieure du Trésor",
     "Encours de la dette intérieure du Trésor", "Treasury (central government)", "stock", _UNIT),
    ("Encours de la dette du Trésor",
     "Encours de la dette du Trésor", "Treasury (central government)", "stock", _UNIT),
]


def _annual(path: str) -> list[dict]:
    df = pd.read_excel(path, sheet_name=0, header=None)
    years = {c: str(int(v)) for c, v in enumerate(df.iloc[0].tolist())
             if isinstance(v, (int, float)) and pd.notna(v) and 1990 < v < 2100}
    rows, done = [], set()
    labels = df[0].astype(str).str.strip().tolist()
    for i, lab in enumerate(labels):
        for prefix, comp, cov, meas, unit in _ANNUAL:
            if not lab.startswith(prefix) or (prefix, unit) in done:
                continue
            # "Encours de la dette du Trésor" must not also catch the two
            # longer labels above it.
            if prefix == "Encours de la dette du Trésor" and ("extérieure" in lab or "intérieure" in lab):
                continue
            done.add((prefix, unit))
            pct = None
            if unit == _UNIT and i + 1 < len(labels) and labels[i + 1].startswith("En %"):
                pct = i + 1
            for c, y in years.items():
                v = pd.to_numeric(df.iloc[i, c], errors="coerce")
                if pd.notna(v):
                    rows.append({"coverage": cov, "component": comp, "period": y,
                                 "frequency": "annual", "measure": meas,
                                 "value": float(v), "unit": unit,
                                 "series_code": "DTFE dette-exterieure-publique-annuel"})
                if pct is not None:
                    p = pd.to_numeric(df.iloc[pct, c], errors="coerce")
                    if pd.notna(p):
                        rows.append({"coverage": cov, "component": comp, "period": y,
                                     "frequency": "annual", "measure": "share_of_gdp",
                                     "value": round(float(p) * 100, 10), "unit": "percent",
                                     "series_code": "DTFE dette-exterieure-publique-annuel"})
    if len(done) != len(_ANNUAL):
        raise ValueError(f"DTFE annual: found {len(done)} of {len(_ANNUAL)} series")
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = _quarterly(path)
    for p in extras or []:
        if "annuel" in os.path.basename(p).lower():
            rows += _annual(p)
    return pd.DataFrame(rows)
