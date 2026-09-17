"""End-to-end behaviour of the inventory and impact assessment."""
from __future__ import annotations

import math

import pytest

from micp_lca import build_inventory, run_scenario
from micp_lca.benchmarks import benchmark_impacts, compare_scenarios, compare_with_status_quo
from micp_lca.lcia import fu_conversion


def test_all_scenarios_run(data):
    for name in data.scenarios["scenarios"]:
        r = run_scenario(name, data)
        gwp = r.gwp()
        assert math.isfinite(gwp), name
        assert r.coverage["GWP-total"] == pytest.approx(1.0), name


def test_inventory_normalised_per_kg_solids(data):
    inv = build_inventory("SP_lab_protocol_90d", data)
    S = inv.meta["solids_kg_per_specimen"]
    assert S == pytest.approx(0.007)
    # 36 doses x 10 mL over 90 days at 60 h intervals; 2.8 g/L CaCl2 -> 9.08 mmol Ca per specimen
    assert inv.meta["n_doses"] == 36
    assert inv.meta["ca_mol_per_kg_solids"] == pytest.approx(36 * 0.010 * 2.8 / 110.98 / S, rel=1e-6)
    # urea 20 g/L -> molar excess over calcium of ~13
    assert inv.meta["urea_to_ca_molar_ratio"] == pytest.approx(20 / 60.06 / (2.8 / 110.98), rel=1e-6)
    # measured CaCO3 gain (8.96 wt%) is used and lies below the stoichiometric maximum
    assert inv.meta["caco3_precipitated_kg_per_kg_solids"] == pytest.approx(0.0896)
    assert inv.meta["caco3_theoretical_kg_per_kg_solids"] > inv.meta["caco3_precipitated_kg_per_kg_solids"]


def test_product_mass_and_functional_units(data):
    inv = build_inventory("GYP_WCFC_single_dose", data)
    assert 1.0 < inv.product_kg_per_kg_solids < 1.1
    assert fu_conversion(inv, "kg_solids") == 1.0
    assert fu_conversion(inv, "kg_product") == pytest.approx(1 / inv.product_kg_per_kg_solids)
    assert fu_conversion(inv, "m3_product") == pytest.approx(1100 / inv.product_kg_per_kg_solids)
    assert fu_conversion(inv, "m3_MPa") == pytest.approx(1100 / inv.product_kg_per_kg_solids / 1.9)


def test_ureolytic_route_has_nitrogen_emissions_and_lactate_route_has_none(data):
    sp = run_scenario("SP_lab_protocol_90d", data)
    bc = run_scenario("BC_lactate_30d", data)
    sp_direct = sp.contrib[sp.contrib["group"] == "Direct process emissions"]
    assert (sp_direct["key"] == "ammonia").any() and (sp_direct["key"] == "ammonium").any()
    assert sp.totals(("A1", "A2", "A3"))["AP"] > 10 * bc.totals(("A1", "A2", "A3"))["AP"]
    bc_direct = bc.contrib[bc.contrib["group"] == "Direct process emissions"]
    assert not (bc_direct["key"] == "ammonia").any()
    assert (bc_direct["key"] == "carbon dioxide (biogenic)").any()


def test_stoichiometric_urea_dosing_reduces_impacts(data):
    lab = run_scenario("SP_lab_protocol_90d", data)
    opt = run_scenario("SP_optimised_stoichiometric", data)
    assert opt.meta["urea_kg_per_kg_solids"] < 0.15 * lab.meta["urea_kg_per_kg_solids"]
    assert opt.gwp() < lab.gwp()
    assert opt.totals(("A1", "A2", "A3"))["EP-terrestrial"] < 0.2 * lab.totals(("A1", "A2", "A3"))["EP-terrestrial"]


def test_lab_scale_energy_is_much_larger_than_industrial(data):
    lab = run_scenario("SP_lab_scale_energy_90d", data)
    ind = run_scenario("SP_lab_protocol_90d", data)
    assert lab.gwp() > 10 * ind.gwp()


