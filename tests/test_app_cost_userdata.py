"""Tests for the cost module, the user-data merge and the Streamlit application pages."""
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest
import yaml

from micp_lca import load_data, run_scenario
from micp_lca.cost import cost_summary, cost_table
from micp_lca.paths import data_dir

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"


# ------------------------------------------------------------------------------------------ cost
def test_cost_table_and_summary(data):
    r = run_scenario("GYP_WCFC_single_dose", data)
    ct = cost_table(r, data, "bulk")
    assert {"module", "group", "process_id", "amount", "cost_eur", "priced"} <= set(ct.columns)
    assert ct["priced"].mean() > 0.9, "most inventory flows should carry an indicative price"
    cb, cl = cost_summary(r, data, "bulk"), cost_summary(r, data, "lab")
    assert 0.0 < cb["total_A1-A3"] < 5.0
    assert cl["total_A1-A3"] > cb["total_A1-A3"], "laboratory-grade media must cost more than bulk"
    assert cb["total_C1-C4"] > 0
    assert cb["functional_unit"] == "kg_product"


def test_feather_hydrolysate_reduces_cost(data):
    base = cost_summary(run_scenario("GYP_WCFC_single_dose", data), data, "bulk")["total_A1-A3"]
    feather = cost_summary(run_scenario("GYP_WCFC_single_dose_feather", data), data, "bulk")["total_A1-A3"]
    assert feather < 0.6 * base, "feather hydrolysate should cut the media cost substantially (Ottová et al. 2026: −80 %)"


# ------------------------------------------------------------------------------------------ literature pathways
@pytest.mark.parametrize("scenario", ["LIT_SP_NH4YE_medium", "LIT_SP_corn_steep_liquor", "LIT_SP_manure_effluent", "LIT_EICP",
                                      "LIT_denitrification", "LIT_acetate_oxidation", "LIT_photosynthetic"])
def test_literature_pathways_run(data, scenario):
    r = run_scenario(scenario, data)
    assert r.gwp() > 0
    assert r.meta["caco3_precipitated_kg_per_kg_solids"] > 0
    per_caco3 = run_scenario(scenario, data, functional_unit="kg_caco3_precipitated").gwp()
    assert per_caco3 == pytest.approx(r.gwp() * r.inventory.product_kg_per_kg_solids / r.meta["caco3_precipitated_kg_per_kg_solids"], rel=1e-6)


def test_literature_results_table(data):
    lit = data.literature_results
    assert len(lit) >= 20
    assert set(lit["source_id"]) <= set(data.sources), "every literature result must cite a registered source"
    porter = lit[(lit["source_id"] == "PORTER2021") & (lit["indicator"] == "GWP") & (lit["pathway_or_variant"] == "urea hydrolysis")]
    assert porter["value"].max() == pytest.approx(2.06)


# ------------------------------------------------------------------------------------------ user data merge
@pytest.fixture
def user_data_root(tmp_path):
    """A copy of the data folder with user additions in data/user."""
    src = data_dir()
    dst = tmp_path / "data"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("*.sqlite", "raw", "__pycache__"))
    user = dst / "user"
    user.mkdir(exist_ok=True)
    (user / "background_processes.csv").write_text(
        "process_id,name,unit,category,geography,reference_year,data_type,source_id,gwp_fossil,gwp_min,gwp_max,adp_fossil_MJ,ecoinvent_proxy,"
        "profile_proxy,pedigree_R,pedigree_C,pedigree_T,pedigree_G,pedigree_F,basic_uncertainty,notes,AP\n"
        "my_urea,Urea (supplier EPD),kg,chemical,CZ,2025,user,INDICATIVE,0.5,,,,,,1,1,1,1,1,1.05,test,0.004\n"
        "yeast_extract,Yeast extract (overridden),kg,medium_component,RER,2025,user,INDICATIVE,3.0,,,,,,2,2,2,2,2,1.05,override,\n",
        encoding="utf-8")
    (user / "chemicals.yaml").write_text(yaml.safe_dump({"my_urea": {"name": "Urea (supplier)", "formula": "CO(NH2)2", "molar_mass": 60.06,
                                                                       "carbon_content": 0.2, "carbon_origin": "fossil", "nitrogen_content": 0.4665,
                                                                       "background_process": "my_urea"}}), encoding="utf-8")
    (user / "scenarios.yaml").write_text(yaml.safe_dump({"scenarios": {"USER_TEST": {"description": "user scenario", "protocol": "pre_c_g_30_0",
                                                                                       "scaleup_overrides": {"industrial.curing_chamber.U_W_m2K": 0.2}}}}),
                                         encoding="utf-8")
    (user / "prices.csv").write_text("process_id,unit,price_bulk_eur,price_bulk_min,price_bulk_max,price_lab_eur,currency_year,source_id,notes\n"
                                     "electricity_CZ_lv,kWh,0.99,,,0.99,2025,USER,test\n", encoding="utf-8")
    return dst


