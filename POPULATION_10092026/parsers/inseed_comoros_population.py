"""INSEED Comores — RGPH 2017, "Rapport Analyse État et Structure de la
population" (Tier-3 PDF, from INSEED's NADA catalogue, study 8).

Census, period 2017, series_type `census`:

* Tableau 2.4  resident population by ISLAND (Mwali, Ndzuwani, Ngazidja) and
               PRÉFECTURE, by sex -- each island asserted equal to the sum of
               its préfectures, and the three islands to ENSEMBLE;
* Tableau 3.1  population by five-year age group and sex, nationally and for
               each island (male / female only per island: the table prints no
               island total by age).

Islands are SUMS of their préfectures; never add the two levels. Island names
are kept as printed (upper case in 2.4, e.g. "MWALI"); préfectures are named by
their capitals, as the table's own note says.

THE TWO TABLES DISAGREE, and are not reconciled. Tableau 3.1's "Total" row
gives Ndzuwani female 162 272 and the national female total 376 503; Tableau
2.4 gives 162 212 and 376 504. Geography totals are therefore taken from 2.4
ONLY, and 3.1 contributes its AGE rows only -- so each key carries one table's
figure, and the disagreement is recorded here rather than averaged away.

SPACING IS INCONSISTENT -- "381812", "9 348", "33 099", "190 082" in one table
-- so counts are split under each row's own arithmetic, never by whitespace:
male + female = total in 2.4; in 3.1 the national total = male + female and,
for each sex, the three islands = the national figure. Tableau 3.1 is printed
with residues of 1 (0-4 ans: the islands' males sum to 53 043 against 53 044),
so a residue of 1 is accepted there; the split must still be unique, and any
larger gap raises.

A MISPRINT, REFUSED: Tableau 2.4's NDZUWANI female 162 212 contradicts its
own row (165 110 + 162 212 != 327 382) and Tableau 3.1 (162 272); only that
cell is dropped (`_MISPRINTS`). Islands vs their préfectures differ by up to 3
(rounding residues as printed) and are accepted within that.

NOT READ: Tableaux 2.1-2.3 (de jure / de facto shares, urban-rural shares),
the "Résultats globaux" report (same census, fewer breakdowns), the communes
annex, and earlier rounds (RGPH 2003 is not on NADA).

CROSS-CHECK: ENSEMBLE 758 316 (381 812 M / 376 504 F); Ngazidja 379 367;
Moroni 121 236; 0-4 ans 103 581.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_CODE = "KM_RGPH2017"
_ISLANDS = ["MWALI", "NDZUWANI", "NGAZIDJA"]
# Tableau 2.4 rows that fail their own male + female = total, with the cell
# that is refused: NDZUWANI prints female 162 212, but 165 110 + 162 212 is
# 327 322, not the printed 327 382 -- and Tableau 3.1 prints 162 272, which
# does add up. A one-digit misprint (7 -> 1); male and total are kept, the
# contradicted female cell is not.
_MISPRINTS = {("NDZUWANI", 165110, 162212, 327382): "female"}


def _rec(sex, age, geo, value, code):
    return {"series_type": "census", "sex": sex, "age_group": age,
            "geography": geo, "period": "2017", "frequency": "annual",
            "measure": "count", "value": float(value), "unit": "persons",
            "series_code": code}


def _numbers(tokens):
    """Every reading of `tokens` as integers: a 4+-digit token is a whole
    number; otherwise 1-3 digits followed by 3-digit groups."""
    if not tokens:
        yield []
        return
    if re.fullmatch(r"\d{4,}", tokens[0]):
        for tail in _numbers(tokens[1:]):
            yield [int(tokens[0])] + tail
        return
    for k in range(1, min(len(tokens), 3) + 1):
        head = tokens[:k]
        if re.fullmatch(r"\d{1,3}", head[0]) and all(
                re.fullmatch(r"\d{3}", t) for t in head[1:]):
            for tail in _numbers(tokens[k:]):
                yield [int("".join(head))] + tail


def _unique(cands, where):
    if len(cands) != 1:
        raise ValueError(f"Comoros {where}: {len(cands)} readings")
    return cands[0]


def _pages(path):
    with pdfplumber.open(path) as pdf:
        return [(p.extract_text() or "") for p in pdf.pages]


def _table(pages, caption):
    for t in pages:
        for m in re.finditer(caption, t):
            body = t[m.end():]
            if re.search(r"\d{4,}|\d{1,3} \d{3}", body[:600]):
                return body.splitlines()
    raise ValueError(f"Comoros: {caption!r} not found")


def _t24(pages):
    out, rows = [], []
    for ln in _table(pages, r"Tableau 2\.4\s*: Répartition de la population du pays"):
        m = re.match(r"^([A-Za-zÀ-ÿ'’ \-]+?)\s+([\d ]+)$", ln.strip())
        if not m:
            if rows and ln.startswith("NB"):
                break
            continue
        label = m.group(1).strip()
        if label.upper() in ("EFFECTIF", "ILE/PRÉFECTURES"):
            continue
        reads = [n for n in _numbers(m.group(2).split()) if len(n) == 3]
        good = [n for n in reads if n[0] + n[1] == n[2]]
        if good:
            trip = _unique(good, f"T2.4 {ln!r}")
        else:
            bad = [n for n in reads if (label, *n) in _MISPRINTS]
            trip = _unique(bad, f"T2.4 {ln!r} (fails male + female = total)")
        rows.append((label, trip))
    labels = [r[0] for r in rows]
    if labels[0] != "ENSEMBLE" or len(rows) != 22:
        raise ValueError(f"Comoros T2.4: rows {labels}")
    nat = rows[0][1]
    # islands = sum of their préfectures; ENSEMBLE = sum of islands
    i, island_sum = 1, [0, 0, 0]
    while i < len(rows):
        name, trip = rows[i]
        if name not in _ISLANDS:
            raise ValueError(f"Comoros T2.4: expected an island, got {name!r}")
        j, s = i + 1, [0, 0, 0]
        while j < len(rows) and rows[j][0] not in _ISLANDS:
            s = [a + b for a, b in zip(s, rows[j][1])]
            j += 1
        # the préfectures sum to the island within 3 (rounding residues as
        # printed: Ndzuwani's sum to 165 111 / 162 273 / 327 384)
        skip = _MISPRINTS.get((name, *trip))
        if any(abs(a - b) > 3 for a, b, sx in zip(s, trip, ("male", "female", "total"))
               if sx != skip):
            raise ValueError(f"Comoros T2.4: {name} {trip} != préfectures {s}")
        for sex, v in zip(("male", "female", "total"), trip):
            if sex != skip:
                out.append(_rec(sex, "Total", name, v, f"{_CODE}_T2.4"))
        for pname, ptrip in rows[i + 1:j]:
            for sex, v in zip(("male", "female", "total"), ptrip):
                out.append(_rec(sex, "Total", pname, v, f"{_CODE}_T2.4"))
        island_sum = [a + b for a, b in zip(island_sum, trip)]
        i = j
    # The islands sum to ENSEMBLE exactly for the total, within 1 for males
    # (381 813 vs 381 812), and within 61 for females -- Ndzuwani's misprinted
    # 162 212 (60 short) plus the same 1-person residue.
    tol = {0: 1, 1: 61, 2: 0}
    if any(abs(island_sum[k] - nat[k]) > tol[k] for k in range(3)):
        raise ValueError(f"Comoros T2.4: islands {island_sum} != ENSEMBLE {nat}")
    for sex, v in zip(("male", "female", "total"), nat):
        out.append(_rec(sex, "Total", "Total country", v, f"{_CODE}_T2.4"))
    return out


def _age(label):
    s = label.replace(" ", "")
    m = re.fullmatch(r"(\d{1,2})(?:-|à)(\d{1,2})", s)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2))}"
    m = re.fullmatch(r"(\d{1,2})\+", s)
    return f"{int(m.group(1))}+" if m else None


def _t31(pages):
    out, n = [], 0
    for ln in _table(pages, r"Tableau 3\.1\s*: Répartition de la population par groupes"):
        m = re.match(r"^(\d{1,2}\s*(?:-|à)\s*\d{1,2}|\d{1,2}\+)\s+([\d ]+)$", ln.strip())
        if not m:
            if n and not ln.strip():
                continue
            if n >= 18:
                break
            continue
        age = _age(m.group(1))
        cands = []
        for v in _numbers(m.group(2).split()):
            if len(v) != 9:
                continue
            t, hm, hf = v[0], v[1], v[2]
            if (abs(hm + hf - t) <= 1 and abs(v[3] + v[5] + v[7] - hm) <= 1
                    and abs(v[4] + v[6] + v[8] - hf) <= 1):
                cands.append(v)
        v = _unique(cands, f"T3.1 {ln!r}")
        n += 1
        out += [_rec("total", age, "Total country", v[0], f"{_CODE}_T3.1"),
                _rec("male", age, "Total country", v[1], f"{_CODE}_T3.1"),
                _rec("female", age, "Total country", v[2], f"{_CODE}_T3.1")]
        for k, isl in enumerate(_ISLANDS):
            out += [_rec("male", age, isl, v[3 + 2 * k], f"{_CODE}_T3.1"),
                    _rec("female", age, isl, v[4 + 2 * k], f"{_CODE}_T3.1")]
    if n != 18:
        raise ValueError(f"Comoros T3.1: {n} age groups, expected 18")
    return out


def parse(local_path: str) -> pd.DataFrame:
    pages = _pages(local_path)
    df = pd.DataFrame(_t24(pages) + _t31(pages))
    key = ["series_type", "sex", "age_group", "geography", "period", "measure"]
    if df.duplicated(key).any():
        raise ValueError("Comoros: duplicate keys")
    return df