def test_feather_hydrolysate_reduces_media_burden(data):
    med = run_scenario("BC_commercial_media_28d", data)
    fea = run_scenario("BC_feather_media", data)
    assert fea.by_group().loc["Cultivation: media", "GWP-total"] < med.by_group().loc["Cultivation: media", "GWP-total"]


def test_en15804_biogenic_carbon_closes_to_zero(data):
    r = run_scenario("GYP_WCFC_single_dose_EN15804", data)
    total_bio = r.totals(("A1", "A2", "A3", "C1", "C2", "C3", "C4"))["GWP-biogenic"]
    # biogenic uptake (A1) balanced by emissions (A3) and release of the stored carbon (C4) -> ~0
    assert abs(total_bio) < 1e-3
    ef = run_scenario("GYP_WCFC_single_dose", data)
    bg = ef.contrib[(ef.contrib["kind"] == "background") & ef.contrib["module"].isin(["A1", "A2", "A3"])]
    assert ef.totals(("A1", "A2", "A3"))["GWP-biogenic"] == pytest.approx(bg["GWP-biogenic"].sum())  # EF 3.1: biogenic CO2 = 0


def test_carbonation_uptake_is_negative_flow(data):
    r = run_scenario("GYP_WCFC_single_dose", data)
    up = r.contrib[r.contrib["group"] == "Carbonation uptake"]["GWP-total"].sum()
    assert up < 0
    assert abs(up) < 0.05


def test_module_d_credit_only_when_enabled(data):
    with_d = run_scenario("SP_optimised_struvite_D", data)
    without = run_scenario("SP_optimised_stoichiometric", data)
    assert with_d.totals(("D",))["GWP-total"] < 0
    assert without.totals(("D",))["GWP-total"] == 0


def test_abiotic_control_has_no_cultivation(data):
    r = run_scenario("ABIOTIC_WCFC_gypsum", data)
    assert "Cultivation: media" not in set(r.contrib["group"])
    assert r.inventory.caco3_kg_per_kg_solids == 0.0


def test_temperature_override_lowers_curing_heat(data):
    base = run_scenario("GYP_WCFC_single_dose", data)
    cold = run_scenario("GYP_WCFC_single_dose_20C", data)
    assert cold.by_group().loc["Curing: heat", "GWP-total"] < base.by_group().loc["Curing: heat", "GWP-total"]


def test_benchmarks_and_comparison(data):
    aac = benchmark_impacts("AAC_block_ODB", data, include_eol=False)
    assert 0.3 < aac["GWP-total"] < 0.7
    per_m3 = benchmark_impacts("AAC_block_ODB", data, functional_unit="m3_product", include_eol=False)
    assert per_m3["GWP-total"] == pytest.approx(aac["GWP-total"] * 428)
    fixed = benchmark_impacts("WCF_OPC_foamed_block", data, include_eol=True)
    assert fixed["GWP-total"] == pytest.approx(0.334)
    rs = [run_scenario(n, data) for n in ("GYP_WCFC_single_dose", "BC_lactate_30d")]
    table = compare_scenarios(rs, data)
    assert "AAC_block_ODB" in table.index and "GYP_WCFC_single_dose" in table.index
    sq = compare_with_status_quo(rs[0], data)
    assert sq["status_quo_basket"] > sq["landfill_of_absorbed_fines"] > 0


def test_material_override(data):
    h = run_scenario("SP_lab_protocol_90d", data)
    g = run_scenario("SP_lab_protocol_90d", data, overrides={"material": "wcf_g"})
    assert g.meta["material"] == "wcf_g"
    assert g.inventory.caco3_kg_per_kg_solids > h.inventory.caco3_kg_per_kg_solids


def test_coverage_reporting(data):
    r = run_scenario("GYP_WCFC_single_dose", data)
    assert 0 < r.coverage_native["AP"] < r.coverage["AP"] <= 1.0
    assert r.missing["PM"]   # generic ÖKOBAUDAT datasets do not report the additional indicators
