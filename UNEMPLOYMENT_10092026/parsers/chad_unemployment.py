"""Chad — INSEED ECOSIT4 (Quatrième Enquête sur la Consommation des Ménages et
le Secteur Informel au Tchad), Rapport général, chapter 7 "Emploi".

A HOUSEHOLD survey (consumption/poverty, with an employment section),
collected July-September 2018 and January-April 2019 -> period 2019, reference
"2018-2019", as `labour/` dates the same report.

READ BY A BESPOKE GRID READER, not the shared engine: each table below is
stated as a caption, its column meanings in printed order, and the label that
closes it; a row is a label plus EXACTLY the table's column count, wrapped
labels ("Autre centre" / "urbain 89,0 ...") are rejoined, and the few rows
that print fewer cells than columns are either mapped explicitly (where the
missing column is known -- N'Djaména has no rural stratum) or refused.

TAKEN (rates as published; working-age base exactly as each caption states):

* 7.01 / 7.03  taux d'activité, 5+ and 15+, Ensemble column only (the other
               columns split by relationship to the household head -- no
               schema dimension) by city / stratum;
* 7.04         taux d'activité 15+ by province x age (15-29 / 30-49 / 50+);
* 7.05         taux d'activité 15+ by stratum x sex;
* 7.13 / 7.14  chômage BIT, 15-64 and 15+, by stratum x sex and age -> strict;
* 7.15 / 7.16  chômage BIT, 15+ and 15-64, by province x milieu and sex;
* 7.17         chômage élargi 15+ by stratum x sex and age -> broad;
* 7.19         chômage élargi 15-64 by milieu x sex/age (élargi half ONLY);
* 7.20         BIT and élargi 15-64 by education x sex / province -- only
               rows printing all twelve cells (blank cells shift the rest);
* 7.21         BIT and élargi 15-64 by diploma x sex / milieu -- rows with
               all ten cells;
* 7.25         taux combiné du chômage et de la main-d'oeuvre potentielle
               (SU3) by province x milieu -> labour_underutilisation_rate,
               broad.

PUBLISHED DEFECTS, NOT SMOOTHED:

* 7.19's BIT half: its sex rows print rural before urban (Masculin 1,4 / 5,1)
  while its age rows print urban first (15 à 29: 7,6 / 2,3) -- 7.13 settles
  that 5,1 is the urban male rate. The half is not collected (7.13 carries
  the same figures cleanly).
* 7.24's counts contradict the report: "Main-d'oeuvre (A)" 4 346 263 is BELOW
  the 4 350 913 employed 15+ quoted on page 191, and its 49 327 unemployed give
  1,1% against the 2,0% BIT rate of 7.14. Its counts are not collected; its
  SU3 (8,6) is the national row of 7.25, which is.
* 7.18 re-presents 7.14 and 7.17 by milieu (values agree) and is skipped.
* 7.22's "sous-emploi invisible" is INCOME-based (earning under the SMIG), not
  time-related underemployment; it has no topic here and is not forced into
  `underemployment_rate`. 7.23 (dependency ratio) likewise.

age 15-29 is INSEED's "classe d'âges", not a declared youth band, so it is an
`unemployment_rate` row with age_group "15-29", never `youth_unemployment_rate`.

CROSS-CHECK: activité 15+ 60,0 (H 72,9 / F 49,3); BIT 15+ 2,0 (N'Djaména
7,9; 15-29 3,4); BIT 15-64 2,0; élargi 15+ 18,5 (F 26,8); élargi 15-64 19,1;
SU3 8,6 (urbain 15,9, N'Djaména 24,9); Moyen Chari activité 83,0.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from ._common import numbers_in, row

_SURVEY = ("ECOSIT4 -- Quatrième Enquête sur la Consommation des Ménages et le "
           "Secteur Informel au Tchad")
_BASE = dict(survey=_SURVEY, period="2019", reference_period="2018-2019",
             frequency="ad_hoc")

_LFPR = "labour_force_participation_rate"
_UR = "unemployment_rate"
_SU3 = "labour_underutilisation_rate"


def _stratum(label: str) -> dict:
    """Where a row is a city / stratum rather than a province."""
    lab = label.replace("’", "'")
    low = lab.lower()
    if low in ("tchad", "total"):
        return {}
    if low == "rural":
        return {"locality": "rural", "locality_label": lab}
    if low.startswith(("autre", "autres")):
        return {"locality": "other", "locality_label": lab}
    if low in ("milieu urbain", "ensemble urbain", "urbain"):
        return {"locality": "urban", "locality_label": lab}
    # N'Djaména, Moundou, Sarh, Abéché: cities, each an urban stratum.
    return {"locality": "urban", "locality_label": lab}


def _province(label: str) -> dict:
    lab = label.replace("’", "'")
    if lab.lower() in ("tchad", "total"):
        return {}
    return {"geography": lab}


_M, _F = {"sex": "male"}, {"sex": "female"}
_A1529, _A3049, _A50 = ({"age_group": "15-29"}, {"age_group": "30-49"},
                        {"age_group": "50+"})
_URB = {"locality": "urban", "locality_label": "Urbain"}
_RUR = {"locality": "rural", "locality_label": "Rural"}
_SKIP = None
_EDU = ["Sans instruction", "Primaire", "Secondaire général",
        "Secondaire technique/professionnel", "Supérieur", None]

# (caption regex, last-row regex, columns, row-context fn, defaults, extras)
# A column is a dict merged into the row (None = not collected).
_TABLES = [
    dict(code="T7.01", cap=r"^Tableau 7\.01 :", last=r"^Tchad\b",
         cols=[_SKIP] * 5 + [{}], ctx=_stratum,
         d=dict(topic=_LFPR, working_age_base="5+",
                series_label="Taux d'activité des individus âgés de 5 ans et plus")),
    dict(code="T7.03", cap=r"^Tableau 7\.03 :", last=r"^Tchad\b",
         cols=[_SKIP] * 5 + [{}], ctx=_stratum,
         d=dict(topic=_LFPR, working_age_base="15+",
                series_label="Taux d'activité des personnes âgées de 15 ans et "
                             "plus (selon le lien de parenté)")),
    dict(code="T7.04", cap=r"^Tableau 7\.04 :", last=r"^Tchad\b",
         cols=[_A1529, _A3049, _A50, {}], ctx=_province,
         d=dict(topic=_LFPR, working_age_base="15+",
                series_label="Taux d'activité (15 ans et plus) par province")),
    dict(code="T7.05", cap=r"^Tableau 7\.05 :", last=r"^Tchad\b",
         cols=[_M, _F, {}], ctx=_stratum,
         d=dict(topic=_LFPR, working_age_base="15+",
                series_label="Taux d'activité des personnes âgées de 15 ans et "
                             "plus selon le sexe")),
    dict(code="T7.13", cap=r"^Tableau 7\.13 :", last=r"^Total\b",
         cols=[_M, _F, _A1529, _A3049, _A50, {}], ctx=_stratum,
         d=dict(topic=_UR, definition="strict", working_age_base="15-64",
                series_label="Taux de chômage au sens du BIT des 15-64 ans")),
    dict(code="T7.14", cap=r"^Tableau 7\.14 :", last=r"^Total\b",
         cols=[_M, _F, _A1529, _A3049, _A50, {}], ctx=_stratum,
         d=dict(topic=_UR, definition="strict", working_age_base="15+",
                series_label="Taux de chômage des personnes âgées de 15 ans et "
                             "plus au sens du BIT")),
    dict(code="T7.15", cap=r"^Tableau 7\.15 :", last=r"^Tchad\b",
         cols=[_URB, _RUR, _M, _F, {}], ctx=_province,
         # N'Djaména is wholly urban: four cells, no rural one.
         short={"N'Djaména": [_URB, _M, _F, {}]},
         d=dict(topic=_UR, definition="strict", working_age_base="15+",
                series_label="Taux de chômage des personnes âgées de 15 ans et "
                             "plus par province (BIT)")),
    dict(code="T7.16", cap=r"^Tableau 7\.16 :", last=r"^Tchad\b",
         cols=[_URB, _RUR, _M, _F, {}], ctx=_province,
         short={"N'Djaména": [_URB, _M, _F, {}]},
         d=dict(topic=_UR, definition="strict", working_age_base="15-64",
                series_label="Taux de chômage des personnes âgées de 15-64 ans "
                             "au sens du BIT par province")),
    dict(code="T7.17", cap=r"^Tableau 7\.17 :", last=r"^Total\b",
         cols=[_M, _F, _A1529, _A3049, _A50, {}], ctx=_stratum,
         d=dict(topic=_UR, definition="broad", working_age_base="15+",
                series_label="Taux de chômage des personnes âgées de 15 ans et "
                             "plus (au sens élargi)")),
    dict(code="T7.19", cap=r"^Tableau 7\.19 :", last=r"^Total\b",
         cols=[_URB, _RUR, {}, _SKIP, _SKIP, _SKIP],
         ctx=lambda lab: {"Masculin": _M, "Féminin": _F, "15 à 29": _A1529,
                          "30 à 49": _A3049, "50 et plus": _A50,
                          "Total": {}}[lab],
         d=dict(topic=_UR, definition="broad", working_age_base="15-64",
                series_label="Taux de chômage élargi des personnes âgées de "
                             "15-64 ans")),
    dict(code="T7.25", cap=r"^Tableau 7\.25:", last=r"^Total\b",
         cols=[_URB, _RUR, {}], ctx=_province,
         short={"Ville de N'djamena": [_URB, {}]},
         d=dict(topic=_SU3, definition="broad", working_age_base="15+",
                series_label="Taux combiné du chômage et de la main-d'oeuvre "
                             "potentielle (SU3)")),
]

_EXPECT = {"T7.01": 8, "T7.03": 8, "T7.04": 22, "T7.05": 5, "T7.13": 8,
           "T7.14": 8, "T7.15": 23, "T7.16": 23, "T7.17": 8, "T7.19": 6,
           "T7.25": 22}
_FURNITURE = re.compile(r"^(TCHAD_ECOSIT4|\d{1,3}$)")


def _pages(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        # chapter 7 spans pdf pages 189-214; read a margin either side
        return [(p.extract_text() or "") for p in pdf.pages[185:216]]


def _rows_after(lines: list[str], start: int, ncols: int, last: str):
    """(label, numbers) pairs from `start` until the `last` label's row."""
    out, pending = [], ""
    for ln in lines[start:]:
        s = ln.strip()
        if not s or _FURNITURE.match(s):
            continue
        if re.match(r"^Tableau 7\.\d+", s):
            break
        # An AGE label carries digits of its own ("15 à 29 31,5 ..."), which a
        # lazy label match would read as a value: cut it off first.
        age = re.match(r"^(\d+ à \d+|\d+ et plus)\s+(.*)$", s)
        if age:
            m = re.match(r"^()((?:\d[\d ]*(?:,\d+)?\s*)+)$", age.group(2))
            nums = numbers_in(m.group(2), decimal=",") if m else []
            label = age.group(1)
        else:
            m = re.match(r"^(.*?)\s*((?:-?\d[\d ]*(?:,\d+)?\s*)+)$", s)
            nums = numbers_in(m.group(2), decimal=",") if m else []
            label = (m.group(1) if m else s).strip()
        if not nums or not label and not pending:
            pending = f"{pending} {s}".strip() if not nums else pending
            if len(pending) > 60:          # prose, or a wrapped header
                pending = ""
            continue
        if pending and (not label or label[0].islower()):
            label = f"{pending} {label}".strip()
        pending = ""
        out.append((label.replace("’", "'"), nums))
        if re.match(last, label):
            break
    return out


