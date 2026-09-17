"""Parametric (one-variable) analysis: vary one input of a scenario between limits and record the response.

A *sweep parameter* is addressed by a key with a namespace prefix:

======================= ==================================================================================
``protocol:<path>``     a value of the (effective) protocol, e.g. ``protocol:biocementation_solution.dose_mL``,
                        ``protocol:biocementation_solution.supplements.urea``, ``protocol:incubation.duration_d``
``scenario:<key>``      a scenario key, e.g. ``scenario:carbonation_uptake_fraction``, ``scenario:transport_chemicals_km``
``reagent:<key>``       a ``reagent_optimisation`` key: ``urea_to_ca_molar_ratio``, ``solution_recirculation_fraction``,
                        ``nutrient_broth_factor``
``scaleup:<path>``      a scale-up parameter (dotted path of ``scaleup.yaml``), e.g. ``scaleup:industrial.curing_chamber.U_W_m2K``
``harvest_od600``       harvest optical density of the culture
``medium:<id>.<chem>``  g/L of a component of a medium (inline copy of the medium is modified)
``strain:<id>.<path>``  a property of the organism, e.g. ``strain:x.cultivation.duration_h``, ``strain:x.light_kWh_per_L_day``
``material:<id>.<key>`` a property of the waste material, e.g. ``material:wcf_c.portlandite_wt``, ``material:wcf_c.transport_km``
======================= ==================================================================================

:func:`available_parameters` lists the parameters that make sense for a given configuration with
default limits; :func:`sweep` evaluates the model for a list of values and returns a tidy table
(indicators per functional unit, cost, yields) that the application plots and the PDF report uses.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .inventory import Params, _deep_merge, build_inventory
from .lcia import assess
from .loaders import DataBundle


@dataclass
class SweepParameter:
    key: str
    label: str
    unit: str
    value: float
    lo: float
    hi: float
    integer: bool = False
    group: str = "recipe"
    notes: str = ""

    def values(self, steps: int = 11, lo: float | None = None, hi: float | None = None) -> list[float]:
        a, b = (self.lo if lo is None else lo), (self.hi if hi is None else hi)
        vals = np.linspace(a, b, int(steps))
        if self.integer:
            vals = np.unique(np.round(vals).astype(int))
        return [float(v) for v in vals]


# --------------------------------------------------------------------------------------------
# applying a parameter value to a configuration


def _set_path(d: dict[str, Any], path: str, value: Any) -> None:
    node = d
    parts = path.split(".")
    for p in parts[:-1]:
        node = node.setdefault(p, {})
        if not isinstance(node, dict):
            raise KeyError(f"cannot descend into '{p}' of '{path}'")
    node[parts[-1]] = value


def _get_path(d: dict[str, Any], path: str, default: Any = None) -> Any:
    node: Any = d
    for p in path.split("."):
        if not isinstance(node, dict) or p not in node:
            return default
        node = node[p]
    return node


def effective_config(scenario: str, data: DataBundle, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Scenario configuration with defaults and overrides applied (what the model will see)."""
    cfg = data.scenario_config(scenario)
    if overrides:
        cfg.update(overrides)
    return cfg


def effective_protocol(cfg: dict[str, Any], data: DataBundle) -> dict[str, Any]:
    base = cfg.get("custom_protocol") or data.protocols[cfg["protocol"]]
    return _deep_merge(base, cfg.get("protocol_overrides") or {})


def apply_parameter(key: str, value: float, cfg_overrides: dict[str, Any] | None, param_overrides: dict[str, float] | None,
                    data: DataBundle, scenario: str) -> tuple[dict[str, Any], dict[str, float]]:
    """Return new (overrides, param_overrides) with ``key`` set to ``value``."""
    ov = copy.deepcopy(cfg_overrides or {})
    po = dict(param_overrides or {})
    ns, _, rest = key.partition(":")
    if ns == "protocol":
        ov.setdefault("protocol_overrides", {})
        _set_path(ov["protocol_overrides"], rest, value)
    elif ns == "scenario":
        ov[rest] = value
    elif ns == "reagent":
        # start from the scenario's own reagent settings so that the other keys are preserved
        base_ro = dict(data.scenario_config(scenario).get("reagent_optimisation") or {})
        base_ro.update(ov.get("reagent_optimisation") or {})
        base_ro[rest] = value
        ov["reagent_optimisation"] = base_ro
    elif ns == "scaleup":
        po[rest] = float(value)
    elif key == "harvest_od600":
        ov["harvest_od600_override"] = float(value)
    elif ns in ("medium", "strain", "material"):
        ident, _, path = rest.partition(".")
        table = {"medium": ("custom_media", data.media), "strain": ("custom_strains", data.strains), "material": ("custom_materials", data.materials)}[ns]
        cfg_key, base_table = table
        ov.setdefault(cfg_key, {})
        entry = copy.deepcopy(ov[cfg_key].get(ident) or base_table[ident])
        if ns == "medium":
            entry.setdefault("components", {})[path] = float(value)
        else:
            _set_path(entry, path, value)
        ov[cfg_key][ident] = entry
    else:
        raise KeyError(f"unknown sweep parameter '{key}'")
    return ov, po


