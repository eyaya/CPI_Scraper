"""Parser for the INSEED Comores IHPC monthly bulletin (Tier 2).

inseed-comores.org is a Next.js front end over a Strapi CMS. The monthly bulletin
is a CMS record, not a PDF: `discover` saves the Strapi JSON for the newest IHPC
publication and this parser reads 'Tableau 1 : Variation des indices par fonction
Base 100: <year>' out of its `paragraphs`, where it is stored as an HTML table:

  Regroupements   Pondérations | Indices pour les mois          | Variations en % sur
                               | Avril 25 … Mars 26  Avril 26   | 1 mois  3 mois  12 mois
  INDICE GLOBAL        10 000  | 149.1   …   149.3     150.0    |  0.4     0.6     0.6

The five index columns are individually dated and NOT contiguous — they run
[m-12, m-3, m-2, m-1, m] — so each column's own header gives its period and the
report month is simply the newest of them. We emit an index row per dated column
and the month-on-month / year-on-year rates against the report month.

Sub-items are bulleted with '❖', but the marker is not a reliable filter: INSEED
also bullets '❖ Boissons alcoolisées et tabac', which is COICOP function 02, not a
food sub-item. Rows are therefore matched against the known function labels, so
genuine sub-items (❖ Pains et céréales, ❖ Autres combustibles, …) simply don't
match and are skipped.
"""
from __future__ import annotations
import json
import re
import unicodedata
from io import StringIO

import pandas as pd

from .ihpc_note_pdf import read_many

_GEOGRAPHY = "Moroni"        # the IHPC basket covers the capital, not the country
_FALLBACK_BASE_YEAR = "2011"

_FR_MONTHS = {
    "janvier": "01", "fevrier": "02", "mars": "03", "avril": "04", "mai": "05",
    "juin": "06", "juillet": "07", "aout": "08", "septembre": "09",
    "octobre": "10", "novembre": "11", "decembre": "12",
}
# (code, label as published, normalised prefix to match on). First match wins.
_FUNCTIONS = [
    ("00", "Indice global", "indice global"),
    ("01", "Produits alimentaires et boissons non alcoolisées",
     "produits alimentaires et boissons non alcoolisees"),
    ("02", "Boissons alcoolisées et tabac", "boissons alcoolisees et tabac"),
    ("03", "Articles d'habillement et chaussures", "articles d'habillement et chaussures"),
    ("04", "Logement, eau, gaz, électricité et autres combustibles",
     "logement, eau, gaz, electricite et autres combustibles"),
    ("05", "Meubles, articles de ménage et entretien courant de la maison",
     "meubles, articles de menage et entretien courant"),
    ("06", "Santé", "sante"),
    ("07", "Transports", "transports"),
    ("08", "Communications", "communications"),
    ("09", "Loisirs et culture", "loisirs et culture"),
    ("10", "Enseignement", "enseignement"),
    ("11", "Restaurants et hôtels", "restaurants et hotels"),
    ("12", "Biens et services divers", "biens et services divers"),
]
# 'Avril 26' (2022 on) but also 'Nov. 19', 'Déc 15', 'Sept. 20' (older bulletins)
_RE_MONTH_HDR = re.compile(r"^([A-Za-zéûÉ]+)\.?\s*(\d{2})$")
_RE_BASE = re.compile(r"base\s*100\s*:?\s*(\d{4})", re.I)


def _norm(s: str) -> str:
    """Lowercase, drop accents/bullets/'dont :', collapse whitespace (incl. the
    non-breaking spaces the CMS emits inside column headers)."""
    s = str(s).replace("\xa0", " ").replace("❖", " ")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s).strip().lower()
    return re.sub(r"\s*dont\s*:?\s*$", "", s).strip()


