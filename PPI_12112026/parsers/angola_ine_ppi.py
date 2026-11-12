"""Angola -- INE Índice de Preços no Produtor (IPP), Folha de Informação Rápida.

One parser for every issue on INE's publication list (35 issues, 2020-Q4 to
September 2026), three layouts:

  quarterly issues (I-IV Trimestre 2021-2024, base 2015=100, CAE Rev.2 2010):
      Quadro 3 -- index for the same quarter a year earlier, the previous quarter
      and the quarter ("2021_T4 2022_T3 2022_T4"), then "Homóloga" (y/y) and
      "Trimestral" (q/q) for the quarter;
  annual issues ("IPP 2020", the 2022/2023/2024 annual editions -- listed by INE
      under "Maio 2023" (twice) and "Junho 2024"):
      Quadro 3 -- yearly indices and "Variação % em relação ao período anterior"
      (annual-average change); the 2020 edition prints 2019_T4, 2019, 2020_T1..T4,
      2020, and Quadros 4/5 the 2020 quarters' y/y (+ the year's average change)
      and q/q;
  monthly issues (from Maio 2025, base 2019=100, CAE 2019): Quadro 3 index, Quadro
      4 m/m %, Quadro 5 y/y % for a 13-month window. Quadro 6 repeats Quadro 4.

Rows are read by their CAE code (BCDE, B, 061_062, 08991/8991, ... 36_37) and the
goods categories by theirs (A1-A4); each row gets INE's own designation for that
code (the PDF wraps the label around the code, so the label is not read from the
line). A row prints its weight first when the table has a weight column.
Contribution tables (p.p.) are not collected.

Header check: the September 2026 issue's Quadro 3 prints "Jan-25" between Dez-25
and Fev-26 while Quadros 4-5 of the same issue print "Jan-26" for the same
window; a single label that breaks an otherwise consecutive month sequence is
taken as the sequence's month and the fix is recorded in parse.notes.

CROSS-CHECK (verbatim): Set-26 total index 283,37, m/m 28,70, y/y 57,07; Set-25
180,41 (both the Sep 2025 and Sep 2026 issues); 2022_T4 total 307,7, y/y -9,7,
q/q -12,9; annual 2023 total 290,8, change -17,6.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

NAME = "Índice de Preços no Produtor (IPP)"
DESIG = {
    "BCDE": "INDÚSTRIA TOTAL", "B": "Indústria Extractiva",
    "061_062": "Extracção de Petróleo e Gás Natural", "8991": "Extracção de Diamantes",
    "081_091": "Resto das Indústrias Extractivas", "C": "Indústria Transformadora",
    "10_12": "Indústrias alimentares, das bebidas e do Tabaco", "101_108": "Indústrias Alimentares",
    "11_12": "Indústrias das bebidas e do Tabaco", "13_15": "Fabricação de têxteis, Vestuários e Calçados",
    "16": "Indústrias de Madeira", "17_18": "Fabricação de Pastas de Papel, Edição e Impressão",
    "19_23": "Fabricação de Produtos Petrolíferos, Químicos e Outros", "24_25": "Indústrias Metalúrgicas",
    "26_30": "Fabricação de Máquinas, Equipamentos, Aparelhos e Automóveis",
    "31_33": "Fabricação de Mobiliário, Colchões e Outras",
    "D": "Produção e Distribuição de Electricidade, Gás e Vapor",
    "35": "Produção e Distribuição de Electricidade",
    "E": "Captação, Tratamento e Distribuição de Água e Saneamento",
    "36_37": "Captação, Tratamento e Distribuição de Água",
    "A1": "Bens Intermédios (A1)", "A2": "Bens de Investimentos (A2)",
    "A3": "Bens de Consumo (A3)", "A4": "Produtos de Energia (A4)"}
_CODE = r"(BCDE|[BCDE]|0?\d{2,4}(?:_\d{2,3})?)"
_NUM = r"-?\d+,\d+"
_ROW = re.compile(rf"^(?P<pre>.*?)\s*{_CODE}\s+(?P<nums>(?:{_NUM}\s*)+)$")
_GOODS = re.compile(rf"^.*?\((A[1-4])\)\s+(?P<nums>(?:{_NUM}\s*)+)$")
_MON = {m: i for i, m in enumerate(["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago",
                                     "set", "out", "nov", "dez"], 1)}


def _tokens(line: str):
    """Period / change-column tokens of a header line, else None. "CAE 2019"
    names the classification, not a column."""
    line = re.sub(r"CAE\s*(?:Rev\.?\s*\d\s*)?\d{4}", " ", line)
    t = re.findall(r"[A-Za-zçÇ]{3}\s?-\s?\d{2}|\d{4}_T[1-4]|(?<![\d,])(?:19|20)\d{2}(?![\d,_])|Homóloga|Trimestral", line)
    # "CAE" on the line above leaves its year ("2019") leading a month/quarter
    # header: it names the classification, not a column.
    if len(t) > 2 and re.fullmatch(r"(?:19|20)\d{2}", t[0]) and not re.fullmatch(r"(?:19|20)\d{2}", t[1]):
        t = t[1:]
    return t if len(t) >= 2 else None


def _period(tok: str):
    m = re.fullmatch(r"([A-Za-zçÇ]{3})\s?-\s?(\d{2})", tok)
    if m and m.group(1).lower() in _MON:
        return "monthly", f"20{m.group(2)}-{_MON[m.group(1).lower()]:02d}"
    m = re.fullmatch(r"(\d{4})_T([1-4])", tok)
    if m:
        return "quarterly", f"{m.group(1)}-Q{m.group(2)}"
    if re.fullmatch(r"(19|20)\d{2}", tok):
        return "annual", tok
    return None


def _fix_months(cols, notes, where):
    """One label breaking a consecutive monthly run (Jan-25 between Dez-25 and Fev-26)."""
    ks = [int(p[:4]) * 12 + int(p[5:]) - 1 if f == "monthly" else None for f, p in cols]
    if None in ks or len(ks) < 5:
        return cols
    exp = [ks[0] + i for i in range(len(ks))]
    bad = [i for i, (a, b) in enumerate(zip(ks, exp)) if a != b]
    if len(bad) == 1 and 0 < bad[0] < len(ks) - 1:
        i = bad[0]
        k = exp[i]
        new = ("monthly", f"{k // 12}-{k % 12 + 1:02d}")
        msg = f"{where}: header {cols[i][1]} read as {new[1]} (out of sequence)"
        if msg not in notes:
            notes.append(msg)
        cols = cols[:i] + [new] + cols[i + 1:]
    elif bad:
        raise ValueError(f"{where}: month header not consecutive: {[c[1] for c in cols]}")
    return cols


def _blocks(text: str):
    """(title, lines) per Quadro."""
    parts = re.split(r"\n(?=Quadro\s*\d+\s*[-–])", "\n" + text)
    for p in parts:
        lines = [l.strip() for l in p.strip().splitlines()]
        if lines and re.match(r"Quadro\s*\d+", lines[0]):
            yield lines[0], lines[1:]


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        pages = [pg.extract_text() or "" for pg in pdf.pages]
    text = "\n".join(pages[3:])          # skip cover, credits, contents
    out, notes = [], []
    for title, lines in _blocks(text):
        tl = title.lower().replace(" ", "")
        if "contribui" in tl or "secções" in tl or "secçoes" in tl or "tipodebens" in tl \
                or "tipodeindústria" in tl or "categoriadebens" in tl or "tipodeindustria" in tl:
            continue
        mb = re.search(r"\((\d{4})=100\)", title)
        if "índicedepreços" in tl or "indicedepre" in tl:
            kind, base = "index", f"{mb.group(1)}=100" if mb else ""
        elif "mensal" in tl:
            kind, base = "inflation_mom", ""
        elif "homóloga" in tl or "homologa" in tl:
            kind, base = "inflation_yoy", ""
        elif "trimestral" in tl:
            kind, base = "inflation_qoq", ""
        elif "taxadevaria" in tl:
            kind, base = "rate_2020", ""
        else:
            continue
        if kind == "index" and not base:
            raise ValueError(f"{path}: {title}: no base")
        cols = None
        for line in lines:
            if cols is None:
                toks = _tokens(line)
                if toks and not _ROW.match(line):
                    cols = toks
                continue
            m = _ROW.match(line) or _GOODS.match(line)
            if not m:
                continue
            code = m.group(2) if m.re is _ROW else m.group(1)
            key = code.lstrip("0") if re.fullmatch(r"0\d{3,4}", code) else code
            if key not in DESIG:
                continue
            nums = [float(x.replace(",", ".")) for x in m.group("nums").split()]
            ncol = len(cols)
            if len(nums) == ncol + 1:
                weight, nums = nums[0], nums[1:]
            elif len(nums) == ncol:
                weight = None
            else:
                continue                    # a wrapped or partial row: not guessed
            # Column meaning.
            pers = [_period(t) for t in cols]
            if kind == "index":
                idx_cols = [(i, p) for i, p in enumerate(pers) if p]
                n_idx = len(idx_cols)
                # annual edition: "2019..2023 2019..2023" -> second run is the change
                years = [p[1] for _, p in idx_cols]
                half = n_idx // 2
                if n_idx >= 4 and n_idx % 2 == 0 and years[:half] == years[half:]:
                    for (i, p), (j, q) in zip(idx_cols[:half], idx_cols[half:]):
                        if nums[i] == 0:
                            continue
                        out.append(C.row(index_name=NAME, industry=DESIG[key], industry_code_nso=code,
                                         period=p[1], frequency=p[0], measure="index", value=nums[i],
                                         base_period=base))
                        out.append(C.row(index_name=NAME, industry=DESIG[key], industry_code_nso=code,
                                         period=q[1], frequency=q[0], measure="inflation_avg", value=nums[j]))
                else:
                    fixed = _fix_months([p for _, p in idx_cols], notes, f"{path}|{title}") \
                        if all(p[0] == "monthly" for _, p in idx_cols) else [p for _, p in idx_cols]
                    for (i, _), p in zip(idx_cols, fixed):
                        if nums[i] == 0:     # "0,0" = no production in the category, not a price level
                            continue
                        out.append(C.row(index_name=NAME, industry=DESIG[key], industry_code_nso=code,
                                         period=p[1], frequency=p[0], measure="index", value=nums[i],
                                         base_period=base))
                    last = fixed[-1]
                    for i, t in enumerate(cols):
                        if t in ("Homóloga", "Trimestral"):
                            if last[0] != "quarterly":
                                raise ValueError(f"{title}: {t} column after a non-quarter {last}")
                            out.append(C.row(index_name=NAME, industry=DESIG[key], industry_code_nso=code,
                                             period=last[1], frequency="quarterly",
                                             measure="inflation_yoy" if t == "Homóloga" else "inflation_qoq",
                                             value=nums[i]))
                if weight is not None:
                    yr = re.search(r"CAE\s*(\d{4})", " ".join(lines[:6]))
                    out.append(C.row(index_name=NAME, industry=DESIG[key], industry_code_nso=code,
                                     period=base[:4], frequency="annual", measure="weight",
                                     value=weight, base_period=base))
            else:
                for i, p in enumerate(pers):
                    if not p:
                        continue
                    meas = kind
                    if kind == "rate_2020":
                        meas = "inflation_avg" if p[0] == "annual" else "inflation_yoy"
                    if meas in ("inflation_mom",) and p[0] != "monthly":
                        continue
                    out.append(C.row(index_name=NAME, industry=DESIG[key], industry_code_nso=code,
                                     period=p[1], frequency=p[0], measure=meas, value=nums[i]))
    df = pd.DataFrame(out)
    if df.empty:
        raise ValueError(f"no IPP rows in {path}")
    # Quadro 4 and 6 repeat each other; any cell printed twice must agree.
    k = ["industry_code_nso", "period", "frequency", "measure"]
    g = df.groupby(k).value
    if (g.max() - g.min()).abs().gt(0.001).any():
        bad = (g.max() - g.min())[lambda s: s.abs() > 0.001]
        raise ValueError(f"{path}: a cell printed twice with different values: {bad.head(3).to_dict()}")
    parse.notes = notes
    return df.drop_duplicates(k).reset_index(drop=True)


def parse_issues(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """Every issue: the descriptor lists `extra_urls` oldest first and the
    latest issue as its primary file; a cell printed by several issues (each
    monthly issue reprints 13 months) takes the NEWEST issue's value."""
    frames, notes = [], []
    for p in list(extras or []) + [path]:
        frames.append(parse(p).assign(_order=len(frames)))
        notes += parse.notes
    df = pd.concat(frames, ignore_index=True)
    df = (df.sort_values("_order", kind="stable")
            .drop_duplicates(["industry_code_nso", "period", "frequency", "measure", "base_period"], keep="last"))
    parse_issues.notes = notes
    return df.drop(columns="_order").reset_index(drop=True)


# A % change carries the base of its index (set from this output; see _base_carry).
from ._base_carry import carry_base  # noqa: E402
parse_issues = carry_base(parse_issues)
