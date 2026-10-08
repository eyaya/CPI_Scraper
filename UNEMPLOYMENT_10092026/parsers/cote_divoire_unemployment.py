"""Côte d'Ivoire — ANStat (formerly INS): EHCVM 2021 and ENSETE 2013, both read
from Wayback Machine `id_` copies of the NSO's OWN files.

WHY THE ARCHIVE. anstat.ci answers every client -- plain, and four browser
fingerprints -- with a Cloudflare interactive challenge (HTTP 403), and the ENE
2019 report it links from centredecalcul.anstat.ci has no capture anywhere.
The Wayback Machine holds byte-identical copies of two ANStat/INS
publications, and an `id_` capture returns the original file unchanged: this
is the NSO's publication, not an aggregator's re-estimate (the README's
warning stands -- the widely quoted 2.3% is ILOSTAT's, not ANStat's; ANStat's
own rates below are 5,3% for 2014 and 3,1% for 2021/22).

1. EHCVM 2021 -- "Profil de pauvreté de la Côte d'Ivoire 2021", chapter 4
   (19th-ICLS definitions, working-age population 16+, the legal minimum):
   * Tableau 4-2: main d'œuvre % (participation), main d'œuvre, hors main
     d'œuvre and working-age population COUNTS, by sex, age band, education,
     milieu (Abidjan / autres villes / rural) and total;
   * Tableau 4-3: its last share column -- "% population en emploi dans la
     PAT", the employment-to-population ratio -- and the employed count. The
     page interleaves the table with prose, so each row is located by its
     label and checked: employed / working-age (from 4-2) must reproduce the
     printed ratio;
   * Tableau 4-8: unemployment rate by sex, education and milieu, crossed with
     six age bands, and the unemployed count.
2. ENSETE 2013 -- "Enquête nationale sur la situation de l'emploi et du travail
   des enfants", rapport descriptif (INS, Aug 2014; reference week February
   2014; already on the 19th-ICLS norms; working age 14+):
   * Tableau 1.3 participation, 1.4 unemployment rate, 1.9 employment ratio,
     by milieu, sex, age band and education;
   * the five national LEVELS stated in the chapter's prose -- taken only
     because they prove each other: working-age 14 501 118 = main d'œuvre
     8 070 764 + hors main d'œuvre 6 430 354, and main d'œuvre = employed
     7 644 539 + unemployed 426 225.

PUBLISHED CONTRADICTIONS, KEPT AND LABELLED, NOT RECONCILED:
* EHCVM's main d'œuvre (4-2: 9 307 770) is NOT employed + unemployed (4-3 and
  4-8: 9 199 529 + 296 059 = 9 495 588). The 3,1% unemployment rate is
  296 059 / 9 495 588; 4-2's 55,9% participation is 9 307 770 / 16 643 249.
  Each is collected under its own table's label.
* EHCVM 4-8's unemployed counts by EDUCATION sum to 606 058 against a total of
  296 059 (by sex and by milieu they sum exactly); those four counts are
  refused, the rates are kept.
* Both reports' prose misquotes their own tables (ENSETE: Abidjan
  participation "59,7%" against the table's 59, employment ratio 47,2 against
  52,5; EHCVM: "1,9% primaire, 7% secondaire" against 1,8 and 6,6). The
  tables are collected.

`definition` is strict for every unemployment rate (both reports state the
19th-ICLS / BIT concepts and publish no broad measure).

CROSS-CHECK: EHCVM -- chômage 3,1 (Abidjan 6,3; 16-24 9,5); participation
55,9; ratio emploi 55,3; PAT 16 643 249. ENSETE -- chômage 5,3 (Abidjan 10,9;
14-24 9,6); participation 55,7; ratio emploi 52,7.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_P = r"(\d+,\d)%"
_CNT = r"(\d{1,3}(?: \d{3})*)"


def _f(t: str) -> float:
    return float(t.replace(" ", "").replace(",", "."))


def _split_two(run: str) -> list[tuple[float, float]]:
    """Every way to read a run of space-separated digit groups as TWO counts
    ("300 418 967 273" is 300 418 + 967 273, or 300 418 967 + 273). The
    caller keeps the one its table's arithmetic accepts."""
    g = run.split()

    def ok(part):
        return bool(part) and len(part[0]) <= 3 and all(len(x) == 3 for x in part[1:])

    return [(_f(" ".join(g[:i])), _f(" ".join(g[i:])))
            for i in range(1, len(g)) if ok(g[:i]) and ok(g[i:])]


