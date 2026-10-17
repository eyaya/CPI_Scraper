"""Angola — Ministério das Finanças, Unidade de Gestão da Dívida Pública (UGD),
"Boletim Estatístico da Dívida Pública" (quarterly), Visão Geral tables.

PUBLISHER: UGD/MINFIN. The ugd.minfin.gov.ao portal is an Angular app over a
Squidex CMS: the bulletin list is the JSON at
cms.minfin.gov.ao/api/content/portal-ugd/boletins-da-divida-publica and each
file is /api/assets/portal-ugd/<asset id>. Each issue prints a rolling window
of SIX quarters; merge-on-write accumulates history across issues.

COVERAGE: "Dívida Governamental" -- government (central government) debt,
external + domestic. Government-GUARANTEED debt is reported separately in the
bulletin (Tabela 10) and is NOT included here.

TABLES READ (USD and Kz amounts in "mil milhões" = billions, as printed):

* Tabela 1  stock of Dívida Governamental, Externa, Interna -- each quarter in
            USD and in Kz (the flows "Desembolsos/Emissões" and
            "Resgates/Amortizações" printed below are NOT stocks and are not
            collected)
* Tabela 2  stock by original maturity (short / medium-long)
* Tabela 3  stock by currency (national / foreign)
* Tabela 6  "Dívida Governamental, % do PIB" -- the published ratio for the
            year 2025 and the two latest quarters

Tabela 4 (by domicile) repeats Tabela 1's Interna/Externa digit for digit and
is checked equal, not emitted. Tabela 1's Kz figures use SPACE thousands
("55 420,81") right beside the USD figure ("60,77"), so each quarter is read as
a (USD, Kz) pair under the pattern "d,dd  ddd ddd,dd"; every row must yield
exactly six pairs, and Externa + Interna must equal Governamental (to 0.02).

RATIOS ARE REVISED: Gráfico 1's note says the debt/GDP series was revised for
INE's new 2025 nominal GDP, so values differ from earlier issues; the newest
issue wins through merge-on-write.

CROSS-CHECK (II Trim. 26): Dívida Governamental USD 72,04 bn / Kz 65 745,41
bn; Externa 50,91; Interna 21,14; 51,24% of GDP. I Trim. 25: 60,77 / 55 420,81.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_Q = re.compile(r"\b(I{1,3}|IV)\s*Trim\.?\s*(\d{2})\b")
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}
_DEC = r"\d{1,3},\d+"
_PAIR = re.compile(rf"({_DEC})\s+(\d{{1,3}}(?: \d{{3}})*,\d+)")
_SERIES = "UGD Boletim Estatístico da Dívida Pública"


def _f(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def _quarters(line: str) -> list[str]:
    qs = [f"20{y}-Q{_ROMAN[r]}" for r, y in _Q.findall(line.replace("IITrim", "II Trim"))]
    return qs


def _block(text: str, caption: str) -> list[str]:
    i = re.search(caption, text)
    if not i:
        raise ValueError(f"Angola UGD: '{caption}' not found")
    body = text[i.end():]
    return body[:body.find("Fonte")].splitlines()


def _tabela1(text: str):
    lines = _block(text, r"Tabela 1 ?: ?Stock, desembolsos e resgates")
    qs = next(_quarters(l) for l in lines if len(_quarters(l)) == 6)
    out, pending = {}, ""
    for ln in lines:
        s = ln.strip()
        if s.startswith("Desembolsos"):
            break
        pairs = _PAIR.findall(s)
        if len(pairs) == 6:
            label = (re.sub(r"[\d ,]+$", "", s).strip() or pending).strip()
            if label == "Dívida" or not label:
                label = "Dívida Governamental"
            out[label] = pairs
            pending = ""
        elif s and not _DEC_RE.search(s) and "Descrição" not in s and "USD" not in s:
            pending = s
    if set(out) != {"Dívida Governamental", "Dívida Externa", "Dívida Interna"}:
        raise ValueError(f"Angola UGD Tabela 1: rows {list(out)}")
    for i in range(6):
        g, e, d = (_f(out[k][i][0]) for k in ("Dívida Governamental", "Dívida Externa",
                                              "Dívida Interna"))
        if abs(e + d - g) > 0.02:
            raise ValueError(f"Angola UGD Tabela 1 {qs[i]}: {e}+{d} != {g}")
    return qs, out


_DEC_RE = re.compile(_DEC)


def _six(text: str, caption: str, labels: list[str]):
    lines = _block(text, caption)
    qs = next(_quarters(l) for l in lines if len(_quarters(l)) == 6)
    vals = []
    for ln in lines:
        nums = _DEC_RE.findall(ln)
        if len(nums) == 6 and not _quarters(ln):
            vals.append([_f(n) for n in nums])
    if len(vals) != len(labels):
        raise ValueError(f"Angola UGD {caption}: {len(vals)} rows for {labels}")
    total, *parts = vals
    for i in range(6):
        if abs(sum(p[i] for p in parts) - total[i]) > 0.02:
            raise ValueError(f"Angola UGD {caption}: parts do not sum in {qs[i]}")
    return qs, dict(zip(labels, vals))


_KEY = ["component", "period", "frequency", "measure", "unit", "series_code"]


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """The current issue strictly, plus BACK ISSUES leniently.

    Each issue prints a six-quarter window, so one back issue extends the
    series by up to four quarters. A back issue must yield Tabelas 1-4 or it
    is skipped with a message (layouts vary: the I Trim. 2026 issue renames
    Tabela 1, the III Trim. 2025 one heads it differently); its Tabela 6
    ratios are taken only if they parse. Overlapping quarters: the newest
    issue wins (UGD revises; ratios were re-based on INE's new 2025 GDP).
    """
    frames = [pd.DataFrame(_parse_one(path, strict=True))]
    for p in extras or []:
        try:
            if _is_annual(p):
                frames.append(pd.DataFrame(_annual(p)))
                continue
            frames.append(pd.DataFrame(_parse_one(p, strict=False)))
        except (ValueError, StopIteration) as e:
            print(f"[angola] back issue {p.rsplit('/', 1)[-1]} not read: "
                  f"{type(e).__name__} {e}")
    frames = [f.assign(_end=f.loc[f.frequency == "quarterly", "period"].max()
                       if (f.frequency == "quarterly").any() else "")
              for f in frames if len(f)]
    df = pd.concat(frames, ignore_index=True).sort_values("_end", kind="stable")
    return df.drop_duplicates(_KEY, keep="last").drop(columns="_end")


def _parse_one(path: str, strict: bool) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages[:10])
    rows = []

    def add(comp, period, freq, measure, value, unit, code):
        rows.append({"component": comp, "period": period, "frequency": freq,
                     "measure": measure, "value": value, "unit": unit,
                     "series_code": f"{_SERIES}, {code}"})

    qs, t1 = _tabela1(text)
    for label, pairs in t1.items():
        for q, (usd, kz) in zip(qs, pairs):
            add(label, q, "quarterly", "stock", _f(usd), "USD billion", "Tabela 1")
            add(label, q, "quarterly", "stock", _f(kz), "AOA billion", "Tabela 1")

    for cap, labels in (
        (r"Tabela ?2 ?: ?Stock de Dívida Governamental por Maturidade",
         ["Dívida Governamental (por maturidade original)", "Curto Prazo (<= 1 ano)",
          "Médio a Longo Prazo (acima de 1 ano)"]),
        (r"Tabela ?3 ?: ?Stock de Dívida Governamental por Moeda",
         ["Dívida Governamental (por moeda)", "Moeda Nacional", "Moeda Estrangeira"]),
    ):
        q2, t = _six(text, cap, labels)
        for label in labels[1:]:
            for q, v in zip(q2, t[label]):
                add(label, q, "quarterly", "stock", v, "USD billion", cap.split(" ?:")[0].replace(" ?", " "))

    # Tabela 4 (by domicile) must repeat Tabela 1's split.
    q4, t4 = _six(text, r"Tabela ?4 ?: ?Stock de Dívida Governamental por Domicílio",
                  ["total", "Interna", "Externa"])
    for i in range(6):
        if (t4["Interna"][i], t4["Externa"][i]) != (_f(t1["Dívida Interna"][i][0]),
                                                    _f(t1["Dívida Externa"][i][0])):
            raise ValueError(f"Angola UGD: Tabela 4 disagrees with Tabela 1 in {q4[i]}")

    try:
        _tabela6(text, add)
    except (ValueError, StopIteration):
        if strict:
            raise
        print(f"[angola] {path.rsplit('/', 1)[-1]}: Tabela 6 not read (layout differs)")
    return rows


def _tabela6(text: str, add) -> None:
    lines = _block(text, r"Tabela 6 ?: ?Principais rácios")
    # The header wraps: "I Trimestre II Trimestre" / "2025" / "de 2026 de 2026"
    # -- the bare year is the annual column, each "de YYYY" a quarter's year.
    hdr = " ".join(lines[:4])
    yr = re.search(r"(?<!de )\b(20\d\d)\b", hdr)
    m = next((re.findall(r"(\d{1,3},\d+)%", l) for l in lines
              if "%doPIB" in l.replace(" ", "") and "Dívida" in l.replace(" ", "")), None)
    if not m or len(m) != 3:
        raise ValueError("Angola UGD Tabela 6: debt/GDP row not read")
    tri = list(zip(re.findall(r"\b(I{1,3}|IV)\s*Trimestre", hdr),
                   re.findall(r"de\s*(20\d\d)", hdr)))
    if not yr or len(tri) != 2:
        raise ValueError(f"Angola UGD Tabela 6: header {hdr!r}")
    add("Dívida Governamental", yr.group(1), "annual", "share_of_gdp", _f(m[0]),
        "percent", "Tabela 6")
    for (r, y), v in zip(tri, m[1:]):
        add("Dívida Governamental", f"{y}-Q{_ROMAN[r]}", "quarterly", "share_of_gdp",
            _f(v), "percent", "Tabela 6")


# --- ANNUAL BULLETIN (added 2026-10-14) -------------------------------------
# "Boletim Estatístico Anual da Dívida Pública 2024", Tabela 1 "Stock,
# emissões e resgates da Dívida Governamental, em mil milhões": end-year
# stocks of Dívida Governamental / Externa / Interna, USD and Kz, for 2020-2024,
# plus a "2025P (Dados até Março)" column -- a MARCH figure, not a year-end,
# which is NOT read (the quarterly bulletins carry 2025-Q1). Only the stock rows
# (the first occurrence of each label; the flows below repeat the labels) are
# read, as annual rows under series code "UGD Boletim Estatístico Anual,
# Tabela 1". The 2025 annual edition prints its Tabela 1 with labels below
# their figures and a value split from its row, so it is not read.
_ANNUAL_CAP = "Tabela 1 : Stock, emissões e resgates da Dívida Governamental"


_ANNUAL_PAIR = re.compile(r"(\d{1,3},\d+)\s+(\d{1,3}(?: \d{3}(?![,\d]))*(?:,\d+)?)(?![\d,])")


def _is_annual(path: str) -> bool:
    with pdfplumber.open(path) as pdf:
        return any(_ANNUAL_CAP in (p.extract_text() or "") for p in pdf.pages[:10])


def _annual(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        text = next(t for t in (p.extract_text() or "" for p in pdf.pages[:10])
                    if _ANNUAL_CAP in t)
    lines = [ln.strip() for ln in text[text.find(_ANNUAL_CAP):].splitlines()]
    hdr = next(ln for ln in lines if re.fullmatch(r"(?:20\d{2}\s+){2,}20\d{2}", ln))
    years = hdr.split()
    vals = {}
    for lab in ("Dívida Governamental", "Dívida Externa", "Dívida Interna"):
        ln = next((x for x in lines if x.startswith(lab + " ")), None)
        if ln is None:
            raise ValueError(f"Angola UGD annual: row {lab!r} not found")
        # Kz is printed WITHOUT decimals here ("63,62 41 328"): a USD figure
        # with a decimal comma, then space-grouped Kz whose groups are exactly
        # three digits not followed by a comma (that would be the next USD).
        pairs = _ANNUAL_PAIR.findall(ln[len(lab):])
        if len(pairs) < len(years):
            raise ValueError(f"Angola UGD annual {lab!r}: {len(pairs)} pairs")
        vals[lab] = pairs[:len(years)]
    rows = []
    for j, y in enumerate(years):
        for k, unit in ((0, "USD billion"), (1, "AOA billion")):
            g, e, i = (_f(vals[l][j][k]) for l in
                       ("Dívida Governamental", "Dívida Externa", "Dívida Interna"))
            if abs(e + i - g) > (0.02 if k == 0 else 2):
                raise ValueError(f"Angola UGD annual {y}: Externa + Interna != Governamental")
        for lab, pairs in vals.items():
            for v, unit in ((pairs[j][0], "USD billion"), (pairs[j][1], "AOA billion")):
                rows.append({"component": lab, "period": y, "frequency": "annual",
                             "measure": "stock", "value": _f(v), "unit": unit,
                             "series_code": "UGD Boletim Estatístico Anual, Tabela 1"})
    return rows
