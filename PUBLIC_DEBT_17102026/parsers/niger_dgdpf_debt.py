"""Niger — Bulletin Statistique sur la Dette Publique, Direction Générale de la
Dette Publique et du Financement (DGDPF), Ministère de l'Economie et des
Finances, on finances.gouv.ne (PhocaDownload, `?download=<id>`).

COVERAGE, as the bulletin defines it ("Périmètre de la dette utilisé"): the
external and domestic debt contracted by the CENTRAL ADMINISTRATION, including
debt on-lent to public enterprises, EXCLUDING state-guaranteed debt. The
external/domestic split is by CURRENCY, not residence, except BOAD loans in
FCFA, which count as external.

WHAT IS READ: Tableau 1 "Encours de la dette publique (extérieure et
intérieure) par type de dette", milliards FCFA. Five period columns of stocks,
then "% du PIB" and "% du total" for the LAST column only:
  * quarterly issues -- five consecutive quarter-ends ending with the issue's
    quarter (T4 2025: Dec 2024, Mar, Jun, Sep, Dec 2025);
  * the annual issue -- five year-ends (2020..2024), dated as annual periods.
The header wraps its month words across lines, so periods are rebuilt from the
ORDER of month words and years in the header block and must come out
consecutive; anything else raises. Every period is held to the table's own
identities (to 0,02):
  dette publique   = dette intérieure + dette extérieure
  dette extérieure = multilatérale + bilatérale + commerciale
  instruments      = bons + obligations du Trésor
"-" is an empty cell (titrisation, passifs), never zero.

% du PIB is relative to the GDP each issue states ("PIB nominal = 12 354,12"),
which differs between issues; collected as printed per issue's period.

NOT READ: creditor/currency tables (2-3), cost-risk indicators (4), on-lent
and guaranteed debt (5-6, 17 -- outside the perimeter), flows (7-14), PPPs.

CROSS-CHECK: end-Dec 2025 dette publique totale brute 5 913,27 (47,9 % of
GDP), intérieure 2 739,88, extérieure 3 173,39; end-Sep 2025 5 880,00; end-2020
3 510,39 (annual 2024 issue).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_UNIT = "FCFA milliards"
# Two decimals and space-grouped thousands since 2024 ("3 510,39"); the
# 2022-2023 issues mix one decimal and unspaced thousands ("4205,7").
_NUM = r"(?:\d{1,3}(?: \d{3})*,\d{1,2}|\d+,\d{1,2}|-)"
_ROW = re.compile(rf"^(?P<lab>[A-Za-zéèêÉ][^\d%-]*?)\s+(?P<v>(?:{_NUM}\s+){{4}}{_NUM})"
                  rf"(?:\s+(?P<pib>\d{{1,3}}(?:,\d)?)%\s+(?P<tot>\d{{1,3}}(?:,\d)?)%)?$")
_MONTH_Q = {"mars": 1, "juin": 2, "septembre": 3, "décembre": 4, "decembre": 4}


def _num(s: str):
    return None if s == "-" else float(s.replace(" ", "").replace(",", "."))


def _periods(header: str) -> list[tuple[str, str]]:
    months = [m.lower() for m in re.findall(
        r"\b(mars|juin|septembre|d[ée]cembre)\b", header, re.I)]
    years = [int(y) for y in re.findall(r"\b(20\d\d)\b", header)]
    if len(months) != 5 or len(years) != 5:
        raise ValueError(f"DGDPF NE: header gives {months} / {years}")
    if set(months) == {"décembre"} or set(months) == {"decembre"}:
        ys = sorted(years)
        if ys != list(range(ys[0], ys[0] + 5)):
            raise ValueError(f"DGDPF NE: annual columns not consecutive {ys}")
        return [(str(y), "annual") for y in ys]
    # Quarterly issue: the header scatters month words and years across
    # lines, but the five columns are consecutive quarter-ends. The LAST year
    # printed with the latest quarter anchors the sequence.
    # The header's words and years cannot be paired by position, so try every
    # final quarter of the latest year and keep the ONE whose five consecutive
    # quarter-ends reproduce exactly the header's month words and its years.
    qs = sorted(_MONTH_Q[m.replace("decembre", "décembre")] for m in months)
    last_y = max(years)
    fits = []
    for q_end in (1, 2, 3, 4):
        seq, (y, q) = [], (last_y, q_end)
        for _ in range(5):
            seq.append((y, q))
            y, q = (y, q - 1) if q > 1 else (y - 1, 4)
        seq.reverse()
        if sorted(q for _, q in seq) == qs and sorted(y for y, _ in seq) == sorted(years):
            fits.append(seq)
    if len(fits) != 1:
        raise ValueError(f"DGDPF NE: header {months} / {years} fits "
                         f"{len(fits)} consecutive quarter sequences")
    return [(f"{y}-Q{q}", "quarterly") for y, q in fits[0]]


def _table1(path: str) -> tuple[list[tuple[str, str]], dict]:
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:15]:
            t = page.extract_text() or ""
            m = re.search(r"Tableau 1\s*[–-]\s*Encours de la dette publique", t)
            if m and "Dette publique totale brute" in t:
                body = t[m.end():]
                head = body[:body.index("Pour référence")] if "Pour référence" in body \
                    else body[:body.index("Dette publique totale")]
                rows = {}
                for ln in body.splitlines():
                    r = _ROW.match(ln.strip())
                    if r:
                        raw = re.findall(_NUM, r.group("v"))
                        rows[r.group("lab").strip()] = (
                            # Space-grouped thousands: split by the number
                            # pattern, never on whitespace ("3 510,39").
                            [_num(v) for v in raw],
                            r.group("pib"), r.group("tot"),
                            # columns printed to ONE decimal (2022-2023)
                            [bool(re.search(r",\d$", v)) for v in raw])
                    if ln.startswith("Bulletin Statistique"):
                        break
                return _periods(head), rows
    raise ValueError("DGDPF NE: Tableau 1 not found")


def _check(rows: dict, j: int, where: str) -> None:
    # Two-decimal columns must add to 0,02; a column printed to one decimal
    # (2022-2023 issues: "4205,7" = 1474,7 + 2730,9 printed as 4205,6) to
    # 0,15 -- the rounding of three one-decimal figures.
    tol = 0.15 if any(r[3][j] for r in rows.values()) else 0.02
    def v(k):
        x = rows[k][0][j]
        return 0.0 if x is None else x
    for tot, parts in (("Dette publique totale brute", ("Dette intérieure", "Dette extérieure")),
                       ("Dette extérieure", ("Multilatérale", "Bilatérale", "Commerciale")),
                       ("Instruments financiers", ("Bons du Trésor", "Obligations du Trésor"))):
        s = sum(v(p) for p in parts)
        if abs(s - v(tot)) > tol:
            raise ValueError(f"DGDPF NE {where}: {tot} {v(tot)} != parts {s:.2f}")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    out = {}
    # Oldest issue first, so the newest issue wins where periods overlap.
    for p in list(reversed(extras or [])) + [path]:
        periods, rows = _table1(p)
        need = {"Dette publique totale brute", "Dette intérieure", "Dette extérieure",
                "Multilatérale", "Bilatérale", "Commerciale", "Instruments financiers",
                "Bons du Trésor", "Obligations du Trésor"}
        if not need <= set(rows):
            raise ValueError(f"DGDPF NE {p}: rows missing {need - set(rows)}")
        for j, (per, freq) in enumerate(periods):
            _check(rows, j, f"{p} {per}")
            for lab, (vals, pib, tot, _) in rows.items():
                if vals[j] is not None:
                    out[(lab, per, freq, "stock", _UNIT)] = vals[j]
                if j == len(periods) - 1:
                    if pib:
                        out[(lab, per, freq, "share_of_gdp", "percent")] = _num(pib)
                    if tot:
                        out[(lab, per, freq, "share", "percent")] = _num(tot)
    return pd.DataFrame([{"component": c, "period": per, "frequency": f,
                          "measure": m, "value": v, "unit": u,
                          "series_code": "DGDPF T1"}
                         for (c, per, f, m, u), v in out.items()])
