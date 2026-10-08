"""São Tomé and Príncipe — INE: RGPH 2012 thematic report 5 "Actividade
Económica" (primary), IOF 2017 report and QUIBB 2005 report (extras).

INE runs no labour force survey; the three documents that print headline
labour-force tables are the census and two household surveys. Each is
recognised by its own text, never by file name.

RGPH 2012 (census, May 2012; the same report `labour/` reads for composition):
    Tabela 3.1.2  15+ by activity status, counts by sex   -> labour_force,
                  employed, unemployed, working_age_population (total only)
    Tabela 3.4.4  taxa líquida de atividade, sex x residence x age
                                                          -> labour_force_participation_rate
    Tabela 3.4.6  the same by district x age
    Tabela 4.3.4  taxa líquida de ocupação, sex x residence x age
                                                          -> employment_to_population_ratio
    Tabela 4.3.6  the same by district x age
    Tabela 5.3.3  taxa de desemprego, sex x residence x age -> unemployment_rate
    Tabela 5.3.6  the same by district x age
  Unemployed = without work, available AND seeking (chapter V's definition)
  -> `strict`. Base 15+.

IOF 2017 (Inquérito aos Orçamentos Familiares):
    Tabela 23  taxa de desemprego by sex           -> unemployment_rate (BIT)
    Tabela 22  taxa de desemprego (BIT) dos jovens  -> youth_unemployment_rate
    Tabela 19  jovens 15-24 fora da escola e do trabalho -> neet_rate
  Only the "Total" columns -- the others split by poverty status, which no
  column here holds. THE YOUTH BAND OF TABELA 22 IS NOT PRINTED against it:
  the neighbouring tables say 15-24 and the report's prose says "16 a 24
  anos", so age_group carries "Jovens" as printed rather than a guessed band.
  NOT TAKEN, and why: Tabela 20 "taxa de actividade" (52,4 / 65,8 / 39,3) is
  digit for digit Tabela 24's "Razão emprego/população" -- one of the two is
  mislabelled and the report does not say which, so neither is collected;
  Tabela 18 "taxa de emprego dos jovens" (78,7) is 100 minus the youth
  unemployment rate (21,3), i.e. employed/active youth, not an employment-to-
  population ratio.

QUIBB 2005 (Questionário Unificado de Indicadores Básicos de Bem-Estar):
    Tabela 5.1  população activa and % of the 15+   -> labour_force,
                labour_force_participation_rate, working_age_population
    Tabela 5.3  população desempregada and taxa     -> unemployed, unemployment_rate
  (the report numbers two tables "5.3"; the unemployment one is meant) by sex,
  residence, domínio (Água Grande / outros urbanos) and education. NOT TAKEN:
  Tabela 5.2's "população empregada" -- QUIBB splits the employed into
  "permanent" (44 714) and "precário" (9 319), and 5.2 counts only the
  first, so it is not the employed population. The domínio "Rural" rows repeat
  the residence "Rural" rows (checked equal) and are not emitted twice.

PUBLISHED DEFECTS:
* RGPH Tabela 3.1.2 prints the 15+ residents as 104 120 total but 54 443 men
  and 54 879 women (sum 109 322), and those sex figures do not reproduce the
  published participation rates (38 400 / 54 443 = 70,5, printed 74,6). Only
  the total is collected.
* RGPH 4.3.6's "Total" row gives the national employment rate as 54,2, 4.3.4
  as 54,1; the district table's national row is not emitted (its age values
  are identical to 4.3.4's, checked), the sex x residence table's is.

CROSS-CHECK: RGPH -- LF 65 152, unemployed 8 857, LFPR 62,6 (urban 64,1),
EPR 54,1, unemployment 13,6 (women 19,7; 15-24 20,8; Cantagalo 16,8).
IOF 2017 -- unemployment 8,9 (men 5,1, women 14,6); youth 21,3; NEET 22,6.
QUIBB 2005 -- LFPR 72,6; unemployment 14,8 (women 21,1; Água Grande 14,6).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_AGES = ["15-24", "25-34", "35-44", "45-54", "55-64", "65+"]
_DISTRICTS = {"Lobata", "Lembá", "Mé-Zochi", "Agua Grande", "Cantagalo", "Caué",
              "Príncipe"}
_D = r"\d{1,3},\d"


def _f(s):
    return float(s.replace(" ", "").replace(",", "."))


def _text(path) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [p.extract_text() or "" for p in pdf.pages]


def _after(pages, caption, where):
    rx = re.compile(caption)
    for t in pages:
        m = rx.search(t)
        if m and not re.search(r"\.{5}", t[m.start():m.start() + 200]):
            return [ln.strip() for ln in t[m.end():].splitlines()]
    raise ValueError(f"{where}: {caption!r} not found")


# --------------------------------------------------------------- RGPH 2012
_RGPH = dict(survey="Recenseamento Geral da População e da Habitação (RGPH) 2012",
             period="2012", reference_period="RGPH 2012", frequency="ad_hoc",
             working_age_base="15+")


def _rgph_312(pages):
    out = []
    lines = _after(pages, r"Tabela 3\.1\.2 Repartição da população de 15 anos", "RGPH 3.1.2")
    want = {"População Residente": "working_age_population",
            "População Ativa": "labour_force",
            "População Ativa Empregada": "employed",
            "População Ativa Desempregada": "unemployed"}
    got = {}
    for ln in lines:
        m = re.match(r"^(População (?:Residente|Ativa(?: Empregada| Desempregada)?))\s+"
                     r"(\d+)\s+(\S+)\s+(\d+)\s+\S+\s+(\d+)\s", ln)
        if m:
            got[m.group(1)] = [float(m.group(i)) for i in (2, 4, 5)]
    if set(got) != set(want):
        raise ValueError(f"RGPH 3.1.2: rows {list(got)}")
    lf, em, un = (got[k] for k in ("População Ativa", "População Ativa Empregada",
                                    "População Ativa Desempregada"))
    for j in range(3):
        if em[j] + un[j] != lf[j]:
            raise ValueError("RGPH 3.1.2: employed + unemployed != active")
    for label, topic in want.items():
        vals = got[label]
        sexes = [("total", vals[0])] if topic == "working_age_population" else \
            list(zip(("total", "male", "female"), vals))
        for sex, v in sexes:
            out.append(C.row(topic=topic, value=v, series_label=label, sex=sex,
                             series_code="RGPH2012 T3.1.2", **_RGPH))
    return out


def _age_rows(lines, n_vals, stop=r"^(Tabela|Gráfico|Capítulo|\d{2,3}$)"):
    rx = re.compile(rf"^(.+?)\s+((?:{_D}\s*){{{n_vals}}})$")
    for ln in lines:
        if re.match(stop, ln):
            break
        m = rx.match(ln)
        if m:
            yield m.group(1).strip(), [_f(v) for v in m.group(2).split()]


def _blocks_sex_by_rows(pages, caption, topic, label, code, definition, where):
    """Tables laid out as  [Total|Masculino|Feminino] blocks of
    Total/Urbano/Rural rows x (Total + six ages)  (4.3.4, 5.3.3)."""
    out, sex, n = [], "total", 0
    for ln in _after(pages, caption, where):
        if re.match(r"^(Tabela|Gráfico|\s*Por distrito)", ln) or "Por distrito" in ln:
            break
        h = re.match(r"^(Masculino|Feminino)\s+Total\s+15-24", ln)
        if h:
            sex = "male" if h.group(1) == "Masculino" else "female"
            continue
        m = re.match(rf"^(Total|Urbano|Rural)\s+((?:{_D}\s*){{7}})$", ln)
        if not m:
            continue
        loc = {"Total": {}, "Urbano": {"locality": "urban", "locality_label": "Urbano"},
               "Rural": {"locality": "rural", "locality_label": "Rural"}}[m.group(1)]
        vals = [_f(v) for v in m.group(2).split()]
        for age, v in zip(["Total"] + _AGES, vals):
            out.append(C.row(topic=topic, value=v, series_label=label, sex=sex,
                             age_group=age, definition=definition,
                             series_code=code, **_RGPH, **loc))
        n += 1
    if n != 9:
        raise ValueError(f"{where}: {n} rows, expected 9")
    return out


def _rgph_344(pages):
    """Tabela 3.4.4: blocks headed Total/Urbano/Rural, rows = ages, cols = T/M/F."""
    out, loc, n = [], None, 0
    lines = _after(pages, r"Tabela 3\.4\.4\. Taxa líquida de atividade", "RGPH 3.4.4")
    for ln in lines:
        if re.match(r"^(Tabela|\s*Por distrito)", ln) or "Por distrito" in ln:
            break
        m = re.match(rf"^(Total|Urbano|Rural|\d{{2}}(?:-\d{{2}}|\+) anos)\s+({_D}) ({_D}) ({_D})$", ln)
        if not m:
            continue
        lab = m.group(1)
        if lab in ("Total", "Urbano", "Rural"):
            loc = {"Total": {}, "Urbano": {"locality": "urban", "locality_label": "Urbano"},
                   "Rural": {"locality": "rural", "locality_label": "Rural"}}[lab]
            age = "Total"
        else:
            age = lab.replace(" anos", "")
        for sex, v in zip(("total", "male", "female"), m.groups()[1:]):
            out.append(C.row(topic="labour_force_participation_rate", value=_f(v),
                             series_label="Taxa líquida de atividade",
                             definition="strict", sex=sex, age_group=age,
                             series_code="RGPH2012 T3.4.4", **_RGPH, **loc))
        n += 1
    if n != 21:
        raise ValueError(f"RGPH 3.4.4: {n} rows, expected 21")
    return out


def _by_district(pages, caption, topic, label, code, definition, where, national=None):
    out, n = [], 0
    for lab, vals in _age_rows(_after(pages, caption, where), 7):
        lab = re.sub(r"\s+", " ", lab)
        if lab in ("Total", "Total de STP"):
            if national is None:
                raise ValueError(f"{where}: unexpected national row")
            for age, v in zip(["Total"] + _AGES, vals):
                ref = national.get(age)
                if ref is None or abs(ref - v) > 0.15:
                    raise ValueError(f"{where}: national {age} {v} vs {ref}")
            continue
        if lab not in _DISTRICTS:
            raise ValueError(f"{where}: unknown district {lab!r}")
        for age, v in zip(["Total"] + _AGES, vals):
            out.append(C.row(topic=topic, value=v, series_label=label, geography=lab,
                             age_group=age, definition=definition,
                             series_code=code, **_RGPH))
        n += 1
    if n != 7:
        raise ValueError(f"{where}: {n} districts, expected 7")
    return out


def _national(rows):
    return {r["age_group"]: r["value"] for r in rows
            if r["sex"] == "total" and r["locality"] == "all"
            and r["geography"] == "Total country"}


def _rgph(pages):
    rows = _rgph_312(pages)
    rows += _rgph_344(pages)
    rows += _by_district(pages, r"Tabela nº 3\.4\.6\. Taxa líquida de atividade",
                         "labour_force_participation_rate", "Taxa líquida de atividade",
                         "RGPH2012 T3.4.6", "strict", "RGPH 3.4.6")
    epr = _blocks_sex_by_rows(pages, r"Tabela 4\.3\.4\. Taxa líquida de ocupação",
                              "employment_to_population_ratio", "Taxa líquida de ocupação",
                              "RGPH2012 T4.3.4", "not_applicable", "RGPH 4.3.4")
    rows += epr
    rows += _by_district(pages, r"Tabela 4\.3\.6\. Taxa líquida de ocupação",
                         "employment_to_population_ratio", "Taxa líquida de ocupação",
                         "RGPH2012 T4.3.6", "not_applicable", "RGPH 4.3.6",
                         national=_national(epr))
    ur = _blocks_sex_by_rows(pages, r"Tabela 5\.3\.3\. Taxa de desemprego segundo",
                             "unemployment_rate", "Taxa de desemprego",
                             "RGPH2012 T5.3.3", "strict", "RGPH 5.3.3")
    rows += ur
    rows += _by_district(pages, r"Tabela 5\.3\.6\. Taxa de desemprego",
                         "unemployment_rate", "Taxa de desemprego",
                         "RGPH2012 T5.3.6", "strict", "RGPH 5.3.6",
                         national=_national(ur))
    return rows


# --------------------------------------------------------------- IOF 2017
_IOF = dict(survey="Inquérito aos Orçamentos Familiares (IOF) 2017",
            period="2017", reference_period="IOF 2017", frequency="ad_hoc",
            working_age_base="15+")


def _iof(pages):
    out = []
    specs = [
        (r"Tabela 23\. Taxa de desemprego dos indivíduos de 15 anos", "unemployment_rate",
         "Taxa de desemprego", "Total", "strict", "IOF2017 T23"),
        (r"Tabela 22\. Taxa de desemprego \(BIT\) dos jovens", "youth_unemployment_rate",
         "Taxa de desemprego (BIT) dos jovens", "Jovens", "strict", "IOF2017 T22"),
        (r"Tabela 19\. Percentagem de jovens de 15 a 24 anos", "neet_rate",
         "Jovens fora do sistema educativo e do mercado de trabalho", "15-24",
         "not_applicable", "IOF2017 T19"),
    ]
    for caption, topic, label, age, definition, code in specs:
        row = next((ln for ln in _after(pages, caption, code)
                    if re.match(r"^Total(\s+\d{1,3}\.\d){9}$", ln)), None)
        if row is None:
            raise ValueError(f"{code}: no nine-value Total row")
        vals = [float(v) for v in row.split()[1:]]
        h, m, t = vals[6:9]                   # the "Total" block: Homem Mulher Total
        if not (min(h, m) - 0.15 <= t <= max(h, m) + 0.15):
            raise ValueError(f"{code}: total {t} outside {h}/{m}")
        for sex, v in (("male", h), ("female", m), ("total", t)):
            out.append(C.row(topic=topic, value=v, series_label=label, sex=sex,
                             age_group=age, definition=definition,
                             series_code=code, **_IOF))
    # The unemployment rate is also Tabela 15's: they must agree.
    t15 = _after(pages, r"Tabela 15\. Situação do emprego por género", "IOF2017 T15")
    des = next(ln for ln in t15 if ln.startswith("Desempregados"))
    if [float(x) for x in des.split()[1:4]] != [r["value"] for r in out[:3]]:
        raise ValueError("IOF2017: Tabela 15 and Tabela 23 disagree")
    return out


# --------------------------------------------------------------- QUIBB 2005
_QB = dict(survey="Questionário Unificado de Indicadores Básicos de Bem-Estar (QUIBB) 2005",
           period="2005", reference_period="QUIBB 2005", frequency="ad_hoc",
           working_age_base="15+")
_QB_SECTIONS = {"Sexo": "sex", "Meio de residência": "loc", "Meio de Residência": "loc",
                "Domínio do estudo": "dom", "Nível de instrução": "edu"}


def _qb_rows(lines):
    section = None
    for ln in lines:
        if ln.startswith(("Os chefes", "Emprego Permanente", "Gráfico", "Fevereiro")):
            break
        if ln in _QB_SECTIONS:
            section = _QB_SECTIONS[ln]
            continue
        m = re.match(rf"^(Total)\s+(\d+)\s+%\s+({_D})\s+(\d+)\s+%$", ln)
        if m:
            yield None, "Total", (m.group(2), None, m.group(3), m.group(4))
            continue
        m = re.match(rf"^(.+?)\s+(\d+)\s+({_D})\s+({_D})\s+(\d+)\s+({_D})$", ln)
        if m and section:
            yield section, m.group(1), (m.group(2), m.group(3), m.group(4), m.group(5))


def _qb_dims(section, lab):
    if section is None:
        return {}
    if section == "sex":
        return {"sex": {"Homem": "male", "Mulher": "female"}[lab]}
    if section == "loc":
        return {"locality": C.normalise_locality(lab), "locality_label": lab}
    if section == "dom":
        if lab == "Água Grande":
            return {"geography": "Água Grande"}
        if lab.startswith("Outros"):
            return {"locality": "other", "locality_label": lab}
        return None                                 # "Rural": the residence row again
    return {"education": lab}


def _quibb(pages):
    out = []
    t51 = list(_qb_rows(_after(pages, r"Tabela 5\.1 População activa segundo o sexo",
                               "QUIBB T5.1")))
    t53 = list(_qb_rows(_after(pages, r"Tabela 5\.3 – População desempregada", "QUIBB T5.3")))
    # Total + 2 sexes + 2 residences + 3 domínios + 4 education levels.
    if len(t51) != 12 or len(t53) != 12:
        raise ValueError(f"QUIBB: {len(t51)} / {len(t53)} rows, expected 12")
    rural = {}
    for (sec, lab, g), (sec2, lab2, g2) in zip(t51, t53):
        # QUIBB spells the domain "Outros Urbanos" in 5.1, "Outros Urbano" in
        # 5.3: matched without the plural; 5.1's spelling is kept.
        if (sec, lab.rstrip("s")) != (sec2, lab2.rstrip("s")):
            raise ValueError(f"QUIBB: rows out of step {lab!r} / {lab2!r}")
        if lab == "Rural":
            rural.setdefault("rows", []).append((g, g2))
        d = _qb_dims(sec, lab)
        if d is None:
            continue
        lf, lfpr, pop = float(g[0]), _f(g[2]), float(g[3])
        un, ur, lf2 = float(g2[0]), _f(g2[2]), float(g2[3])
        if lf2 != lf:
            raise ValueError(f"QUIBB {lab}: active population differs between tables")
        code = "QUIBB2005 T5.1"
        out += [C.row(topic="labour_force", value=lf, series_label="População activa",
                      series_code=code, **_QB, **d),
                C.row(topic="labour_force_participation_rate", value=lfpr,
                      series_label="População activa (% da pop. >=15 anos)",
                      definition="strict", series_code=code, **_QB, **d),
                C.row(topic="working_age_population", value=pop,
                      series_label="Pop. >=15 anos", series_code=code, **_QB, **d),
                C.row(topic="unemployed", value=un, series_label="Pop. desempregada",
                      series_code="QUIBB2005 T5.3", **_QB, **d),
                C.row(topic="unemployment_rate", value=ur, series_label="Taxa de desemprego",
                      definition="strict", series_code="QUIBB2005 T5.3", **_QB, **d)]
    if len(rural.get("rows", [])) != 2 or rural["rows"][0] != rural["rows"][1]:
        raise ValueError("QUIBB: domínio Rural no longer equals residence Rural")
    return out


def _parse_one(path):
    pages = _text(path)
    head = " ".join(pages[:60])
    if "QUIBB-STP-2005" in head:
        return _quibb(pages)
    if re.search(r"Fonte: IOF 2017", head):
        return _iof(pages)
    if "Tabela 5.3.3" in " ".join(pages) and "Recenseamento" in " ".join(pages[:5]):
        return _rgph(pages)
    raise ValueError(f"STP: unrecognised document {path!r}")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        rows += _parse_one(p)
    return pd.DataFrame(rows)
