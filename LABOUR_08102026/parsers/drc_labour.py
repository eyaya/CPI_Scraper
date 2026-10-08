"""DR Congo — INS (Institut National de la Statistique), Enquête 1-2-3
2011-2012, Rapport global (2014), Phase 1 chapter 5 "Emploi".

READ FROM AN ARCHIVED COPY OF INS'S OWN FILE. ins-rdc.org answers a Cloudflare
403 to every client, and the rebuilt ins.gouv.cd carries three items, none of
them this report. The Wayback Machine holds INS's PDF as INS served it
(captured 2015-08-21), and the descriptor fetches the capture's `id_` URL, which
returns the original bytes with no archive banner or rewriting. That is an
unchanged copy of the NSO's publication, not an aggregator: every figure below
is INS's, printed by INS.

PHASE 1 ONLY -- the household employment survey. Phase 2 (the informal
production units, UPI) is excluded throughout: its tables count the jobs of
informal units, the Kenya trap in the other direction.

Two distributions of the employed ("actifs occupés de 10 ans ou plus"), each by
Kinshasa / urban areas other than Kinshasa / rural / RDC:

* Tableau I.5.4, secteur institutionnel -- Administration, Parapublic, Privé
  formel, Informel non agricole, Informel agricole -> `formality` (a
  production-unit split whose main axis is formal vs informal, as Cameroon's
  EESI3 list is filed);
* Tableau I.5.6, CSP -- cadres, indépendants, employés/ouvriers, manœuvres,
  aides familiaux -> `employment_status`, National (a hybrid of status and
  skill level, as for Chad and Cameroon).

THE COLUMN ORDER HOLDS UP ARITHMETICALLY. The RDC column of each block must be
a weighted average of the three area columns, and for both blocks one set of
weights fits exactly (Kinshasa ~8%, other urban ~21%, rural ~70% -- and the
report says Kinshasa holds 8% of the employed). The parser checks the weaker,
necessary form on every row: RDC lies within its area columns.

THE ACTIVITY-SECTOR BLOCK OF I.5.4 IS NOT COLLECTED, because it fails exactly
that test. Its RDC column cannot be an average of its own area columns:
Industrie is 4,4 nationally against 14,6 / 13,9 / 4,5, below all three, and no
positive weights reproduce the column (least squares needs a NEGATIVE weight on
Kinshasa). Primaire 71,2 and Services 9,2 are off by several points against the
weights the other two blocks share. Either the national column or the area
columns are wrong, and nothing in the report says which; the prose repeats
both. A partial block would publish a contradiction as data.

NOT COLLECTED: I.5.5 (characteristics BY sector -- age, share of women, years
of schooling, tenure; its "Répartition des emplois" column duplicates I.5.4
with public = administration + parapublic); I.5.6's rows below the CSP
(pluriactivité and salarisation RATES); I.5.3 (regional distribution of the
10+ population and a 10-15 activity rate); graphs 5.1-5.5. No nomenclature is
named -> National / Not applicable.

PERIOD 2012: the survey is "Enquête 1-2-3 / 2011-2012", reported as 2012.

CROSS-CHECK (RDC): informel agricole 59,7; informel non agricole 28,9;
administration 5,7 (Kinshasa 15,4); indépendants 62,7; aides familiaux 20,2
(rural 25,8); cadres 21,3 in Kinshasa.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = "Enquête 1-2-3 2011-2012, Phase 1 (emploi)"
_BASE = dict(survey=_SURVEY, period="2012", reference_period="Enquête 1-2-3 2011-2012",
             frequency="ad_hoc", measure="share", unit="percent",
             working_age_base="10+")
_COLS = [{"geography": "Kinshasa"},
         {"locality": "urban", "locality_label": "Milieu urbain (sans Kinshasa)"},
         {"locality": "rural", "locality_label": "Milieu rural"},
         {}]
_INST = ["Administration", "Parapublic", "Privé formel", "Informel non agricole",
         "Informel agricole"]
_CSP = ["Cadres", "Travailleurs indépendants", "Employés, ouvriers",
        "Manœuvres et autres", "Aides familiaux"]
_ROW = r"^{label}\s+(\d{{1,3}},\d)\s+(\d{{1,3}},\d)\s+(\d{{1,3}},\d)\s+(\d{{1,3}},\d)$"


def _page(path: str, caption: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[60:72]:
            text = page.extract_text() or ""
            m = re.search(caption, text)
            if m:
                return [ln.strip() for ln in text[m.end():].splitlines()]
    raise ValueError(f"Enquête 1-2-3: {caption!r} not found")


def _block(lines: list[str], labels: list[str], where: str) -> list[list[float]]:
    rows, i = [], 0
    for lab in labels:
        rx = re.compile(_ROW.format(label=re.escape(lab)))
        while i < len(lines) and not rx.match(lines[i]):
            i += 1
        if i == len(lines):
            raise ValueError(f"{where}: row {lab!r} not found in order")
        rows.append([float(v.replace(",", ".")) for v in rx.match(lines[i]).groups()])
        i += 1
    for j in range(4):
        s = sum(r[j] for r in rows)
        if abs(s - 100) > 0.25:
            raise ValueError(f"{where}: column {j} sums to {s:.1f}")
    for lab, (k, u, r, t) in zip(labels, rows):
        if not (min(k, u, r) - 0.1 <= t <= max(k, u, r) + 0.1):
            raise ValueError(f"{where}: RDC {lab} {t} lies outside its areas "
                             f"{k} / {u} / {r}")
    return rows


def _emit(topic, classification, labels, rows, code):
    out = []
    for lab, vals in zip(labels, rows):
        for ctx, v in zip(_COLS, vals):
            out.append(C.row(topic=topic, characteristic=lab,
                             classification=classification, value=v,
                             series_code=code, **_BASE, **ctx))
    return out


def parse(path: str) -> pd.DataFrame:
    t54 = _page(path, r"Tableau I\.5\.4\s*:\s*Structure des emplois par secteur "
                      r"institutionnel")
    # Bound the institutional block by its own sub-heading and the next one.
    a = t54.index("Secteur institutionnel")
    b = t54.index("Secteur d'activité")
    inst = _block(t54[a + 1:b], _INST, "I.5.4 secteur institutionnel")
    t56 = _page(path, r"Tableau I\.5\.6\s*:\s*Structure par CSP")
    end = next(i for i, ln in enumerate(t56) if ln.startswith("Taux de pluriactivit"))
    csp = _block(t56[:end], _CSP, "I.5.6 CSP")
    return pd.DataFrame(
        _emit("formality", "Not applicable", _INST, inst, "Enquête 1-2-3 T I.5.4")
        + _emit("employment_status", "National", _CSP, csp, "Enquête 1-2-3 T I.5.6"))
