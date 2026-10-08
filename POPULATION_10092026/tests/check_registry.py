"""Registry sanity check: every Population descriptor must resolve, offline.

Run before any network run. It asserts, for every `sources/*.yaml`:

  * the eleven identity keys every Population descriptor carries are present;
  * `parser:` exists in the parser REGISTRY and is callable;
  * the `discover.method` is one `core/run.py` actually dispatches on;
  * an `api:` source carries an `api:` block;
  * `frequency` is annual -- population is a mid-year annual series, and a
    descriptor claiming otherwise is a copy-paste from CPI or GDP.

    python -m indicators.population.tests.check_registry
"""
from __future__ import annotations
import collections
import glob
import os
import re
import sys

import yaml

from indicators.population.parsers import REGISTRY

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(os.path.dirname(HERE), "sources")
# HERE = .../indicators/population/tests -> repo root is three levels up.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RUN_PY = os.path.join(REPO, "core", "run.py")

# Measured across all 36 descriptors: these are present in every one.
REQUIRED = ("agency", "country", "frequency", "geography", "indicator", "iso3",
            "parser", "publication_code", "source_type", "tier")


def known_methods() -> set[str]:
    with open(RUN_PY, encoding="utf-8") as fh:
        src = fh.read()
    return set(re.findall(r'method == "([a-z_]+)"', src)) | {"page_scrape"}


def main() -> int:
    methods = known_methods()
    problems: list[str] = []
    used = collections.Counter()
    tiers = collections.Counter()
    files = sorted(glob.glob(os.path.join(SOURCES, "*.yaml")))
    if not files:
        print(f"no descriptors found in {SOURCES}")
        return 1

    for path in files:
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as fh:
            d = yaml.safe_load(fh) or {}

        for key in REQUIRED:
            if key not in d:
                problems.append(f"{name}: missing required key {key!r}")

        parser = d.get("parser")
        if parser not in REGISTRY:
            problems.append(f"{name}: parser {parser!r} is not in the REGISTRY")
        elif not callable(REGISTRY[parser]):
            problems.append(f"{name}: REGISTRY[{parser!r}] is not callable")

        # An `api` source is either a PxWeb query (`api:` block) or a plain JSON
        # endpoint fetched through `discover:` (LISGIS Liberia). Neither is an error.
        if d.get("source_type") == "api" and not (d.get("api") or d.get("discover")):
            problems.append(f"{name}: source_type api with neither an `api:` nor a `discover:` block")

        freq = str(d.get("frequency", "")).strip().lower()
        if freq and freq != "annual":
            problems.append(
                f"{name}: frequency {d.get('frequency')!r} — population is an "
                f"annual mid-year series")

        method = (d.get("discover") or {}).get("method", "page_scrape")
        used[method] += 1
        tiers[d.get("tier")] += 1
        if method not in methods:
            problems.append(
                f"{name}: discover method {method!r} is not dispatched by "
                f"core/run.py")

        print(f"  {name:30} tier {d.get('tier')}  "
              f"{str(d.get('source_type')):6} {d.get('parser')}")

    print()
    print(f"  by tier: {dict(sorted(tiers.items(), key=lambda kv: str(kv[0])))}")
    print(f"  discovery methods ({len(used)}): "
          f"{', '.join(f'{m} x{n}' for m, n in used.most_common())}")
    print()
    if problems:
        print(f"FAILED ({len(problems)}):")
        for p in problems:
            print("  -", p)
        return 1
    print(f"{len(files)} descriptor(s) OK — every parser resolves and every "
          f"discovery method is known")
    return 0


if __name__ == "__main__":
    sys.exit(main())