def _read(text: str, spec: dict) -> list[dict]:
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if re.match(spec["cap"], ln.strip())
              and not re.search(r"\.{4}", ln)]
    if not starts:
        raise ValueError(f"ECOSIT4 {spec['code']}: caption not found")
    got = _rows_after(lines, starts[-1] + 1, len(spec["cols"]), spec["last"])
    out, used = [], 0
    for label, nums in got:
        cols = spec["cols"]
        if len(nums) != len(cols):
            short = spec.get("short", {})
            if label in short and len(nums) == len(short[label]):
                cols = short[label]
            else:
                continue                       # a misaligned row is refused
        try:
            base_ctx = spec["ctx"](label)
        except KeyError:
            raise ValueError(f"ECOSIT4 {spec['code']}: unexpected row {label!r}")
        used += 1
        for col, v in zip(cols, nums):
            if col is None:
                continue
            kw = {**spec["d"], **base_ctx, **col}
            out.append(row(value=v, series_code=f"ECOSIT4 {spec['code']}",
                           **_BASE, **kw))
    if used < _EXPECT[spec["code"]]:
        raise ValueError(f"ECOSIT4 {spec['code']}: {used} rows read, "
                         f"{_EXPECT[spec['code']]} expected")
    return out


def _education_tables(text: str) -> list[dict]:
    """7.20 (education x sex/province) and 7.21 (diploma x sex/milieu): the BIT
    and élargi halves side by side. Only rows printing EVERY cell are taken."""
    out = []
    lines = text.splitlines()
    # --- 7.20: 12 cells = (5 levels + Ensemble) x (BIT, élargi)
    i = next(k for k, ln in enumerate(lines)
             if re.match(r"^Tableau 7\.20 :", ln.strip()))
    for label, nums in _rows_after(lines, i + 1, 12, r"^Total\b"):
        if len(nums) != 12:
            continue
        ctx = ({"sex": "male"} if label == "Masculin" else
               {"sex": "female"} if label == "Féminin" else
               {} if label == "Total" else {"geography": label})
        for j, v in enumerate(nums):
            edu = _EDU[j % 6]
            strict = j < 6
            out.append(row(
                topic=_UR, definition="strict" if strict else "broad",
                series_label=("Taux de chômage au sens du BIT" if strict else
                              "Taux de chômage élargi")
                + " des 15-64 ans par niveau d'études",
                value=v, working_age_base="15-64",
                education=edu or "Total", series_code="ECOSIT4 T7.20",
                **_BASE, **ctx))
    # --- 7.21: 10 cells = (M, F, Urbain, Rural, Ensemble) x (BIT, élargi)
    i = next(k for k, ln in enumerate(lines)
             if re.match(r"^Tableau 7\.21 :", ln.strip()))
    tails = {"DEUG, DUT,": "DEUG, DUT, BTS", "Master/DEA/": "Master/DEA/DESS"}
    cols = [_M, _F, _URB, _RUR, {}]
    pending = None
    for ln in lines[i + 1:]:
        s = ln.strip()
        if s.startswith("7.4") or re.match(r"^Tableau 7\.22", s):
            break
        if s in tails:
            pending = tails[s]
            continue
        m = re.match(r"^([A-Za-zÉé/,. ]*?)\s*(\d[\d, ]*)$", s)
        if not m:
            continue
        # Whole tokens only: a regex counting cells would split "100" into
        # 1, 0, 0 and admit Doctorat/Phd's eight cells as ten.
        nums = [float(t.replace(",", ".")) for t in m.group(2).split()]
        label = m.group(1).strip() or pending
        pending = None
        if not label or len(nums) != 10:
            continue
        edu = "Total" if label == "Total" else label
        for j, v in enumerate(nums):
            strict = j < 5
            out.append(row(
                topic=_UR, definition="strict" if strict else "broad",
                series_label=("Taux de chômage au sens du BIT" if strict else
                              "Taux de chômage élargi")
                + " des 15-64 ans par diplôme le plus élevé",
                value=v, working_age_base="15-64", education=edu,
                series_code="ECOSIT4 T7.21", **_BASE, **cols[j % 5]))
    return out


def parse(path: str, extras=None) -> pd.DataFrame:
    text = "\n".join(_pages(path))
    out = []
    for spec in _TABLES:
        out += _read(text, spec)
    out += _education_tables(text)
    df = pd.DataFrame(out)
    # Guard the anchors the docstring quotes.
    def v(code, **kw):
        m = df.series_code == code
        for k, val in kw.items():
            m &= df[k] == val
        vals = df.loc[m, "value"].tolist()
        if len(vals) != 1:
            raise ValueError(f"ECOSIT4 {code} {kw}: {len(vals)} values")
        return vals[0]
    nat = dict(geography="Total country", locality="all", sex="total",
               age_group="Total", education="Total")
    for code, want in (("ECOSIT4 T7.05", 60.0), ("ECOSIT4 T7.14", 2.0),
                       ("ECOSIT4 T7.17", 18.5), ("ECOSIT4 T7.19", 19.1),
                       ("ECOSIT4 T7.25", 8.6)):
        got = v(code, **nat)
        if got != want:
            raise ValueError(f"{code} national: got {got}, want {want}")
    return df
