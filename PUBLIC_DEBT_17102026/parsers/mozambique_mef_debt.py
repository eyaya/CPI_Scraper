"""Mozambique — Ministério da Economia e Finanças (MEF), "Boletim da Dívida
Pública" (quarterly), Tabelas 1, 2 and 6.

PUBLISHER: MEF, mef.gov.mz "Gestão da Dívida Pública" publications (source
line on every table: "MF – Meridian", the debt recording system). Each issue
prints the previous and the current quarter.

COVERAGE: "Total da Dívida" = Dívida Externa + Dívida Interna as the bulletin
defines them; the bulletin does not state a wider perimeter (no SOE or
guaranteed-debt line), so coverage is recorded as stated by MEF.

TABLES READ (Portuguese number format "8.918,02"):

* Tabela 1  stock of external, domestic and total debt, each quarter in USD
            million AND MZN million; the current quarter's "% PIB" (measure
            share_of_gdp). "% Total" and "Var. %" are not collected.
* Tabela 2  external debt by creditor (USD million): the three groups
            (Credores Multilaterais, Credores Bilaterais, Título Externo) and
            every named creditor under them, labelled "<group>: <creditor>".
            Each group must equal the sum of its creditors and the TOTAL must
            equal Tabela 1's external debt.
* Tabela 6  domestic debt by instrument (MZN million): Obrigações do Tesouro
            (with its three sub-lines), Bilhetes do Tesouro, Outros
            Instrumentos; OT + BT + Outros must equal Tabela 1's domestic debt.

BACK ISSUES (added 2026-10-12): Tabela 1 only, from the 2023 I T - 2024 I T
issues -- see `parse`. 2024 II T - 2025 I T are not on MEF's site (404).

NOT COLLECTED: Tabela 3 (currency shares, %), Tabelas 4-5 (disbursement and
debt-service FLOWS).

CROSS-CHECK (II T 2026): total USD 17.386,32 m / MZN 1.110.985,56 m (73,6% of
GDP); external USD 8.851,00 m; multilateral 4.618,85; IDA 3.118,26; MOZAM 2032
897,07; domestic MZN 545.406,67 m; OT 201.094,36.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_N = r"\d{1,3}(?:\.\d{3})*,\d+"
_Q = re.compile(r"(20\d\d)\s+(I{1,3}|IV)\s*T\b")
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}
_GROUPS = ("Credores Multilaterais", "Credores Bilaterais", "Título Externo")
_SERIES = "MEF Boletim da Dívida Pública"


def _f(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _region(text: str, caption: str) -> list[str]:
    # Captions are matched WITH their unit suffix: the table of contents
    # repeats each caption without it.
    m = re.search(caption, text)
    if not m:
        raise ValueError(f"Mozambique MEF: '{caption}' not found")
    body = text[m.end():]
    return body[:body.find("Fonte")].splitlines()


_KEY = ["component", "period", "frequency", "measure", "unit", "series_code"]
_T1_LEGACY = re.compile(r"Tabela 1: Stock da Dívida Pública \( ?em milhões de meticais\)"
                        r"|Tabela 1: Stock da Dívida Pública 20\d\d I+V?T/20\d\d I+V?T"
                        r" \(milhões de meticais\)")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """The current issue in full, plus Tabela 1 from each BACK ISSUE.

    Back issues (2023 I T - 2024 I T) print Tabela 1 as a text table in an
    older layout -- caption "(em milhões de meticais)", no "% PIB" column --
    and are read by `_tabela1_legacy`. Issues from 2025 print Tabela 1 as an
    IMAGE (the caption is followed by nothing), and 2022 issues use a
    three-column layout with English number format and USD in parentheses;
    neither is read. Overlapping quarters: the newest issue wins (2023 II T
    total was 15.067,03 in the 2023 II T issue, 15.030,94 in the III T one).
    """
    frames = [_parse_current(path)]
    for p in extras or []:
        frames.append(pd.DataFrame(_tabela1_legacy(p)))
    frames = [f.assign(_end=f["period"].max()) for f in frames if len(f)]
    df = pd.concat(frames, ignore_index=True).sort_values("_end", kind="stable")
    return df.drop_duplicates(_KEY, keep="last").drop(columns="_end")


def _tabela1_legacy(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    hits = [m for m in _T1_LEGACY.finditer(text)
            if "...." not in text[m.end():m.end() + 40]]
    if not hits:
        print(f"[mozambique] {path.rsplit('/', 1)[-1]}: no legacy text Tabela 1 -- not read")
        return []
    body = text[hits[-1].end():]
    body = body[:body.find("Fonte")].splitlines()
    qs = [f"{y}-Q{_ROMAN[r]}" for y, r in _Q.findall(" ".join(body[:4]))]
    if len(qs) != 2:
        raise ValueError(f"Mozambique legacy Tabela 1: quarters {qs}")
    vals = {}
    for ln in body:
        # "6 52.541,88": a stray space inside a number -- rejoined, and the
        # identities below prove the reading.
        ln = re.sub(r"(?<=\s\d) (?=\d{1,2}\.\d{3},)", "", " " + ln.strip()).strip()
        m = re.match(rf"^(Dívida Externa|Dívida Interna|Total da Dívida)\s+({_N})\s+({_N})"
                     rf"\s+({_N})\s+({_N})\s", ln)
        if m:
            vals[m.group(1)] = [_f(m.group(i)) for i in range(2, 6)]
    if set(vals) != {"Dívida Externa", "Dívida Interna", "Total da Dívida"}:
        raise ValueError(f"Mozambique legacy Tabela 1: rows {list(vals)}")
    for j in range(4):
        e, d, t = (vals[k][j] for k in ("Dívida Externa", "Dívida Interna", "Total da Dívida"))
        if abs(e + d - t) > 0.1:
            raise ValueError(f"Mozambique legacy Tabela 1: external + domestic != total ({e}+{d} vs {t})")
    rows = []
    for lab, (u1, z1, u2, z2) in vals.items():
        for q, u, z in ((qs[0], u1, z1), (qs[1], u2, z2)):
            for v, unit in ((u, "USD million"), (z, "MZN million")):
                rows.append({"component": lab, "period": q, "frequency": "quarterly",
                             "measure": "stock", "value": v, "unit": unit,
                             "series_code": f"{_SERIES}, Tabela 1"})
    return rows


def _parse_current(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    rows = []

    def add(comp, period, measure, value, unit, code):
        rows.append({"component": comp, "period": period, "frequency": "quarterly",
                     "measure": measure, "value": value, "unit": unit,
                     "series_code": f"{_SERIES}, {code}"})

    # --- Tabela 1 ---------------------------------------------------------
    t1 = _region(text, r"Tabela 1: Stock da Dívida Pública \(milhões\)")
    qs = [f"{y}-Q{_ROMAN[r]}" for y, r in _Q.findall(" ".join(t1[:4]))]
    if len(qs) != 2:
        raise ValueError(f"Mozambique Tabela 1: quarters {qs}")
    t1v = {}
    for ln in t1:
        m = re.match(rf"^(Dívida Externa|Dívida Interna|Total da Dívida)\s+({_N})\s+({_N})"
                     rf"\s+({_N})\s+({_N})\s+\S+%\s+\S+%\s+(\d+,\d+)%$", ln.strip())
        if not m:
            continue
        lab = m.group(1)
        u1, z1, u2, z2 = (_f(m.group(i)) for i in range(2, 6))
        t1v[lab] = (u2, z2)
        for q, u, z in ((qs[0], u1, z1), (qs[1], u2, z2)):
            add(lab, q, "stock", u, "USD million", "Tabela 1")
            add(lab, q, "stock", z, "MZN million", "Tabela 1")
        add(lab, qs[1], "share_of_gdp", _f(m.group(6)), "percent", "Tabela 1")
    if set(t1v) != {"Dívida Externa", "Dívida Interna", "Total da Dívida"}:
        raise ValueError(f"Mozambique Tabela 1: rows {list(t1v)}")

    # --- Tabela 2 ---------------------------------------------------------
    t2 = _region(text, r"Tabela 2: Composição do Stock da Dívida Pública Externa por Credor \(USD milhões\)")
    group, sums, totals, total = None, {}, {}, None
    for ln in t2:
        m = re.match(rf"^(.+?)\s+({_N})\s+({_N})\s+-?\d+,\d+%\s+-?\d+,\d+%$", ln.strip())
        if not m:
            continue
        lab, a, b = m.group(1).strip(), _f(m.group(2)), _f(m.group(3))
        if lab == "TOTAL":
            total = (a, b)
            continue
        if lab in _GROUPS:
            group = lab
            totals[group] = (a, b)
            sums[group] = [0.0, 0.0]
            comp = lab
        else:
            if group is None:
                raise ValueError(f"Mozambique Tabela 2: creditor {lab!r} outside a group")
            sums[group][0] += a
            sums[group][1] += b
            comp = f"{group}: {lab}"
        add(comp, qs[0], "stock", a, "USD million", "Tabela 2")
        add(comp, qs[1], "stock", b, "USD million", "Tabela 2")
    if set(totals) != set(_GROUPS) or total is None:
        raise ValueError(f"Mozambique Tabela 2: groups {list(totals)}")
    for g in _GROUPS:
        if any(abs(sums[g][i] - totals[g][i]) > 0.05 for i in (0, 1)):
            raise ValueError(f"Mozambique Tabela 2: {g} creditors do not sum")
    if abs(total[1] - t1v["Dívida Externa"][0]) > 0.05:
        raise ValueError("Mozambique Tabela 2: TOTAL differs from Tabela 1")

    # --- Tabela 6 ---------------------------------------------------------
    t6 = _region(text, r"Tabela 6: Stock da Dívida Pública Interna por Instrumento \(MZN milhões\)")
    top, parent = {}, None
    for ln in t6:
        m = re.match(rf"^(.+?)\s+({_N})\s+({_N})\s+\d+%\s+-?\d+%$", ln.strip())
        if not m:
            continue
        lab, a, b = m.group(1).strip(), _f(m.group(2)), _f(m.group(3))
        if lab.upper().startswith("TOTAL"):
            # The table's own total repeats Tabela 1's domestic debt: checked,
            # not emitted twice.
            if abs(b - t1v["Dívida Interna"][1]) > 0.05:
                raise ValueError("Mozambique Tabela 6: TOTAL differs from Tabela 1")
            continue
        if lab in ("Obrigações do Tesouro", "Bilhetes do Tesouro", "Outros Instrumentos"):
            parent = lab
            top[lab] = b
            comp = lab
        else:
            if parent is None:
                raise ValueError(f"Mozambique Tabela 6: sub-line {lab!r} before any instrument")
            comp = f"{parent}: {lab}"
        add(comp, qs[0], "stock", a, "MZN million", "Tabela 6")
        add(comp, qs[1], "stock", b, "MZN million", "Tabela 6")
    if len(top) != 3 or abs(sum(top.values()) - t1v["Dívida Interna"][1]) > 0.05:
        raise ValueError(f"Mozambique Tabela 6: instruments {top} vs Tabela 1")
    return pd.DataFrame(rows)