# --------------------------------------------------------------------------------------------
# parameter registry for a configuration


def _rng(v: float, lo_frac: float = 0.5, hi_frac: float = 1.5, floor: float = 0.0, cap: float | None = None) -> tuple[float, float]:
    lo, hi = max(floor, v * lo_frac), v * hi_frac
    if v == 0:
        lo, hi = 0.0, 1.0
    if cap is not None:
        hi = min(hi, cap)
    return lo, hi


def available_parameters(scenario: str, data: DataBundle, overrides: dict[str, Any] | None = None,
                         param_overrides: dict[str, float] | None = None) -> list[SweepParameter]:
    """Parameters that can be swept for this configuration, with sensible default limits."""
    cfg = effective_config(scenario, data, overrides)
    proto = effective_protocol(cfg, data)
    media = {**data.media, **(cfg.get("custom_media") or {})}
    strains = {**data.strains, **(cfg.get("custom_strains") or {})}
    materials = {**data.materials, **(cfg.get("custom_materials") or {})}
    chemicals = {**data.chemicals, **(cfg.get("custom_chemicals") or {})}
    strain = strains[proto["strain"]]
    material_id = cfg.get("material") or proto["material"]
    material = materials[material_id]
    out: list[SweepParameter] = []

    def add(key: str, label: str, unit: str, value: Any, lo: float, hi: float, integer: bool = False, group: str = "recipe", notes: str = "") -> None:
        if value is None:
            return
        out.append(SweepParameter(key, label, unit, float(value), float(lo), float(hi), integer, group, notes))

    # recipe / composition ---------------------------------------------------------------------
    add("protocol:solids_g", "Dry solids per specimen", "g", proto.get("solids_g"), *_rng(float(proto.get("solids_g", 25)), 0.5, 2.0))
    add("protocol:gypsum_fraction", "Waste-gypsum fraction of the solids", "-", proto.get("gypsum_fraction", 0.0), 0.0, 0.3)
    susp = proto.get("suspension") or {}
    add("protocol:suspension.volume_mL", "Bacterial suspension volume per specimen", "mL", susp.get("volume_mL"), *_rng(float(susp.get("volume_mL", 10)), 0.25, 2.0))
    add("protocol:suspension.od600", "Suspension optical density (OD600)", "-", susp.get("od600"), 0.5, max(2.0 * float(susp.get("od600", 2)), 5.0))
    add("harvest_od600", "Harvest OD600 of the culture", "-", cfg.get("harvest_od600_override") or (strain.get("cultivation") or {}).get("harvest_od600") or 2.5, 0.5, 10.0)
    add("protocol:saline_mL", "Extra saline per specimen", "mL", proto.get("saline_mL"), 0.0, max(2.0 * float(proto.get("saline_mL", 0) or 0), 10.0))
    hcl = proto.get("hcl") or {}
    add("protocol:hcl.volume_mL", "HCl volume per specimen", "mL", hcl.get("volume_mL"), 0.0, max(2.0 * float(hcl.get("volume_mL", 0) or 0), 5.0))
    bs = proto.get("biocementation_solution") or {}
    add("protocol:biocementation_solution.dose_mL", "Biocementation-solution dose volume", "mL", bs.get("dose_mL"), *_rng(float(bs.get("dose_mL", 5)), 0.25, 3.0))
    dosing = bs.get("dosing") or {}
    mode = dosing.get("mode", "repeated")
    if mode == "repeated":
        add("protocol:biocementation_solution.dosing.interval_h", "Dosing interval", "h", dosing.get("interval_h"), 12.0, 240.0)
        add("protocol:biocementation_solution.dosing.duration_d", "Dosing period", "d", dosing.get("duration_d", (proto.get("incubation") or {}).get("duration_d")), 1.0, 120.0)
    elif mode == "fixed":
        add("protocol:biocementation_solution.dosing.n_doses", "Number of doses", "-", dosing.get("n_doses"), 1, max(2 * int(dosing.get("n_doses", 5)), 10), integer=True)
    for cid, g in (bs.get("supplements") or {}).items():
        name = (chemicals.get(cid) or {}).get("name", cid)
        add(f"protocol:biocementation_solution.supplements.{cid}", f"{name} in the biocementation solution", "g/L", g, *_rng(float(g), 0.0, 2.0))
    if "urea" in (bs.get("supplements") or {}):
        add("reagent:urea_to_ca_molar_ratio", "Urea : Ca molar ratio", "mol/mol", (cfg.get("reagent_optimisation") or {}).get("urea_to_ca_molar_ratio") or 1.0, 0.5, 4.0,
            notes="0 = as in protocol; the sweep sets the ratio explicitly")
    add("reagent:solution_recirculation_fraction", "Recirculated share of the biocementation solution", "-", (cfg.get("reagent_optimisation") or {}).get("solution_recirculation_fraction", 0.0), 0.0, 0.9)
    add("reagent:nutrient_broth_factor", "Nutrient-broth strength factor", "-", (cfg.get("reagent_optimisation") or {}).get("nutrient_broth_factor", 1.0), 0.0, 2.0)
    inc = proto.get("incubation") or {}
    add("scenario:temperature_override_C", "Cultivation and curing temperature", "°C", cfg.get("temperature_override_C") or inc.get("temperature_C"), 15.0, 37.0)
    add("protocol:incubation.duration_d", "Biocementation period", "d", inc.get("duration_d"), 1.0, max(2.0 * float(inc.get("duration_d", 30)), 60.0))
    dry = proto.get("drying") or {}
    add("protocol:drying.duration_d", "Drying / conditioning period", "d", dry.get("duration_d", 0.0), 0.0, 60.0)
    add("protocol:precipitation_efficiency", "Precipitation efficiency (share of the theoretical CaCO3 yield)", "-", proto.get("precipitation_efficiency", 1.0), 0.1, 1.0,
        notes="ignored when a measured CaCO3 gain caps the yield")
    # cultivation medium components ------------------------------------------------------------
    cult = strain.get("cultivation") or {}
    variant = cfg.get("cultivation_variant") or proto.get("cultivation_variant")
    if variant and variant in (strain.get("alternative_cultivation_media") or {}):
        cult = {**cult, **strain["alternative_cultivation_media"][variant]}
    med_id = cult.get("medium")
    if med_id and med_id in media and not cfg.get("abiotic"):
        for cid, g in (media[med_id].get("components") or {}).items():
            name = (chemicals.get(cid) or {}).get("name", cid)
            add(f"medium:{med_id}.{cid}", f"{name} in the cultivation medium ({med_id})", "g/L", g, *_rng(float(g), 0.0, 2.0), group="cultivation")
        add(f"strain:{proto['strain']}.cultivation.duration_h", "Cultivation time", "h", cult.get("duration_h"), 6.0, 96.0, group="cultivation")
    if strain.get("light_kWh_per_L_day"):
        add(f"strain:{proto['strain']}.light_kWh_per_L_day", "Light energy for phototrophic culture", "kWh/(L·d)", strain["light_kWh_per_L_day"], 0.0, 2.0 * float(strain["light_kWh_per_L_day"]), group="cultivation")
    # system / technology ------------------------------------------------------------------------
    add("scenario:carbonation_uptake_fraction", "Carbonation of the portlandite (share)", "-", cfg.get("carbonation_uptake_fraction", 0.0), 0.0, 1.0, group="system")
    add(f"material:{material_id}.portlandite_wt", "Portlandite content of the fines", "wt%", material.get("portlandite_wt"), 0.0, 25.0, group="system")
    add(f"material:{material_id}.transport_km", "Transport distance of the fines", "km", material.get("transport_km", 70), 0.0, 500.0, group="system")
    add("scenario:transport_chemicals_km", "Transport distance of chemicals", "km", cfg.get("transport_chemicals_km", 200), 0.0, 2000.0, group="system")
    scale = cfg.get("scale", "industrial")
    P = Params(data.scaleup, scale, {**(cfg.get("scaleup_overrides") or {}), **(param_overrides or {})})
    for path, (v, lo, hi) in P.ranges(scale).items():
        if hi > lo:
            add(f"scaleup:{path}", path.replace(f"{scale}.", "").replace("_", " ").replace(".", " › "), "", P.get(path), lo, hi, group="scale-up")
    return out


