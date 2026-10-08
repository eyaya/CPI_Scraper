"""ONS Algeria, Rétrospective Statistique 1962-2020, Chapitre XIV "Comptes
Economiques" (CH14_Comp_Economique1962_2020Fr.pdf) -- the long history the
current 'Comptes économiques' PDF (2021-2024 only) cannot give.

TWO AGGREGATES, KEPT APART. ONS prints both of its national concepts:

* "PRODUCTION INTÉRIEURE BRUTE" (Tableaux 16-16.8, 1974-2020): the national
  accounting system's aggregate, by 19 branches ("genre d'activité
  économique"), plus TVA and droits de douane -- production approach, current
  prices. It EXCLUDES the non-market services (administrations, financial
  institutions, real estate) that the SNA adds back.
* "PRODUIT INTÉRIEUR BRUT (S.C.N.)" (Tableaux 27-27.8, 1974-2020): the SNA
  aggregate by expenditure (uses) and by income, current prices; and
  Tableau 29, the SNA PIB 1963-2020 with its growth rate, GNP, per-capita
  values in DA and US$, and PIB in US$.

They are different numbers for the same year -- 2012: 13 561 457,2 vs
16 209 598,0 million DA -- so `series_code` and `category_group` name the
concept on every row ("DZ-RETRO-PrIB" vs "DZ-RETRO-SCN"). Neither is chained to
the 2021-2024 series of the current report (PIB 2021 = 25,2 trillion DA, a
different vintage); that series keeps its own rows.

READING. Values carry SPACE thousands and a comma decimal ("1 421 693,3"), and
every value ends in its decimal token, so a row's tokens are grouped up to each
comma-bearing token -- which also absorbs ONS's stray spaces ("28 1249,3" =
281 249,3) and missing ones ("5971552,4"). Each table is then held to its own
arithmetic, per year, or the parse raises:

* T16.x : the 19 branches sum to "Total (V.A.)" and Total + TVA + Droits de
  douanes = "Production Intérieure Brute";
* T27.x : the uses sum to "Emplois du P I B" (imports subtracted) and the four
  income items sum to "Produit intérieur brut (S C N)", which must equal it;
* T29   : the SNA PIB 2007-2020 equals Tableau 27's.

Tolerance is 0,05 million DA per item summed (each is rounded to 0,1), and
at least 0,5; published residues beyond that are pinned in `_KNOWN_GAPS`, not
smoothed.

TABLE 29's GROWTH RATE IS A VOLUME RATE: it reads 0,8% for 1980 while the
nominal PIB beside it rose 26,7%. ONS does not label it, so it is collected as
`growth_yoy` at `constant` prices with the label as printed and this evidence
recorded here. Its exchange rate and population columns are not GDP and are
not collected; the per-capita and US$ columns are ONS's own published figures.

NOT COLLECTED: Tableaux 1-15 (1963-1973, a different, SCEA-era layout per
period), 17-17.8 (public sector only), 18.x (production by legal sector), 20
(resources/uses balance -- its PIB is the Tableau 16 aggregate already
collected), 21/22/28 (national/monetary disposable income), 23-25
(accumulation, rest of world), 26.x (the SNA bridge from the national
aggregate -- its PIB equals Tableau 27's).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]
_UNIT = "DZD million"
_CAP = re.compile(r"^Tableau\s*(\d+)\s*(?:\.\s*(\d+))?\s*:\s*(.*)")
_YEAR = re.compile(r"\b(19[6-9]\d|20[0-2]\d)\b")
# (table, year) -> published residue (million DA) allowed beyond rounding.
_KNOWN_GAPS: dict[tuple[str, str], float] = {
    # T16.4, 2000: the 19 branches sum to 2 975 857,2 against a printed Total
    # (V.A.) of 3 430 857,3 -- 455 000,1 short -- while Total + TVA + Droits =
    # PIB holds exactly. Hydrocarbures prints "1 161 314,7"; 1 616 314,7 (a
    # transposition) would close the gap to 0,1. Kept AS PRINTED; pinned here
    # so any other gap, or a corrected reprint, raises.
    ("16.4", "2000"): -455000.1,
    # T29, 2018: PIB printed 20 393 352,4; Tableaux 26.8 and 27.8 print
    # 20 393 524,4 -- a transposition of "524" in Tableau 29. Kept as printed.
    ("29", "2018"): -172.0,
    # Residues in ONS's own tables, every other identity of the same table
    # holding: T16.7 2015 branches +2 461,3 (Chimie prints 73 325,1 for both
    # 2015 and 2016 -- 2015 looks copied); T27 1975 uses -180,0 and 1977
    # -10,0; T27.2 income items 1987 +81,0 and 1988 +657,2.
    ("16.7", "2015"): 2461.3,
    ("27", "1975"): -180.0,
    ("27", "1977"): -10.0,
    ("27.2", "1987"): 81.0,
    ("27.2", "1988"): 657.2,
}
_TOL = 0.5


def _values(tokens: list[str]) -> list[float]:
    """Group space-split tokens into values, each ending at a comma token."""
    out, cur = [], []
    for t in tokens:
        cur.append(t)
        if "," in t:
            s = "".join(cur).replace(",", ".")
            if not re.fullmatch(r"-?\d+(?:\.\d+)?", s):
                raise ValueError(f"unreadable value {' '.join(cur)!r}")
            out.append(float(s))
            cur = []
    if cur:
        raise ValueError(f"trailing tokens without a decimal: {cur}")
    return out


def _split_row(line: str, n: int):
    """'label  v1 ... vn' -> (label, [n values]) or None."""
    m = re.search(r"\s(-\s?)?\d[\d ,]*$", line)
    if not m:
        return None
    # The value run starts at the first token that is numeric from there on.
    toks = line.split()
    for k in range(len(toks)):
        tail = toks[k:]
        if all(re.fullmatch(r"-?\d+(?:,\d+)?|-", t) for t in tail):
            lab = " ".join(toks[:k]).strip()
            tail = [t for t in tail]
            # A minus sign printed apart from its number ("- 314 399,3").
            merged, i = [], 0
            while i < len(tail):
                if tail[i] == "-" and i + 1 < len(tail):
                    merged.append("-" + tail[i + 1]); i += 2
                else:
                    merged.append(tail[i]); i += 1
            try:
                vals = _values(merged)
            except ValueError:
                return None
            if len(vals) == n and lab:
                return lab, vals
            return None
    return None


def _page_lines(page) -> list[list[dict]]:
    """Words grouped into visual lines (same baseline), left to right."""
    words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) < 2.5:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(ln, key=lambda w: w["x0"]) for ln in lines]


def _num_word(t: str) -> bool:
    return bool(re.fullmatch(r"-|-?\d+(?:,\d+)?", t))


def _tables(path: str) -> dict[str, dict]:
    """{'16.7': {'title': ..., 'years': [...], 'rows': [(label, vals)]}}

    VALUES ARE ASSIGNED TO YEAR COLUMNS BY POSITION. A row's text cannot be
    split reliably: ONS prints most values with one decimal but some without
    ("24 481", Hydrocarbures 1978), and "24 481 33 534,7" reads more than one
    way. Each numeric word goes to the year whose header it sits under (the
    column boundaries are the midpoints between header centres), and a
    column's words are joined into one value."""
    out, cur = {}, None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for ln in _page_lines(page):
                text = " ".join(w["text"] for w in ln)
                m = _CAP.match(text)
                if m:
                    tid = m.group(1) + (f".{m.group(2)}" if m.group(2) else "")
                    cur = {"title": m.group(3), "years": None, "centres": None,
                           "rows": []}
                    out[tid] = cur
                    continue
                if cur is None:
                    continue
                if cur["years"] is None:
                    yw = [w for w in ln if _YEAR.fullmatch(w["text"])]
                    if len(yw) >= 4 and re.match(r"^(Genre|Désignation|Années)", text):
                        cur["years"] = [w["text"] for w in yw]
                        # Values are RIGHT-ALIGNED under their year: match on
                        # the right edge, not the centre (a leading "1" can
                        # sit exactly between two header centres).
                        cur["centres"] = [w["x1"] for w in yw]
                    continue
                cs = cur["centres"]
                step = cs[1] - cs[0]
                first_col = cs[0] - step + 4
                # A decimal printed apart from its number ("80 242 ,0") is
                # not label text.
                lab = [w["text"] for w in ln if (w["x1"] <= first_col
                       or not _num_word(w["text"]))
                       and not re.fullmatch(r",\d+", w["text"])]
                nums = [w for w in ln if w["x1"] > first_col
                        and _num_word(w["text"])]
                if not lab or not nums:
                    continue
                # Words of one value are ~2pt apart; values are >=10pt apart.
                runs: list[list[dict]] = []
                for w in nums:
                    if runs and w["x0"] - runs[-1][-1]["x1"] < 5:
                        runs[-1].append(w)
                    else:
                        runs.append([w])
                cols: list[list[str]] = [[] for _ in cs]
                for r in runs:
                    j = min(range(len(cs)), key=lambda k: abs(cs[k] - r[-1]["x1"]))
                    if cols[j]:
                        cols = None
                        break
                    cols[j] = [w["text"] for w in r]
                if cols is None or any(not c for c in cols):
                    continue
                vals = []
                for c in cols:
                    # A LOST DECIMAL COMMA: ONS prints one decimal throughout,
                    # and T27.4's 2001 exports read "1 550 898 4". A final
                    # single digit after a 3-digit group, in a value with no
                    # comma at all, is that decimal -- confirmed by the table's
                    # own identity, which then holds exactly.
                    if (len(c) >= 2 and not any("," in t for t in c)
                            and re.fullmatch(r"\d", c[-1])
                            and re.fullmatch(r"\d{3}", c[-2])):
                        c = c[:-1] + ["," + c[-1]]
                        c[-2] = c[-2] + c[-1]
                        c = c[:-1]
                    s = "".join(c).replace(",", ".")
                    if s.startswith("-") and len(c) > 1 and c[0] == "-":
                        s = "-" + "".join(c[1:]).replace(",", ".")
                    if not re.fullmatch(r"-?\d+(?:\.\d+)?", s):
                        break
                    vals.append(float(s))
                else:
                    cur["rows"].append((" ".join(lab).strip(), vals))
    return out


