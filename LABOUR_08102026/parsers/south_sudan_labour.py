"""South Sudan — NBS (then SSCCSE), "Southern Sudan Counts: Tables from the 5th
Sudan Population and Housing Census, 2008" (2010), chapter 5 "Economic
Activity".

A CENSUS (the long-form questionnaire), so the universe is the resident
population. Six tables, each a pair of bases:

* Tables 5-3 / 5-4  main occupational group (10 groups)  -> occupation
* Tables 5-5 / 5-6  industry aggregates (9 groups)       -> industry
* Tables 5-7 / 5-8  employment status (5 categories)     -> employment_status

the first of each pair on persons aged 10 and above, the second on 15 and
above, by sex, urban/rural, age group, educational attainment and the ten
states. Each ROW is a population group whose values are that group's
distribution across the categories (every row ends "100"), so every row is a
composition in this schema's sense, with the group carried in sex / locality /
age_group / education / geography.

THE UNIVERSE IS NOT "THE EMPLOYED", and it travels in `survey`. NBS defines it
as the population "who worked previously" -- in the key findings and in Table
5-5's caption "in work or who worked previously": persons currently working
PLUS persons not working now whose last job is described. It was collected
anyway, deliberately: the current workers are the overwhelming majority (the
census's own 15+ participation rate is 74% and unemployment 12%), the
categories are exactly those of employment composition, and nothing else of
this kind exists for South Sudan. But a user comparing these shares with a
currently-employed distribution from another country must see the difference,
so every row's `survey` names it.

CLASSIFICATIONS. Industry was coded to ISIC Rev.4 two-digit codes and then
AGGREGATED by NBS into nine groups of its own making (Appendix A: "01-09:
Agriculture, forestry, fishing and mining", "58-82, 90-96, 99: Other service
and professional/technical activities" ...). The nine groups are not ISIC
categories, so they are National -- the appendix mapping is recorded here
rather than claimed on every row. The occupation groups carry ISCO-08's major
group names, but ISCO is named nowhere in the volume -> National (the Somalia
and Nigeria call). Status -> National.

THE PAGES ARE LANDSCAPE TABLES PRINTED SIDEWAYS, TWO TO A PAGE. Text runs
vertically; one page holds the end of one table part and the start of the
next, and a part that does not finish continues at the low-x end of the
following page (Table 5-5's household-head and state rows sit on p.85 beside
the start of 5-6). pdfplumber's line reading reverses every token on these
pages ("6.1" for 1.6) -- the trap that was flagged. So the chapter is read
from PyMuPDF WORD positions: a table line is a constant x (constant y on the
two portrait pages, 87-88, where 5-7 and 5-8 are stacked), and a word's
position across the line says whether it is a section heading, a row label
or a value. Headings and labels wrap, in ways no sequential reader handles:
see `_rows`. Every row must carry exactly one value per category plus a
closing 100, its categories must sum to 100 (+-0.35), and every table must
yield all 10 states, 5 education groups, 2 localities and 2 sexes -- so a
mis-ordered or mis-assigned line cannot pass silently.

NOT COLLECTED: the household-head sections of every table (sex, education
and occupational status OF THE HEAD -- a characteristic of the household, not
of the worker, and no column of this schema holds it); Tables 5-1/5-2 (rates,
`unemployment`'s territory) and 5-9/5-10 (reasons for not seeking work).

Period 2008 (census night 22 April 2008).

CROSS-CHECK: the key findings' "63% of those aged 15 and above ... in
agriculture, animal husbandry or fishery" = Table 5-6 63.3; "13% paid
employees, 37% own account, 42% unpaid family workers" = Table 5-8 13.0 /
36.9 / 42.7; "24% employed in public administration" (secondary or higher,
15+) = Table 5-6 24.2; Table 5-3 skilled agricultural (10+) 59.8; Table 5-7
urban paid employees 35.2; Western Equatoria agriculture 78.1 (5-5, 10+) and
77.2 (5-6, 15+).
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd

from . import _common as C

_SURVEY = ("5th Sudan Population and Housing Census 2008 (Southern Sudan) -- "
           "persons working or who worked previously")

_OCC = ["Managers", "Professionals", "Technicians and associate professionals",
        "Clerical support workers", "Service and sales workers",
        "Skilled agricultural, forestry and fishery",
        "Craft and other trades workers",
        "Plant/machine operators, and assemblers", "Elementary occupations",
        "Armed forces occupations"]
_IND = ["Agriculture, forestry, fishing and mining", "Manufacturing",
        "Construction and utilities supply",
        "Wholesale, retail trade and repair of motor vehicles",
        "Accommodation, food service, transportation and storage",
        "Other service and professional/technical activities",
        "Public administration and defense; compulsory social security",
        "Education, health and social work",
        "Household production for own use/Domestic personnel"]
_STA = ["Paid Employee", "Employer", "Own Account Worker",
        "Unpaid Family Worker", "Unpaid Working for Others"]

# table -> (topic, categories, working-age base)
_TABLES = {
    "5-3": ("occupation", _OCC, "10+"), "5-4": ("occupation", _OCC, "15+"),
    "5-5": ("industry", _IND, "10+"), "5-6": ("industry", _IND, "15+"),
    "5-7": ("employment_status", _STA, "10+"),
    "5-8": ("employment_status", _STA, "15+"),
}
# Row-group headings, longest first so "Sex of household head" is not "Sex".
_SECTIONS = [
    ("Educational attainment of household head", None),
    ("Occupational status of household head", None),
    ("Sex of household head", None),
    ("Educational attainment", "education"),
    ("Urban/rural", "locality"),
    ("Age group", "age_group"),
    ("State", "geography"),
    ("Sex", "sex"),
]
_STATES = {"Upper Nile", "Jonglei", "Unity", "Warrap",
           "Northern Bahr El Ghazal", "Western Bahr El Ghazal", "Lakes",
           "Western Equatoria", "Central Equatoria", "Eastern Equatoria"}
_HEADINGS = dict(_SECTIONS)
_STARTERS = {h.split()[0] for h in _HEADINGS}
_NUM = re.compile(r"^\d*\.?\d+$")
_CAPTION = re.compile(r"^Table (5-\d+):")


def _lines(path: str):
    """Chapter 5 as (page, line position, [(word, is_heading_column)]) in
    reading order, for both page orientations.

    Most pages are LANDSCAPE TABLES PRINTED SIDEWAYS (text direction (0,-1)):
    a line of the table is a constant x, and reading across it runs from high
    y to low y. The section-heading column sits at y0 > 722 and the row labels
    just below it. Pages 87-88 are PORTRAIT: a line is a constant y, headings
    at x0 < (page left edge + 55). A landscape table starts at the high-x end of one page and
    its tail continues at the low-x end of the next, so sorting each page by
    line position and taking pages in order IS the reading order.
    """
    with fitz.open(path) as doc:
        first = next(i for i, p in enumerate(doc)
                     if re.search(r"^Table 5-3: Main occupational type",
                                  p.get_text(), re.M))
        for pno in range(first, first + 8):
            page = doc[pno]
            dirs = [tuple(round(v) for v in ln["dir"])
                    for b in page.get_text("dict")["blocks"]
                    for ln in b.get("lines", [])]
            sideways = dirs.count((0, -1)) > len(dirs) / 2
            words = []
            # Portrait pages shift their margin page to page (headings at x0
            # 82 on p.87, 69 on p.88; labels 63 points to the right of them),
            # so the heading column is measured from the page's own left edge.
            left = min(wd[0] for wd in page.get_text("words") if wd[1] <= 778)
            for x0, y0, x1, y1, w, *_ in page.get_text("words"):
                # The printed page number sits in the bottom margin (y0 ~784)
                # and, on a sideways page, on the same x as a table row.
                if y0 > 778:
                    continue
                w = w.replace("ﬁ", "fi").replace("ﬂ", "fl")
                if sideways:
                    words.append(((x0 + x1) / 2, -(y0 + y1) / 2, w, y0 > 722))
                else:
                    words.append(((y0 + y1) / 2, x0, w, x0 < left + 55))
            words.sort()
            line, pos = [], None
            for lpos, col, w, head in words:
                if pos is not None and lpos - pos > 2.5:
                    yield pno, pos, [(w_, h_) for _, w_, h_ in sorted(line)]
                    line = []
                if not line:
                    pos = lpos
                line.append((col, w, head))
            if line:
                yield pno, pos, [(w_, h_) for _, w_, h_ in sorted(line)]


def _rows(path: str):
    """(table, heading_words, label_words, values) per data row.

    Two wraps defeat a sequential reader. A HEADING ("Sex of" / "household" /
    "head") runs down beside the rows it heads, so its fragments interleave
    with them: fragments within 12 points of the previous one extend the same
    heading, a mutable list resolved only after the chapter is read. A LABEL
    ("Secondary or" / "higher") wraps over two lines with its numbers set on
    EITHER one, so a fragment line is given to the NEAREST numeric row of the
    same table part (row pitch ~11.3 points, wrap pitch ~9.2), never simply
    to the next.
    """
    rows, frags = [], []     # rows: [table, heading, seg, page, pos, parts, vals]
    table, in_header, seg = None, False, 0
    heading, head_at, head_page = None, None, None
    for pno, pos, words in _lines(path):
        text = " ".join(w for w, _ in words)
        m = _CAPTION.match(text)
        if m:
            table = m.group(1) if m.group(1) in _TABLES else None
            in_header, heading, seg = True, None, seg + 1
            continue
        if text.startswith("Source:"):
            seg += 1
            continue
        if table is None:
            continue
        n_cols = len(_TABLES[table][1]) + 1
        nums = [w for w, _ in words if _NUM.match(w)]
        if in_header:
            if len(nums) != n_cols:
                continue
            in_header = False
        label = []
        for w, is_head in words:
            if _NUM.match(w):
                continue
            if is_head:
                # A short section ("Sex of household head": two rows) puts
                # the next heading within 12 points of its last fragment, so a
                # complete heading followed by a heading's first word starts
                # anew ("Sex" + "of" continues; "... head" + "Educational" not).
                complete = heading is not None and " ".join(heading) in _HEADINGS
                if (heading is not None and head_page == pno
                        and pos - head_at <= 12
                        and not (complete and w in _STARTERS)):
                    heading.append(w)
                else:
                    heading = [w]
                head_at, head_page = pos, pno
            else:
                label.append(w)
        if not nums:
            if label:
                frags.append((seg, pno, pos, label))
            continue
        if len(nums) != n_cols:
            raise ValueError(f"SSD census T{table}: {len(nums)} values on line "
                             f"{text!r}, expected {n_cols}")
        if heading is None:
            raise ValueError(f"SSD census T{table}: row {label} has no heading")
        rows.append([table, heading, seg, pno, pos, [(pos, label)],
                     [float(v) for v in nums]])
    for seg_, pno, pos, label in frags:
        cands = [r for r in rows if r[2] == seg_ and r[3] == pno]
        if not cands:
            raise ValueError(f"SSD census: label fragment {label} with no row")
        min(cands, key=lambda r: abs(r[4] - pos))[5].append((pos, label))
    return [(t, h, [w for _, ws in sorted(parts) for w in ws], vals)
            for t, h, _, _, _, parts, vals in rows]




def parse(path: str) -> pd.DataFrame:
    out = []
    for table, heading_words, label_words, vals in list(_rows(path)):
        topic, cats, base = _TABLES[table]
        heading = " ".join(heading_words)
        if heading not in _HEADINGS:
            raise ValueError(f"SSD census T{table}: unknown section {heading!r}")
        col = _HEADINGS[heading]
        text = " ".join(label_words)
        if vals[-1] != 100 or abs(sum(vals[:-1]) - 100) > 0.35:
            raise ValueError(f"SSD census T{table} {text!r}: categories sum to "
                             f"{sum(vals[:-1]):.1f}, closing value {vals[-1]}")
        if col is None:                         # household-head sections
            continue
        ctx = {}
        if col == "sex":
            if text != "Southern Sudan":
                ctx["sex"] = C.normalise_sex(text)
        elif col == "locality":
            ctx["locality"] = C.normalise_locality(text)
            ctx["locality_label"] = text
        elif col == "geography":
            if text not in _STATES:
                raise ValueError(f"SSD census T{table}: unknown state {text!r}")
            ctx["geography"] = text
        else:
            ctx[col] = text
        for cat, v in zip(cats, vals[:-1]):
            out.append(C.row(topic=topic, characteristic=cat,
                             classification="National", value=v,
                             survey=_SURVEY, period="2008",
                             reference_period="5th Population and Housing "
                                              "Census, 22 April 2008",
                             frequency="ad_hoc", measure="share",
                             unit="percent", working_age_base=base,
                             series_code=f"SSD Census 2008 T{table}", **ctx))
    df = pd.DataFrame(out)
    # Every table must have yielded its national row, both sexes, both
    # localities, five education groups and all ten states.
    for table in _TABLES:
        sub = df[df.series_code == f"SSD Census 2008 T{table}"]
        groups = sub.drop_duplicates(["sex", "locality", "age_group",
                                      "education", "geography"])
        if (groups.geography != "Total country").sum() != 10 or \
                (groups.education != "Total").sum() != 5 or \
                (groups.locality != "all").sum() != 2 or \
                (groups.sex != "total").sum() != 2:
            raise ValueError(f"SSD census T{table}: incomplete -- "
                             f"{len(groups)} groups read")
    return df
