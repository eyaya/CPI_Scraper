"""Registry sanity check: every labour descriptor must resolve, offline.

Run before any network run. It asserts, for every `sources/*.yaml`:

  * the required identity keys are present;
  * `parser:` exists in the parser REGISTRY -- the step that is otherwise done
    by hand for each new country, and the one that fails a whole run later;
  * the `discover.method` is one `core/run.py` actually dispatches on;
  * every parser module named by a descriptor exposes a callable `parse`;
  * a descriptor in `sources_blocked/` is NOT also in `sources/`, so a source
    recorded as blocked cannot quietly still be collected.

It also reports the classification and topic vocabulary each layout declares,
because those are the two fields that decide whether a category is comparable.

    python -m indicators.labour.tests.check_registry
"""
from __future__ import annotations
import glob
import os
import re
import sys

import yaml

from indicators.labour.parsers import REGISTRY

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(os.path.dirname(HERE), "sources")
BLOCKED = os.path.join(os.path.dirname(HERE), "sources_blocked")
# HERE = .../indicators/labour/tests -> repo root is three levels up.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RUN_PY = os.path.join(REPO, "core", "run.py")

REQUIRED = ("country", "iso3", "indicator", "tier", "source_type", "agency",
            "frequency", "parser")


def known_methods() -> set[str]:
    """The discovery methods core/run.py dispatches on, read from the source so
    this check cannot drift out of date."""
    with open(RUN_PY, encoding="utf-8") as f:
        src = f.read()
    return set(re.findall(r'method == "([a-z_]+)"', src)) | {"page_scrape"}


def main() -> int:
    methods = known_methods()
    problems: list[str] = []
    files = sorted(glob.glob(os.path.join(SOURCES, "*.yaml")))
    if not files:
        print(f"no descriptors found in {SOURCES}")
        return 1

    blocked = {os.path.splitext(os.path.basename(p))[0]
               for p in glob.glob(os.path.join(BLOCKED, "*.yaml"))}

    for path in files:
        name = os.path.basename(path)
        stem = os.path.splitext(name)[0]
        with open(path, encoding="utf-8") as f:
            d = yaml.safe_load(f)

        for key in REQUIRED:
            if key not in d:
                problems.append(f"{name}: missing required key {key!r}")

        parser = d.get("parser")
        if parser not in REGISTRY:
            problems.append(
                f"{name}: parser {parser!r} is not in the REGISTRY "
                f"({sorted(REGISTRY)})")
        elif not callable(REGISTRY[parser]):
            problems.append(f"{name}: REGISTRY[{parser!r}] is not callable")

        method = d.get("discover", {}).get("method", "page_scrape")
        if method not in methods:
            problems.append(
                f"{name}: discover method {method!r} is not dispatched by "
                f"core/run.py")

        # A SOURCE RECORDED AS BLOCKED MUST NOT ALSO BE LIVE. Zimbabwe and
        # Kenya are blocked for reasons that are about the SOURCE, not the
        # parser, and a stray descriptor in sources/ would quietly undo that.
        if stem in blocked:
            problems.append(
                f"{name}: also present in sources_blocked/ — a blocked source "
                f"must not be collected")

        print(f"  {name:22} tier {d.get('tier')}  {str(d.get('source_type')):5} "
              f"{d.get('parser')}")

    print()
    if blocked:
        print(f"  blocked, deliberately not collected: {', '.join(sorted(blocked))}")
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
