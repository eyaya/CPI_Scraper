"""INS Guinée — RGPH-3 (2014) census structure and the RGPH-3 projections
2014-2040 (Tier-3 PDFs, stat-guinee.org).

TWO DOCUMENTS, TWO SERIES, NEVER MIXED:

* `RGPH3_etat_structure.pdf` -- the census (series_type `census`, period 2014):
    - Tableau A.05  resident population by PRÉFECTURE and sex (+ the printed
                    rapport de masculinité, as `sex_ratio`)
    - Tableau A.08  national population by five-year age group and sex
                    (+ sex ratio per age)
    - Tableaux A.09-A.16  each administrative REGION by age group and sex
                    (the "Ensemble" columns; the urban/rural split has no column
                    in this schema)
* `RGPH3_perspectives_demographiques.pdf` (extra) -- the projections
  (series_type `projection`, 1 July of each year 2014-2040):
    - Tableaux 14-19  national population by age group, total / male / female
    - Tableaux 30-38  regions and préfectures by sex, three years per table

REGION AND PRÉFECTURE SHARE NAMES (Boké, Faranah, Kankan, Kindia, Labé, Mamou
are both), and `geography` is in the merge key, so the level is written into
the name: "Région de Boké" vs "Préfecture de Boké". Conakry is a region with a
single préfecture of the same extent; both are kept as published. Regions are
the SUMS of their préfectures -- do not add the two levels together (README,
"Overlapping geographies").

SPACE THOUSANDS, NO RELIABLE GAPS. "104 347 108 236 212 583" splits more than
one way, and the projection tables pack columns 2.5 pt apart -- the same gap as
inside a number -- so neither whitespace nor x-gaps can be trusted. Two
readings, each proved:

* count triples (male, female, total) are split under the table's own
  arithmetic: the token run must divide into exactly ONE well-formed triple
  with male + female = total, or the cell is refused (`_split_triples`);
* the age tables have no internal identity, so tokens are binned to the
  nearest column-header centre (numbers sit under their header), and each bin
  must be a well-formed space-grouped number; the three sex tables are then
  held to male + female = total for every age and year.

ROUNDING, PUBLISHED: the projections are rounded sex by sex, so male + female
misses the printed total by exactly 1 in some cells (0-4 ans 2015: 993 421 +
959 842 = 1 953 263 against 1 953 264). A residue of 1 is accepted, kept as
printed and never "corrected"; anything larger raises. The census tables add
up exactly and are held to that.

LETTER-SPACED DIGITS, REJOINED: Tableau 38 prints the national 2038-2040
values as "1 0 078 611" (10 078 611); see `_rejoin_letterspaced` for the
narrow rule and why the arithmetic still decides.

A PUBLISHED DEFECT, REFUSED: in Tableau 31 the "Guinée" row prints with
overlapping glyphs -- "5 590 7975 964 264 11 555 0615 …" -- for 2017-2018. The
values could be reconstructed by arithmetic (5 590 797 + 5 964 264 =
11 555 061) but that would be reading what is not printed; malformed cells
yield no valid split and are dropped (counted in the run log); well-formed
years on the same row are kept.

NOT READ: Tableau 3.03 (shares only; A.08 gives the counts), the urban/rural
and milieu-by-préfecture tables (no locality column here), sub-préfecture
projections (Tableaux 45-53, 90+: a finer level than this indicator carries),
the Annuaire 2024 Tableau 3.26 (a reprint of these same projections; an earlier
unregistered reader of it, which grouped rows by y-bucket rounding -- README
trap 5 -- is replaced by this module), and the RGPH-4 preliminary report
(overlapping analytical bands only -- see README).

CROSS-CHECK: census total 10 523 261 (5 084 306 M / 5 438 955 F); Préfecture
de Boké 450 278; Conakry 1 660 973; 0-4 ans 1 764 144. Projection 2014 0-4 ans
1 916 997; Région de Boké 2017 1 190 724; Guinée 2019 12 218 357.
"""
from __future__ import annotations

import re
import sys

import pandas as pd
import pdfplumber

_NUM_TOKEN = re.compile(r"^\d{1,3}$")
_GROUP = re.compile(r"^\d{3}$")
_REGIONS = ["Boké", "Conakry", "Faranah", "Kankan", "Kindia", "Labé", "Mamou",
            "N'Zérékoré"]


def _rec(series, sex, age, geo, period, measure, value, unit, code):
    return {"series_type": series, "sex": sex, "age_group": age,
            "geography": geo, "period": str(period), "frequency": "annual",
            "measure": measure, "value": float(value), "unit": unit,
            "series_code": code}


