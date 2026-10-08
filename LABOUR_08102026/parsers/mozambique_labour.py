"""Mozambique — INE Moçambique, IOF 2022 (Inquérito sobre Orçamento Familiar),
Relatório Final, chapter 6 "Emprego".

A HOUSEHOLD budget survey, not a labour force survey: the IOF visits each
household for seven days, spread over twelve months of collection (weights set
to the population at 1 July 2022, mid-collection), and its employment chapter
covers the population aged 15 and over. INE has no recent LFS; the Anuário's
labour tables are registered unemployed and INEFP placements (administrative,
the Kenya trap), so the IOF is the household source.

Two distributions of the EMPLOYED aged 15+:

* Quadro 6.5  ramos de actividade económica (10 groups incl. Desconhecido)
              -> industry
* Quadro 6.6  posição no processo laboral (11 categories) -> employment_status

Each ROW is a population group -- Total, Sexo, Área de residência, Província
(Maputo is the PROVINCE, "Cidade de Maputo" the city), Nível de educação --
and its values are that group's distribution across the categories, summing to
100 (like Mali's EMOP workbooks). The group rides in sex / locality /
geography / education. The trailing "N" (the group's employed count, space
thousands) is NOT collected: levels belong to `unemployment`.

THE COLUMN HEADERS ARE ROTATED 90 DEGREES, and the text layer returns each one
REVERSED and interleaved ("arutlucirgA", "acsep e arutlucivlis"), so reading
order cannot name a column. The mapping is established from PAGE GEOMETRY on
every run: the rotated glyphs are clustered into lines by x-centre, each line
reversed to reading order, and each line assigned to the value column whose
x-centre is nearest (a header may take two lines -- "Agricultura," /
"silvicultura e pesca"; "Serviços administra-" / "tivos"). The names so read
must equal the published list below, in order, or the parse raises. Confirmed
by the report's own prose: agriculture 74,7 (~75%), rural 89,2, urban commerce
and finance 21,0; conta própria sem empregados 72,0, trabalhador familiar sem
remuneração 12,6, empresa privada 7,0, nível superior in administração pública
64,1.

POSIÇÃO NO PROCESSO LABORAL IS A HYBRID -- it crosses status (conta própria
com / sem empregados, trabalhador familiar) with the employer's institutional
sector for employees (administração pública, autarquias, empresa pública /
privada, cooperativa, ONG, casa particular, organismos internacionais). The
eleven partition the employed, so it is filed as `employment_status`,
National.

CLASSIFICATION: the methodology says ramos were CODED with CAE Rev.2 (INE's
national classification of economic activities) and occupations with CPM
Rev.2, but the table prints ten AGGREGATED groups under no scheme name ("nove
ramos" in the prose, plus Desconhecido) -> National.

A PUBLISHED INCONSISTENCY, NOT COLLECTED BUT RECORDED: the two tables disagree
on the size of two education groups -- Desconhecido N 81 369 in 6.5 against
37 138 in 6.6, "Nunca frequentou escola" 2 854 968 against 2 899 198 (their
sums agree, 2 936 337) -- and men 5 388 335 against 5 388 334. The Ns are not
collected; the shares of those two groups should be read with that in mind.

PERIOD 2022 (twelve months of collection, weights at 1 July 2022).

CROSS-CHECK (Total): agricultura, silvicultura e pesca 74,7; comércio e
finanças 8,5; outros serviços 8,6; conta própria sem empregados 72,0;
Cidade de Maputo empresa privada 33,1; Mulher agricultura 82,6.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = "Inquérito sobre Orçamento Familiar (IOF 2022)"
_T65 = ["Agricultura, silvicultura e pesca", "Extração de minas",
        "Indústria manufatureira", "Energia", "Construção",
        "Transporte e comunicações", "Comércio e finanças",
        "Serviços administrativos", "Outros serviços", "Desconhecido"]
_T66 = ["Administração Pública", "Autarquias locais", "Empresa pública",
        "Organismos Internacionais/Embaixada", "Empresa Privada",
        "Cooperativa", "ONG/Associações sem fins lucrativos",
        "Casa particular", "Conta própria com empregados",
        "Conta própria sem empregados",
        "Trabalhador familiar sem remuneração"]
_TABLES = [
    (r"Quadro 6\.5 - Distribui..o percentual da popula..o de 15 anos",
     "industry", _T65, "IOF2022 Q6.5"),
    (r"QUADRO 6\.6 - Distribui..o percentual da popula..o de 15 anos",
     "employment_status", _T66, "IOF2022 Q6.6"),
]
_SECTIONS = {"Sexo": "sex", "Área de residência": "locality",
             "Província": "geography", "Nível de educação": "education"}
_LOCALITY = {"Urbana": "urban", "Rural": "rural"}
_SEXES = {"Homem": "male", "Mulher": "female"}
_DEC = r"\d{1,3},\d"
# Groups per section, as printed: 1 Total + 2 + 2 + 11 + 6.
_EXPECT = {None: 1, "sex": 2, "locality": 2, "geography": 11, "education": 6}


def _headers(page, value_xs: list[float]) -> list[str]:
    """Column names from the rotated header glyphs, assigned by geometry."""
    rot = sorted((c for c in page.chars if not c["upright"]),
                 key=lambda c: (c["x0"] + c["x1"]) / 2)
    lines, cur, last = [], [], None
    for c in rot:
        x = (c["x0"] + c["x1"]) / 2
        if last is not None and x - last > 3:
            lines.append(cur)
            cur = []
        cur.append(c)
        last = x
    if cur:
        lines.append(cur)
    cols: list[list[tuple[float, str]]] = [[] for _ in value_xs]
    for ln in lines:
        x = sum((c["x0"] + c["x1"]) / 2 for c in ln) / len(ln)
        # rotated counter-clockwise: reading order runs bottom to top
        text = "".join(c["text"] for c in sorted(ln, key=lambda c: -c["top"]))
        k = min(range(len(value_xs)), key=lambda i: abs(value_xs[i] - x))
        if abs(value_xs[k] - x) > 15:
            raise ValueError(f"IOF 2022: header line {text!r} at x={x:.0f} "
                             f"is under no value column")
        cols[k].append((x, text))
    names = []
    for parts in cols:
        s = " ".join(t.strip() for _, t in sorted(parts))
        s = re.sub(r"-\s+", "", s)          # "administra- tivos"
        s = re.sub(r"/\s+", "/", s)          # "Internacionais/ Embaixada"
        names.append(re.sub(r"\s+", " ", s).strip())
    return names


def _read(pdf, caption: str, labels: list[str], where: str):
    page = next((p for p in pdf.pages
                 if re.search(caption, p.extract_text() or "")), None)
    if page is None:
        raise ValueError(f"{where}: caption not found")
    k = len(labels)
    row_re = re.compile(rf"^(\D+?)\s+((?:{_DEC}\s+){{{k}}})100,0\s+[\d ]+$")
    # value-column x-centres from the national Total row
    words = page.extract_words()
    total_top = next(w["top"] for w in words
                     if w["text"] == "Total" and any(
                         abs(v["top"] - w["top"]) < 3 and re.fullmatch(_DEC, v["text"])
                         for v in words))
    vals = sorted((w for w in words if abs(w["top"] - total_top) < 3
                   and re.fullmatch(_DEC, w["text"])), key=lambda w: w["x0"])
    xs = [(w["x0"] + w["x1"]) / 2 for w in vals][:k]
    names = _headers(page, xs)
    if names != labels:
        raise ValueError(f"{where}: header geometry reads {names}, the layout "
                         f"states {labels}")

    section, out = None, []
    for ln in (page.extract_text() or "").splitlines():
        ln = ln.strip()
        if ln in _SECTIONS:
            section = _SECTIONS[ln]
            continue
        m = row_re.match(ln)
        if not m:
            continue
        group = m.group(1).strip()
        v = [float(x.replace(",", ".")) for x in m.group(2).split()]
        if abs(sum(v) - 100) > 0.35:
            raise ValueError(f"{where}: {group!r} sums to {sum(v):.1f}")
        if group == "Total":
            section = None
        out.append((section, group, v))
    got = {s: sum(1 for x in out if x[0] == s) for s in _EXPECT}
    if got != _EXPECT:
        raise ValueError(f"{where}: groups per section {got}, printed {_EXPECT}")
    return out


def parse(path: str) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(path) as pdf:
        for caption, topic, labels, code in _TABLES:
            for section, group, vals in _read(pdf, caption, labels, code):
                ctx = {}
                if section == "sex":
                    ctx["sex"] = _SEXES[group]
                elif section == "locality":
                    ctx["locality"] = _LOCALITY[group]
                    ctx["locality_label"] = group
                elif section == "geography":
                    ctx["geography"] = group
                elif section == "education":
                    ctx["education"] = group
                for cat, v in zip(labels, vals):
                    rows.append(C.row(topic=topic, characteristic=cat,
                                      classification="National", value=v,
                                      survey=_SURVEY, period="2022",
                                      reference_period="IOF 2022",
                                      frequency="ad_hoc", measure="share",
                                      unit="percent", working_age_base="15+",
                                      series_code=code, **ctx))
    return pd.DataFrame(rows)
