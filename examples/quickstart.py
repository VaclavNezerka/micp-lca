"""Quick start: run the prototype recipe, compare with benchmarks, rank uncertainties.

    python examples/quickstart.py
"""
from micp_lca import load_data, run_scenario
from micp_lca.benchmarks import compare_scenarios, compare_with_status_quo
from micp_lca.sensitivity import oat_sensitivity
from micp_lca.uncertainty import MCSettings, monte_carlo

data = load_data()

# 1. one scenario, cradle-to-gate per kg of product
r = run_scenario("GYP_WCFC_single_dose", data)
print(f"{r.scenario}: {r.gwp():.3f} kg CO2e/kg (A1-A3), AP {r.totals(('A1','A2','A3'))['AP']:.4f} mol H+ eq/kg")
print(r.by_group()[["GWP-total", "AP", "EP-terrestrial"]].round(4))

# 2. the same recipe with feather-hydrolysate medium and at 20 °C
for name in ("GYP_WCFC_single_dose_feather", "GYP_WCFC_single_dose_20C"):
    print(f"{name}: {run_scenario(name, data).gwp():.3f} kg CO2e/kg")

# 3. benchmarks per m3 of block
rs = [run_scenario(n, data, functional_unit="m3_product") for n in ("GYP_WCFC_single_dose", "BC_lactate_30d", "SP_optimised_recirculation")]
print(compare_scenarios(rs, data, functional_unit="m3_product").round(1))

# 4. system expansion: block + waste disposal function
print(compare_with_status_quo(r, data, benchmark="AAC_block_ODB"))

# 5. what drives the result?
print(oat_sensitivity("GYP_WCFC_single_dose", data, top=8)[["input", "result_low", "result_high", "swing"]])
mc = monte_carlo("GYP_WCFC_single_dose", data, MCSettings(n=200, seed=1))
print(mc.percentiles().loc[["GWP-total", "AP"]])
print(mc.spearman("GWP-total", top=6))