def _numbers(tokens):
    """All ways to read a token run as well-formed space-grouped integers."""
    if not tokens:
        yield []
        return
    for k in range(1, min(len(tokens), 4) + 1):
        head, rest = tokens[:k], tokens[k:]
        if not _NUM_TOKEN.match(head[0]) or not all(_GROUP.match(t) for t in head[1:]):
            continue
        if head[0].startswith("0") and head[0] != "0":
            continue
        for tail in _numbers(rest):
            yield [int("".join(head))] + tail


def _split_triples(tokens, n_triples, tol=0):
    """The unique split of `tokens` into n (male, female, total) triples with
    |male + female - total| <= tol; None if there is none or more than one.
    `tol` is 0 for the census and 1 for the projections, which INS rounds
    sex by sex (see the module docstring)."""
    sols = []
    for nums in _numbers(tokens):
        if len(nums) != 3 * n_triples:
            continue
        if all(abs(nums[3 * i] + nums[3 * i + 1] - nums[3 * i + 2]) <= tol
               for i in range(n_triples)):
            sols.append(nums)
            if len(sols) > 1:
                return None
    return sols[0] if sols else None


def _norm_age(label):
    s = label.replace("10t", "10")
    m = re.search(r"(\d{1,2})\s*(?:à|a)\s*(\d{1,2})", s)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2))}"
    m = re.search(r"(\d{1,2})\s*(?:ans)?\s*et\s*(?:plus|\+)", s)
    if m:
        return f"{int(m.group(1))}+"
    return None


# --------------------------------------------------------------------------
# census (État et structure)
# --------------------------------------------------------------------------

def _table_lines(pages, caption):
    for t in pages:
        m = re.search(caption, t)
        if m:
            return t[m.end():].splitlines()
    raise ValueError(f"Guinea census: {caption!r} not found")


def _split_label(line):
    toks = line.split()
    i = 0
    while i < len(toks) and not re.fullmatch(r"\d+(,\d+)?", toks[i]):
        i += 1
    return " ".join(toks[:i]), toks[i:]


_AGE_ROW = re.compile(r"^\s*(\d{1,2}\s*à\s*\d{1,2}\s*ans|\d{1,2}\s*ans\s*et\s*(?:plus|\+))"
                      r"\s+(.*)$|^\s*(Total|ENSEMBLE|Ensemble)\s+(.*)$")


def _age_line(line):
    """(age_group, value tokens) for an age row -- whose label itself starts
    with digits ("0 à 4 ans 890 034 ...") -- or (None, None)."""
    m = _AGE_ROW.match(line)
    if not m:
        return None, None
    if m.group(1):
        return _norm_age(m.group(1)), m.group(2).split()
    return "Total", m.group(4).split()


def _census(path):
    with pdfplumber.open(path) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages[100:]]
    out, code = [], "GN_RGPH3_2014"

    # A.05 -- préfectures by sex. A region name either sits on its own line or
    # prefixes the block's middle préfecture ("Boké Fria ..."), so it is
    # stripped from the front of the label.
    prefs = 0
    for ln in _table_lines(pages, r"Tableau A\.05"):
        label, toks = _split_label(ln)
        if not toks:
            continue
        trip = _split_triples([t for t in toks if "," not in t], 1)
        if trip is None:
            continue
        for r in _REGIONS:
            if label.startswith(r + " ") and label != r:
                label = label[len(r) + 1:]
        if label.upper() == "ENSEMBLE":
            geo = "Total country"
        else:
            geo = f"Préfecture de {label}"
            prefs += 1
        for sex, v in zip(("male", "female", "total"), trip):
            out.append(_rec("census", sex, "Total", geo, 2014, "count", v,
                            "persons", code + "_A.05"))
        ratios = [t for t in toks if "," in t]
        if ratios:
            out.append(_rec("census", "total", "Total", geo, 2014, "sex_ratio",
                            float(ratios[0].replace(",", ".")), "ratio",
                            code + "_A.05"))
        if geo == "Total country":
            break
    # 33 préfectures + Conakry (a special zone printed as its own line); they
    # must add up to the printed ENSEMBLE exactly, for each sex.
    tot = {s: sum(r["value"] for r in out if r["series_code"].endswith("A.05")
                  and r["measure"] == "count" and r["sex"] == s
                  and r["geography"] != "Total country") for s in ("male", "female", "total")}
    nat = {r["sex"]: r["value"] for r in out if r["series_code"].endswith("A.05")
           and r["measure"] == "count" and r["geography"] == "Total country"}
    if prefs != 34 or tot != nat:
        raise ValueError(f"Guinea A.05: {prefs} préfectures summing to {tot}, "
                         f"national {nat}")

    # A.08 -- national age x sex (+ sex ratio per age)
    ages = 0
    for ln in _table_lines(pages, r"Tableau A\.0\s*8"):
        age, toks = _age_line(ln)
        if age == "Total":
            break
        if not age:
            continue
        trip = _split_triples([t for t in toks if "," not in t], 1)
        if trip is None:
            raise ValueError(f"Guinea A.08: cannot split {ln!r}")
        ages += 1
        for sex, v in zip(("male", "female", "total"), trip):
            out.append(_rec("census", sex, age, "Total country", 2014, "count",
                            v, "persons", code + "_A.08"))
        ratio = [t for t in toks if "," in t]
        if ratio:
            out.append(_rec("census", "total", age, "Total country", 2014,
                            "sex_ratio", float(ratio[0].replace(",", ".")),
                            "ratio", code + "_A.08"))
    if ages != 20:
        raise ValueError(f"Guinea A.08: read {ages} age groups, expected 20")

    # A.09-A.16 -- regions by age x sex, "Ensemble" (last) triple. Conakry
    # (A.10) is wholly urban and prints only Urbain + Ensemble.
    for num, region in zip(range(9, 17), _REGIONS):
        cap = rf"Tableau A\.\s*0?\s*{num}\s*:" if num == 9 else rf"Tableau A\.{num}\s*:"
        n_trip = 2 if region == "Conakry" else 3
        got = 0
        for ln in _table_lines(pages, cap):
            if ln.startswith("Tableau"):
                break
            age, toks = _age_line(ln)
            if not age:
                continue
            nums = _split_triples(toks, n_trip)
            if nums is None:
                raise ValueError(f"Guinea A.{num:02d}: cannot split {ln!r}")
            m, f, t = nums[-3:]
            if n_trip == 3 and nums[2] + nums[5] != t:
                raise ValueError(f"Guinea A.{num:02d}: urban + rural != total in {ln!r}")
            got += 1
            for sex, v in zip(("male", "female", "total"), (m, f, t)):
                out.append(_rec("census", sex, age, f"Région de {region}", 2014,
                                "count", v, "persons", f"{code}_A.{num:02d}"))
            if age == "Total":
                break
        if got != 21:
            raise ValueError(f"Guinea A.{num:02d}: read {got} rows, expected 21")
    return out


