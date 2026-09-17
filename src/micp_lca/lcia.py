"""Life-cycle impact assessment with the EF 3.1 method (EN 15804+A2 indicators).

Background flows are characterised with the per-unit impact factors stored in the background
database (ÖKOBAUDAT EN 15804+A2 datasets, literature values); direct elementary flows of the
foreground (CO2, NH3, NH4+, N2O, Cl-, residual organics, water) are characterised with the
official EF 3.1 characterisation factors (``data/lcia``).

Data gaps are never filled silently: for every impact category the *coverage* (share of the
background flows for which a factor exists) is reported alongside the results.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .inventory import Inventory, build_inventory
from .loaders import BackgroundProcess, DataBundle

PRODUCTION_MODULES_EXCLUDE = ("C1", "C2", "C3", "C4", "D", "B1")
FU_LABELS = {
    "kg_product": "1 kg of dry biocemented product",
    "m3_product": "1 m3 of biocemented product",
    "kg_solids": "1 kg of dry waste fines processed",
    "kg_caco3_precipitated": "1 kg of microbially precipitated CaCO3",
    "m3_MPa": "1 m3 of product per MPa of compressive strength (strength-normalised)",
}


def background_factor(proc: BackgroundProcess, category: str, bg_module: str | None) -> float:
    """Impact factor of a background dataset for one category (NaN if unavailable).

    ``bg_module`` selects one declared module (e.g. ``C4`` for landfilling); otherwise the
    production modules of the dataset are summed (see :meth:`BackgroundProcess.production_modules`).
    """
    return proc.factor(category, bg_module)


@dataclass
class Results:
    scenario: str
    functional_unit: str
    fu_factor: float                 # multiply per-kg-solids amounts by this to get per FU
    contrib: pd.DataFrame            # one row per flow: module, group, kind, key, amount, unit, <categories>
    categories: list[str]
    units: dict[str, str]
    coverage: dict[str, float]       # category -> GWP-weighted share of background flows with any factor (native or proxy)
    coverage_native: dict[str, float]  # category -> share with a native (non-proxy) factor
    missing: dict[str, list[str]]    # category -> background process ids lacking a factor
    proxy_filled: dict[str, list[str]]  # category -> background process ids whose factor is a scaled proxy profile
    inventory: Inventory
    meta: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ aggregations
    def totals(self, modules: tuple[str, ...] | None = None) -> pd.Series:
        df = self.contrib if modules is None else self.contrib[self.contrib["module"].isin(modules)]
        return df[self.categories].sum()

    def by_module(self) -> pd.DataFrame:
        return self.contrib.groupby("module")[self.categories].sum().reindex(
            [m for m in ("A1", "A2", "A3", "C1", "C2", "C3", "C4", "D") if m in set(self.contrib["module"])])

    def by_group(self) -> pd.DataFrame:
        return self.contrib.groupby("group")[self.categories].sum().sort_values("GWP-total", ascending=False)

    def contributions(self, category: str = "GWP-total") -> pd.DataFrame:
        g = self.contrib.groupby(["module", "group"])[[category]].sum()
        total = g[category].sum()
        g["share"] = g[category] / total if total else float("nan")
        return g.sort_values(category, ascending=False)

    def gwp(self, modules: tuple[str, ...] = ("A1", "A2", "A3")) -> float:
        return float(self.totals(modules)["GWP-total"])

    def summary(self) -> dict[str, Any]:
        a13 = self.totals(("A1", "A2", "A3"))
        c = self.totals(("C1", "C2", "C3", "C4"))
        d = self.totals(("D",))
        return {
            "scenario": self.scenario, "functional_unit": self.functional_unit,
            **{f"{k} [A1-A3]": float(a13[k]) for k in self.categories},
            **{f"{k} [C1-C4]": float(c[k]) for k in self.categories},
            **{f"{k} [D]": float(d[k]) for k in self.categories},
            **{f"{k} [A1-A3+C]": float(a13[k] + c[k]) for k in self.categories},
            "coverage GWP-total": self.coverage.get("GWP-total"),
            "coverage AP (native)": self.coverage_native.get("AP"),
            "coverage AP (incl. proxies)": self.coverage.get("AP"),
            "fc_MPa": self.inventory.fc_MPa, "bulk_density_kg_m3": self.inventory.bulk_density_kg_m3,
            "product_kg_per_kg_solids": self.inventory.product_kg_per_kg_solids,
            "caco3_kg_per_kg_product": self.inventory.caco3_kg_per_kg_solids / self.inventory.product_kg_per_kg_solids,
        }


def fu_conversion(inv: Inventory, functional_unit: str) -> float:
    """Factor converting per-kg-solids amounts to the functional unit."""
    p = inv.product_kg_per_kg_solids
    if functional_unit == "kg_solids":
        return 1.0
    if functional_unit == "kg_product":
        return 1.0 / p
    if functional_unit == "m3_product":
        return inv.bulk_density_kg_m3 / p
    if functional_unit == "kg_caco3_precipitated":
        if inv.caco3_kg_per_kg_solids <= 0:
            raise ValueError("no microbially precipitated CaCO3 in this scenario; FU not applicable")
        return 1.0 / inv.caco3_kg_per_kg_solids
    if functional_unit == "m3_MPa":
        if not inv.fc_MPa:
            raise ValueError("compressive strength not available for this scenario; FU 'm3_MPa' not applicable")
        return inv.bulk_density_kg_m3 / p / inv.fc_MPa
    raise ValueError(f"unknown functional unit '{functional_unit}'")


def assess(inv: Inventory, data: DataBundle, *, functional_unit: str = "kg_product",
           bg_factor_overrides: dict[str, float] | None = None) -> Results:
    """Characterise an inventory. ``bg_factor_overrides`` = {process_id: multiplier} (Monte Carlo)."""
    cats = data.category_codes
    fu = fu_conversion(inv, functional_unit)
    rows: list[dict[str, Any]] = []
    missing: dict[str, set[str]] = {c: set() for c in cats}
    proxied: dict[str, set[str]] = {c: set() for c in cats}
    covered_w: dict[str, float] = {c: 0.0 for c in cats}
    native_w: dict[str, float] = {c: 0.0 for c in cats}
    total_w = 0.0
    # water use is always characterised with the Czech scarcity factor; the other categories use the
    # site-generic EF 3.1 factors unless the scenario asks for country-specific ones (site_specific_cf)
    site_specific = bool(inv.config.get("site_specific_cf", False))
    accounting = inv.config.get("carbon_accounting", "EF31")
    mult = bg_factor_overrides or {}
    for f in inv.flows:
        amount = f.amount * fu
        row: dict[str, Any] = {"module": f.module, "group": f.group, "kind": f.kind, "key": f.key,
                               "amount": amount, "unit": f.unit, "compartment": f.compartment}
        if f.kind == "background":
            proc = data.background.get(f.key)
            if proc is None:
                raise KeyError(f"background process '{f.key}' not found (flow in group '{f.group}')")
            scale = mult.get(f.key, 1.0)
            gwp = background_factor(proc, "GWP-total", f.bg_module)
            w = abs(amount * (gwp if not math.isnan(gwp) else 0.0))
            total_w += w
            for c in cats:
                fac = background_factor(proc, c, f.bg_module)
                if math.isnan(fac):
                    missing[c].add(f.key)
                    row[c] = 0.0
                else:
                    covered_w[c] += w
                    if c in proc.proxy_filled:
                        proxied[c].add(f.key)
                    else:
                        native_w[c] += w
                    row[c] = amount * fac * scale
        else:
            for c in cats:
                cf = data.cf(f.key, f.compartment, c, location="CZ" if (site_specific or c == "WDP") else "GLO")
                if accounting == "EN15804A2" and f.key == "carbon dioxide (biogenic)" and c in ("GWP-total", "GWP-biogenic"):
                    cf = 1.0   # -1/+1 convention: biogenic CO2 emissions count (uptake credited below)
                row[c] = amount * cf
        rows.append(row)
    # EN 15804+A2 biogenic carbon accounting (-1/+1): uptake with organic inputs, release of the stored fraction at C4
    if accounting == "EN15804A2":
        m = inv.meta
        uptake_co2 = -float(m.get("biogenic_c_inputs_kg_per_kg_solids", 0.0)) * 44.01 / 12.011 * fu
        stored_co2 = float(m.get("c_stored_biogenic_as_co2_kg_per_kg_solids", 0.0)) * fu
        emitted_co2 = float(m.get("co2_biogenic_direct_kg_per_kg_solids", 0.0)) * fu
        residual = max(-uptake_co2 - stored_co2 - emitted_co2, 0.0)   # organics not oxidised in A3 nor stored -> assumed mineralised
        for module, val, label in (("A1", uptake_co2, "biogenic CO2 uptake in organic inputs (-1)"),
                                   ("A3", residual, "residual organic carbon mineralised (+1)"),
                                   ("C4", stored_co2, "biogenic carbon stored in product, released at end of life (+1)")):
            if val:
                row = {"module": module, "group": "Biogenic carbon (EN 15804+A2 −1/+1)", "kind": "accounting",
                       "key": label, "amount": val, "unit": "kg CO2", "compartment": "air"}
                row.update({c: 0.0 for c in cats})
                row["GWP-total"] = val
                row["GWP-biogenic"] = val
                rows.append(row)
    contrib = pd.DataFrame(rows)
    coverage = {c: (covered_w[c] / total_w if total_w else 1.0) for c in cats}
    coverage_native = {c: (native_w[c] / total_w if total_w else 1.0) for c in cats}
    return Results(scenario=inv.scenario, functional_unit=functional_unit, fu_factor=fu, contrib=contrib, categories=cats,
                   units={c: data.category_unit(c) for c in cats}, coverage=coverage, coverage_native=coverage_native,
                   missing={c: sorted(v) for c, v in missing.items()}, proxy_filled={c: sorted(v) for c, v in proxied.items()},
                   inventory=inv, meta=dict(inv.meta))


def run_scenario(scenario: str, data: DataBundle, *, functional_unit: str | None = None,
                 overrides: dict[str, Any] | None = None, param_overrides: dict[str, float] | None = None,
                 bg_factor_overrides: dict[str, float] | None = None) -> Results:
    """Build the inventory of ``scenario`` and assess it."""
    inv = build_inventory(scenario, data, overrides=overrides, param_overrides=param_overrides)
    fu = functional_unit or inv.config.get("functional_unit", "kg_product")
    return assess(inv, data, functional_unit=fu, bg_factor_overrides=bg_factor_overrides)


def results_table(results: list[Results], modules: tuple[str, ...] = ("A1", "A2", "A3"),
                  categories: list[str] | None = None) -> pd.DataFrame:
    """Scenario × category table of impacts for the given modules."""
    cats = categories or results[0].categories
    df = pd.DataFrame({r.scenario: r.totals(modules)[cats] for r in results}).T
    df.index.name = "scenario"
    return df
