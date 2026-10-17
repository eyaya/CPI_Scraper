"""Morocco — Ministry of Economy and Finance (DTFE) annual public-debt series,
as published by the Ministry on the national open-data portal data.gov.ma
("Séries annuelles de dette publique", file publicdebtannualseries-2013q4-portail.xls,
"Mise à jour : 31 mars 2014").

WHY A SECOND MOROCCO SOURCE. The primary descriptor (morocco.yaml) reads the
DTFE's current workbooks through Wayback `id_` copies, because finances.gov.ma
refuses connections from this network, and the Wayback Machine has been
answering it with HTTP 429. data.gov.ma serves the Ministry's own earlier
release of the SAME annual table directly, so Morocco is collectable without
the archive. It is an OLDER VINTAGE (March 2014) and carries its own
series_code, so it never overwrites the 2022 vintage's rows; where the two
overlap (1998-2013) both stay, distinguishable.

COLLECTED (1998-2013): public external debt outstanding (US$ million and MAD
million, with % of GDP), Treasury external, domestic and total debt
outstanding (MAD million, % of GDP) -- the rows defined in morocco_dtfe_debt.
Debt service, interest charges and average cost are flows / rates and are left
out.

THE YEAR HEADER. The workbook holds the table twice, English sheet first,
French second; the French header omits the "2013" label although its 2013
column is filled. Every numeric cell of the two sheets is identical (checked
on every run), so the years are read from the English header and the labels
from the French sheet, whose wording the DTFE parser's row definitions use.

CROSS-CHECK: public external debt 2013 US$28 801 m / MAD 234 746 m (26,5 % of
GDP); Treasury debt 2013 MAD 554 261,5 m (62,5 %); 1998 Treasury debt
256 691,1 (66,7 %).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .morocco_dtfe_debt import _ANNUAL, _UNIT

_SERIES = "DTFE annual series (data.gov.ma, update 31 Mar 2014)"


def parse(path: str, extras=None) -> pd.DataFrame:
    book = pd.read_excel(path, sheet_name=None, header=None)
    fr = next(df for name, df in book.items() if name.endswith("-FR"))
    en = next(df for name, df in book.items() if name.endswith("-EN"))
    a = fr.iloc[1:, 1:].apply(pd.to_numeric, errors="coerce").to_numpy()
    b = en.iloc[1:, 1:].apply(pd.to_numeric, errors="coerce").to_numpy()
    if a.shape != b.shape or not np.array_equal(np.nan_to_num(a, nan=-1.0),
                                                np.nan_to_num(b, nan=-1.0)):
        raise ValueError("data.gov.ma Morocco: the EN and FR sheets no longer "
                         "carry identical figures -- cannot borrow the EN years")
    years = {c: str(int(v)) for c, v in enumerate(en.iloc[0].tolist())
             if isinstance(v, (int, float)) and pd.notna(v) and 1990 < v < 2100}

    labels = fr[0].astype(str).str.strip().tolist()
    rows, done = [], set()
    for i, lab in enumerate(labels):
        for prefix, comp, cov, meas, unit in _ANNUAL:
            if not lab.startswith(prefix) or (prefix, unit) in done:
                continue
            if prefix == "Encours de la dette du Trésor" and ("extérieure" in lab or "intérieure" in lab):
                continue
            done.add((prefix, unit))
            pct = i + 1 if (unit == _UNIT and i + 1 < len(labels)
                            and labels[i + 1].startswith("En %")) else None
            for c, y in years.items():
                v = pd.to_numeric(fr.iloc[i, c], errors="coerce")
                if pd.notna(v):
                    rows.append({"coverage": cov, "component": comp, "period": y,
                                 "frequency": "annual", "measure": meas,
                                 "value": float(v), "unit": unit, "series_code": _SERIES})
                if pct is not None:
                    p = pd.to_numeric(fr.iloc[pct, c], errors="coerce")
                    if pd.notna(p):
                        # The cell is a fraction formatted as a percent.
                        rows.append({"coverage": cov, "component": comp, "period": y,
                                     "frequency": "annual", "measure": "share_of_gdp",
                                     "value": round(float(p) * 100, 10),
                                     "unit": "percent", "series_code": _SERIES})
    if len(done) != len(_ANNUAL):
        raise ValueError(f"data.gov.ma Morocco: found {len(done)} of {len(_ANNUAL)} series")
    return pd.DataFrame(rows)
