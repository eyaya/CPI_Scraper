"""INSTAT Gabon (ex-DGS) -- Annuaire Statistique du Gabon 2016-2020, section
II.1 "Structure de la population":

* Tableau II.1.1  population by sex (and urban/rural), 2016-2020, persons;
                  2016 "estimée à partir des données du RGPL 2013", 2017-2020
                  "... de l'EGEP II 2017" (the footnotes' two bases);
* Tableau II.1.2  population by province x sex, 2017-2020 (two pages).

EXTRA: the Annuaire statistique du Gabon 2004-2008 (DGSEE; Wayback `id_` copy
of stat-gabon.org's own file, as gdp/sources/gabon.yaml), Tableau II.1.1.1
"Estimation de la population gabonaise par milieu de résidence et par sexe":
2001 and 2002 by sex (2003-2008 rows print ".."). Filed under its own
series_code.

Added 2026-10-13 as a SECOND Gabon descriptor (gabon_annuaire.yaml) beside
gabon.yaml (the EGEP II 2017 synthesis: 2017 national by age x sex).

WHAT IS FILED:
* national by sex for 2016, 2018, 2019, 2020 from II.1.1. 2017 national is
  NOT filed here: gabon.yaml already holds it, and II.1.1 prints 2017 males as
  952 947 where II.1.2 and the EGEP II synthesis print 952 974;
* the nine provinces by sex for 2017-2020 from II.1.2. II.1.2's Total row is
  checked against II.1.1 (2018-2020 equal) and not filed twice.
NOT FILED: urban/rural (the schema has no locality column).

series_type estimate; series_code names the base (RGPL 2013 for 2016, EGEP II
2017 after), so the 2016-2017 break in base is visible.

PUBLISHED, PINNED: II.1.1 2017 male 952 947 vs II.1.2 952 974 (above).
Province names as printed ("Ogooué-lolo"; "Ogooué Maritime" on one page,
"Ogooué maritime" on the other -> filed as "Ogooué-Maritime" once).
"""
from __future__ import annotations

import collections
import re

import fitz
import pandas as pd

_NUM = re.compile(r"(?<!\d)(?:\d{1,3}(?: \d{3})+|\d+)(?!\d)")
_PROVS = {"estuaire": "Estuaire", "hautogooue": "Haut-Ogooué",
          "moyenogooue": "Moyen-Ogooué", "ngounie": "Ngounié", "nyanga": "Nyanga",
          "ogooueivindo": "Ogooué-Ivindo", "ogoouelolo": "Ogooué-Lolo",
          "ogoouemaritime": "Ogooué-Maritime", "woleuntem": "Woleu-Ntem",
          "total": "Total country"}


