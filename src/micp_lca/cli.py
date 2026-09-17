"""Command-line interface: ``micp-lca --help``."""
from __future__ import annotations

import json
from pathlib import Path

import click
import pandas as pd

from . import __version__
from .benchmarks import compare_scenarios, compare_with_status_quo
from .db import build_database, query, store_results
from .export import inventory_table, to_brightway
from .lcia import run_scenario
from .loaders import load_data
from .paths import results_dir
from .report import (markdown_table, plot_contributions, plot_mc_histogram, plot_scenario_comparison, plot_tornado,
                     write_results)
from .sensitivity import oat_sensitivity
from .uncertainty import MCSettings, monte_carlo

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)


@click.group()
@click.version_option(__version__)
def main() -> None:
    """LCA toolkit for MICP-based recycling of waste concrete fines and sub-sieve demolition residues."""


@main.command("build-db")
@click.option("--path", type=click.Path(), default=None, help="Output SQLite file (default data/db/micp_lca.sqlite)")
def build_db(path: str | None) -> None:
    """Build the SQLite database from the YAML/CSV data files."""
    p = build_database(path)
    click.echo(f"database written to {p}")


@main.command("list")
def list_items() -> None:
    """List scenarios, protocols, materials, strains and benchmarks."""
    data = load_data()
    click.echo("Scenarios:")
    for k, v in data.scenarios["scenarios"].items():
        click.echo(f"  {k:32s} {v.get('description', '')}")
    click.echo("Benchmarks:")
    for k, v in data.scenarios["benchmarks"].items():
        click.echo(f"  {k:32s} {v.get('description', '')}")
    click.echo("Protocols: " + ", ".join(data.protocols))
    click.echo("Materials: " + ", ".join(data.materials))
    click.echo("Strains:   " + ", ".join(data.strains))


@main.command()
@click.argument("scenario")
@click.option("--fu", "functional_unit", default=None, help="kg_product | m3_product | kg_solids | kg_caco3_precipitated | m3_MPa")
@click.option("--material", default=None, help="override the material (e.g. wcf_g)")
@click.option("--scale", default=None, type=click.Choice(["lab", "industrial"]))
@click.option("--category", default="GWP-total")
@click.option("--json", "as_json", is_flag=True, help="print the summary as JSON")
def run(scenario: str, functional_unit: str | None, material: str | None, scale: str | None, category: str, as_json: bool) -> None:
    """Run one scenario and print totals and contributions."""
    data = load_data()
    overrides = {k: v for k, v in (("material", material), ("scale", scale)) if v}
    r = run_scenario(scenario, data, functional_unit=functional_unit, overrides=overrides)
    if as_json:
        click.echo(json.dumps(r.summary(), indent=2, default=float))
        return
    click.echo(f"Scenario {r.scenario} — functional unit: {r.functional_unit}")
    click.echo(f"Product: {r.inventory.product_kg_per_kg_solids:.3f} kg per kg solids; CaCO3 precipitated "
               f"{r.inventory.caco3_kg_per_kg_solids:.4f} kg/kg solids; fc = {r.inventory.fc_MPa} MPa")
    tot = pd.DataFrame({"A1-A3": r.totals(("A1", "A2", "A3")), "C1-C4": r.totals(("C1", "C2", "C3", "C4")), "D": r.totals(("D",))})
    tot["unit"] = [r.units[c] for c in tot.index]
    tot["coverage"] = [f"{r.coverage[c]:.0%}" for c in tot.index]
    click.echo(tot.to_string(float_format=lambda v: f"{v:.4g}"))
    click.echo(f"\nContributions to {category} (A1–A3 + C + D):")
    click.echo(r.contributions(category).to_string(float_format=lambda v: f"{v:.4g}"))
    if r.meta.get("reaction_notes"):
        click.echo("\nNotes: " + "; ".join(r.meta["reaction_notes"]))


