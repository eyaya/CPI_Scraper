"""Tunisia — Ministère des Finances (D.G.R.E.), "Résultats provisoires de
l'exécution du Budget de l'Etat", monthly bulletin, page "Public debt / Dette
publique" (section II, "Encours de la Dette Publique").

PUBLISHER: the Ministry of Finance -- Tunisia's official compiler of public-debt
statistics (it also feeds the SDDS page at the back of the same bulletin).

COVERAGE: the bulletin's own label is "Encours de la Dette Publique" in a
bulletin covering the State budget ("cover State's Budget", page 2), i.e. the
debt of the State (central government). It is recorded as published:
"Dette publique (Etat), as published by the Ministère des Finances".

WHAT ONE ISSUE GIVES. The page is a grid of columns headed by the bulletin's
own labels, read from the header geometry every run:

    End December   End November    LF     (unlabelled)
    2025   2024    2025   2024     2025   2023   2022

* the two "End <month>" groups are end-of-month positions, current year and
  year earlier -> monthly periods (2025-12, 2024-12, 2025-11, 2024-11);
* "LF" / "LFR" (loi de finances / rectificative) columns are BUDGET FORECASTS,
  not outturns -> never collected;
* the unlabelled columns to the right are past end-year outturns -> annual.
The column set changes between issues (December 2023 prints LF, LFR and LF
over three years; the second group is the PREVIOUS month, e.g. August issue =
July and August); the header is parsed, never assumed. January issues head
their columns in Arabic only and are not read (raise; skipped as an extra).

Rows taken, in printed order, all in MDT (millions de dinars tunisiens, page 2):
  Outstanding public debt (stock) and its "% du PIB" (share_of_gdp);
  Domestic debt (stock) and its "% part" (share of total);
  Foreign debt (stock) and its "% part" (share of total).
Checked every run: domestic + foreign = total (to 0.2 MDT) and the two shares
sum to 100 (to 0.2) in every column; the %-of-GDP line prints no value for the
second "End <month>" group, and is mapped by x position, not order.

NOT COLLECTED: debt service, amortisation and interest (flows, not stocks); the
external-debt-by-currency / by-creditor breakdowns (pie charts, labels only);
forecast columns. Some issues are SCANS with no text layer (e.g. "BULLETIN MAI
2025"): such an issue raises, and as an extra it is skipped with a message.

CROSS-CHECK (December 2025 issue): encours end-Dec 2025 141 665,4 MDT (82,1% of
GDP); domestic 86 178,0 (60,8%); foreign 55 487,3 (39,2%); end-2022 114 895,7.
"""
from __future__ import annotations

import collections
import re

import fitz  # PyMuPDF
import pandas as pd

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}
# Some issues head a column group in French ("End June | End Mai").
_MONTHS.update({"janvier": 1, "février": 2, "fevrier": 2, "mars": 3,
                "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "août": 8,
                "aout": 8, "septembre": 9, "octobre": 10, "décembre": 12})
_UNIT = "TND million"
_NUM = re.compile(r"^-?\d{1,3}(?:,\d+)?%?$")


def _lines(page) -> list[list[tuple]]:
    rows = collections.defaultdict(list)
    for w in page.get_text("words"):
        rows[round(w[1] / 2.5)].append(w)
    return [sorted(rows[k], key=lambda w: w[0]) for k in sorted(rows)]


def _values(line) -> list[tuple[float, float, bool]]:
    """(x, value, is_percent) for each number on a line. A thousands group is
    printed as a separate word ("141" "665,4"): rejoin a 1-3 digit word with
    the "ddd,d" word that follows it within 15 points."""
    out, i, ws = [], 0, [w for w in line if _NUM.match(w[4])]
    while i < len(ws):
        x, t = ws[i][0], ws[i][4]
        if (i + 1 < len(ws) and re.fullmatch(r"-?\d{1,3}", t)
                and re.fullmatch(r"\d{3},\d+%?", ws[i + 1][4])
                and ws[i + 1][0] - ws[i][2] < 15):
            t = t + ws[i + 1][4]
            i += 1
        pct = t.endswith("%")
        out.append((x, float(t.rstrip("%").replace(",", ".")), pct))
        i += 1
    return out


def _debt_page(doc):
    for page in doc:
        tx = page.get_text()
        if "Encours de la Dette Publique" in tx and "% part" in tx:
            return page
    raise ValueError("Tunisia MoF bulletin: no debt page with a text layer "
                     "(scanned issue?)")


