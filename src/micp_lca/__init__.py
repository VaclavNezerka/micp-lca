"""micp_lca – life-cycle assessment toolkit for microbially induced carbonate precipitation (MICP)
based recycling of waste concrete fines and demolition residues.

The package implements an ex-ante (prospective) LCA model following ISO 14040/14044 and
EN 15804+A2 (modules A1–A3, C1–C4, optional D) with the EF 3.1 impact assessment method.
Foreground inventories are generated parametrically from the laboratory protocols published by
the CTU Prague / UCT Prague group (see data/foreground/*.yaml) and scaled to industrial conditions
with a transparent engineering model (data/foreground/scaleup.yaml).

Typical use::

    from micp_lca import load_data, run_scenario
    data = load_data()
    res = run_scenario("GYP_WCFC_single_dose", data)
    print(res.totals())            # impacts per functional unit by EF 3.1 category
    print(res.contributions())     # by life-cycle stage / process group
"""
from __future__ import annotations

from .loaders import DataBundle, load_data
from .inventory import build_inventory, Inventory
from .lcia import assess, Results, run_scenario
from .benchmarks import benchmark_impacts, compare_scenarios

__version__ = "0.1.0"
__all__ = [
    "DataBundle", "load_data", "build_inventory", "Inventory", "assess", "Results",
    "run_scenario", "benchmark_impacts", "compare_scenarios", "__version__",
]
