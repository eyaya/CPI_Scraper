"""Comoros — Ministère des Finances et du Budget, Direction de la Dette
Publique (DDP), "Bulletin statistique de la dette publique" (quarterly),
Tableaux 1-3.

PUBLISHER: DDP / MFB, finances.gouv.km (source line "Meridian/ DDP").
COVERAGE: central government (the bulletin's own heading: "dette de
l'administration centrale"), external + domestic.

TWO COLUMNS PER TABLE: "2025" (the end-2025 stock -> annual period 2025) and
"T1 2026" (-> 2026-Q1). Amounts in millions of KMF.

* Tableau 1  external, domestic and total public debt stock; "Part de la dette
             extérieure / intérieure" (measure share). "Variation (en %)" rows
             are computed changes and are not collected.
* Tableau 2  external debt by creditor: Multilatéraux, Bilatéraux, Banques
             commerciales extérieures and every named creditor, labelled
             "<group>: <creditor>"; each group must equal the sum of its
             creditors and the total must equal Tableau 1's external debt.
* Tableau 3  domestic debt by financing type: bank debt and "Autres moyens de
             financement et de trésorerie" with their lines; total = Tableau 1.

READ BY WORD POSITION. Counts use SPACE thousands and sit side by side
("176 900 180 354"), which splits more than one way. Each number token is
assigned to the column whose header ("2025", "2026") it lies under, and every
identity above must hold, so a mis-split raises rather than ships.

PINNED PUBLISHED INCONSISTENCY (`_KNOWN_GAPS`): T1 2026 multilateral
creditors sum to 100 489 vs the printed 92 943; the groups to 180 367 vs the
printed 180 354. Kept as printed.

CROSS-CHECK (T1 2026, KMF million): public debt 219 765; external 180 354;
domestic 39 411; IDA 48 341; Exim Bank Chine 37 556; external share 82,07%.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_SERIES = "DDP Bulletin statistique de la dette publique"
_UNIT = "KMF million"
_NUM = re.compile(r"^\d{1,3}$")
_PCT = re.compile(r"^(\d{1,3},\d+)%$")
_T2_GROUPS = {"Total multilatéraux": "Multilatéraux", "Total bilatéraux": "Bilatéraux",
              "Banques commerciales extérieures": "Banques commerciales extérieures"}
# PUBLISHED INCONSISTENCIES, pinned: (table, group or "__total__", column) ->
# (printed figure, sum of its printed parts). T1 2026's multilateral creditors
# sum to 100 489 against a printed group total of 92 943 (IDA's 48 341 is the
# likely misprint: 92 943 - the others = 40 795), and the three groups then sum
# to 180 367 against the printed external total of 180 354 (= Tableau 1). All
# figures are kept AS PRINTED; any other gap, or a change to these, raises.
_KNOWN_GAPS = {
    ("Tableau 2", "Multilatéraux", 1): (92943.0, 100489.0),
    ("Tableau 2", "__total__", 1): (180354.0, 180367.0),
}
_T3_GROUPS = ("Dette intérieure bancaire", "Autres moyens de financement et de trésorerie")


def _page_lines(page):
    """Rows rebuilt from words: (label, [col0 tokens], [col1 tokens], pct list)."""
    words = page.extract_words(keep_blank_chars=False)
    hdr = [w for w in words if w["text"] in ("2025", "2026")]
    if len(hdr) < 2:
        return None
    x2025 = next(w["x1"] for w in hdr if w["text"] == "2025")
    x2026 = next(w["x1"] for w in hdr if w["text"] == "2026")
    lines = {}
    for w in words:
        lines.setdefault(round(w["top"] / 3), []).append(w)
    out = []
    for _, ws in sorted(lines.items()):
        ws.sort(key=lambda w: w["x0"])
        label, cols, pcts = [], ([], []), []
        for w in ws:
            t = w["text"]
            if _NUM.match(t) and w["x0"] > x2025 - 90:
                cols[0 if abs(w["x1"] - x2025) < abs(w["x1"] - x2026) else 1].append(t)
            elif _PCT.match(t):
                pcts.append(t)
            else:
                label.append(t)
        out.append((" ".join(label).strip(), cols, pcts))
    return out


def _v(tokens) -> float:
    return float("".join(tokens))


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        pages = {}
        for p in pdf.pages:
            t = p.extract_text() or ""
            for n in (1, 2, 3):
                if re.search(rf"^Tableau {n} ?:", t, re.M):
                    pages[n] = _page_lines(p)
    if set(pages) != {1, 2, 3}:
        raise ValueError(f"Comoros DDP: tables found {sorted(pages)}")
    periods = ("2025", "2026-Q1")
    freqs = ("annual", "quarterly")
    rows = []

    def add(comp, vals, measure="stock", unit=_UNIT, code=""):
        for p, f, v in zip(periods, freqs, vals):
            rows.append({"component": comp, "period": p, "frequency": f,
                         "measure": measure, "value": v, "unit": unit,
                         "series_code": f"{_SERIES}, {code}"})

    # Tableau 1
    t1 = {}
    for label, cols, pcts in pages[1]:
        if label in ("Dette extérieure", "Dette intérieure", "Dette publique") and all(cols):
            t1[label] = (_v(cols[0]), _v(cols[1]))
            add(label, t1[label], code="Tableau 1")
        elif label.startswith("Part de la dette") and len(pcts) == 2:
            add(label, [float(x.rstrip("%").replace(",", ".")) for x in pcts],
                measure="share", unit="percent", code="Tableau 1")
    if len(t1) != 3 or any(abs(t1["Dette extérieure"][i] + t1["Dette intérieure"][i]
                               - t1["Dette publique"][i]) > 1 for i in (0, 1)):
        raise ValueError(f"Comoros Tableau 1: {t1}")

    # Tableaux 2 and 3: groups with member lines, then a grand total.
    def grouped(lines, groups, total_label, want, code):
        group, sums, gv, total = None, {}, {}, None
        for label, cols, _ in lines:
            if not all(cols) or not label:
                continue
            vals = (_v(cols[0]), _v(cols[1]))
            if label == total_label:
                total = vals
                continue
            if label in groups:
                group = groups[label] if isinstance(groups, dict) else label
                gv[group], sums[group] = vals, [0.0, 0.0]
                add(group, vals, code=code)
            elif group:
                sums[group][0] += vals[0]
                sums[group][1] += vals[1]
                add(f"{group}: {label}", vals, code=code)
        names = list(groups.values()) if isinstance(groups, dict) else list(groups)
        if set(gv) != set(names) or total is None:
            raise ValueError(f"Comoros {code}: groups {list(gv)}, total {total}")
        def check(key, printed, parts):
            if abs(printed - parts) <= 1:
                return
            if _KNOWN_GAPS.get(key) != (printed, parts):
                raise ValueError(f"Comoros {key}: printed {printed} vs parts {parts}")

        for g in names:
            for i in (0, 1):
                check((code, g, i), gv[g][i], round(sums[g][i], 1))
        for i in (0, 1):
            check((code, "__total__", i), total[i], round(sum(gv[g][i] for g in names), 1))
        if any(abs(total[i] - want[i]) > 1 for i in (0, 1)):
            raise ValueError(f"Comoros {code}: total {total} vs Tableau 1 {want}")

    grouped(pages[2], _T2_GROUPS, "Total encours extérieur", t1["Dette extérieure"], "Tableau 2")
    grouped(pages[3], _T3_GROUPS, "Total", t1["Dette intérieure"], "Tableau 3")
    return pd.DataFrame(rows)
