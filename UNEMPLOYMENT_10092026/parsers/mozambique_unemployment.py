"""Mozambique — INE, IOF (Inquérito sobre Orçamento Familiar) final reports,
chapter 6 "Emprego": IOF 2022 (primary) and IOF 2019/20 (extra).

THE SAME 2022 REPORT `labour/` READS (its Quadros 6.5/6.6, composition). This
module takes the headline tables of the same chapter, in both rounds:

    Quadro 6.1  PEA / PNEA (% of the 15+) [and N]  -> labour_force_participation_rate
                                                      [, working_age_population]
    Quadro 6.3  taxa de emprego by sex [, N]       -> employment_to_population_ratio
                                                      [, employed]
    Quadro 6.4  taxas específicas de emprego by age x residence x sex
                                                    -> employment_to_population_ratio
    Quadro 6.7  taxa de subemprego by sex          -> underemployment_rate
    Quadro 6.8  taxa de desemprego by sex [, N]    -> unemployment_rate [, unemployed]

each by residence, the eleven provinces and education level. The N columns
exist only in 2022. No dedicated labour force survey report was found in
INE's document library (folders 44454, 331703, 181701 checked); the IOF
employment module is the current source.

NOT THE ILO DEFINITIONS, AND BOTH REPORTS SAY SO. INE dropped the job-search
criterion ("foi dispensado o critério 'procura de emprego'") and adopts a
"definição alternativa" that also counts as UNEMPLOYED the "Desempregado C" --
casual workers, own-account and family workers without regular work, and
unpaid family workers who did not work in the reference week -- and removes
them from the employed. So the unemployment rate (17,5% in 2019/20, 18,4% in
2022) and the PEA share are `broad`, and every series_label says "definição
alternativa"; the employment rate is on the same alternative employed
population. None of these is comparable with an ILO-strict rate.

A PUBLISHED INCONSISTENCY, KEPT (2022): Quadro 6.3's employed (11 389 792)
plus Quadro 6.8's unemployed (2 489 415) is 13 879 207, but Quadro 6.1's PEA is
84,9% of 15 951 545 = 13 542 861 -- 336 346 apart. 6.8's rate reproduces
against 6.1's PEA (18,4%), 6.3's against the 15+ population (71,4%). Both
counts are collected as printed.

A MISPRINTED HEADER (2022): Quadro 6.8 heads its count column "População
subempregada", but it is the UNEMPLOYED (2 489 415, against 6.7's 921 682
underemployed; the 18,4% reproduces from it). Collected as `unemployed`.

2019/20 DIFFERS IN FORM, NOT CONCEPT: no N columns, "Homens / Mulheres",
"Maputo Província / Maputo Cidade" (2022: "Maputo / Cidade de Maputo" -- kept
as printed, so a join across rounds must map them), no "Nunca frequentou
escola" row, a few integer cells ("11" for 11,0), and two misprinted captions
("QUADRO 6,7", "QUADRO 6,8: Taxas de dsemprego") -- matched as printed. Each
report's round is read from its own running head, never from the file name.

NOT TAKEN: PNEA % (the inactivity rate -- no topic), Quadro 6.2 (reasons for
inactivity), the estado civil rows (no column holds marital status), 6.7's
underemployed count (no topic), Gráfico 6.1 (chart), and the 2014/15 figures
quoted only in 2019/20's prose.

Base 15+. Periods 2022 and 2020 (2019/20 dated to its final year, as the
corpus dates multi-year rounds).

CROSS-CHECK: 2022 -- PEA 84,9 (rural 90,0); employment rate 71,4; 15-19
employment rate 43,5; underemployment 8,1; unemployment 18,4 (Cidade de
Maputo 36,5); unemployed 2 489 415. 2019/20 -- PEA 86,6; employment rate
74,0; unemployment 17,5 (Maputo Cidade 37,1); underemployment 12,5.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_ALT = "definição alternativa"
_ROUNDS = {
    "2022": dict(mark=r"IOF\s*[–-]?\s*2022\b", period="2022", ref="IOF 2022",
                 survey="Inquérito sobre Orçamento Familiar (IOF) 2022",
                 counts=True, q61=22, qsex=20),
    "2019/20": dict(mark=r"IOF\s*[–-]?\s*2019/20", period="2020", ref="IOF 2019/20",
                    survey="Inquérito sobre Orçamento Familiar (IOF) 2019/20",
                    counts=False, q61=21, qsex=19),
}
_D = r"\d{1,3}(?:,\d)?"
_N = r"\d{1,3}(?: \d{3})*"
_STOP = (r"^(Relatório Final|Instituto Nacional|O Gráfico|O Quadro|O quadro|"
         r"De acordo|6\.2\.2)")
_SECTIONS = {"sexo": "sex", "área de residência": "locality",
             "província": "geography", "nível de educação": "education",
             "estado civil": "skip"}
_PROVINCES = {"Niassa", "Cabo Delgado", "Nampula", "Zambézia", "Tete", "Manica",
              "Sofala", "Inhambane", "Gaza", "Maputo", "Cidade de Maputo",
              "Maputo Província", "Maputo Cidade"}
_SEX = {"Homem": "male", "Mulher": "female", "Homens": "male", "Mulheres": "female"}


def _f(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def _pages(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [p.extract_text() or "" for p in pdf.pages[45:80]]


def _round(pages: list[str]) -> dict:
    # Each report also quotes the other round in its prose, so a mere mention
    # decides nothing: the round is the one its RUNNING HEAD repeats on every
    # page, which must outnumber any other by far.
    text = " ".join(pages[5:20])
    n = {r: len(re.findall(rf"Orçamento Familiar\s*[–-]\s*{cfg['mark']}", text, re.I))
         for r, cfg in _ROUNDS.items()}
    best = max(n, key=n.get)
    if n[best] < 5 or any(v * 3 > n[best] for r, v in n.items() if r != best):
        raise ValueError(f"IOF: cannot tell the round from the running heads ({n})")
    return _ROUNDS[best]


def _lines(pages: list[str], caption: str, where: str) -> list[str]:
    rx = re.compile(caption, re.I)
    for text in pages:
        m = rx.search(text)
        if m:
            return [ln.strip() for ln in text[m.end():].splitlines()]
    raise ValueError(f"{where}: {caption!r} not found")


def _rows(lines: list[str], pattern: str):
    """(section, label, groups) for every data line until the table ends."""
    rx = re.compile(rf"^(.+?)\s+{pattern}$")
    section = None
    for ln in lines[1:]:
        if re.match(_STOP, ln):
            break
        key = ln.lower()
        if key in _SECTIONS:
            section = _SECTIONS[key]
            continue
        m = rx.match(ln)
        if m and m.group(1).strip() == "Total":
            # The national row: in 6.3/6.7/6.8 it follows the column header
            # "Sexo", which must not be read as opening a section.
            section = None
            yield None, "Total", m.groups()[1:]
        elif m and section != "skip":
            yield section, m.group(1).strip(), m.groups()[1:]


def _dims(section, label, where):
    if section is None:
        if label != "Total":
            raise ValueError(f"{where}: row {label!r} outside any section")
        return {}
    if section == "sex":
        if label not in _SEX:
            raise ValueError(f"{where}: unknown sex row {label!r}")
        return {"sex": _SEX[label]}
    if section == "locality":
        return {"locality": C.normalise_locality(label), "locality_label": label}
    if section == "geography":
        if label not in _PROVINCES:
            raise ValueError(f"{where}: unknown province {label!r}")
        return {"geography": label}
    return {"education": label}


def _base(cfg):
    return dict(survey=cfg["survey"], period=cfg["period"],
                reference_period=cfg["ref"], frequency="ad_hoc",
                working_age_base="15+")


def _q61(pages, cfg):
    code = f"{cfg['ref']} Q6.1"
    tail = rf" ({_N})" if cfg["counts"] else ""
    out, n = [], 0
    for section, lab, g in _rows(
            _lines(pages, r"QUADRO 6[.,]1\s*-\s*Distribui", code),
            rf"({_D}) ({_D}) (100,0){tail}"):
        if abs(_f(g[0]) + _f(g[1]) - 100) > 0.15:
            raise ValueError(f"{code} {lab}: PEA + PNEA != 100")
        d = _dims(section, lab, code)
        out.append(C.row(topic="labour_force_participation_rate", value=_f(g[0]),
                         series_label=f"PEA (% da população de 15+ anos), {_ALT}",
                         definition="broad", series_code=code, **_base(cfg), **d))
        if cfg["counts"]:
            out.append(C.row(topic="working_age_population", value=_f(g[3]),
                             series_label="População de 15 anos ou mais (N)",
                             series_code=code, **_base(cfg), **d))
        n += 1
    if n != cfg["q61"]:
        raise ValueError(f"{code}: {n} rows, expected {cfg['q61']}")
    return out


def _by_sex(pages, cfg, caption, num, topic, label, count_topic, count_label,
            definition):
    code = f"{cfg['ref']} Q6.{num}"
    tail = rf" ({_N})" if cfg["counts"] else ""
    out, n = [], 0
    for section, lab, g in _rows(_lines(pages, caption, code),
                                 rf"({_D}) ({_D}) ({_D}){tail}"):
        h, m, t = (_f(x) for x in g[:3])
        if not (min(h, m) - 0.15 <= t <= max(h, m) + 0.15):
            raise ValueError(f"{code} {lab}: total {t} outside {h}/{m}")
        d = _dims(section, lab, code)
        for sex, v in (("male", h), ("female", m), ("total", t)):
            out.append(C.row(topic=topic, value=v, series_label=label,
                             definition=definition, series_code=code,
                             **_base(cfg), **{**d, "sex": sex}))
        if count_topic and cfg["counts"]:
            out.append(C.row(topic=count_topic, value=_f(g[3]),
                             series_label=count_label, series_code=code,
                             **_base(cfg), **d))
        n += 1
    if n != cfg["qsex"]:
        raise ValueError(f"{code}: {n} rows, expected {cfg['qsex']}")
    return out


def _q64(pages, cfg):
    code = f"{cfg['ref']} Q6.4"
    cols = [({}, "total"), ({}, "male"), ({}, "female")] + [
        ({"locality": loc, "locality_label": lab}, sex)
        for loc, lab in (("urban", "Urbana"), ("rural", "Rural"))
        for sex in ("total", "male", "female")]
    out, n = [], 0
    for ln in _lines(pages, r"QUADRO 6[.,]4\s*[-:]?\s*Taxas", code):
        if re.match(_STOP, ln):
            break
        m = re.match(rf"^(Total|\d{{2}} ?- ?\d{{2}}|65\+)\s+((?:{_D}\s*){{9}})$", ln)
        if not m:
            continue
        n += 1
        age = re.sub(r"\s*-\s*", "-", m.group(1))
        if age == "Total":
            continue               # Quadro 6.3's figures, taken there
        for (d, sex), v in zip(cols, m.group(2).split()):
            out.append(C.row(topic="employment_to_population_ratio", value=_f(v),
                             series_label=f"Taxa específica de emprego, {_ALT}",
                             series_code=code, **_base(cfg),
                             **{**d, "sex": sex, "age_group": age}))
    if n != 12:
        raise ValueError(f"{code}: {n} rows, expected 12")
    return out


def _parse_one(path: str) -> list[dict]:
    pages = _pages(path)
    cfg = _round(pages)
    rows = _q61(pages, cfg)
    rows += _by_sex(pages, cfg, r"QUADRO 6[.,]3\s*:?\s*-\s*Taxas de emprego", 3,
                    "employment_to_population_ratio", f"Taxa de emprego, {_ALT}",
                    "employed", f"População empregada, {_ALT}", "not_applicable")
    rows += _q64(pages, cfg)
    rows += _by_sex(pages, cfg, r"QUADRO 6[.,]7\s*[-:]\s*Taxas de subemprego", 7,
                    "underemployment_rate", "Taxa de subemprego", None, None,
                    "not_applicable")
    rows += _by_sex(pages, cfg, r"QUADRO 6[.,]8\s*[-:]\s*Taxas de d\w*semprego", 8,
                    "unemployment_rate", f"Taxa de desemprego, {_ALT}",
                    "unemployed", f"População desempregada, {_ALT}", "broad")
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        rows += _parse_one(p)
    return pd.DataFrame(rows)
