"""ONS Algeria — Rétrospective Statistique 1962-2020, Chapitre I "Démographie".

The one ONS publication that reprints sixty years of population in tables
(ons.dz/rgph2020, the census page, answers HTTP 500, which is why Algeria was
on the rejected list). Chapter 1 is a separate PDF, article 2849 of ons.dz:

* Tableau 41      mid-year ESTIMATES by sex, 1970-2019, in THOUSANDS;
* Tableau 42      CENSUS 1966 by age (5-year) and sex, persons;
* Tableaux 43-45  CENSUS 1977 / 1987 / 1998 by age and sex -- the "Total"
                  block (ménages ordinaires et collectifs + nomades) only;
* Tableaux 46-48  CENSUS 1987 / 1998 / 2008 by wilaya and sex (ménages
                  ordinaires et collectifs);
* Tableaux 54-74  mid-year ESTIMATES by age and sex, 1999-2019, THOUSANDS;
* Tableau 76      CENSUS density by wilaya at the five censuses (hab./km²).

THE UNIVERSES DIFFER AND ARE RECORDED, NOT RECONCILED. 1966 counts all
residents (incl. "population comptée à part"); 1977 and 1987 exclude
foreigners and the population comptée à part and are SAMPLE estimates (1/10,
1/30); the wilaya tables count ordinary and collective households only (1987
on a 1/5 wilaya sample), i.e. WITHOUT nomads. So each wilaya table's own
"Algérie" row is a different total from the same year's age table: for 1987
and 1998, where the age table gives the fuller national figure, the wilaya
table's "Algérie" row is NOT emitted (it would collide on the merge key with a
different number); for 2008, the only national 2008 count here, it is.

SPACE-GROUPED NUMBERS ARE SPLIT UNDER THE TABLE'S OWN ARITHMETIC. A row like
"1 188 403 1 155 798 2 344 201" reads several ways. Every split of a row's
digit groups into the expected number of values is enumerated, and exactly one
must satisfy masculin + féminin = total (and, for the three-block census
tables, ordinaires + nomades = total in every column). Zero or two consistent
splits raise. The thousands tables carry ONS's own warning that totals "peuvent
diverger aux arrondis près", so there the identity is held to +-1.

PUBLISHED OFF-BY-ONES: the 1998 census table (T45) prints several sums one
person off its parts (0-4, ordinaires: 1 627 670 + 1 552 105 = 3 179 775,
printed 3 179 776); its identity is held to +-1, the 1977 and 1987 tables'
exactly. One estimate row fails outright and is kept as printed, pinned in
`_KNOWN`: 2002's "80 ans et plus" (T57, thousands) prints 129 + 125 = 244.
The wilaya tables (1987 on a 1/5 sample) miss by a few persons
(Chlef 1987: 342 881 + 342 328 = 685 209, printed 685 205) and are held to
0.2%. Values are kept as printed.

ESTIMATE TOTALS PRINTED TWICE agree: Tableau 41's total for 1999-2019 equals
each age table's Total row; it is checked equal and emitted once.

Tableau 40 (totals only) repeats Tableau 41 and is not read; its and Tableau
41's "1966*" row is the census, given in full by Tableau 42. Tableaux 49-53
(by STRATE, urban/rural) have no column in this schema; 1-39 are vital
statistics and life tables; 75 is age at first marriage.

CROSS-CHECK: census 1966 total 12 096 347; 1987 22 881 508; 2008 Algérie
(ménages) 34 080 030; estimate 2019 43 424 thousand (M 22 003 / F 21 421);
Alger density 2008 3 666,4.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_TABLE = re.compile(r"Tableau\s*(\d+)\s*:")
_NUM_TOK = re.compile(r"^(?:\d+|-)$")


def _splits(tokens: list[str], k: int) -> list[list[int]]:
    """Every way to read `tokens` as k space-grouped integers."""
    out = []

    def rec(i, cur):
        if len(cur) == k:
            if i == len(tokens):
                out.append(cur)
            return
        if i >= len(tokens):
            return
        t = tokens[i]
        if t == "-":
            rec(i + 1, cur + [0])
            return
        if len(t) > 1 and t[0] == "0":
            return
        val, j = t, i + 1
        rec(j, cur + [int(val)])
        while j < len(tokens) and re.fullmatch(r"\d{3}", tokens[j]):
            val += tokens[j]
            j += 1
            rec(j, cur + [int(val)])

    rec(0, [])
    return out


def _mft(v, tol):
    return abs(v[0] + v[1] - v[2]) <= tol


def _mft_sample(v):
    # Sample-based wilaya tables print sums a few persons off (1987 Chlef:
    # 342 881 + 342 328 = 685 209, printed 685 205). A WRONG split is off by
    # orders of magnitude, so 0.2% cannot admit one; uniqueness is still
    # required by `_read`.
    return abs(v[0] + v[1] - v[2]) <= max(1, 0.002 * v[2])


def _three_blocks(v, tol):
    a, b, c = v[0:3], v[3:6], v[6:9]
    return (all(_mft(x, tol) for x in (a, b, c))
            and all(abs(a[i] + b[i] - c[i]) <= tol for i in range(3)))


# PUBLISHED ROWS THAT FAIL THEIR OWN IDENTITY, kept as printed. Each must
# still read ONE way structurally; if ONS corrects the row it passes the check
# and the entry becomes dead (harmless), and any OTHER failing row raises.
_KNOWN = {
    # T57 (2002, thousands): 129 + 125 = 254, printed 244.
    ("ONS RS T57", "80 ans et plus"),
}


def _read(tokens, k, check, where, known=False):
    every = {tuple(s) for s in _splits(tokens, k)}
    sols = {s for s in every if check(list(s))}
    if not sols and known and len(every) == 1:
        sols = every
    if len(sols) != 1:
        raise ValueError(f"ONS Algeria {where}: {len(sols)} consistent readings "
                         f"of {' '.join(tokens)!r}")
    return list(sols.pop())


def _tables(path: str) -> dict[int, list[str]]:
    """Table number -> its lines (caption excluded), across the chapter."""
    out: dict[int, list[str]] = {}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[40:64]:
            cur = None
            for ln in (page.extract_text() or "").splitlines():
                m = _TABLE.search(ln)
                if m and ln.lstrip().startswith("Tableau"):
                    cur = int(m.group(1))
                    out.setdefault(cur, [])
                    continue
                if cur is not None:
                    out[cur].append(ln.strip())
    return out


def _row(series, sex, age, geo, period, measure, value, unit, code):
    return {"series_type": series, "sex": sex, "age_group": age,
            "geography": geo, "period": str(period), "frequency": "annual",
            "measure": measure, "value": value, "unit": unit,
            "series_code": code}


_SEXES = ("male", "female", "total")
_AGE = re.compile(r"^(\d{1,2}\s*-\s*\d{1,2}|\d{1,2}\s*(?:&|et)\s*\+|\d+ ans et plus|"
                  r"N\.D\.|TOTAL|Total|0)\s+([\d\s-]+)$")


def _age_label(a: str) -> str:
    a = re.sub(r"\s+", " ", a).strip()
    return "Total" if a.upper() == "TOTAL" else a


def _age_table(lines, k, check, series, period, unit, code):
    rows = []
    for ln in lines:
        if ln.startswith(("Source", "*", "(", "N.B")):
            break
        m = _AGE.match(ln)
        if not m:
            continue
        lab = _age_label(m.group(1))
        v = _read(m.group(2).split(), k, check, f"{code} {ln[:20]}",
                  known=(code, lab) in _KNOWN)
        v = v[-3:]                           # the Total block of 43-45
        for sex, val in zip(_SEXES, v):
            rows.append(_row(series, sex, _age_label(m.group(1)), "Total country",
                             period, "count", val, unit, code))
    return rows


def _wilaya_table(lines, period, code, keep_national):
    rows = []
    wil = re.compile(r"^(\d{2}\s*-\s*\D+?|Algérie)\s+([\d\s]+)$")
    for ln in lines:
        m = wil.match(ln)
        if not m:
            continue
        name = re.sub(r"\s+", " ", m.group(1)).strip()
        if name == "Algérie" and not keep_national:
            continue
        v = _read(m.group(2).split(), 3, _mft_sample, f"{code} {name}")
        geo = "Total country" if name == "Algérie" else name
        for sex, val in zip(_SEXES, v):
            rows.append(_row("census", sex, "Total", geo, period, "count", val,
                             "persons", code))
    return rows


def parse(path: str) -> pd.DataFrame:
    t = _tables(path)
    rows = []

    # Tableau 41: estimates by sex (thousands); the 1966* row is the census.
    for ln in t[41]:
        m = re.match(r"^(19[7-9]\d|20[0-2]\d)\s+([\d\s]+)$", ln)
        if m:
            v = _read(m.group(2).split(), 3, lambda s: _mft(s, 1), f"T41 {m.group(1)}")
            for sex, val in zip(_SEXES, v):
                rows.append(_row("estimate", sex, "Total", "Total country",
                                 m.group(1), "count", val, "thousand_persons",
                                 "ONS RS T41"))

    rows += _age_table(t[42], 3, lambda s: _mft(s, 0), "census", 1966, "persons",
                       "ONS RS T42")
    # 1998 (T45) prints sums one person off in places (0-4 ordinaires:
    # 1 627 670 + 1 552 105 = 3 179 775, printed 3 179 776): held to +-1 there,
    # exact in 1977 and 1987.
    for tab, year, tol in ((43, 1977, 0), (44, 1987, 0), (45, 1998, 1)):
        rows += _age_table(t[tab], 9, lambda s, tol=tol: _three_blocks(s, tol),
                           "census", year, "persons", f"ONS RS T{tab}")
    for tab, year in ((46, 1987), (47, 1998), (48, 2008)):
        rows += _wilaya_table(t[tab], year, f"ONS RS T{tab}",
                              keep_national=(year == 2008))
    for tab in range(54, 75):
        year = 1999 + (tab - 54)
        rows += _age_table(t[tab], 3, lambda s: _mft(s, 1), "estimate", year,
                           "thousand_persons", f"ONS RS T{tab}")

    # Tableau 76: density at the five censuses ("19981" = 1998, footnote 1).
    for ln in t.get(76, []):
        m = re.match(r"^(\D+?)\s+((?:\d[\d ]*,\d\s*){5})$", ln)
        if not m:
            continue
        vals = re.findall(r"\d[\d ]*?,\d", m.group(2))
        vals = [float(x.replace(" ", "").replace(",", ".")) for x in vals]
        if len(vals) != 5:
            raise ValueError(f"ONS Algeria T76: {ln!r}")
        name = m.group(1).strip().rstrip("*").strip()
        geo = "Total country" if name == "Total" else name
        for year, val in zip((1966, 1977, 1987, 1998, 2008), vals):
            rows.append(_row("census", "total", "Total", geo, year, "density",
                             val, "per_km2", "ONS RS T76"))

    df = pd.DataFrame(rows)
    key = ["series_type", "sex", "age_group", "geography", "period", "measure"]
    dup = df[df.duplicated(key, keep=False)]
    if len(dup) and (dup.groupby(key)["value"].nunique() > 1).any():
        bad = dup.groupby(key)["value"].nunique()
        raise ValueError(f"ONS Algeria: tables disagree on {bad[bad > 1].index[0]}")
    df = df.drop_duplicates(key)

    # Coverage guards: what the chapter prints.
    est = df[(df.series_type == "estimate") & (df.age_group == "Total")
             & (df.sex == "total")]
    if sorted(est.period) != [str(y) for y in range(1970, 2020)]:
        raise ValueError(f"ONS Algeria: estimate years {sorted(est.period)[:3]}..")
    for y in ("1987", "1998", "2008"):
        n = df[(df.series_type == "census") & (df.period == y)
               & (df.geography != "Total country") & (df.measure == "count")]
        if n.geography.nunique() != 48:
            raise ValueError(f"ONS Algeria: {y} has {n.geography.nunique()} wilayas")
    return df
