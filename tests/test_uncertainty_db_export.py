from __future__ import annotations

import json
import math

import pytest
from click.testing import CliRunner

from micp_lca import run_scenario
from micp_lca.cli import main
from micp_lca.db import build_database, query, store_results
from micp_lca.export import inventory_table, to_brightway
from micp_lca.sensitivity import oat_sensitivity
from micp_lca.uncertainty import CIROTH_2016, ECOINVENT_V2, MCSettings, monte_carlo, pedigree_gsd


def test_pedigree_gsd():
    assert pedigree_gsd((1, 1, 1, 1, 1), 1.0) == pytest.approx(1.0)
    assert pedigree_gsd((1, 1, 1, 1, 1), 1.05) == pytest.approx(1.05)
    g = pedigree_gsd((3, 3, 3, 2, 3), 1.05, CIROTH_2016)
    expect = math.exp(math.sqrt(sum(math.log(x) ** 2 for x in (1.61, 1.04, 1.10, 1.04, 1.65, 1.05))))
    assert g == pytest.approx(expect)
    assert pedigree_gsd((5, 5, 5, 5, 5), 1.05, ECOINVENT_V2) < pedigree_gsd((5, 5, 5, 5, 5), 1.05, CIROTH_2016)


def test_monte_carlo_runs(data):
    mc = monte_carlo("GYP_WCFC_single_dose", data, MCSettings(n=40, seed=1))
    assert len(mc.category_samples) == 40
    p = mc.percentiles()
    assert p.loc["GWP-total", 0.025] < p.loc["GWP-total", 0.5] < p.loc["GWP-total", 0.975]
    s = mc.spearman("GWP-total", top=5)
    assert len(s) == 5 and all(abs(v) <= 1 for v in s.values)


def test_oat_sensitivity(data):
    df = oat_sensitivity("SP_optimised_stoichiometric", data, top=10)
    assert len(df) == 10
    assert (df["swing"] >= 0).all()
    assert df["swing"].is_monotonic_decreasing


def test_database_roundtrip(tmp_path, data):
    p = build_database(tmp_path / "test.sqlite", data)
    df = query("SELECT COUNT(*) AS n FROM background_processes", p)
    assert int(df["n"].iloc[0]) == len(data.background)
    r = run_scenario("GYP_WCFC_single_dose", data)
    store_results([r], "test_run", p)
    res = query("SELECT value FROM results WHERE scenario='GYP_WCFC_single_dose' AND category_code='GWP-total' AND modules='A1-A3'", p)
    assert float(res["value"].iloc[0]) == pytest.approx(r.gwp())


def test_exports(data, tmp_path):
    r = run_scenario("BC_lactate_30d", data)
    df = inventory_table(r, data)
    assert {"technosphere", "biosphere"} <= set(df["type"])
    assert (df["ecoinvent_proxy"] != "").all()
    bw = to_brightway(r, data)
    key = next(iter(bw))
    assert bw[key]["exchanges"][0]["type"] == "production"
    json.dumps({f"{k[0]}|{k[1]}": v for k, v in bw.items()}, default=str)


def test_cli_smoke(tmp_path):
    runner = CliRunner()
    assert runner.invoke(main, ["list"]).exit_code == 0
    res = runner.invoke(main, ["run", "GYP_WCFC_single_dose", "--json"])
    assert res.exit_code == 0, res.output
    out = json.loads(res.output)
    assert "GWP-total [A1-A3]" in out
    res = runner.invoke(main, ["run", "GYP_WCFC_single_dose", "--fu", "m3_product"])
    assert res.exit_code == 0, res.output
    res = runner.invoke(main, ["status-quo", "GYP_WCFC_single_dose"])
    assert res.exit_code == 0, res.output