@main.command("run-all")
@click.option("--fu", "functional_unit", default="kg_product")
@click.option("--out", default=None, help="output directory (default results/)")
@click.option("--store", is_flag=True, help="also store results in the SQLite database")
@click.option("--category", default="GWP-total")
def run_all(functional_unit: str, out: str | None, store: bool, category: str) -> None:
    """Run every scenario, write CSV tables and comparison figures."""
    data = load_data()
    out_dir = Path(out) if out else results_dir()
    results = []
    for name in data.scenarios["scenarios"]:
        try:
            results.append(run_scenario(name, data, functional_unit=functional_unit))
        except ValueError as exc:  # e.g. FU not applicable
            click.echo(f"skipped {name}: {exc}")
    paths = write_results(results, out_dir)
    table = compare_scenarios(results, data, category=category, functional_unit=functional_unit)
    table.to_csv(out_dir / f"comparison_{category.replace('&', 'and')}_{functional_unit}.csv")
    fig = plot_scenario_comparison(table, category, results[0].units[category], out_dir / f"comparison_{category.replace('&', 'and')}_{functional_unit}.png")
    click.echo(markdown_table(table))
    click.echo(f"\nwritten: {paths['summary']}, {paths['en15804']}, {fig}")
    if store:
        store_results(results, run_id=pd.Timestamp.now().strftime("run_%Y%m%d_%H%M%S"))
        click.echo("results stored in the database")


@main.command()
@click.argument("scenario")
@click.option("--category", default="GWP-total")
@click.option("--fu", "functional_unit", default=None)
@click.option("--out", default=None)
def contributions(scenario: str, category: str, functional_unit: str | None, out: str | None) -> None:
    """Contribution analysis figure for one scenario."""
    data = load_data()
    r = run_scenario(scenario, data, functional_unit=functional_unit)
    out_dir = Path(out) if out else results_dir()
    p = plot_contributions(r, category, out_dir / f"contrib_{scenario}_{category.replace('&', 'and')}.png")
    click.echo(r.by_group()[[category]].to_string(float_format=lambda v: f"{v:.4g}"))
    click.echo(f"figure: {p}")


@main.command()
@click.argument("scenario")
@click.option("--category", default="GWP-total")
@click.option("--top", default=15)
@click.option("--out", default=None)
def sensitivity(scenario: str, category: str, top: int, out: str | None) -> None:
    """One-at-a-time sensitivity (tornado) for one scenario."""
    data = load_data()
    df = oat_sensitivity(scenario, data, category=category, top=top,
                         extra_scenario_keys={"effluent_treatment": ["ammonia_stripping", "struvite"], "scale": ["lab"],
                                              "electricity": ["electricity_DE_lv"], "carbon_accounting": ["EN15804A2"]})
    out_dir = Path(out) if out else results_dir()
    df.to_csv(out_dir / f"sensitivity_{scenario}_{category.replace('&', 'and')}.csv", index=False)
    unit = load_data().category_unit(category)
    p = plot_tornado(df, category, unit, out_dir / f"tornado_{scenario}_{category.replace('&', 'and')}.png", top=top)
    click.echo(df[["input", "low", "high", "result_low", "result_high", "swing"]].to_string(float_format=lambda v: f"{v:.4g}"))
    click.echo(f"figure: {p}")


