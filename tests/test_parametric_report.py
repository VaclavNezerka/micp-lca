"""Tests for custom compositions, the parametric sweep, the figure/PDF report modules and the rebuilt builder page."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from micp_lca import run_scenario
from micp_lca.cli import main
from micp_lca.parametric import apply_parameter, available_parameters, describe_sweep, find_parameter, sweep

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"


# ------------------------------------------------------------------------------------------ custom compositions
def test_custom_protocol_reproduces_predefined(data):
    proto = copy.deepcopy(data.protocols["pre_c_g_30_0"])
    r0 = run_scenario("GYP_WCFC_single_dose", data)
    r1 = run_scenario("GYP_WCFC_single_dose", data, overrides={"custom_protocol": proto})
    assert r1.gwp() == pytest.approx(r0.gwp(), rel=1e-9)


def test_custom_media_strain_material(data):
    lb = copy.deepcopy(data.media["lb_25"])
    lb["components"]["tryptone"] *= 0.5
    r = run_scenario("GYP_WCFC_single_dose", data, overrides={"custom_media": {"lb_25": lb}})
    assert r.gwp() < run_scenario("GYP_WCFC_single_dose", data).gwp()
    st = copy.deepcopy(data.strains["sutcliffiella_cohnii_DSM6307"])
    st["cultivation"]["medium"] = "nb_8"
    r2 = run_scenario("GYP_WCFC_single_dose", data, overrides={"custom_strains": {"sutcliffiella_cohnii_DSM6307": st}})
    assert r2.gwp() < r.gwp(), "a leaner cultivation medium must lower the footprint further"
    mat = copy.deepcopy(data.materials["wcf_c"])
    mat["portlandite_wt"] = 0.0
    r3 = run_scenario("GYP_WCFC_single_dose", data, overrides={"custom_materials": {"wcf_c": mat}})
    assert r3.meta["carbonation_uptake_kg_per_kg_solids"] == 0.0
    assert "custom" not in data.media, "inline definitions must not leak into the loaded bundle"


def test_custom_organism_with_new_pathway(data):
    """A user-defined ureolytic organism grown on NB with urea + CaCl2 in the solution."""
    organism = {"name": "My ureolytic isolate", "pathway": "ureolytic",
                "cultivation": {"medium": "nb_8", "temperature_C": 30, "duration_h": 24, "harvest_od600": 2.0, "harvest": "centrifugation", "resuspension_medium": "saline"}}
    proto = copy.deepcopy(data.protocols["pre_c_g_30_0"])
    proto["strain"] = "my_isolate"
    proto["biocementation_solution"]["supplements"] = {"urea": 20.0, "calcium_chloride": 11.0}
    proto["biocementation_solution"]["dosing"] = {"mode": "fixed", "n_doses": 5}
    r = run_scenario("GYP_WCFC_single_dose", data, overrides={"custom_protocol": proto, "custom_strains": {"my_isolate": organism}})
    assert r.meta["pathway"] == "ureolytic" and r.meta["carbonate_source"] == "urea"
    assert r.meta["n_hydrolysed_kg_per_kg_solids"] > 0
    assert r.totals(("A1", "A2", "A3"))["AP"] > run_scenario("GYP_WCFC_single_dose", data).totals(("A1", "A2", "A3"))["AP"]


# ------------------------------------------------------------------------------------------ parametric sweep
def test_available_parameters_and_apply(data):
    ps = available_parameters("SP_lab_protocol_90d", data)
    keys = {p.key for p in ps}
    assert {"protocol:biocementation_solution.dose_mL", "reagent:urea_to_ca_molar_ratio", "scenario:carbonation_uptake_fraction", "harvest_od600",
            "scaleup:industrial.curing_chamber.U_W_m2K", "medium:tsb_30.tryptone", "material:wcf_h.portlandite_wt"} <= keys
    for p in ps:
        assert p.hi > p.lo
    ov, po = apply_parameter("protocol:biocementation_solution.dosing.interval_h", 120.0, {"scale": "industrial"}, None, data, "SP_lab_protocol_90d")
    assert ov["protocol_overrides"]["biocementation_solution"]["dosing"]["interval_h"] == 120.0 and ov["scale"] == "industrial"
    ov, po = apply_parameter("scaleup:industrial.curing_chamber.U_W_m2K", 0.2, None, None, data, "SP_lab_protocol_90d")
    assert po == {"industrial.curing_chamber.U_W_m2K": 0.2}
    ov, _ = apply_parameter("medium:tsb_30.tryptone", 5.0, None, None, data, "SP_lab_protocol_90d")
    assert ov["custom_media"]["tsb_30"]["components"]["tryptone"] == 5.0
    with pytest.raises(KeyError):
        apply_parameter("nonsense:x", 1.0, None, None, data, "SP_lab_protocol_90d")


def test_sweep_monotonic_responses(data):
    df = sweep("SP_lab_protocol_90d", data, "reagent:urea_to_ca_molar_ratio", [1.0, 2.0, 4.0, 8.0], categories=["GWP-total", "AP"])
    assert list(df["value"]) == [1.0, 2.0, 4.0, 8.0]
    assert (df["error"] == "").all()
    assert df["GWP-total"].is_monotonic_increasing and df["AP"].is_monotonic_increasing
    assert df["urea_to_ca_molar_ratio"].tolist() == pytest.approx([1.0, 2.0, 4.0, 8.0])
    assert {"GWP-total +C", "cost_bulk_EUR", "cost_lab_EUR", "caco3_kg_per_kg_solids", "n_doses"} <= set(df.columns)
    d = describe_sweep(df, "GWP-total")
    assert d["monotonic"] == "increases" and d["x_of_y_min"] == 1.0 and 0 < d["r2_linear"] <= 1
    # fewer doses -> fewer reagents -> lower impact, and the CaCO3 cap is released when the reagents become limiting
    df2 = sweep("BC_lactate_30d", data, "protocol:biocementation_solution.dosing.interval_h", [24.0, 72.0, 168.0], categories=["GWP-total"])
    assert df2["GWP-total"].is_monotonic_decreasing and df2["n_doses"].is_monotonic_decreasing
    assert df2["caco3_kg_per_kg_solids"].iloc[-1] < df2["caco3_kg_per_kg_solids"].iloc[0]


def test_sweep_reports_errors_instead_of_crashing(data):
    df = sweep("SP_lab_protocol_90d", data, "protocol:biocementation_solution.dose_mL", [1.0, 5.0], functional_unit="m3_MPa", categories=["GWP-total"])
    assert (df["error"] != "").all(), "no strength -> m3_MPa not applicable, reported per point"


def test_sweep_parameter_values():
    from micp_lca.parametric import SweepParameter
    p = SweepParameter("k", "label", "-", 5.0, 1.0, 9.0, integer=True)
    assert p.values(5) == [1.0, 3.0, 5.0, 7.0, 9.0]
    assert p.values(3, 2.0, 4.0) == [2.0, 3.0, 4.0]


# ------------------------------------------------------------------------------------------ figures and PDF report
def test_figures(data, tmp_path):
    from micp_lca import figures
    from micp_lca.benchmarks import compare_scenarios
    r = run_scenario("SP_lab_protocol_90d", data)
    assert figures.contribution_by_group(r, "GWP-total", "kg CO2 eq", tmp_path / "c.png").stat().st_size > 5000
    assert figures.indicator_profile(r, ["GWP-total", "AP", "WDP"], tmp_path / "p.png").exists()
    assert figures.module_split(r, ["GWP-total", "AP"], tmp_path / "m.png").exists()
    tab = compare_scenarios([r], data, category="GWP-total")
    assert figures.benchmark_comparison(tab, "GWP-total", "kg CO2 eq", "kg", tmp_path / "b.png", highlight="SP_lab_protocol_90d").exists()
    assert figures.nitrogen_fate(r.meta["nitrogen_fate_kg_per_kg_solids"], tmp_path / "n.png").exists()
    assert figures.carbon_waterfall({"a": 1.0, "b": -0.2, "c": 0.5}, "kg CO2 eq", "kg", tmp_path / "w.png").exists()


def test_pdf_report(data, tmp_path):
    from micp_lca.pdfreport import ReportOptions, build_report
    ps = available_parameters("GYP_WCFC_single_dose", data)
    sp = find_parameter(ps, "protocol:biocementation_solution.dose_mL")
    sw = sweep("GYP_WCFC_single_dose", data, sp.key, sp.values(5), categories=["GWP-total", "GWP-fossil", "AP", "EP-terrestrial", "WDP"])
    out = build_report("GYP_WCFC_single_dose", data, tmp_path / "r.pdf",
                       options=ReportOptions(author="pytest", sweep=sw, sweep_parameter=sp, oat_top=6, comparison_scenarios=["BC_lactate_30d"]))
    assert out.exists() and out.stat().st_size > 200_000
    pypdf = pytest.importorskip("pypdf")
    reader = pypdf.PdfReader(str(out))
    assert len(reader.pages) >= 8
    text = "".join(p.extract_text() for p in reader.pages)
    for needle in ("1. Summary", "2. Goal and scope", "Life-cycle inventory", "impact assessment", "Parametric analysis", "One-at-a-time", "Indicative cost",
                   "Data quality", "Interpretation and conclusions", "References", "ISO 14040", "EN 15804", "Dose volume"):
        assert needle.lower() in text.lower(), needle
    # every citation number in the text has an entry in the reference list
    import re
    cited = {int(n) for m in re.findall(r"\[([0-9, ]+)\]", text) for n in m.split(",") if n.strip().isdigit()}
    listed = {int(n) for n in re.findall(r"\n\[(\d+)\] ", text)}
    assert cited and cited <= listed


def test_pdf_report_custom_composition(data, tmp_path):
    from micp_lca.pdfreport import build_report
    proto = copy.deepcopy(data.protocols["lit_eicp_30d"])
    proto["name"] = "custom EICP test"
    out = build_report("LIT_EICP", data, tmp_path / "custom.pdf", overrides={"custom_protocol": proto, "carbonation_uptake_fraction": 0.5})
    assert out.exists() and out.stat().st_size > 100_000


# ------------------------------------------------------------------------------------------ CLI
def test_cli_parameters_sweep_report(tmp_path):
    runner = CliRunner()
    res = runner.invoke(main, ["parameters", "BC_lactate_30d"])
    assert res.exit_code == 0 and "protocol:biocementation_solution.dose_mL" in res.output
    res = runner.invoke(main, ["sweep", "BC_lactate_30d", "-p", "scenario:carbonation_uptake_fraction", "--from", "0", "--to", "1", "--steps", "3", "--out", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "sweep_BC_lactate_30d_scenario_carbonation_uptake_fraction.csv").exists()
    res = runner.invoke(main, ["report", "ABIOTIC_WCFC_gypsum", "-o", str(tmp_path / "abiotic.pdf"), "--no-oat", "--steps", "3", "-p", "scenario:carbonation_uptake_fraction"])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "abiotic.pdf").stat().st_size > 100_000


# ------------------------------------------------------------------------------------------ builder page
pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


def _builder() -> AppTest:
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    return AppTest.from_file(str(APP / "pages" / "1_Scenario_builder.py"), default_timeout=900)


def test_builder_custom_mode_matches_template_and_sweeps():
    at = _builder().run()
    assert not at.exception
    gwp_pre = at.metric[0].value
    at.sidebar.radio[0].set_value("Custom composition").run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.metric[0].value == gwp_pre, "the pre-filled custom composition must reproduce the template"
    assert "sweep" in at.session_state and len(at.session_state["sweep"]["df"]) >= 3
    # change the dose volume in the custom editor -> result changes
    dose = [n for n in at.number_input if n.label.startswith("Dose volume")][0]
    dose.set_value(20.0).run()
    assert not at.exception
    assert at.metric[0].value != gwp_pre
    # switch the sweep to a scale-up parameter
    grp = [s for s in at.selectbox if s.label == "Parameter group"][0]
    grp.set_value("scale-up").run()
    assert not at.exception
    assert at.session_state["sweep"]["parameter"].key.startswith("scaleup:")


def test_builder_generates_pdf(monkeypatch, tmp_path):
    at = _builder().run()
    btn = [b for b in at.button if "Generate PDF" in b.label][0]
    btn.click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("Report written" in s.value for s in at.success)
    out = ROOT / "results" / "report_GYP_WCFC_single_dose.pdf"
    assert out.exists() and out.stat().st_size > 100_000