def find_parameter(params: list[SweepParameter], key: str) -> SweepParameter | None:
    return next((p for p in params if p.key == key), None)


# --------------------------------------------------------------------------------------------
# the sweep


def sweep(scenario: str, data: DataBundle, key: str, values: list[float], *, overrides: dict[str, Any] | None = None,
          param_overrides: dict[str, float] | None = None, functional_unit: str | None = None,
          modules: tuple[str, ...] = ("A1", "A2", "A3"), categories: list[str] | None = None,
          with_cost: bool = True, with_eol: bool = True) -> pd.DataFrame:
    """Evaluate the scenario for every value of the parameter ``key``.

    Returns one row per value with the impact indicators per functional unit (``modules``), the
    indicators including C1–C4 (``<cat> +C``) when ``with_eol``, the indicative cost (bulk and
    laboratory grade) and the main physical quantities of the inventory.
    """
    from .cost import cost_summary
    cats = categories or data.category_codes
    rows: list[dict[str, Any]] = []
    for v in values:
        ov, po = apply_parameter(key, v, overrides, param_overrides, data, scenario)
        try:
            inv = build_inventory(scenario, data, overrides=ov, param_overrides=po)
            fu = functional_unit or inv.config.get("functional_unit", "kg_product")
            res = assess(inv, data, functional_unit=fu)
        except (ValueError, KeyError, ZeroDivisionError) as exc:
            rows.append({"value": v, "error": str(exc)})
            continue
        t = res.totals(modules)
        row: dict[str, Any] = {"value": v, "error": ""}
        row.update({c: float(t[c]) for c in cats})
        if with_eol:
            tc = res.totals(("C1", "C2", "C3", "C4"))
            row.update({f"{c} +C": float(t[c] + tc[c]) for c in cats})
        if with_cost and not data.prices.empty:
            row["cost_bulk_EUR"] = cost_summary(res, data, "bulk")["total_A1-A3"]
            row["cost_lab_EUR"] = cost_summary(res, data, "lab")["total_A1-A3"]
        m = res.meta
        row.update({"caco3_kg_per_kg_solids": m.get("caco3_precipitated_kg_per_kg_solids"), "product_kg_per_kg_solids": m.get("product_kg_per_kg_solids"),
                    "liquid_to_solid_L_per_kg": m.get("liquid_to_solid_L_per_kg"), "n_doses": m.get("n_doses"),
                    "urea_to_ca_molar_ratio": m.get("urea_to_ca_molar_ratio"), "fu_factor": res.fu_factor, "functional_unit": res.functional_unit})
        rows.append(row)
    df = pd.DataFrame(rows)
    df.attrs["parameter"] = key
    return df


