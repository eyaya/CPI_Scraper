"""Nigeria — NBS Nigeria Labour Force Survey (NLFS), Annual Report 2023.

THE ANNUAL STATE REPORT, NOT THE QUARTERLY BULLETIN. `unemployment/` reads the
newest quarterly NLFS release, which carries only the self-employed/employee
split, the agriculture share and the informal RATE. This 308-page report pools
four quarters (October 2022 - November 2023, Q4 2022 to Q3 2023, on the revised
2022 methodology) so that states can be estimated, and it is the one NLFS
publication that prints the composition of employment. Base 15+.

COLLECTED

* Table 8   status in employment by state and sex: Self-Employed / Employees,
            % of the employed (37 states + FCT, no national row).
            -> employment_status, geography = state.
* Table 17  informal employment by state and sex, COUNTS: "Informal
            Employment" and "Informal Employment (excluding agriculture)",
            37 states + FCT + NATIONAL. -> formality.
* Figure 9  employment by the 20 ISIC sections of the main job, % (national).
* Figure 11 employment by the 9 occupation major groups, % (national).

FIGURES 9 AND 11 PASS THE BURKINA FASO TEST, and are read under a strict
shape. NBS prints each category with its value as TEXT data labels, one bar
per line ("Manufacturing 12.7"), so the numbers exist in the file and each is
tied to its own label on its own line -- unlike Senegal's glyph fragments or
Zimbabwe's value-less bars. Two occupation labels wrap AROUND their value
("Skilled agricultural forestry and fishery" / "28.1" / "workers"); the tail
starts lower-case and continues the label above, and the reader then insists
on exactly the nine groups, in the printed order, summing to 99.9.

FIGURE 9'S LABELS ARE TRUNCATED IN THE CHART ("Wholesale and retail trade;
repair of motor…") and are collected VERBATIM, ellipsis included -- the
Somalia precedent. Table 10 prints the full names on page 25, but pairing a
truncated label with a full one is an edit the chart did not make; a reader
can see the truncation.

CLASSIFICATION IS "National", NOT ISIC Rev.4 / ISCO-08. The report names
"the International Standard Industrial Classification (ISIC)" and "the
International Standard Classification of Occupations (ISCO)" in the section
text and Annex 4, but NEVER A REVISION, and this schema's vocabulary is
revisions. The labels are recognisably Rev.4 / ISCO-08 wording; recording
that would be inference -- the same call as Somalia, which names ISIC/ISCO
only without a revision. Status (self-employed / employees) names no ICSE.

NOT COLLECTED

* Table 8's first three columns: the employment-to-population ratio, which is
  `unemployment`'s.
* Table 9 (private / public sector) and Figure 8 -- shares of EMPLOYEES only,
  not of the employed; the Lesotho precedent keeps an employee-universe
  sector split out of a corpus of employed-population distributions.
* Table 10 and Figure 10 -- ROW percentages (sex and urban/rural split WITHIN
  each industry), which this indicator does not collect.
* From the annex tables, the private/public sector EMPLOYEE rows (employees
  universe, as Table 9), "Employees social protection", and every labour-force
  status row (working-age, labour force, unemployed, LU2-LU4, NEET, youth...)
  -- `unemployment`'s territory.

ANNEX 1, TABLES 18-165 (added 2026-10-01): four headline blocks per state --
by sex, by place of residence, by educational level, by age group. Five of
their rows describe the composition of ALL the employed and are collected,
count and percent:

* Self-employed / Employees                    -> employment_status
* Employed population in agriculture           -> industry (one category, as
                                                 printed; National)
* Informal employment                          -> formality (% of employed)
* Informal employment (excluding agriculture)  -> formality (% of NON-
                                                 agricultural employed, as the
                                                 label says)

Each table's percent columns are within-group (column) shares. What is emitted
is only what Tables 8 and 17 do not already hold: the by-sex block's status
SHARES and informal COUNTS repeat Tables 8 and 17 and are verified equal and
skipped (Table 8's "Self-Employed" spelling is used for the annex's
"Self-employed", so one state's series stays one series); the residence,
education and age blocks' "Total" columns repeat the by-sex Total and are
verified, not emitted. Groups go in locality, education and age_group exactly
as printed ("Post Sec", "45-55", "55-64" -- NBS's overlapping band labels are
NBS's). "-" is an empty cell, never 0.

Every block is held to its own arithmetic: self-employed + employees =
employed, each count agrees with its printed percent of the group's employed,
and the groups' employed sum to the Total (to rounding). State names come from
each table's caption and must be one of Table 8's 37; Table 102's caption
misspells Kebbi as "Kabbi" (its three sibling tables say Kebbi), the one alias.

145 OF THE 148 ANNEX TABLES ARE READ. Three are refused, each by a rule that
matches the defect itself, so a reissued table is read:
* T28 (Akwa Ibom, education): the header misprints two groups -- the Secondary
  column is headed "Total" and Post Sec "No Education".
* T144 (Plateau) and T148 (Rivers), education: digits wrap INSIDE the narrow
  columns ("2,414,61" / "0"), signed by truncated header words ("Primar",
  "Secondar", "Tota").
Precision varies by table and is kept as printed: whole-number percents
(Akwa Ibom T27 "26"), two-decimal percents (Taraba "70.52"), one-decimal
counts (Cross River T52 "716,794.6"); the arithmetic checks follow each
cell's printed precision.

TRAPS

* Two state names wrap in Table 17 ("AKWA" / numbers / "IBOM", "CROSS" /
  numbers / "RIVER"): the numbers sit on the line between the halves.
* RIVERS' female employee share prints as "20", not "20.0".
* State names are printed in capitals; they are written in title case here
  (FCT kept), as other sub-national geographies in the corpus are.

CROSS-CHECK: agriculture, forestry and fishing 30.1% (25,341,219 persons);
wholesale and retail 27.5%; services and sales workers 33.8%; informal
employment NATIONAL 77,561,393 (M 36,803,336 / F 40,758,051), excluding
agriculture 52,360,868; Lagos employees 33.8%.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

SURVEY = "Nigeria Labour Force Survey (NLFS) Annual Report 2023"
_BASE = dict(survey=SURVEY, period="2023",
             reference_period="Oct 2022 - Nov 2023", frequency="annual",
             working_age_base="15+")

_T8 = re.compile(r"^Table 8: Status in Employment by Sex", re.M)
_T17 = re.compile(r"^Table 17: Informal Employment by State and Sex", re.M)
_F9 = "Figure 9: Employment by Economic Sector of Main Job"
_F11 = "Figure 11: Employed Persons by Occupation"
_NUM = r"\d+(?:\.\d+)?"
_CNT = r"\d{1,3}(?:,\d{3})*"

_STATES = 37                        # 36 states + FCT
_OCCUPATIONS = [
    "Services and sales workers",
    "Skilled agricultural forestry and fishery workers",
    "Craft and related trades workers", "Elementary occupations",
    "Plant and machine operators and assemblers", "Professionals",
    "Technicians and associate professionals", "Clerical support workers",
    "Managers"]


def _state(name: str) -> str:
    name = " ".join(name.split())
    return "FCT" if name == "FCT" else name.title()


def _pages(pdf) -> list[str]:
    return [p.extract_text() or "" for p in pdf.pages]


def _table_8(pages: list[str]) -> list[dict]:
    """Rows 'STATE e e e  s s s  w w w' from the caption to the page after."""
    i = next(n for n, t in enumerate(pages) if _T8.search(t))
    text = "\n".join(pages[i:i + 2])
    out, seen = [], set()
    row = re.compile(rf"^([A-Z][A-Z ]+?)((?: {_NUM}){{9}})$")
    for ln in text[_T8.search(text).end():].splitlines():
        m = row.match(ln.strip())
        if not m:
            continue
        state = _state(m.group(1))
        v = [float(x) for x in m.group(2).split()]
        seen.add(state)
        # v[0:3] is the employment-to-population ratio -- unemployment's.
        for lab, vals in (("Self-Employed", v[3:6]), ("Employees", v[6:9])):
            for sex, val in zip(("total", "male", "female"), vals):
                out.append(C.row(topic="employment_status", characteristic=lab,
                                 classification="National", value=val, sex=sex,
                                 geography=state, measure="share",
                                 unit="percent", series_code="NLFS2023 T8",
                                 **_BASE))
        for a, b in ((3, 6), (4, 7), (5, 8)):
            if abs(v[a] + v[b] - 100) > 0.15:
                raise ValueError(f"NLFS2023 T8: {state} shares do not sum to 100")
    if len(seen) != _STATES:
        raise ValueError(f"NLFS2023 T8: read {len(seen)} states, want {_STATES}")
    return out


def _table_17(pages: list[str]) -> list[dict]:
    i = next(n for n, t in enumerate(pages) if _T17.search(t))
    text = pages[i]
    lines = [ln.strip() for ln in text[_T17.search(text).end():].splitlines()]
    row = re.compile(rf"^([A-Z][A-Z ]*?)?\s*((?:{_CNT} ?){{6}})$")
    out, pending, n = [], None, 0
    for k, s in enumerate(lines):
        m = row.match(s)
        if not m:
            continue
        name = m.group(1)
        if not name:
            # "AKWA" / numbers / "IBOM": the halves straddle the numbers.
            name = f"{lines[k - 1]} {lines[k + 1]}"
        v = [float(x.replace(",", "")) for x in m.group(2).split()]
        # Male + female = total to ROUNDING: each figure is a rounded
        # weighted estimate, and NATIONAL misses by 6 (informal) and 3
        # (excluding agriculture) persons as printed.
        for a in (0, 3):
            if abs(v[a] - v[a + 1] - v[a + 2]) > 10:
                raise ValueError(f"NLFS2023 T17: {name} sexes do not sum")
        geo = "Total country" if name.strip() == "NATIONAL" else _state(name)
        n += geo != "Total country"
        for lab, vals in (("Informal employment", v[0:3]),
                          ("Informal employment (excluding agriculture)", v[3:6])):
            for sex, val in zip(("total", "male", "female"), vals):
                out.append(C.row(topic="formality", characteristic=lab,
                                 classification="Not applicable", value=val,
                                 sex=sex, geography=geo, measure="count",
                                 unit="persons", series_code="NLFS2023 T17",
                                 **_BASE))
        if geo == "Total country":
            break
    if n != _STATES or not out or out[-1]["geography"] != "Total country":
        raise ValueError(f"NLFS2023 T17: read {n} states and no NATIONAL row")
    return out


def _figure(pages: list[str], caption: str) -> list[tuple[str, float]]:
    """Label/value pairs printed as text data labels above a figure caption."""
    # The figure's own page: its caption directly follows a bar's value line
    # (the list of figures carries the same caption, after dot leaders).
    text = next(t for t in pages
                if re.search(rf"\n[^\n]*\d\n{re.escape(caption)}", t))
    body = [ln.strip() for ln in text[:text.index(caption)].splitlines()]
    # The bars start after the section's prose, whose last line ends a
    # sentence ("... of total employed persons.", "... of the workforce.").
    # Prose carries numbers too ("51,383 (0.1%)"), so it must not be scanned.
    start = max(n for n, s in enumerate(body) if s.endswith(".")) + 1
    pairs, head = [], ""
    for s in body[start:]:
        m = re.fullmatch(rf"(.*?)\s*({_NUM})", s)
        if m:
            pairs.append([f"{head} {m.group(1)}".strip(), float(m.group(2))])
            head = ""
        elif pairs and not head and re.match(r"^[a-z]", s):
            pairs[-1][0] += " " + s          # wrapped tail of the label above
        elif not head:
            head = s                         # a label whose value is below
        else:
            raise ValueError(f"{caption}: two label lines without a value: "
                             f"{head!r} / {s!r}")
    if head:
        raise ValueError(f"{caption}: label {head!r} has no value")
    return [(lab, val) for lab, val in pairs]


def _figures(pages: list[str]) -> list[dict]:
    out = []
    ind = _figure(pages, _F9)
    if len(ind) != 20 or abs(sum(v for _, v in ind) - 100.1) > 0.05:
        raise ValueError(f"NLFS2023 F9: read {len(ind)} sections, "
                         f"sum {sum(v for _, v in ind):.1f}")
    if ind[0] != ("Agriculture, forestry and fishing", 30.1):
        raise ValueError(f"NLFS2023 F9: first bar {ind[0]}")
    occ = _figure(pages, _F11)
    if [l for l, _ in occ] != _OCCUPATIONS:
        raise ValueError(f"NLFS2023 F11: read {[l for l, _ in occ]}")
    if abs(sum(v for _, v in occ) - 99.9) > 0.05:
        raise ValueError("NLFS2023 F11: shares do not sum to 99.9")
    for topic, code, pairs in (("industry", "NLFS2023 F9", ind),
                               ("occupation", "NLFS2023 F11", occ)):
        for lab, val in pairs:
            out.append(C.row(topic=topic, characteristic=lab,
                             classification="National", value=val,
                             measure="share", unit="percent",
                             series_code=code, **_BASE))
    return out


# --------------------------------------------------------------------------
# Annex 1: state headline tables 18-165
# --------------------------------------------------------------------------

# "Place Of Residence" (Ogun, Table 127) and "Education Level" (Akwa Ibom)
# vary the wording; matched case-insensitively and normalised.
_ANNEX_CAP = re.compile(r"^Table (\d+)\s*:\s*:?\s*(.+?) state by (Sex|Place of "
                        r"Residence|Educational Level|Education Level|Age-Group)\s*$",
                        re.I)
_DIMS = {
    "Sex": ("sex", ["Male", "Female"]),
    "Place of Residence": ("locality", ["Urban", "Rural"]),
    "Educational Level": ("education", ["No Education", "Primary", "Secondary",
                                        "Post Sec", "Post Grad"]),
    "Education Level": ("education", ["No Education", "Primary", "Secondary",
                                      "Post Sec", "Post Grad"]),
    "Age-Group": ("age_group", ["15-24", "25-34", "35-44", "45-55", "55-64", "65+"]),
}
_ALIAS = {"Kabbi": "Kebbi"}
# AKWA IBOM'S EDUCATION TABLE (T28) MISPRINTS ITS HEADER: by x-position the
# Secondary column is headed "Total" and the Post Sec column "No Education"
# (once for the counts, once for the percents). The values are the usual five
# groups -- they sum to the 2,142,818 employed -- but which column is which can
# only be borrowed from other states' tables, not read off this one. Refused,
# and matched on the exact misprinted header so a corrected table is read.
_WRAPPED_DIGITS = {"Primar", "Secondar", "Tota"}
SKIPPED: list[int] = []         # annex tables refused this run, for the record
_T28_HEADER = (28, "Number Percentage % Headline Indicators No No Post No No "
                   "Total Primary Total Total Primary Total Post Grad Education "
                   "Education Grad Education Education")
# printed row head -> (topic, characteristic as emitted)
_ROWS = {
    "Self-employed": ("employment_status", "Self-Employed"),
    "Employees": ("employment_status", "Employees"),
    "Employed population in agriculture": ("industry",
                                           "Employed population in agriculture"),
    "Informal employment (excluding agriculture)": (
        "formality", "Informal employment (excluding agriculture)"),
    "Informal employment": ("formality", "Informal employment"),
    "Employed population": (None, None),          # reference only
}
# Percents carry one decimal, or two in Taraba's tables (70.52); counts are
# whole, or unrounded weighted estimates in Cross River's T52 ("2,022,481.4").
_TOK = re.compile(r"^(?:\d{1,3}(?:,\d{3})*(?:\.\d)?|\d{1,3}\.\d\d?|100(?:\.00?)?|-)$")


def _annex_blocks(pages: list[str]):
    """(table no, state, dimension, lines) for every annex table."""
    lines = []
    for t in pages:
        lines += [ln.strip() for ln in t.splitlines()]
    heads = [(k, _ANNEX_CAP.match(s)) for k, s in enumerate(lines)]
    heads = [(k, m) for k, m in heads if m and int(m.group(1)) >= 18]
    out = []
    for n, (k, m) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        body = [s for s in lines[k + 1:end] if not s.startswith("Page |")]
        name = " ".join(m.group(2).replace("-", " ").split()).title()
        name = "FCT" if name == "Fct" else _ALIAS.get(name, name)
        dim = {"place of residence": "Place of Residence",
               "education level": "Educational Level"}.get(
            m.group(3).lower(), m.group(3).title().replace("-group", "-Group"))
        out.append((int(m.group(1)), name, dim, body))
    return out


# The two long labels wrap, in two shapes: the head alone on its line with the
# numbers on the next ("Employed population in" / 410,928 ... / "agriculture"),
# or the head and the numbers on one line with the tail below ("Informal
# employment (excluding 581,215 ..." / "agriculture)"). Each row is found by
# the shortest prefix that identifies it, longest prefix first.
_HEADS = [("Informal employment (excluding", "Informal employment (excluding agriculture)"),
          ("Employed population in", "Employed population in agriculture"),
          ("Informal employment", "Informal employment"),
          ("Employed population", "Employed population"),
          ("Self-employed", "Self-employed"),
          ("Employees", "Employees")]


def _annex_rows(body: list[str], ncol: int, where: str) -> dict:
    """Printed row head -> (counts, percents), None for "-"."""
    got, k = {}, 0
    while k < len(body):
        s = body[k]
        for prefix, head in _HEADS:
            if s == prefix and k + 1 < len(body):
                toks = body[k + 1].split()          # numbers on the next line
                k += 1
            elif s.startswith(prefix + " ") and _TOK.match(s[len(prefix):].split()[0]):
                toks = s[len(prefix):].split()      # numbers on the head's line
            elif s.startswith(head + " ") and _TOK.match(s[len(head):].split()[0]):
                toks = s[len(head):].split()        # unwrapped label
            else:
                continue
            # Third shape (Kano T96): "Informal employment 4,076,057 ..." with
            # "(excluding agriculture)" alone on the NEXT line.
            if (head == "Informal employment" and k + 1 < len(body)
                    and body[k + 1].startswith("(excluding agriculture)")):
                head = "Informal employment (excluding agriculture)"
            if len(toks) != 2 * ncol or not all(_TOK.match(t) for t in toks):
                raise ValueError(f"{where}: {head!r} reads {toks}")
            num = [None if t == "-" else float(t.replace(",", "")) for t in toks]
            if head in got:
                raise ValueError(f"{where}: {head!r} twice")
            # Tolerance follows the printed precision: some tables (Akwa Ibom
            # T27) print whole-number percents ("26" for 26.4).
            tol = [0.15 if "." in t else 0.55 for t in toks[ncol:]]
            got[head] = (num[:ncol], num[ncol:], tol)
            break
        k += 1
    missing = set(_ROWS) - set(got)
    if missing:
        raise ValueError(f"{where}: rows not read: {sorted(missing)}")
    return got


def _annex_check(got: dict, where: str):
    emp = got["Employed population"][0]
    se, ee = got["Self-employed"], got["Employees"]
    for j, e in enumerate(emp):
        if not e:
            continue
        if abs((se[0][j] or 0) + (ee[0][j] or 0) - e) > 2:
            raise ValueError(f"{where} col {j}: self-employed + employees != employed")
        for head in ("Self-employed", "Employees", "Employed population in agriculture",
                     "Informal employment"):
            n, pc, tol = got[head][0][j], got[head][1][j], got[head][2][j]
            if n is not None and pc is not None and abs(100 * n / e - pc) > tol:
                raise ValueError(f"{where} col {j}: {head} {n} is not {pc}% of {e}")


def _annex(pages: list[str], states: set, t8: list[dict], t17: list[dict]) -> list[dict]:
    t8v = {(r["geography"], r["characteristic"], r["sex"]): r["value"] for r in t8}
    t17v = {(r["geography"], r["characteristic"], r["sex"]): r["value"] for r in t17}
    SKIPPED.clear()
    blocks = _annex_blocks(pages)
    by_state: dict = {}
    for no, state, dim, _ in blocks:
        by_state.setdefault(state, []).append(dim.replace("Education Level",
                                                          "Educational Level"))
    if set(by_state) != states or any(
            sorted(v) != sorted(["Sex", "Place of Residence", "Educational Level",
                                 "Age-Group"]) for v in by_state.values()):
        raise ValueError(f"NLFS2023 annex: states/tables read {by_state}")
    sex_total: dict = {}
    out = []
    for no, state, dim, body in sorted(blocks, key=lambda b: b[2] != "Sex"):
        col, groups = _DIMS[dim]
        where = f"NLFS2023 T{no} {state}"
        # The header (one or several lines above the first indicator) must
        # carry the groups in order.
        top = " ".join(body[:next(n for n, s in enumerate(body)
                                  if s.startswith("Working-age population"))])
        if (no, top) == _T28_HEADER:
            continue
        # SOME EDUCATION TABLES WRAP DIGITS INSIDE THEIR NARROW COLUMNS
        # (Plateau T144: "2,414,61" / "0"; header "Primar" / "y"), so a
        # count's digits sit on two lines. The truncated header words are the
        # signature; such a table is refused (see _WRAPPED_DIGITS).
        if _WRAPPED_DIGITS & set(top.split()):
            SKIPPED.append(no)
            continue
        # A two-line header wraps "No" / "Education" (Kano T96), so the test is
        # each group's FIRST word in order, and all of its words present.
        words, pos = top.split(), 0
        for g in groups:
            first = g.split()[0]
            if first not in words[pos:] or not all(w in words for w in g.split()):
                raise ValueError(f"{where}: header lacks {g!r}: {top!r}")
            pos = words.index(first, pos) + 1
        got = _annex_rows(body, len(groups) + 1, where)
        _annex_check(got, where)
        code = f"NLFS2023 T{no}"
        if dim == "Sex":
            sex_total[state] = {h: (v[0][0], v[1][0]) for h, v in got.items()}
            for j, sex in enumerate(("total", "male", "female")):
                for head, lab in (("Self-employed", "Self-Employed"),
                                  ("Employees", "Employees")):
                    pc = got[head][1][j]
                    if pc is not None and abs(pc - t8v[(state, lab, sex)]) > 0.05:
                        raise ValueError(f"{where}: {lab} {sex} {pc} != Table 8")
                for head in ("Informal employment",
                             "Informal employment (excluding agriculture)"):
                    n = got[head][0][j]
                    if n is not None and abs(n - t17v[(state, head, sex)]) > 1:
                        raise ValueError(f"{where}: {head} {sex} {n} != Table 17")
                emit = [("Self-Employed", "count", got["Self-employed"][0][j]),
                        ("Employees", "count", got["Employees"][0][j])]
                for head in ("Employed population in agriculture",):
                    emit += [(head, "count", got[head][0][j]),
                             (head, "share", got[head][1][j])]
                for head in ("Informal employment",
                             "Informal employment (excluding agriculture)"):
                    emit.append((head, "share", got[head][1][j]))
                for lab, meas, v in emit:
                    if v is None:
                        continue
                    out.append(_annex_row(lab, meas, v, state, code, sex=sex))
            continue
        # residence / education / age: the Total column repeats the by-sex
        # Total; checked, not emitted.
        tot = sex_total[state]
        for head, (cnt, pct, tol) in got.items():
            same_pct = (pct[0] is None and tot[head][1] is None) or (
                pct[0] is not None and tot[head][1] is not None
                and abs(pct[0] - tot[head][1]) <= tol[0])
            if abs(cnt[0] - tot[head][0]) > 1 or not same_pct:
                raise ValueError(f"{where}: {head} Total {cnt[0]} / {pct[0]} differs "
                                 f"from the by-sex table's {tot[head]}")
        emp = got["Employed population"][0]
        if abs(sum(e or 0 for e in emp[1:]) - emp[0]) > 3 * len(groups):
            raise ValueError(f"{where}: groups' employed sum to "
                             f"{sum(e or 0 for e in emp[1:])}, not {emp[0]}")
        for j, g in enumerate(groups, start=1):
            ctx = ({"locality": g.lower(), "locality_label": g}
                   if col == "locality" else {col: g})
            for head, (topic, lab) in _ROWS.items():
                if topic is None:
                    continue
                for meas, v in (("count", got[head][0][j]), ("share", got[head][1][j])):
                    if v is not None:
                        out.append(_annex_row(lab, meas, v, state, code, **ctx))
    return out


def _annex_row(lab, meas, v, state, code, **ctx):
    topic = {"Self-Employed": "employment_status", "Employees": "employment_status",
             "Employed population in agriculture": "industry"}.get(lab, "formality")
    return C.row(topic=topic, characteristic=lab,
                 classification="Not applicable" if topic == "formality" else "National",
                 value=v, measure=meas,
                 unit="persons" if meas == "count" else "percent",
                 geography=state, series_code=code, **_BASE, **ctx)


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        pages = _pages(pdf)
    t8, t17 = _table_8(pages), _table_17(pages)
    states = {r["geography"] for r in t8}
    return pd.DataFrame(t8 + t17 + _figures(pages) + _annex(pages, states, t8, t17))
