"""Cabo Verde -- monetary-poverty layout (INE, "Perfil da Pobreza em Cabo Verde.
Evolução da Pobreza Monetária Absoluta: 2001/02, 2007 e 2015", IDRF 2015;
plus the INE press note "Resultados da estimativa de pobreza SWIFT 2023").

Absolute poverty on two lines -- "pobreza absoluta global" (overall) and
"pobreza absoluta extrema" -- with SEPARATE URBAN AND RURAL LINES (Tabela 16:
2015 global 95.461 / 81.710 CVE, extreme 49.699 / 49.205 per person per year),
so no single national line value exists and line_value is left blank.
Consumption per person.

NUMBER FORMAT: comma decimals AND DOT thousands ("511.217"). The shared reader
treats only spaces as thousands separators, so dots between digit groups are
removed from the page text first (decimals here are always commas).

Read:
  Tabela 17  Cabo Verde / Urbano / Rural x 2001, 2007, 2015: P0 P1 P2 + extreme P0
  Tabela 18  the six 2001 study domains, 2001 and 2007 blocks only
  Tabela 35  2015: national, urban, rural, 9 islands and the three study domains
             that are not islands (Praia, Resto de Santiago, Outras Ilhas):
             poor count, P0 P1 P2, extreme count and P0, population share,
             shares of the poor and the very poor
  Tabela 36  22 municipalities (concelhos) -- the five that ARE islands
             (São Vicente, Sal, Boavista, Maio, Brava) come from Tabela 35 only
  Tabelas 37-40  the same ten columns by sex, age, marital status, literacy,
             education, activity status and socio-economic group of the head,
             expenditure quintile, household size and type
  Tabela 24  P0 (both lines) by sex of the head, urban/rural and municipality
  SWIFT 2023 Tabela 1, the 2023 column only: absolute poverty on the national
             line and extreme poverty on the INTERNATIONAL US$2.15 (2017 PPP)
             line -- survey-to-survey IMPUTATION into IV IDRF 2023 from a model
             estimated on III IDRF 2015, tagged as such in `survey`. Its 2015
             column is the model's in-sample fit (35,50 vs the official 35,2)
             and is not read.

PUBLISHED INCONSISTENCIES kept out: Tabela 18's 2015 block disagrees with
Tabela 35 (Resto de Santiago 44,7 vs 44,8; Outras ilhas 26,2 vs 25,1) -- 2015
comes from Tabela 35. Tabela 39 prints 663 poor "Desempregado" heads against
6.563 in Tabela 38 for the same 14.324 people; kept verbatim (note).

CROSS-CHECK (verbatim): 56,8 / 45,4 / 35,2 (2001, 2007, 2015); P1 11,4, P2 5,0,
extreme 10,6 (2015); 179.909 poor; Boavista 7,5; Paúl extreme 32,1; female head
39,0; Médio/Superior 1,8; SWIFT 2023 24,75 (absolute), 2,28 (US$2.15).
"""
from __future__ import annotations

import re

import pandas as pd

from . import poverty_tables as T
from ._vocab import label_rows

_S = {"skip": True}
_EX = {"line_level": "extreme", "line_name": "Limiar da pobreza absoluta extrema"}
_Y = {"2001": {"period": "2001", "survey": "IDRF 2001/02", "reference_period": "2001/02"},
      "2007": {"period": "2007", "survey": "IDRF 2007", "reference_period": "2007"},
      "2015": {"period": "2015", "survey": "IDRF 2015", "reference_period": "2015"}}
_N = r"(?=\s+-?\d)"

# Tabelas 35-40: População | poor | P0 P1 P2 | very poor | P0x | pop % | poor % | very poor %
_TEN = [_S, {"metric": "poor_count"}, {"metric": "headcount"}, {"metric": "gap"},
        {"metric": "severity"}, {"metric": "poor_count", **_EX}, {"metric": "headcount", **_EX},
        {"metric": "population_share"}, {"metric": "poor_share"}, {"metric": "poor_share", **_EX}]
_FOUR = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"},
         {"metric": "headcount", **_EX}]

_ISLANDS = ["Santo Antão", "São Vicente", "São Nicolau", "Sal", "Boavista", "Maio",
            "Santiago", "Fogo", "Brava"]
_CONCELHOS = ["Ribeira Grande", "Paúl", "Porto Novo", "Ribeira Brava", "Tarrafal de São Nicolau",
              "Tarrafal", "Santa Catarina", "Santa Cruz", "Praia", "São Domingos", "São Miguel",
              "São Salvador do Mundo", "São Lourenço dos Órgãos", "Ribeira Grande de Santiago",
              "Mosteiros", "São Filipe", "Santa Catarina do Fogo"]


def _geo(names):
    return [{"match": "^" + re.escape(n) + _N, "geography": n} for n in names]


def _loc_rows():
    return [{"match": r"^Urbano" + _N, "topic": "locality", "locality": "urban", "locality_label": "Urbano"},
            {"match": r"^Rural" + _N, "topic": "locality", "locality": "rural", "locality_label": "Rural"}]


