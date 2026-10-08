"""Registry sanity check: every CPI descriptor must resolve, offline.

Run before any network run. It asserts, for every `sources/*.yaml`:

  * the required identity keys are present;
  * `parser:` exists in the parser REGISTRY and is callable -- the step done by
    hand for each of fifty-two countries, and the one that fails a whole run
    later;
  * the `discover.method` is one `core/run.py` actually dispatches on (an
    unknown method is a silent ValueError a whole run later);
  * `expect_divisions`, where a descriptor sets it, is a sane count.

    python -m indicators.cpi.tests.check_registry
"""
from __future__ import annotations
import glob
import os
import re
import sys

import yaml

from indicators.cpi import coicop
from indicators.cpi.parsers import REGISTRY

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(os.path.dirname(HERE), "sources")
# HERE = .../indicators/cpi/tests -> repo root is three levels up.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RUN_PY = os.path.join(REPO, "core", "run.py")

REQUIRED = ("country", "iso3", "indicator", "source_type", "parser")


def known_methods() -> set[str]:
    """Read the dispatched discovery methods out of core/run.py, so this check
    cannot drift out of date with the harness."""
    with open(RUN_PY, encoding="utf-8") as fh:
        src = fh.read()
    return set(re.findall(r'method == "([a-z_]+)"', src)) | {"page_scrape"}


def main() -> int:
    methods = known_methods()
    problems: list[str] = []
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

        method = d.get("discover", {}).get("method", "page_scrape")
        if method not in methods:
            problems.append(
                f"{name}: discover method {method!r} is not dispatched by "
                f"core/run.py")

        # A descriptor may lower the division floor where an NSO publishes
        # fewer (a central-bank fallback with all-items only), but a value
        # above the COICOP table is always a typo.
        ed = d.get("expect_divisions")
        if ed is not None and not (0 <= ed <= coicop.N_DIVISIONS):
            problems.append(
                f"{name}: expect_divisions {ed} outside 0..{coicop.N_DIVISIONS}")

        print(f"  {name:28} {str(d.get('source_type')):5} {d.get('parser')}")

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
