"""ANStat Côte d'Ivoire — RGPH 2021 and RGPH 2014 censuses (Tier-3 PDFs, read
from Wayback Machine `id_` copies of ANStat's / INS's own files).

anstat.ci answers every client with a Cloudflare interactive challenge (as for
labour, unemployment and GDP), so both reports are fetched as the Wayback
Machine's byte-for-byte captures of the files ANStat itself published -- not
an aggregator, the NSO's own PDFs.

RGPH 2021, Rapport thématique Tome 1 "État et structure de la population"
(ANStat, July 2025) -- series_type `census`, period 2021:
* Tableau 2.7  resident population by DISTRICT and REGION: counts, the region's
               "poids démographique" (`share`) and rapport de masculinité
               (`sex_ratio`);
* Tableau 3.2  population by five-year age group and sex (+ sex ratio), with
               the printed "Non déclaré" age row kept as its own age_group.

RGPH 2014, Rapport global d'analyse (INS, February 2017) -- period 2014:
* Tableau 2.3  population by region / autonomous district, counts + share;
* Tableau 2.7  population by five-year age group and sex (+ sex ratio).

DISTRICTS ARE SUMS OF REGIONS. Tableau 2.7 (2021) interleaves 14 district rows
with the 31 regions; each district's count is asserted equal to the sum of its
regions before it is kept (Bas-Sassandra 2 687 176 = San-Pedro + Gbôklè +
Nawa). Never add the two levels. A PUBLISHED DEFECT on the district rows: their
"poids" column is not the district's weight (Bas-Sassandra prints 3,1, where
2 687 176 / 29 389 150 is 9,1) and their sex ratio cannot be checked, so for
districts ONLY the count is taken. The two autonomous districts (Abidjan,
Yamoussoukro) have no regions and are kept whole.

Names are as printed in each report: 2021 uses mixed case ("Haut-Sassandra"),
2014 upper case ("HAUT-SASSANDRA"); a typesetting space after a hyphen
("Bas- Sassandra") is closed up.

PUBLISHED RESIDUE KEPT: in 2021 Tableau 3.2 male + female misses the printed
total by 1 in places (20-24 ans: 1 527 341 + 1 470 417 = 2 997 758, printed
2 997 759); a residue of 1 is accepted as printed, the split must still be
unique, and anything larger raises.

PUBLISHED GAP KEPT: the 2021 regions and autonomous districts sum to
29 389 152, two more than the printed national 29 389 150; pinned in the code.

NOT READ: Annexe 2 single-year ages (the PDF carries a doubled, interleaved
text layer there: "Tablea4u0 x répartition ..."); the functional-age and
religion/ethnicity/nationality tables; the per-region 2014 booklets on ins.ci.

CROSS-CHECK: 2021 total 29 389 150 (15 344 990 M / 14 044 160 F, RM 109,3);
Abidjan 6 321 017; 0-4 ans 3 696 301. 2014 total 22 671 331 (RM 107,0);
Abidjan 4 707 404.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_NUM = re.compile(r"^\d{1,3}$")
_GRP = re.compile(r"^\d{3}$")
_DISTRICTS_2021 = {
    "Bas-Sassandra", "Comoé", "Denguélé", "District Autonome d'Abidjan",
    "District Autonome de Yamoussoukro", "Gôh-Djiboua", "Lacs", "Lagunes",
    "Montagnes", "Sassandra-Marahoué", "Savane", "Vallée de Bandama", "Woroba",
    "Zanzan"}
_AUTONOMOUS = {"District Autonome d'Abidjan", "District Autonome de Yamoussoukro"}


def _rec(sex, age, geo, period, measure, value, unit, code):
    return {"series_type": "census", "sex": sex, "age_group": age,
            "geography": geo, "period": str(period), "frequency": "annual",
            "measure": measure, "value": float(value), "unit": unit,
            "series_code": code}


def _dec(t):
    return float(t.replace(",", "."))


def _numbers(tokens):
    if not tokens:
        yield []
        return
    # RGPH 2014 prints counts without separators ("1870275"): a 4+-digit
    # token is a whole number on its own.
    if re.fullmatch(r"\d{4,}", tokens[0]):
        for tail in _numbers(tokens[1:]):
            yield [int(tokens[0])] + tail
        return
    for k in range(1, min(len(tokens), 4) + 1):
        head, rest = tokens[:k], tokens[k:]
        if _NUM.match(head[0]) and all(_GRP.match(t) for t in head[1:]):
            for tail in _numbers(rest):
                yield [int("".join(head))] + tail


def _one_count(tokens):
    nums = [n for n in _numbers(tokens) if len(n) == 1]
    return nums[0][0] if len(nums) == 1 else None


def _triple(tokens, tol=0):
    sols = [n for n in _numbers(tokens) if len(n) == 3
            and abs(n[0] + n[1] - n[2]) <= tol]
    return sols[0] if len(sols) == 1 else None


def _pages(path):
    with pdfplumber.open(path) as pdf:
        return [(p.extract_text() or "") for p in pdf.pages]


def _after(pages, caption):
    # The caption also appears in the list of tables; the real table is the
    # occurrence followed by data (a space-grouped or 6+-digit count).
    for t in pages:
        for m in re.finditer(caption, t):
            if re.search(r"\d{1,3} \d{3} \d{3}|\d{6,}", t[m.end():m.end() + 1500]):
                return t[m.end():].splitlines()
    raise ValueError(f"Côte d'Ivoire: {caption!r} not found")


def _page_with(pages, caption):
    """All lines of the page carrying `caption` AND table data -- for a table
    whose caption is typeset BELOW its rows (RGPH 2021 Tableau 3.2)."""
    for t in pages:
        if re.search(caption, t) and re.search(r"\d{1,3} \d{3} \d{3}", t):
            return t.splitlines()
    raise ValueError(f"Côte d'Ivoire: {caption!r} not found with data")


def _clean(name):
    return re.sub(r"-\s+", "-", name.replace("’", "'")).strip()


def _age(label):
    s = label.strip()
    m = re.match(r"^(\d{1,2})-(\d{1,2}) ans$", s)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2))}"
    m = re.match(r"^(\d{1,2}) ans (?:&|et) ?\+$", s)
    if m:
        return f"{int(m.group(1))}+"
    if s.startswith("Non déclaré"):
        return "Non déclaré"
    if s == "Total":
        return "Total"
    return None


def _age_table(lines, period, code, tol=0):
    """Rows 'label M F T RM [...]'; the counts split under M + F = T."""
    out, n = [], 0
    for ln in lines:
        m = re.match(r"^(.*?ans(?: & \+| et \+)?|Non déclaré|Total)\s+(.+)$", ln.strip())
        if not m:
            continue
        age = _age(m.group(1))
        if age is None:
            continue
        toks = m.group(2).split()
        counts = [t for t in toks if "," not in t]
        decs = [t for t in toks if "," in t]
        trip = _triple(counts[:-1] if len(counts) > 3 and counts[-1] == "100" else counts,
                       tol)
        if trip is None:
            raise ValueError(f"Côte d'Ivoire {code}: cannot split {ln!r}")
        n += 1
        for sex, v in zip(("male", "female", "total"), trip):
            out.append(_rec(sex, age, "Total country", period, "count", v,
                            "persons", code))
        if decs:
            out.append(_rec("total", age, "Total country", period, "sex_ratio",
                            _dec(decs[0]), "ratio", code))
        if age == "Total":
            break
    return out, n


def _rgph2021(path):
    pages = _pages(path)
    out, code = [], "CI_RGPH2021_T2.7"
    rows = []
    for ln in _after(pages, r"Tableau 2\.7 : Répartition de la population résidente, rapport"):
        s = ln.strip()
        m = re.match(r"^(\D+?)\s+((?:\d{1,3}\s)*\d{1,3})\s+(\d+,\d)\s+(\d+,\d)\s+[\d ]+$", s)
        if not m:
            if s.startswith("Ensemble"):
                pass
            continue
        name = _clean(m.group(1))
        count = _one_count(m.group(2).split())
        if count is None:
            raise ValueError(f"Côte d'Ivoire T2.7: cannot read {s!r}")
        rows.append((name, count, _dec(m.group(3)), _dec(m.group(4))))
        if name.startswith("Ensemble"):
            break
    names = [r[0] for r in rows]
    if not names or not names[-1].startswith("Ensemble") or len(rows) != 46:
        raise ValueError(f"Côte d'Ivoire T2.7: read {len(rows)} rows ({names[-1:]})")
    # districts: check each equals the sum of the regions that follow it
    i, regions_total = 0, 0
    while i < len(rows) - 1:
        name, count, share, ratio = rows[i]
        if name not in _DISTRICTS_2021:
            raise ValueError(f"Côte d'Ivoire T2.7: expected a district, got {name!r}")
        j, s = i + 1, 0
        while j < len(rows) - 1 and rows[j][0] not in _DISTRICTS_2021:
            s += rows[j][1]
            j += 1
        if name in _AUTONOMOUS:
            out += [_rec("total", "Total", name, 2021, "count", count, "persons", code),
                    _rec("total", "Total", name, 2021, "share", share, "percent", code),
                    _rec("total", "Total", name, 2021, "sex_ratio", ratio, "ratio", code)]
            regions_total += count
        else:
            if s != count:
                raise ValueError(f"Côte d'Ivoire T2.7: {name} {count} != regions {s}")
            out.append(_rec("total", "Total", f"{name} (district)", 2021, "count",
                            count, "persons", code))
            for rn, rc, rs, rr in rows[i + 1:j]:
                out += [_rec("total", "Total", rn, 2021, "count", rc, "persons", code),
                        _rec("total", "Total", rn, 2021, "share", rs, "percent", code),
                        _rec("total", "Total", rn, 2021, "sex_ratio", rr, "ratio", code)]
                regions_total += rc
        i = j
    nat = rows[-1]
    # PUBLISHED: the units sum to 29 389 152 against the printed national
    # 29 389 150. Both kept as printed; this exact gap is pinned so any other
    # (or a corrected table) raises and is looked at.
    if regions_total != nat[1] and (regions_total, nat[1]) != (29389152, 29389150):
        raise ValueError(f"Côte d'Ivoire T2.7: regions sum {regions_total} != {nat[1]}")
    out += [_rec("total", "Total", "Total country", 2021, "count", nat[1], "persons", code),
            _rec("total", "Total", "Total country", 2021, "sex_ratio", nat[3], "ratio", code)]

    ages, n = _age_table(_page_with(pages, r"Tableau 3\.2 : Répartition de la population "
                                           r"résidente par groupe d.âges selon le"),
                         2021, "CI_RGPH2021_T3.2", tol=1)
    if n != 22:
        raise ValueError(f"Côte d'Ivoire T3.2: {n} rows, expected 22")
    tot = [r for r in ages if r["age_group"] == "Total" and r["sex"] == "total"
           and r["measure"] == "count"]
    if tot[0]["value"] != nat[1]:
        raise ValueError("Côte d'Ivoire: T3.2 total disagrees with T2.7")
    # T2.7 already gives the national both-sexes count and sex ratio; T3.2
    # adds everything else, including the national male / female totals.
    return out + [r for r in ages
                  if not (r["age_group"] == "Total" and r["sex"] == "total")]


def _rgph2014(path):
    pages = _pages(path)
    out, code = [], "CI_RGPH2014_T2.3"
    lines = _after(pages, r"Tableau 2\.3 : répartition de la population totale par entité")
    # the table continues onto the next page; gather until ENSEMBLE
    lines = lines + next(t.splitlines() for t in pages
                         if "INDENIE-DJUABLIN" in t and "ENSEMBLE" in t)
    rows, held = [], ""
    for k, ln in enumerate(lines):
        s = ln.strip()
        m = re.match(r"^([A-Z'’ \-]*?)\s*((?:\d{1,3}\s)*\d{1,3})\s+(\d+(?:,\d+)?)$", s)
        if not m:
            held = s if re.fullmatch(r"[A-Z'’ \-]+", s) else ""
            continue
        name = m.group(1).strip()
        if not name:                                  # wrapped: label around numbers
            nxt = lines[k + 1].strip() if k + 1 < len(lines) else ""
            name = f"{held} {nxt}".strip()
        count = _one_count(m.group(2).split())
        if count is None:
            raise ValueError(f"Côte d'Ivoire 2014 T2.3: cannot read {s!r}")
        name = _clean(name)
        if name not in [r[0] for r in rows]:
            rows.append((name, count, _dec(m.group(3))))
        if name == "ENSEMBLE":
            break
    *regs, nat = rows
    if nat[0] != "ENSEMBLE" or sum(r[1] for r in regs) != nat[1] or len(regs) != 33:
        raise ValueError(f"Côte d'Ivoire 2014 T2.3: {len(regs)} units summing to "
                         f"{sum(r[1] for r in regs)} vs {nat}")
    for name, count, share in regs:
        out += [_rec("total", "Total", name, 2014, "count", count, "persons", code),
                _rec("total", "Total", name, 2014, "share", share, "percent", code)]
    ages, n = _age_table(_after(pages, r"Tableau 2\.7\s*: Structure par âge et par sexe"),
                         2014, "CI_RGPH2014_T2.7")
    if n != 19:
        raise ValueError(f"Côte d'Ivoire 2014 T2.7: {n} rows, expected 19")
    if [r["value"] for r in ages if r["age_group"] == "Total" and r["sex"] == "total"
            and r["measure"] == "count"] != [nat[1]]:
        raise ValueError("Côte d'Ivoire 2014: T2.7 total disagrees with T2.3")
    return out + ages


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = _rgph2021(local_path)
    for p in extras or []:
        if "2014" in p:
            rows += _rgph2014(p)
    df = pd.DataFrame(rows)
    key = ["series_type", "sex", "age_group", "geography", "period", "measure"]
    if df.duplicated(key).any():
        raise ValueError(f"Côte d'Ivoire: duplicate keys "
                         f"{df[df.duplicated(key)][key].head(3).values.tolist()}")
    return df
