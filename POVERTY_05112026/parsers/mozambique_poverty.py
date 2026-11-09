"""Mozambique -- monetary poverty (the official compiler: the Ministry of
Economy and Finance / former Ministry of Planning and Development).

INE Moçambique runs the household budget surveys (IAF 1996/97, IAF 2002/03,
IOF 2008/09, IOF 2014/15) but does NOT publish the poverty estimates: the
national poverty assessments ("Avaliação Nacional da Pobreza e Bem-Estar")
are the ministry's -- MPD/DNEAP for the third (2010), MEF/DEEF for the fourth
(2016). Both files are Wayback `id_` copies of the government's own hosts
(ine.gov.mz serves an incomplete TLS chain; mef.gov.mz has dropped them).

Lines: cost-of-basic-needs consumption lines set per SPATIAL DOMAIN (13
domains, Quadro 12-1), so no single national amount exists -> line_value
blank. Welfare = consumption per capita.

TWO EDITIONS, KEPT APART BY `survey`. The fourth assessment re-estimated the
earlier rounds (national P0 1996/97 69,7 vs the third's 69.4; 2002/03 52,8 vs
54.1; 2008/09 51,7 vs 54.7), so each round appears once per edition:
  "IAF 1996/97 (Terceira Avaliação, MPD/DNEAP 2010)" ...
  "IAF 1996/97 (Quarta Avaliação, MEF/DEEF 2016)" ...
Periods are the first survey year (1996, 2002, 2008, 2014).

`parse_terceira` -- "Pobreza e Bem-Estar em Moçambique: Terceira Avaliação
Nacional" (MPD/DNEAP, Oct 2010): Quadros 3-5 / 3-7 / 3-8, P0 / P1 / P2 for
national, urban/rural, Norte/Centro/Sul and 11 provinces x 3 rounds (decimal
POINTS; the two "Diferença" columns are derived and skipped).

`parse` -- "Evolução da Pobreza e Bem-Estar em Moçambique, 1996/97-2014/15"
(MEF/DEEF discussion paper; figures "Fonte: DEEF (2016)", the fourth
assessment): Tabela 1 P0 for the same 17 areas x 4 rounds; Tabela 4 P1
national/urban/rural x 4; Tabela 5 number of poor persons x 4 (dot
thousands, read by its own pattern). Tabelas 2/3 (food share, real
consumption) are not poverty measures; Tabelas 6-9 are multidimensional.

Province names are filed in ONE spelling across both editions ("Zambézia",
"Maputo Província", "Maputo Cidade"); the third assessment prints
"Zambezia", "Província de Maputo", "Cidade de Maputo".

CROSS-CHECK (verbatim): third -- P0 69.4 / 54.1 / 54.7, P1 2008-09 21.2,
P2 11.0, Sofala 1996-97 87.9, Cidade de Maputo 2008-09 36.2. Fourth -- P0
69,7 / 52,8 / 51,7 / 46,1; Maputo Cidade 2014/15 11,6; Niassa 60,6; P1
16,7; poor 11 826 280 (urban 3 038 517 + rural 8 787 763 = national).
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C
from .poverty_tables import make_parser

_LINE = "Linha de pobreza de consumo (por domínio espacial)"
_AREAS = [  # (printed label regex, attributes)
    (r"Nacional", {}),
    (r"Urbano", {"topic": "locality", "locality": "urban", "locality_label": "Urbano"}),
    (r"Rural", {"topic": "locality", "locality": "rural", "locality_label": "Rural"}),
    (r"Norte", {"geography": "Norte"}), (r"Centro", {"geography": "Centro"}),
    (r"Sul", {"geography": "Sul"}),
    (r"Niassa", {"geography": "Niassa"}), (r"Cabo Delgado", {"geography": "Cabo Delgado"}),
    (r"Nampula", {"geography": "Nampula"}), (r"Zamb[eé]zia", {"geography": "Zambézia"}),
    (r"Tete", {"geography": "Tete"}), (r"Manica", {"geography": "Manica"}),
    (r"Sofala", {"geography": "Sofala"}), (r"Inhambane", {"geography": "Inhambane"}),
    (r"Gaza", {"geography": "Gaza"}),
    (r"(?:Província de Maputo|Maputo Província)", {"geography": "Maputo Província"}),
    (r"(?:Cidade de Maputo|Maputo Cidade)", {"geography": "Maputo Cidade"}),
]


def _rows(areas=_AREAS):
    return [{"match": rf"^{lab}(?=\s+-?\d)", **attrs} for lab, attrs in areas]


def _cols(metric, rounds, skip_after=0):
    return [{"metric": metric, "period": p, "survey": s, "reference_period": r}
            for p, r, s in rounds] + [{"skip": True}] * skip_after


_T3 = " (Terceira Avaliação, MPD/DNEAP 2010)"
_R3 = [("1996", "1996/97", "IAF 1996/97" + _T3), ("2002", "2002/03", "IAF 2002/03" + _T3),
       ("2008", "2008/09", "IOF 2008/09" + _T3)]
_T4 = " (Quarta Avaliação, MEF/DEEF 2016)"
_R4 = [("1996", "1996/97", "IAF 1996/97" + _T4), ("2002", "2002/03", "IAF 2002/03" + _T4),
       ("2008", "2008/09", "IOF 2008/09" + _T4), ("2014", "2014/15", "IOF 2014/15" + _T4)]

LAYOUT_TERCEIRA = {
    "survey": "IOF 2008/09" + _T3, "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall", "line_name": _LINE,
    "period": "2008", "reference_period": "2008/09", "strict_rows": True,
    "tables": [
        {"page_contains": ["quadro 3-5: incidência da pobreza", "nível inicial e mudança"],
         "start": r"^1996-97 2002-03 2008-09", "end": r"^Dispersão",
         "columns": _cols("headcount", _R3, 2), "rows": _rows()},
        {"page_contains": ["quadro 3-7: índice de profundidade da pobreza", "1996-97 e"],
         "start": r"^1996-97 2002-03 2008-09", "end": r"^Dispersão",
         "columns": _cols("gap", _R3, 2), "rows": _rows()},
        {"page_contains": ["quadro 3-8: índice de severidade da pobreza", "1996-97 e"],
         "start": r"^1996-97 2002-03 2008-09", "end": r"^Dispersão",
         "columns": _cols("severity", _R3, 2), "rows": _rows()},
    ],
}

LAYOUT = {
    "survey": "IOF 2014/15" + _T4, "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall", "line_name": _LINE,
    "period": "2014", "reference_period": "2014/15", "strict_rows": True,
    "tables": [
        {"page_contains": ["tabela 1: incidência da pobreza de consumo"],
         "start": r"^Área IAF96 IAF02 IOF08 IOF14", "end": r"^Nota",
         "exact_numbers": True, "columns": _cols("headcount", _R4), "rows": _rows()},
        {"page_contains": ["tabela 4: profundidade da pobreza"],
         "start": r"^Tabela 4: Profundidade", "end": r"^Fonte",
         "exact_numbers": True, "columns": _cols("gap", _R4), "rows": _rows(_AREAS[:3])},
    ],
}

_terceira = make_parser(LAYOUT_TERCEIRA)
_quarta = make_parser(LAYOUT)
_COUNT = re.compile(r"^(Nacional|Urbano|Rural)((?:\s+\d{1,3}(?:\.\d{3})+){4})\s*$")


def parse_terceira(path: str) -> pd.DataFrame:
    return _terceira(path)


def parse(path: str) -> pd.DataFrame:
    """Tabelas 1 and 4 by the engine; Tabela 5's dot-thousands counts here."""
    import pdfplumber
    df = _quarta(path)
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    seg = text[text.index("Tabela 5: Indivíduos pobres"):]
    seg = seg[:seg.index("Fonte")]
    attrs = dict((lab, a) for lab, a in _AREAS[:3])
    rows = []
    for ln in seg.splitlines():
        m = _COUNT.match(ln.strip())
        if not m:
            continue
        for (p, r, s), tok in zip(_R4, m.group(2).split()):
            rows.append(C.row(metric="poor_count", value=float(tok.replace(".", "")),
                              survey=s, welfare_aggregate="consumption",
                              line_type="national", line_level="overall", line_name=_LINE,
                              period=p, reference_period=r, frequency="ad_hoc",
                              **attrs[m.group(1)]))
    if len(rows) != 12:
        raise ValueError(f"MEF Tabela 5: read {len(rows)} counts, expected 12")
    return pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