# --------------------------------------------------------------------------
# projections (Perspectives démographiques)
# --------------------------------------------------------------------------

def _rows(page, gap=3.5):
    """Words clustered into rows by vertical distance (README trap 5)."""
    words = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))
    rows, cur, last = [], [], None
    for w in words:
        if last is not None and w["top"] - last > gap:
            rows.append(sorted(cur, key=lambda x: x["x0"]))
            cur = []
        cur.append(w)
        last = w["top"]
    if cur:
        rows.append(sorted(cur, key=lambda x: x["x0"]))
    return rows


def _age_tables(pdf):
    """Tableaux 14-19: years down, age groups across -> {(sex, age, year): v}."""
    sexes = {14: "total", 15: "total", 16: "male", 17: "male", 18: "female",
             19: "female"}
    vals = {}
    for page in pdf.pages[40:60]:
        text = page.extract_text() or ""
        m = re.search(r"Tableau (1[4-9]) : Répartition de la population", text)
        if not m:
            continue
        tab = int(m.group(1))
        rows = _rows(page)
        header = next(r for r in rows if r and r[0]["text"] == "Année")
        groups, cur = [], [header[1]]
        for w in header[2:]:
            if w["x0"] - cur[-1]["x1"] > 8:
                groups.append(cur)
                cur = [w]
            else:
                cur.append(w)
        groups.append(cur)
        cols = [(_norm_age(" ".join(w["text"] for w in g)),
                 (g[0]["x0"] + g[-1]["x1"]) / 2) for g in groups]
        if any(a is None for a, _ in cols):
            raise ValueError(f"Guinea T{tab}: unreadable header {cols}")
        for r in rows:
            # a year row carries only numbers after the year -- a wrapped
            # caption line "2014 à 2040 (voir suite)" also starts with a year
            if not re.fullmatch(r"20[1-4]\d", r[0]["text"]) or not all(
                    re.fullmatch(r"\d{1,3}", w["text"]) for w in r[1:]):
                continue
            year = int(r[0]["text"])
            bins = {a: [] for a, _ in cols}
            for w in r[1:]:
                cx = (w["x0"] + w["x1"]) / 2
                bins[min(cols, key=lambda c: abs(c[1] - cx))[0]].append(w["text"])
            for a, toks in bins.items():
                nums = [n for n in _numbers(toks) if len(n) == 1]
                if len(nums) != 1:
                    raise ValueError(f"Guinea T{tab} {year} {a}: {toks}")
                vals[(sexes[tab], a, year)] = nums[0][0]
    return vals


