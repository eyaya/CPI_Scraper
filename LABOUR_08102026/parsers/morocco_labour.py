"""Morocco — HCP "Activité, emploi et chômage", employment composition.

One module per country, read by `pdf_tables_labour.make_parser`. The report is
the one `unemployment` collects (Tableaux 2 and 3 there, Tableau 4 here).

TABLEAU 4 IS FOUR COMPOSITION TABLES STACKED IN ONE. Under a single header --
Indicateurs | Masculin | Féminin | Urbain | Rural | National -- HCP prints a
run of sub-blocks, each its own distribution summing to 100:

    - Structure de l'emploi selon les grands groupes de professions (en %)
    - Structure de l'emploi selon le statut professionnel (en %)
    - Structure de l'emploi selon les secteurs d'emploi (en %)
    - Structure de l'emploi selon les branches d'activité économique (en %)

Each becomes its own table spec, opened by its sub-heading and closed on its
own "Total" row -- the same shape Ethiopia's stacked blocks needed.

THE FIVE COLUMNS ARE TWO DIMENSIONS, NOT ONE. Masculin and Féminin are national
figures by sex; Urbain and Rural are both sexes by place; National is both, for
everyone. So the sex columns carry `sex` and the residence columns carry
`locality`, and neither is allowed to overwrite the other -- reading them as a
flat five-way split would publish urban employment as a third sex.

WHAT IS DELIBERATELY LEFT HERE:

* The blocks by AGE. `age_group` is a COLUMN in this schema, not a topic:
  there is no "employment by age" topic to hang a distribution of the employed
  on, and inventing one to hold a percentage would misdescribe it. (The
  DIPLÔME dimension is no longer left -- see TABLEAU 5 below, which carries it
  in the `education` column.)
* "Population active occupée (en milliers)", "Taux de féminisation" and "Taux
  d'emploi" -- employment levels and rates, which belong to `unemployment`.
TABLEAU 5 IS NOW COLLECTED, and carries the DIPLOMA dimension.
"Structures socio-professionnelles de l'emploi selon le niveau du diplôme, le
sexe et le milieu de résidence" runs over ten pages (27-36) in FIVE POPULATION
BLOCKS -- NATIONAL, URBAIN, RURAL, MASCULIN, FÉMININ -- each repeating three of
Tableau 4's structures with the three diploma levels as its columns.

AN EARLIER NOTE HERE CALLED THIS "a schema question rather than a parsing one",
on the grounds that the five blocks overlap. That was too pessimistic: they map
onto exactly the `sex` x `locality` cells Tableau 4 already uses -- NATIONAL is
sex=total/locality=all, URBAIN is total/urban, MASCULIN is male/all, and so on
-- so they occupy DISTINCT merge keys and nothing is double counted. The
diploma level rides in the `education` column, which the engine forwards from a
column spec exactly as it forwards sex and locality.

WHAT DIFFERS FROM TABLEAU 4, and why each spec is built the way it is:

* THERE IS NO OCCUPATION BREAKDOWN HERE. Tableau 5 carries age, statut
  professionnel, secteurs d'emploi and branches d'activité -- four structures,
  of which three are collectable. The age one is left, as everywhere else.
* THE COLUMN HEADERS WRAP FOUR DIFFERENT WAYS across the ten pages ("Sans
  diplôme Niveau moyen4 Niveau supérieur5", "Sans / diplôme moyen supérieur",
  ...), and two carry FOOTNOTE DIGITS. They are never parsed: the printed
  ORDER is fixed -- Sans diplôme, Niveau moyen, Niveau supérieur -- and is
  declared here, the same way Tableau 4's five columns are.
* "NATIONAL" CANNOT PIN ITS OWN PAGES. The sector rows of EVERY block contain
  "y compris la promotion nationale", so the substring "national" appears on
  pages 29, 31, 33 and 35 as well as 27-28. Pinning the national block on that
  token would pull the urban, rural, male and female figures into the national
  series -- real values in the wrong series. NATIONAL is therefore pinned by
  EXCLUSION of the other four block words; the other four pin cleanly on their
  own.
* THE CAPTIONS WRAP AS IN TABLEAU 4, so `caption_inline` is needed again, and
  each pattern must match two wrappings: "secteurs d'emploi (en %)" on some
  pages and the bare "d'emploi (en %)" on others; "branches d'activité
  économique (en %)" against the bare "d'activité économique (en %)". HCP also
  mixes straight and curly apostrophes between pages, hence `d.emploi` rather
  than a literal quote.

HCP DROPS THE LEADING ZERO on small decimals here (",0", ",1", ",3"). An
earlier note said such rows "would be skipped as short", which was wrong and
comfortingly so: the patterns matched the DIGITS AFTER the comma, so ",1"
parsed as 1.0 at full column width -- a TENFOLD error, invisible to every
downstream check, rather than a missing row. `numbers_in` now restores the lost
zero before reading, and `labour/tests/test_offline.py` pins it.

THE SUB-HEADING SHARES ITS LINE WITH THE FIRST CATEGORY, so each block's
caption is matched on the line that carries "(en %)" and `caption_inline` keeps
what follows it. Matching the heading's FIRST line instead cannot work: the
heading wraps, and a caption pattern is tested against one line at a time, so
"selon les grands" and "groupes de professions" are never both on it.

THE OCCUPATION BLOCK HAS TEN GROUPS, NOT NINE. Two of them wrap around their
own numbers, and the second's label is split across the break:

    Membres des corps legislatifs, elus
    locaux, responsables hierarchiques
    de la fonction publique directeurs et    0,9 0,5 1,3 0,1 0,9
    cadres de direction d'entreprises
    Cadres superieurs et membres des
    professions liberales                    3,4 10,7 7,3 0,8 4,9

Which values belong to which group is settled by GEOMETRY, not by reading: the
"0,9" run sits at y=181 inside the first label's block (167-193) and the "3,4"
run at y=210 inside the second's (205-213). Read carelessly this publishes the
directors' 0,9 under "professions liberales" -- a different and much larger
occupation -- so it is worth restating that the numbers were placed by position
in the page, not by which label reads more plausibly.

NO CLASSIFICATION IS NAMED ANYWHERE IN THE REPORT -- CITP, CITE, nomenclature
and CSP appear nowhere in it. The occupation groups are recognisably ISCO-88
shaped ("Membres des corps législatifs...", "Cadres moyens", "Artisans et
ouvriers qualifiés...") and the branches are HCP's own eight-way grouping, but
saying so would be inference. National, as for Botswana and Tanzania.

FRENCH CONVENTIONS: comma decimals, and stocks "en milliers" -- though no stock
is collected here, every value in these four blocks being a percentage.

METHODOLOGY BREAK, inherited from the descriptor and repeated because it
matters for any series built on this: HCP replaced the Enquête Nationale sur
l'Emploi with the Enquête sur la Main-d'Œuvre (EMO) from Q1 2026, and the two
are not comparable. This layout reads the ANNUAL ENE report.

CROSS-CHECK (2025, Masculin / Féminin / Urbain / Rural / National): salariés
61,1 / 60,6 / 70,9 / 44,6 / 61,0; aides familiales 5,0 / 24,0 / 1,5 / 21,2 /
8,9; agriculture, forêt et pêche 23,8 / 32,1 / 4,5 / 60,5 / 25,5; secteur privé
91,7 / 89,0 / 88,0 / 96,4 / 91,1; "Ouvriers et manœuvres agricoles et de la
pêche" 13,7 / 26,3 / 3,4 / 37,7 / 16,2; and the two wrapped occupation groups,
"Membres des corps législatifs ... cadres de direction d'entreprises" 0,9 / 0,5
/ 1,3 / 0,1 / 0,9 and "Cadres supérieurs et membres des professions libérales"
3,4 / 10,7 / 7,3 / 0,8 / 4,9.
"""
from __future__ import annotations

