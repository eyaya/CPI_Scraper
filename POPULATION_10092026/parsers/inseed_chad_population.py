"""INSEED Chad — Annuaire Statistique National, chapter "Population":
official projections based on the RGPH2 (2009) census.

Each yearbook edition reprints the projections for two adjacent years:

* Tableau 3/4  national population by sex and by milieu (Urbain / Rural);
* Tableau 7/8  national population by 5-year age group x sex;
* Tableaux 5-6 / 6-7  the same for the urban and the rural population;
* Tableau 8    population by PROVINCE x sex (2019-20 and 2021 editions only).

Editions 2019-20, 2021, 2022, 2023 and 2024 are read (years 2019-2024). Where two
editions print the same year, the NEWER edition wins (files are read oldest
first; later rows replace earlier ones on the merge key).

NOT READ: the single-year age table (Tableau 4/5). Its sex headers contradict
its own data between editions -- the 2021 edition heads it "Total Féminin
Masculin" over the very numbers the 2019-20 edition heads "Masculin Féminin
Total", and in both the first column is the sum of the other two -- so which
column is male cannot be read off the page. The 5-year tables carry a consistent
"Total Hommes/Masculin Femmes/Féminin" header in every edition.

NUMBERS USE SPACE THOUSANDS SEPARATORS, so "2 755 200 1 425 206 1 329 994"
reads several ways. Every row is split under the table's own arithmetic
(Total = Hommes + Femmes, Urbain + Rural = Total) and a row with no unique
consistent split raises. One glitch is repaired first: the 2023 edition prints
"17 414717" (a lost separator), so a digit run longer than three whose length
is a multiple of three is regrouped.

LABELS AND NUMBERS ARE ON DIFFERENT LINES in the urban/rural tables (the band
label is typeset a line below its figures), so bands are read as two ordered
lists -- the numeric rows and the band labels of the region -- and paired in
order; the counts must match exactly.

PUBLISHED INCONSISTENCY KEPT, NOT RECONCILED: in the 2019-20 and 2021 editions
the age-band tables' "Total" (national 2020: 16 063 434; urban 2019: 3 816 030)
is below the headline Tableau 3 (16 244 513; 3 855 240) for the same year. The headline (Tableau 3) total is the
one emitted as the national count; the band table's own Total row is checked
against the sum of its bands and not emitted, so its bands sum to a figure the
headline does not. The 2022-2024 editions agree with themselves.

PROVINCE NAMES: the 2021 edition's text layer drops interior spaces
("LogoneOccidental", "BarhElGazel") and the editions disagree on accents
("N'Djaména" / "N’Djamena"). These are text-layer and typesetting variants of
one province, so each is mapped to the spelling of the 2019-20 edition (which
the text layer renders with its spaces); names otherwise as printed, including
"Wadi-ira" (sic). Urban and rural are carried as geography "Urbain" / "Rural"
(milieu de résidence, as published) -- they overlap the national total and the
provinces and must not be summed with them.

THE 2021 EDITION'S "05-sept" AND "oct-14" bands are Excel date artefacts of
5-9 and 10-14, and the 2022 edition's urban "4-9" is a misprint of 5-9; all
three are mapped back by position (see `_EXCEL_DATES`, `_MISPRINTS`).

CROSS-CHECK: 2024 total 18 675 547 (M 9 348 740, F 9 326 807), urban 4 836 967;
2023 0-4 3 512 072; 2020 Batha 689 835; 2019 total 15 692 969.
"""
from __future__ import annotations

import itertools
import re
import unicodedata

import pandas as pd
import pdfplumber

_NUM_TOK = re.compile(r"^\d+$")
_BAND = re.compile(r"^(\d{1,2}\s*-\s*\d{1,2}|80\s*\+|Total)$")
_CAP_SEXMIL = re.compile(r"Population totale du Tchad (?:en|de)\s.*sexe et (?:par )?milieu", re.I)
_CAP_BANDS = re.compile(r"Population totale (urbaine |rurale )?du Tchad .*groupe d", re.I)
_CAP_PROV = re.compile(r"Population totale du Tchad .*par province", re.I)
_YEARS = re.compile(r"\b(20\d\d)\b")
_SERIES = "TD_PROJ_RGPH2"
# EXCEL DATE ARTEFACTS: the 2021 edition prints the bands "5-9" and "10-14" as
# "05-sept" and "oct-14" -- Excel turned them into dates before the table was
# set. Their place in the sequence (between 0-4 and 15-19) settles what they
# are; these two strings, and only these, are mapped back.
_EXCEL_DATES = {"05-sept": "5-9", "oct-14": "10-14"}
# A MISPRINT, mapped the same way: the 2022 edition's urban table labels its
# second band "4-9" (617 586 in 2021), which as printed overlaps 0-4. It sits
# between 0-4 and 10-14 and the other editions print 5-9 there. Checked by
# position in `_bands` -- the mapping applies only as the second band.
_MISPRINTS = {"4-9": "5-9"}
_FURNITURE = re.compile(
    r"^(ANNUAIRE STATISTIQUE NATIONAL DU TCHAD|L.Institut National de la Statistique|"
    r"Avenue du G|T[ée]+l\s*:|Site web|\d{1,3}$)")


