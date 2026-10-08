"""Comoros — INSEED Comores: three publications, three survey rounds.

INSEED's documents are served from its NADA catalogue
(nada.inseed-comores.org/index.php/catalog/<id>/download/<n>); inseed.km is no
longer the NSO. Each file is recognised by its own content, not its name.

1. EEIC 2021 -- Enquête sur l'Économie Informelle aux Comores (catalog 10,
   download 107, the analysis report, February 2023). Phase 1 is the HOUSEHOLD
   employment survey; its "Certains indicateurs du marché du travail" table
   (pp. 4-5) gives the employed population -- 220 890 persons -- by status in
   employment (5 categories), branch (7 groups) and occupation (7 groups), as
   COUNTS by sex and milieu. Tableaux 2 and 3 (p. 34) add the formal/informal
   split of all employment and the split by type of production unit (secteur
   informel / formel / ménages), by sex -- their "Total" column only.
2. RGPH 2017 -- "Caractéristiques économiques" thematic report (catalog 8,
   download 65). Tableau 3.2 status in employment by sex within Urbain / Rural
   / Comores; 3.5 seventeen branches by milieu x sex; 3.7 occupational groups
   by sex and milieu. Base 15+.
3. EESIC 2013 Phase 1 -- Emploi (catalog 5, download 47). Tableau 26
   "Principaux acteurs de l'offre d'emploi": institutional sector by island
   (Moroni / reste de Ngazidja / Ndzouani / Mwali), milieu and sex.

THE EEIC COUNTS ARE SPLIT BY THE TEXT LAYER. PyMuPDF gives one cell per line,
but a count sometimes breaks across two ("145" / "758" for 145 758), and
pdfplumber's line layout fuses the five columns. So every EEIC row's digit
groups are re-split under the table's own arithmetic -- masculin + féminin =
total and urbain + rural = total, each to within 2 (INSEED's rounding: the
Employeur row gives 1 671 + 5 192 = 6 863 against 6 862) -- and a row with no
split, or more than one, raises. The algorithm is Algeria's.

THE "'000" IN EEIC'S ROW LABELS IS WRONG: "Population totale (nombre '000)"
is followed by 810 532, the population itself (the report's p. 10: "810 000
personnes"). The employed counts are persons, not thousands.

EEIC PERIOD: 2021, the survey's own year (NADA: "EEIC 2021"; p. 10 "la
population totale au Comores en 2021"), though Tableaux 2-3 are footed
"enquête sur l'économie informel, 2022" -- the report's year. Working-age base
14-64, as the report defines it (p. 10).

TOPIC CHOICES. RGPH Tableau 3.7 is headed "catégories socioprofessionnelles"
but its categories are occupational groups (intellectuels et scientifiques,
conducteurs d'installations et de machines ...) -> `occupation`, National.
EESIC Tableau 26 -> `sector`, as Niger's identical ERI-ESI Tableau 5.30; its
printed subtotals ("Ensemble" under secteur privé formel / informel) are
verified sums and not collected, and the leaves carry their parent in the
label ("Secteur privé informel - initiative privée").

NOT COLLECTED, AND WHY:
* RGPH 3.3 (primary / secondary / tertiary): the sums of 3.5's branches under
  their own section headings; collecting both would put two partitions of the
  employed under one topic. 3.5's TOTAL is taken instead.
* RGPH 3.2's "% Femmes" column (row percentage) and every Effectif row.
* EESIC Tableau 16 "Bilan de l'emploi" -- implausible as printed: jobs in
  FORMAL production units are 97,4% informal, and all employment 0,6% formal,
  against 13,0% formal in EEIC 2021. Not collected until explained.
* EEIC Tableaux 2/3's per-branch and "hors agriculture" columns (row % within
  a branch, or a restricted universe), Tableau 4 onward (informal-sector
  module detail), and the occupation block's missing Total.
* The EEIC phase-2 (UPI) questionnaire and results.

All categories are INSEED's own (no scheme named) -> National; formality ->
Not applicable. EESIC 2013's Tableau 26 states no age base (the survey covers
10+), so "not stated".

CROSS-CHECK: EEIC 2021 employed 220 890; employés rémunérés 77 373; agriculture
64 384; informal employment 87,0%. RGPH 2017 (Comores) indépendants 51,7;
agriculture/élevage 31,59; agriculture, élevage, pêche (occupation) 28,5.
EESIC 2013 secteur privé informel 73,1 (Ensemble); administration publique 14,9.
"""
from __future__ import annotations

