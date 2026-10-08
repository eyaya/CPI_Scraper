"""Nigeria -- NBS Nigeria Labour Force Survey (NLFS) Annual Report 2023.

Four pooled quarters (October 2022 - November 2023), 15+, the first NLFS round
on the 2023 methodology to publish STATE estimates. The quarterly bulletin the
main descriptor follows carries the national headline only; this report adds:

* Table 6   labour force, employed and unemployed (counts and %) for the nation,
            by sex, education, age group and residence;
* Table 7   the employment-to-population ratio by AGE (its other rows restate
            Table 6 and are checked, not re-emitted);
* Table 12  time-related underemployment by education and sex;
* Table 15  LU2 / LU3 / LU4 for the nation;
* Annex 1   (Tables 18-165) every state's headline -- working-age population,
            labour force, employed, unemployed, outside the labour force,
            time-related underemployment, the 15-24 youth series, NEET, the
            extended labour force and LU2-LU4 -- by sex, residence, education
            and age group.

THE STATE TABLES IN THE BODY ARE CROSS-CHECKS, NOT SOURCES. Tables 5 (working-
age population), 8 (its employment-to-population columns), 11 (unemployment),
13 (underemployment), 16 (LU2-LU4) and Figure 5 (participation, printed as
ordered text labels) give the same state x sex figures as the annex's by-sex
tables; every one is compared with the annex and a disagreement raises. The
annex is read once, so nothing is emitted twice. Figure 5's prose ranks Niger
third at 85.8%; the chart itself prints Niger 87.2 and Plateau 85.8 -- the
chart is what is checked against.

TABLE 6'S AGE BLOCK MEANS SOMETHING ELSE BY "%", and is held to arithmetic.
For every other block, "Employed %" is the employment-to-population ratio and
"Unemployed %" the unemployment rate (Male: 73.7 and 4.7 = 2,062,701 /
43,564,586). In the age block "Employed %" is employed / LABOUR FORCE (15-24:
20,645,254 / 22,728,403 = 90.8, against Table 7's employment ratio of 49.4) and
"Unemployed %" matches neither (15-24 prints 10.1; its own counts give 9.2).
Each row's percentages are therefore emitted only if they reproduce from the
row's counts; the age block's do not, and are refused. Its COUNTS are
consistent (employed + unemployed = labour force) and are kept.

STATE-LEVEL INVARIANT: participation x (100 - unemployment) / 100 must equal
the employment ratio (Abia: 77.0 x 81.3% = 62.6) -- checked for every state
and sex.

ANNEX DEFECTS are the ones labour/parsers/nigeria_labour.py found in the same
tables, and are handled by importing its rules rather than re-deriving them:
Akwa Ibom's T28 misprints its header (refused), Plateau T144 and Rivers T148
wrap digits inside columns (refused, detected by the truncated header words),
T102's caption reads "Kabbi" (Kebbi). The two indicators cannot disagree about
which annex tables are readable.

NOT COLLECTED: discouraged job-seekers (no topic -- they are part of, not the
whole, potential labour force); the underemployed, LU2 and LU4 COUNTS (no
count topic for them); own-use producers; informal employment and the private /
public / social-protection employee rows (labour/'s, or employees only); the
outside-the-labour-force share (no inactivity-rate topic); Figure 18's LU by
sex (chart labels without an order to trust).

CROSS-CHECK (2023): labour force 88,940,861 (76.3%); employed 84,148,566
(72.2%); unemployed 4,792,296 (5.4%); LU2 15.9, LU3 8.3, LU4 18.5; Abia
unemployment 18.7% (M 17.4 / F 19.9); 15-24 employment ratio 49.4.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from indicators.labour.parsers import nigeria_labour as LAB

from . import _common as C

_BASE = dict(survey="Nigeria Labour Force Survey (NLFS) Annual Report 2023",
             period="2023", reference_period="Oct 2022 - Nov 2023",
             frequency="annual", working_age_base="15+",
             series_code="NLFS Annual 2023")
_SEX = ("total", "male", "female")
RESIDUALS: list[tuple] = []      # (table, column, persons) -- see _annex_check


def _emit(out, topic, label, value, measure, unit, definition="not_applicable",
          **ctx):
    if value is None:
        return
    out.append(C.row(topic=topic, definition=definition, series_label=label,
                     value=value, measure=measure, unit=unit, **_BASE, **ctx))


def _close(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol


def _n(tok: str):
    return None if tok in ("-", "") else float(tok.replace(",", ""))


# --------------------------------------------------------------------------
# Annex 1 -- the state tables
# --------------------------------------------------------------------------
# printed head -> (count topic, count definition, pct topic, pct definition,
#                  age_group, series label). None = not collected.
_LF_ROWS = {
    "Working-age population": ("working_age_population", None, None, None, None),
    "Labour force population": ("labour_force", "strict",
                                "labour_force_participation_rate", "strict", None),
    "Employed population": ("employed", None,
                            "employment_to_population_ratio", None, None),
    "Unemployed population": ("unemployed", "strict",
                              "unemployment_rate", "strict", None),
    "Outside the labour force population": ("outside_labour_force", None,
                                            None, None, None),
    "Time-related underemployment": (None, None, "underemployment_rate", None, None),
    "Young population (aged 15-24)": ("working_age_population", None,
                                      None, None, "15-24"),
    "Young labour force (aged 15-24)": ("labour_force", "strict",
                                        "labour_force_participation_rate",
                                        "strict", "15-24"),
    "Young employed (aged 15-24)": ("employed", None,
                                    "employment_to_population_ratio", None, "15-24"),
    "Young unemployed (aged 15-24)": ("unemployed", "strict",
                                      "youth_unemployment_rate", "strict", "15-24"),
    "NEET (aged 15-24)": ("neet_rate", None, "neet_rate", None, "15-24"),
    "Extended labour force": ("labour_force", "broad", None, None, None),
    "LU2": (None, None, "labour_underutilisation_rate", "broad", None),
    "LU3": (None, None, "labour_underutilisation_rate", "broad", None),
    "LU4": (None, None, "labour_underutilisation_rate", "broad", None),
}
# Two heads wrap: "Outside the labour force" / numbers / "population", or the
# head with its numbers on one line and the tail below. Matched by the shortest
# prefix that identifies each row, longest first, the same way labour/ does.
_PREFIX = sorted(((h if h != "Outside the labour force population"
                   else "Outside the labour force", h) for h in _LF_ROWS),
                 key=lambda p: -len(p[0]))


_COUNT_ONLY = {"Working-age population", "Young population (aged 15-24)",
               "Extended labour force"}


def _norm(x: str) -> str:
    return re.sub(r"-\s+", "-", " ".join(x.split()))


def _rejoin(body: list[str]) -> list[str]:
    """Rejoin a head split AROUND its numbers (Kano T96):

        Time-related 860,023 485,545 ...        Young employed (aged 15- 1,733,471 ...
        underemployment                         24)

    The label fragment before the first value plus the wordless line after it
    must spell one of the known heads exactly, or nothing is joined.
    """
    heads = {_norm(h): h for h in _LF_ROWS}
    out, k = [], 0
    while k < len(body):
        s = body[k]
        toks = s.split()
        first = next((i for i, t in enumerate(toks) if LAB._TOK.match(t) and "-" != t
                      and re.search(r"\d", t)), None)
        if first and k + 1 < len(body) and not re.search(r"\d{2},\d", body[k + 1]):
            whole = _norm(" ".join(toks[:first]) + " " + body[k + 1])
            if whole in heads:
                out.append(heads[whole] + " " + " ".join(toks[first:]))
                k += 2
                continue
        out.append(s)
        k += 1
    return out


def _annex_rows(body: list[str], ncol: int, where: str) -> dict:
    body = _rejoin(body)
    got, k = {}, 0
    while k < len(body):
        s = body[k]
        for prefix, head in _PREFIX:
            rest = None
            if s == prefix and k + 1 < len(body):
                rest, k = body[k + 1], k + 1
            elif s.startswith(prefix + " "):
                tail = s[len(prefix):].strip()
                if tail.startswith("population "):       # unwrapped long label
                    tail = tail[len("population "):]
                if tail.split() and LAB._TOK.match(tail.split()[0]):
                    rest = tail
            if rest is None:
                continue
            # "Employed population" must not take "Employed population in
            # agriculture"; "Young population" is not "Young labour force".
            toks = rest.split()
            if not all(LAB._TOK.match(t) for t in toks):
                break
            # Rows with no percentage ("-" in every % cell) sometimes print
            # their counts alone (Zamfara T162's working-age population).
            if len(toks) == ncol and head in _COUNT_ONLY:
                toks = toks + ["-"] * ncol
            # A count that wraps BELOW its row (Abia T19: the rural "outside"
            # count 40,334 sits on the next line, after the percentages)
            # belongs at the end of the count group. Its placement is then
            # proven by _annex_check: each count must reproduce its own %.
            nxt = body[k + 1].split() if k + 1 < len(body) else []
            if (len(toks) < 2 * ncol and nxt and len(toks) + len(nxt) == 2 * ncol
                    and all(LAB._TOK.match(t) and "," in t for t in nxt)):
                at = ncol - len(nxt)
                toks = toks[:at] + nxt + toks[at:]
                k += 1
            # In the AGE tables the 15-24 rows print their percentages for
            # Total and 15-24 and leave the other age columns' % cells blank
            # rather than "-" (Abia T21: 7 counts, 2 percents). Only those
            # rows, and only trailing cells, are padded.
            if ("15-24" in head and ncol < len(toks) < 2 * ncol
                    and len(toks) - ncol >= 2):
                toks = toks + ["-"] * (2 * ncol - len(toks))
            if len(toks) != 2 * ncol:
                raise ValueError(f"{where}: {head!r} reads {toks}")
            if head in got:
                raise ValueError(f"{where}: {head!r} twice")
            got[head] = ([_n(t) for t in toks[:ncol]], [_n(t) for t in toks[ncol:]],
                         [0.15 if "." in t else 0.55 for t in toks[ncol:]])
            break
        k += 1
    missing = set(_LF_ROWS) - set(got)
    if missing:
        raise ValueError(f"{where}: rows not read: {sorted(missing)}")
    return got


def _annex_check(got: dict, where: str):
    """Counts add up and every printed % reproduces from its counts."""
    wap, lf = got["Working-age population"][0], got["Labour force population"][0]
    emp, un = got["Employed population"][0], got["Unemployed population"][0]
    out_lf = got["Outside the labour force population"][0]
    ywap, ylf = got["Young population (aged 15-24)"][0], got["Young labour force (aged 15-24)"][0]
    for j in range(len(wap)):
        if lf[j] is not None and abs((emp[j] or 0) + (un[j] or 0) - lf[j]) > 3:
            raise ValueError(f"{where} col {j}: employed + unemployed != labour force")
        # NBS's labour force + outside-the-labour-force falls SHORT of the
        # working-age population in many tables (Adamawa T22: 1,654 persons;
        # Anambra T30: 15,439, 0.45%), while each share reproduces from its
        # own count -- a published residual, not a misread. It varies by state,
        # so it is RECORDED, not tested; the outside count itself is validated
        # by its own printed share below.
        if wap[j] is not None:
            gap = wap[j] - (lf[j] or 0) - (out_lf[j] or 0)
            if abs(gap) > 3:
                RESIDUALS.append((where, j, gap))
        for head, den in (("Labour force population", wap), ("Employed population", wap),
                          ("Outside the labour force population", wap),
                          ("Unemployed population", lf),
                          ("Young labour force (aged 15-24)", ywap),
                          ("Young employed (aged 15-24)", ywap),
                          ("Young unemployed (aged 15-24)", ylf),
                          ("NEET (aged 15-24)", ywap)):
            n, pc, tol = got[head][0][j], got[head][1][j], got[head][2][j]
            if n is not None and pc is not None and den[j]:
                if abs(100 * n / den[j] - pc) > tol + 0.05:
                    raise ValueError(f"{where} col {j}: {head} {pc}% is not "
                                     f"100 x {n:,.0f} / {den[j]:,.0f}")


def _annex(pages: list[str]) -> tuple[list[dict], dict]:
    blocks = LAB._annex_blocks(pages)
    out, by_sex = [], {}
    RESIDUALS.clear()
    for no, state, dim, body in sorted(blocks, key=lambda b: b[2] != "Sex"):
        dim = dim.replace("Education Level", "Educational Level")
        col, groups = LAB._DIMS[dim]
        where = f"NLFS2023 T{no} {state}"
        top = " ".join(body[:next(n for n, s in enumerate(body)
                                  if s.startswith("Working-age population"))])
        if (no, top) == LAB._T28_HEADER or LAB._WRAPPED_DIGITS & set(top.split()):
            continue                          # refused, as in labour/ (see docstring)
        got = _annex_rows(body, len(groups) + 1, where)
        _annex_check(got, where)
        if dim == "Sex":
            by_sex[state] = got
            ctxs = [{"sex": s} for s in _SEX]
        else:
            # The Total column repeats the by-sex Total: checked, not emitted.
            for head, (cnt, pct, tol) in got.items():
                if not (cnt[0] == by_sex[state][head][0][0]
                        or _close(cnt[0], by_sex[state][head][0][0], 1)):
                    raise ValueError(f"{where}: {head} Total differs from the "
                                     f"by-sex table")
            ctxs = [None] + [({"locality": g.lower(), "locality_label": g}
                              if col == "locality" else {col: g}) for g in groups]
        for head, (ctopic, cdef, ptopic, pdef, age) in _LF_ROWS.items():
            cnt, pct, _ = got[head]
            for j, ctx in enumerate(ctxs):
                if ctx is None:
                    continue
                c = {**ctx, "geography": state}
                if age:
                    if c.get("age_group") not in (None, age):
                        continue          # the youth rows only exist for 15-24
                    if c.get("age_group") == age:
                        # The age table's 15-24 column restates the by-sex
                        # table's youth Total -- same merge key. Checked, not
                        # re-emitted.
                        tot = by_sex[state][head]
                        if not ((cnt[j] == tot[0][0] or _close(cnt[j], tot[0][0], 1))
                                and (pct[j] is None or _close(pct[j], tot[1][0], 0.15))):
                            raise ValueError(f"{where}: {head} 15-24 differs from "
                                             f"the by-sex table")
                        continue
                    c["age_group"] = age
                if ctopic:
                    _emit(out, ctopic, head, cnt[j], "count", "persons",
                          definition=cdef or "not_applicable", **c)
                if ptopic:
                    _emit(out, ptopic, head, pct[j], "rate", "percent",
                          definition=pdef or "not_applicable", **c)
    return out, by_sex


# --------------------------------------------------------------------------
# The body tables
# --------------------------------------------------------------------------

def _lines(pages: list[str], caption: str, stop: str = r"^(Table \d+|Page \|)") -> list[str]:
    rx = re.compile(caption)
    for i, text in enumerate(pages):
        m = rx.search(text)
        if m and not re.search(r"\.{4}", text[m.end():m.end() + 80].split("\n")[0]):
            lines = text[m.end():].splitlines()[1:]
            # a table may run onto the next page
            lines += (pages[i + 1].splitlines() if i + 1 < len(pages) else [])
            out = []
            for ln in lines:
                if re.match(stop, ln.strip()) and out:
                    if ln.strip().startswith("Page |"):
                        continue
                    break
                out.append(ln.strip())
            return out
    raise ValueError(f"NLFS2023: {caption!r} not found")


def _state_rows(lines: list[str], states: set, width: int, where: str) -> dict:
    upper = {s.upper(): s for s in states}
    rx = re.compile(r"^(" + "|".join(sorted(map(re.escape, upper), key=len,
                                            reverse=True)) + r")\s+(.*)$")
    got = {}
    for ln in lines:
        m = rx.match(ln)
        if not m or upper[m.group(1)] in got:
            continue
        vals = [_n(t) for t in m.group(2).split()]
        if len(vals) < width:
            raise ValueError(f"{where}: {ln!r}")
        got[upper[m.group(1)]] = vals[:width]
    if set(got) != states:
        raise ValueError(f"{where}: states read {len(got)}, missing "
                         f"{sorted(states - set(got))}")
    return got


def _cross_check(pages: list[str], by_sex: dict):
    """The body's state tables against the annex's by-sex tables."""
    states = set(by_sex)
    checks = [
        (r"Table 5: Working Age Population by State and Sex", 3,
         "Working-age population", 0, 1),
        (r"Table 8: Status in Employment by Sex", 3, "Employed population", 1, 0.05),
        (r"Table 11: Unemployment Rate by State and Sex", 3,
         "Unemployed population", 1, 0.05),
        (r"Table 13: Underemployment Rate by State and Sex", 3,
         "Time-related underemployment", 1, 0.05),
    ]
    for cap, width, head, part, tol in checks:
        rows = _state_rows(_lines(pages, cap), states, width, cap)
        for st, vals in rows.items():
            ann = by_sex[st][head][part]
            for j in range(3):
                if vals[j] is not None and ann[j] is not None and abs(vals[j] - ann[j]) > tol:
                    raise ValueError(f"{cap} {st} col {j}: {vals[j]} != annex {ann[j]}")
    t16 = _state_rows(_lines(pages, r"Table 16: Labour Underutilization by State"),
                      states, 3, "T16")
    fig5 = _state_rows(_lines(pages, r"LABOUR FORCE PARTICIPATION RATE BY STATE",
                              stop=r"^Figure 5"), states, 1, "Figure 5")
    for st in states:
        for j, h in enumerate(("LU2", "LU3", "LU4")):
            if not _close(t16[st][j], by_sex[st][h][1][0], 0.05):
                raise ValueError(f"T16 {st} {h}: {t16[st][j]} != annex")
        lfpr = by_sex[st]["Labour force population"][1]
        if not _close(fig5[st][0], lfpr[0], 0.05):
            raise ValueError(f"Figure 5 {st}: {fig5[st][0]} != annex {lfpr[0]}")
        for j in range(3):
            ur = by_sex[st]["Unemployed population"][1][j]
            epr = by_sex[st]["Employed population"][1][j]
            if None not in (lfpr[j], ur, epr) and abs(lfpr[j] * (100 - ur) / 100 - epr) > 0.15:
                raise ValueError(f"{st} col {j}: participation x (1 - unemployment) "
                                 f"!= employment ratio")


_T6_DIMS = {"Sex": ("sex", {"Male": "male", "Female": "female"}),
            "Education Level": ("education", None),
            "Age-Group": ("age_group", None),
            "Place of Residence": ("locality", {"Urban": "urban", "Rural": "rural"})}


def _table_6_7(pages: list[str]) -> list[dict]:
    out = []
    dim = None
    t6 = {}
    for ln in _lines(pages, r"Table 6: Population in the Labour Force, Employed"):
        if ln in _T6_DIMS or ln == "National":
            dim = ln if ln != "National" else None
        m = re.match(r"^(National|[A-Za-z][A-Za-z -]*?|\d{2}-\d{2}|65\+)\s+"
                     r"([\d,]+)\s+([\d.]+)\s+([\d,]+)\s+([\d.]+)\s+([\d,]+)\s+([\d.]+)$", ln)
        if not m:
            continue
        lab = m.group(1)
        lf, lfp, e, ep, u, up = (_n(m.group(i)) for i in range(2, 8))
        t6[(dim, lab)] = (lf, lfp, e, ep, u, up)
    if len(t6) != 1 + 2 + 5 + 6 + 2:
        raise ValueError(f"NLFS2023 T6: read {len(t6)} rows")
    for (dim, lab), (lf, lfp, e, ep, u, up) in t6.items():
        if abs(e + u - lf) > 3:
            raise ValueError(f"T6 {lab}: employed + unemployed != labour force")
        ctx = {}
        if dim:
            col, vmap = _T6_DIMS[dim]
            if col == "locality":
                ctx = {"locality": vmap[lab], "locality_label": lab}
            else:
                ctx = {col: vmap[lab] if vmap else lab}
        _emit(out, "labour_force", "Labour force population", lf, "count",
              "persons", definition="strict", **ctx)
        _emit(out, "employed", "Employed population", e, "count", "persons", **ctx)
        _emit(out, "unemployed", "Unemployed population", u, "count", "persons",
              definition="strict", **ctx)
        # Each % only where it reproduces from the row's own counts: ep / lfp
        # must equal e / lf (so ep is the employment ratio on the same base)
        # and up must equal u / lf. The age block fails both and is refused.
        rates_ok = (abs(ep / lfp - e / lf) < 0.003 and abs(100 * u / lf - up) < 0.06)
        if dim == "Age-Group":
            if rates_ok:
                raise ValueError(f"T6 {lab}: the age block's % now reproduce from "
                                 f"its counts -- re-read it and collect them")
            continue
        if not rates_ok:
            raise ValueError(f"T6 {lab}: % do not reproduce from the counts")
        _emit(out, "labour_force_participation_rate", "Labour force population",
              lfp, "rate", "percent", definition="strict", **ctx)
        _emit(out, "employment_to_population_ratio", "Employed population", ep,
              "rate", "percent", **ctx)
        _emit(out, "unemployment_rate", "Unemployed population", up, "rate",
              "percent", definition="strict", **ctx)
    # Table 7: the employment ratio by AGE; its other rows must equal Table 6.
    dim, seen = None, 0
    for ln in _lines(pages, r"Table 7: Employment to Population Ratio"):
        if ln in _T6_DIMS:
            dim = ln
        m = re.match(r"^([A-Za-z][A-Za-z -]*?|\d{2}-\d{2}|65\+)\s+([\d,]+)\s+([\d.]+)$", ln)
        if not m or dim is None:
            continue
        lab, e, r = m.group(1), _n(m.group(2)), _n(m.group(3))
        seen += 1
        if dim == "Age-Group":
            if abs(e - t6[(dim, lab)][2]) > 1:
                raise ValueError(f"T7 {lab}: employed differs from Table 6")
            _emit(out, "employment_to_population_ratio",
                  "Employment to Population Ratio", r, "rate", "percent",
                  age_group=lab)
        elif abs(r - t6[(dim, lab)][3]) > 0.05:
            raise ValueError(f"T7 {lab}: ratio {r} != Table 6's {t6[(dim, lab)][3]}")
    if seen != 15:
        raise ValueError(f"NLFS2023 T7: read {seen} rows")
    return out


def _table_12_15(pages: list[str]) -> list[dict]:
    out = []
    n = 0
    for ln in _lines(pages, r"Table 12: Time-Related Underemployment Rate by Level"):
        m = re.match(r"^(No Education|Primary|Secondary|Post-Secondary|Post-Graduate)"
                     r"\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)$", ln)
        if m:
            n += 1
            for s, v in zip(_SEX, m.groups()[1:]):
                _emit(out, "underemployment_rate", "Time-related underemployment",
                      _n(v), "rate", "percent", education=m.group(1), sex=s)
    if n != 5:
        raise ValueError(f"NLFS2023 T12: read {n} rows")
    text = "\n".join(_lines(pages, r"Table 15: Labour Underutilization \(LU1 - LU4\)",
                            stop=r"^Disaggregating"))
    rates = re.findall(r"^(\d+\.\d)%$", text, re.M)
    if len(rates) != 4 or rates[0] != "5.4":
        raise ValueError(f"NLFS2023 T15: rates {rates}")
    for lab, v in zip(("LU2", "LU3", "LU4"), rates[1:]):
        _emit(out, "labour_underutilisation_rate", lab, float(v), "rate",
              "percent", definition="broad")
    return out


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        pages = LAB._pages(pdf)
    annex, by_sex = _annex(pages)
    _cross_check(pages, by_sex)
    rows = _table_6_7(pages) + _table_12_15(pages) + annex
    return pd.DataFrame(rows)
