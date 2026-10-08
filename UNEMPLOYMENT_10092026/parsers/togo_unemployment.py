"""Togo — INSEED, Enquête Régionale Intégrée sur l'Emploi et le Secteur
Informel (ERI-ESI) 2017, Rapport global.

THE AFRISTAT ERI-ESI TEMPLATE, read once and reused. The 2017 ERI-ESI round
was run in eight WAEMU countries on one AFRISTAT template, so the same three
headline tables recur with the same shapes in Togo's and Senegal's reports
(and in Niger's, whose recap `niger_unemployment` reads through the engine).
The reader for that template lives HERE and `senegal_unemployment` imports it,
rather than each country re-deriving it. Three tables are read:

* RECAP -- "Principaux indicateurs de l'emploi" (front matter). Columns are the
  capital city | autres urbains | ensemble urbain | rural | national; blocks for
  the BIT unemployment rate (Ensemble/Homme/Femme, then 15-34 / 35+), the SU2
  rate and the SU4 rate (likewise).
* SU TABLE -- "Principales caractéristiques de la sous-utilisation de la main
  d'œuvre" (Togo 5.4): SU1 | SU2 | labour force (count) | SU3 | SU4 | extended
  labour force (count), by sex, age group, education, milieu and region.
* OPPORTUNITIES -- "Aperçu de quelques indicateurs des possibilités d'emploi"
  (Togo 5.15): the employment-to-population ratio of the 15+, the NEET rates
  of the 15-24 and 15-35, and the employed count.

THE TABLES OVERLAP, AND THE OVERLAP IS THE CHECK. The recap's national BIT rate
is the SU table's national row; the recap's urban/rural columns are the SU
table's milieu rows. Every cell is keyed on what it measures (topic, label,
sex, age, education, place) and a cell met twice must carry the same value
both times or the parse raises; it is then emitted once.

TOPICS follow the existing francophone layouts (Burkina Faso, Niger, Cameroon):
SU1 -> unemployment_rate / strict; SU2 (time-related underemployment +
unemployment) -> underemployment_rate / broad; SU3 and SU4 ->
labour_underutilisation_rate / broad, told apart by `series_label`. Age bands
inside a breakdown are `unemployment_rate` with `age_group` set, exactly as the
report prints them, not `youth_unemployment_rate` -- INSEED does not single any
of them out as "youth".

NOT COLLECTED: the extended-labour-force count (no topic holds labour force +
potential labour force), unemployment duration (years), migration, schooling,
income, informality and vulnerability rows of the recap, the other columns of
the opportunities table (vulnerable/precarious employment, multiple jobs, wage
shares -- no topic), and the NEET cells of its AGE rows: INSEED fills the
"15-24 NEET" column on the 25-34 row (55,9), which cannot describe 15-24 year
olds. Chapters 9-14 are the informal production-unit (UPI) module.

Base 15+. Period 2017 (the survey year; the report gives no quarter).

CROSS-CHECK (Togo): chômage BIT 3,9 (H 5,0 / F 2,9; Lomé 7,8; rural 2,0);
15-34 ans 6,8; SU2 16,1; SU3 16,2; SU4 26,8 (15-34 ans 34,6); main d'œuvre
2 375 754; ratio emploi/population 60,7; NEET 15-24 26,5; actifs occupés
2 282 551.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_DEC = r"\d*,\d+"
_CNT = r"\d{1,3}(?: \d{3})*"


def num(tok: str) -> float:
    """'7,8' -> 7.8; ',9' -> 0.9 (Senegal drops the leading zero);
    '1 234 567' -> 1234567."""
    t = tok.replace(" ", "")
    if t.startswith(","):
        t = "0" + t
    return float(t.replace(",", "."))


# --------------------------------------------------------------------------
# Cells, keyed on what they measure, so overlapping tables check each other
# --------------------------------------------------------------------------
class Cells:
    def __init__(self, where: str):
        self.where = where
        self.rows: dict[tuple, dict] = {}

    def add(self, **kw):
        key = (kw["topic"], kw.get("definition", "not_applicable"),
               kw["series_label"], kw.get("sex", "total"),
               kw.get("age_group", "Total"), kw.get("education", "Total"),
               kw.get("geography", "Total country"), kw.get("locality", "all"),
               kw.get("locality_label", "Total"))
        if key in self.rows:
            if self.rows[key]["value"] != kw["value"]:
                raise ValueError(f"{self.where}: {key} printed as "
                                 f"{self.rows[key]['value']} and {kw['value']}")
            return
        self.rows[key] = C.row(**kw)

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(list(self.rows.values()))


def _lines(pages: list[str], caption: str, where: str) -> list[str]:
    """Lines of the page(s) carrying `caption`, from the caption on. The list
    of tables repeats each caption with dot leaders; those are skipped."""
    rx = re.compile(caption, re.I | re.M)
    for text in pages:
        for m in rx.finditer(text):
            # A long caption wraps in the list of tables, so its dot leaders
            # can sit on the NEXT line: look a little past the caption.
            if "...." in text[m.start():m.end() + 250]:
                continue
            return [ln.strip() for ln in text[m.start():].splitlines()[1:]]
    raise ValueError(f"{where}: caption {caption!r} not found")


# --------------------------------------------------------------------------
# The three template tables
# --------------------------------------------------------------------------
def read_recap(pages, cfg, cells: Cells) -> int:
    """'Principaux indicateurs de l'emploi': 5 columns, indicator blocks."""
    lines = _lines(pages, r"^Principaux indicateurs de l.emploi", cfg["where"])
    heads = [
        (r"^Taux de chômage (?:BIT|\(au sens strict du BIT\))\s*$", "su1"),
        (r"^Taux combiné du sous-emploi lié au temps", "su2"),
        (r"^Taux de sous-utilisation de la main", "su4"),
    ]
    rowpat = re.compile(rf"^(Ensemble|Homme|Femme|15 - 34 ans|35 ans et plus)"
                        rf"\s+((?:{_DEC}\s+){{4}}{_DEC})$")
    current, n = None, 0
    for ln in lines:
        if ln.startswith("Source"):
            break
        hit = next((key for pat, key in heads if re.match(pat, ln)), None)
        if hit:
            current = hit
            continue
        m = rowpat.match(ln)
        if not m:
            # A new capitalised heading closes the block (the recap carries
            # durations in YEARS and incomes in FCFA under headings this reader
            # does not know; their sub-rows must not be read as rates).
            if re.match(r"^[A-ZÉ]", ln) and not re.search(r"\d", ln):
                current = None
            continue
        if current is None:
            continue
        lab = m.group(1)
        extra = ({"sex": C.normalise_sex(lab)} if lab in ("Homme", "Femme")
                 else {} if lab == "Ensemble"
                 else {"age_group": re.sub(r"\s*-\s*", "-", lab)})
        for col, tok in zip(cfg["recap_columns"], m.group(2).split()):
            cells.add(**cfg["base"], **cfg["su"][current], **col, **extra,
                      value=num(tok), series_code="ERI-ESI recap")
            n += 1
    if n != 13 * 5:
        raise ValueError(f"{cfg['where']} recap: read {n} cells, expected 65 "
                         f"(13 rows x 5 columns)")
    return n