import itertools
import re

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber

from . import _common as C

_EEIC = "Enquête sur l'Économie Informelle aux Comores (EEIC) 2021"
_RGPH = "Recensement Général de la Population et de l'Habitation (RGPH) 2017"
_EESIC = "Enquête sur l'Emploi et le Secteur Informel aux Comores (EESIC) 2013, phase 1"

_M, _F = {"sex": "male"}, {"sex": "female"}
_U = {"locality": "urban", "locality_label": "Urbain"}
_R = {"locality": "rural", "locality_label": "Rural"}


# --------------------------------------------------------------------------
# Shared: a token stream of one cell per line, and rows matched to labels
# --------------------------------------------------------------------------

def _stream(doc, pages) -> list[str]:
    """Non-empty lines of the given pages, minus each page's running number
    (a bare integer among its first few lines) -- else "28" is read as a cell."""
    out = []
    for i in pages:
        lines = [ln.strip() for ln in doc[i].get_text().splitlines() if ln.strip()]
        head = [j for j, ln in enumerate(lines[:4]) if re.fullmatch(r"\d{1,3}", ln)]
        out += [ln for j, ln in enumerate(lines) if j not in head[:1]]
    return out


_NUMLINE = re.compile(r"^[\d\s,]+$")


def _words(s: str) -> list[str]:
    return re.sub(r"[^\w']+", " ", s.lower()).split()


def _label_ok(acc: str, expected: str) -> bool:
    """The text gathered before a row must END with the expected label -- or,
    where the label's tail wraps past its numbers (and a page break), with at
    least its first two words."""
    a, e = _words(acc), _words(expected)
    for k in range(len(e), min(2, len(e)) - 1, -1):
        if a[-k:] == e[:k]:
            return True
    return False


def _rows(tokens: list[str], labels: list[str], ncols: int, where: str):
    """Read `len(labels)` rows of `ncols` decimal/integer cells in order."""
    out, acc, vals, it = [], "", [], iter(labels)
    want = next(it)
    for tok in tokens:
        if _NUMLINE.match(tok):
            vals += [float(v.replace(",", ".")) for v in
                     re.findall(r"\d+(?:,\d+)?", re.sub(r"(\d) ,(\d)", r"\1,\2", tok))]
            if len(vals) >= ncols:
                if len(vals) > ncols:
                    raise ValueError(f"{where}: {want!r} read {vals}")
                if not _label_ok(acc, want):
                    raise ValueError(f"{where}: expected {want!r}, text was {acc[-120:]!r}")
                out.append((want, vals))
                acc, vals = "", []
                want = next(it, None)
                if want is None:
                    return out
            continue
        # "Personnel de service et vendeurs  9,1": label and first cell together
        m = re.match(r"^(.*?[^\d\s,])\s+([\d,\s]+)$", tok)
        if m and not vals:
            acc += " " + m.group(1)
            vals += [float(v.replace(",", ".")) for v in re.findall(r"\d+(?:,\d+)?", m.group(2))]
            continue
        if vals:
            raise ValueError(f"{where}: {want!r} broken off after {vals} by {tok!r}")
        acc += " " + tok
    raise ValueError(f"{where}: stopped at {want!r}")


def _find(doc, caption: str) -> int:
    for i, page in enumerate(doc):
        text = page.get_text()
        for m in re.finditer(caption, text):
            if not re.search(r"\.{4}", text[m.end():m.end() + 200].split("\n")[0]
                             + text[m.end():m.end() + 200].split("\n", 1)[-1][:60]):
                return i
    raise ValueError(f"caption not found: {caption!r}")


