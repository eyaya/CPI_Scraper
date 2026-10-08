"""ANSADE Mauritania — RGPH-5 (2023) census, earlier census rounds, and the
2023-2053 projections (Tier-3 PDFs from ANSADE's catalogue API).

Primary, RGPH-5 Thème 2 "Structure par sexe et par âge" (census, 2023):
* Tableau A.2.3       national population by age group and sex;
* Tableaux A.2.4-18   the same for each of the 15 wilayas.

Extra, RGPH-5 Thème 1 "État et répartition spatiale" -- Tableau A.1.2: each
wilaya's population at the 1988, 2000, 2013 and 2023 censuses (series_type
`census`, one period per round) and the printed intercensal growth rates
(`growth_rate`, dated to the END year of each interval). "Nouakchott global"
is printed beside its three wilayas (Ouest, Nord, Sud) for 2013 and 2023 and
alone for 1988/2000; it is kept as published -- never add it to its parts.

Extra, "Projections démographiques 2023-2053" (series_type `projection`): for every year 2023-2053 (section A) and each wilaya by age
x sex for every year printed (section D). The urban / rural sections (B, C)
have no column here.

READING. Counts are space-grouped and, in the projections, LETTER-SPACED in
places -- "3 4 002" is 34 002, "9 7 811" is 97 811 and "8 08 289" is
808 289 (touching glyphs split into two short tokens). Every row is therefore split under its own arithmetic: each (total,
male, female) triple must satisfy total = male + female (within 1 -- the
census and the projections both print 1-person residues, e.g. 70-74 ans:
28 133 + 26 903 = 55 036 against 55 037), with two adjacent single digits
allowed to join ONLY as the leading group of a number, and the reading must
be unique or the row raises. Tableau A.1.2 has no such identity, so its counts
are binned by the x-position of the year headers and then checked: each
year's wilayas must sum to "Mauritanie" (Nouakchott counted once), and the
2023 column must equal each wilaya's census total from Thème 2.

Age bands are ANSADE's own: the census splits "Moins d'un an" and "1-4"; the
projections print "0-4". Both kept as printed.

NOT READ: Thème 1's moughataa / commune table (finer than this indicator's
level), the density and urbanisation tables, and the projection's urban/rural
sections.

CROSS-CHECK: 2023 census 4 927 532 (2 375 470 M / 2 552 062 F); Hodh Chargui
625 644; 1988 census 1 864 236; projection 2053 11 010 691.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

# Thème 2's captions abbreviate one wilaya and misspell another; the names
# Tableau A.1.2 (and ANSADE's other tables) print are used, so one wilaya is
# one geography across both tables.
_CAPTION_NAMES = {"D. Nouadhibou": "Dakhlet Nouadhibou",
                  "Tris Zemmour": "Tiris Zemmour"}


def _rec(series, sex, age, geo, period, measure, value, unit, code):
    return {"series_type": series, "sex": sex, "age_group": age,
            "geography": geo, "period": str(period), "frequency": "annual",
            "measure": measure, "value": float(value), "unit": unit,
            "series_code": code}


def _numbers(tokens):
    """All readings of a token run as integers: 1-3 digits then 3-digit
    groups, a 4+-digit token as a whole number, and two adjacent single
    digits joined as a leading group (letter-spacing: "3 4 002")."""
    if not tokens:
        yield []
        return
    t0 = tokens[0]
    if re.fullmatch(r"\d{4,}", t0):
        for tail in _numbers(tokens[1:]):
            yield [int(t0)] + tail
        return
    heads = []
    for k in range(1, min(len(tokens), 3) + 1):
        h = tokens[:k]
        if re.fullmatch(r"\d{1,3}", h[0]) and all(re.fullmatch(r"\d{3}", t) for t in h[1:]):
            heads.append(("".join(h), k))
    # letter-spaced leading group: two short tokens that together make 2-3
    # digits ("3 4 002" -> 34 002, "8 08 289" -> 808 289), followed by
    # 3-digit groups. The row's own arithmetic must still pick ONE reading.
    # ... or a whole small number split in two ("8 61" -> 861: 1 961 + 861 =
    # 2 822 in Inchiri 25-29), so the join may stand with no groups after it.
    if (len(tokens) >= 2 and re.fullmatch(r"\d{1,2}", t0)
            and re.fullmatch(r"\d{1,2}", tokens[1]) and len(t0 + tokens[1]) <= 3):
        for k in range(2, min(len(tokens), 4) + 1):
            h = tokens[2:k]
            if all(re.fullmatch(r"\d{3}", t) for t in h):
                heads.append((t0 + tokens[1] + "".join(h), k))
    for num, k in heads:
        for tail in _numbers(tokens[k:]):
            yield [int(num)] + tail


def _triples(tokens, n, order="mft"):
    """Unique reading as n triples; order 'mft' (male, female, total) or
    'tmf' (total, male, female). Returns [(m, f, t), ...] or None."""
    sols = []
    for v in _numbers(tokens):
        if len(v) != 3 * n:
            continue
        trip = []
        for i in range(n):
            a, b, c = v[3 * i:3 * i + 3]
            m, f, t = (a, b, c) if order == "mft" else (b, c, a)
            if abs(m + f - t) > 1:
                break
            trip.append((m, f, t))
        else:
            sols.append(trip)
            if len(sols) > 1:
                return None
    return sols[0] if sols else None


def _age(label):
    s = label.strip().replace(" ", "")
    if s.lower().startswith("moins"):
        return "<1"
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2))}"
    m = re.fullmatch(r"(\d{1,2})\+", s)
    if m:
        return f"{int(m.group(1))}+"
    return "Total" if s == "Total" else None


_AGE_START = r"(Moins d'un an|Moins d’un an|\d{1,2}\s?-\s?\d{1,2}|\d{1,2}\+|Total)"


# --------------------------------------------------------------------------
# census, Thème 2
# --------------------------------------------------------------------------

def _theme2(path):
    out, totals = [], {}
    with pdfplumber.open(path) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]
    for t in pages:
        m = re.search(r"Tableau A\.2\.(\d+)\s*: Répartition de la population (?:totale|"
                      r"de la Wilaya (?:de l’|de l'|de |du |d’|d')?\s*([^,]+?))"
                      r"\s*par âge et par sexe", t)
        if not m or int(m.group(1)) < 3:
            continue
        geo = ("Total country" if m.group(2) is None
               else _CAPTION_NAMES.get(m.group(2).strip(), m.group(2).strip()))
        code = f"MR_RGPH5_A.2.{m.group(1)}"
        n = 0
        for ln in t[m.end():].splitlines():
            mm = re.match(rf"^{_AGE_START}\s+([\d ]+)$", ln.strip())
            if not mm:
                continue
            age = _age(mm.group(1))
            trip = _triples(mm.group(2).split(), 1, "mft")
            if trip is None:
                raise ValueError(f"Mauritania {code}: cannot split {ln!r}")
            (ml, fl, tl), = trip
            n += 1
            for sex, v in (("male", ml), ("female", fl), ("total", tl)):
                out.append(_rec("census", sex, age, geo, 2023, "count", v,
                                "persons", code))
            if age == "Total":
                totals[geo] = tl
                break
        if n != 19:                    # 18 age bands + Total
            raise ValueError(f"Mauritania {code}: {n} rows, expected 19")
    wilayas = [g for g in totals if g != "Total country"]
    # the 15 wilayas sum to 4 927 531 against the national 4 927 532 -- the
    # same 1-person residue the tables print throughout; more raises.
    if len(wilayas) != 15 or abs(sum(totals[w] for w in wilayas)
                                 - totals["Total country"]) > 1:
        raise ValueError(f"Mauritania Thème 2: {len(wilayas)} wilayas summing to "
                         f"{sum(totals[w] for w in wilayas)} vs {totals.get('Total country')}")
    return out, totals


# --------------------------------------------------------------------------
# census rounds, Thème 1 Tableau A.1.2
# --------------------------------------------------------------------------

def _theme1(path, totals_2023):
    out = []
    with pdfplumber.open(path) as pdf:
        page = next(p for p in pdf.pages
                    if re.search(r"Tableau A\.1\.\s*2\s+Evolution de la population",
                                 p.extract_text() or ""))
        words = page.extract_words()
    lines, cur, last = [], [], None
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if last is not None and w["top"] - last > 3:
            lines.append(sorted(cur, key=lambda x: x["x0"]))
            cur = []
        cur.append(w)
        last = w["top"]
    lines.append(sorted(cur, key=lambda x: x["x0"]))
    head = next(l for l in lines if [w["text"] for w in l[:4]] == ["1988", "2000", "2013", "2023"]
                or any(w["text"] == "1988" for w in l[:3]))
    years = [w for w in head if re.fullmatch(r"(1988|2000|2013|2023)", w["text"])][:4]
    cen = [((w["x0"] + w["x1"]) / 2, int(w["text"])) for w in years]
    rate_x = min(w["x0"] for w in head if "-" in w["text"])     # rate columns start
    rate_hdr = [w["text"] for w in head if re.fullmatch(r"\d{4}-\d{4}", w["text"])]
    counts = {}
    for l in lines[lines.index(head) + 1:]:
        label = " ".join(w["text"] for w in l if not re.match(r"^[\d,\-]", w["text"]))
        if not label or label.startswith("Source"):
            continue
        cnt = [w for w in l if re.fullmatch(r"\d+", w["text"]) and w["x1"] < rate_x - 2]
        rates = [w for w in l if w["x0"] >= rate_x - 2 and re.fullmatch(r"-?\d+(,\d+)?|-", w["text"])]
        bins = {y: [] for _, y in cen}
        for w in cnt:
            cx = (w["x0"] + w["x1"]) / 2
            bins[min(cen, key=lambda c: abs(c[0] - cx))[1]].append(w["text"])
        row = {}
        for y, toks in bins.items():
            if not toks:
                continue
            reads = [v for v in _numbers(toks) if len(v) == 1]
            if len(reads) != 1:
                raise ValueError(f"Mauritania A.1.2 {label} {y}: {toks}")
            row[y] = reads[0][0]
        counts[label] = row
        geo = "Total country" if label == "Mauritanie" else label
        for y, v in row.items():
            out.append(_rec("census", "total", "Total", geo, y, "count", v,
                            "persons", "MR_RGPH_A.1.2"))
        rvals = [w["text"] for w in sorted(rates, key=lambda w: w["x0"])]
        for hdr, rv in zip(rate_hdr, rvals):
            if rv == "-":
                continue
            end = max(int(x) for x in hdr.split("-"))
            out.append(_rec("census", "total", "Total", geo, end, "growth_rate",
                            float(rv.replace(",", ".")), "percent", "MR_RGPH_A.1.2"))
    nat = counts.pop("Mauritanie")
    parts = {k: v for k, v in counts.items() if k != "Nouakchott global"}
    for y, v in nat.items():
        s = sum(r.get(y, 0) for r in parts.values())
        if y in (1988, 2000):                       # Nouakchott printed only globally
            s += counts["Nouakchott global"][y]
        if abs(s - v) > 1:            # 2023: 4 927 531 vs 4 927 532, as printed
            raise ValueError(f"Mauritania A.1.2 {y}: wilayas sum {s} != {v}")
    for w, t in totals_2023.items():          # every wilaya, strictly
        if w == "Total country":
            continue
        if w not in counts or abs(counts[w].get(2023, -9) - t) > 1:
            raise ValueError(f"Mauritania A.1.2 2023 {w}: "
                             f"{counts.get(w, {}).get(2023)} != Thème 2 {t}")
    return out


# --------------------------------------------------------------------------
# projections
# --------------------------------------------------------------------------

def _projections(path, census_totals):
    """Blocks -- one page section of two years (2053 stands alone) -- are read
    IN DOCUMENT ORDER, and a block is kept only if all 18 of its rows (17 age
    bands + Total) read cleanly for every year it carries. Some pages carry a
    doubled, interleaved text layer ("00--44 13305 678408 ..."); such a block
    is refused whole and logged, never partly kept.

    ONLY THE NATIONAL SECTION IS READ. The wilaya section (D) cannot be
    attributed reliably: its text layer carries content OVERLAID from other
    pages -- page 51 (Hodh El Gharbi) also yields a Brakna block headed
    "2053 2024"; page 59 (Assaba) repeats "D. Wilayas / a. Hodh Chargui /
    2023 2024" -- and running heads are misspelt ("Tagan", "Gorlgol"). A block
    that silently belongs to another wilaya passes every arithmetic check, so
    the wilaya projections are refused rather than risk misattribution;
    wilaya-level population comes from the census tables instead."""
    import sys
    with pdfplumber.open(path) as pdf:
        texts = [(p.extract_text() or "") for p in pdf.pages]
    blocks, section, cur = [], None, None
    for t in texts[14:]:
        for ln in t.splitlines():
            s = re.sub(r"^[A-D]\.\s*", "", ln.strip())   # "A. National" -> "National"
            if not s:
                continue
            if s == "National":
                section = "A"
                continue
            if s in ("Milieu urbain", "Milieu rural"):
                section = "skip"
                continue
            if s == "Wilayas":
                section = "D"
                continue
            ym = re.fullmatch(r"(20[2-5]\d)(?:\s+(20[2-5]\d))?", s)
            if ym:
                cur = {"section": section, "years": tuple(int(y) for y in ym.groups() if y),
                       "rows": [], "ok": True}
                blocks.append(cur)
                continue
            if cur is None or cur["section"] not in ("A", "D"):
                continue
            # only a line that OPENS with an age label is data; footers and
            # headers are not -- the completeness check catches real losses
            if not re.match(r"(?:Moins d|\d{1,2}\s?-\s?\d{1,2}\s|\d{1,2}\+\s|Total\s+\d)", s):
                continue
            # non-capturing: re.split would otherwise return the age label
            parts = re.split(r"\s(?=(?:Moins d|\d{1,2}\s?-\s?\d{1,2}\s|\d{1,2}\+\s|Total\s))", s)
            if len(parts) != len(cur["years"]):
                cur["ok"] = False
                continue
            for part, year in zip(parts, cur["years"]):
                mm = re.match(rf"^{_AGE_START}\s+([\d ]+)$", part.strip())
                trip = _triples(mm.group(2).split(), 1, "tmf") if mm else None
                if trip is None:
                    cur["ok"] = False
                    continue
                (ml, fl, tl), = trip
                cur["rows"].append((_age(mm.group(1)), year, ml, fl, tl))
    for b in blocks:
        if not all(len({a for a, y, *_ in b["rows"] if y == yr}) == 18 for yr in b["years"]):
            b["ok"] = False

    out, refused = [], []
    for b in blocks:
        if b["section"] != "A":
            continue
        if not b["ok"]:
            refused.append("-".join(map(str, b["years"])))
            continue
        for age, year, ml, fl, tl in b["rows"]:
            for sex, v in (("male", ml), ("female", fl), ("total", tl)):
                out.append(_rec("projection", sex, age, "Total country", year,
                                "count", v, "persons", "MR_PROJ_2023-2053"))
    if refused:
        raise ValueError(f"Mauritania national projections unreadable: {refused}")
    nat = {r["value"] for r in out if r["period"] == "2023" and r["age_group"] == "Total"
           and r["sex"] == "total"}
    if nat != {census_totals["Total country"]}:
        raise ValueError(f"Mauritania projections: 2023 total {nat} != census "
                         f"{census_totals['Total country']}")
    nat_years = {r["period"] for r in out if r["geography"] == "Total country"}
    if len(nat_years) != 31:
        raise ValueError(f"Mauritania projections: {len(nat_years)} national years")
    return out


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows, totals = _theme2(local_path)
    for p in extras or []:
        low = p.lower()
        if "theme-1" in low or "theme1" in low or "repartition" in low:
            rows += _theme1(p, totals)
        elif "projection" in low:
            rows += _projections(p, totals)
    df = pd.DataFrame(rows)
    key = ["series_type", "sex", "age_group", "geography", "period", "measure"]
    dup = df[df.duplicated(key, keep=False)]
    if len(dup):
        if (dup.groupby(key)["value"].nunique() > 1).any():
            raise ValueError("Mauritania: conflicting duplicate keys")
        df = df.drop_duplicates(key)
    return df
