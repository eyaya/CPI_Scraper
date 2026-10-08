"""Algeria — ONS Rétrospective Statistique 1962-2020, Chapitre II "Emploi"
(the same PDF `labour/` reads), plus ONS's 2024 unemployment communiqué.

THE RETROSPECTIVE REPRINTS EVERY HOUSEHOLD EMPLOYMENT SURVEY ROUND, June 2000
to May 2019 -- 23 rounds, one page each (Tableaux 17-35), two a year (April and
September) in 2014 and 2016-2018. From each page:

* "Quelques indicateurs": taux d'activité, taux d'emploi, taux de chômage;
* population active / occupée / en chômage (counts);
* employed and unemployed by sex x strate (urbain / rural / total);
* employed and unemployed by age group.

and from the series tables at the end of the chapter:

* Tableau 36  taux de chômage back to 1966 (censuses RGPH 1966/1977/1987,
              Main d'œuvre surveys 1982-1992, LSMS 1995, ONS 1996/1997);
* Tableau 37  taux d'activité back to 1977 (incl. RGPH 1998).
  Only the years BEFORE the first round page are taken from them; every year
  that also has a round page is CHECKED against it (Tableau 38, the employment
  rate, starts in 2000 and is checked only).
* Tableau 16.1  the 1998 census labour force ("population active") by wilaya
              and sex.

DATING, as `labour/` does it: each round is dated to the QUARTER of its
reference month (juin 2000 -> 2000-Q2, septembre -> Q3, décembre 2008 ->
2008-Q4), the month kept in reference_period; the series-table years before
2000 are annual. Units are persons to 2007 and thousands ("Unité : en
millier") from December 2008 -- read per page, never assumed.

READING. The round tables print adjacent counts with SPACE thousands
separators ("3 098 380 2 284 529 5 382 909 ..."), which read more than one
way. Columns are therefore taken from WORD GEOMETRY -- numbers are clustered
by the gap between words (a thousands space is ~2 pt, a column gap 8 pt or
more) -- and every row is then held to the table's arithmetic: urbain + rural
= total for each population; masculin + féminin = ensemble in every column;
the age groups sum to the Total row. Tableau 16.1 contains a misprinted
group ("181 7 03" for Skikda's 181 703) and is split under masculin + féminin
= ensemble, requiring exactly one solution.

DEFINITIONS. ONS's own footnote to Tableau 36 defines the unemployment rate as
"population en chômage (STR 1 + STR 2) / population active", STR being persons
"sans travail et à la recherche d'un emploi" -- the job-SEEKING (strict)
concept -- so the round and series rates are filed strict. The rates of
activity and employment are defined on the population aged 15 and over
(footnotes ** and ***), so their base is 15+. The COUNTS are not on a 15+
base -- the June 2000 age table counts 25 075 employed under 15 -- and carry
"not stated", as in `labour/`; so do the unemployment rates, whose labour-
force denominator includes them, and the pre-2000 series rates, whose job-
seeker age limits the footnote says varied (15-60+, 16+, 16-64, 16-60).

2024: ONS's only post-2019 labour release is a three-page communiqué,
"Résultats préliminaires relatifs à l'enquête Activité, Emploi et Chômage.
Octobre 2024", whose title reads "Le taux de chômage en Algérie pour l'année
2024 est de 9,7%". It is collected as that ONE figure, labelled as published
(preliminary, after ONS's stated adjustments), reference the last week of
October 2024 -> 2024-Q4. The communiqué states no definition, so the row
carries not_applicable rather than an inferred one. Nothing else in it is a
statistic.

PUBLISHED MISPRINT: December 2008's age table prints employed 40-44 as "0"
(1 082 thousand short of the Total) -- not collected, pinned and re-checked.
December 2008 also splits by dispersion (aggloméré / épars), filed as
locality "other" with the printed label, as labour/ files RGPH 1987.
Septembre 2018's employed age groups sum to 10 800 thousand against a printed
Total of 11 001 (the unemployed column adds up): every printed group is kept,
the 201 gap is pinned.

NOT COLLECTED: the sector distributions (`labour/` collects them); Tableau 16.2
(nomadic households); the shares beside the counts.

CROSS-CHECK: juin 2000 taux de chômage 28,89, population active 8 690 855,
employed urban men 3 098 380; avril 2016 taux d'activité 42,0, unemployed
1 198 (thousands); mai 2019 taux de chômage 11,4; 1966 taux de chômage 32,9;
RGPH 1998 population active 8 056 789 (Alger 909 780); 2024 9,7.
"""
from __future__ import annotations