def _emit(rows, ctxs, survey, period, reference, base, topic, cls, measure,
          unit, code, rename=None, skip=()):
    out = []
    for lab, vals in rows:
        if lab in skip:
            continue
        name = (rename or {}).get(lab, lab)
        name = "Total" if name.upper() == "TOTAL" else name
        for ctx, v in zip(ctxs, vals):
            if ctx is None:
                continue
            out.append(C.row(topic=topic, characteristic=name, classification=cls,
                             value=v, survey=survey, period=period,
                             reference_period=reference, frequency="ad_hoc",
                             measure=measure, unit=unit, working_age_base=base,
                             series_code=code, **ctx))
    return out


def _check_sums(rows, parts, total_label, ncols, where, tol=0.35, skip_cols=()):
    by = dict(rows)
    for j in range(ncols):
        if j in skip_cols:
            continue
        s = sum(by[p][j] for p in parts)
        if abs(s - by[total_label][j]) > tol:
            raise ValueError(f"{where}: column {j} parts sum to {s:.2f}, "
                             f"{total_label} {by[total_label][j]}")


# --------------------------------------------------------------------------
# 1. EEIC 2021
# --------------------------------------------------------------------------

_EEIC_STATUS = ["Employé rémunéré", "Employeur", "Travailleur à son propre compte",
                "Travailleurs familiaux contributeurs",
                "Travailleurs non classés par le statut", "Total"]
_EEIC_BRANCH = ["Agriculture", "Fabrication", "Construction",
                "Mines et carrières ; Approvisionnement en électricité, gaz et eau",
                "Services marchands (Commerce ; Transport ; Hébergement et "
                "restauration ; et Services commerciaux et administratifs)",
                "Services non marchands (administration publique ; services et "
                "activités communautaires, sociaux et autres)",
                "Non classable par activité économique", "Total"]
_EEIC_OCC = ["Gestionnaires, professionnels et techniciens",
             "Employés de bureau, de service et de vente",
             "Travailleurs agricoles et artisans qualifiés",
             "Opérateurs d'installations et de machines et assembleurs",
             "Professions élémentaires", "Forces armées", "Non classé ailleurs"]
_EEIC_COLS = [_M, _F, _U, _R, {}]


def _split_counts(groups: list[str]):
    """Split digit groups into (M, F, U, R, T) with M+F = T and U+R = T (to 2)."""
    n, sols = len(groups), []
    for cuts in itertools.combinations(range(1, n), 4):
        bounds = (0, *cuts, n)
        parts = [groups[a:b] for a, b in zip(bounds, bounds[1:])]
        if any(len(p[0]) > 3 or any(len(g) != 3 for g in p[1:]) or
               (len(p) > 1 and p[0].startswith("0")) for p in parts):
            continue
        m, f, u, r, t = (int("".join(p)) for p in parts)
        if abs(m + f - t) <= 2 and abs(u + r - t) <= 2:
            sols.append([m, f, u, r, t])
    return sols


