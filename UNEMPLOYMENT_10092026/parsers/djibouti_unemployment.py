"""Djibouti — INSTAD, RGPH-3 (Troisième Recensement Général de la Population et
de l'Habitat, May 2024), Tome 3 "Caractéristiques économiques de la
population".

The SAME volume `labour/` reads for occupation and formality; this module takes
its headline series. A census, so the universe is the whole resident
population; the volume works on the 15+ (the active population is 330 726).

* Tableau n°18-21  unemployment rates, "BIT" and "élargi" side by side, by
                   region, milieu, age group and education x sex, on four
                   populations: 15-64 (n°18), 15-59 (n°19), and the youth
                   15-34 (n°20) and 15-24 (n°21);
* Tableau n°9      taux d'occupation over the working-age population -- the
                   employment-to-population ratio -- by region, milieu, age
                   group and education x sex (15+);
* Tableau n°5      the active population by sex x region / milieu (counts);
* Tableau n°17     occupés / chômeurs / chômeurs découragés / ensemble by
                   region (counts).

BIT AND ÉLARGI ARE THE NSO'S OWN LABELS, AND THEY ADD UP. Tableau n°17 gives
111 360 chômeurs and 37 202 chômeurs découragés in an active population of
330 726: 111 360 / (330 726 - 37 202) = 37,94 is the BIT rate the prose
reports (37,9), and (111 360 + 37 202) / 330 726 = 44,92 the élargi (44,9).
So "Taux de chômage BIT" -> strict, "élargi" -> broad, and the n°17 / n°5
"active population" (which counts the discouraged) is a BROAD labour force.

TABLEAUX n°9 AND n°10 CARRY THE SAME CAPTION ("... par rapport à la
population en âge de travailler") OVER DIFFERENT NUMBERS (Ensemble 27,6 and
55,1). n°9 is the one the caption describes: Annexe n°29 prints the same
percentages as employed / working-age population (men in Djibouti-Ville
91 976 = 38,3%). n°10's 55,1 is 182 164 / 330 726 -- employed over the ACTIVE
population, i.e. 100 minus the élargi rate -- its caption is wrong, and it is
not collected (it adds nothing the broad rate does not say).

REPEATED ROWS ARE CHECKED, NOT RE-EMITTED. n°18-21 print the same five-year
age rows (15-19 ... 30-34 appear in all four, identically): they are taken
from n°18 and every repeat must agree. n°20 and n°21 are YOUTH tables -- their
region / milieu / education / Ensemble rows are filed as
`youth_unemployment_rate` with age_group 15-34 / 15-24. n°17's Ensemble row is
n°5's Ensemble column: checked equal, emitted once.

REGION SPELLING: n°21 prints "Djibouti-ville"; it is recorded as
"Djibouti-Ville" like every other table, so the region joins across its own
indicators. Every other label is as printed.

NOT COLLECTED: n°10 (above); n°22-23 (distributions of the unemployed);
the annex count tables n°28-36 (n°28 is labour's sector table; n°29's
percentages repeat n°9); the 15+ national unemployment rates, which the volume
gives only in Graphique n°17 and the prose.

CROSS-CHECK: n°18 Ensemble BIT 38,2 / élargi 45,1 (F 45,1 / 53,2); n°20
youth 15-34 BIT 54,7; n°21 15-24 BIT 69,1; n°9 EPR 27,6 (F 19,3); n°17
chômeurs 111 360, découragés 37 202; n°5 active 330 726 (M 191 144).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = ("Troisième Recensement Général de la Population et de l'Habitat "
           "(RGPH-3)")
_BASE = dict(survey=_SURVEY, period="2024", reference_period="RGPH-3, May 2024",
             frequency="ad_hoc")
_REGIONS = ["Djibouti-Ville", "Ali-Sabieh", "Dikhil", "Tadjourah", "Obock", "Arta"]
_SEX3 = [{"sex": "male"}, {"sex": "female"}, {}]
_SECTIONS = {"Région": "geography", "Milieu de résidence": "locality",
             "Groupe d'âges": "age_group", "Niveau d'instruction": "education"}


def _pages(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [p.extract_text() or "" for p in pdf.pages]


def _table(pages: list[str], n: int) -> list[str]:
    cap = re.compile(rf"^Tableau n°{n}\.", re.M)
    for t in pages:
        m = cap.search(t)
        if m and not re.search(r"\.{5}", t[m.end():m.end() + 200]):
            body = t[m.end():]
            body = body[:body.index("Source")] if "Source" in body else body
            return [ln.strip() for ln in body.splitlines() if ln.strip()]
    raise ValueError(f"RGPH-3: Tableau n°{n} not found")


def _num(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def _grid(lines: list[str], ncols: int, where: str):
    """(section, label, values) for every data row of a sectioned table."""
    out, section = [], None
    val = r"\d+(?:,\d+)?"
    for ln in lines:
        if ln in _SECTIONS:
            section = _SECTIONS[ln]
            continue
        # "Secondaire 1" / "Secondaire 2": a label may end in its own digit.
        m = re.match(rf"^(Secondaire \d|.*?[A-Za-zé+])\s+"
                     rf"((?:{val}\s+){{{ncols - 1}}}{val})$", ln)
        if not m:
            continue
        label = m.group(1)
        if label == "Djibouti-ville":
            label = "Djibouti-Ville"
        if label == "Ensemble":
            out.append((None, label, [_num(v) for v in m.group(2).split()]))
        elif section is None:
            continue                       # header words with digits
        else:
            out.append((section, label, [_num(v) for v in m.group(2).split()]))
    if not out or out[-1][1] != "Ensemble":
        raise ValueError(f"{where}: no closing Ensemble row")
    return out


def _dims(section, label) -> dict:
    if section is None:
        return {}
    if section == "locality":
        return {"locality": "urban" if label == "Urbain" else "rural",
                "locality_label": label}
    if section == "age_group":
        return {"age_group": label.replace(" ans", "").replace(" et +", "+")}
    return {section: label}


def _unemployment(pages) -> list[dict]:
    out, ages = [], {}
    specs = [(18, "unemployment_rate", "15-64", None),
             (19, "unemployment_rate", "15-59", None),
             (20, "youth_unemployment_rate", "15+", "15-34"),
             (21, "youth_unemployment_rate", "15+", "15-24")]
    for n, topic, base, youth in specs:
        rows = _grid(_table(pages, n), 6, f"RGPH-3 T{n}")
        expect = {"geography": 6, "locality": 2, "education": 5}
        got = {k: sum(1 for s, _, _ in rows if s == k) for k in expect}
        if got != expect:
            raise ValueError(f"RGPH-3 T{n}: sections read {got}, want {expect}")
        for section, label, v in rows:
            if section == "age_group":
                if label in ages:
                    if ages[label] != v:
                        raise ValueError(f"RGPH-3 T{n}: age row {label} {v} "
                                         f"differs from n°18's {ages[label]}")
                    continue
                if n != 18:
                    raise ValueError(f"RGPH-3 T{n}: age row {label} not in n°18")
                ages[label] = v
            dims = _dims(section, label)
            age = youth if youth and section != "age_group" else dims.pop("age_group", "Total")
            dims.pop("age_group", None)
            t = topic if section != "age_group" else "unemployment_rate"
            for (sx, (dfn, lab)), x in zip(
                    [(s, d) for s in _SEX3 for d in (("strict", "Taux de chômage BIT"),
                                                     ("broad", "Taux de chômage élargi"))],
                    v):
                out.append(C.row(topic=t, definition=dfn, value=x,
                                 series_label=lab, age_group=age,
                                 working_age_base=base if t == "unemployment_rate"
                                 or youth is None else "15+",
                                 series_code=f"RGPH-3 T{n}", **_BASE, **sx, **dims))
    if len(ages) != 10:
        raise ValueError(f"RGPH-3 T18: {len(ages)} age rows, want 10")
    return out


def _epr(pages) -> list[dict]:
    rows = _grid(_table(pages, 9), 3, "RGPH-3 T9")
    out = []
    for section, label, v in rows:
        dims = _dims(section, label)
        for sx, x in zip(_SEX3, v):
            out.append(C.row(topic="employment_to_population_ratio", value=x,
                             series_label="Taux d'occupation par rapport à la "
                                          "population en âge de travailler",
                             working_age_base="15+", series_code="RGPH-3 T9",
                             **_BASE, **sx, **dims))
    if len(rows) != 6 + 2 + 11 + 5 + 1:
        raise ValueError(f"RGPH-3 T9: {len(rows)} rows")
    return out


def _split(groups: list[str], n: int, ok) -> list[float]:
    """Digit groups -> n numbers that satisfy `ok` (the table's arithmetic):
    "149 118 111 082 260 200" reads several ways with space thousands."""
    import itertools
    sols = []
    for cuts in itertools.combinations(range(1, len(groups)), n - 1):
        b = (0, *cuts, len(groups))
        parts = [groups[x:y] for x, y in zip(b, b[1:])]
        if any(len(p[0]) > 3 or any(len(g) != 3 for g in p[1:]) for p in parts):
            continue
        v = [float("".join(p)) for p in parts]
        if ok(v):
            sols.append(v)
    if len(sols) != 1:
        raise ValueError(f"RGPH-3: groups {groups} split {len(sols)} ways")
    return sols[0]


def _counts(pages) -> list[dict]:
    out, seen = [], {}

    def emit(topic, dfn, label, value, code, **dims):
        key = (topic, label, tuple(sorted(dims.items())))
        if key in seen:
            if seen[key] != value:
                raise ValueError(f"RGPH-3: {key} = {value}, earlier {seen[key]}")
            return
        seen[key] = value
        out.append(C.row(topic=topic, definition=dfn, value=value,
                         series_label=label, working_age_base="15+",
                         series_code=code, **_BASE, **dims))

    lf = "Population active (occupés, chômeurs et chômeurs découragés)"
    # Tableau n°5: Masculin | Féminin | Ensemble | % (the % is a distribution
    # across regions -- not collected).
    lines = _table(pages, 5)
    rows = []
    for ln in lines:
        m = re.match(r"^(.*?[A-Za-zé])\s+([\d ]+?)\s+\d+(?:,\d+)?$", ln)
        if m and m.group(1) in _REGIONS + ["Urbain", "Rural", "Ensemble"]:
            rows.append((m.group(1), _split(m.group(2).split(), 3,
                                            lambda v: abs(v[0] + v[1] - v[2]) <= 2)))
    names = [r[0] for r in rows]
    if names != _REGIONS + ["Urbain", "Rural", "Ensemble"]:
        raise ValueError(f"RGPH-3 T5: rows {names}")
    for label, v in rows:
        if abs(v[0] + v[1] - v[2]) > 2:
            raise ValueError(f"RGPH-3 T5: {label} sexes do not sum")
        if label in _REGIONS:
            dims = {"geography": label}
        elif label in ("Urbain", "Rural"):
            dims = {"locality": label.lower().replace("urbain", "urban"),
                    "locality_label": label}
        else:
            dims = {}
        for sx, x in zip(_SEX3, v):
            emit("labour_force", "broad", lf, x, "RGPH-3 T5", **sx, **dims)
    # Tableau n°17: rows by status, columns the six regions then Ensemble (the
    # rotated header is unreadable; the order is n°5's, proved by the
    # Ensemble row equalling n°5's Ensemble column, checked by `emit`).
    lines = _table(pages, 17)
    # "Chômeurs découragés" wraps AROUND its numbers: "Chômeurs" / bare
    # numbers / "découragés" -- the bare number line is that row.
    k = lines.index("découragés")
    if lines[k - 2] != "Chômeurs" or not re.fullmatch(r"[\d ]+", lines[k - 1]):
        raise ValueError(f"RGPH-3 T17: découragés block reads {lines[k - 2:k + 1]}")
    rowtext = {"employed": next(x for x in lines if x.startswith("Actifs Occupés")),
               "unemployed": next(x for x in lines if re.match(r"^Chômeurs\s+\d", x)),
               "potential_labour_force": lines[k - 1],
               "labour_force": next(x for x in lines if x.startswith("Ensemble"))}
    spec = [("employed", "not_applicable", "Actifs occupés"),
            ("unemployed", "strict", "Chômeurs"),
            ("potential_labour_force", "not_applicable", "Chômeurs découragés"),
            ("labour_force", "broad", lf)]
    vals = {}
    for topic, dfn, label in spec:
        groups = re.findall(r"\d+", re.sub(r"^\D+", "", rowtext[topic]))
        # Seven columns; the last (Ensemble) is the sum of the six regions.
        v = _split(groups, 7, lambda v: abs(sum(v[:6]) - v[6]) <= 2)
        if len(v) != 7:
            raise ValueError(f"RGPH-3 T17: {label} reads {v}")
        vals[topic] = v
        for g, x in zip(_REGIONS + [None], v):
            emit(topic, dfn, label, x, "RGPH-3 T17",
                 **({"geography": g} if g else {}))
    for j in range(7):
        if abs(vals["employed"][j] + vals["unemployed"][j]
               + vals["potential_labour_force"][j] - vals["labour_force"][j]) > 2:
            raise ValueError(f"RGPH-3 T17: column {j} does not sum")
    return out


# --------------------------------------------------------------------------
# EDST -- Enquête Djiboutienne sur les Statistiques du Travail (quarterly)
# --------------------------------------------------------------------------

_EDST = "Enquête Djiboutienne sur les Statistiques du Travail (EDST)"
# Annexe -> (topic, definition, series label as the annex heads it)
_EDST_ANNEXES = {
    2: ("labour_force_participation_rate", "strict", "Taux de participation"),
    3: ("employment_to_population_ratio", "not_applicable", "Ratio emploi/population"),
    4: ("unemployment_rate", "strict", "Taux de chômage"),
    5: ("underemployment_rate", "broad",
        "Taux combiné du chômage et sous-emploi lié au temps du travail"),
    6: ("labour_underutilisation_rate", "broad",
        "Taux combiné du chômage et de la main d'œuvre potentielle"),
    7: ("labour_underutilisation_rate", "broad", "Sous-utilisation de la main d'œuvre"),
    9: ("neet_rate", "not_applicable",
        "NEEF - Ni en emploi, ni en études, ni en formation"),
}
# Annexe 1 rows taken (the current quarter's three columns): counts, and the
# time-related underemployment rate, which no detailed annex repeats.
_EDST_A1 = [
    # labels wrap AROUND their numbers ("Population en âge de" / numbers /
    # "travailler"), so each is matched on its first fragment
    (r"^Population en âge de", "working_age_population", "not_applicable",
     "Population en âge de travailler"),
    (r"^Population dans la main", "labour_force", "not_applicable",
     "Population dans la main d'œuvre"),
    (r"^Population en emploi", "employed", "not_applicable", "Population en emploi"),
    (r"^Population au chômage", "unemployed", "strict", "Population au chômage"),
    (r"^Population hors main", "outside_labour_force", "not_applicable",
     "Population hors main d'œuvre"),
    (r"^Main d.œuvre potentielle", "potential_labour_force", "not_applicable",
     "Main d'œuvre potentielle"),
    (r"^Taux du sous-emploi li", "underemployment_rate", "not_applicable",
     "Taux du sous-emploi lié au temps"),
]
# Annexe 1 also prints LFPR / EPR / SU1-SU4 for the quarter; they are CHECKED
# against the detailed annexes' totals, not emitted twice. Where the note
# disagrees with itself the detailed annex is collected and the gap is listed
# here, so a new disagreement raises instead of passing silently.
_EDST_A1_RATES = [(r"^Taux de participation", 2), (r"^Ratio population / emploi", 3),
                  (r"^SU1", 4), (r"^SU2", 5), (r"^SU3", 6), (r"^SU4", 7)]
# 2025-Q4: Annexe 1 prints SU1 37,7; Annexe 4 prints 37,3 -- and the note's
# own counts give 108 739 / 291 392 = 37,32, so Annexe 4 is right.
_EDST_KNOWN_GAPS = {("2025-Q4", 4, "total"): (37.7, 37.3)}
# 2025-Q2: the note's own "Main d'œuvre potentielle" (100 758 / 95 672 /
# 196 430) is the SU3 NUMERATOR -- unemployed + potential (117 985 + 78 444
# = 196 429) -- not the potential labour force; the Q3 note reprints Q2 as
# 33 469 / 44 975 / 78 444, which SU3 (52,3) confirms. Not collected for Q2.
_EDST_BAD_PLF = {"2025-Q2"}
_REGION_NAMES = {"djibouti ville": "Djibouti-ville", "djibouti-ville": "Djibouti-ville",
                 "autres régions": "Autres régions", "autre régions": "Autres régions"}
_EDST_STRIP = re.compile(r"^(?:Sexe|SEXE|Groupes? d.\s?âges?|Groupe|d\s?.\s?âge|"
                         r"Milieu de résidence|Milieu de|MILIEU DE|résidence|"
                         r"RESIDENCE|Nationalité|Grandes régions|Grandes|régions)\s+")


def _edst_ctx(label: str):
    """Dimensions for a detailed-annex row label, or None to skip it."""
    lab = re.sub(r"(\d)\s+(\d)", r"\1\2", label).strip()     # "2 5-34"
    low = lab.lower()
    if low in ("ensemble pays", "total djibouti", "national", "total",
               "total national"):
        return {}
    if low == "hommes":
        return {"sex": "male"}
    if low == "femmes":
        return {"sex": "female"}
    if re.fullmatch(r"\d\d-\d\d|65\+", lab):
        return {"age_group": lab}
    if low in ("urbain", "rural"):
        return {"locality": "urban" if low == "urbain" else "rural",
                "locality_label": lab.capitalize()}
    if low in _REGION_NAMES:
        return {"geography": _REGION_NAMES[low]}
    if low in ("djiboutienne", "non djiboutienne", "etranger"):
        return None                 # nationality: no column in this schema
    if low == "région 1":
        # T2 Annexe 7 labels its first "grande région" "Région 1" where every
        # other annex prints Djibouti-ville. Probably the same row, but the
        # note does not say so -- not collected rather than relabelled.
        return None
    raise ValueError(f"EDST: unclassifiable row {label!r}")


def _split_mft(groups: list[str]):
    """Trailing digit groups -> [M, F, T] with M + F = T (to 3), or None.
    The SHORTEST trailing run that splits is the current quarter; the
    previous quarter's columns sit before it."""
    import itertools
    for start in range(len(groups) - 3, max(-1, len(groups) - 10), -1):
        g = groups[start:]
        sols = []
        for cuts in itertools.combinations(range(1, len(g)), 2):
            b = (0, *cuts, len(g))
            parts = [g[x:y] for x, y in zip(b, b[1:])]
            if any(len(p[0]) > 3 and len(p) > 1 for p in parts) or \
                    any(len(x) != 3 for p in parts for x in p[1:]):
                continue
            v = [float("".join(p)) for p in parts]
            if abs(v[0] + v[1] - v[2]) <= 3:
                sols.append(v)
        if len(sols) == 1:
            return sols[0]
    return None


def _edst(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    head = " ".join(pages[:2])
    # "(EDST) T4-2025" or "INSTAD- EDST- T2- 2025" on the cover
    m = re.search(r"EDST\)?\s*-?\s*T([1-4])\s*-\s*(20\d\d)", head)
    if not m:
        raise ValueError("EDST: cannot read the note's quarter")
    period, ref = f"{m.group(2)}-Q{m.group(1)}", f"T{m.group(1)}-{m.group(2)}"
    text = "\n".join(pages)
    blocks = {}
    for am in re.finditer(r"^Annexe ?(\d+) ?:", text, re.M):
        n = int(am.group(1))
        first = text[am.end():am.end() + 400].split("\n")
        if re.search(r"\.{4}", " ".join(first[:2])) or n in blocks:
            continue                # list of annexes
        end = re.search(r"^Source", text[am.end():], re.M)
        blocks[n] = text[am.end():am.end() + (end.start() if end else 3000)]
    out = []
    base = dict(survey=_EDST, period=period, reference_period=ref,
                frequency="quarterly", working_age_base="16+")
    totals = {}
    # Detailed annexes: the first number after the label is the estimate.
    for n, (topic, dfn, label) in _EDST_ANNEXES.items():
        if n not in blocks:
            raise ValueError(f"EDST {ref}: Annexe {n} not found")
        seen = set()
        for ln in blocks[n].splitlines():
            ln = ln.strip()
            # T1's Annexe 3 prints dot decimals ("28.8"), every other "28,8"
            # The label may end in a digit ("16-24"): the trailing run of
            # estimate, s.e., CI bounds, CV and deff anchors the row.
            mm = re.match(r"^(.*?\S)\s+(\d+[,.]\d)\s+\d+[,.]\d+"
                          r"(?:\s+[\d,.]+){2,4}\s*$", ln)
            if not mm:
                continue
            lab = _EDST_STRIP.sub("", _EDST_STRIP.sub("", mm.group(1).strip()))
            ctx = _edst_ctx(lab)
            if ctx is None:
                continue
            key = tuple(sorted(ctx.items()))
            if key in seen:
                raise ValueError(f"EDST {ref} Annexe {n}: {lab!r} read twice")
            seen.add(key)
            v = float(mm.group(2).replace(",", "."))
            if not ctx and n in totals:
                raise ValueError(f"EDST {ref} Annexe {n}: two national rows")
            if not ctx:
                totals[n] = v
            if ctx in ({"sex": "male"}, {"sex": "female"}):
                totals[(n, ctx["sex"])] = v
            age = ctx.pop("age_group", "16-24" if n == 9 else "Total")
            out.append(C.row(topic=topic, definition=dfn, value=v, series_label=label,
                             age_group=age, series_code=f"EDST Annexe {n}",
                             **base, **ctx))
        if n not in totals:
            raise ValueError(f"EDST {ref} Annexe {n}: no national row")
    # Annexe 1: the current quarter is the LAST three columns (Homme, Femme,
    # Total); the T2-T4 notes print the previous quarter first.
    a1 = blocks.get(1)
    if a1 is None:
        raise ValueError(f"EDST {ref}: Annexe 1 not found")
    lines = [ln.strip() for ln in a1.splitlines() if ln.strip()]

    def row_nums(pat):
        k = next((i for i, x in enumerate(lines) if re.match(pat, x)), None)
        if k is None:
            raise ValueError(f"EDST {ref} Annexe 1: {pat} not found")
        joined = lines[k]
        if k + 1 < len(lines) and re.fullmatch(r"[\d ,]+", lines[k + 1]):
            joined += " " + lines[k + 1]
        return re.sub(pat, "", joined)

    sx3 = [{"sex": "male"}, {"sex": "female"}, {}]
    got_counts = {}
    for pat, topic, dfn, label in _EDST_A1:
        txt = row_nums(pat)
        if topic == "underemployment_rate":
            v = [float(x.replace(",", ".")) for x in re.findall(r"\d+,\d+|\d+", txt)[-3:]]
            su2 = [float(x.replace(",", ".")) for x in
                   re.findall(r"\d+,\d+|\d+", row_nums(r"^SU2"))[-3:]]
            if v == su2:
                # THE T2 NOTE'S OWN ROW IS A COPY OF ITS SU2 ROW (39,2 / 53,8 /
                # 44,3); the T3 note reprints T2 as 6,7 / 9,8 / 7,6. Not taken.
                continue
        else:
            v = _split_mft(re.findall(r"\d+", txt))
            if v is None:
                raise ValueError(f"EDST {ref} Annexe 1: cannot split {label}: {txt!r}")
            got_counts[topic] = v[2]
        if topic == "potential_labour_force":
            # Held to the note's own SU3: (U + PLF) / (LF + PLF).
            u, lf, plf = (got_counts["unemployed"], got_counts["labour_force"], v[2])
            su3 = 100 * (u + plf) / (lf + plf)
            ok = abs(su3 - totals[6]) <= 0.15
            if period in _EDST_BAD_PLF:
                if ok:
                    raise ValueError(f"EDST {ref}: potential labour force now "
                                     f"agrees with SU3 -- remove it from _EDST_BAD_PLF")
                continue
            if not ok:
                raise ValueError(f"EDST {ref}: potential labour force {plf} gives "
                                 f"SU3 {su3:.2f}, Annexe 6 prints {totals[6]}")
        for ctx, x in zip(sx3, v):
            out.append(C.row(topic=topic, definition=dfn, value=x, series_label=label,
                             series_code="EDST Annexe 1", **base, **ctx))
    gaps = []
    for pat, n in _EDST_A1_RATES:
        v = [float(x.replace(",", ".")) for x in re.findall(r"\d+,\d+|\d+", row_nums(pat))[-3:]]
        for sx, got in zip(("male", "female", "total"), v):
            want = totals[n] if sx == "total" else totals.get((n, sx))
            if want is None or abs(got - want) <= 0.05:
                continue
            if _EDST_KNOWN_GAPS.get((period, n, sx)) == (got, want):
                continue
            gaps.append(((period, n, sx), (got, want)))
    if gaps:
        raise ValueError(f"EDST {ref}: Annexe 1 disagrees with the detailed annexes: {gaps}")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        with pdfplumber.open(p) as pdf:
            first = " ".join((pdf.pages[i].extract_text() or "") for i in range(2))
        if "EDST" in first:
            rows += _edst(p)
        else:
            pages = _pages(p)
            rows += _unemployment(pages) + _epr(pages) + _counts(pages)
    return pd.DataFrame(rows)