import itertools
import re

import pandas as pd
import pdfplumber

from . import _common as C

_ONS = "Enquête emploi auprès des ménages (ONS)"
# period -> (age label, column, shortfall vs the Total) for a printed zero.
_KNOWN_BAD_AGE = {"2008-Q4": ("40-44", 0, 1082.0)}
# (period, column) -> printed Total minus the sum of the printed age groups.
# Septembre 2018: employed groups sum to 10 800 thousand, Total 11 001.
_KNOWN_AGE_GAP = {("2018-Q3", 0): 201.0}
_MONTH_Q = {"janvier": 1, "fevrier": 1, "février": 1, "mars": 1, "avril": 2,
            "mai": 2, "juin": 2, "juillet": 3, "aout": 3, "août": 3,
            "septembre": 3, "octobre": 4, "novembre": 4, "decembre": 4,
            "décembre": 4}


def _fr(x: str) -> float:
    return float(x.replace(" ", "").replace(",", "."))


def _lines(page) -> list[list[dict]]:
    rows: dict[int, list[dict]] = {}
    for w in page.extract_words():
        rows.setdefault(round(w["top"] / 3), []).append(w)
    return [sorted(rows[k], key=lambda w: w["x0"]) for k in sorted(rows)]


def _cells(words: list[dict], label_x: float) -> tuple[str, list]:
    """(label, cells) of one table line: words left of `label_x` are the label;
    the rest are clustered into numbers by the gap between words. A lone "/"
    or "-" is an empty cell."""
    label = " ".join(w["text"] for w in words if w["x1"] <= label_x)
    rest = [w for w in words if w["x1"] > label_x]
    cells, cur, last_x1 = [], [], None
    for w in rest:
        if w["text"] in ("/", "-"):
            if cur:
                cells.append(cur)
                cur = []
            cells.append(None)
            last_x1 = w["x1"]
            continue
        if cur and last_x1 is not None and w["x0"] - last_x1 > 5:
            cells.append(cur)
            cur = []
        cur.append(w["text"])
        last_x1 = w["x1"]
    if cur:
        cells.append(cur)
    return label, [None if c is None else _fr("".join(c)) for c in cells]


def _row_cells(words: list[dict], label_word: dict, heads: list[dict],
               ref: str) -> list:
    """The cells of the row whose label word is `label_word`: words within 5 pt
    of its baseline, right of it, rebuilt into NUMBERS by gap (a thousands
    space is ~2 pt, a column gap 8 pt or more), each given to the header whose
    right edge it is nearest. A lone "-" or "/" is an empty cell."""
    row = sorted((w for w in words if abs(w["top"] - label_word["top"]) < 5
                  and w["x0"] > label_word["x1"] + 5), key=lambda w: w["x0"])
    nums, cur = [], []
    for w in row:
        if cur and (w["x0"] - cur[-1]["x1"] > 5 or w["text"] in ("-", "/")
                    or cur[-1]["text"] in ("-", "/")):
            nums.append(cur)
            cur = []
        cur.append(w)
    if cur:
        nums.append(cur)
    cells = [None] * len(heads)
    for num in nums:
        j = min(range(len(heads)), key=lambda k: abs(num[-1]["x1"] - heads[k]["x1"]))
        if cells[j] is not None:
            raise ValueError(f"ONS {ref}: two numbers under one column")
        txt = "".join(w["text"] for w in num)
        cells[j] = None if txt in ("-", "/") else _fr(txt)
    return cells


