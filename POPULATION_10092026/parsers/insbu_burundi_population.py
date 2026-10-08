"""INSBU Burundi — Annuaire statistique du Burundi, chapter I "Population":
the 2024 census (RGPHAE 2024) and the 1979, 1990 and 2008 censuses.

The README once recorded Burundi as rejected ("the publications API carries
only a 1987 DHS and notices about the census in the field"). The 2024 YEARBOOK
now carries the RGPHAE 2024 results, and reprints the three earlier censuses:

* Tableau 1.01  total population, national + the five provinces x sex (2024);
* Tableau 1.02  population of ordinary households by milieu x sex (2024);
* Tableau 1.08  population of ordinary households by age group x sex (2024);
* Tableau 1.09  population by age x sex at the 1979, 1990 and 2008 censuses.

TWO UNIVERSES, NOT RECONCILED: Tableau 1.01 counts the TOTAL population
(12 332 788) while 1.02-1.08 count the population of ORDINARY HOUSEHOLDS
(12 220 934, collective households excluded). The national and provincial
totals come from 1.01; the age and milieu breakdowns from 1.02/1.08, whose own
"Burundi"/"Ensemble" total rows are NOT emitted (they would collide with
1.01's national total under the same key while counting a smaller universe).
So the 2024 age bands sum to 12 220 934, not to the national 12 332 788.

PROVINCES ONLY. Tableau 1.01 lists each of the five provinces (Buhumuza,
Bujumbura, Burunga, Butanyerera, Gitega -- the 2025 administrative map) followed
by its communes, all in capitals. Provinces are identified structurally (a row
equal to the sum of the rows after it) and checked against the national row;
the communes are not read -- one of them is also called GITEGA, which would
collide with the province of that name, and they are a finer level than the
other countries carry.

TABLEAU 1.09'S 2024 COLUMN IS NOT READ: it misprints three cells (0-4 female
"1 108 195" against 1 018 195 in Tableau 1.08; 20-24 female "56 554" for
565 554; 30-34 female "41 596" for 414 596). 2024 comes from Tableau 1.08.
Its 1990 AGGREGATE rows do not add up either (under-20: 2 957 307 printed,
1 675 583 + 1 716 479 = 3 392 062), so only the 5-year bands and "70 et plus"
are read for 1979-2008, each held to Total = Masculin + Féminin; the census
Total rows (1979 4 031 420; 1990 5 292 793; 2008 8 053 574) do add up and are
emitted. 1979's sex columns print without thousands separators -- grouping is
decided by the same identity.

Age labels are normalised to the corpus form ("0 - 4 ans" / "15 19 ans" ->
"0-4", "80 ans ou plus" -> "80+"); the wide groups the NSO prints (0-14, 15-59,
60+) are kept as published groups. Milieu is carried as geography "Urbain" /
"Rural" (ordinary households) and overlaps the national total.

CROSS-CHECK: 2024 total 12 332 788 (M 5 901 069); Buhumuza 2 052 261; urban
2 990 466; 0-4 2 041 065; 2008 total 8 053 574, 1979 0-4 697 580.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_SERIES = "BI_RGPHAE_2024"
_TOK = re.compile(r"^\d+$")
# Commune rows of Tableau 1.01 that print M + F != T (see _t101).
_BAD_ROWS = {"KIGANDA"}


def _numbers(tokens: list[str]):
    """Group digit tokens into numbers: a run of 3-digit tokens continues the
    number opened by a 1-3 digit token; a 4+ digit token is a number alone."""
    if not tokens:
        yield []
        return
    t0 = tokens[0]
    if not _TOK.match(t0):
        return
    if len(t0) > 3:
        for rest in _numbers(tokens[1:]):
            yield [int(t0)] + rest
        return
    for k in range(1, len(tokens) + 1):
        grp = tokens[:k]
        if any(len(g) != 3 or not _TOK.match(g) for g in grp[1:]):
            break
        for rest in _numbers(tokens[k:]):
            yield [int("".join(grp))] + rest


def _triples(tokens: list[str], n_triples: int, need: int, order="TMF"):
    """Split into n_triples (T, M, F) triples; the first `need` must satisfy
    T = M + F (within 2 persons of rounding). Returns the unique set of
    consistent leading triples, or None."""
    sols = set()
    for c in _numbers(tokens):
        if len(c) != 3 * n_triples:
            continue
        ok = True
        for i in range(need):
            t, m, f = c[3 * i:3 * i + 3] if order == "TMF" else (
                c[3 * i + 2], c[3 * i], c[3 * i + 1])
            if abs(t - m - f) > 2:
                ok = False
                break
        if ok:
            sols.add(tuple(c[:3 * need]))
    return list(sols.pop()) if len(sols) == 1 else None


def _band(label: str) -> str | None:
    s = label.lower().replace("ou plus", "+").replace("ouplus", "+")
    s = s.replace("et plus", "+").replace("ans", "").replace("à", "-")
    s = re.sub(r"\s+", " ", s).strip()
    m = re.fullmatch(r"(\d{1,2})\s*-?\s*(\d{1,2})", s)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2))}"
    m = re.fullmatch(r"(\d{1,2})\s*\+", s)
    if m:
        return f"{int(m.group(1))}+"
    return None


def _row(sex, age, geo, period, value, code=_SERIES):
    return {"series_type": "census", "sex": sex, "age_group": age,
            "geography": geo, "period": period, "frequency": "annual",
            "measure": "count", "value": float(value), "unit": "persons",
            "series_code": code}


def _lines(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        out = []
        for p in pdf.pages[15:40]:
            out += [ln.strip() for ln in (p.extract_text() or "").splitlines()
                    if ln.strip()]
    return out


def _block(lines, caption, stop=r"^(Source|SOURCE|Tableau)"):
    i = next(i for i, ln in enumerate(lines) if re.search(caption, ln))
    out = []
    for ln in lines[i + 1:]:
        if re.match(stop, ln) and not re.search(caption, ln):
            if ln.startswith(("Source", "SOURCE")):
                break
            if re.match(r"Tableau", ln) and "(suite)" not in ln:
                break
        out.append(ln)
    return out


def _label_and_tokens(ln):
    toks = ln.split()
    lab = []
    while toks and not _TOK.match(toks[0]):
        lab.append(toks.pop(0))
    return " ".join(lab), toks


def _t101(lines, out):
    blk = _block(lines, r"Tableau 1\.\s*01\.")
    rows = []
    for ln in blk:
        if ln.startswith("Tableau 1. 01") or "(suite)" in ln:
            continue
        lab, toks = _label_and_tokens(ln)
        if not lab or not toks or not lab.isupper():
            continue
        groupings = {tuple(c) for c in _numbers(toks) if len(c) == 3}
        sols = {c for c in groupings if abs(c[0] + c[1] - c[2]) <= 2}
        if not sols and lab in _BAD_ROWS:
            # A PUBLISHED error: commune KIGANDA prints 68 276 + 80 246 as
            # 149 522 (1 000 too many). No grouping adds up, so the one that
            # comes closest is taken -- and must be the only one that close.
            # The commune is not emitted; its printed total is what the
            # province sum uses, and that sum must still hold.
            gap = {c: abs(c[0] + c[1] - c[2]) for c in groupings}
            best = min(gap.values())
            sols = {c for c, g in gap.items() if g == best}
        if len(sols) != 1:
            raise ValueError(f"INSBU T1.01: cannot split {ln!r}")
        rows.append((lab, sols.pop()))
    if rows[0][0] != "BURUNDI":
        raise ValueError(f"INSBU T1.01: first row {rows[0][0]!r}")
    nat, rest = rows[0], rows[1:]
    provinces, i = [], 0
    while i < len(rest):
        name, vals = rest[i]
        acc, j = 0, i + 1
        while j < len(rest) and acc < vals[2]:
            acc += rest[j][1][2]
            j += 1
        if acc != vals[2]:
            raise ValueError(f"INSBU T1.01: communes of {name} sum {acc} vs "
                             f"{vals[2]}")
        provinces.append((name, vals))
        i = j
    for k in range(3):
        if sum(p[1][k] for p in provinces) != nat[1][k]:
            raise ValueError("INSBU T1.01: provinces do not sum to Burundi")
    if len(provinces) != 5:
        raise ValueError(f"INSBU T1.01: {len(provinces)} provinces")
    for geo, vals in [("Total country", nat[1])] + provinces:
        for sex, v in zip(("male", "female", "total"), vals):
            out.append(_row(sex, "Total", geo, "2024", v))


def _t102(lines, out):
    blk = _block(lines, r"Tableau 1\.\s*02\.")
    for ln in blk:
        lab, toks = _label_and_tokens(ln)
        if lab not in ("URBAIN", "RURAL"):
            continue
        toks = [t for t in toks if "," not in t]   # drop the percentages
        sols = {tuple(c) for c in _numbers(toks) if len(c) == 3 and
                c[0] == c[1] + c[2]}
        if len(sols) != 1:
            raise ValueError(f"INSBU T1.02: cannot split {ln!r}")
        t, m, f = sols.pop()
        geo = lab.capitalize()
        for sex, v in (("total", t), ("male", m), ("female", f)):
            out.append(_row(sex, "Total", geo, "2024", v))


def _t108(lines, out):
    blk = _block(lines, r"Tableau 1\.\s*08\.")
    n = 0
    for ln in blk:
        lab, toks = _label_and_tokens(ln)
        if lab.startswith("Burundi") or not toks:
            continue
        # "15 19 ans" puts a digit before the label text ends: rebuild
        m = re.match(r"^(\d{1,2})\s*-?\s*(\d{1,2})?\s*(ans.*?|ouplus)\s+(\d.*)$", ln)
        if m and not lab:
            lab = f"{m.group(1)}-{m.group(2)}" if m.group(2) else \
                f"{m.group(1)} {m.group(3)}"
            toks = m.group(4).split()
        elif re.match(r"^\d{1,2}-", ln) or re.match(r"^\d{1,2}\s", ln):
            m2 = re.match(r"^(\d{1,2}\s*-?\s*\d{0,2}\s*ans(?: ou ?plus| et plus)?)\s+(.*)$", ln)
            if not m2:
                continue
            lab, toks = m2.group(1), m2.group(2).split()
        age = _band(lab)
        if age is None:
            continue
        toks = [t for t in toks if "," not in t]
        # T M F then three shares (integers like "100" or "50" survive the
        # comma filter): keep the leading consistent triple
        sols = set()
        for c in _numbers(toks):
            if len(c) >= 3 and c[0] == c[1] + c[2] and c[0] > 1000:
                sols.add(tuple(c[:3]))
        if len(sols) != 1:
            raise ValueError(f"INSBU T1.08: cannot split {ln!r} ({len(sols)})")
        t, mm, f = sols.pop()
        for sex, v in (("total", t), ("male", mm), ("female", f)):
            out.append(_row(sex, age, "Total country", "2024", v))
        n += 1
    if n < 20:
        raise ValueError(f"INSBU T1.08: only {n} age rows")


def _t109(lines, out):
    blk = _block(lines, r"Tableau 1\.\s*09\.")
    years = ("1979", "1990", "2008")
    seen = set()
    for ln in blk:
        # labels begin with a digit ("0 à 4 ans", "70 et plus"), so they are
        # matched as a pattern rather than split off as non-numeric words
        m = re.match(r"^(\d{1,2}\s*à\s*\d{1,2}(?:\s*ans)?|\d{2}\s*(?:ans\s*)?"
                     r"et plus)\s+(\d.*)$", ln)
        if m:
            lab, toks = m.group(1), m.group(2).split()
        else:
            lab, toks = _label_and_tokens(ln)
        if lab == "Total":
            age = "Total"
        else:
            age = _band(lab)
            if age is None or age in ("0-14",):
                continue
            # the wide groups ("Moins de 20 ans", "20 à 59 ans", "60 à 69 ans")
            # are where 1990 does not add up -- bands and 70+ only
            if lab.startswith(("Moins", "20 à 59", "60 à 69")):
                continue
        if not toks or age in seen:
            continue
        n_tr = len(toks) and (4 if len(toks) >= 12 else 3)
        sol = None
        for nt in (4, 3):
            sol = _triples(toks, nt, 3)
            if sol:
                break
        if not sol:
            # "80 ans et plus" / "70 à 74": 2024-only rows, read from T1.08
            continue
        seen.add(age)
        for k, y in enumerate(years):
            t, m, f = sol[3 * k:3 * k + 3]
            for sex, v in (("total", t), ("male", m), ("female", f)):
                out.append(_row(sex, age, "Total country", y, v,
                                code=f"BI_RGPH_{y}"))
    if "Total" not in seen or "0-4" not in seen or "70+" not in seen:
        raise ValueError(f"INSBU T1.09: rows read {sorted(seen)}")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    lines = _lines(path)
    out: list[dict] = []
    _t101(lines, out)
    _t102(lines, out)
    _t108(lines, out)
    _t109(lines, out)
    df = pd.DataFrame(out)
    key = ["series_type", "sex", "age_group", "geography", "period", "measure"]
    dup = df[df.duplicated(key, keep=False)]
    if len(dup) and (dup.groupby(key)["value"].nunique() > 1).any():
        raise ValueError("INSBU: one key carries two different values")
    return df.drop_duplicates(key).reset_index(drop=True)