def _check(tid: str, year: str, got: float, want: float, what: str,
           items: int = 1):
    # Each printed item is rounded to 0,1, so a sum of n items can drift by up
    # to 0,05 per item from its printed total.
    gap = round(got - want, 1)
    if abs(gap) > max(_TOL, 0.05 * items + 0.05) and _KNOWN_GAPS.get((tid, year)) != gap:
        raise ValueError(f"ONS Rétrospective T{tid} {year}: {what} sums to "
                         f"{got:,.1f}, printed {want:,.1f} (gap {gap})")


def _row(approach, cat, group, code, year, value, measure="level",
         price="current", unit=_UNIT):
    return {"approach": approach, "category": cat, "category_group": group,
            "series_code": code, "geography": "National", "period": year,
            "frequency": "annual", "price_basis": price,
            "seasonal_adjustment": "not_applicable", "measure": measure,
            "value": value, "unit": unit, "base_period": ""}


def _production(t: dict, tid: str) -> list[dict]:
    rows = {lab.lstrip("- ").strip(): v for lab, v in t["rows"]}
    labs = [lab.lstrip("- ").strip() for lab, _ in t["rows"]]
    tot = next(l for l in labs if l.startswith("Total"))
    pib = next(l for l in labs if l.startswith("Production Intérieure Brute"))
    branches = labs[:labs.index(tot)]
    taxes = labs[labs.index(tot) + 1:labs.index(pib)]
    if len(branches) < 15 or len(taxes) != 2:
        raise ValueError(f"ONS Rétrospective T{tid}: read {labs}")
    out, grp = [], "Production intérieure brute par genre d'activité (concept national), prix courants"
    for j, y in enumerate(t["years"]):
        _check(tid, y, sum(rows[b][j] for b in branches), rows[tot][j], "branches",
               len(branches))
        _check(tid, y, rows[tot][j] + sum(rows[x][j] for x in taxes), rows[pib][j],
               "Total (V.A.) + taxes")
        for lab in branches + [tot] + taxes:
            out.append(_row("production", lab, grp, "DZ-RETRO-PrIB", y, rows[lab][j]))
        out.append(_row("aggregate", pib, grp, "DZ-RETRO-PrIB", y, rows[pib][j]))
    return out


