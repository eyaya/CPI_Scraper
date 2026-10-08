"""INS DR Congo — Annuaire statistique 2015 de la RDC, section 1.3 "Situation
démographique": official 2015 population ESTIMATES (no census since 1984).

REACHED THROUGH THE WAYBACK MACHINE. ins-rdc.org answers a Cloudflare 403 to
every client, and the new ins.gouv.cd lists no yearbook. The descriptor fetches
the `id_` capture of INS's own file (original bytes; the 2017-10-21 capture is
complete at 584 pages -- two later captures are truncated at 1 MB and 9 MB).

* Tableau 1.29        2015 population of the 26 new provinces + RDC (persons);
* Tableau 1.30        2015 national population by 5-year age group x sex
                      (thousands);
* Tableaux 1.31-1.56  the same for each of the 26 provinces (thousands).

UNITS AS PUBLISHED: Tableau 1.29 prints persons rounded to the thousand
("11 575 000"); the age tables print "Effectifs (en milliers)" -> unit
`thousand_persons`. Nothing is rescaled. The age tables carry no Total row and
print each sex's percentage beside its count (not collected -- the counts are).

NOT READ: Tableaux 2.1-2.7 (province x sex 2010-2015, province x age 2010-2015).
Their pages carry a second, rotated copy of the table in the text layer, and
the two interleave character by character ("Province FS exe 201208 82 ..."),
so values past the first page cannot be attributed. The 2015 figures they would
repeat are read from 1.29-1.56 instead.

PROVINCE NAMES follow Tableau 1.29 ("Kongo-Central", "Mai-Ndombe"); the age
tables' captions spell some differently ("Kongo Central", "Maï Ndombe") and are
matched to 1.29's spelling by an accent/space/hyphen-insensitive key.

CHECKS: the 26 provinces of 1.29 sum to 86 025 000 against the printed RDC
row of 85 026 000 -- a published 999 000 gap, pinned (the RDC figure is the one
the national age table adds up to, 85 026 thousand); every age
table has its 16 bands (0-4 ... 70-74, 75+) for both sexes; each table's
province's age bands (thousands) add up to its 1.29 total within rounding. The
printed percentages are not collected and not trusted as a check -- Kongo
Central's male shares sum to 103.12.

CROSS-CHECK: RDC 2015 85 026 000; Kinshasa 11 575 000; national 0-4 males
8 271 thousand, females 8 191; Kinshasa 75+ males 13 thousand.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd
import pdfplumber

_SERIES = "CD_INS_EST_2015"
_KNOWN_GAP = 999_000      # provinces minus RDC row in Tableau 1.29 (see _t129)
_BAND = r"(?:\d{1,2}-\d{1,2}|75\+)"
_AGE_ROW = re.compile(rf"(?<![\d,])({_BAND})\s+(\d+)\s+(\d+,\d+)\s+(\d+)\s+(\d+,\d+)")
_CAP_AGE = re.compile(r"Tableau 1\.(\d{2})\s*:\s*Population (?:de la |de l[’']|du |de )"
                      r"(.+?) par groupe d.\s*.ges et par sexe en 2015")
_BANDS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
          "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75+"]


def _key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[\s'’\-]", "", s).lower()


def _row(sex, age, geo, value, unit):
    return {"series_type": "estimate", "sex": sex, "age_group": age,
            "geography": geo, "period": "2015", "frequency": "annual",
            "measure": "count", "value": float(value), "unit": unit,
            "series_code": _SERIES}


def _t129(text: str, out: list) -> dict:
    i = text.find("Tableau 1.29")
    if i < 0:
        raise ValueError("INS RDC: Tableau 1.29 not found")
    provs, nat = {}, None
    for ln in text[i:].splitlines()[1:]:
        if ln.startswith("Source"):
            break
        toks = ln.split()
        # "<n> <name...> <chef-lieu> <area> <pop: 3 tokens>" ; pop >= 1 million
        if len(toks) < 5 or not re.fullmatch(r"\d{1,3}", toks[-3]) or toks[-1] != "000":
            continue
        pop = int("".join(toks[-3:]))
        if toks[0] == "RDC":
            nat = pop
            continue
        if not toks[0].isdigit():
            continue
        name = toks[1]
        provs[name] = pop
    # PUBLISHED INCONSISTENCY, PINNED: the 26 provinces sum to 86 025 000 but
    # the RDC row prints 85 026 000 -- 999 000 apart. The RDC figure is the
    # one the national age table (1.30) adds up to (85 026 thousand), so both
    # are emitted as printed and the gap is held to its known size; any other
    # gap raises.
    gap = sum(provs.values()) - (nat or 0)
    if nat is None or len(provs) != 26 or gap not in (0, _KNOWN_GAP):
        raise ValueError(f"INS RDC T1.29: {len(provs)} provinces summing "
                         f"{sum(provs.values())} vs {nat}")
    out.append(_row("total", "Total", "Total country", nat, "persons"))
    for name, v in provs.items():
        out.append(_row("total", "Total", name, v, "persons"))
    return {_key(n): n for n in provs}


def _age_table(text: str, geo: str, out: list, code: str):
    rows = {}
    for m in _AGE_ROW.finditer(text):
        band = m.group(1)
        if band in rows:
            continue
        rows[band] = (int(m.group(2)), float(m.group(3).replace(",", ".")),
                      int(m.group(4)), float(m.group(5).replace(",", ".")))
    if list(rows) != _BANDS:
        raise ValueError(f"INS RDC {code}: bands read {list(rows)}")
    # The printed percentages are NOT used as a check: they are themselves
    # inconsistent in places (Kongo Central's male shares sum to 103.12 while
    # its counts give 20.8% for 0-4, printed 20.58). The counts are held to
    # Tableau 1.29's province totals instead (see `parse`).
    for band, (m_, _, f_, _) in rows.items():
        out.append(_row("male", band, geo, m_, "thousand_persons"))
        out.append(_row("female", band, geo, f_, "thousand_persons"))


def _page_texts(pdf) -> list[str]:
    """One text per page -- but a TWO-UP SPREAD is cut down to its own half.

    From page 97 on, the PDF is a spread: the left half repeats the previous
    page's table and the right half holds the new one, and extract_text()
    interleaves the two on the same lines ("0-4 1216 20,98 ... 0-4 572 20,58").
    Where a page carries two age-table captions, the page is cropped to the
    right of the SECOND caption's "Tableau" word, so only its own table is read.
    """
    out = []
    for page in pdf.pages[90:125]:
        text = page.extract_text() or ""
        caps = list(_CAP_AGE.finditer(text))
        if len(caps) > 1:
            words = page.extract_words()
            tabs = [w for i, w in enumerate(words[:-1]) if w["text"] == "Tableau"
                    and words[i + 1]["text"].startswith("1." + caps[-1].group(1))]
            if not tabs:
                raise ValueError(f"INS RDC: cannot locate {caps[-1].group(0)!r}")
            # the band labels start a little LEFT of the caption ("10-14"
            # lost its first digit at a 2 pt margin): crop 12 pt to its left
            x0 = tabs[0]["x0"] - 12
            text = page.crop((x0, 0, page.width, page.height)).extract_text() or ""
        out.append(text)
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        raw = [(p.extract_text() or "") for p in pdf.pages[90:125]]
        pages = _page_texts(pdf)
    out: list[dict] = []
    canon = _t129(next(t for t in raw if "Tableau 1.29" in t), out)
    seen = set()
    for t in pages:
        caps = list(_CAP_AGE.finditer(t))
        if not caps:
            continue
        # after cropping, each page holds ONE age table, read from its caption
        cap = caps[-1]
        code = f"T1.{cap.group(1)}"
        if code in seen:
            continue
        seen.add(code)
        if code == "T1.30":
            geo = "Total country"
        else:
            name = re.sub(r"\s+", " ", cap.group(2)).strip()
            geo = canon.get(_key(name))
            if geo is None:
                raise ValueError(f"INS RDC {code}: province {name!r} not in T1.29")
        _age_table(t[cap.start():], geo, out, code)
    if len(seen) != 27:
        raise ValueError(f"INS RDC: {len(seen)} age tables read, expected 27")
    df = pd.DataFrame(out)
    key = ["series_type", "sex", "age_group", "geography", "period", "measure"]
    if df.duplicated(key).any():
        raise ValueError("INS RDC: duplicate keys")
    # Each province's age table must add up (in thousands) to its 1.29 total
    # within the rounding of 32 cells, so a band misattributed from the
    # neighbouring half of a spread cannot pass.
    for geo, g in df[df["unit"] == "thousand_persons"].groupby("geography"):
        tot = df[(df["geography"] == geo) & (df["unit"] == "persons")]["value"]
        if len(tot) and abs(g["value"].sum() * 1000 - tot.iloc[0]) > 40_000:
            raise ValueError(f"INS RDC: {geo} age table sums "
                             f"{g['value'].sum():.0f}k vs {tot.iloc[0]:.0f}")
    return df
