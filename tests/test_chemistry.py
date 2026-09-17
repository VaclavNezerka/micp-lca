import math

import pytest

from micp_lca import chemistry as chem


def test_stoichiometric_caco3_from_urea_and_cacl2():
    b = chem.ReagentBalance(ca_mol=1.0, urea_mol=13.0, chloride_mol=2.0, carbonate_source="urea", ca_source="CaCl2")
    theo, expected = chem.caco3_stoichiometry(b, efficiency=0.8)
    assert abs(theo - 0.10009) < 1e-6           # 1 mol CaCO3 = 100.09 g
    assert abs(expected - 0.08007) < 1e-5


def test_van_paassen_ratio():
    """0.6 kg urea and 1.1 kg CaCl2 per kg CaCO3 (van Paassen et al. 2010)."""
    kg_caco3 = 1.0
    mol = kg_caco3 * 1000 / chem.M["CaCO3"]
    assert abs(mol * chem.M["urea"] / 1000 - 0.60) < 0.01
    assert abs(mol * chem.M["CaCl2"] / 1000 - 1.11) < 0.01


def test_urea_carbon_and_nitrogen_balance():
    b = chem.ReagentBalance(ca_mol=1.0, urea_mol=2.0, carbonate_source="urea", ca_source="CaCl2")
    out = chem.react(b, urea_hydrolysed_fraction=1.0)
    # 2 mol urea hydrolysed: 1 mol C stored in CaCO3, 1 mol C emitted as fossil CO2
    assert abs(out.c_stored_fossil_kg - chem.M["CO2"] / 1000) < 1e-9
    assert abs(out.co2_fossil_kg - chem.M["CO2"] / 1000) < 1e-9
    assert abs(out.n_hydrolysed_kg - 4 * chem.M["N"] / 1000) < 1e-9
    assert out.urea_unhydrolysed_kg == 0.0
    # carbon closure: C in urea = C stored + C emitted
    c_in = 2.0 * chem.M["C"] / 1000
    c_out = (out.c_stored_fossil_kg + out.co2_fossil_kg) * chem.M["C"] / chem.M["CO2"]
    assert abs(c_in - c_out) < 1e-9


def test_urea_co2_release_factor_matches_ipcc():
    # IPCC 2019: 0.20 kg C per kg urea -> 0.733 kg CO2 per kg urea
    assert abs(chem.CO2_PER_UREA_HYDROLYSED - 0.733) < 0.001
    assert abs(chem.N_PER_UREA - 0.4665) < 0.001


def test_lactate_route_carbon_split():
    # 1 mol Ca-lactate = 2 mol lactate = 6 mol C; 1 mol CaCO3 -> 1/6 stored, 5/6 emitted biogenic
    b = chem.ReagentBalance(ca_mol=1.0, organic_mol=2.0, organic_kind="lactate", carbonate_source="organic", ca_source="CaLactate")
    out = chem.react(b, lactate_oxidised_fraction=1.0)
    assert abs(out.c_stored_biogenic_kg - chem.M["CO2"] / 1000) < 1e-9
    assert abs(out.co2_biogenic_kg - 5 * chem.M["CO2"] / 1000) < 1e-9
    assert out.co2_fossil_kg == 0.0


def test_acetate_route_and_denitrification():
    # 1 mol Ca-acetate (petrochemical): 4 C, 1 stored, 3 emitted as fossil CO2
    b = chem.ReagentBalance(ca_mol=1.0, organic_mol=2.0, organic_kind="acetate", organic_c_origin="fossil", carbonate_source="organic")
    out = chem.react(b, lactate_oxidised_fraction=1.0)
    assert abs(out.c_stored_fossil_kg - chem.M["CO2"] / 1000) < 1e-9
    assert abs(out.co2_fossil_kg - 3 * chem.M["CO2"] / 1000) < 1e-9
    assert out.organic_effluent_flow == "acetic acid"
    # denitrification: nitrate-N to N2 with residual nitrate
    b = chem.ReagentBalance(ca_mol=2.0, organic_mol=2.0, organic_kind="acetate", organic_c_origin="biogenic",
                            nitrate_mol=1.6, carbonate_source="organic")
    out = chem.react(b, nitrate_denitrified_fraction=0.9)
    assert abs(out.nitrate_n_denitrified_kg - 1.6 * 0.9 * chem.M["N"] / 1000) < 1e-9
    assert abs(out.nitrate_residual_kg - 1.6 * 0.1 * chem.M["NO3"] / 1000) < 1e-9


def test_inorganic_carbon_route():
    b = chem.ReagentBalance(ca_mol=1.0, bicarbonate_mol=0.5, carbonate_source="inorganic")
    theo, _ = chem.caco3_stoichiometry(b)
    assert abs(theo - 0.5 * chem.M["CaCO3"] / 1000) < 1e-9
    out = chem.react(b)
    assert abs(out.c_stored_geogenic_kg - 0.5 * chem.M["CO2"] / 1000) < 1e-9


def test_measured_gain_capped_by_calcium_supply():
    b = chem.ReagentBalance(ca_mol=0.5, urea_mol=1.0, carbonate_source="urea")
    out = chem.react(b, measured_caco3_kg=0.2)
    assert abs(out.caco3_precipitated_kg - 0.5 * chem.M["CaCO3"] / 1000) < 1e-9
    assert out.notes


def test_nitrogen_fate_closure():
    f = chem.nitrogen_fate(1.0, fraction_drained=0.4, nh3_volatilised_fraction=0.8, n2o_fraction=0.01, treatment_efficiency=0.9)
    n_out = (f["nh4_to_water"] * chem.M["N"] / chem.M["NH4"] + f["nh3_to_air"] * chem.M["N"] / chem.M["NH3"]
             + f["n2o_to_air"] * 2 * chem.M["N"] / chem.M["N2O"] + f["n_recovered"] + f["n_retained_in_product"])
    assert abs(n_out - 1.0) < 1e-9
    assert f["n_recovered"] == pytest.approx(0.99 * 0.4 * 0.9)


def test_carbonation_uptake():
    assert abs(chem.carbonation_uptake_kg(1.0, 1.0) - 0.594) < 0.001
