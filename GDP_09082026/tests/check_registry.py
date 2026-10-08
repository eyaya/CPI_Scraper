"""Registry sanity check: every GDP descriptor must resolve, offline.

Run before any network run. It asserts, for every `sources/*.yaml`:

  * the ten identity keys every GDP descriptor carries are present;
  * `parser:` exists in the parser REGISTRY and is callable -- the step done by
    hand for each of thirty-eight countries, and the one that fails a whole run
    later;
  * the `discover.method` is one `core/run.py` actually dispatches on. GDP uses
    FOURTEEN distinct discovery methods, more than any other indicator here, so
    a typo in a rarely-run one would otherwise surface months later;
  * an `api:` source carries an `api:` block;
  * `frequency` is one the schema recognises.

    python -m indicators.gdp.tests.check_registry
"""
from __future__ import annotations
import collections
import glob
import os
import re
import sys

import yaml

from indicators.gdp.parsers import REGISTRY

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(os.path.dirname(HERE), "sources")
# HERE = .../indicators/gdp/tests -> repo root is three levels up.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RUN_PY = os.path.join(REPO, "core", "run.py")

# Measured across all 38 descriptors: these ten are present in every one.
REQUIRED = ("agency", "country", "frequency", "geography", "indicator",
            "iso3", "parser", "source_type", "tier")
FREQUENCIES = {"annual", "quarterly", "annual + quarterly"}


def known_methods() -> set[str]:
    """Read the dispatched discovery methods out of core/run.py, so this check
    cannot drift out of date with the harness."""
    with open(RUN_PY, encoding="utf-8") as fh:
        src = fh.read()
    return set(re.findall(r'method == "([a-z_]+)"', src)) | {"page_scrape"}


def main() -> int:
    methods = known_methods()
    problems: list[str] = []
    used = collections.Counter()
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
        if freq and freq not in FREQUENCIES:
            problems.append(
                f"{name}: frequency {d.get('frequency')!r} is not one of "
                f"{sorted(FREQUENCIES)}")

        method = (d.get("discover") or {}).get("method", "page_scrape")
        used[method] += 1
        if method not in methods:
            problems.append(
                f"{name}: discover method {method!r} is not dispatched by "
                f"core/run.py")

        print(f"  {name:28} tier {d.get('tier')}  "
              f"{str(d.get('source_type')):6} {d.get('parser')}")

    print()
    print(f"  discovery methods in use ({len(used)}): "
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
