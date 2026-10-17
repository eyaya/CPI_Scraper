"""Algeria -- Banque d'Algérie, Rapport annuel, statistical annex table "Dette
publique intérieure de l'Administration Centrale", source line "Direction
Générale du Trésor".

WHY THE CENTRAL BANK. The Ministry of Finance (mf.gov.dz) answers HTTP 500 and
publishes no debt statistics; the Banque d'Algérie reprints the Treasury's
domestic-debt table in each annual report, credited -- the sanctioned
fallback. (The Banque d'Algérie's ECONOMY-WIDE external debt series is not
public debt and stays excluded.)

COVERAGE as the caption states it: DOMESTIC public debt of the central
government ("Administration Centrale"). No external public debt is published
in this table. Unit: DZD billion ("En milliards de dinars ; fin de périodes").

EDITIONS: each report prints five year-ends; the 2024 report (Tableau 7,
2020-2024) is the primary and the 2022 report (Tableau 11, 2018-2022) an
extra, adding 2018-2019. The newer edition wins any year both print (the
values for 2020-2022 agree). Year headers carry revision marks in the 2022
edition ("2020**", "2022***") which are stripped. The 2019 report's table has
a letter-spaced text layer ("4 5 2 ,0") and is not read.

READ BY COLUMN POSITION. Adjacent cells use SPACE thousands separators, so a
line like "0 2 079,7 2 614,1" reads more than one way; words are assigned to
the year column whose header they sit under, then joined within the column.

COMPONENTS, nested as printed: Total dette intérieure; Dette courante (Bons du
Trésor et titres assimilés, Autres); Dette d'assainissement (Crédits à long
terme de la Banque d'Algérie, Avance exceptionnelle, Créances rachetées --
itself six lines --, Mise à niveau des fonds propres des banques, Bons CNR,
Bons CNAS); Autres (emprunt national); Dette envers le CCP. Sub-lines carry
their parent ("Dette d'assainissement: Créances rachetées: Dette des
agriculteurs"). The memo line "Dette intérieure en pourcentage du PIB" is
collected as share_of_gdp; the PIB row itself is GDP, not debt, and is not.

CHECKS (each year, to within 0,15): total = courante + assainissement +
emprunt national + CCP; assainissement = its six lines; créances rachetées =
its six lines.

CROSS-CHECK: total 2024 17 243,4 (48,2 % of GDP); 2020 9 423,4; 2018 7 436,2;
Bons du Trésor 2024 5 483,4; Crédits BA 2019 6 556,2.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_CAPTION = re.compile(r"Tableau \d+ ?: ?Dette publique int.rieure de l'Administration Centrale")
_YEAR = re.compile(r"^(20\d\d)\**$")

_TOP = ["Total dette intérieure", "Dette courante", "Dette d'assainissement",
        "Autres (emprunt national)*", "Dette envers le CCP"]
_COURANTE = ["Bons du Trésor et titres assimilés", "Autres *"]
_ASSAIN = ["Crédits à long terme de la Banque d'Algérie",
           "Avance exceptionnelle de la Banque d'Algérie", "Créances rachetées",
           "Mise à niveau des fonds propres des banques", "Bons (CNR)", "Bons (CNAS)"]
_CREANCES = ["Entreprises publiques, EPIC & agro-industrie",
             "Dette d'assainissement complémentaire", "Dette des agriculteurs",
             "Obligations de rachat des crédits syndiqués",
             "Obligations de placement de liquidité", "Obligations bonification"]
_PCT = "Dette intérieure en pourcentage du PIB"


def _component(label: str, parent: str, sub: bool) -> str:
    lab = label.rstrip(" *")
    if label.startswith("Autres (emprunt national)"):
        return "Autres (emprunt national)"
    if sub:
        return f"Dette d'assainissement: Créances rachetées: {lab}"
    return f"{parent}: {lab}" if parent else lab


def _edition(path: str) -> dict[tuple[str, str, str], float]:
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[100:]:
            t = page.extract_text() or ""
            if _CAPTION.search(t) and "Total dette" in t and not re.search(r"\.{8}", t):
                break
        else:
            raise ValueError(f"BA: domestic debt table not found in {path}")
        words = page.extract_words(keep_blank_chars=False, use_text_flow=False)

    # Header: the five year tokens on one line.
    lines: dict[int, list[dict]] = {}
    for w in words:
        lines.setdefault(round(w["top"]), []).append(w)
    hdr = next(ws for top, ws in sorted(lines.items())
               if sum(bool(_YEAR.match(w["text"])) for w in ws) == 5)
    cols = sorted(((w["x0"] + w["x1"]) / 2, _YEAR.match(w["text"]).group(1))
                  for w in hdr if _YEAR.match(w["text"]))
    first_x = cols[0][0] - (cols[1][0] - cols[0][0]) / 2
    years = [y for _, y in cols]

    out: dict[tuple[str, str, str], float] = {}
    parent, sub = "", False
    for top, ws in sorted(lines.items()):
        ws = sorted(ws, key=lambda w: w["x0"])
        label = " ".join(w["text"] for w in ws if w["x1"] <= first_x).strip()
        cells = {y: [] for y in years}
        for w in ws:
            if w["x1"] <= first_x:
                continue
            xc = (w["x0"] + w["x1"]) / 2
            y = min(cols, key=lambda c: abs(c[0] - xc))[1]
            cells[y].append(w["text"])
        if not label or not all(cells[y] for y in years):
            continue
        if label.startswith("PIB"):
            continue
        if label == _PCT:
            comp, meas, unit = "Total dette intérieure", "share_of_gdp", "percent"
        elif label in _TOP or label.startswith("Autres (emprunt national)"):
            parent, sub = ("Dette courante" if label == "Dette courante" else
                           "Dette d'assainissement" if label == "Dette d'assainissement" else ""), False
            comp, meas, unit = _component(label, "", False), "stock", "DZD billion"
        elif label in _COURANTE or label in _ASSAIN:
            sub = label == "Créances rachetées"
            comp, meas, unit = _component(label, parent, False), "stock", "DZD billion"
        elif label in _CREANCES or label.startswith("Entreprises publiques, EPIC"):
            comp, meas, unit = _component(label, parent, True), "stock", "DZD billion"
        else:
            continue
        for y in years:
            v = float("".join(cells[y]).replace(",", "."))
            out[(comp, y, meas)] = v
    _check(out, years)
    return out


def _check(out, years) -> None:
    g = lambda c, y: out.get((c, y, "stock"), 0.0)
    for y in years:
        tot = g("Total dette intérieure", y)
        parts = (g("Dette courante", y) + g("Dette d'assainissement", y)
                 + g("Autres (emprunt national)", y) + g("Dette envers le CCP", y))
        if abs(tot - parts) > 0.15:
            raise ValueError(f"BA {y}: total {tot} != parts {parts:.1f}")
        ass = sum(g(f"Dette d'assainissement: {c.rstrip(' *')}", y) for c in _ASSAIN)
        if abs(g("Dette d'assainissement", y) - ass) > 0.15:
            raise ValueError(f"BA {y}: assainissement does not sum ({ass:.1f})")
        cre = sum(v for (c, yy, m), v in out.items()
                  if yy == y and m == "stock"
                  and c.startswith("Dette d'assainissement: Créances rachetées: "))
        if abs(g("Dette d'assainissement: Créances rachetées", y) - cre) > 0.15:
            raise ValueError(f"BA {y}: créances rachetées do not sum ({cre:.1f})")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """Primary = newest edition; extras newest first; the newer edition wins."""
    merged: dict[tuple[str, str, str], float] = {}
    for p in [path, *(extras or [])]:
        for k, v in _edition(p).items():
            merged.setdefault(k, v)
    rows = []
    for (comp, y, meas), v in merged.items():
        rows.append({"component": comp, "period": y, "frequency": "annual",
                     "measure": meas, "value": v,
                     "unit": "percent" if meas == "share_of_gdp" else "DZD billion",
                     "series_code": "BA RA dette intérieure AC"})
    return pd.DataFrame(rows)