def _round_page(page, text: str) -> list[dict] | None:
    m = re.search(r"Quelques indicateurs\s*[-–]+\s*([A-Za-zéû]+)\s+(\d{4})", text)
    if not m:
        return None
    month, year = m.group(1).lower(), m.group(2)
    period = f"{year}-Q{_MONTH_Q[month]}"
    ref = f"{month} {year}"
    thousands = bool(re.search(r"Unit[ée]\s*:\s*en millier", text))
    unit = "thousand_persons" if thousands else "persons"
    kw = dict(survey=_ONS, period=period, reference_period=ref,
              frequency="ad_hoc")
    out = []

    def add(topic, v, label, code, base="not stated", definition="not_applicable",
            measure=None, unit_=None, **ctx):
        out.append(C.row(topic=topic, value=v, series_label=label,
                         definition=definition, series_code=code,
                         working_age_base=base, measure=measure, unit=unit_,
                         **kw, **ctx))

    code = re.search(r"Tableau\s*(\d+)\s*:", text)
    code = f"ONS Rétrospective T{code.group(1)}" if code else "ONS Rétrospective"

    # rates
    rates = {}
    for lab, topic, base, definition in (
            ("Taux d’activité", "labour_force_participation_rate", "15+", "not_applicable"),
            ("Taux d’emploi", "employment_to_population_ratio", "15+", "not_applicable"),
            ("Taux de chômage", "unemployment_rate", "not stated", "strict")):
        # avril 2017 prints a whole number ("Taux d'activité 42")
        r = re.search(re.escape(lab) + r"\s+(\d+(?:,\d+)?)\s*$", text, re.M)
        if not r:
            raise ValueError(f"ONS {ref}: '{lab}' not found")
        rates[topic] = _fr(r.group(1))
        add(topic, rates[topic], lab, code, base=base, definition=definition)

    # population active / occupée / en chômage
    counts = {}
    for lab, topic in (("Population active", "labour_force"),
                       ("Population occupée", "employed"),
                       ("Population en chômage", "unemployed")):
        # "8 690 855 100" (space-grouped) or "11423 100" (ungrouped, 2012+);
        # the share column that follows is 100 or carries a decimal comma.
        r = re.search(re.escape(lab) + r"\s+(\d{1,3}(?: \d{3})+|\d+)\s+(?:100\b|\d+,\d)",
                      text)
        if not r:
            raise ValueError(f"ONS {ref}: '{lab}' count not found")
        counts[topic] = _fr(r.group(1))
        add(topic, counts[topic], lab, code, unit_=unit)
    if abs(counts["labour_force"] - counts["employed"] - counts["unemployed"]) > 1:
        raise ValueError(f"ONS {ref}: active != occupée + chômage")
    if abs(100 * counts["unemployed"] / counts["labour_force"]
           - rates["unemployment_rate"]) > 0.15:
        raise ValueError(f"ONS {ref}: taux de chômage != chômage / active")

    lines = _lines(page)
    # sex x strate: header "Urbain Rural Total Urbain Rural Total"
    # The header is "Urbain Rural Total" twice -- sometimes after a "Strate"
    # stub on the same line -- except in December 2008, which splits by
    # DISPERSION ("Aggloméré Epars Total"), filed as labour/ files RGPH 1987.
    hi = strata = None
    for i, ln in enumerate(lines):
        words = [w["text"] for w in ln]
        for pair, ctxs in (
                (["Urbain", "Rural", "Total"],
                 [{"locality": "urban", "locality_label": "Urbain"},
                  {"locality": "rural", "locality_label": "Rural"}, {}]),
                (["Aggloméré", "Epars", "Total"],
                 [{"locality": "other", "locality_label": "Aggloméré"},
                  {"locality": "other", "locality_label": "Epars"}, {}])):
            if words[-6:] == pair * 2:
                hi, strata = i, ctxs
                first = ln[len(words) - 6]
        if hi is not None:
            break
    if hi is None:
        raise ValueError(f"ONS {ref}: sex x strate header not found")
    # READ BY COLUMN POSITION. A row's total cells can sit on a baseline a
    # point or two off its other cells (septembre 2010), so cells are taken by
    # the six header words' right edges (numbers are right-aligned under them)
    # and rows by their label's vertical position, not by text lines.
    heads = lines[hi][len(lines[hi]) - 6:]
    words = page.extract_words()
    grid = {}
    for lab in ("Masculin", "Féminin", "Ensemble"):
        lw = next((w for w in words if w["text"] == lab
                   and w["top"] > heads[0]["top"]), None)
        if lw is None:
            raise ValueError(f"ONS {ref}: row {lab} not found")
        row = [w for w in words if abs(w["top"] - lw["top"]) < 5
               and w["x0"] > lw["x1"] + 5]
        # First rebuild NUMBERS from the row's words (a thousands space is a
        # ~2 pt gap, a column gap 8 pt or more), then give each number to
        # the header whose right edge it is nearest.
        row = sorted(row, key=lambda w: w["x0"])
        nums, cur = [], []
        for w in row:
            if cur and (w["x0"] - cur[-1]["x1"] > 5 or w["text"] in ("-", "/")
                        or cur[-1]["text"] in ("-", "/")):
                nums.append(cur)
                cur = []
            cur.append(w)
        if cur:
            nums.append(cur)
        cells = [None] * 6
        for num in nums:
            x1 = num[-1]["x1"]
            j = min(range(6), key=lambda k: abs(x1 - heads[k]["x1"]))
            if cells[j] is not None:
                raise ValueError(f"ONS {ref}: {lab} two numbers under column {j}")
            txt = "".join(w["text"] for w in num)
            cells[j] = None if txt in ("-", "/") else _fr(txt)
        grid[lab] = cells
    if set(grid) != {"Masculin", "Féminin", "Ensemble"}:
        raise ValueError(f"ONS {ref}: sex x strate rows {sorted(grid)}")
    for lab, c in grid.items():
        for a, b, t in ((0, 1, 2), (3, 4, 5)):
            if None not in (c[a], c[b]) and abs(c[a] + c[b] - c[t]) > 1:
                raise ValueError(f"ONS {ref}: {lab} urbain + rural != total")
    for j in range(6):
        m_, f_, e_ = grid["Masculin"][j], grid["Féminin"][j], grid["Ensemble"][j]
        if None not in (m_, f_, e_) and abs(m_ + f_ - e_) > 1:
            raise ValueError(f"ONS {ref}: masculin + féminin != ensemble, col {j}")
    if grid["Ensemble"][2] != counts["employed"] or grid["Ensemble"][5] != counts["unemployed"]:
        raise ValueError(f"ONS {ref}: sex x strate totals != population counts")
    sexes = {"Masculin": {"sex": "male"}, "Féminin": {"sex": "female"}, "Ensemble": {}}
    for lab, c in grid.items():
        for j, (topic, label) in enumerate([("employed", "Population occupée")] * 3
                                           + [("unemployed", "Population en chômage")] * 3):
            ctx = {**sexes[lab], **strata[j % 3]}
            if not ctx or c[j] is None:
                continue        # national totals: the population counts above
            add(topic, c[j], label, code, unit_=unit, **ctx)

    # age groups: header "Groupe d'âge Occupés Chômeurs"
    ai = next(i for i, ln in enumerate(lines)
              if [w["text"] for w in ln][:3] == ["Groupe", "d’âge", "Occupés"])
    aheads = lines[ai][2:4]
    label_x = aheads[0]["x0"] - 10
    # Row labels: the words left of the Occupés column, below the header,
    # grouped by baseline; the table ends at the "Total" label.
    lws = sorted((w for w in words if w["top"] > aheads[0]["bottom"]
                  and w["x1"] < label_x), key=lambda w: (round(w["top"]), w["x0"]))
    labels = []
    for w in lws:
        if labels and abs(w["top"] - labels[-1][-1]["top"]) < 3:
            labels[-1].append(w)
        else:
            labels.append([w])
    ages = []
    for lab_words in labels:
        lab = " ".join(w["text"] for w in lab_words)
        lab = re.sub(r"\s*-\s*", "-", lab).strip()
        ages.append((lab, _row_cells(words, lab_words[-1], aheads, ref)))
        if lab == "Total":
            break
    if not ages or ages[-1][0] != "Total":
        raise ValueError(f"ONS {ref}: age table not closed by a Total row")
    *groups, (_, tot) = ages
    # PUBLISHED MISPRINT: December 2008 prints employed aged 40-44 as "0"
    # (the other groups sum 1 082 thousand short of the Total). The cell is
    # not collected, and the shortfall is pinned so a correction is noticed.
    bad = _KNOWN_BAD_AGE.get(period)
    if bad:
        lab, j, gap = bad
        cell = dict(groups)[lab][j]
        s = sum(c[j] for _, c in groups if c[j] is not None)
        if cell != 0 or tot[j] - s != gap:
            raise ValueError(f"ONS {ref}: {lab} misprint no longer as recorded")
        groups = [(l, [None if (l == lab and k == j) else v for k, v in enumerate(c)])
                  for l, c in groups]
    for j in range(2):
        if bad and j == bad[1]:
            continue
        s = sum(c[j] for _, c in groups if c[j] is not None)
        gap = _KNOWN_AGE_GAP.get((period, j))
        if gap is not None:
            # every printed group kept; the published shortfall must persist
            if tot[j] - s != gap:
                raise ValueError(f"ONS {ref}: recorded age-table gap {gap} is now "
                                 f"{tot[j] - s} -- ONS corrected it")
            continue
        if abs(s - tot[j]) > 2 + (len(groups) if thousands else 0):
            raise ValueError(f"ONS {ref}: age groups sum to {s}, Total {tot[j]}")
    if tot != [counts["employed"], counts["unemployed"]]:
        raise ValueError(f"ONS {ref}: age Total {tot} != population counts")
    for lab, c in groups:
        for j, (topic, label) in enumerate((("employed", "Occupés"),
                                            ("unemployed", "Chômeurs"))):
            if c[j] is not None:
                add(topic, c[j], label, code, unit_=unit, age_group=lab)
    return out, period, rates