def test_user_data_is_merged(user_data_root):
    d = load_data(user_data_root)
    assert "my_urea" in d.background and d.background["my_urea"].gwp == pytest.approx(0.5)
    assert d.background["my_urea"].factor("AP") == pytest.approx(0.004), "extra category columns are read as native factors"
    assert d.background["yeast_extract"].gwp == pytest.approx(3.0), "user rows override curated ids"
    assert "[user-defined]" in d.background["yeast_extract"].notes
    assert "my_urea" in d.chemicals
    assert "USER_TEST" in d.scenarios["scenarios"]
    assert float(d.prices.loc[d.prices["process_id"] == "electricity_CZ_lv", "price_bulk_eur"].iloc[0]) == pytest.approx(0.99)
    assert d.prices["process_id"].is_unique


def test_scaleup_overrides_in_user_scenario(user_data_root):
    d = load_data(user_data_root)
    base = run_scenario("GYP_WCFC_single_dose", d)
    user = run_scenario("USER_TEST", d)
    assert user.gwp() < base.gwp(), "a better-insulated curing chamber (U 0.2 vs 0.35) must lower the heat demand"
    assert run_scenario("USER_TEST", d, param_overrides={"industrial.curing_chamber.U_W_m2K": 0.35}).gwp() == pytest.approx(base.gwp(), rel=1e-6)


# ------------------------------------------------------------------------------------------ Streamlit pages
pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = ["Home.py"] + sorted(p.name for p in (APP / "pages").glob("*.py"))


def _app(page: str) -> AppTest:
    import sys
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    path = APP / page if page == "Home.py" else APP / "pages" / page
    return AppTest.from_file(str(path), default_timeout=600)


@pytest.mark.parametrize("page", PAGES)
def test_pages_render_without_exception(page):
    at = _app(page).run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not at.error, [str(e) for e in at.error]


def test_scenario_builder_reacts_to_inputs():
    at = _app("1_Scenario_builder.py").run()
    gwp_text = at.metric[0].value
    # switch to the laboratory energy model (Technology & system tab)
    energy = [r for r in at.radio if r.label == "Energy model"][0]
    energy.set_value("lab").run()
    assert not at.exception
    assert at.metric[0].value != gwp_text, "the lab energy model must change the GWP"


def test_compare_page_strength_normalised_fu():
    at = _app("2_Compare.py").run()
    at.selectbox[0].set_value("m3_MPa").run()
    assert not at.exception
    # scenarios without a measured strength are reported as warnings rather than crashing the page
    assert len(at.dataframe) >= 2


def test_uncertainty_monte_carlo_button():
    at = _app("3_Uncertainty.py").run()
    at.select_slider[0].set_value(100)
    at.button[0].click().run()
    assert not at.exception
    assert any("Median" in m.label for m in at.metric)


def test_data_editor_writes_user_files(tmp_path, monkeypatch, user_data_root):
    monkeypatch.setenv("MICP_LCA_DATA", str(user_data_root))
    import utils as app_utils  # app/utils.py (sys.path set by _app)
    _app("Home.py")
    app_utils.reload_data()          # drop the cached bundle so the page loads the temporary data root
    at = _app("5_Data_editor.py").run()
    assert not at.exception
    # add a source through the form
    form = at.text_input
    src_id = [t for t in form if t.label.startswith("source_id")][0]
    src_id.set_value("TESTSRC2026")
    cit = [t for t in form if t.label == "Citation"][0]
    cit.set_value("Test citation (2026)")
    [b for b in at.button if "Save source" in b.label][0].click().run()
    assert not at.exception
    saved = pd.read_csv(user_data_root / "user" / "sources.csv")
    assert "TESTSRC2026" in set(saved["source_id"])
    real = ROOT / "data" / "user" / "sources.csv"        # the project's own user folder must stay untouched
    assert not real.exists() or "TESTSRC2026" not in real.read_text(encoding="utf-8")
    app_utils.reload_data()