def _eeic_counts(doc) -> list[dict]:
    p = _find(doc, r"Certains indicateurs du march. du travail")
    toks = _stream(doc, range(p, p + 2))
    start = toks.index("Statut dans l'emploi")
    stop = next(i for i, t in enumerate(toks) if t.startswith("Heures de travail"))
    toks = toks[start + 1:stop]
    rows, acc, groups = [], "", []
    labels = iter(_EEIC_STATUS + _EEIC_BRANCH + _EEIC_OCC)
    want = next(labels)

    def close():
        nonlocal acc, groups, want
        sols = _split_counts(groups)
        if len(sols) != 1:
            raise ValueError(f"EEIC: {want!r} digit groups {groups} split "
                             f"{len(sols)} ways")
        if not _label_ok(acc, want):
            raise ValueError(f"EEIC: expected {want!r}, text was {acc!r}")
        rows.append((want, [float(v) for v in sols[0]]))
        acc, groups, want = "", [], next(labels, None)

    for tok in toks:
        if re.fullmatch(r"[\d ]+", tok):
            groups += tok.split()
            continue
        if groups:
            close()
        acc += " " + tok
    if groups:
        close()
    if want is not None:
        raise ValueError(f"EEIC: stopped before {want!r}")

    status, branch, occ = rows[:6], rows[6:14], rows[14:]
    _check_sums(status, _EEIC_STATUS[:-1], "Total", 5, "EEIC status", tol=2)
    _check_sums(branch, _EEIC_BRANCH[:-1], "Total", 5, "EEIC branch", tol=2)
    tot = dict(branch)["Total"]
    for j in range(5):
        if abs(sum(v[j] for _, v in occ) - tot[j]) > 2:
            raise ValueError("EEIC occupation groups do not sum to the employed")
    kw = dict(survey=_EEIC, period="2021", reference="EEIC 2021, phase 1 (ménages)",
              base="14-64", cls="National", measure="count", unit="persons",
              code="EEIC 2021 indicateurs")
    # One employed Total per topic -- the branch and status Totals are the same
    # 220 890 but sit under different topics, so both are kept.
    return (_emit(status, _EEIC_COLS, topic="employment_status", **kw)
            + _emit(branch, _EEIC_COLS, topic="industry", **kw)
            + _emit(occ, _EEIC_COLS, topic="occupation", **kw))


def _eeic_formality(path: str) -> list[dict]:
    """Tableaux 2 and 3: only the 'Total' column (all branches), which is the
    SECOND-TO-LAST value -- 'Hors agriculture' is last, and a row with an
    empty 'Autres' cell prints five values, not six."""
    with pdfplumber.open(path) as pdf:
        text = next(t for t in (p.extract_text() or "" for p in pdf.pages)
                    if re.search(r"Tableau\.2 Pourcentage de l'emploi informel", t))
    out = []
    specs = [(r"Tableau\.2 Pourcentage de l'emploi informel", ["Emploi informel", "Emploi formel"],
              "EEIC 2021 T2"),
             (r"Tableau\.3 Pourcentage de l'emploi dans les entreprises",
              ["Secteur informel", "Secteur formel", "Ménages"], "EEIC 2021 T3")]
    for cap, cats, code in specs:
        block = text[re.search(cap, text).end():]
        block = block[:block.index("Source")]
        sex, got = None, {}
        for ln in block.splitlines():
            m = re.match(r"^(Total|Hommes|Femmes)?\s*(" + "|".join(cats + ["Total"]) +
                         r")\s+([\d,\s]+)$", ln.strip())
            if not m:
                continue
            sex = {"Total": "total", "Hommes": "male", "Femmes": "female"}.get(m.group(1), sex)
            vals = [float(v.replace(",", ".")) for v in m.group(3).split()]
            got[(sex, m.group(2))] = vals[-2]
        for s in ("total", "male", "female"):
            parts = [got[(s, c)] for c in cats]
            if abs(sum(parts) - 100) > 0.2 or got[(s, "Total")] != 100:
                raise ValueError(f"{code} {s}: {parts}")
            for c in cats:
                out.append(C.row(topic="formality", characteristic=c,
                                 classification="Not applicable", value=got[(s, c)],
                                 survey=_EEIC, period="2021",
                                 reference_period="EEIC 2021, phase 1 (ménages)",
                                 frequency="ad_hoc", measure="share", unit="percent",
                                 working_age_base="14-64", series_code=code, sex=s))
    return out


# --------------------------------------------------------------------------
# 2. RGPH 2017
# --------------------------------------------------------------------------

_RGPH_STATUS = ["Travailleur indépendant", "Employeur/Patron",
                "Salarié/Employé permanent", "Salarié/Employé temporaire",
                "Apprenti", "Domestique", "Aide familial", "Autre",
                "Non déterminé", "Total"]
