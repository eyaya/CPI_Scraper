"""Registry sanity check for the poverty package: every descriptor must resolve
offline before anyone spends a network run on it.

For every `sources/*.yaml`: the identity keys are present, `parser:` is in the
REGISTRY, the discovery method is one core/run.py dispatches on -- and,
specific to poverty, the layout DECLARES ITS LINE: line_type, line_level,
line_name, survey and welfare aggregate, because a headcount without its line
is not interpretable. An international line must name its PPP basis.

    python -m indicators.poverty.tests.check_registry
"""
from __future__ import annotations
import glob
import os
import re
import sys

import yaml

from indicators.poverty import schema
from indicators.poverty.parsers import LAYOUTS, REGISTRY

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(os.path.dirname(HERE), "sources")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RUN_PY = os.path.join(REPO, "core", "run.py")

REQUIRED = ("country", "iso3", "indicator", "tier", "source_type", "agency",
            "frequency", "parser")
LINE_KEYS = ("survey", "welfare_aggregate", "line_type", "line_level", "line_name")


def known_methods() -> set[str]:
    src = open(RUN_PY, encoding="utf-8").read()
    return set(re.findall(r'method == "([a-z_]+)"', src)) | {"page_scrape"}


def _cells(layout: dict):
    yield "layout", layout
    for i, t in enumerate(layout.get("tables", [])):
        for j, c in enumerate(t.get("columns", [])):
            yield f"tables[{i}].columns[{j}]", c


def main() -> int:
    methods = known_methods()
    problems: list[str] = []
    files = sorted(glob.glob(os.path.join(SOURCES, "*.yaml")))
    if not files:
        print(f"no descriptors found in {SOURCES}")
        return 1
    for path in files:
        name = os.path.basename(path)
        d = yaml.safe_load(open(path, encoding="utf-8"))
        for key in REQUIRED:
            if key not in d:
                problems.append(f"{name}: missing required key {key!r}")
        if d.get("indicator") != "Poverty":
            problems.append(f"{name}: indicator must be 'Poverty' (it names the out/ file)")
        parser = d.get("parser")
        if parser not in REGISTRY:
            problems.append(f"{name}: parser {parser!r} is not in the REGISTRY")
        method = (d.get("discover") or {}).get("method", "page_scrape")
        if method not in methods:
            problems.append(f"{name}: discover method {method!r} is not dispatched by core/run.py")
        layout = LAYOUTS.get(parser)
        if layout is None:
            problems.append(f"{name}: no LAYOUT registered for parser {parser!r}")
            continue
        for key in LINE_KEYS:
            if not layout.get(key):
                problems.append(f"{name}: layout declares no default {key!r} -- a poverty "
                                f"rate cannot be interpreted without its line and survey")
        if not (layout.get("period") or layout.get("period_patterns")):
            problems.append(f"{name}: layout has neither `period` nor `period_patterns`")
        for where, c in _cells(layout):
            for key, allowed in (("line_type", schema.LINE_TYPES), ("line_level", schema.LINE_LEVELS),
                                 ("welfare_aggregate", schema.WELFARE), ("metric", schema.METRICS),
                                 ("topic", schema.TOPICS)):
                if key in c and c[key] not in allowed:
                    problems.append(f"{name}: {where}: unknown {key} {c[key]!r}")
            lt = c.get("line_type")
            if lt == "international" and not re.search(r"ppp|ppa|\$", str(c.get("line_name", "")), re.I):
                problems.append(f"{name}: {where}: an international line must name its PPP "
                                f"basis in line_name (US$2.15 2017 PPP vs US$3.00 2021 PPP)")
        print(f"  {name:26} tier {d.get('tier')}  {d.get('source_type'):5} {parser}")
    print()
    if problems:
        print(f"FAILED ({len(problems)}):")
        for p in problems:
            print("  -", p)
        return 1
    print(f"{len(files)} descriptor(s) OK -- every parser resolves, every discovery "
          f"method is known, and every layout declares its poverty line.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
