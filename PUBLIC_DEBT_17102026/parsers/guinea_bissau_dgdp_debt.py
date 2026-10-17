"""Guinea-Bissau — Boletim Estatístico da Dívida Pública, Direção Geral da
Dívida Pública (MF-DGDP), Ministério das Finanças, on mef.gw (Joomla Edocman;
files at /index.php?option=com_edocman&task=document.download&id=<id>).

COVERAGE. The bulletin works with two perimeters and says so ("Nota sobre o
perímetro da dívida"): the debt of the GOVERNO CENTRAL ORÇAMENTAL (central
budgetary government), on which the debt/GDP ratio is computed, and a
consolidated figure adding the debt of EAGB (the public utility). Only the
first is read here: Quadro 9 "Stock da Dívida da Administração Central e
Orçamental", whose text layer is clean in every issue. Quadro 1 (with
"Empresas Publicas") renders as scattered glyphs in the 2026 issue and is
not read.

WHAT IS READ: Quadro 9's three STOCK rows -- "Divida Publica Total", "Divida
Interna", "Divida Externa" -- in milhões XOF and USD, for the two dates each
issue prints ("Stock em 31/12/2024 | Stock em 31/12/2025"; "Stock em
31/12/2025 | Stock I Semestre 2026"). Year-ends are annual periods; the
first-semester figure is dated 2026-Q2 (end-June). Flows (desembolsos,
serviço, amortização, juros) are not read. Values are split at each ",dd"
decimal (the text layer drops spaces inconsistently). Checked every period:
total = interna + externa (to 0,05), in both currencies.

PUBLISHED CAVEATS, KEPT:
  * the 2025 annual issue footnotes that its 31/12/2025 figures "correspondem
    aos montantes apurados no final do primeiro semestre" (no year-end data);
  * the two issues print 31/12/2025 differently (total 1 118 454,51 in the
    annual issue, 1 118 614,51 in the I-Semestre 2026 issue). The NEWEST issue
    wins under merge-on-write; the difference is recorded here.

CROSS-CHECK: I semestre 2026 total 1 202 431,77 XOF m (2 088,64 USD m) =
interna 744 040,24 + externa 458 391,52; 31/12/2024 total 1 096 408,53.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_VAL = re.compile(r"\d[\d ]*?,\d{2}")
_ROWS = {"Divida Publica Total": "Dívida pública total (Governo Central Orçamental)",
         "Divida Interna": "Dívida interna (Governo Central Orçamental)",
         "Divida Externa": "Dívida externa (Governo Central Orçamental)"}


def _num(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def _period(label: str) -> tuple[str, str]:
    m = re.fullmatch(r"31/12/(20\d\d)", label)
    if m:
        return m.group(1), "annual"
    m = re.fullmatch(r"I Semestre (20\d\d)", label)
    if m:
        return f"{m.group(1)}-Q2", "quarterly"
    # "II Semestre 2024" (the I-semester 2025 issue's comparison column) is
    # the stock at end-December 2024 -- the same date as "31/12/2024".
    m = re.fullmatch(r"II Semestre (20\d\d)", label)
    if m:
        return m.group(1), "annual"
    raise ValueError(f"MF-DGDP GW: unknown period {label!r}")


def _quadro9(path: str):
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            # Quadro 9 in the 2026 issues, Quadro 10 in the I-semester 2025
            # issue -- same table, same rows.
            m = re.search(r"Quadro \d+: Stock da Dívida da Administração Central", t)
            if not m:
                continue
            body = t[m.end():]
            hdr = re.search(r"Stock (?:em )?(31/12/20\d\d|I{1,2} Semestre 20\d\d) "
                            r"Stock (?:em )?(31/12/20\d\d|I{1,2} Semestre 20\d\d)", body)
            if not hdr:
                raise ValueError(f"MF-DGDP GW {path}: Quadro 9 header not found")
            periods = [_period(hdr.group(1)), _period(hdr.group(2))]
            got = {}
            for ln in body.splitlines():
                for lab in _ROWS:
                    # First occurrence only: "Divida Interna/Externa" recur
                    # under the flow blocks below.
                    if ln.startswith(lab + " ") and lab not in got:
                        vals = [_num(v) for v in _VAL.findall(ln[len(lab):])]
                        if len(vals) != 4:
                            raise ValueError(f"MF-DGDP GW Q9 {lab}: {vals}")
                        got[lab] = vals
            if set(got) != set(_ROWS):
                raise ValueError(f"MF-DGDP GW {path}: Q9 rows {sorted(got)}")
            return periods, got
    raise ValueError(f"MF-DGDP GW {path}: Quadro 9 not found")



# ---------------------------------------------------------------------------
# BACK ISSUES 2022-2023 (`_legacy`): the same three stock rows, same perimeter,
# in older layouts.
#   * 2023 issues (I semestre; annual): "QUADRO 11/8: Stock da Dívida da
#     Administração Central e Orçamental", read like Quadro 9 but with the
#     column header "I Semestre 2023 [II Semestre 2023]" on its own line; the
#     annual issue prints English figures ("987,721.02"; "1 ,670.75").
#   * 2022 issues: "Figura 1: Stock da Dívida Pública", described as "(externa
#     e interna)": total = interna + externa exactly (no EAGB, no guarantees),
#     i.e. Quadro 9's perimeter. pdfplumber scatters it; PyMuPDF reads it. It
#     prints no column labels; they are taken from the issue's own sentence
#     ("durante o primeiro e segundo semestre do ano 2021 e o final do
#     primeiro semestre do ano 2022"; "durante o ano 2021, o primeiro e o II
#     Semestre de 2022") and must match the column count.
# QUADRO 1 is never read: its total includes EAGB and guarantees.
# Not readable (glyph-scattered; no OCR): the 2014-2018 and 2019-2021
# bulletins and the central-government quadro of the 2024 issues.

_EN = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}")


def _cells(s: str) -> list[float]:
    if re.search(r"\d\.\d{2}\b", s):                 # English figures
        return [float(v.replace(",", "")) for v in _EN.findall(s.replace(" ", ""))]
    return [_num(v) for v in _VAL.findall(s)]


def _legacy(path: str):
    import fitz
    with fitz.open(path) as doc:
        quick = [" ".join(p.get_text().split()) for p in doc]
    # 2023: the central-government quadro
    for k, t in enumerate(quick):
        if (re.search(r"(?i)QUADRO \d+: Stock da D[íi]vida da Administra[çc][ãa]o Central", t)
                and "....." not in t):
            with pdfplumber.open(path) as pdf:
                body = pdf.pages[k].extract_text() or ""
            hdr = re.search(r"(?m)^((?:I{1,2} Semestre 20\d\d\s*)+)$", body)
            if not hdr:
                break
            labels = re.findall(r"I{1,2} Semestre 20\d\d", hdr.group(1))
            got = {}
            for ln in body[hdr.end():].splitlines():
                # "Dívida Pública Total" in one issue, "Divida Publica Total"
                # in the next: compare without accents (same length).
                plain = ln.replace("í", "i").replace("ú", "u")
                for lab in _ROWS:
                    if lab not in got and plain.startswith(lab + " "):
                        got[lab] = _cells(ln[len(lab):])
            return labels, got
    # 2022: Figura 1
    for t in quick:
        if not re.search(r"Figura 1: Stock da D[íi]vida P[úu]blica", t):
            continue
        r = re.search(r"Divida Publica Total (.+?) Divida Interna (.+?) Divida Externa (.+?) "
                      r"Total de Desembolsos", t)
        s1 = re.search(r"durante o primeiro e segundo semestre do ano (20\d\d) e o final "
                       r"do primeiro semestre do ano (20\d\d)", t)
        s2 = re.search(r"durante o ano (20\d\d), o primeiro e o II Semestre de (20\d\d)", t)
        if not r or not (s1 or s2):
            break
        labels = ([f"I Semestre {s1.group(1)}", f"II Semestre {s1.group(1)}",
                   f"I Semestre {s1.group(2)}"] if s1 else
                  [f"31/12/{s2.group(1)}", f"I Semestre {s2.group(2)}",
                   f"II Semestre {s2.group(2)}"])
        return labels, dict(zip(_ROWS, (_cells(g) for g in r.groups())))
    raise ValueError(f"MF-DGDP GW {path}: no readable stock table (legacy)")


def _legacy_checked(path: str):
    labels, got = _legacy(path)
    n = 2 * len(labels)
    if not labels or set(got) != set(_ROWS) or any(len(v) != n for v in got.values()):
        raise ValueError(f"MF-DGDP GW {path}: legacy table {labels} {got}")
    return [_period(x) for x in labels], got

def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    out = {}
    # Oldest issue first, so the newest issue wins where dates overlap.
    for p in list(reversed(extras or [])) + [path]:
        # A BACK ISSUE without a readable stock Quadro (the 2019-2024
        # bulletins print other tables) is skipped with a message; the
        # primary must parse.
        try:
            try:
                periods, got = _quadro9(p)
            except ValueError:
                if p == path:
                    raise
                periods, got = _legacy_checked(p)
        except ValueError as e:
            if p == path:
                raise
            print(f"  [guinea_bissau] back issue skipped ({p.replace(chr(92), '/').rsplit('/', 1)[-1]}): {e}")
            continue
        for j, (per, freq) in enumerate(periods):
            for k, unit in ((0, "XOF million"), (1, "USD million")):
                i = 2 * j + k
                s = got["Divida Interna"][i] + got["Divida Externa"][i]
                if abs(s - got["Divida Publica Total"][i]) > 0.05:
                    raise ValueError(f"MF-DGDP GW {p} {per} {unit}: total "
                                     f"{got['Divida Publica Total'][i]} != {s:.2f}")
                for lab, comp in _ROWS.items():
                    out[(comp, per, freq, unit)] = got[lab][i]
    return pd.DataFrame([{"component": c, "period": per, "frequency": f,
                          "measure": "stock", "value": v, "unit": u,
                          "series_code": "MF-DGDP Q9"}
                         for (c, per, f, u), v in out.items()])