def _uses_income(t: dict, tid: str) -> list[dict]:
    labs = [lab for lab, _ in t["rows"]]
    rows = dict(t["rows"])
    emp = next(l for l in labs if l.startswith("Emplois du P"))
    pib = next(l for l in labs if l.startswith("Produit intérieur brut"))
    uses = labs[:labs.index(emp)]
    inc = labs[labs.index(emp) + 1:labs.index(pib)]
    if len(uses) != 6 or len(inc) != 4:
        raise ValueError(f"ONS Rétrospective T{tid}: read {labs}")
    out, grp = [], "Produit intérieur brut (S.C.N.) et ses emplois, prix courants"
    for j, y in enumerate(t["years"]):
        s = sum(-rows[u][j] if u.startswith("(-)") else rows[u][j] for u in uses)
        _check(tid, y, s, rows[emp][j], "uses", len(uses))
        _check(tid, y, sum(rows[i][j] for i in inc), rows[pib][j], "income items",
               len(inc))
        _check(tid, y, rows[emp][j], rows[pib][j], "uses total vs PIB")
        for u in uses:
            out.append(_row("expenditure", u, grp, "DZ-RETRO-SCN", y, rows[u][j]))
        for i in inc:
            out.append(_row("income", i, grp, "DZ-RETRO-SCN", y, rows[i][j]))
        out.append(_row("aggregate", pib, grp, "DZ-RETRO-SCN", y, rows[pib][j]))
    return out


