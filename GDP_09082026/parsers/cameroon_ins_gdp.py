"""Parser for the INS Cameroun quarterly national-accounts note PDF (Tier 3).

The 'Note d'analyse CNT' annex (pages ~12-19) carries the quarterly GDP (PIB)
breakdown tables. Each table lists, per row (a branch or an expenditure
component), six quarters of LEVELS followed by the six matching year-on-year
percentage changes; the period header row gives the quarters as 'Tn_YYYY'.

Text is clean French (not reversed) but numbers use French formatting — a space
as the thousands separator and a comma as the decimal ('6 401,1' = 6401.1). We
extract the leading label, then every French number in order: the first six are
the quarterly levels, the next six the YoY growth.

Table routing from the caption:
  'branche' / 'secteur'  -> production      'composante'      -> expenditure
  'courant'              -> current prices  'volume chaîné'   -> constant (chained)
  'CVS-CJO'              -> seasonally adjusted, else 'brut' = not adjusted
Contribution tables are skipped. Values are billion XAF (FCFA). Everything as
published by INS; nothing derived.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_PERIOD_RE = re.compile(r"T([1-4])[_ ]?(20\d\d)")
# A French number: digits, optional space-grouped thousands, optional decimal
# comma, optional sign. NOT r"\d{1,3}(?:\s\d{3})*...": the current-price tables
# print levels WITHOUT a thousands space ("6972,9"), which that pattern split
# into "697" + "2,9" -- current FCE/FBCF/exports were published as 2.9/3.8/6.6
# (fixed 2026-10-15). The sign matters for levels like changes in inventories.
_FRNUM_RE = re.compile(r"(?<![\w,])-?\d+(?:\s\d{3})*(?:,\d+)?")

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _spec(caption: str):
    c = caption.lower()
    if "contribution" in c:
        return None
    if "composante" in c:
        approach = "expenditure"
    elif "branche" in c or "secteur" in c:
        approach = "production"
    else:
        return None
    if "courant" in c:
        basis = "current"
    elif "volume" in c or "chaîné" in c or "chaine" in c:
        basis = "constant"
    else:
        return None
    seasonal = "saa" if "cvs" in c else "nsa"
    return approach, basis, seasonal


def _caption(page) -> str:
    lines = [l for l in (page.extract_text() or "").split("\n") if l.strip()]
    return " ".join(lines[:3])


def _periods(tb):
    for row in tb[:4]:
        pers, seen = [], set()
        for c in row:
            for m in _PERIOD_RE.finditer(re.sub(r"\s", "", str(c or ""))):
                p = f"{m.group(2)}-Q{m.group(1)}"
                if p not in seen:
                    seen.add(p); pers.append(p)
        if len(pers) >= 4:
            return pers
    return []


def _frval(tok: str):
    t = tok.replace(" ", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _parse_table(tb, approach, basis, seasonal, base):
    periods = _periods(tb)
    if not periods:
        return []
    n = len(periods)
    rows = []
    for row in tb:
        joined = " ".join(str(c) for c in row if c).strip()
        joined = re.sub(r"\s+", " ", joined)
        label = re.match(r"^([^\d]+?)\s*(?=\d)", joined)
        if not label:
            continue
        # a trailing "-" is the SIGN of the first number ("SIFIM -20,6"), not label
        label = label.group(1).strip(" .:-")
        low = label.lower()
        # skip title / header / prose rows (only real economic categories pass)
        if (not label or _PERIOD_RE.search(label) or len(label) < 3
                or len(label.split()) > 8
                or any(k in low for k in ("libell", "ventilation", "référence",
                                          "reference", "variation", "contribution",
                                          "croissance", "source", "note", "trimestr"))):
            continue
        nums = [v for v in (_frval(t) for t in _FRNUM_RE.findall(joined)) if v is not None]
        if len(nums) < n:
            continue
        approach_r = "aggregate" if low == "pib" or low.startswith("pib ") else approach
        base_p = base if basis == "constant" else ""
        # Emit LEVELS only (first n numbers). The trailing % block differs by table
        # (T/T-4 YoY on 'brut' tables, T/T-1 QoQ on CVS-CJO), so growth is left for a
        # later pass to avoid mislabelling it.
        for period, v in zip(periods, nums[0:n]):
            rows.append({
                "approach": approach_r, "category": label, "category_group": "",
                "series_code": "", "geography": "National", "period": period,
                "frequency": "quarterly", "price_basis": basis,
                "seasonal_adjustment": seasonal, "measure": "level",
                "value": v, "unit": "XAF billion", "base_period": base_p,
            })
    return rows


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """The current note, plus OLDER NOTES (extras) for quarters it does not print.

    Each quarterly note prints only six quarters, so the series is built from
    the back issues INS keeps in its media library (2014 onward). Extras are
    read newest note first, and a note contributes ONLY the quarters no newer
    note already gave -- so every quarter comes from the latest note that prints
    it, and older vintages never overwrite revisions. `category_group` names the
    note each row came from. A note whose layout this reader does not know
    (several 2013-2016 notes) raises in `_parse_one` and is skipped with a
    message rather than misread. The chained-volume reference year stays in
    `base_period`, so a rebase never chains silently.
    """
    df = _parse_one(pdf_path)
    have = set(df["period"])
    for ex in sorted(extras or [], key=_note_key, reverse=True):
        try:
            old = _parse_one(ex)
        except ValueError as e:
            print(f"  [cameroon] skipped {ex.replace(chr(92), '/').rsplit('/', 1)[-1]}: {e}")
            continue
        old = old[~old["period"].isin(have)]
        if old.empty:
            continue
        y, q = _note_key(ex)
        old["category_group"] = f"INS CNT note T{q} {y}"
        have |= set(old["period"])
        df = pd.concat([df, old], ignore_index=True)
    return df


def _note_key(path: str) -> tuple[int, int]:
    """(year, quarter) of a note, from INS's file names: '_T1_2024',
    '3eme_Trim_2019', 'CNT-4T2012', 'T4_2020_Revision'."""
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    for rx in (r"T([1-4])[_-]?(20\d\d)", r"([1-4])(?:eme|er|e)?_?Trim_?(20\d\d)",
               r"([1-4])T(20\d\d)"):
        m = re.search(rx, name, re.I)
        if m:
            return int(m.group(2)), int(m.group(1))
    return 0, 0


def _parse_one(pdf_path: str) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            cap = _caption(page)
            spec = _spec(cap)
            if not spec:
                continue
            ref = re.search(r"r[ée]f[ée]rence\s*(20\d\d)", cap, re.I)
            base = f"chained volume, reference {ref.group(1)}" if ref else "chained volume"
            tbls = [tb for tb in page.extract_tables() if len(tb) >= 10]
            for tb in tbls:
                rows.extend(_parse_table(tb, *spec, base))
    if not rows:
        raise ValueError("no GDP rows parsed from INS Cameroun note")
    out = pd.DataFrame.from_records(rows)[_OUT_COLS]
    return out.drop_duplicates(["approach", "category", "period", "measure",
                                "price_basis", "seasonal_adjustment"])