@main.command("monte-carlo")
@click.argument("scenario")
@click.option("-n", "n", default=500, show_default=True)
@click.option("--seed", default=42)
@click.option("--category", default="GWP-total")
@click.option("--out", default=None)
def monte_carlo_cmd(scenario: str, n: int, seed: int, category: str, out: str | None) -> None:
    """Monte Carlo uncertainty propagation for one scenario."""
    data = load_data()
    mc = monte_carlo(scenario, data, MCSettings(n=n, seed=seed), progress=lambda i: click.echo(f"  {i}/{n}", err=True))
    out_dir = Path(out) if out else results_dir()
    mc.category_samples.to_csv(out_dir / f"mc_samples_{scenario}.csv", index=False)
    pct = mc.percentiles()
    pct.to_csv(out_dir / f"mc_percentiles_{scenario}.csv")
    click.echo(pct.to_string(float_format=lambda v: f"{v:.4g}"))
    click.echo("\nSpearman rank correlations (global sensitivity):")
    sp = mc.spearman(category, top=25)
    sp.rename("spearman_rho").to_csv(out_dir / f"mc_spearman_{scenario}_{category.replace('&', 'and')}.csv", index_label="input")
    click.echo(sp.to_string(float_format=lambda v: f"{v:.3f}"))
    p = plot_mc_histogram(mc.category_samples[category], data.category_unit(category), out_dir / f"mc_{scenario}_{category.replace('&', 'and')}.png")
    click.echo(f"figure: {p}")


@main.command("status-quo")
@click.argument("scenario")
@click.option("--benchmark", default="AAC_block_ODB")
@click.option("--category", default="GWP-total")
def status_quo(scenario: str, benchmark: str, category: str) -> None:
    """System-expansion comparison with 'conventional block + landfilling of the fines'."""
    data = load_data()
    r = run_scenario(scenario, data, functional_unit="kg_product")
    for k, v in compare_with_status_quo(r, data, benchmark, category).items():
        click.echo(f"{k:40s} {v:10.4g} {r.units[category]}/kg product")


@main.command()
@click.argument("scenario")
@click.option("--format", "fmt", type=click.Choice(["csv", "brightway"]), default="csv")
@click.option("--out", default=None)
def export(scenario: str, fmt: str, out: str | None) -> None:
    """Export the foreground inventory (CSV with ecoinvent proxies, or Brightway database dict as JSON)."""
    data = load_data()
    r = run_scenario(scenario, data)
    out_dir = Path(out) if out else results_dir()
    if fmt == "csv":
        p = out_dir / f"inventory_{scenario}.csv"
        inventory_table(r, data).to_csv(p, index=False)
    else:
        p = out_dir / f"brightway_{scenario}.json"
        bw = to_brightway(r, data)
        p.write_text(json.dumps({f"{k[0]}|{k[1]}": v for k, v in bw.items()}, indent=2, default=str), encoding="utf-8")
    click.echo(f"written {p}")


@main.command("parameters")
@click.argument("scenario")
def parameters(scenario: str) -> None:
    """List the parameters that can be swept for a scenario (key, current value, default limits)."""
    from .parametric import available_parameters
    data = load_data()
    for p in available_parameters(scenario, data):
        click.echo(f"{p.key:70s} {p.value:10.4g}  [{p.lo:.4g}, {p.hi:.4g}] {p.unit:10s} {p.label}")


