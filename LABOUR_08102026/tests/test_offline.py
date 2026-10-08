"""Offline self-test for the labour collector.

No network and no live NSO fetch: it replays the ACTUAL printed lines of
published tables through the real parsers, then puts the result through the
real schema validator.

    python -m indicators.labour.tests.test_offline

EVERY FIXTURE BELOW IS VERBATIM from the document the collector downloaded --
pasted exactly as `pdfplumber` renders it, or as the page's own HTML markup
reads, wrapped labels and stray spaces and all. That is not fussiness: the MPI
suite learned it the hard way, when fixtures reconstructed from notes all
turned out to have the wrong number of columns and passed against a parser that
could not read the real report. A fixture written to match the layout tests
nothing.

THE FAILURE MODE THIS SUITE EXISTS FOR is not a crash. It is a row whose value
is well formed, in range, correctly typed, and attached to the WRONG SERIES --
which no validator can see. Every case here is one of those:

* **Morocco, word positions** (`test_morocco_fragment_assignment`) -- the
  flagship. Two occupation groups wrap around their own numbers, and giving
  both loose lines to the row above balances the page perfectly while ending
  one category with the next one's opening words. It would publish the
  directors' 0,9 under "professions libérales". Real page-25 coordinates.
* **Morocco, end to end** -- a caption that shares its line with the first
  category, five columns that are two dimensions (sex and locality), and
  "Total 100 100 100 100 100", which the French space-grouping rule reads as
  the single number 100100100100100.
* **Burkina Faso** -- a chart whose category values are printed as TEXT data
  labels, and the x-axis tick line sitting directly under them.
* **Tunisia** -- an HTML table whose caption is above it, whose page furniture
  arrives as rows, whose missing cells are "--", and whose columns are headed
  with French ordinal quarters that would otherwise date as bare years.
* **Zambia** -- six columns (a count and a share per sex), labels that wrap
  three different ways, and a dash row that must be skipped rather than shifted.
* **Eswatini, word positions** -- a lower-case continuation ("supply") that
  balance alone assigns to the wrong row, truncating one category and
  prefixing the next. Real page-14 coordinates, and a second independent case
  for the same rule Morocco exercises.
* **Eswatini, end to end** -- a column stub merged into the first data row,
  and the employment LEVEL above the table that must not be collected.
* **Algeria** -- adjacent counts with SPACE thousands ("964 020 11 090 975
  110"), which read more than one way; split under hommes + femmes = total,
  and a row that adds up no way (RGPH 1977's misprint) must be refused.
* **Angola** -- a published column that sums to 100 with its values against
  the wrong labels (dropped, and re-checked so a correction is noticed), and a
  quarter that sums to 104,57 as published (kept, pinned).
* **Gambia** -- a 120-character ISIC label that the engine's default pattern
  silently skipped, and GBoS's "*" small-sample marker ahead of a number.
* **Lesotho** -- ICSE-18-A group headings on their own lines, which geometry
  folded into the category below ("Dependent contractors ... Employees").
* **Liberia** -- a table whose labels sit BELOW their numbers, which word
  geometry shifted by one row ("Informal sector" given the household figures).
* **Mali** -- a workbook's national row that is a digit-for-digit copy of its
  rural row: dropped by name and re-checked, an unlisted copy stopped by the
  male/female range guard, and a correction by INSTAT noticed.
* **Chad** -- a wrapped row whose VALUES are split across the wrap (share on
  one line, count on the next), where a naive read takes years of study as
  the share.
* **The guards** -- that `expect_rows`, the classification requirement, the
  period format and the share range actually fire.
"""
from __future__ import annotations
import copy
import datetime as dt
import os
import re
import sys
import tempfile

import pandas as pd

from indicators.labour import schema
from indicators.labour.parsers import _common as C
from indicators.labour.parsers import pdf_tables_labour as P

FAILURES: list[str] = []