# Tableau 36 / 37 footnote markers -> the source ONS names for that year.
_SRC = {"1": "Recensement Général de la Population et de l'Habitat (RGPH)",
        "2": "Enquête Main d'œuvre (MOD)",
        "3": "Enquête LSMS (Enquête sur la mesure des niveaux de vie)",
        "4": "ONS, données statistiques n° 241",
        "5": "ONS, données statistiques n° 263"}


def _series(text: str, caption: str, topic: str, base: str, definition: str,
            label: str, rounds: dict) -> list[dict]:
    body = text[re.search(caption, text).end():]
    body = body[:re.search(r"^\(\*", body, re.M).start()] if re.search(r"^\(\*", body, re.M) else body
    out = []
    years, vals = [], []
    for ln in body.splitlines():
        if ln.startswith("Années") and re.search(r"\d{4}", ln):
            years += re.findall(r"(\d{4})(?:\((\d)\))?", ln)
        elif re.match(r"Taux d", ln):
            vals += [_fr(v) for v in re.findall(r"\d+,\d+", ln)]
    # Rows from 2009/2011 on are split by month (Sept/Avril) under one year
    # line; only the years before the first round page are collected, and
    # those are one value per year.
    pre = [(y, mk) for y, mk in years if int(y) < 2000]
    if len(vals) < len(pre):
        raise ValueError(f"ONS {caption}: {len(vals)} values for {len(pre)} early years")
    for (y, mk), v in zip(pre, vals):
        out.append(C.row(topic=topic, value=v, series_label=label,
                         survey=_SRC.get(mk, "ONS"), period=y,
                         reference_period=f"{y} ({_SRC.get(mk, 'ONS')})",
                         frequency="ad_hoc", working_age_base=base,
                         definition=definition, series_code=f"ONS Rétrospective {caption[:11]}"))
    # Later single-round years must agree with the round pages.
    yv = list(zip([y for y, _ in years], vals))
    for y, v in yv:
        if int(y) >= 2000 and y in rounds and rounds[y] != v:
            raise ValueError(f"ONS {caption} {y}: series {v} != round page {rounds[y]}")
    return out