def _columns(lines) -> list[tuple[float, str, str]]:
    """[(x, frequency|'forecast', period)] from the header geometry."""
    hdr = next((i for i, l in enumerate(lines)
                if any(w[4] == "End" for w in l)), None)
    if hdr is None:
        # January issues head their columns in Arabic only ("جانفي"); without
        # a readable month label the columns cannot be dated, so the issue is
        # not read rather than guessed.
        raise ValueError("Tunisia MoF: no 'End <month>' header on the debt page")
    labels = []
    for j, w in enumerate(lines[hdr]):
        if w[4] == "End":
            labels.append((w[0], "end", lines[hdr][j + 1][4].lower()))
    # LF / LFR labels may sit on the header line or the one after it
    for l in lines[hdr:hdr + 2]:
        labels += [(w[0], "forecast", w[4]) for w in l if w[4] in ("LF", "LFR")]
    years_line = next(l for l in lines[hdr + 1:hdr + 4]
                      if sum(bool(re.fullmatch(r"20\d\d", w[4])) for w in l) >= 4)
    cols = [(w[0], w[4]) for w in years_line if re.fullmatch(r"20\d\d", w[4])]
    claimed: dict[int, tuple[str, str]] = {}
    for lx, kind, word in labels:
        if kind == "forecast":
            i = min(range(len(cols)), key=lambda k: abs(cols[k][0] - lx))
            claimed[i] = ("forecast", cols[i][1])
    for lx, kind, word in labels:
        if kind == "end":
            if word not in _MONTHS:
                raise ValueError(f"Tunisia MoF: unknown month label {word!r}")
            month = _MONTHS[word]
            near = sorted((k for k in range(len(cols)) if k not in claimed),
                          key=lambda k: abs(cols[k][0] - lx))[:2]
            for k in near:
                claimed[k] = ("monthly", f"{cols[k][1]}-{month:02d}")
    return [(cols[k][0],) + claimed.get(k, ("annual", cols[k][1]))
            for k in range(len(cols))]


def _parse_one(path: str) -> list[dict]:
    doc = fitz.open(path)
    page = _debt_page(doc)
    lines = _lines(page)
    cols = _columns(lines)
    start = next(i for i, l in enumerate(lines)
                 if "Encours" in " ".join(w[4] for w in l))
    # Only numbers inside the grid count: the section numbers printed at the
    # right margin ("1", "2", "-2") are not values.
    right = max(c[0] for c in cols) + 30
    series = [v for l in lines[start:]
              if (v := [t for t in _values(l) if t[0] <= right])][:6]
    kinds = [all(p for _, _, p in s) for s in series]
    if kinds != [False, True, False, True, False, True]:
        raise ValueError(f"Tunisia MoF: unexpected encours block shape {kinds}")

    def assign(vals):
        out = {}
        for x, v, _ in vals:
            k = min(range(len(cols)), key=lambda i: abs(cols[i][0] - x))
            if abs(cols[k][0] - x) > 20 or k in out:
                raise ValueError(f"Tunisia MoF: value at x={x:.0f} has no column")
            out[k] = v
        return out

    total, gdp, dom, dom_s, ext, ext_s = (assign(s) for s in series)
    for k in total:
        if abs(dom[k] + ext[k] - total[k]) > 0.2:
            raise ValueError(f"Tunisia MoF: domestic + foreign != total in "
                             f"column {cols[k][2]}")
        if abs(dom_s[k] + ext_s[k] - 100) > 0.2:
            raise ValueError(f"Tunisia MoF: shares do not sum to 100 in "
                             f"column {cols[k][2]}")
    rows = []
    spec = [("Outstanding public debt / Encours de la dette publique", total, "stock"),
            ("Outstanding public debt / Encours de la dette publique", gdp, "share_of_gdp"),
            ("Domestic debt / Dette intérieure", dom, "stock"),
            ("Domestic debt / Dette intérieure", dom_s, "share"),
            ("Foreign debt / Dette extérieure", ext, "stock"),
            ("Foreign debt / Dette extérieure", ext_s, "share")]
    for comp, vals, measure in spec:
        for k, v in vals.items():
            _, freq, period = cols[k]
            if freq == "forecast":
                continue
            rows.append({"component": comp, "period": period, "frequency": freq,
                         "measure": measure, "value": v,
                         "unit": _UNIT if measure == "stock" else "percent",
                         "series_code": "MoF-TN Résultats provisoires, Dette publique"})
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = _parse_one(path)
    for p in extras or []:
        try:
            rows += _parse_one(p)
        except ValueError as e:
            print(f"[tunisia_mof_debt] skipped {p}: {e}")
    df = pd.DataFrame(rows)
    # An older issue restates a period a newer one also prints; the primary
    # (newest) issue is read first, so keep the first reading of each key.
    key = ["component", "period", "frequency", "measure"]
    return df.drop_duplicates(key, keep="first").reset_index(drop=True)