_SECTIONS = [(r"^Sexe$", "sex"), (r"^Groupe d.âges?$", "age"),
             (r"^Niveau d.instruction$", "edu"),
             (r"^Milieu de( résidence)?$", "loc"), (r"^Région$", "geo")]


def _context(section: str, label: str, cfg: dict) -> dict:
    if section == "sex":
        return {"sex": C.normalise_sex(label)}
    if section == "age":
        return {"age_group": re.sub(r"\s*-\s*", "-", label)}
    if section == "edu":
        return {"education": label}
    if section == "loc":
        return cfg["milieu"][label]
    if section == "geo":
        return {"geography": label}
    raise ValueError(f"{cfg['where']}: row {label!r} outside any section")


def read_su_table(pages, cfg, cells: Cells) -> None:
    lines = _lines(pages, cfg["su_caption"], cfg["where"])
    row = re.compile(rf"^(.+?)\s+({_DEC})\s+({_DEC})\s+({_CNT})\s+({_DEC})"
                     rf"\s+({_DEC})\s+({_CNT})$")
    section, seen, lf = None, {}, {}
    for ln in lines:
        if ln.startswith("Source"):
            break
        sec = next((k for pat, k in _SECTIONS if re.match(pat, ln)), None)
        if sec:
            section = sec
            continue
        m = row.match(ln)
        if not m:
            continue
        label = m.group(1).strip()
        ctx = {} if label == cfg["country_label"] else _context(section, label, cfg)
        seen.setdefault(section if ctx else "national", []).append(label)
        su1, su2, n_lf, su3, su4 = (num(m.group(i)) for i in (2, 3, 4, 5, 6))
        for key, v in (("su1", su1), ("su2", su2), ("su3", su3), ("su4", su4)):
            cells.add(**cfg["base"], **cfg["su"][key], **ctx, value=v,
                      series_code=cfg["su_code"])
        cells.add(**cfg["base"], topic="labour_force", series_label=cfg["lf_label"],
                  **ctx, value=n_lf, series_code=cfg["su_code"])
        lf[label] = n_lf
    for sec, want in cfg["su_expect"].items():
        if len(seen.get(sec, [])) != want:
            raise ValueError(f"{cfg['where']} SU table: {sec} rows "
                             f"{seen.get(sec)} (expected {want})")
    # The labour force of the two sexes is the national labour force.
    men, women = (lf[k] for k in ("Homme", "Femme"))
    if abs(men + women - lf[cfg["country_label"]]) > 2:
        raise ValueError(f"{cfg['where']} SU table: men + women "
                         f"{men + women:,.0f} != {lf[cfg['country_label']]:,.0f}")