def _t17():
    out = []
    for start, end, extra in ((r"^Cabo Verde$", r"^Urbano$", {}),
                              (r"^Urbano$", r"^Rural$", {"topic": "locality", "locality": "urban",
                                                         "locality_label": "Urbano"}),
                              (r"^Rural$", r"^Instituto", {"topic": "locality", "locality": "rural",
                                                           "locality_label": "Rural"})):
        out.append({"page_contains": ["tabela 17 – evolução da incidência", "cabo verde 2001, 2007 e 2015"],
                    "start": start, "end": end, "exact_numbers": True, "columns": _FOUR,
                    # 2015 comes from Tabela 35, which prints the same cells with more
                    "rows": [{"match": rf"^{y}" + _N, **_Y[y], **extra} for y in ("2001", "2007")]})
    return out


def _t18():
    out = []
    for y, end in (("2001", r"^ANO 2007"), ("2007", r"^ANO 2015")):
        out.append({"page_contains": ["tabela 18 – evolução da incidência", "domínio de"],
                    "start": rf"^ANO {y}$", "end": end, "exact_numbers": True,
                    "join_wrapped_labels": True, "defaults": _Y[y], "columns": _FOUR,
                    # the national row repeats Tabela 17; S. Antão / S. Vicente are the
                    # islands of the same names in Tabela 35
                    "rows": _geo(["Praia", "Resto de Santiago", "Fogo"]) +
                    [{"match": r"^S\. Antão" + _N, "geography": "Santo Antão"},
                     {"match": r"^S\. Vicente" + _N, "geography": "São Vicente"},
                     {"match": r"^Outras ilhas" + _N, "geography": "Outras Ilhas"}]})
    return out


def _char(start, end, topic, labels, prefix="", **extra):
    rows = label_rows(topic, labels, **extra)
    if prefix:
        for r in rows:
            r["characteristic"] = prefix + r["characteristic"]
    return {"page_contains": ["indicadores da pobreza absoluta global e da pobreza absoluta extrema"],
            "start": start, "end": end, "exact_numbers": True, "join_wrapped_labels": True,
            "defaults": _Y["2015"], "columns": _TEN, "rows": rows}


def _t24():
    cols = [_S, _S, {"metric": "headcount", "characteristic": "Homem", "sex": "male"},
            {"metric": "headcount", "characteristic": "Homem", "sex": "male", **_EX},
            {"metric": "headcount", "characteristic": "Mulher", "sex": "female"},
            {"metric": "headcount", "characteristic": "Mulher", "sex": "female", **_EX}]
    rows = [{"match": r"^Cabo Verde" + _N}] + [dict(r, topic="sex_of_head") for r in _loc_rows()]
    rows += [dict(r, topic="sex_of_head")
             for r in _geo(_CONCELHOS + ["São Vicente", "Sal", "Boavista", "Maio", "Brava"])]
    rows[0]["topic"] = "sex_of_head"
    return {"page_contains": ["tabela 24 – incidência da pobreza global e pobreza extrema, segundo o sexo"],
            "exact_numbers": True, "defaults": {**_Y["2015"], "topic": "sex_of_head"},
            "columns": cols, "rows": rows}