_LOC = {"Abidjan": {"locality": "urban", "locality_label": "Abidjan"},
        "Autres villes": {"locality": "urban", "locality_label": "Autres villes"},
        "Urbain autre": {"locality": "urban", "locality_label": "Urbain autre"},
        "Rural": {"locality": "rural", "locality_label": "Rural"}}
_SECTIONS = [(r"^Sexe$", "sex"), (r"^(Tranche|Groupe) ?d.âge$", "age"),
             (r"^(Niveau d.instruction|niveau d.instruction|Education)$", "edu"),
             (r"^Milieu de résidence$", "loc")]


def _ctx(section: str | None, label: str) -> dict:
    if label in ("Total", "Ensemble"):
        return {}
    if section == "sex":
        return {"sex": C.normalise_sex(label)}
    if section == "age":
        return {"age_group": label}
    if section == "edu":
        return {"education": label}
    if section == "loc":
        return _LOC[label]
    raise ValueError(f"CIV: row {label!r} outside any section")


def _block(text: str, caption: str) -> list[str]:
    m = re.search(caption, text)
    return [ln.strip() for ln in text[m.end():].splitlines()]


def _pages(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [p.extract_text() or "" for p in pdf.pages]


# --------------------------------------------------------------------------
# EHCVM 2021
# --------------------------------------------------------------------------
_EH = dict(survey="EHCVM 2021 -- Enquête Harmonisée sur les Conditions de "
                  "Vie des Ménages", period="2022",
           reference_period="EHCVM 2021 (novembre 2021 - juillet 2022)",
           frequency="ad_hoc", working_age_base="16+")


def _ehcvm(path: str) -> list[dict]:
    pages = _pages(path)
    out, wap = [], {}
    # ---- 4-2: the first page carrying it cleanly (page 81) ----
    t42 = next(t for t in pages if re.search(r"^Tableau 4-2 : Composantes", t, re.M)
               and "...." not in t)
    # "... 31,1% 300 418 967 273 5,8%": hors main d'œuvre and the working-age
    # total are ADJACENT space-grouped counts, so they are captured as one run
    # and split where main d'œuvre + hors main d'œuvre = total.
    row = re.compile(rf"^(.+?)\s+{_P}\s+{_CNT}\s+{_P}\s+(\d{{1,3}}(?: \d{{1,3}})+)"
                     rf"\s+{_P}$")
    section, n = None, 0
    for ln in _block(t42, r"Tableau 4-2 : Composantes[^\n]*"):
        if ln.startswith("Source"):
            break
        sec = next((k for p, k in _SECTIONS if re.match(p, ln)), None)
        if sec:
            section = sec
            continue
        m = row.match(ln)
        if not m:
            continue
        label = m.group(1)
        ctx = _ctx(section, label)
        lfpr, lf = _f(m.group(2)), _f(m.group(3))
        splits = [(a, b) for a, b in _split_two(m.group(5)) if abs(lf + a - b) <= 2]
        if len(splits) != 1:
            raise ValueError(f"EHCVM 4-2 {label}: {m.group(5)!r} splits "
                             f"{len(splits)} ways under the table's arithmetic")
        olf, pat = splits[0]
        if abs(lf / pat * 100 - lfpr) > 0.06:
            raise ValueError(f"EHCVM 4-2 {label}: counts and rate disagree")
        wap[label] = pat
        n += 1
        for topic, v, lab in (
                ("labour_force_participation_rate", lfpr,
                 "Main d'œuvre (% de la population en âge de travailler)"),
                ("labour_force", lf, "Main d'œuvre"),
                ("outside_labour_force", olf, "Hors main d'œuvre"),
                ("working_age_population", pat, "Population en âge de travailler")):
            out.append(C.row(topic=topic, value=v, series_label=lab,
                             definition="strict" if topic.endswith("rate") else
                             "not_applicable",
                             series_code="EHCVM T4-2", **_EH, **ctx))
    if n != 16:
        raise ValueError(f"EHCVM 4-2: {n} rows, expected 16")

    # ---- 4-3: the employment ratio column, located row by row ----
    t43 = next(t for t in pages if "Tableau 4-3 : Population en emploi par âge" in t
               and "...." not in t)
    labels = {"Masculin": "Masculin", "Féminin": "Féminin", "Aucun": "Aucun",
              "Primaire": "Primaire", "Secondaire": "Secondaire",
              "Supérieur": "Supérieur", "Abidjan": "Abidjan",
              "villes": "Autres villes", "Rural": "Rural", "Total": "Total"}
    pat43 = re.compile(rf"\b({'|'.join(labels)})\s+((?:\d+,\d%\s+){{7}}){_CNT}\s+\d+%")
    section_of = {"Masculin": "sex", "Féminin": "sex", "Aucun": "edu",
                  "Primaire": "edu", "Secondaire": "edu", "Supérieur": "edu",
                  "Abidjan": "loc", "villes": "loc", "Rural": "loc", "Total": None}
    got = {}
    for m in pat43.finditer(t43):
        got.setdefault(m.group(1), m)
    if set(got) != set(labels):
        raise ValueError(f"EHCVM 4-3: found rows {sorted(got)}")
    for key, m in got.items():
        label = labels[key]
        epr = _f(m.group(2).split()[6].rstrip("%"))
        emp = _f(m.group(3))
        if abs(emp / wap[label] * 100 - epr) > 0.06:
            raise ValueError(f"EHCVM 4-3 {label}: employed {emp:,.0f} / PAT "
                             f"{wap[label]:,.0f} != {epr}")
        ctx = _ctx(section_of[key], label)
        out.append(C.row(topic="employment_to_population_ratio", value=epr,
                         series_label="% population en emploi dans la PAT",
                         series_code="EHCVM T4-3", **_EH, **ctx))
        out.append(C.row(topic="employed", value=emp,
                         series_label="Effectif en emploi",
                         series_code="EHCVM T4-3", **_EH, **ctx))
    employed_total = _f(got["Total"].group(3))

    # ---- 4-8: unemployment rate by group x age ----
    t48 = next(t for t in pages if re.search(r"^Tableau 4-8 : Taux de chômage", t, re.M)
               and "...." not in t)
    ages = ["16-24", "25-34", "35-44", "45-54", "55-60", "61 et plus"]
    row = re.compile(rf"^(.+?)\s+((?:\d+,\d%\s+){{7}}){_CNT}$")
    section, unemp = None, {}
    for ln in _block(t48, r"Tableau 4-8 : Taux de chômage[^\n]*"):
        if ln.startswith("Source"):
            break
        sec = next((k for p, k in _SECTIONS if re.match(p, ln)), None)
        if sec:
            section = sec
            continue
        m = row.match(ln)
        if not m:
            continue
        label = m.group(1)
        ctx = _ctx(section, label)
        rates = [_f(x.rstrip("%")) for x in m.group(2).split()]
        lab = "Taux de chômage"
        for age, v in zip(ages, rates[:6]):
            out.append(C.row(topic="unemployment_rate", definition="strict",
                             value=v, series_label=lab, age_group=age,
                             series_code="EHCVM T4-8", **_EH, **ctx))
        out.append(C.row(topic="unemployment_rate", definition="strict",
                         value=rates[6], series_label=lab,
                         series_code="EHCVM T4-8", **_EH, **ctx))
        unemp[(section, label)] = _f(m.group(3))
        # Education counts sum to 606 058 against 296 059: refused.
        if section != "edu":
            out.append(C.row(topic="unemployed", value=unemp[(section, label)],
                             series_label="Effectif de chômeurs",
                             series_code="EHCVM T4-8", **_EH, **ctx))
    total = unemp[(section, "Total")]
    for sec in ("sex", "loc"):
        s = sum(v for (k, lab), v in unemp.items() if k == sec and lab != "Total")
        if abs(s - total) > 2:
            raise ValueError(f"EHCVM 4-8: {sec} counts sum to {s:,.0f}")
    if abs(total / (total + employed_total) * 100 - 3.1) > 0.06:
        raise ValueError("EHCVM 4-8: total rate is not unemployed / (employed + "
                         "unemployed)")
    return out


# --------------------------------------------------------------------------
# ENSETE 2013
# --------------------------------------------------------------------------
_EN = dict(survey="ENSETE 2013 -- Enquête Nationale sur la Situation de "
                  "l'Emploi et du Travail des Enfants", period="2014-Q1",
           reference_period="février 2014", frequency="ad_hoc",
           working_age_base="14+")
_TWO = re.compile(r"^(.+?)\s+(\d+(?:,\d)?)\s+(\d+(?:,\d)?)$")


def _ensete_table(pages, caption, col, topic, label, code) -> list[dict]:
    text = next(t for t in pages if re.search(caption, t) and "...." not in t)
    out, section, n = [], None, 0
    for ln in _block(text, caption + r"[^\n]*"):
        if ln.startswith("Source"):
            break
        if re.match(r"^Grouped?.âge$|^Groupe d.âge$", ln):
            section = "age"
            continue
        sec = next((k for p, k in _SECTIONS if re.match(p, ln)), None)
        if sec:
            section = sec
            continue
        m = _TWO.match(ln)
        if not m or not re.match(r"^[A-Za-zé\d]", m.group(1)):
            continue
        a, b = _f(m.group(2)), _f(m.group(3))
        if abs(a + b - 100) > 0.15:
            raise ValueError(f"ENSETE {code} {m.group(1)}: {a} + {b} != 100")
        ctx = _ctx(section, m.group(1).strip())
        n += 1
        out.append(C.row(topic=topic, value=(a, b)[col], series_label=label,
                         definition="strict" if topic in (
                             "unemployment_rate",
                             "labour_force_participation_rate") else
                         "not_applicable",
                         series_code=code, **_EN, **ctx))
    if n != 14:
        raise ValueError(f"ENSETE {code}: {n} rows, expected 14")
    return out


def _ensete(path: str) -> list[dict]:
    pages = _pages(path)[:32]
    out = []
    out += _ensete_table(pages, r"Tableau 1\.3: Structure de la population en âge",
                         0, "labour_force_participation_rate",
                         "Main-d'œuvre (% de la population en âge de travailler)",
                         "ENSETE T1.3")
    out += _ensete_table(pages, r"Tableau 1\.4: Structure de la main d.œuvre",
                         1, "unemployment_rate", "Taux de chômage", "ENSETE T1.4")
    out += _ensete_table(pages, r"Tableau 1\.9: Population en âge de travailler",
                         1, "employment_to_population_ratio",
                         "Population en âge de travailler en emploi (%)",
                         "ENSETE T1.9")
    flat = re.sub(r"\s+", " ", " ".join(pages))
    # The prose groups digits erratically ("14 501118sur", "6430 354"), so
    # every space BETWEEN TWO DIGITS is closed; the identities below then decide
    # whether the five levels were read right.
    flat = re.sub(r"(?<=\d) (?=\d)", "", flat)
    grab = {
        "wap": r"population en âge de travailler est estimée à (\d{7,9})",
        "lf": r"main-d’œuvre, composée des personnes en emploi et de celles au "
              r"chômage, est estimée à (\d{7,9})",
        "emp": r"population en emploi est estimée quant à elle en février 2014, "
               r"à (\d{7,9})",
        "un": r"population au chômage est estimée à (\d{6,9})",
        "olf": r"population hors main-d’œuvre est estimée en février 2014 à "
               r"(\d{7,9})",
    }
    v = {}
    for k, pat in grab.items():
        m = re.search(pat, flat)
        if not m:
            raise ValueError(f"ENSETE: level {k!r} not found in the prose")
        v[k] = float(m.group(1))
    if v["lf"] + v["olf"] != v["wap"] or v["emp"] + v["un"] != v["lf"]:
        raise ValueError(f"ENSETE: the stated levels do not add up: {v}")
    for topic, key, lab in (("working_age_population", "wap",
                             "Population en âge de travailler"),
                            ("labour_force", "lf", "Main-d'œuvre"),
                            ("employed", "emp", "Population en emploi"),
                            ("unemployed", "un", "Population au chômage"),
                            ("outside_labour_force", "olf",
                             "Population hors main-d'œuvre")):
        out.append(C.row(topic=topic, value=v[key], series_label=lab,
                         series_code="ENSETE ch.1 (texte)", **_EN))
    return out


def parse(path: str, extras=None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        head = " ".join(_pages(p)[:2])
        if "ENSETE" in head:
            rows += _ensete(p)
        elif re.search(r"PROFIL DE PAUVRET|EHCVM", head, re.I):
            rows += _ehcvm(p)
        else:
            raise ValueError(f"CIV: unrecognised document {p}")
    return pd.DataFrame(rows)