def _key(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def _rows(page):
    rows = collections.defaultdict(list)
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                t = s["text"].strip()
                if t:
                    rows[round((s["bbox"][1] + s["bbox"][3]) / 2)].append((s["bbox"][0], t))
    out = []
    for y in sorted(rows):
        if out and y - out[-1][0] <= 2:
            out[-1][1].extend(rows[y])
        else:
            out.append([y, list(rows[y])])
    return [(y, sorted(ws)) for y, ws in out]


def _nums(ws, xmin):
    return [float(m.group(0).replace(" ", "")) for x, t in ws if x >= xmin
            for m in _NUM.finditer(t)]


def _annu0408(path: str) -> dict[str, list]:
    """2004-2008 yearbook, Tableau II.1.1.1 'Estimation de la population
    gabonaise par milieu de résidence et par sexe': {year: [H, F, Total]} for
    the years printed with figures (2001, 2002; 2003-2008 print '..')."""
    out = {}
    with fitz.open(path) as doc:
        for page in doc:
            text = page.get_text()
            if "Tableau II.1.1.1" not in text or "....." in text:
                continue
            for _, ws in _rows(page):
                if ws[0][0] > 150 or not re.fullmatch(r"20[01]\d", ws[0][1]):
                    continue
                if all(t == ".." for _, t in ws[1:]):
                    continue
                vals = _nums(ws, 150)
                if len(vals) != 7:
                    raise ValueError(f"Gabon 2004-2008 II.1.1.1 {ws[0][1]}: {vals}")
                out[ws[0][1]] = vals[4:]
            break
    if sorted(out) != ["2001", "2002"]:
        raise ValueError(f"Gabon 2004-2008 II.1.1.1: years {sorted(out)}")
    return out


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    old = {}
    for p in extras or []:
        if "2004-2008" in p:
            old = _annu0408(p)
    if not old:
        raise ValueError("Gabon: the 2004-2008 yearbook extra is missing")
    t111: dict[str, list] = {}
    t112: dict[str, dict[str, list]] = {}
    with fitz.open(local_path) as doc:
        for page in doc:
            text = page.get_text()
            if "Tableau II.1.1" not in text or "....." in text:
                continue
            rows = _rows(page)
            k112 = next(i for i, (_, ws) in enumerate(rows)
                        if any("Tableau II.1.2" in t for _, t in ws))
            # II.1.1: a year's figures can sit on the line above its label
            for i, (y, ws) in enumerate(rows[:k112]):
                lab = ws[0][1]
                m = re.fullmatch(r"(20[12]\d)\**", lab)
                if not m or ws[0][0] > 100:
                    continue
                vals = _nums(ws, 150)
                if len(vals) == 3:          # urban/rural pair on the line above
                    prev = _nums(rows[i - 1][1], 150)
                    if len(prev) != 4:
                        raise ValueError(f"Gabon II.1.1 {m.group(1)}: {prev} + {vals}")
                    vals = prev + vals
                if len(vals) != 7:
                    raise ValueError(f"Gabon II.1.1 {m.group(1)}: {vals}")
                t111[m.group(1)] = vals[4:]        # Ensemble: Hommes, Femmes, Total
            # II.1.2: blocks of two years, each "Provinces Masc Fém Total" x2
            years: list[str] = []
            for y, ws in rows[k112:]:
                yrs = [t for x, t in ws if re.fullmatch(r"20[12]\d", t)]
                if len(yrs) == 2 and len(ws) == 2:
                    years = yrs
                    continue
                g = _PROVS.get(_key(ws[0][1]))
                if g is None or not years:
                    continue
                vals = _nums(ws, 200)
                if len(vals) != 6:
                    raise ValueError(f"Gabon II.1.2 {g} {years}: {vals}")
                for k, yr in enumerate(years):
                    if g in t112.setdefault(yr, {}):
                        raise ValueError(f"Gabon II.1.2 {yr} {g}: twice")
                    t112[yr][g] = vals[3 * k:3 * k + 3]
            break
    if sorted(t111) != ["2016", "2017", "2018", "2019", "2020"]:
        raise ValueError(f"Gabon II.1.1: years {sorted(t111)}")
    if sorted(t112) != ["2017", "2018", "2019", "2020"]:
        raise ValueError(f"Gabon II.1.2: years {sorted(t112)}")

    out = []

    def emit(geo, yr, m, f, t):
        if abs(m + f - t) > 2:
            raise ValueError(f"Gabon {geo} {yr}: {m} + {f} != {t}")
        sc = "GA_DGS_RGPL2013_BASE" if yr == "2016" else "GA_DGS_EGEP2_2017_BASE"
        for sex, v in (("male", m), ("female", f), ("total", t)):
            out.append({"series_type": "estimate", "sex": sex, "age_group": "Total",
                        "geography": geo, "period": yr, "frequency": "annual",
                        "measure": "count", "value": v, "unit": "persons",
                        "series_code": sc})

    for yr, (m, f, t) in old.items():
        out_len = len(out)
        emit("Total country", yr, m, f, t)
        for r in out[out_len:]:
            r["series_code"] = "GA_DGSEE_ANNUAIRE_2004_2008_T2.1.1.1"
    for yr, (m, f, t) in t111.items():
        if yr == "2017":
            # pinned: II.1.1 prints 952 947 males, II.1.2 952 974 (gabon.yaml)
            if (m, t112[yr]["Total country"][0]) != (952947.0, 952974.0):
                raise ValueError(f"Gabon 2017 males: {m} / {t112[yr]['Total country'][0]}")
            continue
        emit("Total country", yr, m, f, t)
    for yr, provs in t112.items():
        if set(provs) != set(_PROVS.values()):
            raise ValueError(f"Gabon II.1.2 {yr}: {sorted(set(_PROVS.values()) ^ set(provs))}")
        tot = provs["Total country"]
        if yr != "2017" and tot != t111[yr]:
            raise ValueError(f"Gabon {yr}: II.1.2 Total {tot} != II.1.1 {t111[yr]}")
        s = [sum(v[k] for g, v in provs.items() if g != "Total country") for k in range(3)]
        if any(abs(a - b) > 5 for a, b in zip(s, tot)):
            raise ValueError(f"Gabon II.1.2 {yr}: provinces {s} != Total {tot}")
        for g, (m, f, t) in provs.items():
            if g != "Total country":
                emit(g, yr, m, f, t)
    return pd.DataFrame(out)
