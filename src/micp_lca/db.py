"""SQLite database built from the plain-text data files.

The database (``data/db/micp_lca.sqlite``) is a derived artefact: the YAML/CSV files remain the
single source of truth. It is convenient for ad-hoc SQL queries, for sharing with colleagues who
do not use Python, and for archiving a frozen snapshot of the data used in a publication.

Tables
------
sources, impact_categories, characterization_factors, background_processes, background_impacts,
chemicals, media, medium_components, strains, materials, material_processing, protocols,
protocol_reagents, scenarios, benchmarks, scaleup_parameters, experimental_results, prices,
literature_results, and (after ``store_results``) results and result_contributions.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .lcia import Results
from .loaders import DataBundle, load_data
from .paths import data_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (source_id TEXT PRIMARY KEY, type TEXT, citation TEXT, doi_or_url TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS impact_categories (code TEXT PRIMARY KEY, ef31_name TEXT, unit TEXT, ef31_method_uuid TEXT, en15804_a2_indicator TEXT, core_or_additional TEXT);
CREATE TABLE IF NOT EXISTS characterization_factors (flow_uuid TEXT, flow_name TEXT, compartment TEXT, ef31_class2 TEXT, category_code TEXT, cf REAL, location TEXT, method_uuid TEXT, derivation TEXT);
CREATE TABLE IF NOT EXISTS background_processes (process_id TEXT PRIMARY KEY, name TEXT, unit TEXT, category TEXT, geography TEXT, reference_year INTEGER, data_type TEXT, source_id TEXT, gwp_min REAL, gwp_max REAL, pedigree TEXT, basic_uncertainty REAL, ecoinvent_proxy TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS background_impacts (process_id TEXT, module TEXT, category_code TEXT, value REAL, unit TEXT, PRIMARY KEY (process_id, module, category_code));
CREATE TABLE IF NOT EXISTS chemicals (chemical_id TEXT PRIMARY KEY, name TEXT, formula TEXT, molar_mass REAL, carbon_content REAL, carbon_origin TEXT, nitrogen_content REAL, calcium_content REAL, chloride_content REAL, background_process TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS media (medium_id TEXT PRIMARY KEY, name TEXT, source_id TEXT, sterilisation TEXT, hydrolysis_json TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS medium_components (medium_id TEXT, chemical_id TEXT, g_per_L REAL, PRIMARY KEY (medium_id, chemical_id));
CREATE TABLE IF NOT EXISTS strains (strain_id TEXT PRIMARY KEY, name TEXT, pathway TEXT, source_id TEXT, cultivation_json TEXT, alternatives_json TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS materials (material_id TEXT PRIMARY KEY, name TEXT, source_id TEXT, oxides_json TEXT, portlandite_wt REAL, caco3_wt REAL, gypsum_wt REAL, mean_particle_um REAL, d90_um REAL, transport_km REAL, product_bulk_density_kg_m3 REAL);
CREATE TABLE IF NOT EXISTS material_processing (material_id TEXT, step_no INTEGER, step TEXT, electricity_kWh_per_t REAL, wear_parts_kg_per_t REAL, source_id TEXT, PRIMARY KEY (material_id, step_no));
CREATE TABLE IF NOT EXISTS protocols (protocol_id TEXT PRIMARY KEY, name TEXT, source_id TEXT, strain_id TEXT, material_id TEXT, solids_g REAL, gypsum_fraction REAL, suspension_mL REAL, suspension_od600 REAL, saline_mL REAL, hcl_molarity REAL, hcl_mL REAL, bs_base_medium TEXT, bs_dose_mL REAL, bs_dosing_json TEXT, incubation_C REAL, incubation_d REAL, drying_C REAL, drying_d REAL, fc_MPa REAL, k_N_mm REAL, caco3_gain_wt_abs REAL, porosity_pct REAL, precipitation_efficiency REAL, notes TEXT);
CREATE TABLE IF NOT EXISTS protocol_reagents (protocol_id TEXT, chemical_id TEXT, g_per_L REAL, PRIMARY KEY (protocol_id, chemical_id));
CREATE TABLE IF NOT EXISTS scenarios (scenario_id TEXT PRIMARY KEY, description TEXT, protocol_id TEXT, config_json TEXT);
CREATE TABLE IF NOT EXISTS benchmarks (benchmark_id TEXT PRIMARY KEY, description TEXT, definition_json TEXT);
CREATE TABLE IF NOT EXISTS scaleup_parameters (scale TEXT, path TEXT, value REAL, min REAL, max REAL, PRIMARY KEY (scale, path));
CREATE TABLE IF NOT EXISTS experimental_results (source_id TEXT, sample_code TEXT, material TEXT, organism TEXT, medium TEXT, treatment TEXT, duration_d REAL, temperature_C REAL, gypsum_wt_pct REAL, property TEXT, value REAL, sd REAL, unit TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS prices (process_id TEXT PRIMARY KEY, unit TEXT, price_bulk_eur REAL, price_bulk_min REAL, price_bulk_max REAL, price_lab_eur REAL, currency_year INTEGER, source_id TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS literature_results (source_id TEXT, study TEXT, system TEXT, functional_unit TEXT, indicator TEXT, value REAL, unit TEXT, pathway_or_variant TEXT, scope TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS results (run_id TEXT, scenario TEXT, functional_unit TEXT, modules TEXT, category_code TEXT, value REAL, unit TEXT, coverage REAL, created TEXT, PRIMARY KEY (run_id, scenario, functional_unit, modules, category_code));
CREATE TABLE IF NOT EXISTS result_contributions (run_id TEXT, scenario TEXT, functional_unit TEXT, module TEXT, grp TEXT, kind TEXT, key TEXT, amount REAL, unit TEXT, category_code TEXT, value REAL);
"""


