"""Botswana — the QMTS Labour Force Module report's BACK-QUARTER and
BREAKDOWN tables, read alongside Table 1.0's current quarter.

ONE ISSUE, EIGHT QUARTERS. `botswana_unemployment` reads Table 1.0's current
quarter only. The same report prints its own trend: Table 1.0 restates the two
previous rounds, Table 2.1c carries unemployment by age for EIGHT rounds (Q3
2019 to Q1 2024), Table 1.2b participation by age for five, and YE2b the youth
rate for eight. Statistics Botswana does not run the QMTS every quarter, so the
rounds are uneven (Q3 2019, Q4 2019, Q1 2020, Q4 2020, Q4 2021, Q4 2022, Q3
2023, Q1 2024) -- they are dated exactly as each column's header prints them.

EVERY COLUMN IS DATED FROM ITS OWN HEADER, never by position: the next issue
will shift every column one round, and a positional layout would then publish
each value under the previous quarter. A header that does not yield the
expected number of quarters raises.

READ HERE (Q1 2024 issue):

* Table 1.0, the two restated rounds (Q4 2022, Q3 2023), totals only, for the
  same rows and labels the current quarter uses;
* Table 2.1c unemployment rate by age (15+): M/F/T for the current round, the
  total for seven earlier ones;
* Table 2.1d unemployment rate by age (18+): M/F/T current, total previous
  -- under its own label, because its male rate (26.5) contradicts Table
  1.0's (27.6) for the same round;
* Table 1.2a/1.2b participation rate by age: M/F current (1.2a), total for
  five rounds (1.2b). 1.2a's last column is headed "Q4 2023" but holds 1.2b's
  Q3 2023 values digit for digit -- a header slip; it is not read;
* Table 2.2 unemployment rate by stratum (Cities and Towns, Urban Villages ->
  urban; Rural Areas -> rural) and sex;
* Table 4.1 NEET rate by age band (within 15-35) and sex, and the previous
  round's total;
* YE2b the youth (15-35) unemployment total for eight rounds -- its AGE rows
  are not read: they disagree with 2.1c for the same bands (15-17: 76.7
  against 75.8; YE2a counts 7,361 unemployed against 2.1c's 7,027), and nothing
  in the report says which is right;
* UN10 unemployed / employed / labour force COUNTS by district and sex (the
  table prints no rates).

ONE SERIES, ONE LABEL: national rows carry Table 1.0's own series_label, so
the eight-round trend is continuous. Where Table 1.0 already gives a round, the
trend table's value is checked EQUAL and not emitted twice; a disagreement
raises.

LEVEL BREAK (from the descriptor): the QMTS is not continuous with the BMTHS
2024/25 round. Every row here is QMTS and says so in `survey`.

CROSS-CHECK: unemployment 15+ Q3 2019 20.7, Q1 2020 23.2, Q4 2021 26.0; 20-24
Q1 2024 44.2; LFPR Q4 2020 60.0; youth Q4 2019 28.8; Urban Villages 31.1;
NEET 18-19 52.9; Gaborone unemployed 24,211.
"""
from __future__ import annotations

import re

import pdfplumber

from . import _common as C

_SURVEY = "Quarterly Multi-Topic Survey (QMTS) -- Labour Force Module"
_U15 = "Unemployment Rate % (15 years and above)"
# Table 2.1d's own label, NOT Table 1.0's: the two DISAGREE. Table 1.0 row 20
# prints the 18+ male rate as 27.6; Table 2.1d prints 26.5 beside its own
# counts (133,607 unemployed of 503,415). Both are kept, told apart by label,
# as Kenya's two LU2 values are.
_U18 = "Unemployment Rate by Age Group (18 years & above)"
_LFPR = "Labour Force Participation Rate (LFPR)"
_YOUTH = "Youth Unemployment Rate (15-35 years)"
_NEET = "Youth NEET Rate (15-35 years)"
# "528525" (row 7 of Table 1.0) prints with no thousands comma.
_NUM = r"(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|-)"
_Q = re.compile(r"Q\s*_?([1-4])\s*_?\s*(20\d\d)")


def _period(q: str, y: str) -> str:
    return f"{y}-Q{q}"