_RGPH_BRANCH = ["Agriculture, élevage Chasse et Sylviculture",
                "Pêche, Pisciculture et Aquaculture", "Activités extractives",
                "Activités de fabrication",
                "Production et distribution d'Electricité, de Gaz et d'Eau",
                "Construction",
                "Commerce, Réparation de véhicules, automobiles et d'articles domestiques",
                "Hôtels et Restaurants",
                "Transports, Activités auxiliaires de transport et communication",
                "Activités financières",
                "Immobiliers, Locations et Services aux entreprises",
                "Activités d'Administration Publique", "Education",
                "Activités de santé et d'action sociale",
                "Activités à caractère collectif ou personnel",
                "Activités des ménages en tant qu'employeurs de personnels domestique",
                "Activités des organisations extraterritoriales", "TOTAL"]
_RGPH_OCC = ["Exécutif +cadres supérieurs", "Intellectuels, Scientifiques",
             "Professions intermédiaires", "Cadre subalterne de l'administration",
             "Personnel de service et vendeurs", "Agriculture, élevage, pêche",
             "Artisanats, ouvriers", "Conducteurs d'installations et de machines",
             "Ouvriers et employés non qualifiés", "Autres métiers et professions",
             "Sans profession, profession non précisés", "Total"]


def _rgph(doc) -> list[dict]:
    kw = dict(survey=_RGPH, period="2017", reference="RGPH 2017", base="15+",
              cls="National", measure="share", unit="percent")
    out = []
    # 3.2: three blocks (Urbain, Rural, Comores) x (M, F, Total, % Femmes).
    p = _find(doc, r"Tableau 3\.2 : R.partition en \(%\) de la population active occup.e")
    toks = _stream(doc, range(p, p + 3))
    toks = toks[next(i for i, t in enumerate(toks) if t.startswith("Tableau 3.2")):]
    for blk, loc in (("Urbain", _U), ("Rural", _R), ("Comores", {})):
        rows = _rows(toks, _RGPH_STATUS, 4, f"RGPH T3.2 {blk}")
        _check_sums(rows, _RGPH_STATUS[:-1], "Total", 3, f"RGPH T3.2 {blk}", tol=0.3)
        out += _emit(rows, [{**loc, **_M}, {**loc, **_F}, loc, None],
                     topic="employment_status", code="RGPH-2017 T3.2", **kw)
        # move past this block's Effectif row (label, then its counts)
        toks = toks[next(i for i, t in enumerate(toks) if t == "Effectif") + 1:]
        while toks and re.fullmatch(r"[\d\s-]+", toks[0]):
            toks = toks[1:]
    # 3.5: branches, Urbain / Rural / Ensemble x (Homme, Femme, Total).
    p = _find(doc, r"Tableau 3\.5 : R.partition de la population active occup.e\s+par branche")
    toks = _stream(doc, range(p, p + 3))
    toks = toks[next(i for i, t in enumerate(toks) if t.startswith("Tableau 3.5")):]
    rows = _rows(toks, _RGPH_BRANCH, 9, "RGPH T3.5")
    _check_sums(rows, _RGPH_BRANCH[:-1], "TOTAL", 9, "RGPH T3.5", tol=0.35)
    cols9 = [{**_U, **_M}, {**_U, **_F}, _U, {**_R, **_M}, {**_R, **_F}, _R, _M, _F, {}]
    out += _emit(rows, cols9, topic="industry", code="RGPH-2017 T3.5", **kw)
    # 3.7: occupational groups, Masculin / Féminin / Comores / Urbain / Rural.
    p = _find(doc, r"Tableau 3\.7 : R.partition en \(%\) des actifs occup.s par cat.gories")
    toks = _stream(doc, range(p, p + 1))
    toks = toks[next(i for i, t in enumerate(toks) if t.startswith("Tableau 3.7")):]
    rows = _rows(toks, _RGPH_OCC, 5, "RGPH T3.7")
    _check_sums(rows, _RGPH_OCC[:-1], "Total", 5, "RGPH T3.7", tol=0.3)
    out += _emit(rows, [_M, _F, {}, _U, _R], topic="occupation",
                 code="RGPH-2017 T3.7", **kw)
    return out