def read_opportunities(pages, cfg, cells: Cells) -> None:
    lines = _lines(pages, cfg["opp_caption"], cfg["where"])
    section, employed, n_rows = None, {}, 0
    for ln in lines:
        if ln.startswith("Source"):
            break
        sec = next((k for pat, k in _SECTIONS if re.match(pat, ln)), None)
        if sec is None and re.match(r"^(Niveau|Milieu de|Groupe d)", ln) \
                and not re.search(r"\d", ln):
            # Senegal wraps "Niveau" / "d'instruction", "Milieu de" / "résidence".
            sec = {"Niveau": "edu", "Milieu": "loc", "Groupe": "age"}[ln.split()[0]]
        if sec:
            section = sec
            continue
        m = re.match(rf"^(.+?)\s+((?:(?:{_DEC}|na)\s+)+)({_CNT})$", ln)
        if not m or re.search(r"\d", m.group(1)) and section != "age":
            continue
        label = m.group(1).strip()
        toks = m.group(2).split()
        ctx = {} if label == cfg["country_label"] else _context(section, label, cfg)
        if ctx.get("locality_label") and label in cfg.get("opp_milieu", {}):
            ctx = cfg["opp_milieu"][label]
        n_rows += 1
        cells.add(**cfg["base"], topic="employment_to_population_ratio",
                  series_label="Ratio emploi/population des 15 ans et plus",
                  **ctx, value=num(toks[0]), series_code=cfg["opp_code"])
        n_emp = num(m.group(3))
        cells.add(**cfg["base"], topic="employed",
                  series_label="Actifs occupés (effectif)", **ctx, value=n_emp,
                  series_code=cfg["opp_code"])
        employed[label] = n_emp
        # NEET columns 5 and 6 are positional only on a complete row (nine
        # cells; or eight on the men's row, which lacks the last, women-only
        # column). An AGE row is never read for them -- see the docstring.
        full = len(toks) == 9 or (len(toks) == 8 and ctx.get("sex") == "male")
        if section != "age" and full:
            for i, band in ((4, "15-24"), (5, "15-35")):
                if toks[i] == "na":
                    continue
                cells.add(**cfg["base"], topic="neet_rate",
                          series_label=f"Jeunes de {band} ans ni dans le système "
                                       f"éducatif ni dans l'emploi",
                          age_group=band, **ctx, value=num(toks[i]),
                          series_code=cfg["opp_code"])
    if n_rows < cfg["opp_min_rows"]:
        raise ValueError(f"{cfg['where']} opportunities: {n_rows} rows")
    men, women = (employed[k] for k in ("Homme", "Femme"))
    if abs(men + women - employed[cfg["country_label"]]) > 2:
        raise ValueError(f"{cfg['where']} opportunities: employed men + women "
                         f"!= national")