from .pdf_tables_labour import make_parser


def _pct(**kw) -> dict:
    return {"measure": "share", "unit": "percent", **kw}


# Masculin | Féminin | Urbain | Rural | National, in the printed order.
# The first two are national figures BY SEX; the next two are both sexes BY
# PLACE. Keeping them in separate schema columns is what stops "Urbain" being
# emitted as a sex.
_COLS = [
    _pct(sex="male"),
    _pct(sex="female"),
    _pct(sex="total", locality="urban", locality_label="Urbain"),
    _pct(sex="total", locality="rural", locality_label="Rural"),
    _pct(sex="total"),
]


# HCP's category names run far past the 80 characters the engine allows by
# default -- "Membres des corps législatifs, élus locaux, responsables
# hiérarchiques de la fonction publique directeurs et cadres de direction
# d'entreprises" is 140 -- and they are full of parentheses ("(non compris les
# ouvriers de l'agriculture)", "(y compris la promotion nationale)"), so the
# label ends at the first VALUE rather than at the first digit-or-paren.
#
# THE LOOKAHEAD MUST ACCEPT A LEADING COMMA, and this cost a dropped category
# before it was caught. HCP writes small decimals without their leading zero,
# so Tableau 5 prints "Activités mal désignées ,0 ,1 ,3". Ending the label at
# `(?=\d)` never fires on that line -- the first character after the label is a
# COMMA -- so the row yielded no label and was discarded BEFORE `numbers_in`
# was reached, which is why restoring the lost zero inside `numbers_in` did not
# help. It disappeared from two of the five blocks (URBAIN and MASCULIN
# branches, pages 30 and 34), and `expect_rows` is what caught it.
_LABEL = r"^([A-Za-zÀ-ſ][^\d]{2,220}?)\s+(?=[,\d])"