def _region_tables(pdf):
    """Tableaux 30-38: préfectures and regions by sex, three years per table.
    A region's label wraps around its numbers ("Région" / numbers / "Boké")."""
    out, dropped, tables = [], 0, 0
    for page in pdf.pages[55:70]:
        text = page.extract_text() or ""
        m = re.search(r"Tableau (3[0-8]) : Répartition de la population des "
                      r"régions administratives et des préfectures", text)
        if not m or "milieu de" in text[m.end():m.end() + 160]:
            continue
        tables += 1
        rows = _rows(page)
        yrow = next(r for r in rows if len(r) == 3
                    and all(re.fullmatch(r"20[1-4]\d", w["text"]) for w in r))
        years = [int(w["text"]) for w in yrow]
        cen = [(w["x0"] + w["x1"]) / 2 for w in yrow]
        bounds = [(cen[0] + cen[1]) / 2, (cen[1] + cen[2]) / 2]
        pending = None
        for r in rows[rows.index(yrow) + 1:]:
            label = " ".join(w["text"] for w in r if not w["text"][0].isdigit())
            toks = _rejoin_letterspaced([w for w in r if w["text"][0].isdigit()])
            if label.startswith(("PERSPECTIVES", "Institut")) or (toks and len(toks) < 3):
                continue                       # running head / page number
            if not toks:
                if pending is not None and label and label != "Région":
                    _emit(out, f"Région de {label.replace('’', chr(39))}", pending)
                    pending = None
                continue
            blocks = [[], [], []]
            for w in toks:
                cx = (w["x0"] + w["x1"]) / 2
                blocks[0 if cx < bounds[0] else (1 if cx < bounds[1] else 2)].append(w["text"])
            trip = {}
            for y, b in zip(years, blocks):
                t = _split_triples(b, 1, tol=1)
                if t is None:
                    dropped += 1
                else:
                    trip[y] = t
            if not label:
                pending = trip
            elif label == "Guinée":
                _emit(out, "Total country", trip)
            elif label not in ("Préfecture", "Masculin Féminin Total Masculin "
                                              "Féminin Total Masculin Féminin Total"):
                _emit(out, f"Préfecture de {label}", trip)
    if tables != 9:
        raise ValueError(f"Guinea projections: {tables} region tables, expected 9")
    if dropped:
        print(f"[guinea] projections: {dropped} malformed cell(s) refused "
              f"(overlapping glyphs in the printed table)", file=sys.stderr)
    return out


def _rejoin_letterspaced(words):
    """Tableau 38 letter-spaces a two-digit leading group: "1 0 078 611" is
    10 078 611, the "1" and "0" touching (gap 0.0). Merge two touching
    single-digit tokens ONLY when a 3-digit group follows; the male + female
    = total split must still be unique afterwards, so a wrong merge cannot
    pass."""
    out, i = [], 0
    while i < len(words):
        w = words[i]
        if (i + 2 < len(words) and len(w["text"]) == 1 and w["text"].isdigit()
                and len(words[i + 1]["text"]) == 1 and words[i + 1]["text"].isdigit()
                and words[i + 1]["x0"] - w["x1"] < 0.5
                and len(words[i + 2]["text"]) == 3):
            out.append({**w, "text": w["text"] + words[i + 1]["text"],
                        "x1": words[i + 1]["x1"]})
            i += 2
            continue
        out.append(w)
        i += 1
    return out


def _emit(out, geo, trip):
    for y, triple in trip.items():
        for sex, v in zip(("male", "female", "total"), triple):
            out.append(_rec("projection", sex, "Total", geo, y, "count", v,
                            "persons", "GN_RGPH3_PROJ_T30-38"))


def _projections(path):
    with pdfplumber.open(path) as pdf:
        ages = _age_tables(pdf)
        regions = _region_tables(pdf)
    bad = [(a, y) for (s, a, y) in ages if s == "total"
           and abs(ages.get(("male", a, y), -9) + ages.get(("female", a, y), -9)
                   - ages[(s, a, y)]) > 1]
    if bad:
        raise ValueError(f"Guinea projections: male + female != total at {bad[:5]}")
    n_years = len({y for (_, _, y) in ages})
    if n_years != 27:
        raise ValueError(f"Guinea projections: {n_years} years by age, expected 27")
    out = [_rec("projection", s, a, "Total country", y, "count", v, "persons",
                "GN_RGPH3_PROJ_T14-19") for (s, a, y), v in ages.items()]
    return out + regions


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = _census(local_path)
    for p in extras or []:
        if "perspective" in p.lower():
            rows += _projections(p)
    df = pd.DataFrame(rows)
    key = ["series_type", "sex", "age_group", "geography", "period", "measure"]
    dup = df[df.duplicated(key, keep=False)]
    if len(dup):
        clash = dup.groupby(key)["value"].nunique()
        if (clash > 1).any():
            raise ValueError("Guinea: conflicting values for "
                             f"{clash[clash > 1].index[:3].tolist()}")
        df = df.drop_duplicates(key)
    return df