def _period(cell: str) -> str | None:
    m = _RE_MONTH_HDR.match(str(cell).replace("\xa0", " ").strip())
    if not m:
        return None
    name = _norm(m.group(1))
    mm = _FR_MONTHS.get(name)
    if mm is None and len(name) >= 3:          # an unambiguous abbreviation
        hits = {v for k, v in _FR_MONTHS.items() if k.startswith(name)}
        mm = hits.pop() if len(hits) == 1 else None
    return f"20{m.group(2)}-{mm}" if mm else None


def _num(v) -> float | None:
    s = str(v).replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse(json_path: str) -> pd.DataFrame:
    """Read EVERY IHPC publication in the saved Strapi page (newest first; the
    discover query asks for up to 100, which holds the whole archive -- 81
    bulletins, March 2016 onward, on 2026-10-13). Each bulletin is read on its
    own and tagged with its report month; the newest bulletin wins on a shared
    (code, geography, period, measure). A bulletin that does not read is
    skipped with a message (read_many), never half-read."""
    with open(json_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    items = payload.get("data") or []
    if not items:
        raise ValueError("Comoros IHPC: Strapi returned no publication")
    by_slug = {}
    for pub in items:
        by_slug.setdefault(str(pub.get("publicationSlug") or len(by_slug)), pub)

    def _tagged(slug: str) -> pd.DataFrame:
        df = _parse_pub(by_slug[slug])
        df["_issue"] = df["period"].max()
        return df
    return read_many(list(by_slug), _tagged, "comoros_inseed")


def _parse_pub(pub: dict) -> pd.DataFrame:
    para = next((p for p in (pub.get("paragraphs") or [])
                 if re.match(r"tableau\s*1(?!\d)", _norm(p.get("title", "")))), None)
    if not para:
        raise ValueError(f"Comoros IHPC: no 'Tableau 1' in {pub.get('publicationSlug')!r}")

    base = _RE_BASE.search(para.get("title", ""))
    base_period = f"{base.group(1) if base else _FALLBACK_BASE_YEAR} = 100"

    tab = pd.read_html(StringIO(para["content"]))[0]

    # The dated header row: the one carrying the '<Mois> YY' index columns.
    hdr_i = next((i for i in range(min(4, len(tab)))
                  if sum(_period(c) is not None for c in tab.iloc[i]) >= 3), None)
    if hdr_i is None:
        raise ValueError("Comoros IHPC: no dated column header in Tableau 1")
    hdr = tab.iloc[hdr_i]

    idx_cols = {j: p for j, c in enumerate(hdr) if (p := _period(c))}
    rate_cols = {}
    for j, c in enumerate(hdr):
        n = _norm(c)
        if n == "1 mois":
            rate_cols[j] = "inflation_mom"
        elif n == "12 mois":
            rate_cols[j] = "inflation_yoy"
    if not idx_cols or len(rate_cols) != 2:
        raise ValueError(
            f"Comoros IHPC: expected dated index columns + 1/12 mois, "
            f"got {sorted(idx_cols.values())} / {sorted(rate_cols.values())}")
    report = max(idx_cols.values())

    records, seen = [], set()
    for _, row in tab.iloc[hdr_i + 1:].iterrows():
        label = _norm(row.iloc[0])
        hit = next(((c, pub_label) for c, pub_label, pref in _FUNCTIONS
                    if label.startswith(pref)), None)
        if not hit or hit[0] in seen:
            continue           # sub-item (❖ Pains et céréales, …) or a repeat
        code, pub_label = hit
        seen.add(code)

        for j, period in idx_cols.items():
            v = _num(row.iloc[j])
            if v is not None:
                records.append((code, pub_label, period, "index", round(v, 4),
                                "Index", base_period))
        for j, measure in rate_cols.items():
            v = _num(row.iloc[j])
            if v is not None:
                records.append((code, pub_label, report, measure, round(v, 4),
                                "percent", ""))

    missing = [c for c, _, _ in _FUNCTIONS if c not in seen]
    if missing:
        raise ValueError(f"Comoros IHPC incomplete: missing function(s) {missing}")

    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = _GEOGRAPHY
    out["frequency"] = "monthly"
    return out
