"""Central African Republic — ICASEES, Comptes nationaux définitifs 2019-2021
(base 2019, SCN 2008), published 2026.

The first rebased national accounts ICASEES has put online. Two files from its
"Tableau de bord" publications list (icasees.org, CC BY 4.0):

* "Jeux de données des Comptes Nationaux de 2005-2019 et 2019-2021" (xlsx,
  primary) -- sheet `Donnee`: value added by 32 branches (primary /
  secondary / tertiary subtotals), TOTAL VAB, taxes on products and GDP,
  AT CURRENT PRICES, 2019-2021 -> production approach.
* "Comptes Nationaux définitifs 2019-2021" (PDF report, extra) -- Tableau 1,
  "Résumé des indicateurs et agrégats économiques de la nation": GDP at
  current and at constant 2019 prices, exports, imports, FBCF, real growth,
  the GDP deflator and GDP per head.

UNITS -- THE WORKBOOK'S OWN LABEL IS WRONG, AND THE FILE SAYS SO. Every row of
`Donnee` carries "millions de F CFA", but the workbook's `Dataset` sheet
describes the same table "en milliards de FCFA", and the report states GDP
"1 952,9 milliards FCFA" for 2019 -- the workbook's 1 952,9. The two
statements contradict; the report and the Dataset sheet agree, so the unit is
recorded as "milliard FCFA" and the parser re-checks every run that workbook
GDP x 1000 equals the report's Tableau 1 GDP in millions (1 952 925 / 2 056 035
/ 2 149 622, to rounding). Tableau 1 itself is in "millions de FCFA".

NOT COLLECTED, AND WHY:
* the workbook's older series (`Donnee_2005-2019`, `Donnee_2013-2019`,
  `Donnée_SCN2008`): SCN 1993-era levels whose price basis is stated nowhere
  in the workbook or the report -- collecting them would mean guessing it.
  (They also run ~36% below the rebased level for 2019: 1 432,0 vs 1 952,9.)
  `Donnée nouvelle` repeats `Donnee` in capitals: checked equal, not emitted.
* report Tableau 17 ("aux prix de 2019"): its 2021 GDP (2 051 859,3) is not
  Tableau 1's constant-price GDP (2 088 958), its GDP row is labelled "prix
  constant de 2005" in a base-2019 report, and its volume indices read as
  "11,340" / "10,341" (decimal comma misplaced). Refused, not repaired.
* report Tableau 14 (resources and uses at current prices): its FBCF 2019
  (384 782) contradicts Tableau 1's (384 847), and its labels wrap across
  codes. Tableau 1's FBCF is collected; T14 is left for a later layout.
* Tableau 1's population, employment, income, saving and ratio rows: no
  approach or measure here holds them (they are not GDP measures).

CHECKS every run: in `Donnee`, each sector equals its branches, the three
sectors equal TOTAL VAB, TOTAL VAB + taxes = GDP (to 0.15); Tableau 1's real
growth for 2020 reproduces from its own constant-price levels (3,41%).

CROSS-CHECK (as printed): GDP 2019 1 952,9 / 2020 2 056,0 / 2021 2 149,6
milliard FCFA; constant 2021 2 088 958 million FCFA; real growth 2020 3,41%;
deflator 2021 102,90; GDP per head 2021 352 912 FCFA; agriculture VA 2021
316,2.
"""
from __future__ import annotations

import re

import openpyxl
import pandas as pd
import pdfplumber

_YEARS = ["2019", "2020", "2021"]


def _row(**kw) -> dict:
    base = {"category_group": "", "geography": "Total country",
            "seasonal_adjustment": "nsa", "base_period": "", "frequency": "annual"}
    base.update(kw)
    return base