def check(name: str, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


# ---------------------------------------------------------------------------
# unit checks on the shared helpers
# ---------------------------------------------------------------------------

def test_numbers():
    # English: comma thousands, dot decimal (ZamStats Table 5.2).
    check("en row", C.numbers_in("Employers in corporations 60,762 1.5", "."),
          [60762.0, 1.5])
    # French/Portuguese: comma decimal, and a SPACE groups thousands.
    check("fr thousands", C.numbers_in("Força de trabalho 9 562 740", ","),
          [9562740.0])
    check("fr decimal", C.numbers_in("Salariés 61,1 60,6 70,9", ","),
          [61.1, 60.6, 70.9])
    # THE CONVENTION IS THE LAYOUT'S, NOT THE LANGUAGE'S. CSO Eswatini prints
    # English decimals but SPACE-separates its thousands, and its layout
    # therefore declares `decimal: "."` -- under which a space groups nothing
    # and the base line "Employed population 131 586 128 770 260 356" reads as
    # SIX numbers rather than three. That is why it self-skips against a
    # three-column table instead of being collected as an employment level,
    # which belongs to `unemployment`.
    check("base line reads as six",
          C.numbers_in("Employed population 131 586 128 770 260 356", "."),
          [131.0, 586.0, 128.0, 770.0, 260.0, 356.0])
    # A SPACE IS NOT ALWAYS A THOUSANDS SEPARATOR. HCP Morocco closes every
    # percentage block on "Total 100 100 100 100 100" -- five values, each
    # group three digits, which the space-grouping rule read as one number.
    check("space_thousands off",
          C.numbers_in("Total 100 100 100 100 100", ",", space_thousands=False),
          [100.0, 100.0, 100.0, 100.0, 100.0])
    check("space_thousands on",
          C.numbers_in("Total 100 100 100 100 100", ","),
          [100100100100100.0])
    # A LEADING COMMA IS A LOST ZERO. HCP Morocco drops the leading zero on
    # small decimals (",0", ",1", ",3"). Read naively the digit after the comma
    # is taken alone, so 0,1 becomes 1.0 -- a TENFOLD error at full column
    # width, which is worse than a skipped row because nothing downstream can
    # see it.
    check("lost leading zero", C.numbers_in("Autres 0,1 ,0 ,3 1,2", ","),
          [0.1, 0.0, 0.3, 1.2])
    check("lost zero alone", C.numbers_in("Apprentis ,9", ","), [0.9])
    # A MIXED ROW must keep every column: HCP prints normal decimals and
    # zero-less ones on the same line, and losing one slides the rest left.
    check("mixed leading-comma row",
          C.numbers_in("Autres 3,7 ,6 1,9 5,0 3,0", ",", space_thousands=False),
          [3.7, 0.6, 1.9, 5.0, 3.0])
    # ... and a comma BETWEEN digits is still an ordinary decimal.
    check("ordinary decimal intact", C.numbers_in("Cadres 12,4 3,0", ","),
          [12.4, 3.0])
    # A DASH IS A CELL. Statistics Botswana prints "613 - 613"; dropping the
    # dash slides every later value one column left.
    check("keep_dash", C.numbers_in("Plant & Machine 33,165 - 613", ".",
                                    keep_dash=True),
          [33165.0, None, 613.0])
    # Non-numeric cells must be None, never 0.
    for token in ("-", "--", "..", "n.a.", ""):
        check(f"non-numeric {token!r}", C.to_number(token), None)


def test_periods():
    for text, want in [
        ("2022Q3", "2022-Q3"),
        ("Q1 2026", "2026-Q1"),
        ("Jan-Mar 2024", "2024-Q1"),
        ("2019", "2019"),
        # INS Tunisie's column headers. WITHOUT these, all nine quarterly
        # columns fall through to the bare-year branch and become three ANNUAL
        # periods that then collide on the merge key -- values that look
        # entirely right, filed under the wrong period.
        ("première-trimestre 2024", "2024-Q1"),
        ("deuxième-trimestre 2025", "2025-Q2"),
        ("troisième-trimestre 2025", "2025-Q3"),
        ("quatrième-trimestre 2025", "2025-Q4"),
        ("T2 2026", "2026-Q2"),
    ]:
        check(f"period {text!r}", C.parse_period(text), want)


def test_row_refuses_category_without_scheme():
    """An industry or occupation label is not comparable across countries
    without the scheme that produced it, so the row builder refuses one."""
    base = dict(topic="industry", characteristic="Commerce", value=24.4,
                survey="s", period="2023", frequency="ad_hoc",
                measure="share", unit="percent")
    try:
        C.row(classification="Not applicable", **base)
        FAILURES.append("row() accepted an industry row with no classification")
    except ValueError:
        pass
    # ... and accepts the same row once the scheme is named.
    try:
        C.row(classification="National", **base)
    except Exception as e:
        FAILURES.append(f"row() rejected a legitimate National industry row: {e}")


# ---------------------------------------------------------------------------
# Morocco: rebuilding rows from word POSITIONS
# ---------------------------------------------------------------------------
#
# VERBATIM page-25 geometry of "Activité, emploi et chômage", as
# `extract_words` reports it: (top, x0, x1, bottom, text) per physical line.
# Two occupation groups wrap AROUND their own numbers here, and the second
# group's label is split across the break.
MOROCCO_WORDS = [
    (147.1, 76.2, 255.7, 158.1, "- Structure de l’emploi selon les grands"),
    (155.6, 76.2, 214.6, 166.7, "groupes de professions (en %)"),
    (167.5, 82.3, 240.7, 178.5, "Membres des corps législatifs, élus"),
    (175.9, 76.2, 241.8, 186.9, "locaux, responsables hiérarchiques"),
    (181.4, 305.3, 519.1, 192.5, "0,9 0,5 1,3 0,1 0,9"),
    (184.3, 76.2, 242.4, 195.3, "de la fonction publique directeurs et"),
    (192.7, 76.2, 226.8, 203.7, "cadres de direction d’entreprises"),
    (204.6, 85.9, 244.5, 215.6, "Cadres supérieurs et membres des"),
    (210.1, 305.3, 519.1, 221.1, "3,4 10,7 7,3 0,8 4,9"),
    (213.0, 76.2, 169.3, 224.0, "professions libérales"),
    (225.0, 84.1, 154.7, 236.0, "Cadres moyens"),
    (227.4, 305.3, 519.1, 238.4, "2,5 8,1 5,4 0,7 3,6"),
]


class _StubPage:
    """The only part of a pdfplumber page `_word_lines` uses."""

    def __init__(self, lines):
        self._lines = lines

    def extract_words(self, **_kw):
        words = []
        for top, x0, x1, bottom, text in self._lines:
            toks = text.split()
            span = (x1 - x0) / max(len(toks), 1)
            for i, tok in enumerate(toks):
                words.append({"text": tok, "top": top, "bottom": bottom,
                              "x0": x0 + i * span,
                              "x1": x0 + (i + 1) * span - 0.5})
        return words


def test_morocco_fragment_assignment():
    """THE CASE THIS ENGINE'S HARDEST RULE EXISTS FOR.

    Two loose label lines sit between two data rows. Handing BOTH to the row
    above balances the page perfectly -- and is wrong: it ends one category
    with the next one's opening words and publishes the next as "professions
    libérales", a fragment of "Cadres supérieurs et membres des professions
    libérales" and a far narrower occupation than the group it names.

    Which values belong to which label is settled by GEOMETRY, not by which
    reading is more plausible: the 0,9 run sits inside the first label's block
    and the 3,4 run inside the second's. Both readings sum to 100, so the
    arithmetic cannot catch this.
    """
    barrier = re.compile(r"Structure de l.emploi selon|^Indicateurs\b", re.I)
    lines = P._word_lines(_StubPage(MOROCCO_WORDS), 2, barrier)

    directors = [l for l in lines if "0,9 0,5 1,3 0,1 0,9" in l]
    seniors = [l for l in lines if "3,4 10,7 7,3 0,8 4,9" in l]
    check("MA one row per value run", (len(directors), len(seniors)), (1, 1))
    if not (directors and seniors):
        return

    # The legislators/directors group keeps its whole label ...
    check("MA directors label head",
          "Membres des corps législatifs" in directors[0], True)
    check("MA directors label tail",
          "cadres de direction d’entreprises" in directors[0], True)
    # ... and must NOT have swallowed the next group's opening words.
    check("MA directors did not steal the next label",
          "Cadres supérieurs" in directors[0], False)
    # The senior-professionals group is whole, not the bare tail.
    check("MA seniors label head",
          seniors[0].startswith("Cadres supérieurs et membres des"), True)
    check("MA seniors label tail", "professions libérales" in seniors[0], True)
    # The sub-heading is a barrier, not a label fragment: it stays on its own
    # line rather than being folded into the first category.
    check("MA sub-heading not in a data row",
          any("Structure de l’emploi selon les grands" in l and "0,9" not in l
              for l in lines), True)


# VERBATIM page-14 geometry of the CSO Eswatini ILFS 2023 booklet. "supply"
# is a lower-case continuation sitting between two data rows, and it is the
# case the fragment rule's lower-case penalty was written for.
ESWATINI_WORDS = [
    (192.3, 77.3, 515.0, 204.3, "Manufacturing 14.5 18.7 16.6"),
    (207.9, 77.3, 515.0, 219.9, "Electricity, gas, steam and air conditioning 1.1 0.4 0.7"),
    (221.8, 77.3, 109.2, 233.8, "supply"),
    (236.2, 77.3, 515.0, 248.2, "Water supply; sewerage, waste management and 0.4 0.0 0.2"),
    (249.9, 77.3, 181.1, 261.9, "remediation activities"),
    (264.3, 77.3, 515.0, 276.3, "Construction 12.1 0.9 6.5"),
]


def test_eswatini_fragment_assignment():
    """A LOWER-CASE FRAGMENT CONTINUES THE ROW ABOVE.

    "supply" sits between two data rows, and giving it to the row BELOW
    balances the page as well as giving it to the row above -- so balance
    alone cannot decide, and the wrong choice truncates one category
    ("Electricity, gas, steam and air conditioning") while prefixing the next
    ("supply Water supply; sewerage ..."). Both products look like perfectly
    ordinary categories downstream.

    English continues a wrapped label in lower case and starts a new one
    capitalised, which is why lower case is treated as strong evidence here
    rather than as a tie-break.
    """
    lines = P._word_lines(_StubPage(ESWATINI_WORDS), 2, None)

    elec = [l for l in lines if "1.1 0.4 0.7" in l]
    water = [l for l in lines if "0.4 0.0 0.2" in l]
    check("SZ one row per value run", (len(elec), len(water)), (1, 1))
    if not (elec and water):
        return

    # The continuation belongs ABOVE ...
    check("SZ electricity keeps 'supply'", "supply" in elec[0], True)
    check("SZ electricity label whole",
          elec[0].startswith("Electricity, gas, steam and air conditioning supply"),
          True)
    # ... and must not have been prefixed onto the row below.
    check("SZ water not prefixed by 'supply'",
          water[0].startswith("Water supply;"), True)
    # The row below keeps its OWN lower-case tail, which wraps forward.
    check("SZ water keeps its own tail",
          "remediation activities" in water[0], True)


# ---------------------------------------------------------------------------
# end-to-end: replayed published pages
# ---------------------------------------------------------------------------

def run_layout(module, pages: list[str], scan_expect: int | None = None,
               only: int | None = None, keep: str | None = None):
    """Parse replayed pages with a country's REAL layout, monkeypatching only
    the PDF text extraction.

    `scan_expect` lowers the `expect_rows` guard, because a fixture is an
    excerpt of a report and the guard is calibrated for the whole thing. The
    guard itself is never relaxed in a layout module, and
    `test_expect_rows_guard_fires` proves it still bites.
    """
    cfg = copy.deepcopy(module.LAYOUT)
    # A fixture is ONE page of a report whose layout may hold several specs,
    # and a spec whose page is absent rightly raises. `keep` selects the spec
    # under test by its series_code; `only` takes the first n.
    if keep is not None:
        cfg["tables"] = [t for t in cfg["tables"]
                         if t.get("series_code") == keep]
    if only is not None:
        cfg["tables"] = cfg["tables"][:only]
    if scan_expect is not None:
        for tbl in cfg.get("tables", []):
            if tbl.get("row_scan"):
                tbl["row_scan"]["expect_rows"] = scan_expect
    orig = P._pages
    P._pages = lambda *_a, **_k: pages
    try:
        return P.make_parser(cfg)("<replay>")
    finally:
        P._pages = orig


def finish(df: pd.DataFrame, country: str) -> pd.DataFrame:
    """Attach the identity columns run.py adds, then validate for real."""
    df = df.copy()
    df["country"] = country
    df["iso3"] = "XXX"
    df["indicator"] = "Labour"
    df["source_type"] = "pdf"
    df["source_url"] = "https://example.invalid/replay"
    df["source_file"] = "replay.pdf"
    df["extracted_at"] = dt.datetime.now().isoformat(timespec="seconds")
    for col in schema.LABOUR_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return schema.validate_labour(df)


def pick(df, topic, **kw):
    m = df["topic"] == topic
    for k, v in kw.items():
        m &= df[k] == v
    vals = df.loc[m, "value"].tolist()
    return vals[0] if len(vals) == 1 else vals


# --- Morocco, as the word-position reader composes page 25 -----------------
MOROCCO_PAGE25 = """Tableau 4 : Les indicateurs socio-professionnels de l’emploi selon le sexe et le
milieu de résidence (suite),
Indicateurs Masculin Féminin Urbain Rural National
- Structure de l’emploi selon les grands
groupes de professions (en %) Membres des corps législatifs, élus locaux, responsables hiérarchiques de la fonction publique directeurs et cadres de direction d’entreprises 0,9 0,5 1,3 0,1 0,9
Cadres supérieurs et membres des professions libérales 3,4 10,7 7,3 0,8 4,9
Cadres moyens 2,5 8,1 5,4 0,7 3,6
Employés 13,7 16,4 19,5 5,4 14,2
Commerçants, intermédiaires commerciaux et financiers 9,9 2,4 10,6 4,7 8,4
Exploitants agricoles, pêcheurs, forestiers chasseurs et travailleurs assimilés 9,7 5,8 1,0 22,3 8,9
Artisans et ouvriers qualifiés des métiers artisanaux (non compris les ouvriers de l’agriculture) 20,7 10,4 22,9 11,6 18,6
Ouvriers et manœuvres agricoles et de la pêche (y compris les ouvriers qualifiés) 13,7 26,3 3,4 37,7 16,2
Conducteurs d’installations et de machines et ouvriers de l’assemblage 5,3 1,7 5,7 2,7 4,6
Manœuvres non agricoles, manutentionnaires et travailleurs des petits métiers 20,0 17,7 22,9 14,1 19,6
Total 100 100 100 100 100
- - Structure de l’emploi selon le statut
professionnel (en %) Salariés 61,1 60,6 70,9 44,6 61,0
Indépendants 29,5 13,3 22,7 31,9 26,2
Employeurs 1,9 0,8 2,4 0,5 1,7
Aides familiales 5,0 24,0 1,5 21,2 8,9
Apprentis 0,3 0,2 0,3 0,3 0,3
Autres situations 2,2 1,1 2,2 1,5 1,9
Total 100 100 100 100 100
24
"""


MOROCCO_COVER = """RÉSULTATS ANNUELS 2025
Année 2025
"""


def test_morocco_label_accepts_a_lost_leading_zero():
    """A CATEGORY WHOSE FIRST VALUE HAS NO LEADING ZERO MUST STILL BE READ.

    HCP prints "Activités mal désignées ,0 ,1 ,3" in Tableau 5. A label
    pattern ending at `(?=\\d)` never fires there -- the next character is a
    comma -- so the row produced no label and was dropped BEFORE `numbers_in`
    could restore the zero. It vanished from two of five blocks, and only
    `expect_rows` made that visible.
    """
    from indicators.labour.parsers import morocco_labour as M
    lab = re.compile(M._LABEL)
    for line, want_label, want_nums in (
        ("Activités mal désignées ,0 ,1 ,3", "Activités mal désignées",
         [0.0, 0.1, 0.3]),
        ("Non déclaré ,1 ,1 ,1 ,0 ,1", "Non déclaré",
         [0.1, 0.1, 0.1, 0.0, 0.1]),
        # ... and an ordinary row is unchanged.
        ("Secteur privé 97,8 94,0 71,0", "Secteur privé", [97.8, 94.0, 71.0]),
    ):
        m = lab.match(line)
        check(f"label of {line[:28]!r}", m.group(1) if m else None, want_label)
        if m:
            check(f"values of {line[:28]!r}",
                  C.numbers_in(line[m.end():], decimal=",",
                               space_thousands=False), want_nums)


def test_morocco_end_to_end():
    """A caption sharing its line with the first category, five columns that
    are TWO dimensions, and a Total row of five 100s.

    THE COVER PAGE IS PART OF THE FIXTURE ON PURPOSE. Morocco's layout sets no
    fixed period and dates the report from its own cover ("RÉSULTATS ANNUELS
    2025"); replaying the table page alone makes the parser refuse to date it,
    which is the correct behaviour and is asserted separately in
    `test_no_silent_undated_output`. Pinning a period here to make the fixture
    parse would have hidden that.
    """
    from indicators.labour.parsers import morocco_labour as M
    df = finish(run_layout(M, [MOROCCO_COVER, MOROCCO_PAGE25], only=2), "Morocco")

    check("MA period", sorted(set(df.period)), ["2025"])
    check("MA topics", sorted(set(df.topic)),
          ["employment_status", "occupation"])
    check("MA classification", set(df.classification), {"National"})
    check("MA everything is a share", set(df.measure), {"share"})

    # THE CAPTION LINE CARRIES THE FIRST CATEGORY. If it were dropped whole,
    # this row -- and the first row of every other block -- would vanish.
    check("MA directors national",
          pick(df, "occupation", sex="total", locality="all",
               characteristic="Membres des corps législatifs, élus locaux, "
                              "responsables hiérarchiques de la fonction "
                              "publique directeurs et cadres de direction "
                              "d’entreprises"), 0.9)
    check("MA seniors national",
          pick(df, "occupation", sex="total", locality="all",
               characteristic="Cadres supérieurs et membres des professions "
                              "libérales"), 4.9)

    # SEX AND LOCALITY ARE SEPARATE DIMENSIONS. Read flat, "Urbain" would be
    # published as a third sex.
    check("MA salaries male",
          pick(df, "employment_status", sex="male", locality="all",
               characteristic="Salariés"), 61.1)
    check("MA salaries female",
          pick(df, "employment_status", sex="female", characteristic="Salariés"), 60.6)
    check("MA salaries urban",
          pick(df, "employment_status", locality="urban",
               characteristic="Salariés"), 70.9)
    check("MA salaries rural",
          pick(df, "employment_status", locality="rural",
               characteristic="Salariés"), 44.6)
    check("MA salaries national",
          pick(df, "employment_status", sex="total", locality="all",
               characteristic="Salariés"), 61.0)
    check("MA urbain is not a sex", set(df.sex), {"male", "female", "total"})

    # "Total 100 100 100 100 100" is FIVE values, not 100100100100100.
    check("MA occupation total row",
          pick(df, "occupation", sex="total", locality="all",
               characteristic="Total"), 100.0)
    check("MA no fused number", bool((df.value <= 100).all()), True)

    # Each block is a complete distribution: the categories plus the published
    # Total come to 200 per column TO ROUNDING. Not exactly 200 -- HCP's ten
    # occupation shares sum to 99,9, and across the five columns the totals
    # run 199,8 to 200,1. Asserting exact equality would be asserting
    # something the source does not publish.
    occ = df[(df.topic == "occupation") & (df.sex == "total") &
             (df.locality == "all")]
    check("MA occupation column sums to ~200",
          abs(occ.value.sum() - 200.0) <= 0.3, True)


# --- Burkina Faso: a chart whose values are text --------------------------
BURKINA_PAGE15 = """Figure 4: Répartition des emplois selon la branche d’activité (%)
Agriculture, sylviculture, pêche 31,4
Commerce 24,4
Activités de fabrication 16,4
Activités extractives 4,1
Construction 4
Enseignement 3,5
Hébergement et restauration 2,9
Autres activités de services n.c.a 2,9
Transports et entreposage 2,5
Activités spéciales des ménages 1,8
Autres branches d'activité 1,6
Activités d'administration publique 1,1
Activités de services de soutien et de bureau 1,1
Activités pour la santé humaine et l'action sociale 1
Activités artistiques, sportives et récréatives 0,6
Activités spécialisées, scientifiques et techniques 0,6
0 5 10 15 20 25 30 35
Le taux de pluriactivité est estimé à 6,1% au niveau national (figure 5). Selon le milieu de résidence, 7,4%
des actifs occupés exercent plusieurs activités en zone rurale. Ils sont 2,5% à Ouagadougou et 3,8%
dans les autres milieux urbains. Ce taux est plus faible chez les femmes que chez les hommes. En effet,
il est de 8,4% pour les hommes et 4,2% pour les femmes. Globalement, le taux de pluriactivité est plus
important chez les populations vivant en milieu rural et chez les actifs occupés de sexe masculin (figure
5).
Figure 5: Taux de pluriactivité selon le milieu de résidence
15
"""


def test_burkina_chart_data_labels():
    """INSD prints its categories and values as TEXT data labels, so they
    exist in the file -- unlike ZIMSTAT's charts, which carry none and are
    blocked. The x-axis tick line sits directly under the last category."""
    from indicators.labour.parsers import burkina_faso_labour as B
    df = finish(run_layout(B, [BURKINA_PAGE15]), "Burkina Faso")

    check("BF rows", len(df), 16)
    check("BF period", sorted(set(df.period)), ["2023"])
    check("BF base 16+", set(df.working_age_base), {"16+"})
    check("BF classification", set(df.classification), {"National"})
    check("BF agriculture",
          pick(df, "industry", characteristic="Agriculture, sylviculture, pêche"),
          31.4)
    check("BF commerce", pick(df, "industry", characteristic="Commerce"), 24.4)
    # An integer among decimals -- "Construction 4", not "4,0".
    check("BF construction", pick(df, "industry", characteristic="Construction"), 4.0)
    # The published distribution.
    check("BF sums to 99.9", round(df.value.sum(), 1), 99.9)

    # THE X-AXIS IS NOT A CATEGORY. It is excluded for carrying eight values
    # where one is expected, not by being named -- and the same structural rule
    # keeps the prose below it out ("... 6,1% ... 7,4%").
    axis = [c for c in df.characteristic if re.search(r"\d", str(c))]
    check("BF no numeric-looking category", axis, [])
    check("BF no prose row",
          any("pluriactivité" in str(c) for c in df.characteristic), False)
    check("BF all values in range", bool(df.value.between(0, 100).all()), True)


# --- Zambia: six columns, wrapped labels, and a dash row ------------------
ZAMBIA_PAGE = """Table 5.2: Number and Percentage Distribution of Employed Persons by Status in employment and Sex,
Zambia 2024
Total Male Female
Status in employment
Number Percent Number Percent Number Percent
Total 3,972,883 100.0 2,425,055 100.0 1,547,828 100.0
Employers in corporations 60,762 1.5 43,048 1.8 17,714 1.1
Employers in household market
34,196 0.9 23,589 1.0 10,607 0.7
enterprises
Owner-operators of corporations
497 0.0 497 0.0 0 0.0
without employees
Own account workers in household
market enterprises without 1,739,620 43.8 966,389 39.9 773,230 50.0
employees
Dependent contractors 0 - 0 - 0 -
Permanent employees 774,392 19.5 521,348 21.5 253,044 16.3
Fixed-term employees 895,290 22.5 607,739 25.1 287,550 18.6
Short-term and casual employees 236,312 5.9 166,457 6.9 69,855 4.5
Paid apprentices, trainees and
54,588 1.4 38,074 1.6 16,514 1.1
interns
Contributing family workers 177,227 4.5 57,913 2.4 119,314 7.7
23
"""


def test_zambia_wrapped_labels_and_dash():
    """Labels wrap three different ways on one page, and the dash row must be
    skipped rather than shifted."""
    from indicators.labour.parsers import zambia_labour as Z
    df = finish(run_layout(Z, [ZAMBIA_PAGE]), "Zambia")

    check("ZM classification", set(df.classification), {"ICSE-18-A"})
    check("ZM counts are persons",
          set(df.loc[df.measure == "count", "unit"]), {"persons"})
    check("ZM total employed",
          pick(df, "employment_status", characteristic="Total", sex="total",
               measure="count"), 3972883.0)

    # A label wrapping AROUND its own numbers is rebuilt whole.
    own = "Own account workers in household market enterprises without employees"
    check("ZM own-account count",
          pick(df, "employment_status", characteristic=own, sex="total",
               measure="count"), 1739620.0)
    check("ZM own-account share",
          pick(df, "employment_status", characteristic=own, sex="total",
               measure="share"), 43.8)
    check("ZM own-account male share",
          pick(df, "employment_status", characteristic=own, sex="male",
               measure="share"), 39.9)
    check("ZM own-account female share",
          pick(df, "employment_status", characteristic=own, sex="female",
               measure="share"), 50.0)
    # A label wrapping forward, head then values then tail.
    check("ZM household-market employers",
          pick(df, "employment_status",
               characteristic="Employers in household market enterprises",
               sex="total", measure="count"), 34196.0)

    # A DASH IS NOT A ZERO. ZamStats prints the count 0 and the share "-", so
    # the row yields three numbers against six columns and is skipped whole --
    # rather than sliding the male and female counts into the share columns.
    check("ZM dash row skipped",
          "Dependent contractors" in set(df.characteristic), False)
    # ... but a PUBLISHED zero is a real figure and must SURVIVE. ZamStats
    # prints 0.0 shares for owner-operators of corporations, and dropping
    # those would be the mirror-image error to inventing one for the dash.
    check("ZM published zeros kept",
          bool((df.loc[df.measure == "share", "value"] == 0.0).any()), True)


# --- Eswatini: a lower-case continuation, and a merged column stub --------
ESWATINI_PAGE = """Table 4.6: Percentage distribution of employed population by sex and economic activity
Sex
Male Female Both Sexes
Employed population 131 586 128 770 260 356
Economic activity
Agriculture, forestry and fishing 18.2 10.0 14.1
Mining and quarrying 0.3 0.1 0.2
Manufacturing 14.5 18.7 16.6
Electricity, gas, steam and air conditioning 1.1 0.4 0.7
supply
Water supply; sewerage, waste management and 0.4 0.0 0.2
remediation activities
Construction 12.1 0.9 6.5
Wholesale and retail trade repair of motor 14.5 21.4 17.9
vehicles and motorcycles
Transportation and storage 7.3 1.0 4.2
Accommodation and food service activities 1.2 2.1 1.7
Information and communication 0.9 2.3 1.6
Financial and insurance activities 2.8 2.8 2.8
Real estate activities 0.3 0.5 0.4
Professional, scientific and technical activities 1.5 1.2 1.3
Administrative and support service 4.9 2.0 3.5
Public administration and defense; compulsory 5.1 3.1 4.1
social security
Education 6.6 13.0 9.8
Human health and social work activities 3.2 5.0 4.1
Arts, entertainment and recreation 0.4 0.1 0.2
Other service activities 1.2 3.6 2.4
Activities of households as employers 0.1 0.7 0.4
undifferentiated goods and services-producing
act
Activities of extraterritorial organizations and 0.0 0.1 0.0
bodies
Not elsewhere classified 3.3 11.2 7.2
All activities 100.0 100.0 100.0
"""


def test_eswatini_stub_and_base_line():
    """The column stub merged into the first data row, and the base line that
    must NOT be collected.

    NOTE ON SCOPE, because the name used to overclaim: this replays composed
    TEXT, so it does not exercise the word-position reader at all -- the
    lower-case continuation rule lives in `_word_lines` and is covered by
    `test_morocco_fragment_assignment` against real coordinates. What this
    proves is the rest of the Table 4.6 path: the stub is stripped, the
    employment LEVEL above the table is not collected, and the shares land on
    the right sex.
    """
    from indicators.labour.parsers import eswatini_labour as E
    df = finish(run_layout(E, [ESWATINI_PAGE], keep="ILFS2023 T4.6"), "Eswatini")
    ind = df[df.topic == "industry"]

    check("SZ everything is a share", set(ind.measure), {"share"})
    check("SZ classification", set(ind.classification), {"National"})
    cats = set(ind.characteristic)
    check("SZ electricity present",
          any(c.startswith("Electricity, gas, steam and air conditioning")
              for c in cats), True)
    check("SZ water supply not prefixed",
          any(c.startswith("Water supply") for c in cats), True)
    check("SZ manufacturing male",
          pick(ind, "industry", characteristic="Manufacturing", sex="male"), 14.5)
    check("SZ manufacturing both",
          pick(ind, "industry", characteristic="Manufacturing", sex="total"), 16.6)
    # The base line is a COUNT and belongs to `unemployment`; its space
    # thousands make it six numbers against three columns, so it self-skips.
    check("SZ base line excluded",
          "Employed population" in cats, False)
    check("SZ no counts collected", set(ind.unit), {"percent"})


# ---------------------------------------------------------------------------
# Tunisia: the HTML engine
# ---------------------------------------------------------------------------
#
# VERBATIM markup of the sector table on ins.tn/statistiques/152, including the
# six furniture rows INS renders inside the table itself and the "--" cells.
TUNISIA_TABLE = """<html><body>
<h3>Répartition de la population active occupée selon le secteur d'activité</h3>
<table id="tblEmployee-0" class="table"><tbody>
<tr class="hide"><td>NoFilter</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr class="hide"><td>Unité : Nombre</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr class="hide"><td>Source : Institut National de la Statistique</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr class="hide"><td>Répartition de la population active occupée selon le secteur d'activité</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
</tbody><thead class="thead-dark"><tr><th scope="col"> </th><th scope="col">première-trimestre 2024</th><th scope="col">deuxième-trimestre 2024</th><th scope="col">troisième-trimestre 2024</th><th scope="col">première-trimestre 2025</th><th scope="col">deuxième-trimestre 2025</th><th scope="col">troisième-trimestre 2025</th><th scope="col">quatrième-trimestre 2025</th><th scope="col">première-trimestre 2026</th><th scope="col">deuxième-trimestre 2026</th></tr></thead><tbody>
<tr><th>Répartition de la population active occupée selon le secteur d'activité</th><td>3476.0</td><td>3484.0</td><td>3512.0</td><td>3568.9</td><td>3609.0</td><td>3605.6</td><td>3609.8</td><td>3626.3</td><td>3568.1</td></tr>
<tr><th>Agriculture et pêche</th><td>533.0</td><td>557.5</td><td>450.3</td><td>499.6</td><td>505.3</td><td>511.8</td><td>534.3</td><td>569.7</td><td>581.6</td></tr>
<tr><th>Industries manufacturières</th><td>656.0</td><td>613.3</td><td>656.5</td><td>713.9</td><td>721.8</td><td>690.5</td><td>680.8</td><td>688.2</td><td>730.3</td></tr>
<tr><th>Industries  non manufacturières</th><td>454.3</td><td>414.6</td><td>514.9</td><td>428.2</td><td>469.2</td><td>474.1</td><td>467.5</td><td>444.9</td><td>477.4</td></tr>
<tr><th>Services</th><td>1828.4</td><td>1895.5</td><td>1887.5</td><td>1927.2</td><td>1912.8</td><td>1927.7</td><td>1925.2</td><td>1920.0</td><td>1778.8</td></tr>
<tr><th>Non déclarés</th><td>4.2</td><td>3.5</td><td>2.8</td><td>--</td><td>--</td><td>--</td><td>1.9</td><td>3.5</td><td>--</td></tr>
</tbody></table></body></html>"""


def test_tunisia_html():
    """The caption is above the table, the page furniture arrives as rows,
    the missing cells are "--", and the columns are French ordinal quarters."""
    from indicators.labour.parsers import tunisia_labour as T
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "tunisia_population_occupee.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(TUNISIA_TABLE)
        df = finish(T.parse(path), "Tunisia")

    # NINE QUARTERS, not three bare years.
    check("TN periods", sorted(set(df.period)),
          ["2024-Q1", "2024-Q2", "2024-Q3", "2025-Q1", "2025-Q2", "2025-Q3",
           "2025-Q4", "2026-Q1", "2026-Q2"])
    check("TN topic", set(df.topic), {"industry"})
    check("TN classification", set(df.classification), {"National"})
    check("TN unit", set(df.unit), {"thousand_persons"})

    # 6 rows x 9 quarters, less the four suppressed "Non déclarés" cells.
    check("TN rows", len(df), 50)
    check("TN total 2026-Q2",
          pick(df, "industry", characteristic="Total", period="2026-Q2"), 3568.1)
    check("TN agriculture 2026-Q2",
          pick(df, "industry", characteristic="Agriculture et pêche",
               period="2026-Q2"), 581.6)
    check("TN services 2024-Q1",
          pick(df, "industry", characteristic="Services", period="2024-Q1"), 1828.4)

    # THE TOTAL ROW IS LABELLED WITH THE TABLE'S OWN TITLE and is relabelled,
    # not dropped -- it is a real published figure.
    check("TN total relabelled", "Total" in set(df.characteristic), True)
    check("TN title not a category",
          any("Répartition" in str(c) for c in df.characteristic), False)

    # PAGE FURNITURE arrives as table rows and must be skipped for HAVING NO
    # VALUE rather than by being named.
    for junk in ("NoFilter", "Unité : Nombre",
                 "Source : Institut National de la Statistique"):
        check(f"TN furniture {junk!r} skipped", junk in set(df.characteristic), False)

    # "--" IS A MISSING CELL, NEVER A ZERO.
    nd = df[df.characteristic == "Non déclarés"]
    check("TN suppressed quarters absent", sorted(set(nd.period)),
          ["2024-Q1", "2024-Q2", "2024-Q3", "2025-Q4", "2026-Q1"])
    check("TN no zero invented", len(df[df.value == 0.0]), 0)


# ---------------------------------------------------------------------------
# the guards
# ---------------------------------------------------------------------------

def test_expect_rows_guard_fires():
    """`expect_rows` is the only thing standing between a scanned table and
    silently shipping a fraction of it."""
    from indicators.labour.parsers import burkina_faso_labour as B
    short = "\n".join(BURKINA_PAGE15.splitlines()[:4] +
                      ["Figure 5: Taux de pluriactivité selon le milieu de résidence"])
    try:
        run_layout(B, [short])          # no scan_expect override
        FAILURES.append("row_scan accepted 3 categories where 16 are expected")
    except ValueError as e:
        if "expect" not in str(e).lower():
            FAILURES.append(f"row_scan raised the wrong error: {e}")


def test_validator_rejects_garbage():
    """The schema guardrails must actually fire."""
    from indicators.labour.parsers import burkina_faso_labour as B
    df = finish(run_layout(B, [BURKINA_PAGE15]), "Burkina Faso")

    # A share outside [0, 100].
    bad = df.copy()
    bad.loc[bad.index[0], "value"] = 4200.0
    try:
        schema.validate_labour(bad)
        FAILURES.append("validator accepted a share of 4200%")
    except Exception:
        pass

    # A malformed period.
    bad2 = df.copy()
    bad2["period"] = "2023-13"
    try:
        schema.validate_labour(bad2)
        FAILURES.append("validator accepted period '2023-13'")
    except Exception:
        pass

    # An unknown topic.
    bad3 = df.copy()
    bad3.loc[bad3.index[0], "topic"] = "employment_vibes"
    try:
        schema.validate_labour(bad3)
        FAILURES.append("validator accepted an unknown topic")
    except Exception:
        pass

    # A CATEGORY TOPIC WITH NO SCHEME. This is the one guard unique to this
    # indicator: an industry label is not comparable across countries without
    # the classification that produced it.
    bad4 = df.copy()
    bad4["classification"] = "Not applicable"
    try:
        schema.validate_labour(bad4)
        FAILURES.append("validator accepted industry rows with no classification")
    except Exception:
        pass


def test_no_silent_undated_output():
    """A layout with neither a fixed period nor a matching pattern must raise
    rather than dating the series to whatever year it can find -- these reports
    routinely carry three."""
    from indicators.labour.parsers import burkina_faso_labour as B
    cfg = copy.deepcopy(B.LAYOUT)
    cfg.pop("period", None)
    cfg.pop("period_patterns", None)
    orig = P._pages
    P._pages = lambda *_a, **_k: [BURKINA_PAGE15]
    try:
        P.make_parser(cfg)("<replay>")
        FAILURES.append("parser dated an undatable report instead of raising")
    except ValueError:
        pass
    finally:
        P._pages = orig


# ---------------------------------------------------------------------------
# Algeria -- adjacent counts with French space thousands
# ---------------------------------------------------------------------------
def test_algeria_space_thousands_split():
    """ONS prints counts side by side with a SPACE as the thousands separator,
    so "964 020 11 090 975 110" has more than one reading. The parser splits
    under the table's own arithmetic (hommes + femmes = total) and must refuse
    a row where no split -- or more than one -- satisfies it. Lines are
    verbatim from the retrospective (MOD June 1989, RGPH 1977)."""
    from indicators.labour.parsers import algeria_labour as A

    # MOD 1989, Agriculture: H F T salariés, then the row % (dropped).
    label, toks = A._split("Agriculture 964 020 11 090 975 110 146 550 15,03")
    check("dz label", label, "Agriculture")
    check("dz MOD split", A._sum_split(toks[:-1], 4, "t"),
          [964020, 11090, 975110, 146550])

    # A lone 4+ digit token is a number on its own (2012 onwards prints
    # "Industrie 1335" without the space in Tableau 1.4).
    check("dz 4-digit token", A._sum_split(["1335", "1663", "2998"], 3, "t"),
          [1335, 1663, 2998])

    # RGPH 1977, the misprinted row: 271 706 + 125 373 != 397 019. There is
    # no consistent split, and the helper must say so rather than pick one.
    _, toks = A._split("Administration et services fournis à la collectivité "
                       "271 706 125 373 397 019 98,6")
    try:
        A._sum_split(toks[:-1], 3, "t")
        FAILURES.append("dz misprint: _sum_split accepted a row that does "
                        "not add up")
    except ValueError:
        pass

    # Letter-spaced and punctuated variants of one label fold together.
    for raw in ("B T P", "B. T. P", "BTP", "B.T.P."):
        check(f"dz label {raw!r}", A._label(raw), "B.T.P")
    check("dz T o t a l", A._label("T o t a l"), "Total")


# ---------------------------------------------------------------------------
# Angola -- a scrambled published column, and columns that do not sum to 100
# ---------------------------------------------------------------------------
def _angola_book(cols: dict) -> str:
    """A 'Taxa de emprego' sheet in INE's layout; `cols` maps (year, label)
    to the eleven sector values, VERBATIM from the 13th-ICLS workbook."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Taxa de emprego"
    keys = list(cols)
    ws.append(["Taxa de emprego, segundo os trimestres - IEA"])
    ws.append([None] + [k[0] for k in keys])
    ws.append([None] + [k[1] for k in keys])
    ws.append(["Sector de actividade económica"] + [None] * len(keys))
    labels = ["Agricultura, produção animal, caça, floresta e pesca",
              "Indústria, Energia e água", "Construção", "Comércio",
              "Transportes", "Actividades financeiras", "Administração",
              "Educação", "Saúde", "Artes", "Não declarado"]
    for i, lab in enumerate(labels):
        ws.append([lab] + [cols[k][i] for k in keys])
    ws.append(["Fonte: INE"])
    path = os.path.join(tempfile.mkdtemp(), "2.QUADROS_ANTIGA.xlsx")
    wb.save(path)
    return path


def test_angola_scrambled_and_off_sum_columns():
    """INE's 2020 'Anual' sector column sums to 100 but its values sit against
    the wrong labels (Agricultura 1,33); it must be dropped, and must RAISE
    once INE corrects it. 2024 I trim sums to 104,57 as published and is kept;
    any other column off 100 must raise."""
    from indicators.labour.parsers import angola_labour as A
    q1_2020 = [58.31, 2.98, 2.17, 16.23, 4.40, 0.62, 7.30, 3.46, 0.92,
               3.62, 0]
    anual_2020 = [1.33, 1.44, 4.10, 2.52, 0.69, 19.30, 55.75, 5.49, 3.57,
                  5.81, 0]
    q1_2024 = [49.67, 4.35, 3.16, 23.64, 5.88, 0.53, 7.98, 3.23, 1.22,
               4.90, 0]
    spec = [("Sector de actividade", "industry", "National")]
    path = _angola_book({(2020, "I trim"): q1_2020,
                         (2020, "Anual"): anual_2020,
                         (2024, "I trim"): q1_2024})
    rows = A._shares(path, spec, A.SURVEY_OLD, "t")
    check("ao periods", sorted({r["period"] for r in rows}),
          ["2020-Q1", "2024-Q1"])
    check("ao 2024-Q1 kept as printed",
          next(r["value"] for r in rows if r["period"] == "2024-Q1"), 49.67)

    # INE fixes the annual column -> the exclusion must announce itself.
    fixed = _angola_book({(2020, "Anual"): q1_2020})
    try:
        A._shares(fixed, spec, A.SURVEY_OLD, "t")
        FAILURES.append("ao: a corrected 2020 Anual column was silently "
                        "dropped")
    except ValueError:
        pass

    # A column off 100 that is NOT pinned must raise.
    bad = _angola_book({(2021, "I trim"): q1_2024})
    try:
        A._shares(bad, spec, A.SURVEY_OLD, "t")
        FAILURES.append("ao: an unpinned column summing to 104,57 passed")
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Gambia -- a category label longer than the engine's default pattern allows
# ---------------------------------------------------------------------------
def test_gambia_long_label_is_read():
    """GBoS's ISIC section T, rejoined from its two printed lines, is 120
    characters. The engine's default label pattern stops at 80, so the row did
    not fail -- it silently vanished, and Table 4.1 shipped 21 of its 22 rows
    until expect_rows caught it. The layout's own pattern must read it, and
    the small-sample "*" must start a number rather than end a label.
    Lines VERBATIM (as rebuilt) from the GLFS 2026 and 2022-23 reports."""
    from indicators.labour.parsers import gambia_labour as G
    long_line = ("Activities of households as employers; undifferentiated goods- "
                 "and services-producing activities of households for own-use "
                 "1.3 1.6")
    m = re.match(G._LONG_LABEL["label"], long_line)
    check("gm long label", m and m.group(1),
          "Activities of households as employers; undifferentiated goods- and "
          "services-producing activities of households for own-use")
    default = r"^([A-Za-zÀ-ſ][^\d]{2,80}?)\s+(?=[\d(-])"
    check("gm default pattern would drop it",
          re.match(default, long_line) is None, True)

    m = re.match(G._STAR_LABEL["label"], "Electricity, gas, steam and air con "
                 "*433 *822 1,254 0.2")
    check("gm star label", m and m.group(1),
          "Electricity, gas, steam and air con")
    for t in G.LAYOUT_2026["tables"] + G.LAYOUT_2018["tables"][:2]:
        check(f"gm {t['series_code']} words mode",
              "label" in t.get("row_scan", {}) or t["topic"] == "occupation",
              True)


# ---------------------------------------------------------------------------
# Lesotho -- ICSE-18-A group headings that must not become label fragments
# ---------------------------------------------------------------------------
def test_lesotho_icse18_headings_are_barriers():
    """BOS prints ICSE-18-A's five group headings on lines of their own. Read
    by geometry they were folded into the category BELOW -- including
    "Dependent contractors Dependent contractors Employees", a heading glued
    to the wrong group, well-formed and wrong. The layout's barrier must stop
    EVERY heading line and NO data row. Lines VERBATIM from LFS 2024 T4.23."""
    from indicators.labour.parsers import lesotho_labour as L
    rx = re.compile(L.LAYOUT_2024["barrier_pattern"])
    for heading in ("Employers", "Independent workers without employees",
                    "Dependent contractors", "Employees",
                    "Contributing family workers"):
        check(f"ls heading {heading!r} is a barrier", bool(rx.search(heading)), True)
    for data in ("Dependent contractors 6.2 4.5 5.4",
                 "Contributing family workers 0.8 0.8 0.8",
                 "Permanent employees 26.5 28.5 27.4",
                 "Employers in corporations 0.3 0.1 0.3"):
        check(f"ls data row {data!r} is not", bool(rx.search(data)), False)


# ---------------------------------------------------------------------------
# Liberia -- labels printed BELOW their numbers
# ---------------------------------------------------------------------------
def test_liberia_label_below_numbers():
    """LISGIS Table 5.4 prints each production-unit label on the line UNDER
    its figures. Word geometry shifted every label down one row and paired
    "Informal sector" with the HOUSEHOLD figures. The table is read from the
    text layer, numbers-then-label, and must add up. Lines VERBATIM from the
    LFS 2016-17 report as `extract_text` renders them."""
    from indicators.labour.parsers import liberia_labour as L
    page = "\n".join([
        "Table 5.4: Distribution of classification of production units",
        "Number Per cent", "Classification of production units",
        "182,144 33.8", "Formal sector", "231,092 42.9", "Informal sector",
        "125,666 23.3", "Household", "538,902 100.0", "Total"])

    class _Pg:
        def extract_text(self):
            return page

    class _Pdf:
        pages = [_Pg()]
        def __enter__(self): return self
        def __exit__(self, *a): return False

    orig = L.pdfplumber.open
    L.pdfplumber.open = lambda path: _Pdf()
    try:
        rows = L._table_5_4("stub.pdf")
    finally:
        L.pdfplumber.open = orig
    got = {(r["characteristic"], r["measure"]): r["value"] for r in rows}
    check("lr informal sector count", got.get(("Informal sector", "count")), 231092.0)
    check("lr household count", got.get(("Household", "count")), 125666.0)
    check("lr no duplicate Total", ("Total", "count") in got, False)


# --- Mali: a national row that is a copy of the rural row -----------------
# Tab4.5 of INSTAT's EMOP 2023 workbook, VERBATIM cell values (label column B,
# as in the file). Its "Ensemble" row repeats "Rural" digit for digit.
_MALI_2023_TAB45 = [
    (None, "Tableau 4.5: Répartition de la population en emplois par région, milieu, sexe, niveau d’instruction selon le secteur d’activité (%)", None, None, None, None, None),
    (None, "Caractéristiques sociodémographiques", "Primaire", "Industrie", "Commerce", "Service", "Total"),
    (None, "Région", None, None, None, None, None),
    (None, "Kayes", 71.92994039983425, 13.290281520261873, 9.580545995880875, 5.199232084024002, 100.000000000001),
    (None, "Milieu", None, None, None, None, None),
    (None, "Urbain", 9.962776248715684, 18.926126351507808, 39.45462529732068, 31.656472102456135, 100.00000000000031),
    (None, "Rural", 71.7390610082031, 9.900236034229186, 12.330060731797, 6.030642225770498, 99.99999999999977),
    (None, "Sexe", None, None, None, None, None),
    (None, "Masculin", 59.597733150554824, 12.084210935542956, 14.84399134963437, 13.474064564270394, 100.00000000000254),
    (None, "Féminin", 56.256605458617095, 11.5330256224183, 23.451263808066404, 8.759105110899304, 100.0000000000011),
    (None, "Ensemble", 71.7390610082031, 9.900236034229186, 12.330060731797, 6.030642225770498, 99.99999999999977),
    (None, "Source : EMOP 2023, passage 2 (Avril-juin)", None, None, None, None, None),
]


def _mali_sheet(rows, title="Tab4.5"):
    import openpyxl
    ws = openpyxl.Workbook().active
    ws.title = title
    for r in rows:
        ws.append(list(r))
    return ws


def test_mali_copied_national_row():
    """INSTAT's 2023 Tab4.5 prints a national row that is the Rural row again
    (71,74 primaire, outside the 59,6 / 56,26 male-female range). It is
    dropped by name and RE-CHECKED; a copy nobody has listed must raise; and
    the formula "Total" column (100.00000000000254) is never emitted."""
    from indicators.labour.parsers import mali_labour as M
    got = M._read_sheet(_mali_sheet(_MALI_2023_TAB45), "2023", "ref")
    nat = [r for r in got if r["geography"] == "Total country"
           and r["locality"] == "all" and r["sex"] == "total"]
    check("ml copied Ensemble dropped", nat, [])
    check("ml rural kept", round(next(r["value"] for r in got
          if r["locality_label"] == "Rural" and r["characteristic"] == "Primaire"), 2), 71.74)
    check("ml no formula Total", any(r["characteristic"] == "Total" for r in got), False)

    # The same copy in a year nobody listed: the range guard must stop it.
    try:
        M._read_sheet(_mali_sheet(_MALI_2023_TAB45), "2099", "ref")
        FAILURES.append("ml range guard did not fire on an unlisted copy")
    except ValueError as e:
        check("ml range guard names Ensemble", "outside Masculin" in str(e), True)

    # If INSTAT corrects the row, the drop must be noticed, not kept silently.
    fixed = [r if r[1] != "Ensemble" else
             (None, "Ensemble", 58.0, 11.9, 18.9, 11.2, 100.0)
             for r in _MALI_2023_TAB45]
    try:
        M._read_sheet(_mali_sheet(fixed), "2023", "ref")
        FAILURES.append("ml correction by INSTAT went unnoticed")
    except ValueError as e:
        check("ml correction noticed", "no longer copies" in str(e), True)


# --- Chad: a wrapped row whose values are split across the wrap -----------
# ECOSIT4 Tableau 7.08, lines VERBATIM as pdfplumber renders page 195.
CHAD_T708 = """Tableau 7.08 : Caractéristiques des emplois principaux par branche institutionnelle
Répartition des
Pourcentag
emplois
e de Années
Pourcent femmes d'études
Branche Institutionnelle Effectif age (%) (%) réussies
Administration 122 625 2,2 14,1 9,3
Entreprise publique ou parapublique/organisme
0,5 20,6
international 27 609 10,4
Entreprise privée 5 471 217 96,4 52,2 2,2
Entreprise associative 22 397 0,4 26,8 7,2
Ménage comme employeur de personnel
0,5 55,1
domestique 30 827 2,1
Ensemble 5 674 675 100,0 51,1 9,0
L’analyse du tableau 7.09 montre que la durée moyenne hebdomadaire de travail est de 33"""


def test_chad_split_wrapped_row():
    """Two labels wrap, and INSEED splits the ROW'S VALUES across the wrap:
    the share and "% femmes" on the middle line, the count and years of study
    on the last. Read naively, "international" gets 10,4 (years of study) as
    its share. The five units must also sum to the Ensemble exactly."""
    from indicators.labour.parsers import chad_labour as T

    class _Pg:
        def extract_text(self):
            return CHAD_T708

    class _Pdf:
        pages = [_Pg()]
        def __enter__(self): return self
        def __exit__(self, *a): return False

    orig = T.pdfplumber.open
    T.pdfplumber.open = lambda path: _Pdf()
    try:
        rows = T._table_7_08("stub.pdf")
    finally:
        T.pdfplumber.open = orig
    got = {(r["characteristic"], r["measure"]): r["value"] for r in rows}
    pub = "Entreprise publique ou parapublique/organisme international"
    check("td wrapped share", got.get((pub, "share")), 0.5)
    check("td wrapped count", got.get((pub, "count")), 27609.0)
    check("td household share",
          got.get(("Ménage comme employeur de personnel domestique", "share")), 0.5)
    check("td private count", got.get(("Entreprise privée", "count")), 5471217.0)
    check("td total", got.get(("Total", "count")), 5674675.0)
    check("td no years-of-study value", 10.4 in got.values(), False)


# --- Merge-on-write must not read a published "NA" as missing --------------
def test_merge_keeps_literal_na_category():
    """INE São Tomé publishes a CAE-STP column literally labelled "NA". The
    merge used to re-read the prior output with pandas' default NA strings,
    so the prior "NA" row came back with a blank key, matched nothing, and was
    written again beside the fresh one -- a duplicate per run. Two identical
    runs must leave the file unchanged."""
    import core.run as R
    from indicators.labour.pipeline import CONFIG
    R.configure(CONFIG)
    rows = []
    for lab, v in (("NA", 4.9), ("N/A", 1.0), ("None", 2.0), ("A", 38.6)):
        rows.append(C.row(topic="industry", characteristic=lab,
                          classification="National", value=v, survey="s",
                          period="2012", frequency="ad_hoc", measure="share",
                          unit="percent", geography="Lobata"))
    new = pd.DataFrame(rows)
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "x_labour.csv")
        new.to_csv(out, index=False)
        merged = R._merge_with_existing(new.copy(), out, "Replay")
    check("merge NA no growth", len(merged), 4)
    check("merge NA labels kept", sorted(map(str, merged["characteristic"])),
          ["A", "N/A", "NA", "None"])


def main() -> int:
    for fn in (test_numbers, test_periods, test_row_refuses_category_without_scheme,
               test_morocco_fragment_assignment, test_eswatini_fragment_assignment,
               test_morocco_label_accepts_a_lost_leading_zero,
               test_morocco_end_to_end,
               test_burkina_chart_data_labels, test_zambia_wrapped_labels_and_dash,
               test_eswatini_stub_and_base_line, test_tunisia_html,
               test_expect_rows_guard_fires, test_validator_rejects_garbage,
               test_no_silent_undated_output,
               test_algeria_space_thousands_split,
               test_angola_scrambled_and_off_sum_columns,
               test_gambia_long_label_is_read,
               test_lesotho_icse18_headings_are_barriers,
               test_liberia_label_below_numbers,
               test_mali_copied_national_row,
               test_chad_split_wrapped_row,
               test_merge_keeps_literal_na_category):
        try:
            fn()
        except Exception as e:            # a crash is a failure too
            FAILURES.append(f"{fn.__name__} raised {type(e).__name__}: {e}")
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("all offline checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