def _census_1998_wilayas(text: str) -> list[dict]:
    body = text[re.search(r"Tab 16\.1\s*:", text).end():]
    body = body[:re.search(r"^Source", body, re.M).start()]
    out = []
    for ln in body.splitlines():
        m = re.match(r"(\d{2}\s*[-–]\s*.+?|Algérie)\s+((?:\d+\s*)+)$", ln.strip())
        if not m:
            continue
        name, toks = m.group(1).strip(), m.group(2).split()
        # PUBLISHED MISPRINT: Skikda's male count prints as "181 7 03" -- the
        # digits of 181 703 (181 703 + 36 531 = 218 234, the printed total).
        if toks[:3] == ["181", "7", "03"]:
            toks = ["181", "703"] + toks[3:]
        sols = []
        for i, j in itertools.combinations(range(1, len(toks)), 2):
            a, b, c = (int("".join(toks[:i])), int("".join(toks[i:j])),
                       int("".join(toks[j:])))
            # Census totals are rounded independently of their parts
            # (Chlef 179 033 + 38 333 = 217 366, printed 217 365): allow 2,
            # but the split must still be unique and every group 3 digits.
            groups = (toks[:i], toks[i:j], toks[j:])
            well_formed = all(len(g[0]) <= 3 and all(len(t) == 3 for t in g[1:])
                              for g in groups)
            if well_formed and abs(a + b - c) <= 2:
                sols.append((a, b, c))
        if len(sols) != 1:
            raise ValueError(f"RGPH 1998 T16.1 {name}: {len(sols)} readings of {toks}")
        a, b, c = sols[0]
        geo = {} if name == "Algérie" else {"geography": re.sub(r"\s+", " ", name)}
        for sx, v in (({"sex": "male"}, a), ({"sex": "female"}, b), ({}, c)):
            out.append(C.row(topic="labour_force", value=v,
                             series_label="Population active (Occupés + STR)",
                             survey="Recensement Général de la Population et de l'Habitat (RGPH) 1998",
                             period="1998", reference_period="RGPH 1998",
                             frequency="ad_hoc", working_age_base="not stated",
                             series_code="ONS Rétrospective T16.1", **geo, **sx))
    wil = {r["geography"] for r in out if r["geography"] != "Total country"}
    if len(wil) != 48:
        raise ValueError(f"RGPH 1998 T16.1: {len(wil)} wilayas read")
    tot = [r for r in out if r["geography"] == "Total country"]
    for sx in ("male", "female", "total"):
        s = sum(r["value"] for r in out if r["geography"] != "Total country" and r["sex"] == sx)
        t = next(r["value"] for r in tot if r["sex"] == sx)
        if abs(s - t) > 30:
            raise ValueError(f"RGPH 1998 T16.1: wilayas sum {s} vs Algérie {t} ({sx})")
    return out


