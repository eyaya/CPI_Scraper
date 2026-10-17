"""Republic of Congo — Caisse Congolaise d'Amortissement (CCA), "Bulletin
Statistique de la Dette Publique" (quarterly), published on the Ministry of
Finance's site (finances.gouv.cg).

PUBLISHER: the CCA, the State's debt-management agency (credited "Source :
CCA" under every table) -- an official national compiler, accepted under the
2026-10-08 source policy.

COVERAGE: "Administration centrale" -- Tableau 3's caption names it, and the
bulletin's stocks are the central government's external and domestic debt.

WHAT IS READ (five quarters per issue; merge-on-write accumulates them, the
newest issue winning on revisions):

* Tableau 1 "Stock de la dette publique" -- external and domestic debt, each
  split into arrears ("Stocks arriérés") and outstanding excluding arrears,
  and the total; every cell printed TWICE, in milliards de USD and milliards
  de FCFA (MN (XAF)). Both are collected, as printed -- the USD figures are
  the CCA's own conversion, not ours.
* Tableau 2 -- the same stocks by creditor class (bilateral, multilateral,
  commercial), domestic "dont dette du marché", in milliards de FCFA, with the
  latest quarter's share of the total ("% du stock").
* Tableau 3 -- external debt by currency of the loan, milliards de FCFA.

PUBLISHED HEADER MISPRINT, HANDLED EXPLICITLY. Tableaux 1 and 2 of the Q2
2026 bulletin head their fourth column "2025T1" between 2025T4 and 2026T2;
Tableau 3 heads the same column "2026T1", and Tableau 1's external total in
that column (3 791,06) is Tableau 3's 2026T1 total. Periods are therefore
taken from Tableau 3's header, and Tableaux 1-2's headers must match it
except where `_HEADER_MISPRINTS` names the slip -- any other disagreement
raises.

"Stocks arriérés" and "Encours hors arriérés" appear under both external and
domestic debt; each is qualified by its parent. "Encours hors / arriérés"
wraps around its numbers.

CHECKS: external + domestic = total; arrears + outstanding = each parent;
bilateral + multilateral + commercial = external; currencies = external total
(all within 0,05 milliard).

CROSS-CHECK (2026T2): total 9 564,28 milliards FCFA (16,61 milliards USD);
external 3 989,07; domestic 5 575,21; market debt 3 005,42; USD-denominated
external debt 2 257,09.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_COV = "Administration centrale"
_Q = re.compile(r"(20\d\d)T([1-4])")
_NUM = re.compile(r"\d{1,3}(?: \d{3})*,\d+|\d+,\d+|\d{4,},\d+")
# (issue's latest quarter, printed label, the quarter it stands for)
_HEADER_MISPRINTS = {("2026-Q2", "2025T1", "2026-Q1")}


def _f(tok):
    return float(tok.replace(" ", "").replace(",", "."))


def _quarters(line):
    return [f"{y}-Q{q}" for y, q in _Q.findall(line)]


def _region(text, caption):
    i = text.index(caption)
    j = text.find("Source", i)
    return text[i + len(caption):j].splitlines()


_KEY = ["coverage", "component", "period", "frequency", "measure", "unit", "series_code"]
# Older issues caption Tableau 1 "Stock de la dette publique (en milliards)"
# or "Encours de la dette publique (en milliards)".
_T1_LEGACY = re.compile(r"^Tableau 1\s*:\s*(?:Stock|Encours) de la dette publique "
                        r"\(en milliards\)\s*$", re.M)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """The current bulletin in full, plus Tableau 1 from each BACK ISSUE.

    Each bulletin prints five quarters, so a back issue extends the series.
    Older bulletins caption Tableau 1 differently and lay out Tableaux 2-3
    differently, so only their Tableau 1 (external / domestic / total, each
    split into arrears and outstanding excluding arrears, USD and FCFA) is
    read, by `_tableau1_legacy`, under the same component names and checks.
    Overlapping quarters: the newest bulletin wins.
    """
    frames = [_parse_current(path)]
    for p in extras or []:
        rows = _tableau1_legacy(p) or _tableau2_encours(p)
        if rows:
            frames.append(pd.DataFrame(rows))
    frames = [f.assign(_end=f["period"].max()) for f in frames]
    df = pd.concat(frames, ignore_index=True).sort_values("_end", kind="stable")
    return df.drop_duplicates(_KEY, keep="last").drop(columns="_end").reset_index(drop=True)


def _tableau1_legacy(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        page = next((p.extract_text() for p in pdf.pages
                     if _T1_LEGACY.search(p.extract_text() or "")
                     and "....." not in (p.extract_text() or "")), None)
    if page is None:
        print(f"[congo] {path.rsplit('/', 1)[-1]}: no legacy Tableau 1 -- not read")
        return []
    m = _T1_LEGACY.search(page)
    body = page[m.end():page.find("Source", m.end())]
    # "4 413, 74": a decimal split by a stray space -- rejoined; the sums
    # below prove every reading.
    body = re.sub(r"(\d), (\d{1,2})(?!\d)", r"\1,\2", body)
    lines = body.splitlines()
    # Five quarters ("2024T1 ... 2025T1"), or -- the 4th-quarter 2024 issue --
    # the previous year-end then four quarters ("2023 2024T1 ... 2024T4").
    periods = None
    for ln in lines:
        m = re.fullmatch(r"\s*(?:(20\d\d)\s+)?((?:20\d\dT[1-4]\s*)+)", ln)
        if m and len(_Q.findall(ln)) + bool(m.group(1)) == 5:
            periods = ([(m.group(1), "annual")] if m.group(1) else []) + \
                      [(q, "quarterly") for q in _quarters(m.group(2))]
            break
    if not periods:
        raise ValueError(f"CCA legacy Tableau 1: no five-column header in {path}")
    out, t1rows, parent = [], {}, None
    for ln in lines:
        nums = _NUM.findall(ln)
        if len(nums) != 10:
            continue
        label = _NUM.sub("", ln).strip()
        if label == "Dette Total":      # the 4th-quarter 2024 issue's spelling
            label = "Dette Totale"
        if label in ("Dette extérieure", "Dette intérieure", "Dette Totale"):
            parent = comp = label
        elif label == "Stocks arriérés":
            comp = f"{parent}: Stocks arriérés"
        elif label in ("Encours hors", "Encours hors arriérés", ""):
            comp = f"{parent}: Encours hors arriérés"
        else:
            raise ValueError(f"CCA legacy Tableau 1: unexpected row {label!r}")
        vals = [_f(x) for x in nums]
        t1rows[comp] = vals
        for (per, freq), usd, xaf in zip(periods, vals[0::2], vals[1::2]):
            for v, unit in ((usd, "USD milliards"), (xaf, "FCFA milliards")):
                out.append({"coverage": _COV, "component": comp, "period": per,
                            "frequency": freq, "measure": "stock",
                            "value": v, "unit": unit, "series_code": "CCA T1"})
    need = {"Dette extérieure", "Dette intérieure", "Dette Totale",
            "Dette extérieure: Stocks arriérés", "Dette extérieure: Encours hors arriérés",
            "Dette intérieure: Stocks arriérés", "Dette intérieure: Encours hors arriérés"}
    if set(t1rows) != need:
        raise ValueError(f"CCA legacy Tableau 1: rows {sorted(t1rows)}")
    for j in range(1, 10, 2):
        x = lambda c: t1rows[c][j]
        if abs(x("Dette extérieure") + x("Dette intérieure") - x("Dette Totale")) > 0.1:
            raise ValueError("CCA legacy Tableau 1: external + domestic != total")
        for p in ("Dette extérieure", "Dette intérieure"):
            if abs(x(f"{p}: Stocks arriérés") + x(f"{p}: Encours hors arriérés") - x(p)) > 0.1:
                raise ValueError(f"CCA legacy Tableau 1: {p} parts do not sum")
    return out


def _parse_current(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        page = next(p.extract_text() for p in pdf.pages
                    if "Tableau 1: Stock de la dette publique (en milliards de dollars"
                    in (p.extract_text() or "")
                    and "Tableau 3 : Stock" in (p.extract_text() or "")
                    and "...." not in (p.extract_text() or ""))
    t1 = _region(page, "Tableau 1: Stock de la dette publique (en milliards de dollars et en milliards de FCFA)")
    t2 = _region(page, "Tableau 2: Evolution du stock de la dette publique (en milliards de FCFA) par type de créanciers")
    t3 = _region(page, "Tableau 3 : Stock de la dette extérieure (en milliards de FCFA) de l’administration centrale par devise")

    # periods from Tableau 3's header
    h3 = next(ln for ln in t3 if len(_Q.findall(ln)) == 5)
    periods = _quarters(h3)
    latest = periods[-1]

    def check_header(lines, name):
        h = next(ln for ln in lines if len(_Q.findall(ln)) == 5)
        for printed, want in zip(_Q.findall(h), periods):
            got = f"{printed[0]}-Q{printed[1]}"
            if got == want:
                continue
            if (latest, f"{printed[0]}T{printed[1]}", want) in _HEADER_MISPRINTS:
                continue
            raise ValueError(f"CCA {name}: header {h!r} disagrees with "
                             f"Tableau 3's {periods}")
    check_header(t1, "Tableau 1")
    check_header(t2, "Tableau 2")

    out = []

    def add(comp, vals, unit, code):
        for per, v in zip(periods, vals):
            out.append({"coverage": _COV, "component": comp, "period": per,
                        "frequency": "quarterly", "measure": "stock",
                        "value": v, "unit": unit, "series_code": code})

    # Tableau 1: 10 numbers per row (USD, XAF per quarter)
    parent, pending = None, ""
    t1rows = {}
    for ln in t1:
        nums = _NUM.findall(ln)
        label = _NUM.sub("", ln).strip()
        if len(nums) == 10:
            label = (pending + " " + label).strip() if pending else label
            pending = ""
            if label in ("Dette extérieure", "Dette intérieure", "Dette Totale"):
                parent = label
                comp = label
            elif label == "Stocks arriérés":
                comp = f"{parent}: Stocks arriérés"
            elif label in ("Encours hors", "Encours hors arriérés", ""):
                comp = f"{parent}: Encours hors arriérés"
            else:
                raise ValueError(f"CCA Tableau 1: unexpected row {label!r}")
            vals = [_f(x) for x in nums]
            t1rows[comp] = vals
            add(comp, vals[0::2], "USD milliards", "CCA T1")
            add(comp, vals[1::2], "FCFA milliards", "CCA T1")
        elif label.startswith("Encours hors"):
            pending = ""                       # label head; the tail follows
    need = {"Dette extérieure", "Dette intérieure", "Dette Totale",
            "Dette extérieure: Stocks arriérés", "Dette extérieure: Encours hors arriérés",
            "Dette intérieure: Stocks arriérés", "Dette intérieure: Encours hors arriérés"}
    if set(t1rows) != need:
        raise ValueError(f"CCA Tableau 1: rows {sorted(t1rows)}")
    for j in range(1, 10, 2):
        x = lambda c: t1rows[c][j]
        if abs(x("Dette extérieure") + x("Dette intérieure") - x("Dette Totale")) > 0.05:
            raise ValueError("CCA Tableau 1: external + domestic != total")
        for p in ("Dette extérieure", "Dette intérieure"):
            if abs(x(f"{p}: Stocks arriérés") + x(f"{p}: Encours hors arriérés") - x(p)) > 0.05:
                raise ValueError(f"CCA Tableau 1: {p} parts do not sum")

    # Tableau 2: 5 stocks + the latest share
    t2rows = {}
    for ln in t2:
        nums = _NUM.findall(ln)
        m = re.search(r"([\d,]+)%\s*$", ln)
        if len(nums) >= 5 and m:
            label = ln[:ln.index(nums[0])].strip()
            vals = [_f(x) for x in nums[:5]]
            t2rows[label] = vals
            add(label, vals, "FCFA milliards", "CCA T2")
            out.append({"coverage": _COV, "component": label, "period": latest,
                        "frequency": "quarterly", "measure": "share",
                        "value": _f(m.group(1)), "unit": "percent",
                        "series_code": "CCA T2"})
    for j in range(5):
        ext = t2rows["Dette extérieure"][j]
        parts = sum(t2rows[k][j] for k in ("Dette bilatérale", "Dette multilatérale",
                                           "Dette commerciale"))
        if abs(ext - parts) > 0.05:
            raise ValueError("CCA Tableau 2: creditor classes do not sum to external")
        if abs(ext - t1rows["Dette extérieure"][2 * j + 1]) > 0.05:
            raise ValueError("CCA Tableau 2 external disagrees with Tableau 1")

    # Tableau 3: currencies
    total = None
    cur = {}
    for ln in t3:
        nums = re.findall(r"\d[\d ]*,\d+", ln)
        m = re.match(r"^([A-Z]{3}|TOTAL)\s", ln)
        if m and len(nums) == 5:
            vals = [_f(x) for x in nums]
            if m.group(1) == "TOTAL":
                total = vals
            else:
                cur[m.group(1)] = vals
                add(f"Dette extérieure par devise: {m.group(1)}", vals,
                    "FCFA milliards", "CCA T3")
    if total is None or not cur:
        raise ValueError("CCA Tableau 3: no currency rows")
    for j in range(5):
        if abs(sum(v[j] for v in cur.values()) - total[j]) > 0.05:
            raise ValueError("CCA Tableau 3: currencies do not sum to TOTAL")
        if abs(total[j] - t2rows["Dette extérieure"][j]) > 0.05:
            raise ValueError("CCA Tableau 3 total disagrees with Tableau 2")

    for j in range(5):
        if abs(t2rows["Stock total"][j] - t1rows["Dette Totale"][2 * j + 1]) > 0.05:
            raise ValueError("CCA Tableau 2 stock total disagrees with Tableau 1")
    df = pd.DataFrame(out)
    # Tableau 2's "Dette extérieure"/"Dette intérieure" FCFA stocks repeat
    # Tableau 1's (checked equal above): keep Tableau 1's.
    dup = (df["series_code"] == "CCA T2") & (df["measure"] == "stock") & \
        df["component"].isin(["Dette extérieure", "Dette intérieure", "Stock total"])
    return df[~dup].reset_index(drop=True)


# ---------------------------------------------------------------------------
# THE 2024 BULLETINS (n°01, covering 2019-2023; and 2nd quarter 2024) have no
# stock Tableau 1. Their "Tableau 2: Encours, Tirages et service de la dette
# de l'administration centrale" opens with three STOCK rows -- Total de
# l'encours, Dette extérieure, Dette intérieure -- in USD and FCFA milliards,
# for year-ends (2019..2023) and, in the 2nd-quarter issue, 2024 T1 and T2.
# Same perimeter (administration centrale) and the same figures as the later
# Tableau 1 where they overlap (end-2023 total 8 516,36), but a different
# table, so it keeps its own series code. Flows below them are not read.
# The header splits years ("202 1"); they are rejoined. Checked: external +
# domestic = total (to 0,1), both currencies.
_T2_ENC = re.compile(r"Tableau 2\s*:\s*Encours, Tirages et service de la dette")
_T2_ROWS = {"Total de l'encours": "Dette Totale", "Dette extérieure": "Dette extérieure",
            "Dette intérieure": "Dette intérieure"}


def _tableau2_encours(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        page = next((p.extract_text() for p in pdf.pages
                     if _T2_ENC.search(p.extract_text() or "")
                     and "____" not in (p.extract_text() or "")
                     and "....." not in (p.extract_text() or "")), None)
    if page is None:
        print(f"[congo] {path.rsplit('/', 1)[-1]}: no Tableau 1 or 2 -- not read")
        return []
    body = page[_T2_ENC.search(page).end():]
    first = body.index("Total de l'encours")
    head = re.sub(r"\b(20\d) (\d)\b", r"\1\2", body[:first])
    quarters = [f"{y}-Q{q}" for q, y in re.findall(r"([1-4])(?:er|e|ème)\s+Trim\s+(20\d\d)", head)]
    years = re.findall(r"(?<!Trim )\b(20\d\d)\b", re.sub(r"[1-4](?:er|e|ème)\s+Trim\s+20\d\d", "", head))
    periods = [(y, "annual") for y in years] + [(q, "quarterly") for q in quarters]
    if len(years) != len(set(years)) or sorted(years) != years or not periods:
        raise ValueError(f"CCA Tableau 2: header {years} {quarters} in {path}")
    got = {}
    for ln in body[first:].splitlines():
        for lab in _T2_ROWS:
            if lab not in got and ln.startswith(lab + " "):
                nums = _NUM.findall(ln[len(lab):])
                if len(nums) != 2 * len(periods):
                    raise ValueError(f"CCA Tableau 2 {lab}: {len(nums)} cells for "
                                     f"{len(periods)} periods in {path}")
                got[lab] = [_f(x) for x in nums]
    if set(got) != set(_T2_ROWS):
        raise ValueError(f"CCA Tableau 2: rows {sorted(got)} in {path}")
    for j in range(2 * len(periods)):
        if abs(got["Dette extérieure"][j] + got["Dette intérieure"][j]
               - got["Total de l'encours"][j]) > 0.1:
            raise ValueError(f"CCA Tableau 2 {path}: external + domestic != total (cell {j})")
    out = []
    for lab, comp in _T2_ROWS.items():
        vals = got[lab]
        for (per, freq), usd, xaf in zip(periods, vals[0::2], vals[1::2]):
            for v, unit in ((usd, "USD milliards"), (xaf, "FCFA milliards")):
                out.append({"coverage": _COV, "component": comp, "period": per,
                            "frequency": freq, "measure": "stock", "value": v,
                            "unit": unit, "series_code": "CCA Encours-Tirages-Service"})
    return out