def _norm_key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[\s'’\-]", "", s).lower()


def _tokens(text: str) -> list[str]:
    out = []
    for t in text.split():
        if _NUM_TOK.match(t) and len(t) > 3 and len(t) % 3 == 0:
            out += [t[i:i + 3] for i in range(0, len(t), 3)]   # "414717"
        else:
            out.append(t)
    return out


def _numbers(tokens: list[str]):
    """All ways of grouping digit tokens into space-separated numbers."""
    if not tokens:
        yield []
        return
    if not _NUM_TOK.match(tokens[0]) or len(tokens[0]) > 3:
        return
    for k in range(1, len(tokens) + 1):
        grp = tokens[:k]
        if any(len(g) != 3 or not _NUM_TOK.match(g) for g in grp[1:]):
            break
        for rest in _numbers(tokens[k:]):
            yield [int("".join(grp))] + rest


def _split_triples(tokens: list[str], n: int) -> list[int] | None:
    """Split into `n` numbers forming (T, A, B) triples with T = A + B.

    INSEED's projections are rounded per cell, so a triple can miss by ONE
    person (2019-20 urban 0-4, 2020: 309 798 + 324 196 = 633 994 vs 633 995).
    An exact split is preferred; failing that, one within 2 persons -- and
    either way it must be the ONLY such split."""
    cands = [c for c in _numbers(tokens) if len(c) == n]
    for tol in (0, 2):
        sols = {tuple(c) for c in cands if all(
            abs(c[i] - c[i + 1] - c[i + 2]) <= tol for i in range(0, n, 3))}
        if len(sols) == 1:
            return list(sols.pop())
        if len(sols) > 1:
            return None
    return None


def _region(lines: list[str], start: int) -> list[str]:
    out = []
    for ln in lines[start + 1:]:
        if ln.startswith("Source") or re.match(r"Tableau\s*\d", ln):
            break
        out.append(ln)
    return out


def _years(caption_lines: str) -> list[str]:
    ys = []
    for y in _YEARS.findall(caption_lines):
        if y not in ys:
            ys.append(y)
    return ys


def _row(series_type, sex, age, geo, period, value, code):
    return {"series_type": series_type, "sex": sex, "age_group": age,
            "geography": geo, "period": period, "frequency": "annual",
            "measure": "count", "value": float(value), "unit": "persons",
            "series_code": code}


def _sex_order(header: str) -> tuple[str, str]:
    """('male','female') if the header puts Hommes/Masculin before
    Femmes/Féminin; the other way round otherwise."""
    h = header.lower()
    m = min((h.find(w) for w in ("hommes", "masculin") if w in h), default=-1)
    f = min((h.find(w) for w in ("femmes", "féminin", "feminin") if w in h), default=-1)
    if m < 0 or f < 0:
        raise ValueError(f"INSEED: no sex header in {header!r}")
    return ("male", "female") if m < f else ("female", "male")


def _sexmil(region: list[str], edition: str, out: list):
    for ln in region:
        m = re.match(r"^(20\d\d)\s+(.*)$", ln)
        if not m:
            continue
        toks = [t for t in _tokens(m.group(2)) if t != "-"]
        # drop the "% des femmes" / "% urbain" cells (with a comma, or 1-2
        # digit integers placed after a total) by trying both and keeping the
        # split that satisfies M + F = T = U + R.
        best = []
        cand = [i for i, t in enumerate(toks) if re.fullmatch(r"\d{1,2}(?:,\d+)?", t)]
        for drop in itertools.product([False, True], repeat=len(cand)):
            gone = {i for i, d in zip(cand, drop) if d}
            keep = [t for i, t in enumerate(toks) if i not in gone]
            if any("," in t for t in keep):
                continue
            for c in _numbers(keep):
                # Urbain + Rural misses the Total by ONE person in 2020
                # (4 034 054 + 12 210 460 = 16 244 514 vs 16 244 513, both
                # editions) -- rounding in INSEED's own figures, allowed for.
                if len(c) == 6 and c[0] + c[1] == c[2] \
                        and abs(c[3] + c[4] - c[5]) <= 1 and c[2] == c[5]:
                    best.append((len(gone), tuple(c)))
        # Dropping the leading 1-2 digit group of EVERY number also "balances"
        # (103 402 + 141 111 = 244 513); the percent cells are the FEWEST
        # tokens whose removal leaves a consistent row.
        fewest = min((g for g, _ in best), default=None)
        best = {c for g, c in best if g == fewest}
        if len(best) != 1:
            raise ValueError(f"INSEED {edition}: cannot split {ln!r} ({len(best)})")
        mm, ff, tt, uu, rr, _ = best.pop()
        y = m.group(1)
        for sex, v in (("male", mm), ("female", ff), ("total", tt)):
            out.append(_row("projection", sex, "Total", "Total country", y, v, _SERIES))
        out.append(_row("projection", "total", "Total", "Urbain", y, uu, _SERIES))
        out.append(_row("projection", "total", "Total", "Rural", y, rr, _SERIES))


def _bands(region: list[str], caption: str, years: list[str], edition: str,
           out: list):
    kind = "Urbain" if "urbaine" in caption.lower() else (
        "Rural" if "rurale" in caption.lower() else "Total country")
    header = next(ln for ln in region if re.search(r"Total\s", ln) and
                  re.search(r"(Hommes|Masculin)", ln))
    if not header.strip().startswith("Total"):
        raise ValueError(f"INSEED {edition}: band header not Total-first: {header!r}")
    sex = _sex_order(header)
    labels, nums = [], []
    for ln in region:
        if ln == header:
            continue
        # "5- 9" / "80 +": a band label split by a stray space
        ln = re.sub(r"^(\d{1,2})\s*-\s*(\d{1,2})(?=\s|$)", r"\1-\2", ln)
        ln = re.sub(r"^80\s*\+", "80+", ln)
        toks = _tokens(ln)
        lab = []
        while toks and not _NUM_TOK.match(toks[0]):
            lab.append(toks.pop(0))
        label = _EXCEL_DATES.get(" ".join(lab), " ".join(lab))
        if label and not _BAND.match(label):
            # "0-4" may also sit alone at the start; "Groupe d'âges" etc. skip
            label = ""
        if label:
            label = re.sub(r"\s+", "", label)
            if label in _MISPRINTS:
                if labels != ["0-4"]:
                    raise ValueError(f"INSEED {edition} {kind}: {label!r} is "
                                     f"not the second band -- re-check")
                label = _MISPRINTS[label]
            labels.append(label)
        if len(toks) >= 6 and all(_NUM_TOK.match(t) for t in toks):
            split = _split_triples(toks, 6)
            if split is None:
                raise ValueError(f"INSEED {edition}: cannot split band row {ln!r}")
            nums.append(split)
    if len(labels) != len(nums):
        raise ValueError(f"INSEED {edition} {kind}: {len(labels)} labels for "
                         f"{len(nums)} rows")
    if labels[-1] != "Total":
        raise ValueError(f"INSEED {edition} {kind}: last row {labels[-1]!r}")
    *bands, total = list(zip(labels, nums))
    # Bands are rounded per cell, so their sum may miss the printed Total by
    # a few persons (2019 urban: 3 816 029 vs 3 816 030); one per band is
    # allowed. A wider gap means a misread row.
    for j in range(6):
        s = sum(r[1][j] for r in bands)
        if abs(s - total[1][j]) > len(bands):
            raise ValueError(f"INSEED {edition} {kind}: column {j} sums {s} "
                             f"vs Total {total[1][j]}")
    for lab, vals in bands:
        for yi, y in enumerate(years[:2]):
            t, a, b = vals[3 * yi:3 * yi + 3]
            for s, v in (("total", t), (sex[0], a), (sex[1], b)):
                out.append(_row("projection", s, lab, kind, y, v, _SERIES))
    # The band tables' own Total rows are NOT emitted: in the 2019-20 and 2021
    # editions they disagree with the headline Tableau 3 for the same year
    # (urban 2019: 3 816 030 here vs 3 855 240 there), and the headline is
    # what the national and milieu totals are taken from.


def _provinces(region: list[str], years: list[str], edition: str, out: list,
               canon: dict):
    header = next(ln for ln in region if re.search(r"Masculin", ln))
    sex = _sex_order(header)
    pending, rows = "", []
    for ln in region:
        if ln == header or re.match(r"^(Province|20\d\d)\b", ln):
            continue
        toks = _tokens(ln)
        lab = []
        while toks and not _NUM_TOK.match(toks[0]):
            lab.append(toks.pop(0))
        if len(toks) >= 6:
            split = _split_triples_ab(toks, edition, ln)
            rows.append([(pending + " ".join(lab)).strip(), split])
            pending = ""
        elif lab and not toks:
            if rows and not rows[-1][0]:
                rows[-1][0] = " ".join(lab)
            elif rows and rows[-1][0].endswith("-"):
                rows[-1][0] += " ".join(lab)
            else:
                pending = " ".join(lab)
    for lab, vals in rows:
        if not lab:
            raise ValueError(f"INSEED {edition}: province row without a name {vals}")
    total = [r for r in rows if r[0].lower().startswith("total")]
    provs = [r for r in rows if not r[0].lower().startswith("total")]
    if total:
        for j in range(6):
            s = sum(r[1][j] for r in provs)
            # per-cell rounding, as for the bands: one person per province
            if abs(s - total[0][1][j]) > len(provs):
                raise ValueError(f"INSEED {edition}: provinces sum {s} vs "
                                 f"Total {total[0][1][j]} (col {j})")
    for lab, vals in provs:
        key = _norm_key(lab)
        name = canon.setdefault(key, lab)
        for yi, y in enumerate(years[:2]):
            a, b, t = vals[3 * yi:3 * yi + 3]
            for s, v in ((sex[0], a), (sex[1], b), ("total", t)):
                out.append(_row("projection", s, "Total", name, y, v, _SERIES))


def _split_triples_ab(toks, edition, ln):
    """Province rows print (A, B, T) per year: T last. Same rounding rule."""
    cands = [c for c in _numbers(toks) if len(c) == 6]
    for tol in (0, 2):
        sols = {tuple(c) for c in cands if all(
            abs(c[i] + c[i + 1] - c[i + 2]) <= tol for i in (0, 3))}
        if len(sols) == 1:
            return list(sols.pop())
        if len(sols) > 1:
            break
    raise ValueError(f"INSEED {edition}: cannot split province row {ln!r}")


def _edition_year(path: str, text: str) -> str:
    m = re.search(r"ANNUAIRE STATISTIQUE NATIONAL DU TCHAD[_ ]*(20\d\d(?:-20\d\d)?)", text)
    return m.group(1) if m else path


def _parse_one(path: str, canon: dict) -> list[dict]:
    out: list[dict] = []
    with pdfplumber.open(path) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages[:70]]
    edition = _edition_year(path, pages[0] + pages[1] if len(pages) > 1 else pages[0])
    seen = set()
    # Tables run across page breaks, so the pages are read as ONE stream with
    # the running header and the institutional footer removed.
    lines = [ln.strip() for text in pages for ln in text.splitlines()
             if ln.strip() and not _FURNITURE.search(ln.strip())]
    if True:
        for i, ln in enumerate(lines):
            joined = ln + " " + (lines[i + 1] if i + 1 < len(lines) else "")
            if "...." in joined or not ln.startswith("Tableau"):
                continue
            if _CAP_SEXMIL.search(joined) and "sexmil" not in seen:
                seen.add("sexmil")
                _sexmil(_region(lines, i), edition, out)
            elif _CAP_PROV.search(joined) and "prov" not in seen:
                seen.add("prov")
                _provinces(_region(lines, i + 1), _years(joined), edition, out, canon)
            elif _CAP_BANDS.search(joined):
                tag = "bands-" + ("u" if "urbaine" in joined else
                                  "r" if "rurale" in joined else "n")
                if tag in seen:
                    continue
                seen.add(tag)
                region = _region(lines, i)
                # a wrapped caption's tail is the first region line
                region = [r for r in region if not r.lower().startswith(
                    ("le sexe", "selon le", "sexe"))]
                _bands(region, joined, _years(joined), edition, out)
    for need in ("sexmil", "bands-n", "bands-u", "bands-r"):
        if need not in seen:
            raise ValueError(f"INSEED {edition}: table {need} not found in {path}")
    return out


def _order(path: str) -> str:
    m = re.search(r"(20\d\d)", path.replace("1920", "2019-2020"))
    return m.group(1) if m else path


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = sorted([path, *(extras or [])], key=_order)   # oldest first
    canon: dict = {}
    rows: list[dict] = []
    for p in files:
        rows += _parse_one(p, canon)
    df = pd.DataFrame(rows)
    key = ["series_type", "sex", "age_group", "geography", "period", "measure"]
    return df.drop_duplicates(key, keep="last").reset_index(drop=True)