def _communique_2024(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    if not re.search(r"Activité, Emploi et Chômage\.\s*Octobre 2024", text):
        raise ValueError("ONS 2024 communiqué: not the October 2024 release")
    m = re.search(r"Le taux de chômage en Algérie pour l.année 2024 est de (\d+,\d)%", text)
    if not m:
        raise ValueError("ONS 2024 communiqué: headline rate not found")
    return [C.row(topic="unemployment_rate", value=_fr(m.group(1)),
                  series_label="Le taux de chômage en Algérie pour l'année 2024 "
                               "(résultats préliminaires, après ajustements)",
                  survey="Enquête Activité, Emploi et Chômage (ONS), résultats préliminaires",
                  period="2024-Q4", reference_period="dernière semaine d'octobre 2024",
                  frequency="ad_hoc", working_age_base="not stated",
                  definition="not_applicable", series_code="ONS Communiqué Chomage2024")]


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        if "chomage2024" in p.lower().replace("\\", "/").rsplit("/", 1)[-1]:
            rows += _communique_2024(p)
            continue
        with pdfplumber.open(p) as pdf:
            texts = [pg.extract_text() or "" for pg in pdf.pages]
            rounds_ur, rounds_ar, rounds_er = {}, {}, {}
            n = 0
            for pg, t in zip(pdf.pages, texts):
                got = _round_page(pg, t)
                if got:
                    r, period, rates = got
                    rows += r
                    n += 1
                    y = period[:4]
                    # a year with two rounds is checked by neither series value
                    for d, k in ((rounds_ur, "unemployment_rate"),
                                 (rounds_ar, "labour_force_participation_rate"),
                                 (rounds_er, "employment_to_population_ratio")):
                        d[y] = None if y in d else rates[k]
            if n != 23:
                raise ValueError(f"ONS Rétrospective: {n} survey-round pages, expected 23")
            full = "\n".join(texts)
            rows += _series(full, r"Tableau 36: Evolution du taux de chômage",
                            "unemployment_rate", "not stated", "strict",
                            "Taux de chômage",
                            {y: v for y, v in rounds_ur.items() if v is not None})
            rows += _series(full, r"Tableau 37: Evolution du taux d.activité",
                            "labour_force_participation_rate", "15+", "not_applicable",
                            "Taux d’activité",
                            {y: v for y, v in rounds_ar.items() if v is not None})
            _series(full, r"Tableau 38: Evolution du taux d.emploi",
                    "employment_to_population_ratio", "15+", "not_applicable",
                    "Taux d’emploi", {y: v for y, v in rounds_er.items() if v is not None})
            rows += _census_1998_wilayas(full)
    return pd.DataFrame(rows)
