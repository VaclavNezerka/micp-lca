"""Benchmark products and scenario comparison.

Benchmarks are defined in ``data/foreground/scenarios.yaml`` (``benchmarks:``) either as a
background dataset (ÖKOBAUDAT EPD-type datasets, per kg) or as fixed impact vectors taken from
published EPDs / LCAs (e.g. the WCF–OPC foamed block of Nežerka et al. 2023). Their end-of-life is
harmonised with the biocemented blocks (demolition, 50 km transport, inert landfill), unless the
dataset already contains modules C1–C4 (``eol_modules_from_dataset``).

``compare_with_status_quo`` implements a system-expansion comparison: a biocemented block that
absorbs *m* kg of waste fines is compared with the basket "conventional block + landfilling of the
same *m* kg of fines" so that both systems deliver the same functions (a block and the disposal of
the waste).
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .lcia import Results, background_factor
from .loaders import DataBundle


def _eol_per_kg(data: DataBundle, category: str, electricity: str = "electricity_CZ_lv") -> float:
    """Harmonised end-of-life impacts per kg of block: C1 (2 kWh/t), C2 (50 km truck), C4 (inert landfill)."""
    c1 = 0.002 * background_factor(data.background[electricity], category, None)
    c2 = 0.05 * background_factor(data.background["transport_truck"], category, None)
    c4 = background_factor(data.background["landfill_inert"], category, "C4")
    vals = [v for v in (c1, c2, c4) if v == v]  # drop NaN
    return sum(vals) if vals else float("nan")


def benchmark_impacts(name: str, data: DataBundle, *, functional_unit: str = "kg_product",
                      include_eol: bool = True) -> pd.Series:
    """Impacts of a benchmark product per functional unit (kg or m3 of product, or m3·MPa)."""
    b = data.scenarios["benchmarks"][name]
    cats = data.category_codes
    per_kg = pd.Series({c: float("nan") for c in cats}, dtype=float)
    density = float(b.get("bulk_density_kg_m3", 1.0))
    if "background_process" in b:
        proc = data.background[b["background_process"]]
        for c in cats:
            per_kg[c] = background_factor(proc, c, None)
        if include_eol:
            if b.get("eol_modules_from_dataset"):
                for c in cats:
                    eol = proc.eol_factor(c)
                    per_kg[c] = per_kg[c] + (eol if eol == eol else 0.0)
            else:
                for c in cats:
                    per_kg[c] = per_kg[c] + _eol_per_kg(data, c)
    elif "fixed_impacts_per_t" in b:      # already includes C1–C4 (NEZERKA2023LCA convention)
        for c, v in b["fixed_impacts_per_t"].items():
            per_kg[c] = float(v) / 1000.0
        if not include_eol and "fixed_impacts_A1A3_per_t" in b:
            for c, v in b["fixed_impacts_A1A3_per_t"].items():
                per_kg[c] = float(v) / 1000.0
    elif "fixed_impacts_per_m3" in b:
        for c, v in b["fixed_impacts_per_m3"].items():
            per_kg[c] = float(v) / density
        if include_eol:
            for c in cats:
                if per_kg[c] == per_kg[c]:
                    per_kg[c] = per_kg[c] + _eol_per_kg(data, c)
    else:
        raise ValueError(f"benchmark '{name}' has no impact definition")
    if functional_unit == "kg_product":
        return per_kg
    if functional_unit == "m3_product":
        return per_kg * density
    if functional_unit == "m3_MPa":
        return per_kg * density / float(b["fc_MPa"])
    raise ValueError(f"functional unit '{functional_unit}' not supported for benchmarks")


def compare_scenarios(results: list[Results], data: DataBundle, benchmarks: list[str] | None = None,
                      category: str = "GWP-total", functional_unit: str = "kg_product") -> pd.DataFrame:
    """Table comparing scenario results (A1–A3 and A1–A3+C) with benchmark products."""
    rows: list[dict[str, Any]] = []
    for r in results:
        a13 = float(r.totals(("A1", "A2", "A3"))[category])
        c = float(r.totals(("C1", "C2", "C3", "C4"))[category])
        rows.append({"item": r.scenario, "type": "scenario", f"{category} A1-A3": a13, f"{category} A1-A3+C": a13 + c,
                     "fc_MPa": r.inventory.fc_MPa, "bulk_density_kg_m3": r.inventory.bulk_density_kg_m3,
                     "coverage": r.coverage.get(category)})
    for b in benchmarks or list(data.scenarios.get("benchmarks", {})):
        try:
            v13 = benchmark_impacts(b, data, functional_unit=functional_unit, include_eol=False)[category]
            vc = benchmark_impacts(b, data, functional_unit=functional_unit, include_eol=True)[category]
        except (ValueError, KeyError):
            continue
        bd = data.scenarios["benchmarks"][b]
        rows.append({"item": b, "type": "benchmark", f"{category} A1-A3": float(v13), f"{category} A1-A3+C": float(vc),
                     "fc_MPa": bd.get("fc_MPa"), "bulk_density_kg_m3": bd.get("bulk_density_kg_m3"), "coverage": 1.0})
    return pd.DataFrame(rows).set_index("item")


def compare_with_status_quo(result: Results, data: DataBundle, benchmark: str = "AAC_block_ODB",
                            category: str = "GWP-total") -> dict[str, float]:
    """System expansion: biocemented block vs. (benchmark block + landfilling of the waste fines it absorbs).

    All values per kg of product (A1–A3 + C1–C4).
    """
    r = result
    fu = r.fu_factor
    solids_per_kg_product = 1.0 / r.inventory.product_kg_per_kg_solids if r.functional_unit == "kg_product" else fu
    bio = float(r.totals(("A1", "A2", "A3", "C1", "C2", "C3", "C4"))[category])
    bench = float(benchmark_impacts(benchmark, data, include_eol=True)[category])
    landfill = solids_per_kg_product * background_factor(data.background["landfill_inert"], category, "C4")
    return {"biocemented_block": bio, f"{benchmark}": bench, "landfill_of_absorbed_fines": landfill,
            "status_quo_basket": bench + landfill, "difference_bio_minus_status_quo": bio - (bench + landfill)}
