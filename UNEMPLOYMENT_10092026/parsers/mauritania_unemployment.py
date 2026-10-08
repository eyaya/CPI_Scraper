"""Mauritania — ANSADE: the quarterly ENTE notes, and ENESI 2017.

1. ENTE -- Enquête Nationale Trimestrielle sur l'Emploi, quarterly note
   ("Note trimestrielle", 2025 Q1-Q4). A HOUSEHOLD LFS (~2 500 households a
   quarter, 21st-ICLS concepts, working age 14-64). Every note closes with
   "Tableaux d'annexes" in the same shape, each table giving the CURRENT
   quarter beside the SAME QUARTER A YEAR EARLIER (header "T4-2024 T4-2025"),
   so four notes yield eight quarters, 2024-Q1 to 2025-Q4:

     Annexe4  taux de participation        -> labour_force_participation_rate
     Annexe5  ratio emploi / PAT           -> employment_to_population_ratio
     Annexe6  taux de chômage (SU1)        -> unemployment_rate, strict
     Annexe7  chômage + sous-emploi (SU2)  -> underemployment_rate, broad
     Annexe8  chômage + MO potentielle (SU3) -> labour_underutilisation_rate, broad
     Annexe9  sous-utilisation (SU4)       -> labour_underutilisation_rate, broad

   each by Sexe, Groupe d'âge (14-35 / 36-64), Niveau d'instruction, Milieu
   and Strate (seven sampling zones: four urban, three rural -> locality with
   the zone in locality_label). The "Ensemble" closing every section must be
   the same number in every section -- it is checked, and emitted once.

   ZONE SPELLINGS: the annexes print "Nouakchott" and "Nouakchot"
   interchangeably (Annexe6 vs Annexe7 of the same note). The one sampling
   zone is recorded as "Nouakchott" throughout, so a zone joins across its own
   indicators; every other label is as printed.

   NOT COLLECTED: Annexes 1-3 (population structure, and the labour-force /
   outside split that repeats Annexe4); the "Résultats clés" fact sheets
   (charts and prose only -- 2026 Q1 is there, but as chart labels; it will
   arrive in tables with that quarter's full note).

2. ENESI 2017 -- Enquête Nationale sur l'Emploi et le Secteur Informel,
   report annexes 2-8 (base 14-64, the survey's own definition, p. 29):
   working-age population, labour force, employed, unemployed and population
   outside the labour force (counts), and the unemployment rate, by age,
   sex, milieu, education and wilaya.

   PUBLISHED DEFECT: Tableau A4.3 is a digit-for-digit copy of A4.2 under the
   same caption ("selon l'âge et le sexe"); it is not read. A6 (time-related
   underemployment COUNTS) has no count topic here and A6.2 crosses it with
   CSP; A3.4 is a distribution across wilayas. Not collected.

   Each table's national Total row repeats across tables of the same topic
   (the labour force's 832 638 closes A3.1, A3.2 and A3.3): every repeat is
   checked equal and emitted once.

The RGPH 2013 census volume `labour` reads is not used here: its activity
and occupation tables sit inside two-column pages whose prose fuses with the
rows, and its base is 10+ against these 14-64 series.

CROSS-CHECK: ENTE 2025-Q4 SU1 13,12 (F 21,29; 14-35 22,17), LFPR 50,01,
EPR 43,45, SU3 28,64, SU4 32,86; 2024-Q4 SU1 12,29. ENESI 2017 unemployment
11,8 (urban 14,9; Nouakchott 15,9); labour force 832 638; unemployed 98 362;
employed 734 277.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

from . import _common as C

_ENTE = "Enquête Nationale Trimestrielle sur l'Emploi (ENTE)"
_ENESI = "Enquête Nationale sur l'Emploi et le Secteur Informel (ENESI) 2017"
_BASE = "14-64"

_ANNEXES = {
    4: ("labour_force_participation_rate", "strict",
        "Taux de participation de la main d'œuvre"),
    5: ("employment_to_population_ratio", "not_applicable",
        "Ratio emploi sur la population en âge de travailler"),
    6: ("unemployment_rate", "strict", "Taux de chômage (SU1)"),
    7: ("underemployment_rate", "broad",
        "Taux de chômage combiné au sous-emploi (SU2)"),
    8: ("labour_underutilisation_rate", "broad",
        "Taux de chômage combiné à la main d'œuvre potentielle (SU3)"),
    9: ("labour_underutilisation_rate", "broad",
        "Sous-utilisation de la main d'œuvre (SU4)"),
}
# The section word ("Sexe", "Groupe d'âge", "Niveau d'instruction", "Milieu",
# "Strate") is vertically centred against its block, so it lands in front of
# the first, a middle or no row, and "Niveau" / "d'instruction" can split over
# two rows -- it is STRIPPED, and each row is classified by its own label,
# which is unambiguous.
_SECTION_WORDS = re.compile(r"^(?:Sexe|Groupe d.âge|Niveau d.instruction|Niveau|"
                            r"d.instruction|Milieu|Strate|strate)\s+")
_EDUCATION = ("Non applicable", "Aucun", "Mahadra/coranique", "Primaire",
              "Secondaire", "Supérieur")
_URBAN_ZONES = ("Nouakchott", "Nouadhibou", "Zoueiratt", "Autre urbain")
_RURAL_ZONES = ("Fleuve", "oasis", "Autre rural")


def _ctx(label: str) -> dict:
    if label in ("Masculin", "Féminin"):
        return {"sex": C.normalise_sex(label)}
    m = re.fullmatch(r"(\d+-\d+) ans", label)
    if m:
        return {"age_group": m.group(1)}
    if label in _EDUCATION:
        return {"education": label}
    if label in ("Urbain", "Rural"):
        return {"locality": label.lower().replace("urbain", "urban"),
                "locality_label": label}
    z = re.match(r"^Zone\s*«\s*(.*?)\s*»$", label)
    if z:
        name = "Nouakchott" if z.group(1) == "Nouakchot" else z.group(1)
        if name in _URBAN_ZONES:
            return {"locality": "urban", "locality_label": name}
        if name in _RURAL_ZONES:
            return {"locality": "rural", "locality_label": name}
    raise ValueError(f"ENTE: unclassifiable row label {label!r}")


def _ente(path: str) -> list[dict]:
    out = []
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    found = set()
    for text in pages:
        m = re.search(r"Annexe\s?(\d)\s?:", text)
        if not m or int(m.group(1)) not in _ANNEXES:
            continue
        n = int(m.group(1))
        topic, dfn, label = _ANNEXES[n]
        hdr = re.search(r"^T([1-4])-(20\d\d)\s+T([1-4])-(20\d\d)\s*$", text, re.M)
        if not hdr:
            raise ValueError(f"ENTE Annexe{n}: no quarter header")
        periods = [(f"{hdr.group(2)}-Q{hdr.group(1)}", f"T{hdr.group(1)}-{hdr.group(2)}"),
                   (f"{hdr.group(4)}-Q{hdr.group(3)}", f"T{hdr.group(3)}-{hdr.group(4)}")]
        if periods[0][0][5:] != periods[1][0][5:] or \
                int(periods[1][0][:4]) - int(periods[0][0][:4]) != 1:
            raise ValueError(f"ENTE Annexe{n}: header {periods} is not a "
                             f"year-on-year pair")
        ensemble, rows, labels = None, 0, set()
        for ln in text[hdr.end():].splitlines():
            ln = ln.strip()
            if ln.startswith("Page "):
                break
            mm = re.match(r"^(.*?)\s*(\d+\.\d+)\s+(\d+\.\d+)$", ln)
            if not mm:
                continue
            lab = _SECTION_WORDS.sub("", mm.group(1).strip())
            lab = _SECTION_WORDS.sub("", lab)      # "Niveau d'instruction X"
            vals = [float(mm.group(2)), float(mm.group(3))]
            if lab in ("Ensemble", "Total"):
                if ensemble is None:
                    ensemble = vals
                elif ensemble != vals:
                    raise ValueError(f"ENTE Annexe{n}: section Ensemble {vals} "
                                     f"differs from {ensemble}")
                continue
            ctx = _ctx(lab)
            if lab in labels:
                raise ValueError(f"ENTE Annexe{n}: {lab!r} read twice")
            labels.add(lab)
            for (period, ref), v in zip(periods, vals):
                out.append(C.row(topic=topic, definition=dfn, value=v,
                                 series_label=label, survey=_ENTE, period=period,
                                 reference_period=ref, frequency="quarterly",
                                 working_age_base=_BASE,
                                 series_code=f"ENTE Annexe{n}", **ctx))
                rows += 1
        if ensemble is None or rows < 2 * 15:
            raise ValueError(f"ENTE Annexe{n}: {rows} values read")
        for (period, ref), v in zip(periods, ensemble):
            out.append(C.row(topic=topic, definition=dfn, value=v,
                             series_label=label, survey=_ENTE, period=period,
                             reference_period=ref, frequency="quarterly",
                             working_age_base=_BASE, series_code=f"ENTE Annexe{n}"))
        found.add(n)
    if found != set(_ANNEXES):
        raise ValueError(f"ENTE {os.path.basename(path)}: annexes {sorted(found)} "
                         f"read, want {sorted(_ANNEXES)}")
    return out


# --------------------------------------------------------------------------
# ENESI 2017
# --------------------------------------------------------------------------

_SEX3 = [{"sex": "male"}, {"sex": "female"}, {}]
_MIL3 = [{"locality": "urban", "locality_label": "Urbain"},
         {"locality": "rural", "locality_label": "Rural"}, {}]
# caption id -> (topic, series label, columns, row kind, definition)
_ENESI_TABLES = [
    ("A2.1", "working_age_population", "Population en âge de travailler", _MIL3, "age"),
    ("A2.2", "working_age_population", "Population en âge de travailler", _SEX3, "age"),
    ("A2.3", "working_age_population", "Population en âge de travailler", _SEX3, "education"),
    ("A3.1", "labour_force", "Main d'œuvre", _MIL3, "age"),
    ("A3.2", "labour_force", "Main d'œuvre", _SEX3, "geography"),
    ("A3.3", "labour_force", "Main d'œuvre", _SEX3, "education"),
    ("A4.2", "employed", "Population en emploi", _SEX3, "age"),
    ("A4.5", "employed", "Population en emploi", _MIL3, "geography"),
    ("A5.1", "unemployed", "Population en chômage", _SEX3, "age"),
    ("A5.2", "unemployed", "Population en chômage", _MIL3, "geography"),
    ("A5.3", "unemployed", "Population en chômage", _SEX3, "geography"),
    ("A7.1", "outside_labour_force", "Population hors de la main d'œuvre", _SEX3, "age"),
    ("A7.2", "outside_labour_force", "Population hors de la main d'œuvre", _MIL3, "geography"),
    ("A8.1", "unemployment_rate", "Taux de chômage", _SEX3, "age"),
    ("A8.2", "unemployment_rate", "Taux de chômage", _MIL3, "age"),
    ("A8.3", "unemployment_rate", "Taux de chômage", _SEX3, "education"),
    ("A8.4", "unemployment_rate", "Taux de chômage", _MIL3, "geography"),
]


def _enesi(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages[65:85])
    out, seen = [], {}
    for tid, topic, label, cols, kind in _ENESI_TABLES:
        m = re.search(rf"^Tableau {re.escape(tid)}\s?:.*$", text, re.M)
        if not m:
            raise ValueError(f"ENESI {tid}: caption not found")
        rate = topic.endswith("_rate")
        num = r"\d+,\d" if rate else r"\d+"
        body = text[m.end():]
        rows, pending = [], ""
        for ln in body.splitlines():
            ln = ln.strip()
            if ln.startswith(("Source", "Tableau", "Annexe", "Edition")) and rows:
                break
            mm = re.match(rf"^(.*?)\s+((?:{num}\s+)*{num})$", ln)
            if not mm or not re.search(r"[A-Za-z]", mm.group(1) + pending) and kind != "age":
                pending = (pending + " " + ln).strip() if not mm else pending
                continue
            vals = [float(v.replace(",", ".")) for v in mm.group(2).split()]
            lab = (pending + " " + mm.group(1)).strip()
            pending = ""
            rows.append((lab, vals))
        # A8.4's Nouakchott is wholly urban and prints no rural rate.
        fixed = []
        for lab, vals in rows:
            if len(vals) == 2 and lab == "Nouakchott" and cols is _MIL3:
                vals = [vals[0], None, vals[1]]
            if len(vals) != 3:
                raise ValueError(f"ENESI {tid}: {lab!r} reads {vals}")
            fixed.append((lab, vals))
        if not fixed or fixed[-1][0] != "Total":
            raise ValueError(f"ENESI {tid}: no Total row ({[r[0] for r in fixed]})")
        *parts, (_, total) = fixed
        if not rate:
            for j in range(3):
                s = sum(v[j] for _, v in parts if v[j] is not None)
                if abs(s - total[j]) > len(parts):
                    raise ValueError(f"ENESI {tid}: column {j} sums to {s}, Total {total[j]}")
            for _, v in fixed:
                if abs(v[0] + v[1] - v[2]) > 2:
                    raise ValueError(f"ENESI {tid}: {v} -- parts do not sum")
        for lab, vals in fixed:
            for ctx, v in zip(cols, vals):
                if v is None:
                    continue
                dims = dict(ctx)
                if lab != "Total":
                    if kind == "age":
                        dims["age_group"] = lab
                    elif kind == "education":
                        dims["education"] = lab
                    else:
                        dims["geography"] = lab
                key = (topic, tuple(sorted(dims.items())))
                if key in seen:
                    if seen[key] != v:
                        raise ValueError(f"ENESI {tid}: {key} = {v}, earlier {seen[key]}")
                    continue
                seen[key] = v
                out.append(C.row(topic=topic,
                                 definition="strict" if rate else "not_applicable",
                                 value=v, series_label=label, survey=_ENESI,
                                 period="2017", reference_period="ENESI 2017",
                                 frequency="ad_hoc", working_age_base=_BASE,
                                 series_code=f"ENESI {tid}", **dims))
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        name = os.path.basename(p).upper()
        rows += _enesi(p) if "ENESI" in name else _ente(p)
    return pd.DataFrame(rows)