def _pages(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [p.extract_text() or "" for p in pdf.pages]


def _page(pages, caption: str, where: str) -> list[str]:
    rx = re.compile(caption, re.M)
    for t in pages:
        m = rx.search(t)
        if m and "……" not in t[m.start():m.start() + 200] and "...." not in \
                t[m.start():m.start() + 200]:
            return [ln.strip() for ln in t[m.start():].splitlines()]
    raise ValueError(f"{where}: caption not found")


def _nums(s: str) -> list[float | None]:
    return [None if v == "-" else float(v.replace(",", ""))
            for v in re.findall(_NUM, s)]


def _row(period, current, topic, label, value, **kw):
    r = {"topic": topic, "definition": kw.pop("definition", "strict"),
         "series_label": label, "sex": "total", "age_group": "Total",
         "education": "Total", "geography": "Total country", "locality": "all",
         "locality_label": "Total", "working_age_base": "15+",
         "period": period,
         "reference_period": (f"QMTS Q{period[-1]} {period[:4]}"
                              + ("" if period == current
                                 else f" (as printed in QMTS {current})")),
         "frequency": "quarterly", "measure": kw.pop("measure", "rate"),
         "value": float(value), "unit": kw.pop("unit", "percent"),
         "survey": _SURVEY, "series_code": kw.pop("series_code")}
    r.update(kw)
    return r


def _age(label: str) -> str:
    s = re.sub(r"\s*-\s*", "-", label.strip())
    return "35" if s == "35 years" else s


def parse_trends(path: str, current_rows: dict) -> list[dict]:
    """`current_rows` maps (topic, series_label, working_age_base, sex,
    period) -> value for what Table 1.0's engine layout already emits, so a
    trend value for the same round is checked rather than duplicated."""
    pages = _pages(path)
    out: list[dict] = []
    have = dict(current_rows)

    def emit(r):
        key = (r["topic"], r["series_label"], r["working_age_base"], r["sex"],
               r["period"], r["age_group"], r["geography"], r["locality_label"])
        if key in have:
            if abs(have[key] - r["value"]) > 0.051:
                raise ValueError(f"BW: {key} prints {r['value']} here and "
                                 f"{have[key]} elsewhere")
            return
        have[key] = r["value"]
        out.append(r)

    # --- Table 1.0: the restated rounds -------------------------------------
    lines = _page(pages, r"^Table 1\.0: National Headline", "BW T1.0")
    head = next(ln for ln in lines if ln.startswith("Indicator/Statistics"))
    # "Indicator/Statistics Q4 2022 Q3 2023 Total Male Female Q1 2024) Q1
    # 2024)": the two restated rounds lead; the trailing pair close the
    # "% change (... TO Q1 2024)" headings. The current round is the one the
    # "Totals QMTS Q1 2024" line names.
    qs = _Q.findall(head)
    tot = next(ln for ln in lines if re.match(r"^Totals QMTS Q", ln))
    cur = _Q.findall(tot)
    if len(qs) != 4 or len(cur) != 1 or qs[2] != cur[0] or qs[3] != cur[0]:
        raise ValueError(f"BW T1.0: header rounds {qs}, current {cur}")
    (q1, y1), (q2, y2), (qc, yc) = qs[0], qs[1], cur[0]
    hist = [_period(q1, y1), _period(q2, y2)]
    current = f"Q{qc} {yc}"
    cur_p = _period(qc, yc)
    from .botswana_unemployment import LAYOUT
    specs = LAYOUT["tables"][0]["rows"]
    for ln in lines:
        body = re.sub(r"^\d{1,2}\s+", "", ln)
        for sp in specs:
            if not re.search(sp["match"], body):
                continue
            if sp.get("exclude") and re.search(sp["exclude"], body):
                continue
            nums = _nums(body)[sp.get("drop_leading", 0):]
            # Labels such as "Population (15 years and above)" carry digits of
            # their own; the data are the trailing seven values.
            nums = nums[-7:]
            if len(nums) != 7:
                raise ValueError(f"BW T1.0 {sp['label']!r}: {nums}")
            rate = sp["topic"] not in ("working_age_population", "labour_force",
                                       "employed", "unemployed",
                                       "outside_labour_force",
                                       "potential_labour_force")
            for per, v in zip(hist, nums[:2]):
                if v is None:
                    continue
                emit(_row(per, current, sp["topic"], sp["label"], v,
                          definition=sp.get("definition", "not_applicable"),
                          measure="rate" if rate else "count",
                          unit="percent" if rate else "persons",
                          working_age_base=sp.get("working_age_base", "15+"),
                          age_group=sp.get("age_group", "Total"),
                          series_code="BW QMTS T1.0"))
            break

    # --- Table 2.1c: unemployment by age, eight rounds -----------------------
    lines = _page(pages, r"^Table 2\.1c Cont.d: Unemployment Rate \(15 years",
                  "BW T2.1c")
    i = next(i for i, ln in enumerate(lines) if ln.startswith("Unemployment Rate Q"))
    qs = re.findall(r"Q([1-4])", lines[i])
    ys = re.findall(r"20\d\d", lines[i + 1])
    if len(qs) != 8 or len(ys) != 8:
        raise ValueError(f"BW T2.1c: header {lines[i]!r} / {lines[i + 1]!r}")
    rounds = [_period(q, y) for q, y in zip(qs, ys)]
    if rounds[0] != cur_p:
        raise ValueError(f"BW T2.1c: first round {rounds[0]} is not {cur_p}")
    n = 0
    for ln in lines[i + 2:]:
        m = re.match(rf"^(\d{{2}}-\d{{2}}|75\+|Total)\s+((?:{_NUM}\s+){{9}}{_NUM})$", ln)
        if not m:
            continue
        v = _nums(m.group(2))
        age = "Total" if m.group(1) == "Total" else _age(m.group(1))
        cells = [(cur_p, "male", v[0]), (cur_p, "female", v[1]), (cur_p, "total", v[2])]
        cells += [(p, "total", x) for p, x in zip(rounds[1:], v[3:])]
        for per, sex, x in cells:
            if x is not None:
                emit(_row(per, current, "unemployment_rate", _U15, x, sex=sex,
                          age_group=age, series_code="BW QMTS T2.1c"))
        n += 1
    if n != 15:
        raise ValueError(f"BW T2.1c: {n} rows, expected 15")

    # --- Table 2.1d: 18+ by age ----------------------------------------------
    lines = _page(pages, r"^Table 2\.1d: Unemployment Rate by Age Group \(18",
                  "BW T2.1d")
    prev = hist[1]
    n = 0
    for ln in lines:
        m = re.match(rf"^(\d{{2}}-\d{{2}}|75\+|Total)\s+((?:{_NUM}\s+){{12}}{_NUM})$", ln)
        if not m:
            continue
        v = _nums(m.group(2))
        age = "Total" if m.group(1) == "Total" else _age(m.group(1))
        for per, sex, x in ((cur_p, "male", v[9]), (cur_p, "female", v[10]),
                            (cur_p, "total", v[11]), (prev, "total", v[12])):
            if x is not None:
                emit(_row(per, current, "unemployment_rate", _U18, x, sex=sex,
                          age_group=age, working_age_base="18+",
                          series_code="BW QMTS T2.1d"))
        n += 1
        if m.group(1) == "Total":
            break
    if n != 14:
        raise ValueError(f"BW T2.1d: {n} rows, expected 14")

    # --- Tables 1.2a / 1.2b: participation by age -----------------------------
    lines = _page(pages, r"^Table 1\.2b: Labour Force Participation Rates by Age",
                  "BW T1.2b")
    hdr = next(ln for ln in lines if ln.count("Q") >= 10)
    found = _Q.findall(hdr)
    rounds = [_period(q, y) for q, y in found[:5]]
    if len(found) != 10 or rounds != [_period(q, y) for q, y in found[5:]] \
            or rounds[-1] != cur_p:
        raise ValueError(f"BW T1.2b: header {hdr!r}")
    n = 0
    for ln in lines:
        m = re.match(rf"^(\d{{2}} - \d{{2}}|75 \+|Total)\s+((?:{_NUM}\s+){{9}}{_NUM})$", ln)
        if not m:
            continue
        v = _nums(m.group(2))[5:]
        age = "Total" if m.group(1) == "Total" else _age(m.group(1))
        for per, x in zip(rounds, v):
            emit(_row(per, current, "labour_force_participation_rate", _LFPR, x,
                      age_group=age, series_code="BW QMTS T1.2b"))
        n += 1
    if n != 15:
        raise ValueError(f"BW T1.2b: {n} rows, expected 15")
    lines = _page(pages, r"^Table 1\.2a: Labour Force Participation Rates by Age",
                  "BW T1.2a")
    for ln in lines:
        m = re.match(rf"^(\d{{2}} - \d{{2}}|75 \+|Total)\s+((?:{_NUM}\s+){{9}}{_NUM})$", ln)
        if not m:
            continue
        v = _nums(m.group(2))
        age = "Total" if m.group(1) == "Total" else _age(m.group(1))
        for sex, x in (("male", v[6]), ("female", v[7]), ("total", v[8])):
            emit(_row(cur_p, current, "labour_force_participation_rate", _LFPR, x,
                      sex=sex, age_group=age, series_code="BW QMTS T1.2a"))
        if age == "Total":
            break               # Table 1.2b follows on the same page

    # --- Table 2.2: by stratum -------------------------------------------------
    # Each stratum name wraps AROUND its numbers: "Cities and" / numbers /
    # "Towns"; "Urban" / numbers / "Villages"; "Rural" / numbers / "Areas".
    lines = _page(pages, r"^Table 2\.2: Unemployment Rate by Strata", "BW T2.2")
    strata = {"Cities and Towns": "urban", "Urban Villages": "urban",
              "Rural Areas": "rural"}
    got, head, vals = 0, None, None
    for ln in lines[1:]:
        if ln.startswith("Total"):
            break
        if re.fullmatch(rf"(?:{_NUM}\s+){{11}}{_NUM}", ln):
            vals = _nums(ln)
            continue
        if not ln or re.search(r"\d", ln) or "Stratum" in ln:
            continue
        if vals is None:
            head = ln
            continue
        name = f"{head} {ln}"
        if name not in strata:
            raise ValueError(f"BW T2.2: stratum {name!r}")
        for sex, x in (("male", vals[9]), ("female", vals[10]), ("total", vals[11])):
            emit(_row(cur_p, current, "unemployment_rate", _U15, x, sex=sex,
                      locality=strata[name], locality_label=name,
                      series_code="BW QMTS T2.2"))
        got, head, vals = got + 1, None, None
    if got != 3:
        raise ValueError(f"BW T2.2: {got} strata, expected 3")

    # --- Table 4.1: NEET by age ---------------------------------------------------
    lines = _page(pages, r"^Table 4\.1- NEET rate by Age Group", "BW T4.1")
    n = 0
    for ln in lines:
        m = re.match(rf"^(\d{{2}}-\d{{2}}|35 years|Total)\s+((?:{_NUM}\s+){{3}}{_NUM})$", ln)
        if not m:
            continue
        v = _nums(m.group(2))
        age = "15-35" if m.group(1) == "Total" else _age(m.group(1))
        for per, sex, x in ((cur_p, "male", v[0]), (cur_p, "female", v[1]),
                            (cur_p, "total", v[2]), (prev, "total", v[3])):
            emit(_row(per, current, "neet_rate", _NEET, x, sex=sex,
                      definition="not_applicable", age_group=age,
                      series_code="BW QMTS T4.1"))
        n += 1
    if n != 7:
        raise ValueError(f"BW T4.1: {n} rows, expected 7")

    # --- YE2b: youth total, eight rounds --------------------------------------
    lines = _page(pages, r"^Table YE2 ?b: Total Youth \(15-35\) Unemployment Rate",
                  "BW YE2b")
    i = next(i for i, ln in enumerate(lines) if ln.startswith("Age Q"))
    rounds = [cur_p] + [_period(q, y) for q, y in _Q.findall(lines[i])]
    if len(rounds) != 8:
        raise ValueError(f"BW YE2b: header {lines[i]!r}")
    tot = next(ln for ln in lines[i:] if ln.startswith("Total "))
    v = _nums(tot)
    cells = [(cur_p, "male", v[0]), (cur_p, "female", v[1]), (cur_p, "total", v[2])]
    cells += [(p, "total", x) for p, x in zip(rounds[1:], v[3:])]
    for per, sex, x in cells:
        emit(_row(per, current, "youth_unemployment_rate", _YOUTH, x, sex=sex,
                  age_group="15-35", series_code="BW QMTS YE2b"))

    # --- UN10: counts by district ---------------------------------------------
    lines = _page(pages, r"^Table UN10: Current Unemployment Rate by District",
                  "BW UN10")
    n, sums = 0, [0.0] * 9
    for ln in lines[2:]:
        m = re.match(rf"^([A-Z][A-Za-z_ ]+?)\s+((?:{_NUM}\s+){{8}}{_NUM})$", ln)
        if not m:
            continue
        name, v = m.group(1).replace("_", " "), _nums(m.group(2))
        if name == "Total":
            if any(abs(a - b) > 3 for a, b in zip(sums, v)):
                raise ValueError(f"BW UN10: districts sum {sums} != Total {v}")
            break
        sums = [a + b for a, b in zip(sums, v)]
        for k, (topic, label) in enumerate((("unemployed", "Unemployed Population"),
                                            ("employed", "Employed Population"),
                                            ("labour_force", "Labour Force (15 years and above)"))):
            for j, sex in enumerate(("male", "female", "total")):
                emit(_row(cur_p, current, topic, label, v[3 * k + j], sex=sex,
                          definition="not_applicable", measure="count",
                          unit="persons", geography=name,
                          series_code="BW QMTS UN10"))
        n += 1
    if n != 26:
        raise ValueError(f"BW UN10: {n} districts, expected 26")
    return out