LAYOUT = {
    "survey": "IDRF 2015", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ",", "line_type": "national", "line_level": "overall",
    "line_name": "Limiar da pobreza absoluta global", "period": "2015", "reference_period": "2015",
    "tables": _t17() + _t18() + [
        {"page_contains": ["tabela 35 – indicadores da pobreza absoluta"], "end": r"^Ilha$",
         "start": r"^Pobres$", "exact_numbers": True, "defaults": _Y["2015"], "columns": _TEN,
         "rows": [{"match": r"^Total" + _N}] + _loc_rows()},
        {"page_contains": ["tabela 35 – indicadores da pobreza absoluta"], "start": r"^Ilha$",
         "end": r"^Domínio", "exact_numbers": True, "defaults": _Y["2015"], "columns": _TEN,
         "rows": _geo(_ISLANDS)},
        {"page_contains": ["tabela 35 – indicadores da pobreza absoluta"], "start": r"^Domínio",
         "end": r"^Fonte", "exact_numbers": True, "defaults": _Y["2015"], "columns": _TEN,
         "rows": _geo(["Praia", "Resto de Santiago", "Outras Ilhas"])},
        {"page_contains": ["tabela 36 – indicadores da pobreza absoluta"], "exact_numbers": True,
         "defaults": _Y["2015"], "columns": _TEN, "rows": _geo([c for c in _CONCELHOS if c != "Praia"])},
        {**_char(r"^Sexo do Representante$", r"^Grupo Etário", "sex_of_head", []),
         "rows": [{"match": r"^Masculino" + _N, "topic": "sex_of_head", "characteristic": "Masculino", "sex": "male"},
                  {"match": r"^Feminino" + _N, "topic": "sex_of_head", "characteristic": "Feminino", "sex": "female"}]},
        _char(r"^Grupo Etário do Representante$", r"^Estado Civil", "age_of_head",
              ["15-24 anos", "25-34 anos", "35-64 anos", "65 anos ou mais"]),
        _char(r"^Estado Civil do Representante$", r"^Fonte", "marital_status_of_head",
              ["Solteiro(a)", "Casado(a) legalmente", "União de facto", "Divorciado(a)",
               "Separado(a)", "Viúvo(a)"]),
        _char(r"^Alfabetização do Representante$", r"^Nível de Instrução", "literacy_of_head", ["Sim", "Não"]),
        _char(r"^Nível de Instrução do Representante$", r"^Situação perante", "education_of_head",
              ["Nunca frequentou", "Básico", "Secundário", "Médio/Superior"]),
        _char(r"^Situação perante atividade económica do Representante$", r"^Fonte",
              "employment_of_head", ["Empregado", "Desempregado", "Inativo"]),
        _char(r"^Grupo Socioeconómico do Representante$", r"^Quintil", "employment_of_head",
              ["Administração Pública", "Setor Empresarial", "Patrão agrícola", "Patrão não agrícola",
               "TCP1 agrícola", "TCP1 não agrícola", "Trabalhador familiar não remunerado",
               "Casa de família", "Desempregado", "Inativo"], prefix="Grupo socioeconómico: "),
        _char(r"^Quintil das despesas de consumo$", r"^Fonte", "quintile",
              ["1º Quintil", "2º Quintil", "3º Quintil", "4º Quintil", "5º Quintil"]),
        _char(r"^Dimensão do Agregado Familiar$", r"^Tipologia do Agregado", "household_size",
              ["1 - 2 pessoas", "3 - 4 pessoas", "5 - 6 pessoas", "7 + pessoas"]),
        _char(r"^Tipologia do Agregado Familiar$", r"^Tipologia dos agregados", "household_type",
              ["Unipessoal", "Casais Isolados", "Casais Isolados com Filhos", "Conjugais Compósitos",
               "Monoparental Nuclear", "Monoparental Compósito", "Agregados Sem Relação de Parentesco"]),
        _char(r"^Tipologia dos agregados, segundo existência", r"^Fonte", "household_type",
              ["Conjugais com crianças", "Monoparentais com crianças", "Agregados sem crianças"]),
        _t24(),
    ],
}

# SWIFT 2023 press note -- a separate small layout
_SW = {"period": "2023", "reference_period": "2023",
       "survey": "IV IDRF 2023 (SWIFT imputation, model from III IDRF 2015)"}
_INT = {"line_type": "international", "line_level": "extreme",
        "line_name": "US$2.15 per person per day (2017 PPP)"}
SWIFT = {
    **{k: LAYOUT[k] for k in ("welfare_aggregate", "unit_of_analysis", "frequency", "decimal",
                              "line_type", "line_level", "line_name")},
    **_SW,
    "tables": [{"page_contains": ["tabela 1. estimativas de pobreza, iii-idrf (2015) e iv-idrf (2023)"],
                "exact_numbers": True, "defaults": _SW, "columns": [_S, {"metric": "headcount"}],
                "rows": [{"match": r"^Nacional Pobreza Absoluta" + _N},
                         {"match": r"^Urbano Pobreza Absoluta" + _N, "topic": "locality",
                          "locality": "urban", "locality_label": "Urbano"},
                         {"match": r"^Rural Pobreza Absoluta" + _N, "topic": "locality",
                          "locality": "rural", "locality_label": "Rural"},
                         {"match": r"^Nacional Pobreza Extrema" + _N, **_INT},
                         {"match": r"^Urbano Pobreza Extrema" + _N, "topic": "locality",
                          "locality": "urban", "locality_label": "Urbano", **_INT},
                         {"match": r"^Rural Pobreza Extrema" + _N, "topic": "locality",
                          "locality": "rural", "locality_label": "Rural", **_INT}]}],
}

_DOT_THOUSANDS = re.compile(r"(?<=\d)\.(?=\d{3}(?!\d))")


def _run(path: str, layout: dict) -> list[dict]:
    pages = T._pages(path, halves=False)
    pages["full"] = [_DOT_THOUSANDS.sub("", t) for t in pages["full"]]
    rows, misses = [], []
    for tbl in layout["tables"]:
        got, matched = T._parse_table(pages, layout, tbl, layout["period"], layout["reference_period"])
        rows.extend(got)
        misses += [f"{tbl['page_contains'][0][:30]}.{r['match']!r}"
                   for ri, r in enumerate(tbl.get("rows", [])) if ri not in matched]
    if misses:
        raise ValueError(f"{len(misses)} Cabo Verde row spec(s) matched nothing: {misses[:6]}")
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = _run(path, LAYOUT)
    for e in extras or []:
        if "swift" in e.lower():
            rows += _run(e, SWIFT)
    return pd.DataFrame.from_records(rows)
