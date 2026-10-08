"""Guinea — INS Guinée, RGPH-3 (Troisième Recensement Général de la Population
et de l'Habitation, 1 March - 2 April 2014), thematic report "Caractéristiques
économiques" (December 2017), chapter 4.

A CENSUS, so the universe is the household population: every table here is
"la population active occupée des ménages ordinaires de 15 ans ou plus" --
3 415 394 persons. Base 15+. Period 2014.

COLLECTED (all column-% distributions of the employed, plus the table's own
"Effectif" counts as `Total`):

* 4.06  grands groupes de professions x milieu x sex        -> occupation
* 4.07  professions x region (8 regions)                     -> occupation
* 4.10  professions x niveau d'instruction                   -> occupation
* 4.11  statut dans la profession x milieu x sex             -> employment_status
* 4.12  statut x region                                      -> employment_status
* 4.13  statut x age group (15 à 19 ... 90 et +)             -> employment_status
* 4.15  statut (salarié split public / privé) x education x sex -> employment_status
* 4.17  20 branches d'activité x milieu x sex                -> industry
* 4.19  branches x niveau d'instruction                      -> industry
* 4.22  secteur primaire / secondaire / tertiaire x milieu x sex -> industry

TRANSPOSED TABLES ARE MAPPED BY ORDER, AND THE ORDER IS PROVEN, NOT ASSUMED.
4.07, 4.12 and 4.13 print the categories ACROSS the columns under headers
hyphenated over five lines ("Indé- / pendant", "Travail- / leur à la / tâche")
that the text layer cannot reassemble. Their columns are assigned the
categories of the principal table (4.06 / 4.11) in its printed order, and that
order is then CHECKED: each such table's own Total row must equal the
principal table's Ensemble column value for value, or the parse raises. The
category LABELS in those tables are therefore the principal table's -- the same
category, spelled as INS spells it where the label is legible. 4.10 and 4.19
print their own labels, which are kept as printed (they differ trivially:
"... sécurité sociale obligatoire" in 4.19 vs "... sécurité sociale" in 4.17).

COLUMNS NOT COLLECTED: every "% Femmes" / "% Femme" column and row (the share
of women WITHIN a category -- a row percentage); the "Total" column of 4.10,
4.15 and 4.19 and the Total rows of 4.07/4.12/4.13 (each repeats the principal
table's national distribution under the same merge key; they are used as the
order check instead).

TABLES NOT COLLECTED: 4.08, 4.14, 4.18 (by marital status -- no dimension in
this schema; and 4.14 is DEFECTIVE: its Total column gives Salarié 3,4 and
"Membre de coopérative" 10,6 against 6,2 and 0,2 in 4.11/4.12 -- the rows are
shifted against their labels); 4.09, 4.16, 4.21, 4.23 (by standard-of-living
quintile -- no dimension; 4.23's caption promises regions but its header is
quintiles); 4.20 (status x branch, a cross of two categories). Chapter 5 is
the unemployed.

CLASSIFICATION: National throughout. The occupation groups track ISCO-08's
major groups and the branches track ISIC sections, but no scheme is named
against any table. Section 4.4.6 says "la classification internationale type
pour l'industrie a été utilisée" -- no revision -- and then defines INS's own
three sectors, putting ARTISANAT in the primary sector and electricity, gas
and water in the tertiary: a national grouping, whatever it was coded from.

COUNTS ("Effectif") USE SPACE THOUSANDS and sit side by side --
"632 540 449 534 1 082 074" -- so they are split under the table's own
arithmetic (male + female = total per milieu; the parts sum to the national
total across regions, age groups and education levels), and a row with no
unique consistent split raises, as for Algeria.

ONE PUBLISHED GAP, KEPT: the education tables' six level counts sum to
3 415 344, not the 3 415 394 employed they are printed beside -- 22 men and 28
women with no level recorded and no column for them. The counts are collected
as printed; the split of each Effectifs row is anchored on the known total.

REGION NAMES: "N’Zérékoré" is printed with a typographic apostrophe in 4.07 and
a straight one in 4.12; the geography is written with the typographic one in
both so that one region is one geography.

SECOND SOURCE (the descriptor's extra file): EHCVM 2018/19, Enquête
Harmonisée sur les Conditions de Vie des Ménages, final report (March 2021),
section 10.17 -- a household survey in two waves (1 July - 31 October 2018,
1 April - 30 June 2019), base 15+, period 2019 as for Chad's ECOSIT4:

* 10.21  secteur institutionnel (État / entreprise publique / privée /
         associative / ménage employeur / organisme international) -> sector
* 10.22  catégorie socioprofessionnelle (10 categories) -> employment_status
* 10.24  branche d'activité, "classification simplifiée" (11) -> industry

each by region, milieu, sex, age group and education. THEIR HEADERS ARE
ROTATED and reach the text layer as spaced letters ("A g ric u ltu re"); the
column order was read from page GEOMETRY (the rotated glyphs above each value
column, which reverse-read "erutlucirgA", "PTB", "latoT") and confirmed by the
report's prose (74,2% travailleurs pour compte propre; among the
university-educated 29,8% cadres supérieurs and 31,3% éducation/santé). The
order is pinned in `_EHCVM` and each row must sum to 100. 10.24's column
labels are ABBREVIATED in the report ("Indust. extr.", "Trans./Comm.") and are
kept as printed, as Somalia's truncated labels are.

EHCVM rows NOT collected: "Statut de handicap" (no dimension here); 10.24's
"Région naturelle" Conakry row and "Zone de résidence" Rural row, which repeat
the administrative-region Conakry and milieu Rural rows digit for digit (both
checked) and would duplicate merge keys. 10.21 PRINTS NO NATIONAL ROW (the
table ends at "Superieur"; the prose gives 93,8% entreprise privée), so none
is emitted. 10.23/10.25 (by welfare quintile) have no dimension here.

CROSS-CHECK (Ensemble, % of 3 415 394 employed): agriculteurs 52,6; personnel
des services 25,1; indépendant 76,4; aide familiale 10,6; salarié 6,2;
agriculture, élevage, sylviculture et pêche 52,0; commerce 21,3; secteur
primaire 54,7. Conakry employed 519 388. EHCVM 2019: compte propre 74,2;
agriculture 40,4; commerce 19,2.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = ("Troisième Recensement Général de la Population et de "
           "l'Habitation (RGPH-3)")
_BASE = dict(survey=_SURVEY, period="2014",
             reference_period="RGPH-3 (1 mars - 2 avril 2014)",
             frequency="ad_hoc", working_age_base="15+",
             classification="National")
_P = dict(measure="share", unit="percent")
_N = dict(measure="count", unit="persons")
_TOTAL_EMPLOYED = 3415394
_EMPLOYED_BY_SEX = {"male": 1933120, "female": 1482274, "total": _TOTAL_EMPLOYED}

_FURNITURE = re.compile(r"^(Institut National de la Statistique|\d+ CARACTERISTIQUES"
                        r"|CARACTERISTIQUES ECONOMIQUES \d+)")
_NUMS = re.compile(r"^(.*?)\s*((?:\d+(?:,\d+)?)(?:\s+\d+(?:,\d+)?)*)$")
_MILIEUX = [("urban", "Urbain"), ("rural", "Rural"), ("all", "Total")]
_SEXES = ["male", "female", "total"]
_EDU = ["Sans niveau", "Primaire", "Collège", "Lycée",
        "Professionnel/Technique", "Universitaire"]


def _f(tok: str) -> float:
    return float(tok.replace(",", "."))


# --------------------------------------------------------------------------
# Getting at a table's lines
# --------------------------------------------------------------------------

def _pages(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [p.extract_text() or "" for p in pdf.pages]


def _table_lines(pages: list[str], num: str) -> list[str]:
    """Lines after the caption of Tableau <num>, over its page and the next
    (4.10's caption closes one page and its body opens the next). The list of
    tables on pages 7-8 repeats every caption, so the body page is the first
    one past it that carries the caption AND a Total line after it."""
    cap = re.compile(rf"^Tableau {re.escape(num)}\s*:", re.M)
    for i, text in enumerate(pages):
        if i < 20 or not cap.search(text):
            continue
        body = (text + "\n" + (pages[i + 1] if i + 1 < len(pages) else ""))
        body = body[cap.search(body).end():]
        lines = [ln.strip() for ln in body.splitlines()]
        return [ln for ln in lines if ln and not _FURNITURE.match(ln)]
    raise ValueError(f"RGPH-3: Tableau {num} not found")


def _rows(lines: list[str], first: str, ncols: int,
          stop: str = r"^Total\b") -> list[tuple[str, list[str]]]:
    """Category rows whose labels wrap ABOVE and BELOW their numbers:

        Agriculteurs et ouvriers qualifiés de      <- opens a label
        l’agriculture de la sylviculture et de la 62,8 32,6 ...
        pêche                                       <- lower-case: continues it

    A digit-free line starting in lower case continues the row just read; one
    starting in upper case opens the next. Reading begins at `first` (the
    header lines above it carry no data) and ends at the Total row."""
    start = next(i for i, ln in enumerate(lines) if re.match(first, ln))
    out, pending = [], []
    for ln in lines[start:]:
        if re.match(stop, ln):
            break
        m = _NUMS.match(ln)
        if m and m.group(2) and len(m.group(2).split()) == ncols:
            label = " ".join(pending + ([m.group(1)] if m.group(1) else []))
            out.append([label, m.group(2).split()])
            pending = []
        elif re.search(r"\d", ln):
            raise ValueError(f"RGPH-3: unreadable row {ln!r}")
        elif out and not pending and re.match(r"^[a-zàâéèêîôûç’'(]", ln):
            out[-1][0] += " " + ln
        else:
            pending.append(ln)
    return [(re.sub(r"\s+", " ", lab).strip(), vals) for lab, vals in out]


def _line(lines: list[str], pattern: str) -> str:
    return next(ln for ln in lines if re.match(pattern, ln))


# --------------------------------------------------------------------------
# Space-thousands counts, split under the table's own arithmetic
# --------------------------------------------------------------------------

def _splits(tokens: list[str], k: int):
    """Every way to read `tokens` as k numbers written with space thousands."""
    if k == 0:
        if not tokens:
            yield []
        return
    for n in range(1, min(len(tokens), 4) + 1):
        head = tokens[:n]
        if len(head[0]) > 3 or any(len(t) != 3 for t in head[1:]):
            continue
        for rest in _splits(tokens[n:], k - 1):
            yield [int("".join(head))] + rest


def _counts(text: str, k: int, check, where: str) -> list[int]:
    tokens = [t for t in text.split() if t != "-"]
    good = [s for s in _splits(tokens, k) if check(s)]
    if len(good) != 1:
        raise ValueError(f"RGPH-3 {where}: {len(good)} consistent readings of "
                         f"{text!r}")
    return good[0]


def _triples_ok(vals: list[int]) -> bool:
    return all(vals[i] + vals[i + 1] == vals[i + 2] for i in range(0, len(vals), 3))


# --------------------------------------------------------------------------
# The tables
# --------------------------------------------------------------------------

def _check_sums(rows, ncols, where, skip=()):
    for j in range(ncols):
        if j in skip:
            continue
        s = sum(_f(v[j]) for _, v in rows)
        if abs(s - 100) > 0.8:
            raise ValueError(f"RGPH-3 {where}: column {j + 1} sums to {s:.1f}")


def _milieu_by_sex(pages, num, first, topic, expect, code):
    """4.06 / 4.17: 12 columns = (Masculin, Féminin, Total, % Femmes) for
    Urbain, Rural, Ensemble. The fourth of each four is a row % and dropped."""
    lines = _table_lines(pages, num)
    rows = _rows(lines, first, 12)
    if len(rows) != expect:
        raise ValueError(f"RGPH-3 T{num}: {len(rows)} categories, expected {expect}")
    _check_sums(rows, 12, f"T{num}", skip=(3, 7, 11))
    out = []
    for lab, vals in rows:
        for b, (loc, loc_lab) in enumerate(_MILIEUX):
            for s, sex in enumerate(_SEXES):
                out.append(C.row(topic=topic, characteristic=lab,
                                 value=_f(vals[4 * b + s]), sex=sex,
                                 locality=loc, locality_label=loc_lab,
                                 series_code=f"RGPH3 T{num}", **_BASE, **_P))
    eff = _line(lines, r"^Effectifs?\b")
    n = _counts(eff.split(None, 1)[1], 9, _triples_ok, f"T{num} Effectif")
    for b, (loc, loc_lab) in enumerate(_MILIEUX):
        for s, sex in enumerate(_SEXES):
            out.append(C.row(topic=topic, characteristic="Total", value=n[3 * b + s],
                             sex=sex, locality=loc, locality_label=loc_lab,
                             series_code=f"RGPH3 T{num}", **_BASE, **_N))
    if n[-1] != _TOTAL_EMPLOYED:
        raise ValueError(f"RGPH-3 T{num}: employed {n[-1]}, not {_TOTAL_EMPLOYED}")
    return out, rows


def _t4_11(pages):
    """Three blocks (Urbain / Rural / Ensemble), columns Masculin, Féminin,
    Ensemble, % Femmes (dropped)."""
    lines = _table_lines(pages, "4.11")
    out, national = [], None
    for (loc, loc_lab), head in zip(_MILIEUX, ("Urbain", "Rural", "Ensemble")):
        i = next(k for k, ln in enumerate(lines) if ln == head)
        rows = _rows(lines[i + 1:], r"^Indépendant", 4)
        if len(rows) != 7:
            raise ValueError(f"RGPH-3 T4.11 {head}: {len(rows)} statuses")
        _check_sums(rows, 4, f"T4.11 {head}", skip=(3,))
        for lab, vals in rows:
            for s, sex in enumerate(_SEXES):
                out.append(C.row(topic="employment_status", characteristic=lab,
                                 value=_f(vals[s]), sex=sex, locality=loc,
                                 locality_label=loc_lab, series_code="RGPH3 T4.11",
                                 **_BASE, **_P))
        eff = next(ln for ln in lines[i + 1:] if ln.startswith("Effectif"))
        n = _counts(eff.split(None, 1)[1], 3, _triples_ok, f"T4.11 {head}")
        for s, sex in enumerate(_SEXES):
            out.append(C.row(topic="employment_status", characteristic="Total",
                             value=n[s], sex=sex, locality=loc,
                             locality_label=loc_lab, series_code="RGPH3 T4.11",
                             **_BASE, **_N))
        national = rows
    return out, national


def _across(pages, num, first, cats, national, topic, dim, code_n):
    """4.07 / 4.12 / 4.13: one row per region or age group, the categories
    ACROSS the columns in the principal table's order, then Total (100) and
    the group's Effectif. Order proven by the Total row (see module doc)."""
    lines = _table_lines(pages, num)
    k = len(cats)
    start = next(i for i, ln in enumerate(lines) if re.match(first, ln))
    groups, total_row = [], None
    for ln in lines[start:]:
        m = re.match(r"^(\d+ à \d+|90 et \+|[^\d]+?)\s+(\d.*)$", ln)
        if not m:
            raise ValueError(f"RGPH-3 T{num}: unreadable row {ln!r}")
        toks = m.group(2).split()
        shares, hundred, count = toks[:k], toks[k], toks[k + 1:]
        if not re.fullmatch(r"100(,0)?", hundred):
            raise ValueError(f"RGPH-3 T{num}: {m.group(1)!r} has no Total 100 in "
                             f"column {k + 1}: {ln!r}")
        if not count or len(count[0]) > 3 or any(len(t) != 3 for t in count[1:]):
            raise ValueError(f"RGPH-3 T{num}: bad Effectif in {ln!r}")
        if m.group(1) == "Total":
            total_row = ([_f(v) for v in shares], int("".join(count)))
            break
        groups.append((m.group(1), [_f(v) for v in shares], int("".join(count))))
    if total_row is None:
        raise ValueError(f"RGPH-3 T{num}: no Total row")
    if total_row[0] != national:
        raise ValueError(f"RGPH-3 T{num}: Total row {total_row[0]} is not the "
                         f"national distribution {national} -- column order "
                         f"cannot be taken from the principal table")
    if sum(g[2] for g in groups) != total_row[1] or total_row[1] != _TOTAL_EMPLOYED:
        raise ValueError(f"RGPH-3 T{num}: Effectifs do not sum to the Total")
    out = []
    for name, shares, count in groups:
        if dim == "geography":
            ctx = {"geography": name.replace("'", "’")}
        else:
            ctx = {"age_group": name}
        if abs(sum(shares) - 100) > 0.8:
            raise ValueError(f"RGPH-3 T{num} {name}: shares sum to {sum(shares)}")
        for cat, v in zip(cats, shares):
            out.append(C.row(topic=topic, characteristic=cat, value=v,
                             series_code=f"RGPH3 T{num}", **ctx, **_BASE, **_P))
        out.append(C.row(topic=topic, characteristic="Total", value=count,
                         series_code=f"RGPH3 T{num}", **ctx, **_BASE, **_N))
    return out, len(groups)


def _by_education(pages, num, first, topic, expect, national, sex=None, lines=None,
                  code=None):
    """4.10 / 4.19 (and each sex block of 4.15): seven columns -- six
    education levels, then Total/Ensemble, which is checked against the
    national distribution and not emitted."""
    lines = lines if lines is not None else _table_lines(pages, num)
    rows = _rows(lines, first, 7)
    if len(rows) != expect:
        raise ValueError(f"RGPH-3 T{num}: {len(rows)} categories, expected {expect}")
    _check_sums(rows, 7, f"T{num}")
    if national is not None and [_f(v[6]) for _, v in rows] != national:
        raise ValueError(f"RGPH-3 T{num}: Total column is not the national "
                         f"distribution -- columns misread")
    ctx = {"sex": sex} if sex else {}
    out = []
    for lab, vals in rows:
        for edu, v in zip(_EDU, vals[:6]):
            out.append(C.row(topic=topic, characteristic=lab, value=_f(v),
                             education=edu, series_code=code or f"RGPH3 T{num}",
                             **ctx, **_BASE, **_P))
    # THE SIX LEVELS DO NOT SUM TO THE TOTAL: 3 415 344 against 3 415 394
    # (men 22 short, women 28) -- employed persons with no level recorded,
    # which INS prints no column for. So the split is anchored on the known
    # total instead, and the shortfall must be small and non-negative.
    eff = next(ln for ln in lines if ln.startswith("Effectif"))
    want = _EMPLOYED_BY_SEX[sex or "total"]
    n = _counts(eff.split(None, 1)[1], 7,
                lambda s: s[6] == want and 0 <= want - sum(s[:6]) <= 100,
                f"T{num} Effectifs")
    for edu, v in zip(_EDU, n[:6]):
        out.append(C.row(topic=topic, characteristic="Total", value=v,
                         education=edu, series_code=code or f"RGPH3 T{num}",
                         **ctx, **_BASE, **_N))
    return out, n[6]


def _t4_15(pages):
    lines = _table_lines(pages, "4.15")
    out = []
    for head, sex in (("Masculin", "male"), ("Féminin", "female"), ("Ensemble", "total")):
        i = lines.index(head)
        got, total = _by_education(pages, "4.15", r"^Indépendant", "employment_status",
                                   8, None, sex=sex, lines=lines[i + 1:],
                                   code="RGPH3 T4.15")
        out += got
    return out


def _t4_22(pages):
    """Sectors across the columns, sex down the rows, a block per milieu. The
    "% Femmes" rows and the Total column are not collected."""
    lines = _table_lines(pages, "4.22")
    cats = ["Secteur primaire", "Secteur secondaire", "Secteur tertiaire"]
    out = []
    for (loc, loc_lab), head in zip(_MILIEUX, ("Urbain", "Rural", "Ensemble")):
        i = lines.index(head)
        for ln, sex in zip(lines[i + 1:i + 4], _SEXES):
            m = re.fullmatch(r"(Masculin|Féminin|Ensemble) (\S+) (\S+) (\S+) (100,0)", ln)
            if not m or C.normalise_sex(m.group(1)) != sex:
                raise ValueError(f"RGPH-3 T4.22 {head}: unreadable {ln!r}")
            vals = [_f(m.group(k)) for k in (2, 3, 4)]
            if abs(sum(vals) - 100) > 0.2:
                raise ValueError(f"RGPH-3 T4.22 {head} {sex}: sums to {sum(vals)}")
            for cat, v in zip(cats, vals):
                out.append(C.row(topic="industry", characteristic=cat, value=v,
                                 sex=sex, locality=loc, locality_label=loc_lab,
                                 series_code="RGPH3 T4.22", **_BASE, **_P))
    return out


# --------------------------------------------------------------------------
# EHCVM 2018/19 (extra file)
# --------------------------------------------------------------------------

_EHCVM_BASE = dict(survey="Enquête Harmonisée sur les Conditions de Vie des "
                          "Ménages (EHCVM) 2018/2019",
                   period="2019",
                   reference_period="EHCVM 2018/2019 (juillet-octobre 2018, "
                                    "avril-juin 2019)",
                   frequency="ad_hoc", working_age_base="15+")

# Column order established from page geometry -- see the module docstring.
_EHCVM = {
    "10.21": ("sector", "Not applicable", [
        "État/Collectivités locales", "Entreprise publique/parapublique",
        "Entreprise Privée", "Entreprise associative",
        "Ménage comme employeur de personnel domestique",
        "Organisme international/Ambassade"]),
    "10.22": ("employment_status", "National", [
        "Cadre supérieur", "Cadre moyen/agent de maîtrise",
        "Ouvrier ou employé qualifié", "Ouvrier ou employé non qualifié",
        "Manœuvre, aide ménagère", "Stagiaire ou Apprenti rémunéré",
        "Stagiaire ou Apprenti non rémunéré", "Aide familial",
        "Travailleur pour compte propre", "Patron"]),
    "10.24": ("industry", "National", [
        "Agriculture", "Elevage/pêche", "Indust. extr.", "Autr. indust.",
        "BTP", "Commerce", "Restaurant/Hotel", "Trans./Comm.",
        "Education/Santé", "Services perso.", "Aut. services"]),
}
_SECTION = [(r"^Région administrative", "region"), (r"^Région naturelle", "natural"),
            (r"^Milieu", "milieu"), (r"^Zone de résidence", "zone"),
            (r"^Sexe", "sex"), (r"^Groupe", "age"), (r"^d'âges$", None),
            (r"^Niveau d'instruction", "education"),
            (r"^Statut de handicap", "handicap")]


def _ehcvm_table(pages: list[str], num: str) -> list[dict]:
    topic, classification, cats = _EHCVM[num]
    k = len(cats) + 1                      # categories + Total (100)
    cap = re.compile(rf"^Tableau {re.escape(num)} :", re.M)
    page = next(t for i, t in enumerate(pages) if i > 30 and cap.search(t))
    lines = [ln.strip() for ln in page[cap.search(page).end():].splitlines()]
    start = next(i for i, ln in enumerate(lines) if ln == "Région administrative")
    section, seen, out = None, {}, []
    for ln in lines[start:]:
        hit = next((sec for pat, sec in _SECTION if re.match(pat, ln)), "none")
        if hit != "none":
            section = hit if hit is not None else section
            continue
        toks = ln.split()
        vals, label = toks[-k:], " ".join(toks[:-k])
        if (len(toks) <= k or not all(re.fullmatch(r"\d+(,\d)?", v) for v in vals)
                or not re.search(r"[A-Za-zé]", label)):
            break                          # end of the table (page number, prose)
        if vals[-1] != "100":
            raise ValueError(f"EHCVM T{num}: {ln!r} has no Total 100")
        shares = [_f(v) for v in vals[:-1]]
        if abs(sum(shares) - 100) > 0.6:
            raise ValueError(f"EHCVM T{num} {label}: sums to {sum(shares):.1f}")
        seen[(section, label)] = shares
        if label == "Total":
            ctx: dict = {}                 # the national row
        elif section == "handicap":
            continue
        elif section in ("region", "natural"):
            if section == "natural" and label == "Conakry":
                if shares != seen.get(("region", "Conakry")):
                    raise ValueError(f"EHCVM T{num}: natural-region Conakry differs")
                continue
            ctx = {"geography": label.replace("'", "’")}
        elif section in ("milieu", "zone"):
            if section == "zone" and label == "Rural":
                if shares != seen.get(("milieu", "Rural")):
                    raise ValueError(f"EHCVM T{num}: zone Rural differs")
                continue
            ctx = {"locality": "rural" if label == "Rural" else "urban",
                   "locality_label": label}
        elif section == "sex":
            ctx = {"sex": C.normalise_sex(label)}
        elif section == "age":
            ctx = {"age_group": label}
        elif section == "education":
            ctx = {"education": label}
        else:
            raise ValueError(f"EHCVM T{num}: row {label!r} outside a section")
        for cat, v in zip(cats, shares):
            out.append(C.row(topic=topic, characteristic=cat, value=v,
                             classification=classification,
                             series_code=f"EHCVM T{num}", **ctx,
                             **_EHCVM_BASE, **_P))
    return out


def _ehcvm(path: str) -> list[dict]:
    pages = _pages(path)
    out = []
    # 8 regions + 2-3 milieux + 2 sexes + 4 ages + 4 levels (+ national).
    for num, least in (("10.21", 20), ("10.22", 21), ("10.24", 26)):
        got = _ehcvm_table(pages, num)
        groups = {(r["geography"], r["locality_label"], r["sex"], r["age_group"],
                   r["education"]) for r in got}
        if len(groups) < least:
            raise ValueError(f"EHCVM T{num}: {len(groups)} groups read, "
                             f"expected at least {least}")
        out += got
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    pages = _pages(path)
    out = []

    occ, occ_rows = _milieu_by_sex(pages, "4.06", r"^Directeurs", "occupation",
                                   10, "4.06")
    out += occ
    occ_cats = [lab for lab, _ in occ_rows]
    occ_nat = [_f(v[10]) for _, v in occ_rows]

    st, st_rows = _t4_11(pages)
    out += st
    st_cats = [lab for lab, _ in st_rows]
    st_nat = [_f(v[2]) for _, v in st_rows]

    ind, ind_rows = _milieu_by_sex(pages, "4.17", r"^Agriculture", "industry",
                                   20, "4.17")
    out += ind
    ind_nat = [_f(v[10]) for _, v in ind_rows]

    got, n = _across(pages, "4.07", r"^Boké", occ_cats, occ_nat, "occupation",
                     "geography", "4.07")
    out += got
    if n != 8:
        raise ValueError(f"RGPH-3 T4.07: {n} regions")
    got, n = _across(pages, "4.12", r"^Boké", st_cats, st_nat, "employment_status",
                     "geography", "4.12")
    out += got
    if n != 8:
        raise ValueError(f"RGPH-3 T4.12: {n} regions")
    got, n = _across(pages, "4.13", r"^15 à 19", st_cats, st_nat, "employment_status",
                     "age", "4.13")
    out += got
    if n != 16:
        raise ValueError(f"RGPH-3 T4.13: {n} age groups")

    got, total = _by_education(pages, "4.10", r"^Directeurs", "occupation", 10, occ_nat)
    out += got
    got, total = _by_education(pages, "4.19", r"^Agriculture", "industry", 20, ind_nat)
    out += got
    out += _t4_15(pages)
    out += _t4_22(pages)
    for extra in extras or []:
        if "EHCVM" in extra.upper():
            out += _ehcvm(extra)
    return pd.DataFrame(out)