@main.command("sweep")
@click.argument("scenario")
@click.option("--parameter", "-p", required=True, help="Parameter key, see `micp-lca parameters SCENARIO`")
@click.option("--from", "lo", type=float, default=None, help="Lower limit (default: registry)")
@click.option("--to", "hi", type=float, default=None, help="Upper limit (default: registry)")
@click.option("--steps", default=11, show_default=True)
@click.option("--functional-unit", "functional_unit", default=None)
@click.option("--out", default=None)
def sweep_cmd(scenario: str, parameter: str, lo: float | None, hi: float | None, steps: int, functional_unit: str | None, out: str | None) -> None:
    """Vary one parameter between limits and tabulate/plot the response of all indicators and the cost."""
    from . import figures
    from .parametric import available_parameters, find_parameter, sweep
    data = load_data()
    sp = find_parameter(available_parameters(scenario, data), parameter)
    if sp is None:
        raise click.ClickException(f"unknown parameter '{parameter}' for {scenario}; run `micp-lca parameters {scenario}`")
    values = sp.values(steps, lo, hi)
    df = sweep(scenario, data, parameter, values, functional_unit=functional_unit)
    out_dir = Path(out) if out else results_dir()
    tag = parameter.replace(":", "_").replace(".", "_").replace("&", "and")
    csv = out_dir / f"sweep_{scenario}_{tag}.csv"
    df.to_csv(csv, index=False)
    cols = [c for c in ["value", "GWP-total", "AP", "EP-terrestrial", "WDP", "cost_bulk_EUR", "caco3_kg_per_kg_solids", "n_doses"] if c in df]
    click.echo(df[cols].to_string(index=False, float_format=lambda v: f"{v:.4g}"))
    panels = [("GWP-total", f"GWP-total [{data.category_unit('GWP-total')}]"), ("AP", f"AP [{data.category_unit('AP')}]"),
              ("EP-terrestrial", f"EP-terrestrial [{data.category_unit('EP-terrestrial')}]"), ("cost_bulk_EUR", "cost, bulk grade [EUR]")]
    fig = figures.sweep_panels(df, f"{sp.label} [{sp.unit}]", sp.value, panels, out_dir / f"sweep_{scenario}_{tag}.png", df["functional_unit"].iloc[0] if "functional_unit" in df else "")
    click.echo(f"written {csv}")
    click.echo(f"figure: {fig}")


@main.command("report")
@click.argument("scenario")
@click.option("--out", "-o", default=None, help="Output PDF (default results/report_<scenario>.pdf)")
@click.option("--functional-unit", "functional_unit", default=None)
@click.option("--parameter", "-p", default=None, help="Parameter to sweep for the parametric section (see `micp-lca parameters`)")
@click.option("--from", "lo", type=float, default=None)
@click.option("--to", "hi", type=float, default=None)
@click.option("--steps", default=9, show_default=True)
@click.option("--mc", "n_mc", default=0, show_default=True, help="Monte Carlo samples (0 = none)")
@click.option("--compare", "compare", multiple=True, help="Other scenarios to show in the comparison figure (repeatable)")
@click.option("--no-oat", is_flag=True, help="Skip the one-at-a-time tornado")
@click.option("--author", default="")
@click.option("--organisation", default="")
@click.option("--title", default=None)
def report_cmd(scenario: str, out: str | None, functional_unit: str | None, parameter: str | None, lo: float | None, hi: float | None,
               steps: int, n_mc: int, compare: tuple[str, ...], no_oat: bool, author: str, organisation: str, title: str | None) -> None:
    """Write a PDF report (goal & scope, system, inventory, LCIA, comparison, sensitivity, cost, data quality, references)."""
    from .parametric import available_parameters, find_parameter, sweep
    from .pdfreport import ReportOptions, build_report
    data = load_data()
    opt = ReportOptions(title=title, author=author, organisation=organisation, functional_unit=functional_unit,
                        comparison_scenarios=list(compare), include_oat=not no_oat)
    if parameter:
        sp = find_parameter(available_parameters(scenario, data), parameter)
        if sp is None:
            raise click.ClickException(f"unknown parameter '{parameter}'")
        opt.sweep_parameter = sp
        opt.sweep = sweep(scenario, data, parameter, sp.values(steps, lo, hi), functional_unit=functional_unit)
    if n_mc:
        opt.mc = monte_carlo(scenario, data, MCSettings(n=n_mc), functional_unit=functional_unit,
                             progress=lambda i: click.echo(f"  MC {i}/{n_mc}", err=True))
    out_path = Path(out) if out else results_dir() / f"report_{scenario}.pdf"
    p = build_report(scenario, data, out_path, options=opt)
    click.echo(f"written {p}")


@main.command("sql")
@click.argument("statement")
def sql(statement: str) -> None:
    """Run a SQL query against the database, e.g. "SELECT * FROM background_processes"."""
    click.echo(query(statement).to_string())


if __name__ == "__main__":
    main()
