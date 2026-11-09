"""Benin -- INSAE's EMICoV poverty notes, from Wayback `id_` copies of
insae-bj.org (INSAE is the former name of INStaD).

parse_2011 -- "Note sur la pauvreté au Bénin en 2011" (EMICoV 2009 suivi and
              EMICoV 2011).
parse_2015 -- "Note sur la pauvreté" (final; EMICoV 2011 and EMICoV 2015).
parse_2019 -- "Note synthèse sur la pauvreté en 2019" (EHCVM 2018/19):
              only Tableau 2's 2015 column -- EMICoV 2015 P0 by department
              RE-ESTIMATED on the EHCVM method (Atacora 53,9 here vs 42,33 in
              the 2015 note; national 39,3 vs 40,08). Its 2019 values are
              already collected from the 2022 note (benin.yaml).

LAYOUT OF THE NOTES. Each milieu/department table prints P0 (%) | P1 | P2 per
round, with P1 and P2 ON 0-1 (0,088) -- unit "index", never rescaled -- and a
STANDARD-ERROR line in parentheses under each row (not taken). In the milieu
tables the values sit on the line ABOVE the label ("31,35 0,088 0,036 ..." /
"Urbain (0,024) ..."). Characteristic tables print monetary and NON-monetary
P0 per round; only the monetary columns (1 and 3) are taken -- "pauvreté non
monétaire" is INSAE's asset/living-conditions index, not a consumption
measure. 2011 is in both notes with identical values; each note's copy keeps
its own survey label so neither overwrites the other ("EMICoV 2011" from the
2011 note, "EMICoV 2011 (républié, note 2015)").

PUBLISHED ODDITY KEPT: the 2015 P1 / P2 (0,18 / 0,12 nationally against
0,098 / 0,039 in 2011) look implausibly high for the P0 shift, but are the
note's own figures and satisfy P0 >= P1 >= P2.

CROSS-CHECK (verbatim): 2009 35,21 / 0,104 / 0,045; 2011 36,20 / 0,098 /
0,039; 2015 40,08 / 0,18 / 0,12; Couffo 2011 46,58; Littoral 2015 25,73;
female head 2011 27,59 (27,6 in the 2015 note); 2015 Atacora (EHCVM method) 53,9.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T

_DEPTS = ["Alibori", "Atacora", "Atlantique", "Borgou", "Collines", "Couffo", "Donga",
          "Littoral", "Mono", "Ouémé", "Plateau", "Zou"]
LINE = "Seuil de pauvreté monétaire (EMICoV)"
LAYOUT = {"survey": "EMICoV", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
          "line_type": "national", "line_level": "overall", "line_name": LINE,
          "period": "2011", "frequency": "ad_hoc", "decimal": ",", "tables": []}


def _plain(line: str) -> list[float]:
    """Numbers on a line, standard errors in parentheses removed."""
    return C.numbers_in(re.sub(r"\([^)]*\)", " ", line), decimal=",")


def _table(pages, caption):
    for t in pages:
        if "...." in t:
            continue
        m = re.search(caption, t)
        if m:
            body = t[m.end():]
            k = re.search(r"^(?:Source|Tableau ?\d)", body, re.M)
            return (body[:k.start()] if k else body).splitlines()
    raise ValueError(f"caption not found: {caption}")


def _rows(lines, labels, n):
    """{label: n numbers}: on the label's own line, else on the numeric-only
    line just above it (the notes print both ways, sometimes in one table)."""
    out, prev = {}, []
    for ln in lines:
        s = ln.strip()
        lab = next((l for l in labels if re.match(re.escape(l) + r"(?=\s|$)", s)), None)
        if lab is None:
            if not re.search(r"[A-Za-zÀ-ÿ]", s) and not s.startswith("("):
                prev = _plain(s)
            continue
        own = _plain(s[len(lab):])
        vals = own if len(own) >= n else prev
        if len(vals) < n:
            raise ValueError(f"row {lab!r}: {len(vals)} numbers, expected {n}: {s!r}")
        out.setdefault(lab, vals[:n])
        prev = []
    missing = [l for l in labels if l not in out]
    if missing:
        raise ValueError(f"rows not found: {missing}")
    return out


def _r(metric, value, per, survey, **kw):
    return C.row(metric=metric, value=value, survey=survey, welfare_aggregate="consumption",
                 line_type="national", line_level="overall", line_name=LINE,
                 unit=("index" if metric in ("gap", "severity") else None),
                 period=per, reference_period=per, frequency="ad_hoc", **kw)


_MIL = {"Urbain": dict(topic="locality", characteristic="Urbain", locality="urban", locality_label="Urbain"),
        "Rural": dict(topic="locality", characteristic="Rural", locality="rural", locality_label="Rural"),
        "Ensemble": {}}


def _fgt(pages, years, surveys, cap_milieu, cap_dept):
    rows = []
    for cap, labels, attrs in ((cap_milieu, list(_MIL), _MIL),
                               (cap_dept, _DEPTS, {d: {"geography": d} for d in _DEPTS})):
        got = _rows(_table(pages, cap), labels, 6)
        for lab, vals in got.items():
            for j, (per, sv) in enumerate(zip(years, surveys)):
                for k, metric in enumerate(("headcount", "gap", "severity")):
                    rows.append(_r(metric, vals[3 * j + k], per, sv, **attrs[lab]))
    return rows


def _chars(pages, years, surveys, specs):
    rows = []
    for cap, topic, labels, extra in specs:
        got = _rows(_table(pages, cap), [l for l, _ in labels], 4)
        for lab, char in labels:
            vals = got[lab]
            for j, (per, sv) in enumerate(zip(years, surveys)):
                rows.append(_r("headcount", vals[2 * j], per, sv, topic=topic, characteristic=char,
                               **extra.get(char, {})))
    return rows


_SEX = {"Homme": {"sex": "male"}, "Femme": {"sex": "female"}}


def _char_specs(t7, t8, t9):
    return [
        (t7, "education_of_head", [(l, l) for l in ("Aucun", "Primaire", "Secondaire", "Supérieur")], {}),
        (t8, "household_size", [("Moins de 3", "Moins de 3 personnes"), ("3 à 4 personnes", "3 à 4 personnes"),
                                ("5 à 7 personnes", "5 à 7 personnes"), ("8 personnes et", "8 personnes et plus")], {}),
        (t9, "sex_of_head", [("Homme", "Homme"), ("Femme", "Femme")], _SEX),
    ]


def parse_2011(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)["full"]
    yrs, svs = ("2009", "2011"), ("EMICoV 2009 (suivi)", "EMICoV 2011")
    rows = _fgt(pages, yrs, svs, r"Tableau 3: Indices de\s+pauvret. mon.taire suivant le milieu",
                r"Tableau 5: Indices de pauvret. mon.taire par d.partement")
    rows += _chars(pages, yrs, svs, _char_specs(r"Tableau 7: Pauvret. et niveau d.instruction",
                                                r"Tableau 8: Pauvret. et taille du m.nage",
                                                r"Tableau 9: INCIDENCE DE pauvret.\s+et sexe"))
    return pd.DataFrame.from_records(rows)


def parse_2015(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)["full"]
    yrs, svs = ("2011", "2015"), ("EMICoV 2011 (républié, note 2015)", "EMICoV 2015")
    rows = _fgt(pages, yrs, svs, r"Tableau 3: Indices de\s+pauvret. mon.taire suivant le milieu",
                r"Tableau 4: Indices de pauvret. mon.taire par d.partement")
    rows += _chars(pages, yrs, svs, _char_specs(r"Tableau 7: Pauvret. et niveau d.instruction",
                                                r"Tableau 8: Pauvret. et taille du m.nage",
                                                r"Tableau 9: Incidence de pauvret.\s+et sexe"))
    return pd.DataFrame.from_records(rows)


def parse_2019(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)["full"]
    got = _rows(_table(pages, r"Tableau ?2 ?: ?L.incidence ?de ?la ?pauvret. ?mon.taire ?selon"),
                _DEPTS + ["Bénin"], 2)
    sv = "EMICoV 2015 (ré-estimé méthode EHCVM, note 2019)"
    rows = [_r("headcount", v[0], "2015", sv, **({} if d == "Bénin" else {"geography": d}))
            for d, v in got.items()]
    return pd.DataFrame.from_records(rows)


parse = parse_2015
LAYOUT_2011 = LAYOUT_2019 = LAYOUT
