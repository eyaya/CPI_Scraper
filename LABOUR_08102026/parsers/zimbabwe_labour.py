"""Zimbabwe — ZIMSTAT 2019 Labour Force and Child Labour Survey (LFCLS), report.

UNBLOCKED BY A DIFFERENT PUBLICATION, NOT A DIFFERENT READING. The quarterly
QLFS that `unemployment/` collects still publishes every composition cut as a
chart with no values in its text layer (re-checked on the Q2 2025 report), and
that refusal stands: measuring bars would invent precision ZIMSTAT never
published. The 2019 LFCLS annual report prints the same cuts as TABLES, and is
what this parser reads. Base 15+; fieldwork 5 June - 7 July 2019.

Five tables, each a COLUMN-percentage distribution (the "(a)"/"(b)" pairs are
one column-% and one row-% table each, and which is which alternates -- "within
Sex" / "within Area" in the caption marks the column-% one):

* Table 4.5(b)  status in employment, by area (Urban / Rural / Total) in
                blocks Male / Female / Both Sexes            -> employment_status
* Table 4.6(a)  23 industries, by sex                        -> industry
* Table 4.7(a)  10 occupation major groups, by sex           -> occupation
* Table 7.1a    sector of employment Formal / Informal / Household, by sex
                within area, percent AND number               -> formality
* Table 7.10    informal vs formal EMPLOYMENT (job-based), Total row only,
                counts by sex                                 -> formality

CLASSIFICATIONS. Section 4.8 states that ISCO-08 "was used to classify and
aggregate" occupation -> ISCO-08. Neither ISIC nor ICSE is named anywhere in
the report's 356 pages, so industry and status are National, although the 23
industries are recognisably ISIC Rev.4 sections (with G split into wholesale
and retail, K into financial and insurance) -- saying so would be inference.

NOT COLLECTED, AND WHY:
* Table 4.8 (institutional sector). Its base is 1,422,153 -- not the 2,897,064
  employed. The report says own-account workers "were not asked questions on
  institutional sector", but 1,422,153 is neither employed minus own-account
  (1,879,532) nor employees (1,735,822), so the universe the shares describe is
  not stated. A share of an unknown population is not collectable.
* 4.5(a), 4.6(b), 4.7(b), 4.8(b): row percentages (sex or area split WITHIN a
  category). The "Total Number" lines are employed totals -- `unemployment`'s
  figure.
* Chapter 7 tables 7.1b-7.9: distributions WITHIN the informal sector (a
  sub-population); 7.10-7.14 by age etc. within informal employment. Only
  7.10's Total row -- informal and formal employment counts that sum exactly
  to each sex's employed -- is a composition of ALL employment.
* Chapter 5 tables other than 5.4-5.6 (EPR rates; 5.7 institutional sector,
  same unstated-base problem as 4.8; education, field of study, hours,
  precarity and NEET cuts, which fit no topic or are rates).

CHAPTER 5, THE YOUTH REPEATS (added 2026-10-01), on the two youth bands
ZIMSTAT prints, "15-24" and "15-35", carried in `age_group` (and the
five-year bands 15-19 .. 30-35 of the occupation table likewise):

* Table 5.4ai / 5.4aii  status in employment, by area within each sex
* Table 5.5ai / 5.5aii  industry (21 / 23 categories), by sex, area, province
* Table 5.6ai / 5.6aii  occupation (9 / 10 groups), by sex, age band, area,
                        province

5.5 and 5.6 are TRANSPOSED against chapter 4: each ROW is a population group
and its values that group's distribution across the categories, closed by
"100" and the group's employed count. Column headers are letter-spaced ("A
gric ult ur e"); the categories are the chapter-4 lists, and the de-spaced
header must carry them in that order (a few labels whose glyphs interleave
with a neighbour's are exempt from the text check but still counted).

FOUR PUBLISHED DEFECTS IN THESE SIX TABLES, each handled by a rule that is
re-checked every run rather than smoothed:
* 5.4aii's FEMALE "Total" column is a copy of the MALE one (3.4 / 29.1 / 67.1 /
  0.3) -- impossible beside female Urban 2.1 and Rural 1.9 employers. Dropped;
  any other Total outside its own Urban-Rural range raises.
* 5.5aii's Area rows carry each other's values: "Urban" prints 57.1%
  agriculture and "Rural" 17.9%, while their counts (766 043 / 719 322) match
  5.6aii's correctly-patterned Urban/Rural rows. Which side is wrong cannot be
  told from the page, so neither area row is collected.
* 5.5aii clips three cells to their integer part ("2.", "1.", "17."); those
  cells are left empty, never read as whole numbers.
* 5.6ai labels Matabeleland North and South the wrong way round: its counts
  (South 10 229, North 18 289) contradict both 5.5ai and the province table
  5.2ai (North 10 230, South 18 288). Both rows are refused. 5.6aii prints the
  bare word "Matabeleland" twice; those rows are assigned by their counts
  (31 850 / 52 362), which 5.5aii prints against the full names.

The 15-19 and 20-24 rows of 5.6ai repeat those of 5.6aii (which adds an Armed
forces column); they are verified equal and taken once, from 5.6aii. Area
counts differ between the status table and the industry/occupation tables
(15-24 urban 276 652 vs 268 671) -- kept as published; the counts themselves
are not collected (levels belong to `unemployment`).

7.1a AND 7.10 ARE DIFFERENT QUANTITIES and keep their printed labels apart:
"Informal" (a SECTOR -- unregistered enterprise, 975,880) vs "Informal
Employment" (a JOB characteristic, 2,187,175).

THE 7.1a ROWS INTERLEAVE PERCENTS WITH SPACE-GROUPED COUNTS --
"Formal 41.6 367 203 33.7 229 196 38.2 596 399" -- so a row is split as
(percent, count) x 3 with the percent required to carry a decimal or be 100,
and every split is then checked twice: the three sectors' counts sum to the
Total count (to within 2 persons -- the report's own weighted cells are
rounded one by one, and Urban female sums to 681 061 under a printed 681 062),
and each count agrees with its percent of that Total to rounding.

CROSS-CHECK: employees 59.9% (both sexes, total); agriculture, forestry and
fishing 36.0%; retail trade 17.0%; elementary occupations 29.4%; informal
sector 975,880 (33.7%); informal employment 2,187,175 of 2,897,064.
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF -- locating 5 pages among 356 without a full layout pass
import pandas as pd
import pdfplumber

from . import _common as C

SURVEY = "Labour Force and Child Labour Survey (LFCLS) 2019"
BASE = dict(survey=SURVEY, period="2019",
            reference_period="LFCLS 2019 (5 June - 7 July 2019)",
            frequency="ad_hoc", working_age_base="15+")

_PCT = r"(?:\d{1,3}\.\d|100(?:\.0)?|0)"
_CNT = r"\d{1,3}(?: \d{3})*"
_AREA = {"Urban": ("urban", "Urban"), "Rural": ("rural", "Rural"),
         "Zimbabwe": ("all", "Total"), "Total": ("all", "Total")}
_SEX_BLOCK = {"Male": "male", "Female": "female", "Both Sexes": "total"}


def _pages(path: str) -> dict[str, str]:
    """Text of each wanted table's page, keyed by table id. Captions also sit
    in the list of tables (dot leaders), so only a caption line without
    leaders counts, and only past the front matter."""
    want = {
        "4.5b": r"^Table 4\.5\(b\): Percent Distribution",
        "4.6a": r"^Table 4\.6\(a\): Percent Distribution",
        "4.7a": r"^Table 4\.7 \(a\): Percent Distribution",
        "7.1a": r"^Table ?7\.1a: Number and Percent Distribution",
        "7.10": r"^Table 7\.10 Currently Employed Persons",
        "5.4ai": r"^Table 5\.4ai: Youth 15-24 years",
        "5.4aii": r"^Table 5\.4aii: Youths 15-35 years",
        "5.5ai": r"^Table 5\.5ai: Youths 15-24 years",
        "5.5aii": r"^Table 5\.5aii: Youths 15-35 years",
        "5.6ai": r"^Table 5\.6ai: Youths 15-24 years",
        "5.6aii": r"^Table 5\.6aii: Youths 15-35 years",
    }
    found: dict[str, int] = {}
    doc = fitz.open(path)
    for i in range(30, len(doc)):
        for ln in doc[i].get_text().splitlines():
            s = ln.strip()
            for key, pat in want.items():
                if key not in found and re.match(pat, s) and "...." not in s:
                    found[key] = i
    missing = set(want) - set(found)
    if missing:
        raise ValueError(f"LFCLS 2019: tables not found: {sorted(missing)}")
    out = {}
    with pdfplumber.open(path) as pdf:
        for key, i in found.items():
            # A youth table may run onto the next page (5.6ai does).
            pages = [i, i + 1] if key.startswith("5.") else [i]
            out[key] = "\n".join(pdf.pages[k].extract_text() or ""
                                  for k in pages)
    return out


def _region(text: str, caption: str) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines()]
    start = next(n for n, s in enumerate(lines) if re.match(caption, s))
    return lines[start + 1:]


def _rejoin(lines: list[str]) -> list[str]:
    """ "Water supply; sewerage, waste management and" / "remediation 0.6 0.3
    0.5": a numberless line followed by a lower-case line carrying the values
    is one label."""
    out, i = [], 0
    while i < len(lines):
        s = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if (not re.search(r"\d", s) and re.match(r"^[a-z]", nxt)
                and re.search(r"\d", nxt)):
            out.append(f"{s} {nxt}")
            i += 2
        else:
            out.append(s)
            i += 1
    return out


def _simple(lines: list[str], ncol: int, stop: str) -> list[tuple[str, list[float]]]:
    """Rows of `label  v1 .. vN`, up to and including the `stop` row."""
    rx = re.compile(rf"^(\D+?)\s+((?:{_PCT}\s*){{{ncol}}})$")
    rows = []
    for s in _rejoin(lines):
        m = rx.match(s)
        if not m:
            continue
        label = m.group(1).strip()
        rows.append((label, [float(v) for v in m.group(2).split()]))
        if re.match(stop, label):
            break
    return rows


def _check(rows, where: str, n: int):
    labels = [r[0] for r in rows]
    if len(rows) != n:
        raise ValueError(f"{where}: expected {n} rows, read {len(rows)}: {labels}")
    cats, total = rows[:-1], rows[-1]
    for j, t in enumerate(total[1]):
        s = sum(r[1][j] for r in cats)
        if abs(s - t) > 0.6:
            raise ValueError(f"{where}: column {j} sums to {s}, Total {t}")


def _emit(out, rows, topic, classification, cols, series):
    for label, vals in rows:
        label = "Total" if label.startswith("Total") else label
        for extra, v in zip(cols, vals):
            out.append(C.row(topic=topic, characteristic=label,
                             classification=classification, value=v,
                             measure="share", unit="percent",
                             series_code=series, **BASE, **extra))


def _loc(name):
    loc, lab = _AREA[name]
    return {"locality": loc, "locality_label": lab}


def _status(text, out):
    lines = _region(text, r"^Table 4\.5\(b\)")
    cols_area = [_loc("Urban"), _loc("Rural"), _loc("Total")]
    blocks, cur = {}, None
    for s in lines:
        if s in _SEX_BLOCK:
            cur = _SEX_BLOCK[s]
            blocks[cur] = []
        elif cur:
            blocks[cur].append(s)
    if list(blocks) != ["male", "female", "total"]:
        raise ValueError(f"LFCLS T4.5b: blocks read {list(blocks)}")
    for sex, blk in blocks.items():
        rows = _simple(blk, 3, r"^Total Percent")
        _check(rows, f"LFCLS T4.5b {sex}", 5)
        _emit(out, rows, "employment_status", "National",
              [{**c, "sex": sex} for c in cols_area], "LFCLS2019 T4.5b")


def _by_sex(text, caption, n, topic, classification, series, out):
    rows = _simple(_region(text, caption), 3, r"^Total Percent")
    _check(rows, series, n)
    _emit(out, rows, topic, classification,
          [{"sex": "male"}, {"sex": "female"}, {"sex": "total"}], series)


def _sector_71a(text, out):
    pair = rf"({_PCT}) ({_CNT})"
    rx = re.compile(rf"^(Formal|Informal|Household|Total) {pair} {pair} {pair}$")
    area = None
    for s in _region(text, r"^Table ?7\.1a"):
        if s in ("Urban", "Rural", "Zimbabwe"):
            area, got = s, {}
            continue
        m = rx.match(s)
        if not (area and m):
            continue
        g = m.groups()
        got[g[0]] = [(float(g[k]), float(g[k + 1].replace(" ", "")))
                     for k in (1, 3, 5)]
        if g[0] != "Total":
            continue
        # Both checks, per sex column: counts sum to the Total, and each count
        # is its printed percent of the Total to rounding.
        if list(got) != ["Formal", "Informal", "Household", "Total"]:
            raise ValueError(f"LFCLS T7.1a {area}: read {list(got)}")
        for j in range(3):
            tot = got["Total"][j][1]
            # To within 2 persons: weighted estimates rounded cell by cell --
            # Urban female prints 229 196 + 273 572 + 178 293 = 681 061 under
            # a Total of 681 062. Kept as published.
            if abs(sum(got[c][j][1] for c in list(got)[:3]) - tot) > 2:
                raise ValueError(f"LFCLS T7.1a {area}: counts do not sum")
            for c in list(got)[:3]:
                pct, n = got[c][j]
                if abs(100 * n / tot - pct) > 0.06:
                    raise ValueError(f"LFCLS T7.1a {area} {c}: {n} is not {pct}%")
        for c, vals in got.items():
            for sex, (pct, n) in zip(("male", "female", "total"), vals):
                for v, meas, unit in ((pct, "share", "percent"),
                                      (n, "count", "persons")):
                    out.append(C.row(topic="formality", characteristic=c,
                                     classification="Not applicable", value=v,
                                     measure=meas, unit=unit, sex=sex,
                                     series_code="LFCLS2019 T7.1a",
                                     **_loc(area), **BASE))
        area = None
    if sum(1 for r in out if r["series_code"] == "LFCLS2019 T7.1a") != 72:
        raise ValueError("LFCLS T7.1a: expected 3 areas x 4 rows x 3 sexes x 2")


def _type_710(text, out):
    pair = rf"{_PCT} ({_CNT})"
    rx = re.compile(rf"^Total {pair} {pair} {pair} {pair} {pair} {pair} ({_CNT})$")
    m = next((rx.match(s) for s in _region(text, r"^Table 7\.10")
              if rx.match(s)), None)
    if not m:
        raise ValueError("LFCLS T7.10: Total row not read")
    n = [float(g.replace(" ", "")) for g in m.groups()]
    inf, frm, allemp = n[0:3], n[3:6], n[6]
    # male + female = total within each type; informal + formal = all employed
    for a in (inf, frm):
        if a[0] + a[1] != a[2]:
            raise ValueError("LFCLS T7.10: sexes do not sum")
    if inf[2] + frm[2] != allemp:
        raise ValueError("LFCLS T7.10: informal + formal != all employed")
    for label, vals in (("Informal Employment", inf), ("Formal Employment", frm)):
        for sex, v in zip(("male", "female", "total"), vals):
            out.append(C.row(topic="formality", characteristic=label,
                             classification="Not applicable", value=v,
                             measure="count", unit="persons", sex=sex,
                             series_code="LFCLS2019 T7.10", **BASE))


# --------------------------------------------------------------------------
# Chapter 5: youth
# --------------------------------------------------------------------------

_IND = ["Agriculture, forestry and fishing", "Mining and quarrying",
        "Manufacturing", "Electricity, gas, steam and air conditioning supply",
        "Water supply; sewerage, waste management and remediation",
        "Construction", "Wholesale trade",
        "Retail trade; sale and repair of motor vehicles and motor cycles",
        "Transportation and storage", "Accommodation and food service activities",
        "Information and communication", "Financial activities",
        "Insurance activities", "Real estate activities",
        "Professional, scientific and technical activities",
        "Administrative and support service activities",
        "Public administration and defence; compulsory social security",
        "Education", "Human health and social work activities",
        "Arts, entertainment and recreation", "Other service activities",
        "Activities of households as employers of domestic personnel",
        "Activities of extraterritorial organizations and bodies"]
_OCC = ["Armed forces occupations", "Managers", "Professionals",
        "Technicians and associate professionals", "Clerical support workers",
        "Service and sales workers",
        "Skilled agricultural, forestry and fishery workers",
        "Craft and related trades workers",
        "Plant and machine operators, and assemblers", "Elementary occupations"]
_NOT_15_24 = {"Real estate activities",
              "Activities of extraterritorial organizations and bodies"}

# table -> (band, topic, classification, categories, labels exempt from the
#           header text check because their glyphs interleave with a neighbour)
_YOUTH = {
    "5.5ai": ("15-24", "industry", "National",
              [c for c in _IND if c not in _NOT_15_24],
              {"Information and communication",
               "Activities of households as employers of domestic personnel"}),
    "5.5aii": ("15-35", "industry", "National", _IND,
               {"Accommodation and food service activities",
                "Public administration and defence; compulsory social security",
                "Activities of households as employers of domestic personnel"}),
    "5.6ai": ("15-24", "occupation", "ISCO-08", _OCC[1:],
              {"Skilled agricultural, forestry and fishery workers",
               "Craft and related trades workers",
               "Plant and machine operators, and assemblers",
               "Elementary occupations"}),
    "5.6aii": ("15-35", "occupation", "ISCO-08", _OCC,
               {"Clerical support workers"}),
}
_PROVINCES = {"Manicaland", "Mashonaland Central", "Mashonaland East",
              "Mashonaland West", "Matabeleland North", "Matabeleland South",
              "Midlands", "Masvingo", "Harare", "Bulawayo"}


def _flat(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def _youth_status(text, key, out):
    band = "15-24" if key == "5.4ai" else "15-35"
    names = {"male": "male", "female": "female", "both sexes": "total"}
    blocks, cur = {}, None
    for s in _region(text, rf"^Table {re.escape(key)}:"):
        if s.lower() in names:
            cur = names[s.lower()]
            blocks[cur] = []
        elif cur:
            blocks[cur].append(s)
            if s.startswith("Total Number") and cur == "total":
                break
    if list(blocks) != ["male", "female", "total"]:
        raise ValueError(f"LFCLS T{key}: blocks read {list(blocks)}")
    parsed = {}
    for sex, blk in blocks.items():
        rows = _simple(blk, 3, r"^Total Percent")
        if len(rows) != 5:
            raise ValueError(f"LFCLS T{key} {sex}: read {[r[0] for r in rows]}")
        for j in range(3):
            tot = sum(r[1][j] for r in rows[:-1])
            if abs(tot - 100) > 0.6:
                raise ValueError(f"LFCLS T{key} {sex}: column {j} sums to {tot}")
        parsed[sex] = rows
    # A sex's Total must lie between its Urban and Rural shares. 5.4aii's
    # female Total column is the male one again -- dropped, and re-checked.
    drop = set()
    for sex, rows in parsed.items():
        bad = [r[0] for r in rows[:-1]
               if not (min(r[1][0], r[1][1]) - 0.1 <= r[1][2]
                       <= max(r[1][0], r[1][1]) + 0.1)]
        if not bad:
            continue
        copy = [r[1][2] for r in rows] == [r[1][2] for r in parsed["male"]]
        if (key, sex) == ("5.4aii", "female") and copy:
            drop.add(sex)
            continue
        raise ValueError(f"LFCLS T{key} {sex}: Total outside Urban-Rural for {bad}")
    if key == "5.4aii" and "female" not in drop:
        raise ValueError("LFCLS T5.4aii: the female Total no longer copies the "
                         "male one -- ZIMSTAT corrected it; collect it")
    cols = [_loc("Urban"), _loc("Rural"), _loc("Total")]
    for sex, rows in parsed.items():
        use = cols[:2] if sex in drop else cols
        _emit(out, [(lab, vals[:len(use)]) for lab, vals in rows],
              "employment_status", "National",
              [{**c, "sex": sex, "age_group": band} for c in use],
              f"LFCLS2019 T{key}")


def _youth_wide(text, key, out, taken_age: dict):
    band, topic, scheme, cats, exempt = _YOUTH[key]
    lines = _region(text, rf"^Table {re.escape(key)}:")
    first = next(n for n, s in enumerate(lines) if s.split()[:1] == ["Sex"])
    header = _flat(" ".join(lines[:first]))
    pos = 0
    for c in cats:
        if c in exempt:
            continue
        k = header.find(_flat(c), pos)
        if k < 0:
            raise ValueError(f"LFCLS T{key}: header does not carry {c!r} in order")
        pos = k + len(_flat(c))
    n = len(cats)
    rows = []
    for s in lines[first:]:
        m = re.match(r"^(\d{2} - \d{2}|[A-Z][A-Za-z ]*?)\s+(\d.*)$", s)
        if not m:
            continue
        toks = m.group(2).split()
        if len(toks) < n + 2 or toks[n] != "100":
            continue
        if not re.fullmatch(r"\d{1,3}(?: \d{3})*", " ".join(toks[n + 1:])):
            continue
        # "2." / "17.": a cell clipped to its integer part -- left empty.
        vals = [None if re.fullmatch(r"\d+\.", t) else float(t) for t in toks[:n]]
        floor = sum(float(t[:-1]) for t in toks[:n] if re.fullmatch(r"\d+\.", t))
        rows.append((m.group(1).strip(), vals, int("".join(toks[n + 1:])), floor))
        if m.group(1).startswith("Total"):
            break
    if not rows or rows[-1][0] != "Total":
        raise ValueError(f"LFCLS T{key}: no Total row")
    # A clipped cell counts at its printed integer part, plus up to 0.9.
    for lab, vals, _, floor in rows:
        known = sum(v for v in vals if v is not None) + floor
        clipped = sum(1 for v in vals if v is None)
        if not (100 - 0.6 - 0.9 * clipped <= known <= 100.6):
            raise ValueError(f"LFCLS T{key} {lab}: row sums to {known}")
    rows = [r[:3] for r in rows]
    total_n = rows[-1][2]
    for grp in (("Male", "Female"), ("Urban", "Rural")):
        got = [r[2] for r in rows if r[0] in grp]
        if len(got) != 2 or abs(sum(got) - total_n) > 2:
            raise ValueError(f"LFCLS T{key}: {grp} counts do not sum to {total_n}")
    provinces = sum(r[2] for r in rows
                    if r[0] in _PROVINCES or r[0] == "Matabeleland")
    if abs(provinces - total_n) > 10:
        raise ValueError(f"LFCLS T{key}: provinces sum to {provinces}, not {total_n}")

    n_bare = sum(1 for r in rows if r[0] == "Matabeleland")
    out_rows = []
    for lab, vals, cnt in rows:
        ctx = {"age_group": band}
        if lab in ("Male", "Female"):
            ctx["sex"] = lab.lower()
        elif lab in ("Urban", "Rural"):
            if key == "5.5aii":         # values swapped against labels (see top)
                continue
            ctx.update(_loc(lab))
        elif re.fullmatch(r"\d{2} - \d{2}", lab):
            if key == "5.6ai":          # taken from 5.6aii, checked equal below
                taken_age[lab] = vals
                continue
            ctx["age_group"] = lab.replace(" ", "")
        elif lab.startswith("Matabeleland"):
            if key == "5.6ai":          # labels contradict their counts
                if (lab, cnt) not in (("Matabeleland South", 10229),
                                      ("Matabeleland North", 18289)):
                    raise ValueError(f"LFCLS T5.6ai: {lab} {cnt} -- the label "
                                     f"swap is gone; re-examine and collect")
                continue
            if lab == "Matabeleland":   # 5.6aii: bare name, placed by its count
                by_n = {31850: "Matabeleland North", 52362: "Matabeleland South"}
                if cnt not in by_n or n_bare != 2:
                    raise ValueError(f"LFCLS T{key}: cannot place Matabeleland {cnt}")
                lab = by_n[cnt]
            ctx["geography"] = lab
        elif lab in _PROVINCES:
            ctx["geography"] = lab
        elif lab != "Total":
            raise ValueError(f"LFCLS T{key}: unknown row {lab!r}")
        out_rows.append((lab, vals, ctx))
    if key == "5.6aii":
        if set(taken_age) != {"15 - 19", "20 - 24"}:
            raise ValueError(f"LFCLS T5.6ai: age rows read {sorted(taken_age)}")
        for lab, vals in taken_age.items():
            mine = next(v for l, v, _ in rows if l == lab)
            if mine[1:] != vals:        # 5.6aii adds Armed forces in front
                raise ValueError(f"LFCLS T5.6ai/aii: {lab} rows disagree")
    for lab, vals, ctx in out_rows:
        for c, v in zip(cats, vals):
            if v is None:
                continue
            out.append(C.row(topic=topic, characteristic=c, classification=scheme,
                             value=v, measure="share", unit="percent",
                             series_code=f"LFCLS2019 T{key}", **BASE, **ctx))


def parse(path: str) -> pd.DataFrame:
    pages = _pages(path)
    out: list[dict] = []
    _status(pages["4.5b"], out)
    _by_sex(pages["4.6a"], r"^Table 4\.6\(a\)", 24, "industry", "National",
            "LFCLS2019 T4.6a", out)
    _by_sex(pages["4.7a"], r"^Table 4\.7 \(a\)", 11, "occupation", "ISCO-08",
            "LFCLS2019 T4.7a", out)
    _sector_71a(pages["7.1a"], out)
    _type_710(pages["7.10"], out)
    _youth_status(pages["5.4ai"], "5.4ai", out)
    _youth_status(pages["5.4aii"], "5.4aii", out)
    taken_age: dict = {}
    for key in ("5.5ai", "5.5aii", "5.6ai", "5.6aii"):
        _youth_wide(pages[key], key, out, taken_age)
    return pd.DataFrame(out)