def _workbook(path: str) -> tuple[list[dict], dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ds = {r[0]: r[1] for r in wb["Dataset"].iter_rows(values_only=True) if r[0]}
    if "milliards" not in str(ds.get("Dataset Description", "")):
        raise ValueError("ICASEES workbook: Dataset sheet no longer states milliards")
    ind = {r[0]: (str(r[1]).strip(), r[3]) for r in
           wb["Indicateur"].iter_rows(min_row=2, values_only=True) if r[0]}
    rows = list(wb["Donnee"].iter_rows(values_only=True))
    hdr = [str(h) for h in rows[0]]
    cols = [hdr.index(y) for y in _YEARS]
    data = {}
    for r in rows[1:]:
        if r[0] in ind:
            data[r[0]] = [float(r[c]) for c in cols]
    if len(data) != 35:
        raise ValueError(f"ICASEES Donnee: {len(data)} indicators, expected 35")
    # Parents from the Indicateur sheet: sectors -> branches.
    for j, y in enumerate(_YEARS):
        for code, (name, parent) in ind.items():
            if code in ("IND1", "IND7", "IND20"):
                kids = [k for k, (_, p) in ind.items() if p == code and k != "IND33"]
                s = sum(data[k][j] for k in kids)
                if abs(s - data[code][j]) > 0.15:
                    raise ValueError(f"ICASEES {y}: {name} != its branches ({s})")
        vab = data["IND1"][j] + data["IND7"][j] + data["IND20"][j]
        if abs(vab - data["IND33"][j]) > 0.15:
            raise ValueError(f"ICASEES {y}: sectors != TOTAL VAB")
        if abs(data["IND33"][j] + data["IND34"][j] - data["IND35"][j]) > 0.15:
            raise ValueError(f"ICASEES {y}: VAB + taxes != GDP")
    # `Donnée nouvelle` repeats `Donnee`: proven, not emitted.
    nv = {r[0]: r for r in wb["Donnée nouvelle"].iter_rows(min_row=2, values_only=True) if r[0]}
    for code, vals in data.items():
        rep = [float(nv[code][4 + j]) for j in range(3)]
        if any(abs(a - b) > 1e-6 for a, b in zip(vals, rep)):
            raise ValueError(f"ICASEES: 'Donnée nouvelle' {code} differs from 'Donnee'")
    out = []
    for code, vals in data.items():
        name = ind[code][0]
        appr = "aggregate" if code in ("IND33", "IND34", "IND35") else "production"
        for y, v in zip(_YEARS, vals):
            out.append(_row(approach=appr, category=name,
                            category_group="Valeurs ajoutées brutes par branche "
                                           "d'activité, valeurs courantes",
                            series_code=f"ICASEES CN 2019-2021 {code}",
                            period=y, price_basis="current", measure="level",
                            value=v, unit="milliard FCFA"))
    return out, {y: data["IND35"][j] for j, y in enumerate(_YEARS)}


_T1 = {  # Tableau 1 label start -> (category, approach, price, measure, unit)
    "PIB à prix courant": ("PIB à prix courant", "aggregate", "current", "level", "million FCFA"),
    "PIB à prix constant": ("PIB à prix constant", "aggregate", "constant", "level", "million FCFA"),
    "Exportations (en millions": ("Exportations", "expenditure", "current", "level", "million FCFA"),
    "Importations (en millions": ("Importations", "expenditure", "current", "level", "million FCFA"),
    "Formation Brute de Capital Fixe": ("Formation Brute de Capital Fixe", "expenditure", "current", "level", "million FCFA"),
    "Taux de croissance réel": ("Taux de croissance réel", "aggregate", "constant", "growth_yoy", "percent"),
    "Déflateur du PIB": ("Déflateur du PIB", "aggregate", "not_applicable", "deflator", "index"),
    "PIB/ habitant": ("PIB/ habitant", "aggregate", "current", "per_capita", "FCFA"),
}


def _report(path: str, gdp_wb: dict) -> list[dict]:
    """Tableau 1, read by WORD POSITION. Counts use space thousands, so a line
    such as "295 813 244 676 231 506" splits more than one way; each digit
    group is instead assigned to the year column whose header ("2019 2020
    2021") it sits under, and the groups in one column are joined."""
    with pdfplumber.open(path) as pdf:
        page = next(pg for pg in pdf.pages[:12]
                    if re.search(r"Tableau 1: R.sum. des indicateurs",
                                 pg.extract_text() or "")
                    and "Superficie" in (pg.extract_text() or ""))
        words = page.extract_words(keep_blank_chars=False)
    hdr = [w for w in words if w["text"] in _YEARS]
    hdr = [w for w in hdr if abs(w["top"] - hdr[0]["top"]) < 3]
    if [w["text"] for w in hdr] != _YEARS:
        raise ValueError(f"ICASEES T1: header years {[w['text'] for w in hdr]}")
    xs = {w["text"]: (w["x0"] + w["x1"]) / 2 for w in hdr}
    first_col = min(w["x0"] for w in hdr) - 25
    # lines by vertical position
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if w["top"] <= hdr[0]["top"] + 2:
            continue
        if lines and abs(lines[-1][0]["top"] - w["top"]) < 3:
            lines[-1].append(w)
        else:
            lines.append([w])
    parsed = []          # (label text, {year: "digits"})
    for ln in lines:
        lab = " ".join(w["text"] for w in ln if w["x1"] < first_col)
        cells: dict[str, list[str]] = {}
        for w in ln:
            if w["x0"] >= first_col and re.fullmatch(r"-?[\d,]+%?", w["text"]):
                y = min(xs, key=lambda k: abs(xs[k] - (w["x0"] + w["x1"]) / 2))
                cells.setdefault(y, []).append(w["text"])
        parsed.append((lab, {y: "".join(v) for y, v in cells.items()}))
    found = {}
    for i, (lab, cells) in enumerate(parsed):
        for key in _T1:
            if lab.startswith(key) and key not in found:
                # a wrapped label carries its numbers on its own line or the next
                c = cells or (parsed[i + 1][1] if i + 1 < len(parsed) else {})
                found[key] = c
    out = []
    for key, (cat, appr, pb, meas, unit) in _T1.items():
        cells = found.get(key)
        if not cells:
            raise ValueError(f"ICASEES T1: {key!r} not read")
        if meas == "growth_yoy" and "2019" in cells:
            raise ValueError(f"ICASEES T1 {key}: a growth value under 2019")
        if meas != "growth_yoy" and set(cells) != set(_YEARS):
            raise ValueError(f"ICASEES T1 {key}: columns {sorted(cells)}")
        for y in _YEARS:
            if y not in cells:
                continue
            v = float(cells[y].rstrip("%").replace(",", "."))
            out.append(_row(approach=appr, category=cat,
                            category_group="Tableau 1: Résumé des indicateurs et "
                                           "agrégats économiques de la nation",
                            series_code="ICASEES CN 2019-2021 rapport T1",
                            period=y, price_basis=pb, measure=meas, value=v,
                            unit=unit,
                            base_period="Constant 2019 prices"
                            if (pb == "constant" and meas == "level") else ""))
    lv = {r["period"]: r["value"] for r in out if r["category"] == "PIB à prix constant"}
    cur = {r["period"]: r["value"] for r in out if r["category"] == "PIB à prix courant"}
    g20 = next(r["value"] for r in out if r["category"] == "Taux de croissance réel"
               and r["period"] == "2020")
    if abs((lv["2020"] / lv["2019"] - 1) * 100 - g20) > 0.01:
        raise ValueError("ICASEES T1: 2020 growth does not reproduce from its levels")
    for y in _YEARS:
        if abs(gdp_wb[y] * 1000 - cur[y]) > 60:
            raise ValueError(f"ICASEES {y}: workbook GDP x1000 != report T1 GDP "
                             f"({gdp_wb[y]} vs {cur[y]}) -- check the units")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows, gdp = _workbook(path)
    for p in extras or []:
        if p.lower().endswith(".pdf"):
            rows += _report(p, gdp)
    df = pd.DataFrame(rows)
    # Deflators are an index; the corpus convention is unit "index" with the
    # reference year in base_period, not in the unit string.
    df.loc[df["measure"] == "deflator", "base_period"] = "2019=100"
    return df