def describe_sweep(df: pd.DataFrame, category: str = "GWP-total") -> dict[str, Any]:
    """Compact description of a sweep response (used for narrative text): range, extremum, monotonicity."""
    ok = df[df.get("error", "") == ""] if "error" in df else df
    if ok.empty or category not in ok:
        return {}
    x, y = ok["value"].to_numpy(float), ok[category].to_numpy(float)
    dy = np.diff(y)
    mono = "increases" if np.all(dy >= -1e-12) else "decreases" if np.all(dy <= 1e-12) else "is non-monotonic"
    i_min, i_max = int(np.argmin(y)), int(np.argmax(y))
    rel = (y.max() - y.min()) / abs(y[0]) if y[0] else float("nan")
    # linearity: R² of a straight-line fit
    r2 = float("nan")
    if len(x) > 2 and np.ptp(x) > 0:
        slope, icpt = np.polyfit(x, y, 1)
        ss_res = float(np.sum((y - (slope * x + icpt)) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    else:
        slope = float("nan")
    return {"x_min": float(x.min()), "x_max": float(x.max()), "y_at_min_x": float(y[0]), "y_at_max_x": float(y[-1]),
            "y_min": float(y.min()), "x_of_y_min": float(x[i_min]), "y_max": float(y.max()), "x_of_y_max": float(x[i_max]),
            "monotonic": mono, "relative_span": float(rel), "slope": float(slope), "r2_linear": float(r2), "n": int(len(x))}