def su_labels() -> dict:
    return {
        "su1": {"topic": "unemployment_rate", "definition": "strict",
                "series_label": "Taux de chômage BIT"},
        "su2": {"topic": "underemployment_rate", "definition": "broad",
                "series_label": "Taux combiné du sous-emploi lié au temps de "
                                "travail et du chômage"},
        "su3": {"topic": "labour_underutilisation_rate", "definition": "broad",
                "series_label": "Taux combiné du chômage et de la main d'œuvre "
                                "potentielle"},
        "su4": {"topic": "labour_underutilisation_rate", "definition": "broad",
                "series_label": "Taux de sous-utilisation de la main d'œuvre"},
    }


def read_eriesi(path: str, cfg: dict) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages[:cfg["max_page"]]]
    cells = Cells(cfg["where"])
    read_recap(pages, cfg, cells)
    read_su_table(pages, cfg, cells)
    read_opportunities(pages, cfg, cells)
    return cells.frame()


# --------------------------------------------------------------------------
# Togo
# --------------------------------------------------------------------------
_URB = {"locality": "urban"}
CONFIG = {
    "where": "Togo ERI-ESI 2017",
    "max_page": 90,
    "base": {"survey": "ERI-ESI -- Enquête Régionale Intégrée sur l'Emploi et "
                       "le Secteur Informel", "period": "2017",
             "reference_period": "ERI-ESI 2017", "frequency": "ad_hoc",
             "working_age_base": "15+"},
    "su": su_labels(),
    "country_label": "Togo",
    "recap_columns": [
        {**_URB, "locality_label": "Lomé"},
        {**_URB, "locality_label": "Autres urbains"},
        {**_URB, "locality_label": "Ens. urbain"},
        {"locality": "rural", "locality_label": "Rural"},
        {},
    ],
    "milieu": {"Lomé": {**_URB, "locality_label": "Lomé"},
               "Autres urbains": {**_URB, "locality_label": "Autres urbains"},
               "Ens. urbain": {**_URB, "locality_label": "Ens. urbain"},
               "Rural": {"locality": "rural", "locality_label": "Rural"}},
    "su_caption": r"^Tableau 5\.4\s*:\s*Principales caractéristiques de la "
                  r"sous-utilisation",
    "su_code": "ERI-ESI T5.4",
    "lf_label": "Main d'œuvre (actifs occupés + chômeurs BIT)",
    "su_expect": {"sex": 2, "age": 7, "edu": 4, "loc": 4, "geo": 6,
                  "national": 1},
    "opp_caption": r"^Tableau 5\.15\s*:\s*Aperçu de quelques indicateurs des "
                   r"possibilités d.emploi",
    "opp_code": "ERI-ESI T5.15",
    "opp_min_rows": 19,
}


def parse(path: str, extras=None) -> pd.DataFrame:
    return read_eriesi(path, CONFIG)