def _block(caption: str, topic: str, expect: int, code: str, page: str) -> dict:
    return {
        "caption": caption, "topic": topic, "classification": "National",
        "columns": _COLS,
        # The caption is the heading's TAIL, which shares its line with the
        # first category; keep what follows it rather than dropping the line.
        "caption_inline": True,
        # PIN EACH BLOCK TO ITS PAGE. Tableau 4 runs over three pages, captioned
        # "(suite)" and "(fin)"; without this every spec scans the whole report
        # and finds its own headings again in TABLEAU 5's national / urban /
        # rural repeats (three columns, so they skip as short) and in the
        # sous-emploi tables, where two rows DID match with five values each
        # and would have been published as occupation categories.
        "page_contains": ["tableau 4", page],
        # Every one of these blocks ends on its own "Total" row, and the next
        # sub-heading follows immediately -- so close there rather than reading
        # on into the next distribution.
        "end_after": r"^Total\s+[\d,]",
        # NO `dash_placeholder` HERE. Every cell in these four blocks is filled
        # (each data line carries exactly five values), so a dash would mean
        # the layout had drifted -- and without the placeholder such a row
        # falls a column short and fails on `expect_rows` instead of quietly
        # sliding its values one column left.
        "series_code": code,
        "row_scan": {"label": _LABEL, "expect_rows": expect},
    }