def _walk_params(node: Any, path: str, out: list[tuple[str, float, float | None, float | None]]) -> None:
    if isinstance(node, dict):
        if "value" in node:
            out.append((path, float(node["value"]), float(node.get("min", node["value"])), float(node.get("max", node["value"]))))
        else:
            for k, v in node.items():
                _walk_params(v, f"{path}.{k}" if path else k, out)
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        out.append((path, float(node), None, None))


def build_database(path: Path | str | None = None, data: DataBundle | None = None) -> Path:
    """(Re)build the SQLite database from the data files and return its path."""
    data = data or load_data()
    path = Path(path) if path else data.root / "db" / "micp_lca.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO sources VALUES (?,?,?,?,?)",
                    [(s["source_id"], s["type"], s["citation"], s["doi_or_url"], s["notes"]) for s in data.sources.values()])
    data.impact_categories.to_sql("impact_categories", con, if_exists="append", index=False)
    data.characterization_factors.to_sql("characterization_factors", con, if_exists="append", index=False)
    for p in data.background.values():
        con.execute("INSERT INTO background_processes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (p.process_id, p.name, p.unit, p.category, p.geography, p.reference_year, p.data_type, p.source_id,
                     p.gwp_min, p.gwp_max, json.dumps(list(p.pedigree)), p.basic_uncertainty, p.ecoinvent_proxy, p.notes))
        for module, cats in p.impacts.items():
            for c, v in cats.items():
                con.execute("INSERT OR REPLACE INTO background_impacts VALUES (?,?,?,?,?)",
                            (p.process_id, module, c, v, f"{data.category_unit(c)}/{p.unit}" if c in data.category_codes else f"?/{p.unit}"))
    for cid, c in data.chemicals.items():
        if cid.startswith("_") or not isinstance(c, dict):
            continue
        con.execute("INSERT INTO chemicals VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, c.get("name"), c.get("formula"), c.get("molar_mass"), c.get("carbon_content"), c.get("carbon_origin"),
                     c.get("nitrogen_content"), c.get("calcium_content"), c.get("chloride_content"), c.get("background_process"), c.get("notes")))
    for mid, m in data.media.items():
        con.execute("INSERT INTO media VALUES (?,?,?,?,?,?)",
                    (mid, m.get("name"), m.get("source_id"), m.get("sterilisation"), json.dumps(m.get("hydrolysis")), m.get("notes")))
        for cid, g in (m.get("components") or {}).items():
            con.execute("INSERT INTO medium_components VALUES (?,?,?)", (mid, cid, float(g)))
    for sid, s in data.strains.items():
        con.execute("INSERT INTO strains VALUES (?,?,?,?,?,?,?)",
                    (sid, s.get("name"), s.get("pathway"), s.get("source_id"), json.dumps(s.get("cultivation")),
                     json.dumps(s.get("alternative_cultivation_media")), s.get("notes")))
    for mid, m in data.materials.items():
        con.execute("INSERT INTO materials VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (mid, m.get("name"), m.get("source_id"), json.dumps(m.get("oxides_wt")), m.get("portlandite_wt"), m.get("caco3_wt"),
                     m.get("gypsum_wt"), m.get("mean_particle_um"), m.get("d90_um"), m.get("transport_km"), m.get("product_bulk_density_kg_m3")))
        for i, st in enumerate(m.get("processing", []), 1):
            con.execute("INSERT INTO material_processing VALUES (?,?,?,?,?,?)",
                        (mid, i, st.get("step"), st.get("electricity_kWh_per_t"), st.get("wear_parts_kg_per_t"), st.get("source_id")))
    for pid, p in data.protocols.items():
        bs = p["biocementation_solution"]
        r = p.get("results") or {}
        con.execute("INSERT INTO protocols VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (pid, p.get("name"), p.get("source_id"), p.get("strain"), p.get("material"), p.get("solids_g"), p.get("gypsum_fraction"),
                     (p.get("suspension") or {}).get("volume_mL"), (p.get("suspension") or {}).get("od600"), p.get("saline_mL"),
                     (p.get("hcl") or {}).get("molarity"), (p.get("hcl") or {}).get("volume_mL"), bs.get("base_medium"), bs.get("dose_mL"),
                     json.dumps(bs.get("dosing")), p["incubation"].get("temperature_C"), p["incubation"].get("duration_d"),
                     (p.get("drying") or {}).get("temperature_C"), (p.get("drying") or {}).get("duration_d"), r.get("fc_MPa"), r.get("k_N_mm"),
                     r.get("caco3_gain_wt_abs"), r.get("porosity_pct"), p.get("precipitation_efficiency"), p.get("notes")))
        for cid, g in (bs.get("supplements") or {}).items():
            con.execute("INSERT INTO protocol_reagents VALUES (?,?,?)", (pid, cid, float(g)))
    for sid, s in data.scenarios.get("scenarios", {}).items():
        con.execute("INSERT INTO scenarios VALUES (?,?,?,?)", (sid, s.get("description"), s.get("protocol"), json.dumps(data.scenario_config(sid))))
    for bid, b in data.scenarios.get("benchmarks", {}).items():
        con.execute("INSERT INTO benchmarks VALUES (?,?,?)", (bid, b.get("description"), json.dumps(b)))
    for scale in ("industrial", "lab"):
        rows: list[tuple[str, float, float | None, float | None]] = []
        _walk_params(data.scaleup.get(scale, {}), "", rows)
        con.executemany("INSERT OR REPLACE INTO scaleup_parameters VALUES (?,?,?,?,?)", [(scale, *r) for r in rows])
    data.experimental.to_sql("experimental_results", con, if_exists="append", index=False)
    if not data.prices.empty:
        data.prices.to_sql("prices", con, if_exists="append", index=False)
    if not data.literature_results.empty:
        data.literature_results.to_sql("literature_results", con, if_exists="append", index=False)
    con.commit()
    con.close()
    return path


