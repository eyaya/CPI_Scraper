"""Madagascar -- Banky Foiben'i Madagasikara (BFM, the central bank), Rapport
Annuel, table "Stock total de la dette extérieure publique et de BFM", sourced
"DDP/MEF et BFM" (the Ministry of Finance's Direction de la Dette Publique, plus
the central bank's own IMF liabilities).

WHY THE CENTRAL BANK. The Ministry (mef.gov.mg) publishes no debt statistics
(its only debt file is a reform-implementation report) and tresor.mg does not
resolve. The BFM report reprints the DDP's external public debt by creditor,
credited -- the sanctioned fallback.

COVERAGE as the table states it: the EXTERNAL debt of the public sector (DDP)
and of the central bank (IMF). No domestic debt is published here.

Each edition prints three years, the last provisional ("[**] Réalisations
provisoires", earlier years "[*] Données mises à jour"):
    2022 report  Tableau 21  2020-2022  "en millions de DTS"
    2021 report  Tableau 20  2019-2021  "en millions de dollars US"
    2019 report  Tableau 21  2017-2019  "en millions de DTS"
THE UNIT CHANGES BETWEEN EDITIONS and is recorded as each table prints it; the
2022 report's LIST of tables calls Tableau 21 "millions de dollars US" while the
table itself says DTS -- the table is followed. Because the unit is part of the
merge key, the 2021 edition's USD figures never collide with the DTS editions;
the two DTS editions cover disjoint years.

THE STRUCTURE ALSO CHANGES. In the 2019 and 2021 editions "Autres créanciers
publics" is a sub-line of "1- Publique" (multilateral + bilateral + other =
public); in the 2022 edition it moves OUT of "Publique" (multilateral +
bilateral = public) and the grand total becomes public + BFM + other. Labels
are kept as printed, and the sum checks accept exactly those two arrangements
and no other.

COMPONENTS: the grand total; "Publique" with "Multilatérale" (BAD, FAD, BIRD,
IDA, Autres) and "Bilatérale" (Club de Paris, Autres institutions); "Autres
créanciers publics"; "BFM" (FMI). Creditor rows carry their group
("Multilatérale: IDA"). "-" cells are not emitted.

CROSS-CHECK: 2022 total 3 429,1 DTS m (public 2 964,5; IDA 1 535,2; IMF 426,5);
2021 total US$ 3 811,7 m; 2017 total 2 044,5 DTS m.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_CAPTION = re.compile(r"Tableau \d+ ?- ?Stock total de la dette ext.rieure publique et de BFM\s*\n"
                      r"\(en millions de (DTS|dollars US)\)")
_NUM = r"(-|\d{1,3}(?: \d{3})*,\d+)"
_ROW = re.compile(rf"^(.*?)\s+{_NUM}\s+{_NUM}\s+{_NUM}$")
_UNITS = {"DTS": "SDR million", "dollars US": "USD million"}
_MULTI = ("BAD", "FAD", "BIRD", "IDA", "Autres")
_BILAT = ("Club de Paris", "Autres institutions")


def _num(s: str) -> float | None:
    return None if s == "-" else float(s.replace(" ", "").replace(",", "."))


def _edition(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            m = _CAPTION.search(t)
            if m and "Rubriques" in t[m.end():m.end() + 80]:
                break
        else:
            raise ValueError(f"BFM: debt table not found in {path}")
    unit = _UNITS[m.group(1)]
    lines = t[m.end():].splitlines()
    hdr = next(l for l in lines if l.startswith("Rubriques"))
    years = re.findall(r"(20\d\d)", hdr)
    if len(years) != 3:
        raise ValueError(f"BFM: header years {years}")

    vals, group = {}, ""
    for ln in lines[lines.index(hdr) + 1:]:
        if ln.startswith("Sources"):
            break
        r = _ROW.match(ln.strip())
        if not r:
            continue
        lab = re.sub(r"^(\d-\s*|-\s*)", "", r.group(1).strip())
        if lab.startswith("Encours total"):
            name = "Encours total de la dette extérieure publique et de BFM"
        elif lab in ("Multilatérale", "Bilatérale"):
            group = lab
            name = lab
        elif lab in ("Publique", "BFM", "Autres créanciers publics"):
            group = ""
            name = lab
        elif lab in _MULTI and group == "Multilatérale" or lab in _BILAT and group == "Bilatérale":
            name = f"{group}: {lab}"
        elif lab == "FMI":
            name = "BFM: FMI"
        else:
            raise ValueError(f"BFM: unexpected row {ln!r}")
        vals[name] = [_num(r.group(k)) for k in (2, 3, 4)]

    need = {"Encours total de la dette extérieure publique et de BFM", "Publique",
            "Multilatérale", "Bilatérale", "Autres créanciers publics", "BFM"}
    if need - set(vals):
        raise ValueError(f"BFM {years}: rows missing {need - set(vals)}")
    z = lambda v: v or 0.0
    for j, y in enumerate(years):
        tot, pub, mul, bil, oth, bfm = (z(vals[k][j]) for k in (
            "Encours total de la dette extérieure publique et de BFM", "Publique",
            "Multilatérale", "Bilatérale", "Autres créanciers publics", "BFM"))
        inside = abs(pub - (mul + bil + oth)) <= 0.15 and abs(tot - (pub + bfm)) <= 0.15
        outside = abs(pub - (mul + bil)) <= 0.15 and abs(tot - (pub + bfm + oth)) <= 0.15
        if not (inside or outside):
            raise ValueError(f"BFM {y}: total {tot}, public {pub} do not reconcile")
        if abs(mul - sum(z(vals.get(f"Multilatérale: {c}", [0, 0, 0])[j]) for c in _MULTI)) > 0.15:
            raise ValueError(f"BFM {y}: multilateral creditors do not sum")

    rows = []
    for name, vs in vals.items():
        for y, v in zip(years, vs):
            if v is not None:
                rows.append({"component": name, "period": y, "frequency": "annual",
                             "measure": "stock", "value": v, "unit": unit,
                             "series_code": "BFM RA dette extérieure"})
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """Primary = newest edition; extras NEWEST FIRST. A (component, year, unit)
    already read from a newer edition is kept."""
    seen, out = set(), []
    for p in [path, *(extras or [])]:
        for r in _edition(p):
            k = (r["component"], r["period"], r["unit"])
            if k not in seen:
                seen.add(k)
                out.append(r)
    return pd.DataFrame(out)
