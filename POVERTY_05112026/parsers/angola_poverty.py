"""Angola -- monetary-poverty layout (INE Angola, "Quadros de Relatório de
Pobreza para Angola - IDR 2019", the table workbook of the IDREA 2018-2019
poverty report; folder População e Sociedade / Pobreza Monetária).

Three FGT indices -- Incidência (P0), Profundidade (P1), Intensidade (P2; the
workbook's word for SEVERITY, confirmed by P0 > P1 > P2 on every row) --
plus the count of poor people and the population total beside them.

THE CUTS ARE CHARACTERISTICS OF THE HOUSEHOLD HEAD. The tables do not say so,
but their population columns do: "Homens" 21 928 358 + "Mulheres" 7 383 622
= the national 29 391 387, so the sexes are of the head (people in male- and
female-headed households), and likewise the age bands (no child bands, same
total) and schooling.

Collected
  Q4.3.3  P0, P1, P2, poor count: national, urban/rural, 18 provinces, sex /
          age / schooling of the head
  Q4.3.4  P0 by province x urban / rural
  Q4.3.5  P0, P1, P2, poor count by household size and labour-force status
          of the head
  Q4.3.6  P0, P1, P2, poor count by the head's employment (employed heads only)
Not collected: Q2.4/Q3.1/Q3.2 (the same figures without counts), number of
workers, dependent children and dwelling type (no topic), Q4.3.6's "Angola"
row (it prints the national 40.6 beside the EMPLOYED-head counts 9 140 138 /
21 722 458, which give 42.1), income/consumption/Gini sheets (not poverty
measures / inequality).

PUBLISHED DEFECT HANDLED: Q4.3.4 swaps the Cuanza Norte and Cuanza Sul LABELS
against Q4.3.3 (43.8 and 50.1 trade places). Q4.3.3 is the consistent one --
its poor / total counts reproduce its own P0 (1 061 098 / 2 119 507 = 50.1 for
Cuanza Sul) -- so the two Cuanza rows of Q4.3.4 are not read.

Excel artefacts: household sizes "1-2", "3-4", "5-6" are stored as DATES
(2025-01-02 ...) and are restored to their printed labels.

CROSS-CHECK (verbatim): P0 40.6 / P1 10.1 / P2 4.4; poor 11 947 270 of
29 391 387; urban 29.8, rural 57.2; Moxico 62.8 (rural 81.3); Luanda 20.1;
female-headed 40.2; heads with no schooling 56.5; 7+ members 50.8.
"""
from __future__ import annotations

import datetime as dt
import re

import pandas as pd

from . import _common as C

_BASE = dict(survey="IDREA 2018-2019", welfare_aggregate="consumption",
             unit_of_analysis="person", line_type="national", line_level="overall",
             line_name="Linha de pobreza nacional", period="2018",
             reference_period="2018-2019", frequency="ad_hoc")

LAYOUT = {**_BASE, "decimal": ".", "tables": []}   # read by the bespoke parse below

_BLOCKS = {  # Q4.3.3 / Q4.3.5 heading -> topic
    "Área de residência": "locality", "Província": "province", "Sexo": "sex_of_head",
    "Idade": "age_of_head", "Escolaridade": "education_of_head",
    "Número de membros no agregado": "household_size",
    "Condição perante o trabalho": "employment_of_head",
    "Receitas laborais": "employment_of_head",
    "Situação perante a actividade": "employment_of_head",
}
_SKIP_BLOCKS = {"Composição do agregado", "Agregados com crianças dependentes",
                "Nª de pessoas com 15+ anos a trabalhar", "Regime de ocupação"}


def _label(v) -> str:
    if isinstance(v, (dt.date, dt.datetime)):
        return f"{v.month}-{v.day}"          # "1-2" stored as 2025-01-02
    return str(v).strip()


def _row(metric, value, **kw):
    return C.row(metric=metric, value=float(value), **{**_BASE, **kw})


def _cells(topic, label, block):
    if topic == "locality":
        loc = {"Urbana": "urban", "Rural": "rural"}[label]
        return dict(topic="locality", characteristic=label, locality=loc, locality_label=label)
    if topic == "province":
        return dict(geography=label)
    kw = dict(topic=topic, characteristic=label)
    if topic == "sex_of_head":
        kw["sex"] = {"Homens": "male", "Mulheres": "female"}[label]
    if block in ("Receitas laborais", "Situação perante a actividade"):
        kw["characteristic"] = f"{block}: {label}"      # one label appears in both blocks
    return kw


def _fgt_sheet(ws, national_label, skip_national=False):
    rows, block, started = [], None, False
    for r in ws.iter_rows(values_only=True):
        if r[0] is None:
            continue
        lab = _label(r[0])
        nums = [x for x in r[1:6] if x is not None]
        if not nums:
            # Title, subtitle and header rows come before the national row;
            # after it, every number-less row is a block heading.
            if started:
                if lab not in _BLOCKS and lab not in _SKIP_BLOCKS and not lab.startswith("Fonte"):
                    raise ValueError(f"angola: unknown block {lab!r} in {ws.title}")
                block = lab
            continue
        if lab == national_label:
            started = True
            if not skip_national:
                for m, x in zip(("headcount", "gap", "severity", "poor_count"), nums):
                    rows.append(_row(m, x))
            continue
        if block in _SKIP_BLOCKS or block is None:
            continue
        if len(nums) != 5 or not all(isinstance(x, (int, float)) for x in nums):
            raise ValueError(f"angola: {ws.title} {lab!r}: {nums}")
        kw = _cells(_BLOCKS[block], lab, block)
        for m, x in zip(("headcount", "gap", "severity", "poor_count"), nums[:4]):
            rows.append(_row(m, x, **kw))
        # the poor count over the population must reproduce the printed P0
        if abs(nums[3] / nums[4] * 100 - nums[0]) > 0.15:
            raise ValueError(f"angola: {ws.title} {lab!r}: poor/total {nums[3]/nums[4]*100:.2f} != P0 {nums[0]}")
    return rows


def parse(path: str) -> pd.DataFrame:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = _fgt_sheet(wb["Q4.3.3"], "Total")
    rows += [r for r in _fgt_sheet(wb["Q4.3.5"], "Angola", skip_national=True)]
    rows += _fgt_sheet(wb["Q4.3.6"], "Angola", skip_national=True)

    n = 0
    for r in wb["Q4.3.4"].iter_rows(values_only=True):
        lab = _label(r[0]) if r[0] is not None else ""
        if lab in ("", "Angola", "Cuanza Norte", "Cuanza Sul") or not isinstance(r[1], (int, float)):
            continue
        for loc, lbl, x in (("urban", "Urbana", r[2]), ("rural", "Rural", r[3])):
            rows.append(_row("headcount", x, geography=lab, topic="locality",
                             characteristic=lbl, locality=loc, locality_label=lbl))
        n += 1
    if n != 16:
        raise ValueError(f"angola: Q4.3.4 gave {n} provinces, want 16 (18 less the swapped Cuanzas)")
    df = pd.DataFrame.from_records(rows)
    # Province names: Q4.3.4 spells some differently from Q4.3.3 ("Uíge"/"Uige",
    # "Malanje"/"Malange", "Huíla"/"Huila", "Cuando Cubango"/"Cuando Kubango").
    # One place, one name: Q4.3.3's spellings are kept throughout.
    df["geography"] = df["geography"].replace(
        {"Uíge": "Uige", "Malanje": "Malange", "Huíla": "Huila", "Cuando Cubango": "Cuando Kubango"})
    return df
