"""Algeria — ONS Rétrospective Statistique 1962-2020, Chapitre II "Emploi".

ONE PDF, FORTY YEARS OF HOUSEHOLD-SIDE COMPOSITION. The chapter reprints, one
table per survey round, what ONS published at the time. Four blocks are read:

* 2000-2019 ENQUÊTE EMPLOI AUPRÈS DES MÉNAGES (Tableaux 17-35). Every round
  carries "Répartition des occupés selon le secteur d'activité - <Mois> <YYYY>":
  employed by ONS's own sector grouping, count and share. 25 rounds: one a year
  to 2013, then April AND September in 2014 and 2016-2018, and May 2019.
* 1989-1992 ENQUÊTES MAIN D'ŒUVRE (M.O.D) (Tableaux 7, 9, 11, 13): employed by
  branche d'activité économique AND SEX, in persons.
* 1997 (Tableau 15): secteur d'activité, and secteur juridique (public/privé)
  -> `sector`.
* RGPH 1977 and 1987 censuses (Tableaux 3, 5): branche by stratum -- urbain/
  rural in 1977, zone agglomérée/éparse in 1987.

WHAT IS DELIBERATELY LEFT:

* TABLEAUX 1.1-1.4, "Situation de l'emploi par secteur d'activité (Hors
  Agriculture)". A compiled series stitched from censuses, a consumption
  survey, the MOD and the LFS, excluding agriculture -- a different universe
  from every table here, and a re-presentation of the same rounds read below.
* The "dont salariés" columns of the MOD and census tables. That is industry
  crossed with status in employment, which one category column cannot hold, and
  its % is a ROW percentage (salaried share within a branch) -- see the README's
  rule on row percentages.
* Employed/unemployed by sex, stratum and age group, and the rates boxes. Those
  are labour-force STATUS levels and rates: `unemployment`'s territory.
* Tableau 16 (RGPH 1998): labour force by wilaya, not composition.

PERIODS ARE SURVEY ROUNDS, NOT YEARS. Two rounds a year from 2014 would collide
on an annual period, so each round is dated to the quarter holding its
reference month (Avril -> Q2, Septembre -> Q3, Décembre -> Q4) and the month is
kept verbatim in `reference_period`. These are single reference-week surveys,
not quarterly averages: frequency is `ad_hoc`. Censuses are annual periods.

THE CATEGORY SET CHANGES BETWEEN ROUNDS and is collected as printed: six groups
in 2000-2001 (Commerce / Services marchands / Services non marchands), four
from 2003 ("Commerce, Services & Administration" merged). No scheme is named --
classification `National`. The text layer letter-spaces some labels
("B T P", "T o t a l"); that spacing is an extraction artefact and is closed up.

UNITS CHANGE TOO: 2000-2001 publish persons, later rounds thousands
("Unité : en millier"). Read per page, never assumed.

WORKING-AGE BASE IS NOT STATED for these distributions. The retrospective's
Tableau 37 puts the activity-rate denominator at 15+, but the June 2000 age
table counts 25 075 employed "- 15 ans" -- so the employed total is NOT a 15+
figure, at least in 2000. Recorded as "not stated" rather than guessed.

SPACE THOUSANDS ARE AMBIGUOUS WHEN COUNTS SIT SIDE BY SIDE. "964 020 11 090
975 110" can be split more than one way. Each row is split under the table's
own arithmetic -- hommes + femmes = total, urbain + rural = ensemble -- and a
row with no split that satisfies it RAISES rather than guessing. The sector
blocks are checked the other way: every share must equal count / total, to
within 0,2 points (ONS's own rounding -- Sept 2018 prints Industrie 13,10 for
1 434 / 11 001 = 13,03).

CROSS-CHECK (employed by sector, thousands): Sept 2012 Agriculture 912 (9,0%),
Industrie 1 335, BTP 1 663, Commerce/Services/Administration 6 260, total
10 170. May 2019 total 11 281, Agriculture 1 083 (9,60%). June 2000 (persons)
total 6 179 992. MOD June 1989 total 4 432 050 (men 4 115 420). RGPH 1987 total
4 137 736.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from ._common import deaccent, row

CLASS = "National"
BASE = "not stated"
SURVEY_LFS = "Enquête emploi auprès des ménages (ONS)"
SURVEY_MOD = "Enquête main d'œuvre (M.O.D)"
SURVEY_1997 = "Enquête emploi 1997 (ONS)"

_MONTHS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
           "juin": 6, "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10,
           "novembre": 11, "decembre": 12}

_TOK = re.compile(r"\d+(?:,\d+)?")


# ---------------------------------------------------------------- helpers
# TYPOGRAPHIC VARIANTS OF ONE PRINTED LABEL. The same round-to-round category
# reaches the text layer as "B T P", "B. T. P", "BTP" and "B.T.P", and one
# label with its capitals two ways. Left alone that splits one series into
# four. Only spacing, punctuation and case are folded here -- a genuinely
# different WORDING (the MOD's "Administr. et services fournis à la
# Collectivité" against "Administration et services à la Collectivité") is
# kept as printed.
_CANON = {
    "btp": "B.T.P",
    "commerce, services & administration": "Commerce, Services & Administration",
}


def _label(text: str) -> str:
    """Close up letter-spacing ("T o t a l"), trailing markers, variants."""
    s = re.sub(r"\*+", "", text).strip(" .:-")
    if re.fullmatch(r"(?:\S )+\S", s):
        s = s.replace(" ", "")
    s = re.sub(r"\s+", " ", s).strip()
    key = re.sub(r"[\s.]", "", s).lower()
    if key == "btp":
        return _CANON["btp"]
    return _CANON.get(s.lower(), s)


def _split(line: str) -> tuple[str, list[str]]:
    """Label, then the numeric tokens that end the line."""
    toks = line.split()
    i = len(toks)
    while i > 0 and _TOK.fullmatch(toks[i - 1]):
        i -= 1
    return " ".join(toks[:i]), toks[i:]


def _groupings(toks: list[str], n: int):
    """Every way to read `toks` as `n` integers with space thousands.

    A number is one 1-3 digit token followed by any count of exactly-3-digit
    tokens (a lone 4+ digit token is a number on its own).
    """
    if n == 0:
        if not toks:
            yield []
        return
    if not toks or "," in toks[0]:
        return
    head = toks[0]
    if len(head) > 3:
        for rest in _groupings(toks[1:], n - 1):
            yield [int(head)] + rest
        return
    j = 1
    while True:
        for rest in _groupings(toks[j:], n - 1):
            yield [int("".join(toks[:j]))] + rest
        if j < len(toks) and len(toks[j]) == 3 and "," not in toks[j]:
            j += 1
        else:
            return


def _sum_split(toks: list[str], n: int, what: str) -> list[int]:
    """Split into `n` counts where count[0] + count[1] == count[2]."""
    hits = {tuple(g) for g in _groupings(toks, n) if g[0] + g[1] == g[2]}
    if len(hits) != 1:
        raise ValueError(f"{what}: {len(hits)} arithmetic-consistent splits of "
                         f"{' '.join(toks)!r} (need exactly 1)")
    return list(hits.pop())


def _pct(tok: str) -> float:
    return float(tok.replace(",", "."))


def _quarter(month_word: str, year: str) -> tuple[str, str]:
    m = _MONTHS[deaccent(month_word).lower()]
    return f"{year}-Q{(m - 1) // 3 + 1}", f"{month_word.capitalize()} {year}"


# ------------------------------------------------- 2000-2019 LFS rounds
_ROUND_CAP = re.compile(
    r"R[ée]partition des occup[ée]+s selon le secteur d.activit[ée]\W*"
    r"([A-Za-zéûÉ]+)\s+((?:19|20)\d{2})")


def _lfs_rounds(pages: list[str]) -> list[dict]:
    out = []
    for text in pages:
        lines = text.splitlines()
        for i, ln in enumerate(lines):
            m = _ROUND_CAP.search(ln)
            if not m:
                continue
            period, ref = _quarter(m.group(1), m.group(2))
            before = "\n".join(lines[:i])
            unit = ("thousand_persons" if re.search(r"millier", before, re.I)
                    else "persons")
            cats, total = [], None
            for body in lines[i + 1:]:
                if body.startswith(("Employed Distribution", "Occupés")):
                    continue
                label, toks = _split(body)
                if not toks:
                    raise ValueError(f"{ref}: unexpected line {body!r}")
                share = _pct(toks[-1])
                count = int("".join(toks[:-1]))
                if not all(len(t) == 3 for t in toks[1:-1]):
                    raise ValueError(f"{ref}: bad count grouping {body!r}")
                lab = _label(label)
                if lab.lower() == "total":
                    total = (count, share)
                    break
                cats.append((lab, count, share))
            if total is None or len(cats) < 4:
                raise ValueError(f"{ref}: sector block not closed by a Total")
            if abs(sum(c for _, c, _ in cats) - total[0]) > len(cats):
                raise ValueError(f"{ref}: categories do not sum to the total")
            # ONS's printed shares are not always count / total to the last
            # digit: Septembre 2018 prints Industrie 13,10 where 1 434 / 11 001
            # is 13,03, and the four shares are padded to two decimals from
            # one. Both are collected as printed; 0,2 points is the tolerance
            # that separates that rounding from a misread row.
            for lab, c, s in cats:
                if abs(c / total[0] * 100 - s) > 0.2:
                    raise ValueError(f"{ref}: {lab} share {s} != {c}/{total[0]}")
            for lab, c, s in cats + [("Total", *total)]:
                common = dict(topic="industry", characteristic=lab,
                              classification=CLASS, survey=SURVEY_LFS,
                              period=period, reference_period=ref,
                              frequency="ad_hoc", working_age_base=BASE,
                              series_code="RETRO-EMPLOI secteur")
                out.append(row(value=c, measure="count", unit=unit, **common))
                out.append(row(value=s, measure="share", unit="percent",
                               **common))
    return out


# ------------------------------------------- MOD 1989-1992, branch by sex
_MOD_CAP = re.compile(r"branche d.activit[ée] [ée]conomique et le sexe")
_MOD_REF = re.compile(r"M\.O\.D\W*Juin\s*((?:19)\d{2})")


def _mod(pages: list[str]) -> list[dict]:
    out = []
    for text in pages:
        lines = text.splitlines()
        for i, ln in enumerate(lines):
            if not ln.startswith("Tableau") or not _MOD_CAP.search(ln):
                continue
            yr = next(_MOD_REF.search(x).group(1) for x in lines[i:i + 3]
                      if _MOD_REF.search(x))
            period, ref = _quarter("Juin", yr)
            j = next(k for k in range(i, len(lines))
                     if lines[k].strip().startswith("Nombre"))
            n_rows = 0
            for body in lines[j + 1:]:
                label, toks = _split(body)
                if not toks:
                    continue          # a wrapped fragment of a long label
                # H F T salariés  %salariés -- the last is the row %, skipped
                h, f, t, _sal = _sum_split(toks[:-1], 4, f"MOD {yr} {label}")
                lab = _label(label)
                for sex, v in (("male", h), ("female", f), ("total", t)):
                    out.append(row(topic="industry", characteristic=lab,
                                   classification=CLASS, survey=SURVEY_MOD,
                                   period=period, reference_period=ref,
                                   frequency="ad_hoc", working_age_base=BASE,
                                   sex=sex, value=v, measure="count",
                                   unit="persons",
                                   series_code=f"RETRO-EMPLOI MOD {yr}"))
                n_rows += 1
                if lab.lower() == "total":
                    break
            if n_rows != 10:
                raise ValueError(f"MOD {yr}: {n_rows} rows, expected 10")
    return out


# ------------------------------------------------------------- 1997
def _y1997(pages: list[str]) -> list[dict]:
    text = next(p for p in pages if "Tableau 15" in p)
    out = []
    blocks = [("secteur d’activité en 1997", "industry"),
              ("secteur juridique en 1997", "sector")]
    lines = text.splitlines()
    for key, topic in blocks:
        i = next(k for k, x in enumerate(lines)
                 if x.startswith("Répartition") and key in x.replace("'", "’"))
        cats = []
        for body in lines[i + 1:]:
            label, toks = _split(body)
            if len(toks) < 2 or "," not in toks[-1] and toks[-1] != "100":
                continue
            lab = _label(label)
            count = int("".join(toks[:-1]))
            cats.append((lab, count, _pct(toks[-1])))
            if lab.lower() == "total":
                break
        total = cats[-1][1]
        # Thousands, rounded per category: the six sectors sum to 5 707
        # against a printed total of 5 708.
        if cats[-1][0].lower() != "total" or \
                abs(sum(c for _, c, _ in cats[:-1]) - total) > len(cats) - 1:
            raise ValueError(f"1997 {topic}: categories do not sum to total")
        for lab, c, s in cats:
            common = dict(topic=topic, characteristic=lab,
                          classification=CLASS if topic == "industry"
                          else "Not applicable",
                          survey=SURVEY_1997, period="1997",
                          reference_period="1997", frequency="ad_hoc",
                          working_age_base=BASE,
                          series_code=f"RETRO-EMPLOI T15 {topic}")
            out.append(row(value=c, measure="count", unit="thousand_persons",
                           **common))
            out.append(row(value=s, measure="share", unit="percent", **common))
    return out


# ------------------------------------------------- RGPH 1977 and 1987
_CENSUS = {
    # caption fragment, year, (stratum labels in printed order), tokens used
    "R.G.P.H. 1977": ("1977", [("urban", "Urbain"), ("rural", "Rural")]),
    "R.G.P.H. 1987": ("1987", [("other", "Zone agglomérée (ACL+AS)"),
                               ("other", "Zone éparse")]),
}


# ROWS THAT DO NOT ADD UP AS PRINTED. RGPH 1977's Administration row is 60 over
# (271 706 + 125 373 = 397 079, printed 397 019) and Autres Services 60 under
# (73 827 + 27 097 = 100 924, printed 100 984) -- yet all three COLUMNS sum
# exactly to the printed Total row. So 60 persons sit in the wrong row of ONE
# column, and nothing on the page says which. Both rows are collected as
# printed; each entry here must reproduce the printed digits exactly, and the
# column-sum check below still has to pass.
_MISPRINTS = {
    ("1977", "Administration et services fournis à la collectivité"):
        (271706, 125373, 397019),
    ("1977", "Autres Services"): (73827, 27097, 100984),
}


def _census(pages: list[str]) -> list[dict]:
    out = []
    lines = "\n".join(pages).splitlines()
    for cap, (yr, strata) in _CENSUS.items():
        i = next(k for k, x in enumerate(lines)
                 if x.startswith("Tableau") and "branche" in x and cap in x)
        j = next(k for k in range(i, len(lines))
                 if lines[k].startswith("Agriculture"))
        table = []
        for body in lines[j:]:
            label, toks = _split(body)
            if not toks:
                continue
            lab = _label(label)
            # 1977: U R Ens %sal ; 1987: A E Ens salariés %sal
            n = 3 if yr == "1977" else 4
            if (yr, lab) in _MISPRINTS:
                vals = _MISPRINTS[(yr, lab)]
                printed = "".join(toks[:-1])
                if not printed.startswith("".join(map(str, vals))):
                    raise ValueError(f"RGPH {yr} {lab}: misprint entry no "
                                     f"longer matches the page ({printed})")
            else:
                vals = _sum_split(toks[:-1], n, f"RGPH {yr} {label}")[:3]
            table.append((lab, vals))
            if lab.lower() == "total":
                break
        if len(table) != 11 or table[-1][0].lower() != "total":
            raise ValueError(f"RGPH {yr}: {len(table)} rows, expected 11")
        for col in range(3):
            if sum(v[col] for _, v in table[:-1]) != table[-1][1][col]:
                raise ValueError(f"RGPH {yr}: column {col} does not sum to "
                                 f"its Total")
        for lab, vals in table:
            for (loc, loc_lab), v in zip(strata + [("all", "Total")], vals):
                out.append(row(topic="industry", characteristic=lab,
                               classification=CLASS,
                               survey=f"Recensement général de la population "
                                      f"et de l'habitat (RGPH) {yr}",
                               period=yr, reference_period=f"RGPH {yr}",
                               frequency="ad_hoc", working_age_base=BASE,
                               locality=loc, locality_label=loc_lab,
                               value=v, measure="count", unit="persons",
                               series_code=f"RETRO-EMPLOI RGPH {yr}"))
    return out


def parse(local_path: str) -> pd.DataFrame:
    with pdfplumber.open(local_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    rows = _lfs_rounds(pages) + _mod(pages) + _y1997(pages) + _census(pages)
    return pd.DataFrame(rows)