def store_results(results: Iterable[Results], run_id: str, path: Path | str | None = None) -> None:
    """Append assessment results (totals and contributions) to the database."""
    path = Path(path) if path else data_dir() / "db" / "micp_lca.sqlite"
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    created = pd.Timestamp.now().isoformat(timespec="seconds")
    for r in results:
        for modules, label in ((("A1", "A2", "A3"), "A1-A3"), (("C1", "C2", "C3", "C4"), "C1-C4"), (("D",), "D")):
            tot = r.totals(modules)
            for c in r.categories:
                con.execute("INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?)",
                            (run_id, r.scenario, r.functional_unit, label, c, float(tot[c]), r.units[c], r.coverage.get(c), created))
        for _, row in r.contrib.iterrows():
            for c in r.categories:
                if row[c]:
                    con.execute("INSERT INTO result_contributions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                (run_id, r.scenario, r.functional_unit, row["module"], row["group"], row["kind"], row["key"],
                                 float(row["amount"]), row["unit"], c, float(row[c])))
    con.commit()
    con.close()


def query(sql: str, path: Path | str | None = None) -> pd.DataFrame:
    """Run a read-only SQL query against the database."""
    path = Path(path) if path else data_dir() / "db" / "micp_lca.sqlite"
    con = sqlite3.connect(path)
    try:
        return pd.read_sql_query(sql, con)
    finally:
        con.close()
