"""DR Congo — Direction Générale de la Dette Publique (DGDP), "Bulletin
trimestriel de la dette publique".

PUBLISHER: the DGDP, the Ministry of Finance's debt-management directorate --
an official national compiler, accepted under the 2026-10-08 source policy.

COVERAGE: the bulletin's "Dette publique" is the State's direct debt
(external + domestic). State-owned enterprises' borrowing (Tableau n°8, nine
SOEs) and provincial debt (Tableau n°9, eight provinces) are reported
SEPARATELY and are not part of the totals read here.

WHAT IS READ:

* Tableau n°1 "Evolution de l'encours de la dette publique" -- annual
  end-year stocks for the last five years, in MILLIONS DE USD: total, external
  (and its technical arrears), domestic; each with its share of GDP and the
  external / domestic shares of the total, all as printed; plus the total in
  MILLIARDS DE CDF. Every issue reprints five years, so merge-on-write keeps
  each year; the newest issue wins on revisions.
* Tableau n°6 "Structure de la dette publique intérieure au 31 décembre" --
  the domestic debt by category (arrears certified/validated, protocols,
  central-bank arrears, public securities), millions USD, at the bulletin's
  reference date.

TRAPS. Numbers mix "4867,98" and "7 385,03" (space thousands, comma
decimals). The 2025 total prints "15 012,141": a footnote marker "1" glued to
15 012,14 -- read as 15 012,14 by an explicit, checked rule (`_FOOTNOTED`),
never by dropping a digit in general. The CDF row wraps its last year onto the
next line.

PUBLISHED CONTRADICTION, KEPT AS THE TABLE PRINTS IT: footnote 1 says the
updated end-2025 stock is "12 012,14 millions USD", while the table prints
15 012,14 -- and the table is the one that reconciles (external 9 730,56 +
domestic 5 281,58 = 15 012,14; Tableau n°7's currency split totals 15 012,14).

CROSS-CHECK (Q4 2025 bulletin): total 15 012,14 (17,32% of GDP); external
9 730,56; domestic 5 281,58; total 32 747,34 milliards CDF; domestic public
securities 1 439,79.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_COV = ("Dette publique de l'Etat (DGDP; dette des entreprises publiques et des "
        "provinces publiée séparément)")
_T1 = re.compile(r"Tableau n°1 : Evolution de l.encours de la dette publique de "
                 r"(\d{4}) à (\d{4})")
_T6 = re.compile(r"Tableau n°6 : Structure de la dette publique intérieure au "
                 r"(\d{1,2}) (\w+) (\d{4})")
_NUM = re.compile(r"\d{1,3}(?: \d{3})+,\d+%?|\d+,\d+%?|\d+%")
# A footnote marker glued to a value: (printed token, value, year it is in).
_FOOTNOTED = {("15 012,141", 15012.14, "2025")}

_T6_CATS = ["Arriérés certifiés et validés", "Arriérés Certifiés non validés",
            "Protocoles d'accords", "Arriérés Banque Centrale du Congo",
            "Encours titres publics"]

# (label at line start, component, measure, unit)
_T1_ROWS = [
    ("Dette Publique", "Dette publique", "stock", "USD million"),
    ("DP en % du PIB", "Dette publique", "share_of_gdp", "percent"),
    ("Dette Extérieure", "Dette extérieure", "stock", "USD million"),
    ("dont arriérés techniques", "Dette extérieure: dont arriérés techniques",
     "stock", "USD million"),
    ("DE en % du PIB", "Dette extérieure", "share_of_gdp", "percent"),
    ("DE-Part en %", "Dette extérieure", "share", "percent"),
    ("Dette Intérieure", "Dette intérieure", "stock", "USD million"),
    ("DI en % du PIB", "Dette intérieure", "share_of_gdp", "percent"),
    ("DI-Part en %", "Dette intérieure", "share", "percent"),
]


def _num(tok: str, year: str) -> float:
    for printed, val, y in _FOOTNOTED:
        if tok == printed and y == year:
            return val
    if re.fullmatch(r"\d{1,3}(?: \d{3})+,\d{3}", tok):
        raise ValueError(f"DGDP: {tok!r} has three decimals -- an unlisted "
                         f"footnote marker? add it to _FOOTNOTED deliberately")
    return float(tok.rstrip("%").replace(" ", "").replace(",", "."))


def _row(rows, comp, per, meas, val, unit, code, freq="annual"):
    rows.append({"coverage": _COV, "component": comp, "period": per,
                 "frequency": freq, "measure": meas, "value": val,
                 "unit": unit, "series_code": code})


def _parse_current(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        texts = [p.extract_text() or "" for p in pdf.pages]
    t1 = next(t for t in texts if _T1.search(t))
    m = _T1.search(t1)
    years = [str(y) for y in range(int(m.group(1)), int(m.group(2)) + 1)]
    lines = [ln.strip() for ln in t1[m.end():].splitlines()]
    out, seen = [], set()

    for i, ln in enumerate(lines):
        if ln.startswith("Dette Publique") and any(
                "Milliards de CDF" in x for x in lines[i + 1:i + 3]):
            nums = _NUM.findall(ln[len("Dette Publique"):])
            nxt = lines[i + 1]
            if len(nums) == len(years) - 1 and re.fullmatch(_NUM.pattern, nxt):
                nums.append(nxt)          # last year wrapped onto the next line
            if len(nums) != len(years):
                raise ValueError(f"DGDP T1 CDF row: {nums}")
            for y, tok in zip(years, nums):
                _row(out, "Dette publique", y, "stock", _num(tok, y),
                     "CDF milliards", "DGDP T1")
            seen.add("CDF")
            continue
        for label, comp, meas, unit in _T1_ROWS:
            if ln.startswith(label) and (label, comp) not in seen:
                nums = _NUM.findall(ln[len(label):])
                if len(nums) != len(years):
                    raise ValueError(f"DGDP T1 {label!r}: {nums}")
                for y, tok in zip(years, nums):
                    _row(out, comp, y, meas, _num(tok, y), unit, "DGDP T1")
                seen.add((label, comp))
                break
    if len(seen) != len(_T1_ROWS) + 1:
        raise ValueError(f"DGDP T1: read {len(seen)} rows, expected "
                         f"{len(_T1_ROWS) + 1}")
    by = {(r["component"], r["period"], r["measure"], r["unit"]): r["value"]
          for r in out}
    for y in years:
        tot = by[("Dette publique", y, "stock", "USD million")]
        parts = (by[("Dette extérieure", y, "stock", "USD million")]
                 + by[("Dette intérieure", y, "stock", "USD million")])
        if abs(tot - parts) > 0.05:
            raise ValueError(f"DGDP T1 {y}: total {tot} != external + domestic "
                             f"{parts}")

    # Tableau n°6: domestic debt by category at the reference date
    t6 = next((t for t in texts if _T6.search(t)), None)
    if t6:
        m6 = _T6.search(t6)
        year6 = m6.group(3)
        lines6 = [ln.strip() for ln in t6[m6.end():].splitlines()]
        label = ""
        parts6 = []
        for ln in lines6:
            if ln.startswith("Source"):
                break
            mm = re.fullmatch(r"(?:(\d)\s+)?(.*?)\s*(\d{1,3}(?: \d{3})*,\d+)\s+(\d+)%", ln)
            if mm:
                name = " ".join(x for x in (label, mm.group(2)) if x).strip()
                val = _num(mm.group(3), year6)
                share = float(mm.group(4))
                parts6.append((name, val, share))
                label = ""
            elif not re.match(r"^(N°|millions USD|Montant)", ln):
                label = ln if not label else f"{label} {ln}"
        if not parts6 or not parts6[-1][0].startswith("Total dette intérieure"):
            raise ValueError(f"DGDP T6: rows {[p[0] for p in parts6]}")
        *cats, total = parts6
        # "Arriérés Banque Centrale du / <numbers> / Congo" wraps AROUND its
        # figures, so a line reader hands "Congo" to the next row. The five
        # categories are stated as printed and checked word by word in order.
        if len(cats) != len(_T6_CATS):
            raise ValueError(f"DGDP T6: {len(cats)} categories, expected "
                             f"{len(_T6_CATS)}")
        flat, pos = " ".join(c[0] for c in cats), 0
        for name in _T6_CATS:
            for word in name.split():
                k = flat.find(word, pos)
                if k < 0:
                    raise ValueError(f"DGDP T6: {name!r} not in order in {flat!r}")
                pos = k + len(word)
        cats = [(name, v, sh) for name, (_, v, sh) in zip(_T6_CATS, cats)]
        if abs(sum(v for _, v, _ in cats) - total[1]) > 0.05:
            raise ValueError("DGDP T6: categories do not sum to the total")
        for name, val, share in cats:
            comp = f"Dette intérieure: {name}"
            _row(out, comp, year6, "stock", val, "USD million", "DGDP T6")
            _row(out, comp, year6, "share", share, "percent", "DGDP T6")
    return pd.DataFrame(out)


# --- BACK ISSUES (added 2026-10-14) -----------------------------------------
# Older bulletins print Tableau n°1 (then section "II-/III- Evolution de
# l'encours ...") with ANNUAL columns followed by quarter columns: Q2 2019
# "2014 2015 2016 2017 2018 | TR1-2019 TR2-2019 | variation", Q2 2022 "2018
# 2019 2020 2021 | TR1-2022 TR2-2022 | variation". Only the ANNUAL columns are
# read -- the plain four-digit years in the header, in order, which are the
# first values of each row -- and only rows whose values all sit on the label's
# line ("dont arriérés techniques" and the CDF row wrap in the 2019 issue and
# are not reassembled). Labels, units and series code are the current
# reader's, so the years join the same series. External + domestic = total is
# checked per year.
_BACK_HEAD = re.compile(r"Evolution de l.encours de la dette publique")
_BACK_ROWS = [r for r in _T1_ROWS if r[0] != "dont arriérés techniques"]


def _parse_back(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        texts = [p.extract_text() or "" for p in pdf.pages]
    t = next((x for x in texts if _BACK_HEAD.search(x) and "Dette Intérieure" in x), None)
    if t is None:
        raise ValueError("DGDP back issue: debt-stock table not found")
    body = t[_BACK_HEAD.search(t).end():]
    head = body[:body.find("Dette publique")]
    # The title ("de 2014 au 2ème trimestre 2019") names the range; its last
    # year is the bulletin's own, whose columns are quarters. The column
    # header follows the units line "(En millions USD)".
    title_years = re.findall(r"(?:19|20)\d{2}", head[:head.find("USD")])
    if not title_years:
        raise ValueError("DGDP back issue: title years not found")
    own = max(title_years)
    head = head[head.find("USD)") + 4:]
    years = [y for y in re.findall(r"(?<![\d-])((?:19|20)\d{2})(?![\d-])", head)
             if y < own]
    # The header wraps ("2018 TR1-2019 TR2-2019" above "2014 2015 2016 2017"),
    # but the columns run chronologically, so the years are sorted.
    years = sorted(years)
    if len(years) < 2 or len(set(years)) != len(years) or             int(years[-1]) - int(years[0]) != len(years) - 1:
        raise ValueError(f"DGDP back issue: annual columns {years}")
    out = []
    lines = [ln.strip() for ln in body.splitlines()]
    for label, comp, meas, unit in _BACK_ROWS:
        # Older issues print "Dette publique" (USD row) and "Dette Publique"
        # (the CDF row below it): the FIRST match, case-insensitively, is USD.
        ln = next((x for x in lines if x.lower().startswith(label.lower())), None)
        if ln is None:
            raise ValueError(f"DGDP back issue: row {label!r} not found")
        nums = _NUM.findall(ln[len(label):])
        if len(nums) < len(years) + 1:
            raise ValueError(f"DGDP back issue {label!r}: {nums}")
        if meas == "stock" and any(t.endswith("%") for t in nums[:len(years)]):
            raise ValueError(f"DGDP back issue {label!r}: a percent in a stock row")
        for y, tok in zip(years, nums):
            _row(out, comp, y, meas, _num(tok, y), unit, "DGDP T1")
    by = {(r["component"], r["period"], r["measure"]): r["value"] for r in out}
    for y in years:
        if abs(by[("Dette publique", y, "stock")] - by[("Dette extérieure", y, "stock")]
               - by[("Dette intérieure", y, "stock")]) > 0.05:
            raise ValueError(f"DGDP back issue {y}: external + domestic != total")
    return out


_KEY = ["component", "period", "measure", "unit", "series_code"]


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """The current bulletin, read whole, then BACK ISSUES (extras, newest
    first) for their annual columns; where two bulletins print the same year
    the newer wins (listed first), and revisions are printed."""
    frames = [_parse_current(path)]
    for p in extras or []:
        name = p.replace(chr(92), "/").rsplit("/", 1)[-1]
        try:
            frames.append(pd.DataFrame(_parse_back(p)))
        except ValueError as e:
            print(f"  [drc] back issue skipped ({name}): {e}")
    df = pd.concat(frames, ignore_index=True)
    first = df.drop_duplicates(_KEY, keep="first")
    changed = int((df.groupby(_KEY)["value"].nunique() > 1).sum())
    if changed:
        print(f"  [drc] {changed} cell(s) revised by a newer bulletin; newest kept")
    return first.reset_index(drop=True)
