"""Guinea-Bissau — INE, III Recenseamento Geral da População e Habitação (RGPH
2009), thematic volume "Características económicas", Anexos 11, 13 and 14.

COUNTS ONLY, AND ONLY OF THOSE WHOSE ANSWER WAS DECLARED -- which is the whole
story of this source. The census counts 488 644 employed (6 and over, its own
definition: "pessoas de 6 e mais anos"), but branch, occupation and status were
declared for only part of them, and the annexes say so in a column of their
own ("Com situação declarada"):

    Anexo 11  ramo de actividade económica   263 071 declared of 488 644  (54%)
    Anexo 13  profissão                      146 722 declared of 488 644  (30%)
    Anexo 14  situação na profissão          324 554 declared of 488 644  (66%)

Every percentage table in the body (Quadros 21-34) distributes the DECLARED
subset only, and "not declared" appears nowhere as a category. For occupation
that is 70% of the employed missing -- and missing unevenly: women are 59,8% of
the employed (Quadro 11) but 30,4% of those with a declared occupation (Quadro
26). A column of shares summing to 100 over that subset would look like the
composition of employment while describing a skewed third of it. So the shares
are NOT collected; the persons counted in each category are, together with the
printed declared subtotal they sum to. Nothing is imputed or rescaled. A user
can see from the subtotal how much of the 488 644 is covered; the collector
does not compute the remainder.

The annexes' own "% of all employed" column is also left out: it misrounds
(Agricultura 96 617 / 488 644 = 19,8, printed 20,0).

READ WITH PyMuPDF, which gives one cell per line: each category is its label
(wrapped over as many as seven lines in Anexo 13) followed by exactly four
cells -- count, %, count again, % -- taken BY POSITION, since a percentage can
print as a bare integer ("4838 / 1 / 4838 / 3,3"). The two counts must agree,
the categories must sum to the declared subtotal (Anexo 11 is 7 over, as
printed -- pinned in `_KNOWN_GAP`), and each annex must yield
its printed number of categories.

Situação na profissão mixes the EMPLOYER of employees (Administração Pública,
Empresa Parapública, Empresa Privada, Sector Informal) with status (Conta
própria, Patrão, Trabalho familiar sem remuneração ...) -> employment_status,
National, a hybrid like Chad's and Cameroon's CSP. No scheme is named anywhere
in the volume -> National throughout.

The census note: counts are of the population enumerated; the post-enumeration
survey measured 4,6% omission, NOT integrated into these figures.

WHY NOT THE ERI-ESI 2017/18 RELATÓRIO GERAL, the newer source: its composition
tables outside the informal-sector module (Tabela 30 formal/informal by
institutional sector, 46 employers by sector, 52 CITP major groups) all sit on
a base of about 241 000 (242 505 / 240 459), while the report's own national
estimate is 394 354 employed (§1, coefficient-of-variation note; the same
figure is Tabela 29's mislabelled "Efetivo" total). Nothing in the report
explains the missing 39%, so the universe of those tables cannot be stated --
the Zimbabwe 4.8 / Niger rule. Tabela 95 and chapter 9 are UPI tables.

CROSS-CHECK (persons): agricultura 96 617; comércio ... 85 356; trabalhadores
não qualificados 48 798; agricultores ... 42 497; conta própria 159 792;
trabalho familiar sem remuneração 117 720.
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd

from . import _common as C

_SURVEY = ("III Recenseamento Geral da População e Habitação (RGPH) 2009, "
           "persons with a declared answer")
_ANNEXES = [  # (anexo, topic, printed number of categories)
    ("11", "industry", 18),
    ("13", "occupation", 10),
    ("14", "employment_status", 9),
]
_NUM = re.compile(r"^\d+(?:[.,]\d+)?$")
# PUBLISHED DISCREPANCY, pinned: Anexo 11's eighteen printed branch counts sum
# to 263 078, seven more than its printed declared subtotal (263 071). Kept as
# printed; any OTHER gap -- or this one closing -- raises.
_KNOWN_GAP = {"11": 7}


def _tokens(path: str) -> list[str]:
    out = []
    with fitz.open(path) as doc:
        for page in doc:
            text = page.get_text()
            if not re.search(r"Anexo 1[0-5]:", text):
                continue
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if lines and re.fullmatch(r"\d{1,3}", lines[0]):   # page number
                lines = lines[1:]
            out += lines
    return out


def _annex(tokens: list[str], no: str, n_cats: int) -> tuple[int, list]:
    where = f"RGPH 2009 Anexo {no}"
    try:
        i = next(k for k, t in enumerate(tokens) if t.startswith(f"Anexo {no}:"))
    except StopIteration:
        raise ValueError(f"{where}: not found") from None
    end = next((k for k in range(i + 1, len(tokens))
                if re.match(r"Anexo \d+", tokens[k])), len(tokens))
    body = tokens[i + 1:end]
    t = body.index("Total")
    employed, declared = int(body[t + 1]), int(body[t + 2])
    if employed != 488644:
        raise ValueError(f"{where}: employed {employed}, expected 488644")
    cats, label, k = [], [], t + 3
    while k < len(body):
        if _NUM.match(body[k]):
            cells = body[k:k + 4]
            if len(cells) < 4 or not all(_NUM.match(c) for c in cells):
                raise ValueError(f"{where}: {' '.join(label)!r} reads {cells}")
            if cells[0] != cells[2]:
                raise ValueError(f"{where}: {' '.join(label)!r} counts "
                                 f"{cells[0]} / {cells[2]} disagree")
            cats.append((re.sub(r"\s+", " ", " ".join(label)).strip(),
                         int(cells[0])))
            label, k = [], k + 4
        else:
            label.append(body[k])
            k += 1
    if len(cats) != n_cats or not all(c[0] for c in cats):
        raise ValueError(f"{where}: {len(cats)} categories, {n_cats} printed: "
                         f"{[c[0] for c in cats]}")
    if sum(c[1] for c in cats) - declared != _KNOWN_GAP.get(no, 0):
        raise ValueError(f"{where}: categories sum to {sum(c[1] for c in cats)}, "
                         f"declared subtotal {declared}")
    return declared, cats


def parse(path: str) -> pd.DataFrame:
    tokens = _tokens(path)
    out = []
    for no, topic, n in _ANNEXES:
        declared, cats = _annex(tokens, no, n)
        for lab, v in [*cats, ("Com situação declarada", declared)]:
            out.append(C.row(topic=topic, characteristic=lab,
                             classification="National", value=v,
                             survey=_SURVEY, period="2009",
                             reference_period="RGPH 2009", frequency="ad_hoc",
                             measure="count", unit="persons",
                             working_age_base="6+",
                             series_code=f"RGPH2009 Anexo {no}"))
    return pd.DataFrame(out)
