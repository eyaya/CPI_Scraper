"""Parser registry for MPI sources.

One module per country, as in every other indicator in this repo: each
`<country>_mpi.py` holds that country's declarative table layout and exposes a
`parse`, built over the shared engine in `mpi_tables.py` (with the number and row
helpers in `_common.py` and the shared column vocabularies in `_vocab.py`).

Ghana is the exception that earns its own hand-written reader: it is the only
African NSO exposing its MPI through a machine-readable API (PxWeb), so
`ghana_pxweb_mpi` is a Tier-1 parser rather than a PDF layout. `ghana_report_mpi`
covers the separate GSS report edition.

Adding a country: write `parsers/<country>_mpi.py`, import and register it here,
and add `sources/<country>.yaml`. A country whose MPI exists only on an
aggregator's server (OPHI, UNDP, MPPN) gets no entry -- see PENDING.md for the
list and the reason.
"""
from . import ghana_pxweb_mpi
from . import angola_mpi
from . import botswana_mpi
from . import burkina_faso_mpi
from . import egypt_mpi
from . import ghana_report_mpi
from . import guinea_mpi
from . import madagascar_mpi
from . import mali_mpi
from . import mauritius_mpi
from . import morocco_mpi
from . import nigeria_mpi
from . import rwanda_mpi
from . import seychelles_mpi
from . import sierra_leone_mpi
from . import somalia_mpi
from . import south_africa_mpi
from . import uganda_mpi
from . import senegal_mpi
from . import mauritania_mpi
from . import djibouti_mpi
from . import sierra_leone_2023_mpi

REGISTRY = {
    # --- Tier 1: API ------------------------------------------------------
    "ghana_pxweb_mpi": ghana_pxweb_mpi.parse,

    # --- Tier 3: report PDF, one layout module per country ----------------
    "angola_mpi": angola_mpi.parse,
    "botswana_mpi": botswana_mpi.parse,
    "burkina_faso_mpi": burkina_faso_mpi.parse,
    "egypt_mpi": egypt_mpi.parse,
    "ghana_report_mpi": ghana_report_mpi.parse,
    "guinea_mpi": guinea_mpi.parse,
    "madagascar_mpi": madagascar_mpi.parse,
    "mali_mpi": mali_mpi.parse,
    "mauritius_mpi": mauritius_mpi.parse,
    "morocco_mpi": morocco_mpi.parse,
    "nigeria_mpi": nigeria_mpi.parse,
    "rwanda_mpi": rwanda_mpi.parse,
    "seychelles_mpi": seychelles_mpi.parse,
    "sierra_leone_mpi": sierra_leone_mpi.parse,
    "somalia_mpi": somalia_mpi.parse,
    "south_africa_mpi": south_africa_mpi.parse,
    "uganda_mpi": uganda_mpi.parse,
    # ANSD/OPCV Senegal national IPM (ESPS-II 2011, rapport national, version
    # provisoire 2018): 5 dims / 25 ind., k = 32%; H, A, M0 with 95% CIs for 14
    # regions + strata; by sex, age and education of the household head.
    "senegal_mpi": senegal_mpi.parse,
    # ANSADE Mauritania IPM-M (EPCV 2019) from the 2024 sociodemographic yearbook
    # T6.7-6.9 (text layer): national/urban/rural, 13 wilayas, ages 0-4 and 5-17,
    # with CIs; 4 dims / 19 ind., k = 38% (method from ANSADE's own brief).
    "mauritania_mpi": mauritania_mpi.parse,
    # INSTAD Djibouti RGPH-3 2024 Thématique 16: census IPM headcount (k=1/3,
    # 3 dims/3 ind., person) -- national, 6 régions, milieu, 20 age groups,
    # 29 préfectures/arrondissements. Only H is published.
    "djibouti_mpi": djibouti_mpi.parse,
    # Stats SL 'Multidimensional Poverty in Sierra Leone 2023' (DHS 2019), on
    # statistics.sl: national, rural/urban, regions, 16 districts, age, head's
    # education, with CIs; 2017 comparable-measure re-estimate kept apart.
    "sierra_leone_2023_mpi": sierra_leone_2023_mpi.parse,
}

# The per-country layouts, keyed by country, for the offline checks in
# `tests/` (and for anyone wanting to inspect a layout without importing its
# module by name). Built from the modules above so it cannot drift from them.
LAYOUTS = {
    name[:-4]: mod.LAYOUT
    for name, mod in list(globals().items())
    if name.endswith("_mpi") and hasattr(mod, "LAYOUT")
}