# --------------------------------------------------------------------------
# 3. EESIC 2013
# --------------------------------------------------------------------------

_T26 = ["initiative privée", "autre acteur", "Ensemble",           # formel
        "initiative privée", "autre acteur", "Ensemble",           # informel
        "Administration publique", "Entreprise publique et parapublique",
        "Ménage employeur"]
_T26_NAMES = ["Secteur privé formel - initiative privée",
              "Secteur privé formel - autre acteur", "Secteur privé formel",
              "Secteur privé informel - initiative privée",
              "Secteur privé informel - autre acteur", "Secteur privé informel",
              "Administration publique", "Entreprise publique et parapublique",
              "Ménage employeur"]
_T26_COLS = [{"geography": "Moroni"}, {"geography": "Reste de Ngazidja"},
             {"geography": "Ndzouani"}, {"geography": "Mwali"},
             _U, _R, _M, _F, {}]


def _eesic(doc) -> list[dict]:
    p = _find(doc, r"Tableau 26 : Principaux acteurs de l.offre d.emploi")
    toks = _stream(doc, range(p, p + 2))
    toks = toks[next(i for i, t in enumerate(toks) if t.startswith("Tableau 26")):]
    raw = _rows(toks, _T26, 9, "EESIC T26")
    rows = [(n, v) for n, (_, v) in zip(_T26_NAMES, raw)]
    by = dict(rows)
    for j in range(9):
        for sub, parts in ((2, (0, 1)), (5, (3, 4))):
            if abs(rows[sub][1][j] - sum(rows[k][1][j] for k in parts)) > 0.15:
                raise ValueError(f"EESIC T26 col {j}: {rows[sub][0]} is not the "
                                 f"sum of its two actors")
        s = sum(rows[k][1][j] for k in (0, 1, 3, 4, 6, 7, 8))
        if abs(s - 100) > 0.35:
            raise ValueError(f"EESIC T26 col {j}: leaves sum to {s:.1f}")
    return _emit(rows, _T26_COLS, survey=_EESIC, period="2013",
                 reference="EESIC 2013 (novembre 2012 - octobre 2013)",
                 base="not stated", topic="sector", cls="National",
                 measure="share", unit="percent", code="EESIC-2013 T26",
                 skip={"Secteur privé formel", "Secteur privé informel"})


# --------------------------------------------------------------------------

def _kind(doc) -> str:
    # Markers the documents print on their opening pages. (The census report
    # misspells its own theme, "CARTERISTIQUES ECONOMIQUES", so it is known by
    # its RGPH banner and a table only it carries.)
    head = re.sub(r"\s+", " ", " ".join(doc[i].get_text()
                                        for i in range(min(6, len(doc)))))
    if re.search(r"Certains indicateurs du march. du travail", head):
        return "eeic"
    if re.search(r"RGPH- ?2017", head) and _has(doc, r"Tableau 3\.7 : R.partition"):
        return "rgph"
    if re.search(r"Situation de l.emploi aux Comores en 2013", head):
        return "eesic"
    raise ValueError("INSEED: unrecognised document")


def _has(doc, pat: str) -> bool:
    return any(re.search(pat, p.get_text()) for p in doc)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows, seen = [], set()
    for p in [path, *(extras or [])]:
        with fitz.open(p) as doc:
            kind = _kind(doc)
            if kind in seen:
                raise ValueError(f"INSEED: two {kind} documents")
            seen.add(kind)
            if kind == "eeic":
                rows += _eeic_counts(doc)
                rows += _eeic_formality(p)
            elif kind == "rgph":
                rows += _rgph(doc)
            else:
                rows += _eesic(doc)
    return pd.DataFrame(rows)
