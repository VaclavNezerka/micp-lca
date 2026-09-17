"""Foreground life-cycle inventory generated from the laboratory protocols.

The model follows the modular structure of EN 15804+A2:

* A1 – supply of raw materials: processing of the waste fines and gypsum after the end-of-waste
  point, production of chemicals and media components, water
* A2 – transport of inputs to the biocementation plant
* A3 – manufacturing: cultivation of the microbial suspension, casting/mixing, dosing of the
  biocementation solution, curing (heated chamber), drying/conditioning, effluent treatment and the
  direct process emissions (CO2, NH3, NH4+, N2O, Cl-, residual organics) and carbonation uptake
* C1–C4 – end of life of the block (demolition, transport, processing or inert landfill)
* D – optional credits for recovered by-products (ammonium sulfate fertiliser)

All amounts are first computed **per laboratory specimen** exactly as described in the papers
(``data/foreground/protocols.yaml``), then normalised **per kg of dry input solids**; the
functional-unit conversion (per kg or m3 of product, per kg CaCO3) is done in :mod:`micp_lca.lcia`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from . import chemistry as chem
from .loaders import DataBundle

MODULES = ("A1", "A2", "A3", "C1", "C2", "C3", "C4", "D")


@dataclass
class Flow:
    kind: str            # 'background' | 'elementary'
    key: str             # background process id or elementary flow name (EF 3.1 nomenclature)
    amount: float        # per kg of dry input solids
    unit: str
    module: str
    group: str
    compartment: str = ""      # elementary flows: air | water | resource
    bg_module: str | None = None  # restrict a background dataset to one of its modules (e.g. 'C4')
    note: str = ""


@dataclass
class Inventory:
    scenario: str
    config: dict[str, Any]
    flows: list[Flow]
    product_kg_per_kg_solids: float
    caco3_kg_per_kg_solids: float
    bulk_density_kg_m3: float
    fc_MPa: float | None
    meta: dict[str, Any] = field(default_factory=dict)

    def add(self, flow: Flow) -> None:
        if flow.amount != 0.0 and not math.isnan(flow.amount):
            self.flows.append(flow)

    def totals_by_key(self) -> dict[tuple[str, str], float]:
        out: dict[tuple[str, str], float] = {}
        for f in self.flows:
            out[(f.kind, f.key)] = out.get((f.kind, f.key), 0.0) + f.amount
        return out


# --------------------------------------------------------------------------------------------
# parameter access (supports Monte-Carlo overrides)


class Params:
    """Access to the scale-up parameters with optional overrides (``{'industrial.curing_chamber.U_W_m2K': 0.5}``)."""

    def __init__(self, scaleup: dict[str, Any], scale: str, overrides: dict[str, float] | None = None):
        self.tree = scaleup
        self.scale = scale
        self.overrides = overrides or {}

    def get(self, path: str, default: float | None = None) -> float:
        """Return the (central or overridden) value of a parameter given by a dotted path."""
        if path in self.overrides:
            return float(self.overrides[path])
        node: Any = self.tree
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                if default is not None:
                    return float(default)
                raise KeyError(f"scale-up parameter '{path}' not found")
            node = node[part]
        if isinstance(node, dict) and "value" in node:
            return float(node["value"])
        return float(node)

    def text(self, path: str, default: str = "") -> str:
        node: Any = self.tree
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return str(node)

    def ranges(self, prefix: str = "industrial") -> dict[str, tuple[float, float, float]]:
        """All parameters with value/min/max under ``prefix`` -> {path: (value, min, max)}."""
        out: dict[str, tuple[float, float, float]] = {}

        def walk(node: Any, path: str) -> None:
            if isinstance(node, dict):
                if "value" in node and "min" in node and "max" in node:
                    out[path] = (float(node["value"]), float(node["min"]), float(node["max"]))
                else:
                    for k, v in node.items():
                        walk(v, f"{path}.{k}" if path else k)

        walk(self.tree.get(prefix, {}), prefix)
        return out


# --------------------------------------------------------------------------------------------
# helpers


def _medium_components(data: DataBundle, medium_id: str) -> dict[str, float]:
    m = data.media[medium_id]
    return {k: float(v) for k, v in (m.get("components") or {}).items()}


def _n_doses(dosing: dict[str, Any]) -> int:
    mode = dosing.get("mode", "repeated")
    if mode == "single":
        return 1
    if mode == "fixed":
        return int(dosing["n_doses"])
    return int(math.floor(float(dosing["duration_d"]) * 24.0 / float(dosing["interval_h"])))


def _deep_merge(base: dict[str, Any], upd: dict[str, Any]) -> dict[str, Any]:
    """Recursive merge used for protocol overrides from scenarios / the application."""
    import copy
    out = copy.deepcopy(dict(base))
    for k, v in (upd or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _with_custom_definitions(data: DataBundle, cfg: dict[str, Any]) -> DataBundle:
    """Return a bundle whose foreground tables include the inline definitions of a scenario.

    A scenario (typically one built interactively) may carry ``custom_media``, ``custom_strains``,
    ``custom_materials`` and ``custom_chemicals`` mappings (same structure as the YAML tables) and a
    complete ``custom_protocol``. They are merged over the loaded tables for this run only, so a
    user-defined composition can be evaluated and saved without touching the database.
    """
    import dataclasses
    fields = {"custom_media": "media", "custom_strains": "strains", "custom_materials": "materials", "custom_chemicals": "chemicals"}
    changes = {attr: {**getattr(data, attr), **cfg[key]} for key, attr in fields.items() if cfg.get(key)}
    if not changes:
        return data
    new = dataclasses.replace(data, **changes)
    if "_cf_cache" in data.__dict__:          # keep the memoised characterisation factors
        new.__dict__["_cf_cache"] = data.__dict__["_cf_cache"]
    return new


def _chem_bg(data: DataBundle, chemical_id: str) -> str:
    c = data.chemicals.get(chemical_id)
    if c is None or "background_process" not in c:
        raise KeyError(f"chemical '{chemical_id}' has no background_process in chemicals.yaml")
    return c["background_process"]


# --------------------------------------------------------------------------------------------
# main builder


def build_inventory(scenario: str, data: DataBundle, *, overrides: dict[str, Any] | None = None,
                    param_overrides: dict[str, float] | None = None) -> Inventory:
    """Build the foreground inventory (per kg of dry input solids) for a named scenario.

    ``overrides`` replace scenario-level keys (e.g. ``{"material": "wcf_g", "scale": "lab"}``);
    ``param_overrides`` replace scale-up parameters by dotted path (used by Monte Carlo).
    """
    cfg = data.scenario_config(scenario)
    if overrides:
        cfg.update(overrides)
    data = _with_custom_definitions(data, cfg)
    base_proto = cfg.get("custom_protocol") or data.protocols[cfg["protocol"]]
    proto = _deep_merge(base_proto, cfg.get("protocol_overrides") or {})
    material_id = cfg.get("material") or proto["material"]
    material = data.materials[material_id]
    scale = cfg.get("scale", "industrial")
    merged_params = {**(cfg.get("scaleup_overrides") or {}), **(param_overrides or {})}   # scenario-level overrides first
    P = Params(data.scaleup, scale, merged_params)
    strain = data.strains[proto["strain"]]
    abiotic = bool(cfg.get("abiotic", False))
    inv = Inventory(scenario=scenario, config=cfg, flows=[], product_kg_per_kg_solids=1.0,
                    caco3_kg_per_kg_solids=0.0, bulk_density_kg_m3=float(material.get("product_bulk_density_kg_m3", 1100)),
                    fc_MPa=None)
    meta = inv.meta
    electricity = cfg.get("electricity", "electricity_CZ_lv")
    water_bg = P.text(f"{scale}.water_source", "water_tap")
    km_chem = float(cfg.get("transport_chemicals_km", 200))
    km_feathers = float(cfg.get("transport_feathers_km", 80))
    km_gypsum = float(cfg.get("transport_gypsum_km", 100))
    temp_override = cfg.get("temperature_override_C")

    S = float(proto["solids_g"]) / 1000.0                     # kg dry solids per specimen
    g_frac = float(proto.get("gypsum_fraction", 0.0))
    residue_kg = S * (1.0 - g_frac)
    gypsum_kg = S * g_frac
    per = 1.0 / S                                             # -> per kg solids

    def add(kind: str, key: str, amount: float, unit: str, module: str, group: str, **kw: Any) -> None:
        inv.add(Flow(kind=kind, key=key, amount=amount * per, unit=unit, module=module, group=group, **kw))

    def add_chemical(chemical_id: str, kg: float, group: str, km: float = km_chem) -> None:
        if kg <= 0:
            return
        add("background", _chem_bg(data, chemical_id), kg, "kg", "A1", group)
        add("background", "transport_truck", kg * km / 1000.0, "tkm", "A2", "Transport")

    def add_energy(kwh_el: float, group: str, module: str = "A3") -> None:
        if kwh_el > 0:
            add("background", electricity, kwh_el, "kWh", module, group)

    def add_heat(kwh_th: float, group: str, carrier: str = "heat_natural_gas") -> None:
        if kwh_th > 0:
            add("background", carrier, kwh_th, "kWh", "A3", group)

    def add_water(kg: float, group: str) -> None:
        if kg > 0:
            add("background", water_bg, kg, "kg", "A1", group)

    # ---------------------------------------------------------------- A1/A2: waste fines and gypsum
    def add_material_processing(mat: dict[str, Any], kg: float, group: str, km: float, truck: str) -> None:
        for step in mat.get("processing", []):
            add_energy(float(step.get("electricity_kWh_per_t", 0.0)) / 1000.0 * kg, group, module="A1")
            wear = float(step.get("wear_parts_kg_per_t", 0.0)) / 1000.0 * kg
            if wear:
                add("background", "chromium_steel_mill_parts", wear, "kg", "A1", group)
        add("background", truck, kg * km / 1000.0, "tkm", "A2", "Transport")

    add_material_processing(material, residue_kg, "Waste fines processing", float(material.get("transport_km", 70)), "transport_truck_trailer")
    if gypsum_kg > 0:
        add_material_processing(data.materials["waste_gypsum_plaster"], gypsum_kg, "Gypsum processing", km_gypsum, "transport_truck")

    # ---------------------------------------------------------------- A3: cultivation of the suspension
    susp = proto.get("suspension", {}) or {}
    V_susp = float(susp.get("volume_mL", 0.0)) / 1000.0     # L
    cult = strain.get("cultivation", {})
    variant = cfg.get("cultivation_variant") or proto.get("cultivation_variant")
    if variant and variant in (strain.get("alternative_cultivation_media") or {}):
        alt = strain["alternative_cultivation_media"][variant]
        cult = {**cult, **alt}
    T_cult = float(temp_override) if temp_override is not None else float(cult.get("temperature_C", 30))
    V_cult = 0.0
    harvest_od = float(cfg.get("harvest_od600_override") or cult.get("harvest_od600") or 2.5)
    if not abiotic and V_susp > 0 and susp.get("od600"):
        V_cult = V_susp * float(susp["od600"]) / harvest_od
    if not abiotic and strain.get("pathway") == "fungal":
        V_cult = float(proto.get("inoculum_agar_L", 0.01))

    def add_medium(volume_L: float, medium_id: str, group: str, supplements: dict[str, float] | None = None,
                   supplements_medium: str | None = None, energy_group: str | None = None) -> None:
        egroup = energy_group or group.replace("media", "energy")
        comps = dict(_medium_components(data, medium_id))
        if supplements_medium:
            for k, v in _medium_components(data, supplements_medium).items():
                comps[k] = comps.get(k, 0.0) + v
        for k, v in (supplements or {}).items():
            comps[k] = comps.get(k, 0.0) + float(v)
        for cid, g_per_L in comps.items():
            kg = g_per_L * volume_L / 1000.0
            km = km_feathers if cid == "chicken_feathers" else km_chem
            add_chemical(cid, kg, group, km)
        add_water(volume_L * 1.0, group)
        m = data.media[medium_id]
        # sterilisation / hydrolysis heat
        cp = P.get("industrial.medium_sterilisation.cp_kJ_kgK", 4.18)
        if scale == "industrial":
            inlet = P.get("industrial.medium_sterilisation.inlet_C", 15)
            if m.get("sterilisation") == "autoclave":
                hold = P.get("industrial.medium_sterilisation.hold_C", 121)
                rec = P.get("industrial.medium_sterilisation.heat_recovery")
                add_heat(volume_L * cp * (hold - inlet) * (1 - rec) / 3600.0, egroup)
                add_energy(P.get("industrial.medium_sterilisation.electricity_kWh_per_m3") * volume_L / 1000.0, egroup)
            if m.get("hydrolysis"):
                frac = float(m["hydrolysis"].get("fraction_of_volume_heated", 1.0))
                rec = P.get("industrial.fermentation.hydrolysate_heating_heat_recovery")
                add_heat(volume_L * frac * cp * (float(m["hydrolysis"]["temperature_C"]) - inlet) * (1 - rec) / 3600.0, egroup)
        else:  # laboratory equipment
            if m.get("sterilisation") == "autoclave":
                a = data.scaleup["lab"]["autoclave"]
                add_energy(float(a["power_kW"]) * float(a["cycle_h"]) / float(a["load_L"]) * volume_L, egroup)
            if m.get("hydrolysis"):
                h = data.scaleup["lab"]["hotplate_hydrolysis"]
                frac = float(m["hydrolysis"].get("fraction_of_volume_heated", 1.0))
                add_energy(float(h["power_kW"]) * float(h["duration_h"]) / float(h["batch_L"]) * volume_L * frac, egroup)

    if V_cult > 0:
        add_medium(V_cult, cult["medium"], "Cultivation: media", cult.get("supplements"), cult.get("supplements_medium"))
        hours = float(cult.get("duration_h", 24))
        if scale == "industrial":
            add_energy(P.get("industrial.fermentation.power_kW_per_m3") * V_cult / 1000.0 * hours, "Cultivation: energy")
            add_energy(P.get("industrial.fermentation.temperature_control_kWh_per_m3_day") * V_cult / 1000.0 * hours / 24.0, "Cultivation: energy")
            if cult.get("harvest") == "centrifugation":
                add_energy(P.get("industrial.harvest.centrifuge_kWh_per_m3") * V_cult / 1000.0, "Cultivation: energy")
        else:
            sh = data.scaleup["lab"]["shaking_incubator"]
            add_energy(float(sh["average_power_kW"]) * hours / float(sh["capacity_L"]) * V_cult, "Cultivation: energy")
            if cult.get("harvest") == "centrifugation":
                c = data.scaleup["lab"]["centrifuge"]
                add_energy(float(c["power_kW"]) * float(c["run_h"]) / float(c["capacity_L"]) * V_cult, "Cultivation: energy")
        # resuspension in saline
        add_medium(V_susp, cult.get("resuspension_medium", "saline"), "Cultivation: media", energy_group="Cultivation: energy")
    elif V_susp > 0:  # abiotic control: saline instead of suspension
        add_medium(V_susp, "saline", "Casting: saline, acid, water")

    # ---------------------------------------------------------------- A3: casting (saline, acid, mixing)
    V_saline = float(proto.get("saline_mL", 0.0)) / 1000.0
    if V_saline > 0:
        add_medium(V_saline, "saline", "Casting: saline, acid, water", energy_group="Mixing/casting energy")
    hcl = proto.get("hcl", {}) or {}
    V_hcl = float(hcl.get("volume_mL", 0.0)) / 1000.0
    hcl_kg = float(hcl.get("molarity", 0.0)) * V_hcl * chem.M["HCl"] / 1000.0
    add_chemical("hydrochloric_acid", hcl_kg, "Casting: saline, acid, water")
    add_water(V_hcl, "Casting: saline, acid, water")
    if scale == "industrial":
        add_energy(P.get("industrial.solids_mixing_kWh_per_t") / 1000.0 * S, "Mixing/casting energy")

    # ---------------------------------------------------------------- A3: biocementation solution
    bs = proto["biocementation_solution"]
    n_doses = _n_doses(bs["dosing"])
    V_dose = float(bs["dose_mL"]) / 1000.0
    V_bs = n_doses * V_dose
    supplements = {k: float(v) for k, v in (bs.get("supplements") or {}).items()}
    ropt = cfg.get("reagent_optimisation") or {}
    balance = chem.ReagentBalance()
    pathway = strain.get("pathway", "")
    if "calcium_chloride" in supplements:
        balance.ca_source = "CaCl2"
        balance.ca_mol = supplements["calcium_chloride"] * V_bs / chem.M["CaCl2"]
        balance.chloride_mol += 2 * balance.ca_mol
    if "calcium_lactate_pentahydrate" in supplements:
        balance.ca_source = "CaLactate"
        mol = supplements["calcium_lactate_pentahydrate"] * V_bs / chem.M["CaLac5"]
        balance.ca_mol += mol
        balance.organic_mol += 2 * mol
        balance.organic_kind = "lactate"
        balance.organic_c_origin = data.chemicals["calcium_lactate_pentahydrate"].get("carbon_origin", "biogenic")
    if "calcium_acetate" in supplements:
        balance.ca_source = "CaAcetate" if balance.ca_source == "none" else balance.ca_source + "+CaAcetate"
        mol = supplements["calcium_acetate"] * V_bs / chem.M["CaAc"]
        balance.ca_mol += mol
        balance.organic_mol += 2 * mol
        balance.organic_kind = "acetate"
        balance.organic_c_origin = data.chemicals["calcium_acetate"].get("carbon_origin", "fossil")
    if "calcium_nitrate_tetrahydrate" in supplements:
        mol = supplements["calcium_nitrate_tetrahydrate"] * V_bs / chem.M["CaNO3_4H2O"]
        balance.ca_mol += mol
        balance.nitrate_mol += 2 * mol
    if "sodium_nitrate" in supplements:
        balance.nitrate_mol += supplements["sodium_nitrate"] * V_bs / chem.M["NaNO3"]
    if "sodium_bicarbonate" in supplements and pathway == "photosynthetic":
        balance.bicarbonate_mol += supplements["sodium_bicarbonate"] * V_bs / chem.M["NaHCO3"]
    if "urea" in supplements:
        if ropt.get("urea_to_ca_molar_ratio") and balance.ca_mol > 0:
            supplements["urea"] = float(ropt["urea_to_ca_molar_ratio"]) * balance.ca_mol * chem.M["urea"] / V_bs
        balance.urea_mol = supplements["urea"] * V_bs / chem.M["urea"]
        balance.carbonate_source = "urea"
    elif balance.organic_mol > 0:
        balance.carbonate_source = "organic"
    elif balance.bicarbonate_mol > 0:
        balance.carbonate_source = "inorganic"
    else:
        balance.carbonate_source = "metabolic"
    if proto.get("carbonate_carbon_source") == "metabolic_biogenic":
        balance.carbonate_source = "metabolic"
    # chloride from saline (suspension carrier + extra saline) and from the acid
    saline_chloride_mol = (V_saline + V_susp) * 9.0 / chem.M["NaCl"]
    balance.chloride_mol += saline_chloride_mol + hcl_kg * 1000.0 / chem.M["HCl"]

    if abiotic:  # negative control: sterile saline replaces the biocementation solution
        add_medium(V_bs, "saline", "Casting: saline, acid, water")
        balance = chem.ReagentBalance(chloride_mol=saline_chloride_mol + hcl_kg * 1000.0 / chem.M["HCl"] + V_bs * 9.0 / chem.M["NaCl"])
    else:
        recirc = float(ropt.get("solution_recirculation_fraction", 0.0))   # share of the BS volume re-used (make-up only)
        fresh = 1.0 - recirc
        nb_factor = float(ropt.get("nutrient_broth_factor", 1.0)) * fresh
        base_comps = {k: v * nb_factor for k, v in _medium_components(data, bs["base_medium"]).items()}
        # medium components (nutrient base) and reagents are tracked in separate groups
        m = data.media[bs["base_medium"]]
        # nutrient base
        for cid, g_per_L in base_comps.items():
            add_chemical(cid, g_per_L * V_bs / 1000.0, "Biocementation: nutrient medium",
                         km_feathers if cid == "chicken_feathers" else km_chem)
        # reagents
        for cid, g_per_L in supplements.items():
            grp = "Biocementation: urea" if cid == "urea" else "Biocementation: calcium source"
            add_chemical(cid, g_per_L * V_bs / 1000.0, grp)
        V_fresh = V_bs * fresh
        add_water(V_fresh, "Biocementation: nutrient medium")
        cp = P.get("industrial.medium_sterilisation.cp_kJ_kgK", 4.18)
        if scale == "industrial":
            inlet = P.get("industrial.medium_sterilisation.inlet_C", 15)
            if m.get("sterilisation") == "autoclave":
                rec = P.get("industrial.medium_sterilisation.heat_recovery")
                add_heat(V_fresh * cp * (P.get("industrial.medium_sterilisation.hold_C", 121) - inlet) * (1 - rec) / 3600.0,
                         "Biocementation: energy")
            if m.get("hydrolysis"):
                frac = float(m["hydrolysis"].get("fraction_of_volume_heated", 1.0))
                rec = P.get("industrial.fermentation.hydrolysate_heating_heat_recovery")
                add_heat(V_fresh * frac * cp * (float(m["hydrolysis"]["temperature_C"]) - inlet) * (1 - rec) / 3600.0,
                         "Biocementation: energy")
            add_energy(P.get("industrial.solution_dosing_kWh_per_m3") * V_bs / 1000.0, "Biocementation: energy")
        else:
            if m.get("sterilisation") == "autoclave":
                a = data.scaleup["lab"]["autoclave"]
                add_energy(float(a["power_kW"]) * float(a["cycle_h"]) / float(a["load_L"]) * V_fresh, "Biocementation: energy")
            if m.get("hydrolysis"):
                h = data.scaleup["lab"]["hotplate_hydrolysis"]
                frac = float(m["hydrolysis"].get("fraction_of_volume_heated", 1.0))
                add_energy(float(h["power_kW"]) * float(h["duration_h"]) / float(h["batch_L"]) * V_fresh * frac, "Biocementation: energy")

    # ---------------------------------------------------------------- chemistry: CaCO3, carbon, nitrogen
    results = dict(proto.get("results") or {})
    if cfg.get("material") and proto.get("results_by_material", {}).get(cfg["material"]):
        results.update(proto["results_by_material"][cfg["material"]])
    if temp_override is not None and proto.get("results_by_temperature", {}).get(int(temp_override)):
        results.update(proto["results_by_temperature"][int(temp_override)])
    measured = results.get("caco3_gain_wt_abs")
    measured_kg = float(measured) / 100.0 * S if (measured is not None and not abiotic) else None
    outcome = chem.react(
        balance, precipitation_efficiency=float(proto.get("precipitation_efficiency", 1.0)),
        measured_caco3_kg=measured_kg,
        urea_hydrolysed_fraction=P.get("industrial.nitrogen_fate.urea_hydrolysed_fraction"),
        lactate_oxidised_fraction=P.get("industrial.lactate_fate.oxidised_fraction"),
        nitrate_denitrified_fraction=P.get("industrial.nitrogen_fate.nitrate_denitrified_fraction", 0.9),
    )
    meta["reaction_notes"] = outcome.notes
    frac_drained = P.get("industrial.effluent.fraction_drained")
    if abiotic:
        outcome.caco3_precipitated_kg = 0.0

    # direct emissions -------------------------------------------------------------------------
    add("elementary", "carbon dioxide (fossil)", outcome.co2_fossil_kg, "kg", "A3", "Direct process emissions", compartment="air")
    add("elementary", "carbon dioxide (biogenic)", outcome.co2_biogenic_kg, "kg", "A3", "Direct process emissions", compartment="air")
    treatment = cfg.get("effluent_treatment", "none")
    n_fate = {"nh4_to_water": 0.0, "nh3_to_air": 0.0, "n2o_to_air": 0.0, "n_recovered": 0.0, "n_retained_in_product": 0.0, "n_drained": 0.0}
    if outcome.n_hydrolysed_kg > 0:
        eff = 0.0
        if treatment == "ammonia_stripping":
            eff = P.get("industrial.effluent.ammonia_stripping.efficiency")
        elif treatment == "struvite":
            eff = P.get("industrial.effluent.struvite.efficiency")
        n_fate = chem.nitrogen_fate(
            outcome.n_hydrolysed_kg, fraction_drained=frac_drained,
            nh3_volatilised_fraction=P.get("industrial.nitrogen_fate.nh3_volatilised_fraction_of_retained_N"),
            n2o_fraction=P.get("industrial.nitrogen_fate.n2o_fraction_of_N"), treatment_efficiency=eff)
        add("elementary", "ammonium", n_fate["nh4_to_water"], "kg", "A3", "Direct process emissions", compartment="water")
        add("elementary", "ammonia", n_fate["nh3_to_air"], "kg", "A3", "Direct process emissions", compartment="air")
        add("elementary", "nitrous oxide", n_fate["n2o_to_air"], "kg", "A3", "Direct process emissions", compartment="air")
        n_treated = n_fate["n_drained"] if treatment != "none" else 0.0
        if treatment == "ammonia_stripping" and n_treated > 0:
            add_energy(P.get("industrial.effluent.ammonia_stripping.electricity_kWh_per_kgN") * n_treated, "Effluent treatment")
            add_chemical("sodium_hydroxide", P.get("industrial.effluent.ammonia_stripping.naoh_kg_per_kgN") * n_treated, "Effluent treatment")
            add_chemical("sulfuric_acid", P.get("industrial.effluent.ammonia_stripping.h2so4_kg_per_kgN") * n_treated, "Effluent treatment")
            if cfg.get("module_d"):
                as_kg = n_fate["n_recovered"] * 132.14 / (2 * chem.M["N"])
                add("background", "ammonium_sulfate_credit", -as_kg, "kg", "D", "Module D credits")
        elif treatment == "struvite" and n_treated > 0:
            add_energy(P.get("industrial.effluent.struvite.electricity_kWh_per_kgN") * n_treated, "Effluent treatment")
            add_chemical("magnesium_oxide", P.get("industrial.effluent.struvite.mgo_kg_per_kgN") * n_treated, "Effluent treatment")
            add_chemical("phosphoric_acid", P.get("industrial.effluent.struvite.h3po4_kg_per_kgN") * n_treated, "Effluent treatment")
            if cfg.get("module_d"):
                as_kg = n_fate["n_recovered"] * 132.14 / (2 * chem.M["N"])   # credited as N-equivalent ammonium sulfate
                add("background", "ammonium_sulfate_credit", -as_kg, "kg", "D", "Module D credits")
    add("elementary", "urea", outcome.urea_unhydrolysed_kg * frac_drained, "kg", "A3", "Direct process emissions", compartment="water")
    add("elementary", outcome.organic_effluent_flow, outcome.organic_unoxidised_kg * frac_drained, "kg", "A3", "Direct process emissions", compartment="water")
    add("elementary", "chloride", outcome.chloride_kg * frac_drained, "kg", "A3", "Direct process emissions", compartment="water")
    if outcome.nitrate_n_denitrified_kg > 0:   # denitrification: N2O by-product (share of denitrified N) and residual nitrate
        n2o_share = P.get("industrial.nitrogen_fate.denitrification_n2o_fraction", 0.02)
        add("elementary", "nitrous oxide", outcome.nitrate_n_denitrified_kg * n2o_share * chem.M["N2O"] / (2 * chem.M["N"]), "kg", "A3",
            "Direct process emissions", compartment="air")
        add("elementary", "nitrate", outcome.nitrate_residual_kg * frac_drained, "kg", "A3", "Direct process emissions", compartment="water")
    # photosynthetic cultures: light energy during the biocementation period
    light = float(strain.get("light_kWh_per_L_day", 0.0) or 0.0)
    if light > 0 and not abiotic:
        add_energy(light * (V_susp + V_bs) * float(proto["incubation"]["duration_d"]), "Curing: electricity")
    # carbonation uptake of atmospheric CO2 by portlandite in the fines (EN 16757 Annex BB convention)
    uptake = chem.carbonation_uptake_kg(residue_kg * float(material.get("portlandite_wt", 0.0)) / 100.0,
                                        float(cfg.get("carbonation_uptake_fraction", 0.0)))
    add("elementary", "carbon dioxide (fossil)", -uptake, "kg", "A3", "Carbonation uptake", compartment="air")

    # ---------------------------------------------------------------- product mass
    caco3_gain = outcome.caco3_precipitated_kg / S
    aft_water = float(proto.get("aft_water_binding_fraction", 0.0)) if gypsum_kg > 0 else 0.0
    nacl_in = (V_saline + V_susp + (V_bs if abiotic else 0.0)) * 9.0 / 1000.0
    retained_salts = nacl_in * (1 - frac_drained) / S
    product_per_solids = 1.0 + caco3_gain + aft_water + retained_salts
    inv.product_kg_per_kg_solids = product_per_solids
    inv.caco3_kg_per_kg_solids = caco3_gain
    product_kg = S * product_per_solids

    # ---------------------------------------------------------------- A3: curing, drying, effluent
    T_inc = float(temp_override) if temp_override is not None else float(proto["incubation"]["temperature_C"])
    d_inc = float(proto["incubation"]["duration_d"])
    d_dry = float(proto.get("drying", {}).get("duration_d", 0.0))
    recirc_frac = float((cfg.get("reagent_optimisation") or {}).get("solution_recirculation_fraction", 0.0)) if not abiotic else 0.0
    liquids_kg = V_susp + V_saline + V_hcl + V_bs * (1.0 - recirc_frac)
    if scale == "industrial":
        U = P.get("industrial.curing_chamber.U_W_m2K")
        a_v = P.get("industrial.curing_chamber.envelope_area_m2_per_m3_chamber")
        m3_per_t = P.get("industrial.curing_chamber.chamber_m3_per_t_product")
        ambient = P.get("industrial.curing_chamber.ambient_C")
        dT = max(T_inc - ambient, 0.0)
        area = a_v * m3_per_t * product_kg / 1000.0
        loss_kwh = U * area * dT * (d_inc + d_dry) * 86400.0 / 3.6e6
        init_kwh = (S + liquids_kg) * P.get("industrial.curing_chamber.initial_heating_cp_kJ_kgK", 1.5) * dT / 3600.0
        add_heat(loss_kwh + init_kwh, "Curing: heat", P.text("industrial.curing_chamber.heat_carrier", "heat_natural_gas"))
        add_energy(P.get("industrial.curing_chamber.air_handling_kWh_per_t_day") * product_kg / 1000.0 * (d_inc + d_dry), "Curing: electricity")
        drained_L = frac_drained * liquids_kg
        free_water = max(liquids_kg - drained_L - aft_water * S, 0.0)
        if P.text("industrial.drying.mode", "ambient_forced_air") == "thermal":
            evap = free_water * P.get("industrial.drying.water_evaporated_fraction")
            add_heat(evap * P.get("industrial.drying.thermal_specific_MJ_per_kg_water") / 3.6, "Drying")
        else:
            add_energy(P.get("industrial.drying.fan_kWh_per_t") * product_kg / 1000.0, "Drying")
        add_energy(P.get("industrial.effluent.basic_treatment_kWh_per_m3") * drained_L / 1000.0, "Effluent treatment")
        meta["effluent_L_per_kg_solids"] = drained_L / S
    else:
        inc = data.scaleup["lab"]["incubator"]
        add_energy(float(inc["average_power_kW"]) * 24.0 * (d_inc + d_dry) / float(inc["capacity_specimens"]), "Curing: electricity")

    # ---------------------------------------------------------------- C1–C4: end of life of the block
    eol = cfg.get("eol", "landfill")
    add_energy(2.0 / 1000.0 * product_kg, "End of life", module="C1")            # demolition/loading, assumption
    add("background", "transport_truck", product_kg * 50.0 / 1000.0, "tkm", "C2", "End of life")
    if eol == "recycling":
        add("background", "rubble_processing", product_kg, "kg", "C3", "End of life", bg_module="C3")
    else:
        add("background", "landfill_inert", product_kg, "kg", "C4", "End of life", bg_module="C4")

    # ---------------------------------------------------------------- results & metadata
    fc = cfg.get("fc_override_MPa", results.get("fc_MPa"))
    inv.fc_MPa = float(fc) if fc is not None else None
    meta.update({
        "material": material_id, "strain": proto["strain"], "pathway": strain.get("pathway"), "scale": scale,
        "solids_kg_per_specimen": S, "gypsum_fraction": g_frac, "n_doses": n_doses,
        "V_suspension_L": V_susp, "V_culture_L": V_cult, "V_biocementation_solution_L": V_bs, "V_saline_L": V_saline,
        "liquid_to_solid_L_per_kg": liquids_kg / S, "T_cultivation_C": T_cult, "T_incubation_C": T_inc,
        "incubation_d": d_inc, "drying_d": d_dry, "urea_kg_per_kg_solids": balance.urea_mol * chem.M["urea"] / 1000.0 / S,
        "ca_mol_per_kg_solids": balance.ca_mol / S, "urea_to_ca_molar_ratio": (balance.urea_mol / balance.ca_mol) if balance.ca_mol else None,
        "caco3_theoretical_kg_per_kg_solids": outcome.caco3_theoretical_kg / S, "caco3_precipitated_kg_per_kg_solids": caco3_gain,
        "precipitation_efficiency": outcome.precipitation_efficiency, "co2_fossil_direct_kg_per_kg_solids": outcome.co2_fossil_kg / S,
        "co2_biogenic_direct_kg_per_kg_solids": outcome.co2_biogenic_kg / S, "c_stored_fossil_as_co2_kg_per_kg_solids": outcome.c_stored_fossil_kg / S,
        "c_stored_biogenic_as_co2_kg_per_kg_solids": outcome.c_stored_biogenic_kg / S, "carbonation_uptake_kg_per_kg_solids": uptake / S,
        "n_hydrolysed_kg_per_kg_solids": outcome.n_hydrolysed_kg / S, "nitrogen_fate_kg_per_kg_solids": {k: v / S for k, v in n_fate.items()},
        "carbonate_source": balance.carbonate_source, "organic_substrate": balance.organic_kind if balance.organic_mol else None,
        "nitrate_n_denitrified_kg_per_kg_solids": outcome.nitrate_n_denitrified_kg / S,
        "product_kg_per_kg_solids": product_per_solids, "fc_MPa": inv.fc_MPa, "k_N_mm": results.get("k_N_mm"),
        "effluent_treatment": treatment, "carbon_accounting": cfg.get("carbon_accounting", "EF31"),
        "biogenic_c_inputs_kg_per_kg_solids": _biogenic_carbon_inputs(inv, data),
    })
    return inv


def _biogenic_carbon_inputs(inv: Inventory, data: DataBundle) -> float:
    """Biogenic carbon (kg C per kg solids) entering with organic inputs (media components, lactate)."""
    bg_to_chem = {c.get("background_process"): cid for cid, c in data.chemicals.items() if isinstance(c, dict)}
    total = 0.0
    for f in inv.flows:
        if f.kind != "background" or f.module != "A1":
            continue
        cid = bg_to_chem.get(f.key)
        if not cid:
            continue
        c = data.chemicals[cid]
        if c.get("carbon_origin") == "biogenic":
            total += f.amount * float(c.get("carbon_content", 0.0))
    return total