LAYOUT = {
    "survey": "Activité, emploi et chômage — résultats annuels",
    "frequency": "annual",
    "working_age_base": "15+",
    # "61,1" and "8 664" -- comma decimals, space thousands.
    "decimal": ",",
    # The labels wrap over two and three lines with their numbers on whichever
    # line is central ("Membres des corps législatifs, élus / locaux,
    # responsables hiérarchiques / de la fonction publique directeurs et 0,9
    # ... / cadres de direction d'entreprises"), which line-based reading
    # truncates.
    "text_mode": "words",
    # The report titles itself "RÉSULTATS ANNUELS 2025", with "Année 2025"
    # beneath it -- taken from the document rather than pinned by hand.
    "period_patterns": [r"RÉSULTATS ANNUELS\s+(20\d{2})", r"Année\s+(20\d{2})"],
    # THE SUB-HEADINGS ARE BARRIERS, NOT LABEL FRAGMENTS. Each block is
    # introduced by a digit-free line sitting directly above its first
    # category, and the word-position reader folded it into that category's
    # label -- putting the heading text inside the characteristic, opening the
    # region one row late, and losing the first category of every block
    # ("Membres des corps législatifs ...", "Administration publique et
    # collectivités locales"). Marking the headings keeps them out of the data.
    "barrier_pattern": r"Structure de l.emploi selon|^Indicateurs\b",
    # EVERY VALUE HERE IS A PERCENTAGE, so a space separates numbers rather
    # than grouping thousands: "Total 100 100 100 100 100" is five values, not
    # 100100100100100. The stocks in this table are "en milliers" and belong to
    # `unemployment`, so nothing collected here needs space-grouping.
    "space_thousands": False,
    "tables": [
        # Each caption is the part of the sub-heading that falls on the line
        # holding the first category, and the counts include each block's own
        # published "Total" row (always 100). Ten occupation groups, six
        # statuses, four sectors, eight branches.
        _block(r"groupes de professions\s*\(en\s*%\)", "occupation", 11,
               "HCP T4-professions", "(suite)"),
        _block(r"^professionnel\s*\(en\s*%\)", "employment_status", 7,
               "HCP T4-statut", "(suite)"),
        _block(r"secteurs d.emploi\s*\(en\s*%\)", "sector", 5,
               "HCP T4-secteurs", "(fin)"),
        _block(r"branches d.activit\S*\s+.conomique\s*\(en\s*%\)", "industry", 9,
               "HCP T4-branches", "(fin)"),
    ],
}


# --------------------------------------------------------------------------
# TABLEAU 5 -- the same structures again, cut by DIPLOMA LEVEL.
#
# Five population blocks x three structures = fifteen specs, generated rather
# than written out: every one differs only in which pages it selects, which
# sex/locality cell it fills, and which caption opens it.
# --------------------------------------------------------------------------

# The printed column order, fixed across all ten pages. Never parsed from the
# headers, which wrap four different ways and carry footnote digits.
_DIPLOMAS = ("Sans diplôme", "Niveau moyen", "Niveau supérieur")

# (block word, the sex/locality cell it fills, extra page_contains, page_excludes)
_T5_BLOCKS = (
    # NATIONAL is pinned by EXCLUSION: "national" also appears in every block's
    # "y compris la promotion nationale" sector row.
    ("NATIONAL", {"sex": "total"}, [],
     ["urbain", "rural", "masculin", "feminin"]),
    ("URBAIN", {"sex": "total", "locality": "urban", "locality_label": "Urbain"},
     ["urbain"], []),
    ("RURAL", {"sex": "total", "locality": "rural", "locality_label": "Rural"},
     ["rural"], []),
    ("MASCULIN", {"sex": "male"}, ["masculin"], []),
    ("FEMININ", {"sex": "female"}, ["feminin"], []),
)

# (caption, topic, expected categories incl. the published Total, tag)
_T5_STRUCTS = (
    (r"^professionnel\s*\(en\s*%\)", "employment_status", 7, "statut"),
    # Matches "secteurs d'emploi (en %)" and the bare "d'emploi (en %)".
    (r"d.emploi\s*\(en\s*%\)", "sector", 5, "secteurs"),
    # Matches "branches d'activité économique (en %)" and the bare tail.
    (r"d.activit\S*\s+.conomique\s*\(en\s*%\)", "industry", 9, "branches"),
)

for _blk, _cut, _want, _not in _T5_BLOCKS:
    for _cap, _topic, _expect, _tag in _T5_STRUCTS:
        LAYOUT["tables"].append({
            "caption": _cap,
            "topic": _topic,
            "classification": "National",
            "caption_inline": True,
            "page_contains": ["tableau 5"] + _want,
            "page_excludes": _not,
            "columns": [{"measure": "share", "unit": "percent",
                         "education": _dip, **_cut} for _dip in _DIPLOMAS],
            "end_after": r"^Total\s+[\d,]",
            "series_code": f"HCP T5-{_blk.lower()}-{_tag}",
            "row_scan": {"label": _LABEL, "expect_rows": _expect},
        })


parse = make_parser(LAYOUT)