def _table_29(path: str, scn: dict[str, float]) -> list[dict]:
    """PIB (SCN) 1963-2020 with growth, GNP, per capita and US$ columns."""
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[-1].extract_text() or ""
    if "Tableau 29" not in text:
        raise ValueError("ONS Rétrospective: Tableau 29 not on the last page")
    grp = "Evolution du PIB et du PNB (Tableau 29)"
    out = []
    for ln in text.splitlines():
        m = re.match(r"^(19[6-9]\d|20[0-2]\d)\s+(.*)$", ln.strip())
        if not m:
            continue
        y, rest = m.groups()
        toks = rest.split()
        # PIB | growth ("-" before 1974) | PNB | population | PIB/cap DA |
        # PNB/cap DA | DA/US$ | PIB/cap US$ | PNB/cap US$ | PIB US$ million
        g = None
        if "-" in toks:
            k = toks.index("-")
            head, tail = toks[:k], toks[k + 1:]
        else:
            # the growth rate is the first token after PIB that has a comma
            # and at most two integer digits
            head = []
            for i, t in enumerate(toks):
                head.append(t)
                if "," in t:
                    break
            nxt = toks[len(head)]
            g = float(nxt.replace(",", "."))
            tail = toks[len(head) + 1:]
        pib = _values(head)
        if len(pib) != 1:
            raise ValueError(f"ONS Rétrospective T29 {y}: PIB reads {head}")
        # PNB (decimal), population (integer, space-grouped), then decimals.
        k = 0
        cur = []
        while "," not in tail[k]:
            cur.append(tail[k]); k += 1
        cur.append(tail[k]); k += 1
        pnb = _values(cur)[0]
        # population: integer tokens until the next comma-bearing group starts;
        # it is 2 tokens ("13 130") -- take tokens up to the first one that,
        # with what follows, leaves exactly six comma values.
        rest_toks = tail[k:]
        for cut in range(1, 4):
            try:
                vals = _values(rest_toks[cut:])
            except ValueError:
                continue
            if len(vals) == 6:
                break
        else:
            raise ValueError(f"ONS Rétrospective T29 {y}: cannot split {rest_toks}")
        pib_pc_da, pnb_pc_da, _fx, pib_pc_usd, pnb_pc_usd, pib_usd = vals
        if y in scn and abs(scn[y] - pib[0]) > _TOL and _KNOWN_GAPS.get(("29", y)) != round(pib[0] - scn[y], 1):
            raise ValueError(f"ONS Rétrospective T29 {y}: PIB {pib[0]} vs "
                             f"Tableau 27's {scn[y]}")
        code = "DZ-RETRO-SCN-T29"
        out.append(_row("aggregate", "Le PIB", grp, code, y, pib[0]))
        if g is not None:
            out.append(_row("aggregate", "Taux de croissance du PIB", grp, code, y, g,
                            measure="growth_yoy", price="constant", unit="percent"))
        out.append(_row("aggregate", "Le PNB", grp, code, y, pnb))
        out.append(_row("aggregate", "PIB/capita en DA", grp, code, y, pib_pc_da,
                        measure="per_capita", unit="DZD"))
        out.append(_row("aggregate", "PNB/capita en DA", grp, code, y, pnb_pc_da,
                        measure="per_capita", unit="DZD"))
        out.append(_row("aggregate", "PIB/capita en US$", grp, code, y, pib_pc_usd,
                        measure="per_capita", unit="USD"))
        out.append(_row("aggregate", "PNB/capita en US$", grp, code, y, pnb_pc_usd,
                        measure="per_capita", unit="USD"))
        out.append(_row("aggregate", "PIB en 10^6 US$", grp, code, y, pib_usd,
                        unit="USD million"))
    years = {r["period"] for r in out}
    if len(years) != 58:
        raise ValueError(f"ONS Rétrospective T29: {len(years)} years, want 58 (1963-2020)")
    return out


def parse(path: str) -> pd.DataFrame:
    tabs = _tables(path)
    prod_ids = ["16"] + [f"16.{i}" for i in range(1, 9)]
    scn_ids = ["27"] + [f"27.{i}" for i in range(1, 9)]
    rows = []
    for tid in prod_ids:
        if tid not in tabs or not tabs[tid]["rows"]:
            raise ValueError(f"ONS Rétrospective: Tableau {tid} not read")
        rows += _production(tabs[tid], tid)
    for tid in scn_ids:
        if tid not in tabs or not tabs[tid]["rows"]:
            raise ValueError(f"ONS Rétrospective: Tableau {tid} not read")
        rows += _uses_income(tabs[tid], tid)
    scn = {r["period"]: r["value"] for r in rows
           if r["series_code"] == "DZ-RETRO-SCN" and r["approach"] == "aggregate"}
    rows += _table_29(path, scn)
    df = pd.DataFrame.from_records(rows)[_OUT_COLS]
    key = ["approach", "category", "series_code", "period", "measure", "price_basis"]
    dup = df[df.duplicated(key, keep=False)]
    if not dup.empty:
        raise ValueError(f"ONS Rétrospective: duplicate keys, e.g. "
                         f"{dup.head(3).to_dict('records')}")
    return df
