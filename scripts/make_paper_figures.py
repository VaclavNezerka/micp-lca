"""Generate all figures, tables and numeric macros of the paper in ``paper/`` from the current model and database.

Usage:  python scripts/make_paper_figures.py [--no-mc] [--no-screens]

Outputs
    paper/figures/*.pdf|png   figures (vector where possible)
    paper/tables/*.tex        LaTeX tables generated from the data
    paper/numbers.tex         \\newcommand macros with every number quoted in the text
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from micp_lca import load_data, run_scenario  # noqa: E402
from micp_lca.benchmarks import benchmark_impacts, compare_with_status_quo  # noqa: E402
from micp_lca.cost import cost_summary  # noqa: E402
from micp_lca.parametric import available_parameters, describe_sweep, find_parameter, sweep  # noqa: E402
from micp_lca.inventory import Params, build_inventory  # noqa: E402
from micp_lca.sensitivity import oat_sensitivity  # noqa: E402
from micp_lca.uncertainty import MCSettings, monte_carlo, pedigree_gsd  # noqa: E402

FIG = ROOT / "paper" / "figures"
TAB = ROOT / "paper" / "tables"
FIG.mkdir(parents=True, exist_ok=True)
TAB.mkdir(parents=True, exist_ok=True)

# The manuscript is typeset with the Times font (\usepackage{times}); the figures use the same family (Times New Roman
# with the Times-compatible STIX glyphs for the mathematics) and no bold face anywhere, so that they read like the text.
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Nimbus Roman", "TeX Gyre Termes", "STIXGeneral"],
                     "mathtext.fontset": "stix", "font.weight": "normal", "axes.titleweight": "normal", "axes.labelweight": "normal",
                     "font.size": 8.5, "axes.titlesize": 9, "axes.labelsize": 8.5, "legend.fontsize": 7.5, "xtick.labelsize": 7.5,
                     "ytick.labelsize": 7.5, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.alpha": 0.25, "grid.linewidth": 0.5, "figure.dpi": 100, "pdf.fonttype": 42})

CORE = ["GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP", "EP-freshwater", "EP-marine", "EP-terrestrial", "POCP",
        "ADP-minerals&metals", "ADP-fossil", "WDP"]
LABEL = {
    "SP_lab_protocol_90d": "SP-lab-90d", "SP_lab_protocol_90d_WCFG": "SP-lab-90d-G", "SP_lab_scale_energy_90d": "SP-lab-energy",
    "SP_optimised_stoichiometric": "SP-stoich", "SP_optimised_recirculation": "SP-recirc", "SP_optimised_struvite_D": "SP-struvite-D",
    "SP_feather_media": "SP-feather", "SP_commercial_media_28d": "SP-commercial", "BC_lactate_30d": "BC-lactate",
    "BC_feather_media": "BC-feather", "BC_commercial_media_28d": "BC-commercial", "GYP_WCFC_single_dose": "GYP-WCFC",
    "GYP_WCFC_repeated": "GYP-WCFC-rep", "GYP_HM1_single_dose": "GYP-HM1", "GYP_HM2_single_dose": "GYP-HM2", "GYP_HM2_repeated": "GYP-HM2-rep",
    "GYP_WCFC_single_dose_20C": "GYP-WCFC-20C", "GYP_WCFC_single_dose_feather": "GYP-WCFC-feather", "GYP_WCFC_single_dose_EN15804": "GYP-WCFC-EN15804",
    "TR_fungal_CaCl2": "TR-CaCl2", "TR_fungal_lactate": "TR-lactate", "ABIOTIC_WCFC_gypsum": "ABIOTIC",
    "LIT_SP_NH4YE_medium": "LIT-SP-NH4YE", "LIT_SP_corn_steep_liquor": "LIT-SP-CSL", "LIT_SP_manure_effluent": "LIT-SP-manure",
    "LIT_EICP": "LIT-EICP", "LIT_denitrification": "LIT-denitrif.", "LIT_acetate_oxidation": "LIT-acetate", "LIT_photosynthetic": "LIT-photo",
    "AAC_block_ODB": "AAC block (ÖKOBAUDAT)", "AAC_block_Environdec_JCLEPRO": "AAC block (EPD)", "WCF_OPC_foamed_block": "WCF–OPC foamed block",
    "clay_brick_ODB": "Clay brick", "adobe_ODB": "Adobe block", "concrete_block_ODB": "Concrete block", "sand_lime_brick_ODB": "Sand-lime brick",
}
PATHWAY_COLOUR = {"ureolytic": "#4c78a8", "organic_acid": "#f58518", "gypsum": "#54a24b", "fungal": "#b279a2", "abiotic": "#9e9e9e",
                  "literature": "#72b7b2", "benchmark": "#bab0ac", "eicp": "#72b7b2", "denitrification": "#72b7b2", "photosynthetic": "#72b7b2",
                  "acetate_oxidation": "#72b7b2"}
MODULE_COLOURS = {"A1": "#4c78a8", "A2": "#9ecae9", "A3": "#f58518", "C1": "#54a24b", "C2": "#88d27a", "C3": "#b79a20", "C4": "#e45756", "D": "#72b7b2"}
PALETTE = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#72b7b2", "#b279a2", "#ff9da6", "#9d755d", "#bab0ac", "#eeca3b",
           "#4e79a7", "#a0cbe8", "#f28e2b", "#ffbe7d", "#59a14f", "#8cd17d", "#b6992d", "#f1ce63", "#499894", "#86bcb6"]
BLOCK = ["SP_lab_protocol_90d", "SP_optimised_stoichiometric", "SP_optimised_recirculation", "SP_optimised_struvite_D", "SP_feather_media",
         "SP_commercial_media_28d", "BC_lactate_30d", "BC_feather_media", "BC_commercial_media_28d", "GYP_WCFC_single_dose", "GYP_WCFC_repeated",
         "GYP_HM1_single_dose", "GYP_HM2_single_dose", "GYP_HM2_repeated", "GYP_WCFC_single_dose_20C", "GYP_WCFC_single_dose_feather",
         "TR_fungal_CaCl2", "TR_fungal_lactate", "ABIOTIC_WCFC_gypsum"]
LIT = ["LIT_SP_NH4YE_medium", "LIT_SP_corn_steep_liquor", "LIT_SP_manure_effluent", "LIT_EICP", "LIT_denitrification", "LIT_acetate_oxidation", "LIT_photosynthetic"]
BENCH = ["AAC_block_ODB", "AAC_block_Environdec_JCLEPRO", "WCF_OPC_foamed_block", "clay_brick_ODB", "adobe_ODB", "concrete_block_ODB", "sand_lime_brick_ODB"]

NUM: dict[str, str] = {}
PRETTY = {"tryptone_casein": "tryptone (bg)", "peptone_generic": "peptone (bg)", "yeast_extract": "yeast extract (bg)", "beef_extract": "beef extract (bg)",
          "calcium_chloride_industrial": "CaCl$_2$ (bg)", "calcium_lactate_pentahydrate": "Ca-lactate (bg)", "urea_EU": "urea (bg)",
          "electricity_CZ_lv": "electricity CZ (bg)", "heat_natural_gas": "natural-gas heat (bg)", "hydrochloric_acid": "HCl (bg)",
          "sodium_chloride": "NaCl (bg)", "landfill_inert": "inert landfill (bg)", "chicken_feathers": "chicken feathers (bg)",
          "curing_chamber.U_W_m2K": "chamber U-value", "curing_chamber.chamber_m3_per_t_product": "chamber volume per t",
          "curing_chamber.ambient_C": "ambient temperature", "curing_chamber.air_handling_kWh_per_t_day": "chamber air handling",
          "medium_sterilisation.heat_recovery": "sterilisation heat recovery", "medium_sterilisation.electricity_kWh_per_m3": "sterilisation electricity",
          "fermentation.power_kW_per_m3": "fermenter power", "fermentation.temperature_control_kWh_per_m3_day": "fermenter temperature control",
          "fermentation.hydrolysate_heating_heat_recovery": "hydrolysate heat recovery", "harvest.centrifuge_kWh_per_m3": "centrifugation energy",
          "drying.fan_kWh_per_t": "drying fan energy", "drying.water_evaporated_fraction": "water evaporated fraction",
          "effluent.fraction_drained": "effluent drained fraction", "effluent.basic_treatment_kWh_per_m3": "effluent treatment energy",
          "effluent.ammonia_stripping.electricity_kWh_per_kgN": "NH$_3$ stripping electricity", "effluent.ammonia_stripping.efficiency": "NH$_3$ stripping efficiency",
          "effluent.ammonia_stripping.naoh_kg_per_kgN": "NH$_3$ stripping NaOH", "effluent.ammonia_stripping.h2so4_kg_per_kgN": "NH$_3$ stripping H$_2$SO$_4$",
          "nitrogen_fate.n2o_fraction_of_N": "N$_2$O share of N", "nitrogen_fate.nh3_volatilised_fraction_of_retained_N": "NH$_3$ volatilised share",
          "nitrogen_fate.urea_hydrolysed_fraction": "urea hydrolysed fraction", "lactate_fate.oxidised_fraction": "lactate oxidised fraction",
          "solids_mixing_kWh_per_t": "solids mixing energy", "solution_dosing_kWh_per_m3": "solution dosing energy"}


def pretty(name: str) -> str:
    n = name.replace("bg:", "").replace("fg:", "").replace("industrial.", "")
    return PRETTY.get(n, n.replace("_", " "))


MKEY = {"SP_lab_protocol_90d_WCFG": "SPlabG", "SP_lab_protocol_90d": "SPlab", "SP_lab_scale_energy_90d": "SPlabenergy",
        "SP_optimised_stoichiometric": "SPstoich", "SP_optimised_recirculation": "SPrecirc", "SP_optimised_struvite_D": "SPstruvite",
        "SP_feather_media": "SPfeather", "SP_commercial_media_28d": "SPcommercial", "BC_lactate_30d": "BClactate", "BC_feather_media": "BCfeather",
        "BC_commercial_media_28d": "BCcommercial", "GYP_WCFC_single_dose_feather": "GYPfeather", "GYP_WCFC_single_dose_EN15804": "GYPEN",
        "GYP_WCFC_single_dose_20C": "GYPtwenty", "GYP_WCFC_single_dose": "GYP", "GYP_WCFC_repeated": "GYPrep", "GYP_HM1_single_dose": "GYPHMone",
        "GYP_HM2_single_dose": "GYPHMtwo", "GYP_HM2_repeated": "GYPHMtworep", "TR_fungal_CaCl2": "TRCaCl", "TR_fungal_lactate": "TRlactate",
        "ABIOTIC_WCFC_gypsum": "ABIOTIC", "LIT_SP_NH4YE_medium": "LITNHYE", "LIT_SP_corn_steep_liquor": "LITCSL", "LIT_SP_manure_effluent": "LITmanure",
        "LIT_EICP": "LITEICP", "LIT_denitrification": "LITdenit", "LIT_acetate_oxidation": "LITacetate", "LIT_photosynthetic": "LITphoto",
        "AAC_block_ODB": "AACODB", "AAC_block_Environdec_JCLEPRO": "AACEPD", "WCF_OPC_foamed_block": "WCFOPC", "clay_brick_ODB": "clay",
        "adobe_ODB": "adobe", "concrete_block_ODB": "concrete", "sand_lime_brick_ODB": "sandlime"}
_MKEY_SORTED = sorted(MKEY.items(), key=lambda kv: -len(kv[0]))


def macro(name: str, value, fmt: str = "{:.3g}") -> None:
    """Register a LaTeX macro (letters only in the name; scenario ids are replaced by short keys)."""
    for sid, short in _MKEY_SORTED:
        name = name.replace(sid, short)
    key = "".join(ch for ch in name if ch.isalpha())
    NUM[key] = fmt.format(value) if not isinstance(value, str) else value


def fmt3(v: float) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "--"
    a = abs(v)
    if a >= 1000:
        return f"{v:,.0f}"
    if a >= 100:
        return f"{v:.0f}"
    if a >= 10:
        return f"{v:.1f}"
    if a >= 0.1:
        return f"{v:.2f}"
    if a >= 0.01:
        return f"{v:.3f}"
    if a >= 0.001:
        return f"{v:.4f}"
    if a == 0:
        return "0"
    e = int(math.floor(math.log10(a)))
    return f"${v / 10 ** e:.1f}" + chr(92) + "times10^{" + str(e) + "}$"


def tex(s: str) -> str:
    return str(s).replace("&", "\\&").replace("_", "\\_").replace("%", "\\%").replace("–", "--").replace("ÖKOBAUDAT", "\\\"OKOBAUDAT")


def save(fig, name: str) -> None:
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight", dpi=200)
    plt.close(fig)
    print("figure", name)


def scen_pathway(data, s: str) -> str:
    cfg = data.scenario_config(s)
    proto = data.protocols[cfg["protocol"]]
    if cfg.get("abiotic"):
        return "abiotic"
    if s.startswith("LIT_"):
        return "literature"
    if float(proto.get("gypsum_fraction", 0) or 0) > 0:
        return "gypsum"
    return data.strains[proto["strain"]].get("pathway", "")


# ============================================================================================ 1 system boundary diagram
def fig_system_boundary() -> None:
    """Product system and modules; drawn on a wide canvas (placed sideways in the paper) so that every field holds its text."""
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 56)
    ax.axis("off")
    ax.grid(False)

    def box(x, y, w, h, text, fc="#eef3f8", ec="#1f3b5a", fs=7.0):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.0", fc=fc, ec=ec, lw=0.8))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.2)

    def arrow(x0, y0, x1, y1, color="#333", ls="-"):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=8, lw=0.8, color=color, ls=ls, shrinkA=0, shrinkB=0))

    # module header band
    for x, w, lab in ((1, 26, "A1 · raw-material supply"), (29.5, 11, "A2 · transport"), (43, 34, "A3 · manufacturing"),
                      (79.5, 11, "C1–C4 · end of life"), (92.5, 7, "D")):
        ax.add_patch(FancyBboxPatch((x, 50.8), w, 4.0, boxstyle="round,pad=0.2", fc="#1f3b5a", ec="none"))
        ax.text(x + w / 2, 52.8, lab, ha="center", va="center", fontsize=7.4, color="white")
    # A1 inputs
    box(1, 42.2, 26, 6.6, "Waste concrete fines and 0–4 mm\ndemolition residues: crushing,\nmilling, screening", fc="#e8f1e4")
    box(1, 35.2, 26, 6.0, "Waste gypsum plaster\ngrinding", fc="#e8f1e4")
    box(1, 28.2, 26, 6.0, "Reagents\nCaCl$_2$, urea, Ca-lactate, Ca-acetate, …")
    box(1, 21.2, 26, 6.0, "Media components\npeptones, yeast extract, hydrolysates, …")
    box(1, 12.2, 26, 8.0, "Water, acids, bases, electricity, heat\n(ÖKOBAUDAT, AGRIBALYSE and\nliterature background datasets)", fc="#f6f6f6")
    # A2
    box(29.5, 30.5, 11, 10, "Lorry\ntransport\n(t·km)")
    # A3 process steps
    box(43, 40.6, 16.2, 8.2, "Cultivation\nsterilisation,\nfermentation, harvest")
    box(60.8, 40.6, 16.2, 8.2, "Casting / mixing\nsaline, HCl,\nvibration")
    box(43, 30.4, 16.2, 8.2, "Biocementation\n$n$ doses × $V$; curing\nat $T$; chamber heat loss")
    box(60.8, 30.4, 16.2, 8.2, "Drying; effluent\ntreatment (NH$_3$\nstripping / struvite)")
    box(43, 19.4, 34, 8.6, "Direct flows: CO$_2$ (fossil / biogenic), NH$_3$, NH$_4^+$, N$_2$O,\nCl$^-$, residual organics; carbonation uptake\nof atmospheric CO$_2$ by the portlandite of the fines", fc="#fdeeee")
    box(43, 8.8, 34, 8.0, "Biocemented block\nfunctional units: 1 kg · 1 m³ · 1 m³·MPa · 1 kg CaCO$_3$", fc="#fff5dd", fs=7.6)
    # C and D
    box(79.5, 8.8, 11, 8.0, "Demolition,\ntransport\n50 km")
    box(79.5, 19.4, 11, 8.6, "Inert landfill\nor recycling")
    box(92.5, 30.4, 7, 8.2, "Credit:\nrecovered\nN fertiliser", fs=6.6)
    # flows
    arrow(27, 45.5, 29.5, 38.5); arrow(27, 38.2, 29.5, 37); arrow(27, 31.2, 29.5, 35.5); arrow(27, 24.2, 29.5, 34)
    arrow(40.5, 37.5, 43, 44.7); arrow(40.5, 34.5, 43, 34.5)
    arrow(59.2, 44.7, 60.8, 44.7); arrow(68.9, 40.6, 68.9, 38.6)
    arrow(59.2, 34.5, 60.8, 34.5)
    arrow(51.1, 30.4, 51.1, 28); arrow(68.9, 30.4, 68.9, 16.8)
    arrow(77, 12.8, 79.5, 12.8)
    arrow(85, 16.8, 85, 19.4)
    arrow(77, 34.5, 92.5, 34.5, ls="--", color="#72b7b2")
    ax.text(50, 3.6, "Cradle-to-grave boundary (A1–A3 + C1–C4; D optional); use stage B not modelled; waste fines, demolition residues and gypsum enter burden-free (cut-off)",
            ha="center", va="center", fontsize=7.0, style="italic", color="#333")
    ax.add_patch(FancyBboxPatch((0.5, 6.8), 99, 43, boxstyle="round,pad=0.3", fc="none", ec="#888", ls="--", lw=0.8))
    save(fig, "fig_system_boundary")


# ============================================================================================ 2 architecture
def fig_architecture(data) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 56)
    ax.axis("off")
    ax.grid(False)

    def box(x, y, w, h, text, fc="#eef3f8", ec="#1f3b5a", fs=6.1):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.0", fc=fc, ec=ec, lw=0.8))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.15)

    def arrow(x0, y0, x1, y1, color="#333"):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=8, lw=0.8, color=color, shrinkA=0, shrinkB=0))

    n_bg = len(data.background)
    n_chem = len([k for k in data.chemicals if not k.startswith('_')])
    for x, lab in ((16, "Data layer\n(plain text, version-controlled)"), (50, "Model layer\n(Python package micp_lca)"), (84, "Interfaces")):
        ax.text(x, 53.5, lab, fontsize=8, ha="center", va="center")
    box(1, 39, 30, 9.5, f"Foreground YAML\n{n_chem} chemicals · {len(data.media)} media · {len(data.strains)} organisms\n{len(data.materials)} materials · {len(data.protocols)} protocols · {len(data.scenarios['scenarios'])} scenarios\nscale-up parameters with ranges", fc="#e8f1e4")
    box(1, 27, 30, 9.5, f"Background CSV: {n_bg} processes\nÖKOBAUDAT (107, EN 15804+A2/EF 3.1)\nAGRIBALYSE 4 (7) · literature/estimates (47)", fc="#e8f1e4")
    box(1, 15, 30, 9.5, "EF 3.1 characterisation factors\n(curated subset + full table, 140 474 rows)\nexperimental results · literature LCAs · prices", fc="#e8f1e4")
    box(1, 3, 30, 9.5, "data/user/\nuser additions and overrides\n(merged at load time)", fc="#fff5dd")
    box(35, 39, 30, 9.5, "loaders → chemistry → inventory\nper specimen → per kg solids →\nfunctional unit (EN 15804+A2 modules)")
    box(35, 27, 30, 9.5, "lcia (EF 3.1, coverage statistics)\nbenchmarks (system expansion)\ncost (bulk / laboratory grade)")
    box(35, 15, 30, 9.5, "uncertainty (pedigree, Monte Carlo)\nsensitivity (one-at-a-time)\nparametric (one-variable sweeps)")
    box(35, 3, 30, 9.5, "figures · pdfreport (narrative, references)\nexport (Brightway, openLCA) · db (SQLite)")
    box(69, 39, 30, 9.5, "Streamlit application (7 pages)\nscenario builder · compare · uncertainty\ndatabase · data editor · literature · cost", fc="#fdeeee")
    box(69, 27, 30, 9.5, "Command-line interface micp-lca\nrun · run-all · sensitivity · monte-carlo\nparameters · sweep · report · export · sql", fc="#fdeeee")
    box(69, 15, 30, 9.5, "PDF report (ReportLab + matplotlib)\ngoal & scope · inventory · LCIA · comparison\nsensitivity · cost · data quality · references", fc="#fdeeee")
    box(69, 3, 30, 9.5, "Quality assurance\n77 automated tests (pytest, AppTest)\ndocumentation · SQLite snapshot", fc="#f6f6f6")
    for y in (43.75, 31.75, 19.75, 7.75):
        arrow(31, y, 35, y)
        arrow(65, y, 69, y)
    save(fig, "fig_architecture")



# ============================================================================================ 2b modelling chain (worked example)
def fig_modelling_chain(data, res_kg: dict, res_m3: dict, res_mpa: dict) -> None:
    s = "GYP_WCFC_single_dose"
    r, m = res_kg[s], res_kg[s].meta
    ct = r.contrib
    ff = r.fu_factor
    el = float(ct[(ct.kind == "background") & (ct.unit == "kWh") & ct.key.str.startswith("electricity")]["amount"].sum()) * ff
    heat = float(ct[(ct.kind == "background") & (ct.unit == "kWh") & ct.key.str.startswith("heat")]["amount"].sum()) * ff
    water = float(ct[(ct.kind == "background") & (ct.key == "water_tap")]["amount"].sum()) * ff
    proto = data.protocols[data.scenario_config(s)["protocol"]]
    bs = proto["biocementation_solution"]
    ref = benchmark_impacts("AAC_block_ODB", data, functional_unit="kg_product", include_eol=False)
    a13 = r.totals(("A1", "A2", "A3"))
    gm3 = res_m3[s].gwp() + float(res_m3[s].totals(("C1", "C2", "C3", "C4"))["GWP-total"])
    gmpa = res_mpa[s].gwp() + float(res_mpa[s].totals(("C1", "C2", "C3", "C4"))["GWP-total"])
    steps = [
        ("1  Laboratory protocol\n(as published, per specimen)",
         f"{proto['solids_g']} g dry solids, {100 * proto['gypsum_fraction']:.0f} % waste gypsum\n{proto['suspension']['volume_mL']} mL suspension (OD600 {proto['suspension']['od600']})\n"
         f"{bs['dose_mL']} mL nutrient broth + {bs['supplements']['calcium_lactate_pentahydrate']} g/L Ca-lactate\n{proto['incubation']['temperature_C']} °C, {proto['incubation']['duration_d']} d curing, {proto['drying']['duration_d']} d drying"),
        ("2  Stoichiometry and\nmass balances",
         f"Ca-lactate → {100 * m['caco3_precipitated_kg_per_kg_solids']:.2f} wt% CaCO$_3$ (limiting reagent)\nbiogenic C respired: {m['co2_biogenic_direct_kg_per_kg_solids'] * ff:.4f} kg CO$_2$/kg\n"
         f"carbonation uptake: {m['carbonation_uptake_kg_per_kg_solids'] * ff:.3f} kg CO$_2$/kg\nno nitrogen by-products"),
        ("3  Per kg of dry solids\nand product",
         f"{m['liquid_to_solid_L_per_kg']:.2f} L liquid per kg solids\n{m['V_culture_L'] / m['solids_kg_per_specimen']:.2f} L culture per kg (LB 25 g/L)\n"
         f"product mass {m['product_kg_per_kg_solids']:.3f} kg per kg solids\nwater {water:.2f} kg per kg product"),
        ("4  Industrial process\nmodel (scale-up)",
         f"sterilisation, fermentation, casting,\ncuring chamber (U = 0.35 W/m²K), drying:\nelectricity {el:.3f} kWh/kg, heat {heat:.3f} kWh/kg\n(laboratory equipment: not extrapolated)"),
        ("5  Characterisation\n(EF 3.1, EN 15804+A2)",
         f"GWP-total {float(a13['GWP-total']):.3f} kg CO$_2$ eq/kg (A1–A3)\nAP {float(a13['AP']):.4f} mol H$^+$ eq/kg\n"
         f"native coverage: GWP {100 * r.coverage_native['GWP-total']:.0f} %, AP {100 * r.coverage_native['AP']:.0f} %\nmodules A1 {100 * float(r.by_module().loc['A1', 'GWP-total']) / float(r.totals()['GWP-total']):.0f} %, A3 {100 * float(r.by_module().loc['A3', 'GWP-total']) / float(r.totals()['GWP-total']):.0f} %"),
        ("6  Functional units and\ninterpretation",
         f"{float(a13['GWP-total']):.2f} kg CO$_2$ eq per kg ({100 * (1 - float(a13['GWP-total']) / float(ref['GWP-total'])):.0f} % below AAC)\n{gm3:.0f} kg CO$_2$ eq per m³\n"
         f"{gmpa:.0f} kg CO$_2$ eq per m³·MPa\nlevers: media, curing heat, dosing"),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.grid(False)
    n = len(steps)
    row_h, gap = 14.2, 1.6
    top = 97.5
    for i, (head, body) in enumerate(steps):
        y = top - (i + 1) * row_h - i * gap
        ax.add_patch(FancyBboxPatch((0.5, y), 23, row_h, boxstyle="round,pad=0.25,rounding_size=1.0", fc="#1f3b5a", ec="none"))
        ax.text(12, y + row_h / 2, head, ha="center", va="center", fontsize=7.8, color="white", linespacing=1.2)
        ax.add_patch(FancyBboxPatch((25, y), 74.5, row_h, boxstyle="round,pad=0.25,rounding_size=1.0", fc="#f4f6f8", ec="#1f3b5a", lw=0.8))
        ax.text(26.2, y + row_h - 1.2, body.replace("\n", "   |   ", 1).replace("\n", "\n", 1), ha="left", va="top", fontsize=7.4, linespacing=1.5)
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((12, y - 0.1), (12, y - gap + 0.1), arrowstyle="-|>", mutation_scale=8, lw=1.0, color="#1f3b5a", shrinkA=0, shrinkB=0))
    ax.text(50, 0.8, "Worked example: gypsum-promoted single-dose recipe GYP-WCFC (S. cohnii, WCF-C + 9 % waste gypsum, protocol C-G-30-0)",
            ha="center", va="center", fontsize=7.2, style="italic", color="#333")
    save(fig, "fig_modelling_chain")


# ============================================================================================ 2c pathway chemistry
def fig_pathways() -> None:
    cards = [
        ("Ureolytic MICP  (S. pasteurii; EICP with plant urease)", "#4c78a8",
         r"$\mathrm{CO(NH_2)_2 + 2\,H_2O \rightarrow 2\,NH_4^+ + CO_3^{2-}}$" + "\n" + r"$\mathrm{Ca^{2+} + CO_3^{2-} \rightarrow CaCO_3}$",
         "urea (fossil carbon), CaCl$_2$, nutrient broth,\ncultivation medium (TSB or feather hydrolysate)",
         "NH$_4^+$ to water, NH$_3$ to air, N$_2$O; fossil CO$_2$ from the\nurea carbon not fixed in CaCO$_3$; Cl$^-$ in effluent and product"),
        ("Non-ureolytic MICP  (S. cohnii, A. pseudofirmus)", "#f58518",
         r"$\mathrm{Ca(C_3H_5O_3)_2 + 6\,O_2 \rightarrow CaCO_3 + 5\,CO_2 + 5\,H_2O}$",
         "calcium lactate (biogenic carbon), nutrient broth,\ncultivation medium (LB or feather hydrolysate)",
         "biogenic CO$_2$ (5/6 of the substrate carbon),\nresidual lactate in the effluent; no nitrogen"),
        ("Gypsum-promoted route  (S. cohnii + waste gypsum)", "#54a24b",
         r"$\mathrm{3\,CaSO_4{\cdot}2H_2O + aluminates + Ca(OH)_2 + H_2O}$" + "\n" + r"$\mathrm{\rightarrow\ AFt\ (ettringite)}$ + minor microbial CaCO$_3$",
         "waste gypsum (9 % of the solids), a single dose of\nnutrient broth + Ca-lactate, LB cultivation medium",
         "negligible; the portlandite of the fines absorbs\natmospheric CO$_2$ by carbonation (uptake)"),
        ("Fungal biomineralisation  (T. reesei)", "#b279a2",
         r"$\mathrm{metabolic\ CO_2 + Ca^{2+} \rightarrow CaCO_3}$" + "\n(mycelium as nucleation template)",
         "malt extract broth, CaCl$_2$ or Ca-lactate,\nagar inoculum",
         "biogenic CO$_2$; Cl$^-$ (CaCl$_2$ variant)"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.0))
    for ax, (title, col, rxn, inputs, byp) in zip(axes.flat, cards):
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.axis("off")
        ax.grid(False)
        ax.add_patch(FancyBboxPatch((1, 1), 98, 98, boxstyle="round,pad=0.5,rounding_size=2", fc="#fbfbfb", ec=col, lw=1.4))
        ax.add_patch(FancyBboxPatch((1, 86), 98, 13, boxstyle="round,pad=0.5,rounding_size=2", fc=col, ec="none"))
        ax.text(50, 92.5, title, ha="center", va="center", fontsize=7.8, color="white")
        ax.text(50, 71, rxn, ha="center", va="center", fontsize=8.2, linespacing=1.6)
        ax.text(4, 51, "Inputs", fontsize=7.6, color=col, va="top")
        ax.text(4, 43, inputs, fontsize=7.3, va="top", linespacing=1.4)
        ax.text(4, 25, "Direct flows and by-products", fontsize=7.6, color=col, va="top")
        ax.text(4, 17, byp, fontsize=7.3, va="top", linespacing=1.4)
    fig.tight_layout(pad=0.6)
    save(fig, "fig_pathways")


# ============================================================================================ 4b the story: levers from the laboratory protocol to the prototype recipe
def fig_levers(data, res_kg: dict) -> None:
    steps = [("SP_lab_protocol_90d", "ureolytic lab\nprotocol\n(as performed)"),
             ("SP_optimised_stoichiometric", "stoichiometric\nurea + NH$_3$\nstripping"),
             ("SP_optimised_recirculation", "+ 80 %\nsolution\nrecirculation"),
             ("SP_feather_media", "feather-\nhydrolysate\nmedia, 28 d"),
             ("BC_lactate_30d", "non-ureolytic\nCa-lactate\nroute"),
             ("BC_feather_media", "+ feather-\nhydrolysate\nmedia"),
             ("GYP_WCFC_single_dose", "gypsum-\npromoted\nsingle dose"),
             ("GYP_WCFC_single_dose_feather", "+ feather-\nhydrolysate\nmedium"),
             ("ABIOTIC_WCFC_gypsum", "abiotic\ncontrol\n(no organism)")]
    vals = [res_kg[s].gwp() for s, _ in steps]
    cols = [PATHWAY_COLOUR[scen_pathway(data, s)] for s, _ in steps]
    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    x = np.arange(len(steps))
    ax.bar(x, vals, color=cols, width=0.66, zorder=3)
    for i, v in enumerate(vals):
        ax.text(i, v * 1.13, f"{v:.2f}", ha="center", va="bottom", fontsize=7)
        if i > 0:
            ch = 100 * (v / vals[i - 1] - 1)
            ax.annotate("", xy=(i - 0.33, v), xytext=(i - 0.67, vals[i - 1]), arrowprops=dict(arrowstyle="-|>", color="#555", lw=0.8, shrinkA=0, shrinkB=0))
            ax.text(i - 0.5, (v * vals[i - 1]) ** 0.5, f"{ch:+.0f} %", ha="center", va="center", fontsize=6.0, color="#222",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9), zorder=4)
    for b, lab, ls in (("AAC_block_ODB", "AAC block (ÖKOBAUDAT)", "--"), ("clay_brick_ODB", "clay brick", ":"), ("adobe_ODB", "adobe block", "-.")):
        v = float(benchmark_impacts(b, data, functional_unit="kg_product", include_eol=False)["GWP-total"])
        ax.axhline(v, color="#666", ls=ls, lw=0.9, zorder=2)
        ax.text(-0.45, v * 1.06, f"{lab}: {v:.2f}", ha="left", va="bottom", fontsize=6.6, color="#444", bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85), zorder=4)
    # route brackets
    for (i0, i1, lab, col) in ((0, 3, "ureolytic route (S. pasteurii)", PATHWAY_COLOUR["ureolytic"]), (4, 5, "non-ureolytic route" + chr(10) + "(S. cohnii)", PATHWAY_COLOUR["organic_acid"]),
                               (6, 7, "gypsum-promoted route" + chr(10) + "(S. cohnii)", PATHWAY_COLOUR["gypsum"])):
        ax.plot([i0 - 0.33, i1 + 0.33], [6.3, 6.3], color=col, lw=2.0, solid_capstyle="butt")
        ax.text((i0 + i1) / 2, 6.8, lab, ha="center", va="bottom", fontsize=6.2, color=col)
    ax.set_yscale("log")
    ax.set_ylim(0.02, 22)
    ax.set_xlim(-0.6, len(steps) - 0.4)
    ax.set_xticks(x, [lab for _, lab in steps], fontsize=6.0)
    ax.set_ylabel("GWP-total [kg CO$_2$ eq per kg product], A1–A3 (log)")
    ax.grid(axis="x", visible=False)
    save(fig, "fig_levers")


# ============================================================================================ 3 database overview
def fig_database(data, res_kg: dict) -> None:
    fig = plt.figure(figsize=(7.0, 4.9))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.15], width_ratios=[1, 1.1], hspace=0.62, wspace=0.42)
    # (a) datasets by type
    nice = {"oekobaudat": "ÖKOBAUDAT", "estimate": "estimate", "agribalyse": "AGRIBALYSE", "literature": "literature", "proxy": "proxy", "secondary_material": "secondary material"}
    types = pd.Series([nice.get(p.data_type, p.data_type) for p in data.background.values()]).value_counts()
    ax = fig.add_subplot(gs[0, 0])
    ax.barh(types.index[::-1], types.values[::-1], color=PALETTE[: len(types)][::-1])
    for i, v in enumerate(types.values[::-1]):
        ax.text(v + 1.5, i, str(v), va="center", fontsize=7)
    ax.set_xlim(0, types.values.max() * 1.15)
    ax.set_title("(a) Datasets by type")
    ax.set_xlabel("number of datasets")
    # (b) sigma_g distribution
    ax = fig.add_subplot(gs[0, 1])
    gsd = [pedigree_gsd(p.pedigree, p.basic_uncertainty) for p in data.background.values()]
    ax.hist(gsd, bins=np.linspace(1.0, 2.6, 17), color="#4c78a8", alpha=0.9)
    ax.set_title("(b) Pedigree-derived $\\sigma_g$")
    ax.set_xlabel("geometric standard deviation $\\sigma_g$")
    ax.set_ylabel("datasets")
    # (c) native coverage per indicator for three scenarios (full width)
    ax = fig.add_subplot(gs[1, :])
    cats = ["GWP-total", "AP", "EP-freshwater", "EP-marine", "EP-terrestrial", "POCP", "ADP-minerals&metals", "ADP-fossil", "WDP", "ODP"]
    scen = ["GYP_WCFC_single_dose", "BC_lactate_30d", "SP_lab_protocol_90d"]
    x = np.arange(len(cats))
    w = 0.26
    for i, sc in enumerate(scen):
        r = res_kg[sc]
        ax.bar(x + (i - 1) * w, [100 * r.coverage_native.get(c, 0) for c in cats], w, color=PALETTE[i], label=LABEL[sc])
    ax.set_xticks(x, cats, rotation=25, ha="right")
    ax.set_ylabel("native coverage [%]")
    ax.set_ylim(0, 124)
    ax.set_title("(c) Share of the cradle-to-gate inventory (GWP-weighted) covered by native, non-proxy factors")
    ax.legend(frameon=False, loc="upper center", ncol=3)
    save(fig, "fig_database")


# ============================================================================================ 4 per kg comparison
def fig_gwp_per_kg(data, res_kg: dict) -> pd.DataFrame:
    rows = []
    for s in BLOCK:
        r = res_kg[s]
        a = r.gwp()
        c = float(r.totals(("C1", "C2", "C3", "C4"))["GWP-total"])
        rows.append({"item": LABEL[s], "id": s, "type": "scenario", "pathway": scen_pathway(data, s), "A1-A3": a, "C": c, "total": a + c})
    for b in BENCH:
        a = float(benchmark_impacts(b, data, functional_unit="kg_product", include_eol=False)["GWP-total"])
        t = float(benchmark_impacts(b, data, functional_unit="kg_product", include_eol=True)["GWP-total"])
        rows.append({"item": LABEL[b], "id": b, "type": "benchmark", "pathway": "benchmark", "A1-A3": a, "C": t - a, "total": t})
    df = pd.DataFrame(rows).sort_values("total")
    fig, ax = plt.subplots(figsize=(7.0, 5.6))
    y = np.arange(len(df))
    cols = [PATHWAY_COLOUR.get(p, "#999") for p in df["pathway"]]
    ax.barh(y, df["A1-A3"], color=cols, height=0.72)
    ax.barh(y, df["C"], left=df["A1-A3"], color=[c + "77" for c in cols], height=0.72, hatch="////", edgecolor="white", lw=0.3)
    for yi, (a, t) in enumerate(zip(df["A1-A3"], df["total"])):
        ax.text(t + 0.02, yi, f"{a:.2f} | {t:.2f}", va="center", fontsize=6.3)
    ax.set_yticks(y, df["item"])
    ax.set_xlabel("GWP-total [kg CO$_2$ eq per kg of dry product]  (solid: A1–A3, hatched: C1–C4)")
    ax.set_xlim(0, df["total"].max() * 1.18)
    from matplotlib.patches import Patch
    handles = [Patch(color=PATHWAY_COLOUR[k], label=lab) for k, lab in (("ureolytic", "ureolytic (S. pasteurii)"), ("organic_acid", "non-ureolytic (S. cohnii, Ca-lactate)"),
                                                                        ("gypsum", "gypsum-promoted (S. cohnii + waste gypsum)"), ("fungal", "fungal (T. reesei)"),
                                                                        ("abiotic", "abiotic control"), ("benchmark", "benchmark products"))]
    ax.legend(handles=handles, frameon=False, loc="lower right", fontsize=6.5)
    save(fig, "fig_gwp_per_kg")
    return df


def fig_per_m3(data, res_m3: dict, res_mpa: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.6))
    rows = []
    for s in BLOCK:
        if s in res_m3:
            r = res_m3[s]
            rows.append({"item": LABEL[s], "pathway": scen_pathway(data, s), "v": r.gwp() + float(r.totals(("C1", "C2", "C3", "C4"))["GWP-total"])})
    for b in BENCH:
        rows.append({"item": LABEL[b], "pathway": "benchmark", "v": float(benchmark_impacts(b, data, functional_unit="m3_product", include_eol=True)["GWP-total"])})
    df = pd.DataFrame(rows).sort_values("v")
    ax = axes[0]
    ax.barh(np.arange(len(df)), df["v"], color=[PATHWAY_COLOUR[p] for p in df["pathway"]], height=0.72)
    for yi, v in enumerate(df["v"]):
        ax.text(v + 10, yi, f"{v:.0f}", va="center", fontsize=6.3)
    ax.set_yticks(np.arange(len(df)), df["item"])
    ax.set_xlabel("GWP-total [kg CO$_2$ eq per m³], A1–A3 + C1–C4")
    ax.set_title("(a) per m³ of product")
    ax.set_xlim(0, df["v"].max() * 1.15)
    rows = []
    for s in BLOCK:
        if s in res_mpa:
            r = res_mpa[s]
            rows.append({"item": LABEL[s], "pathway": scen_pathway(data, s), "v": r.gwp() + float(r.totals(("C1", "C2", "C3", "C4"))["GWP-total"])})
    for b in BENCH:
        rows.append({"item": LABEL[b], "pathway": "benchmark", "v": float(benchmark_impacts(b, data, functional_unit="m3_MPa", include_eol=True)["GWP-total"])})
    df = pd.DataFrame(rows).sort_values("v")
    ax = axes[1]
    ax.barh(np.arange(len(df)), df["v"], color=[PATHWAY_COLOUR[p] for p in df["pathway"]], height=0.72)
    for yi, v in enumerate(df["v"]):
        ax.text(v * 1.05, yi, f"{v:.0f}", va="center", fontsize=6.3)
    ax.set_yticks(np.arange(len(df)), df["item"])
    ax.set_xscale("log")
    ax.set_xlabel("GWP-total [kg CO$_2$ eq per m³·MPa], A1–A3 + C1–C4")
    ax.set_title("(b) per m³ and MPa of compressive strength")
    fig.tight_layout()
    save(fig, "fig_per_m3")


# ============================================================================================ 5 contributions
def fig_contributions(data, res_kg: dict) -> None:
    scen = ["SP_lab_protocol_90d", "BC_lactate_30d", "GYP_WCFC_single_dose"]
    tables = {}
    for s in scen:
        r = res_kg[s]
        df = r.contrib.groupby(["group", "module"])["GWP-total"].sum().unstack("module").fillna(0.0)
        tables[s] = df
    # common group order: mean share of the cradle-to-grave total across the three scenarios
    score = pd.Series(0.0, index=sorted({g for df in tables.values() for g in df.index}))
    for s, df in tables.items():
        tot = abs(float(df.to_numpy().sum())) or 1.0
        score = score.add(df.abs().sum(axis=1) / tot, fill_value=0.0)
    order = score.sort_values().index.tolist()
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 4.2), sharey=True, gridspec_kw={"wspace": 0.12})
    for ax, s in zip(axes, scen):
        df = tables[s].reindex(order).fillna(0.0)
        df = df[[m for m in MODULE_COLOURS if m in df.columns]]
        lp, ln = np.zeros(len(df)), np.zeros(len(df))
        for m in df.columns:
            v = df[m].to_numpy()
            pos, neg = np.clip(v, 0, None), np.clip(v, None, 0)
            ax.barh(np.arange(len(df)), pos, left=lp, color=MODULE_COLOURS[m], label=m, height=0.72)
            ax.barh(np.arange(len(df)), neg, left=ln, color=MODULE_COLOURS[m], height=0.72)
            lp += pos
            ln += neg
        tot = float(df.to_numpy().sum())
        for i, row in enumerate(df.to_numpy()):
            v = row.sum()
            if abs(v) / tot > 0.025:
                ax.text(max(lp[i], 0) + 0.015 * lp.max(), i, f"{100 * v / tot:.0f}%", va="center", fontsize=6.6)
        ax.axvline(0, color="k", lw=0.6)
        ax.set_xlim(min(ln.min() * 1.3, 0), lp.max() * 1.25)
        r = res_kg[s]
        ax.set_title(f"{LABEL[s]}\n{r.gwp():.2f} kg CO$_2$ eq/kg (A1–A3)", fontsize=7.5)
        ax.set_xlabel("kg CO$_2$ eq per kg product")
    axes[0].set_yticks(np.arange(len(order)), order, fontsize=7.2)
    axes[2].legend(title="module", frameon=False, loc="lower right", fontsize=6, title_fontsize=6.5)
    save(fig, "fig_contributions")


# ============================================================================================ 6 heat map of indicators
def fig_heatmap(data, res_kg: dict) -> pd.DataFrame:
    scen = ["SP_lab_protocol_90d", "SP_optimised_recirculation", "SP_feather_media", "BC_lactate_30d", "BC_feather_media", "GYP_WCFC_single_dose",
            "GYP_WCFC_single_dose_feather", "TR_fungal_lactate", "ABIOTIC_WCFC_gypsum", "LIT_EICP"]
    ref = benchmark_impacts("AAC_block_ODB", data, functional_unit="kg_product", include_eol=False)
    cats = [c for c in CORE if c not in ("ODP", "GWP-biogenic", "GWP-luluc")]
    mat = pd.DataFrame({LABEL[s]: {c: float(res_kg[s].totals(("A1", "A2", "A3"))[c]) / float(ref[c]) for c in cats} for s in scen}).T
    fig, ax = plt.subplots(figsize=(7.0, 3.4))
    arr = np.log10(mat.to_numpy(float))
    im = ax.imshow(arr, cmap="RdYlGn_r", vmin=-3, vmax=3, aspect="auto")
    ax.set_xticks(range(len(cats)), cats, rotation=40, ha="right")
    ax.set_yticks(range(len(scen)), mat.index)
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            v = mat.iloc[i, j]
            ax.text(j, i, f"{v:.2f}" if v < 10 else f"{v:.0f}", ha="center", va="center", fontsize=6, color="black" if abs(arr[i, j]) < 2.2 else "white")
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("log$_{10}$(scenario / AAC block)")
    ax.set_title("EN 15804+A2 core indicators relative to the AAC block (A1–A3, per kg of product)")
    ax.grid(False)
    save(fig, "fig_heatmap")
    return mat


# ============================================================================================ 7 nitrogen and carbon balances
def fig_n_c_balance(data, res_kg: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.9), gridspec_kw={"width_ratios": [1, 1.2, 1.2]})
    # (a) nitrogen fate
    ax = axes[0]
    scen = ["SP_lab_protocol_90d", "SP_optimised_stoichiometric", "SP_optimised_recirculation", "SP_optimised_struvite_D"]
    keys = ["nh4_to_water", "nh3_to_air", "n2o_to_air", "n_recovered", "n_retained_in_product"]
    labels = ["NH$_4^+$ to water", "NH$_3$ to air", "N$_2$O to air", "N recovered", "N retained"]
    bottoms = np.zeros(len(scen))
    for k, lab, col in zip(keys, labels, PALETTE):
        vals = np.array([res_kg[s].meta["nitrogen_fate_kg_per_kg_solids"][k] * res_kg[s].fu_factor for s in scen])
        ax.bar(range(len(scen)), vals, bottom=bottoms, color=col, label=lab, width=0.7)
        bottoms += vals
    ax.set_xticks(range(len(scen)), [LABEL[s] for s in scen], rotation=30, ha="right")
    ax.set_ylabel("kg N per kg product")
    ax.set_title("(a) Fate of urea nitrogen")
    ax.legend(frameon=False, fontsize=5.8)

    def waterfall(ax, r, title):
        ct = r.contrib
        comp = {}
        parts = [("A1", float(ct[(ct.kind == "background") & (ct.module == "A1")]["GWP-total"].sum())),
                 ("A2", float(ct[(ct.kind == "background") & (ct.module == "A2")]["GWP-total"].sum())),
                 ("A3 energy", float(ct[(ct.kind == "background") & (ct.module == "A3")]["GWP-total"].sum())),
                 ("fossil CO$_2$", float(ct[(ct.kind == "elementary") & (ct.group == "Direct process emissions") & (ct.key == "carbon dioxide (fossil)")]["GWP-total"].sum())),
                 ("N$_2$O", float(ct[(ct.kind == "elementary") & (ct.key == "nitrous oxide")]["GWP-total"].sum())),
                 ("carbonation", float(ct[ct.group == "Carbonation uptake"]["GWP-total"].sum())),
                 ("C1–C4", float(ct[ct.module.isin(["C1", "C2", "C3", "C4"])]["GWP-total"].sum()))]
        parts = [(k, v) for k, v in parts if abs(v) > 1e-6]
        vals = np.array([v for _, v in parts])
        cum = np.concatenate([[0], np.cumsum(vals)])
        for i, (k, v) in enumerate(parts):
            ax.bar(i, v, bottom=cum[i], color="#e45756" if v > 0 else "#54a24b", width=0.65)
            if abs(v) >= 0.015 * abs(vals).sum():
                ax.text(i, cum[i + 1] + (0.02 if v > 0 else -0.02) * abs(vals).max(), f"{v:+.2g}", ha="center", va="bottom" if v > 0 else "top", fontsize=5.6)
        ax.bar(len(parts), vals.sum(), color="#4c78a8", width=0.65)
        ax.text(len(parts), vals.sum() + 0.02 * abs(vals).max(), f"{vals.sum():.2f}", ha="center", va="bottom", fontsize=6)
        ax.set_xticks(range(len(parts) + 1), [k for k, _ in parts] + ["net"], rotation=35, ha="right", fontsize=6)
        ax.axhline(0, color="k", lw=0.6)
        ax.set_title(title)
        ax.set_ylabel("kg CO$_2$ eq per kg product")

    waterfall(axes[1], res_kg["SP_lab_protocol_90d"], "(b) Climate balance, SP-lab-90d")
    waterfall(axes[2], res_kg["GYP_WCFC_single_dose"], "(c) Climate balance, GYP-WCFC")
    fig.tight_layout()
    save(fig, "fig_n_c_balance")


# ============================================================================================ 8 parametric sweeps
def fig_sweeps(data, res_kg: dict) -> dict:
    specs = [("SP_lab_protocol_90d", "reagent:urea_to_ca_molar_ratio", (1.0, 13.2), "(a) SP-lab-90d", "urea : Ca molar ratio [mol/mol]"),
             ("SP_optimised_recirculation", "reagent:solution_recirculation_fraction", (0.0, 0.9), "(b) SP-recirc", "recirculated share of the solution [-]"),
             ("BC_lactate_30d", "protocol:biocementation_solution.dosing.interval_h", (24.0, 168.0), "(c) BC-lactate", "dosing interval [h]"),
             ("GYP_WCFC_single_dose", "medium:lb_25.tryptone", (0.0, 20.0), "(d) GYP-WCFC", "tryptone in the cultivation medium [g/L]"),
             ("GYP_WCFC_single_dose", "scenario:temperature_override_C", (15.0, 37.0), "(e) GYP-WCFC", "cultivation and curing temperature [°C]"),
             ("GYP_WCFC_single_dose", "scaleup:industrial.curing_chamber.U_W_m2K", (0.2, 1.0), "(f) GYP-WCFC", "curing-chamber U-value [W/(m²K)]")]
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.6))
    out = {}
    for ax, (s, key, (lo, hi), title, xlabel) in zip(axes.flat, specs):
        ps = available_parameters(s, data)
        sp = find_parameter(ps, key)
        vals = sp.values(13, lo, hi)
        df = sweep(s, data, key, vals, categories=["GWP-total", "AP", "EP-terrestrial"], with_cost=True)
        ok = df[df["error"] == ""]
        out[(s, key)] = ok
        base_g = res_kg[s].gwp()
        ax.plot(ok["value"], ok["GWP-total"] / base_g, marker="o", ms=3, lw=1.2, color="#4c78a8", label="GWP-total")
        ax.plot(ok["value"], ok["AP"] / float(res_kg[s].totals(("A1", "A2", "A3"))["AP"]), marker="s", ms=3, lw=1.2, color="#e45756", label="AP")
        if "cost_bulk_EUR" in ok:
            base_c = cost_summary(res_kg[s], data, "bulk")["total_A1-A3"]
            ax.plot(ok["value"], ok["cost_bulk_EUR"] / base_c, marker="^", ms=3, lw=1.2, color="#54a24b", label="cost (bulk)")
        ax.axvline(sp.value, color="#999", ls="--", lw=0.8)
        ax.axhline(1.0, color="#999", ls=":", lw=0.8)
        ax.set_title(title, fontsize=7.5)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("relative to baseline")
    axes[0, 0].legend(frameon=False, fontsize=6)
    fig.tight_layout()
    save(fig, "fig_sweeps")
    return out


# ============================================================================================ 9 literature pathways
def fig_literature(data, res_kg: dict) -> pd.DataFrame:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), gridspec_kw={"width_ratios": [1, 1.25]})
    rows = []
    for s in LIT + ["SP_optimised_recirculation", "BC_lactate_30d", "GYP_WCFC_single_dose"]:
        r = res_kg[s]
        rows.append({"item": LABEL[s], "gwp": r.gwp(), "ap": float(r.totals(("A1", "A2", "A3"))["AP"]), "lit": s.startswith("LIT_")})
    df = pd.DataFrame(rows).sort_values("gwp")
    ax = axes[0]
    ax.barh(np.arange(len(df)), df["gwp"], color=["#72b7b2" if l else "#4c78a8" for l in df["lit"]], height=0.7)
    for yi, v in enumerate(df["gwp"]):
        ax.text(v * 1.05, yi, f"{v:.2f}", va="center", fontsize=6.3)
    ax.set_yticks(np.arange(len(df)), df["item"])
    ax.set_xscale("log")
    ax.set_xlabel("GWP-total [kg CO$_2$ eq per kg product], A1–A3 (log)")
    ax.set_title("(a) Literature pathways vs the block scenarios")
    # per kg CaCO3
    lit = data.literature_results
    g = lit[(lit["indicator"] == "GWP") & (lit["functional_unit"].isin(["1 kg CaCO3", "1 t CaCO3"]))].copy()
    g["v"] = [v / 1000 if fu == "1 t CaCO3" else v for v, fu in zip(g["value"], g["functional_unit"])]
    g["item"] = [f"{s.split(' ')[0]} ({p})" for s, p in zip(g["study"], g["pathway_or_variant"])]
    g["item"] = g["study"].str.replace(" et al. ", " ") + ": " + g["pathway_or_variant"] + g["system"].str.extract(r"(, (?:lab|commercial)[^,]*)")[0].fillna("")
    lit_rows = [{"item": it, "v": v, "kind": "literature"} for it, v in zip(g["item"], g["v"])]
    model_rows = []
    for s in ["SP_lab_protocol_90d", "SP_optimised_stoichiometric", "SP_optimised_recirculation", "BC_lactate_30d", "LIT_SP_NH4YE_medium", "LIT_EICP", "LIT_denitrification"]:
        r = run_scenario(s, data, functional_unit="kg_caco3_precipitated")
        ct = r.contrib
        keep = ct["group"].str.contains("nutrient medium|calcium source|urea|Cultivation: media|Casting|Waste fines", case=False, regex=True) & ct["module"].isin(["A1"])
        model_rows.append({"item": f"model {LABEL[s]} (materials only)", "v": float(ct[keep]["GWP-total"].sum()), "kind": "model-materials", "full": r.gwp()})
    comb = pd.DataFrame(lit_rows + model_rows).sort_values("v")
    ax = axes[1]
    ax.barh(np.arange(len(comb)), comb["v"], color=["#bab0ac" if k == "literature" else "#4c78a8" for k in comb["kind"]], height=0.7)
    for yi, (v, k, row) in enumerate(zip(comb["v"], comb["kind"], comb.itertuples())):
        txt = f"{v:.2f}" + (f" (full: {row.full:.1f})" if k != "literature" else "")
        ax.text(v * 1.05, yi, txt, va="center", fontsize=5.8)
    ax.set_yticks(np.arange(len(comb)), comb["item"], fontsize=6)
    ax.set_xscale("log")
    ax.set_xlabel("kg CO$_2$ eq per kg precipitated CaCO$_3$ (log)")
    ax.set_title("(b) Cross-check per kg CaCO$_3$ (materials only)")
    fig.tight_layout()
    save(fig, "fig_literature")
    return comb


# ============================================================================================ 10 uncertainty
def fig_uncertainty(data, res_kg: dict, run_mc: bool) -> dict:
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.4), gridspec_kw={"width_ratios": [1.05, 1]})
    out = {}
    for i, (ax, s) in enumerate(zip(axes[0], ["GYP_WCFC_single_dose", "SP_optimised_recirculation"])):
        oat = oat_sensitivity(s, data, top=10)
        base = float(oat["base"].iloc[0])
        d = oat.iloc[::-1]
        y = np.arange(len(d))
        ax.barh(y, d["result_low"] - base, color="#4c78a8", height=0.7, label="low bound")
        ax.barh(y, d["result_high"] - base, color="#e45756", height=0.7, label="high bound", alpha=0.85)
        ax.set_yticks(y, [pretty(i) for i in d["input"]], fontsize=6.3)
        ax.axvline(0, color="k", lw=0.6)
        ax.set_xlabel(f"Δ GWP-total [kg CO$_2$ eq/kg] from {base:.3g}")
        ax.set_title(f"({chr(97 + i)}) Tornado, {LABEL[s]}")
        out[("oat", s)] = oat
    axes[0, 0].legend(frameon=False, fontsize=6, loc="lower right")
    # MC
    mc_scen = ["GYP_WCFC_single_dose", "BC_lactate_30d", "SP_lab_protocol_90d", "SP_optimised_recirculation"]
    ax = axes[1, 0]
    for i, s in enumerate(mc_scen):
        f = ROOT / "paper" / "figures" / f"mc_{s}.csv"
        if run_mc or not f.exists():
            mc = monte_carlo(s, data, MCSettings(n=1000, seed=7))
            mc.category_samples.to_csv(f, index=False)
            mc.input_samples.to_csv(ROOT / "paper" / "figures" / f"mc_inputs_{s}.csv", index=False)
            samples = mc.category_samples["GWP-total"]
            sp = mc.spearman("GWP-total", top=40)
            sp.to_csv(ROOT / "paper" / "figures" / f"mc_spearman_{s}.csv", header=["rho"])
        else:
            samples = pd.read_csv(f)["GWP-total"]
            sp = pd.read_csv(ROOT / "paper" / "figures" / f"mc_spearman_{s}.csv", index_col=0)["rho"]
        det = res_kg[s].gwp()
        rel = samples / det
        ax.hist(rel, bins=60, histtype="step", lw=1.3, color=PALETTE[i], label=f"{LABEL[s]} (det. {det:.2f})", density=True)
        out[("mc", s)] = {"samples": samples, "spearman": sp, "det": det}
    ax.axvline(1.0, color="k", ls="--", lw=0.8)
    ax.set_xlabel("GWP-total / deterministic value")
    ax.set_ylabel("probability density")
    ax.set_title("(c) Monte Carlo (1000 samples), A1–A3")
    ax.legend(frameon=False, fontsize=6, loc="upper right")
    ax.set_xlim(0.5, 2.2)
    # Spearman GYP
    ax = axes[1, 1]
    sp = out[("mc", "GYP_WCFC_single_dose")]["spearman"]
    thr = 3 / math.sqrt(1000)
    sp = sp[sp.abs() >= thr].head(10).iloc[::-1]
    ax.barh(np.arange(len(sp)), sp.to_numpy(), color=["#e45756" if v > 0 else "#54a24b" for v in sp.to_numpy()], height=0.7)
    ax.set_yticks(np.arange(len(sp)), [pretty(i) for i in sp.index], fontsize=6.3)
    ax.set_xlabel("Spearman ρ with GWP-total")
    ax.set_title("(d) Global sensitivity, GYP-WCFC")
    fig.tight_layout()
    save(fig, "fig_uncertainty")
    return out


# ============================================================================================ 11 cost
def fig_cost(data, res_kg: dict) -> pd.DataFrame:
    scen = ["SP_lab_protocol_90d", "SP_optimised_recirculation", "SP_feather_media", "BC_lactate_30d", "BC_feather_media", "GYP_WCFC_single_dose",
            "GYP_WCFC_single_dose_feather", "TR_fungal_lactate", "ABIOTIC_WCFC_gypsum", "LIT_SP_NH4YE_medium", "LIT_EICP"]
    rows = []
    for s in scen:
        cb, cl = cost_summary(res_kg[s], data, "bulk"), cost_summary(res_kg[s], data, "lab")
        rows.append({"id": s, "item": LABEL[s], "bulk": cb["total_A1-A3"], "lab": cl["total_A1-A3"], "gwp": res_kg[s].gwp(), "pathway": scen_pathway(data, s)})
    df = pd.DataFrame(rows).sort_values("bulk")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), gridspec_kw={"width_ratios": [1.2, 1]})
    ax = axes[0]
    y = np.arange(len(df))
    ax.barh(y - 0.18, df["bulk"], height=0.36, color="#4c78a8", label="bulk / technical grade")
    ax.barh(y + 0.18, df["lab"], height=0.36, color="#f58518", label="laboratory grade")
    ax.set_yticks(y, df["item"])
    ax.set_xscale("log")
    ax.set_xlabel("indicative cost [EUR per kg product], A1–A3 (log)")
    ax.set_title("(a) Cost at bulk vs laboratory-grade prices")
    ax.legend(frameon=False, fontsize=6, loc="lower right")
    ax = axes[1]
    offsets = {"BC_lactate_30d": (-4, 6), "SP_optimised_recirculation": (4, -8), "BC_feather_media": (-46, 3), "TR_fungal_lactate": (-42, -2),
               "LIT_SP_NH4YE_medium": (5, -9), "LIT_EICP": (4, -8), "GYP_WCFC_single_dose_feather": (4, 6)}
    for _, r in df.iterrows():
        ax.scatter(r["gwp"], r["bulk"], color=PATHWAY_COLOUR.get(r["pathway"], "#999"), s=28, zorder=3)
        ax.annotate(r["item"], (r["gwp"], r["bulk"]), fontsize=5.6, xytext=offsets.get(r["id"], (3, 3)), textcoords="offset points")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("GWP-total [kg CO$_2$ eq per kg], A1–A3")
    ax.set_ylabel("cost, bulk grade [EUR per kg]")
    ax.set_title("(b) Eco-efficiency map")
    fig.tight_layout()
    save(fig, "fig_cost")
    return df


# ============================================================================================ 12 application screenshots
def fig_app_screens() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:  # noqa: BLE001
        return False
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1500, "height": 980})
            pg.goto("http://localhost:8501/Scenario_builder", wait_until="networkidle", timeout=90000)
            pg.wait_for_timeout(6000)
            pg.get_by_text("Custom composition").first.click()
            pg.wait_for_timeout(6000)
            pg.screenshot(path=str(FIG / "shot_builder_custom.png"), full_page=False)
            pg.get_by_text("4 · Parametric analysis").click()
            pg.wait_for_timeout(10000)
            pg.screenshot(path=str(FIG / "shot_parametric.png"), full_page=False)
            pg.goto("http://localhost:8501/Compare", wait_until="networkidle", timeout=90000)
            pg.wait_for_timeout(8000)
            pg.screenshot(path=str(FIG / "shot_compare.png"), full_page=False)
            pg.goto("http://localhost:8501/Uncertainty", wait_until="networkidle", timeout=90000)
            pg.wait_for_timeout(9000)
            pg.screenshot(path=str(FIG / "shot_uncertainty.png"), full_page=False)
            b.close()
    except Exception as exc:  # noqa: BLE001
        print("screenshots failed:", exc)
        return False
    from PIL import Image, ImageDraw, ImageFont
    files = ["shot_builder_custom.png", "shot_parametric.png", "shot_compare.png", "shot_uncertainty.png"]
    ims = []
    for f in files:
        im = Image.open(FIG / f)
        w, h = im.size
        ims.append(im.crop((300, 60, w - 30, h)))          # drop the navigation sidebar and the toolbar
    w, h = ims[0].size
    gap = 28
    canvas = Image.new("RGB", (2 * w + gap, 2 * h + gap), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("times.ttf", 44)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    for i, (im, lab) in enumerate(zip(ims, "abcd")):
        x, y = (i % 2) * (w + gap), (i // 2) * (h + gap)
        canvas.paste(im, (x, y))
        draw.rectangle((x, y, x + 62, y + 58), fill="#1f3b5a")
        draw.text((x + 14, y + 6), f"({lab})", fill="white", font=font)
    canvas = canvas.resize((canvas.width * 3 // 5, canvas.height * 3 // 5), Image.LANCZOS)
    canvas.save(FIG / "fig_app_screens.png", optimize=True)
    print("figure fig_app_screens")
    return True


def fig_report_gallery() -> bool:
    try:
        import fitz
    except Exception:  # noqa: BLE001
        return False
    src = ROOT / "paper" / "appendix_report.pdf"
    if not src.exists():
        src = ROOT / "results" / "report_GYP_WCFC_single_dose.pdf"
    if not src.exists():
        return False
    doc = fitz.open(str(src))
    pages = [0, 1, 3, 4, 5, 7, 8, 10][: len(doc)]
    from PIL import Image
    ims = []
    for i in pages:
        pix = doc[i].get_pixmap(dpi=55)
        ims.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    w, h = ims[0].size
    gap = 10
    cols = 4
    rows = -(-len(ims) // cols)
    canvas = Image.new("RGB", (cols * w + (cols - 1) * gap, rows * h + (rows - 1) * gap), "#dddddd")
    for i, im in enumerate(ims):
        canvas.paste(im, ((i % cols) * (w + gap), (i // cols) * (h + gap)))
    canvas.save(FIG / "fig_report_gallery.png", optimize=True)
    print("figure fig_report_gallery")
    return True


# ============================================================================================ tables
def table_scenarios(data) -> None:
    lines = ["\\begin{tabular}{l l l l p{2.9cm} r r r p{3.2cm}}", "\\toprule",
             "Label & Pathway / organism & Fines & Nutrient base & Reagents (g/L) & Doses & Days & L/S (L/kg) & Process options \\\\ \\midrule"]
    for s in BLOCK + LIT:
        cfg = data.scenario_config(s)
        p = data.protocols[cfg["protocol"]]
        st = data.strains[p["strain"]]
        bs = p["biocementation_solution"]
        r = run_scenario(s, data)
        ORG = {"sporosarcina_pasteurii_DSM33": r"\textit{S.~pasteurii} (ureolytic)", "sutcliffiella_cohnii_DSM6307": r"\textit{S.~cohnii} (Ca-lactate oxidation)",
               "alkalihalobacillus_pseudofirmus_DSM8715": r"\textit{A.~pseudofirmus} (Ca-lactate oxidation)", "trichoderma_reesei_DSM768": r"\textit{T.~reesei} (fungal)",
               "sporosarcina_pasteurii_altmedia": r"\textit{S.~pasteurii}, alternative media", "eicp_jack_bean_urease": "jack-bean urease (EICP)",
               "pseudomonas_denitrificans": "denitrifying bacteria", "bacillus_acetate_oxidiser": r"\textit{Bacillus} sp. (acetate oxidation)",
               "synechococcus_cyanobacteria": "cyanobacteria (photosynthetic)"}
        org = ORG.get(p["strain"], st.get("name", p["strain"]).split(" (")[0])
        opts = []
        if cfg.get("scale") == "lab":
            opts.append("lab energy")
        if cfg.get("effluent_treatment", "none") != "none":
            opts.append(cfg["effluent_treatment"].replace("_", " "))
        if cfg.get("module_d"):
            opts.append("module D")
        if cfg.get("cultivation_variant"):
            opts.append(f"medium: {cfg['cultivation_variant']}")
        if (cfg.get("reagent_optimisation") or {}).get("urea_to_ca_molar_ratio"):
            opts.append(f"urea:Ca {cfg['reagent_optimisation']['urea_to_ca_molar_ratio']}")
        if (cfg.get("reagent_optimisation") or {}).get("solution_recirculation_fraction"):
            opts.append(f"recirc. {cfg['reagent_optimisation']['solution_recirculation_fraction']}")
        if cfg.get("temperature_override_C"):
            opts.append(f"{cfg['temperature_override_C']} °C")
        if cfg.get("carbon_accounting", "EF31") != "EF31":
            opts.append("EN 15804 $-$1/+1")
        if cfg.get("abiotic"):
            opts.append("abiotic")
        REAG = {"calcium_lactate_pentahydrate": "CaL$_2$", "calcium_chloride": "CaCl$_2$", "calcium_acetate_bio": "CaAc (bio)", "calcium_acetate": "CaAc",
                "calcium_nitrate_tetrahydrate": "Ca(NO$_3$)$_2$", "sodium_bicarbonate": "NaHCO$_3$", "sodium_nitrate": "NaNO$_3$", "urea": "urea",
                "jack_bean_meal": "jack-bean meal", "non_fat_milk_powder": "milk powder"}
        reag = ", ".join(f"{REAG.get(k, tex(k))} {v:g}" for k, v in (bs.get("supplements") or {}).items())
        lines.append(f"{LABEL[s]} & {org} & {tex(cfg.get('material') or p['material'])} & {tex(bs.get('base_medium', ''))} & {reag} & {r.meta['n_doses']} & {r.meta['incubation_d']:g} & {r.meta['liquid_to_solid_L_per_kg']:.2g} & {tex('; '.join(opts)) or '--'} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (TAB / "tab_scenarios.tex").write_text("\n".join(lines), encoding="utf-8")


def table_results(data, res_kg: dict) -> None:
    cats = ["GWP-total", "AP", "EP-terrestrial", "EP-freshwater", "POCP", "ADP-fossil", "WDP"]
    lines = ["\\begin{tabular}{l r r r r r r r r}", "\\toprule",
             "Scenario / product & GWP & GWP+C & AP & EP-terr. & EP-fw & POCP & ADP-f & WDP \\\\",
             " & kg CO$_2$ eq & kg CO$_2$ eq & mol H$^+$ eq & mol N eq & kg P eq & kg NMVOC eq & MJ & m$^3$ eq \\\\ \\midrule"]
    for s in BLOCK + LIT:
        r = res_kg[s]
        t = r.totals(("A1", "A2", "A3"))
        c = float(r.totals(("C1", "C2", "C3", "C4"))["GWP-total"])
        lines.append(f"{LABEL[s]} & {fmt3(float(t['GWP-total']))} & {fmt3(float(t['GWP-total']) + c)} & " + " & ".join(fmt3(float(t[k])) for k in cats[1:]) + " \\\\")
    lines.append("\\midrule")
    for b in BENCH:
        v = benchmark_impacts(b, data, functional_unit="kg_product", include_eol=False)
        vc = benchmark_impacts(b, data, functional_unit="kg_product", include_eol=True)
        lines.append(f"{LABEL[b]} & {fmt3(float(v['GWP-total']))} & {fmt3(float(vc['GWP-total']))} & " + " & ".join(fmt3(float(v[k])) if v[k] == v[k] else "--" for k in cats[1:]) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (TAB / "tab_results.tex").write_text("\n".join(lines), encoding="utf-8")


def table_mc(mc_out: dict, res_kg: dict) -> None:
    lines = ["\\begin{tabular}{l r r r r r r r}", "\\toprule",
             "Scenario & Deterministic & P2.5 & P25 & Median & P75 & P97.5 & CV \\\\ \\midrule"]
    for (kind, s), v in mc_out.items():
        if kind != "mc":
            continue
        y = v["samples"]
        q = y.quantile([0.025, 0.25, 0.5, 0.75, 0.975])
        lines.append(f"{LABEL[s]} & {fmt3(v['det'])} & {fmt3(q[0.025])} & {fmt3(q[0.25])} & {fmt3(q[0.5])} & {fmt3(q[0.75])} & {fmt3(q[0.975])} & {100 * y.std() / y.mean():.0f}\\% \\\\")
        macro(f"mcMedian{s}", q[0.5]); macro(f"mcLo{s}", q[0.025]); macro(f"mcHi{s}", q[0.975]); macro(f"mcCV{s}", 100 * y.std() / y.mean(), "{:.0f}")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (TAB / "tab_mc.tex").write_text("\n".join(lines), encoding="utf-8")


def table_cost(df: pd.DataFrame) -> None:
    lines = ["\\begin{tabular}{l r r r r}", "\\toprule", "Scenario & Bulk grade & Laboratory grade & Ratio & GWP (A1--A3) \\\\",
             " & EUR/kg & EUR/kg & -- & kg CO$_2$ eq/kg \\\\ \\midrule"]
    for _, r in df.iterrows():
        lines.append(f"{r['item']} & {fmt3(r['bulk'])} & {fmt3(r['lab'])} & {r['lab'] / r['bulk']:.1f} & {fmt3(r['gwp'])} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (TAB / "tab_cost.tex").write_text("\n".join(lines), encoding="utf-8")


def table_scaleup(data) -> None:
    from micp_lca.inventory import Params
    P = Params(data.scaleup, "industrial")
    names = {"industrial.medium_sterilisation.heat_recovery": ("Sterilisation heat recovery", "--"),
             "industrial.medium_sterilisation.electricity_kWh_per_m3": ("Sterilisation electricity", "kWh/m$^3$"),
             "industrial.fermentation.power_kW_per_m3": ("Fermenter agitation/aeration power", "kW/m$^3$"),
             "industrial.fermentation.temperature_control_kWh_per_m3_day": ("Fermenter temperature control", "kWh/(m$^3$ d)"),
             "industrial.fermentation.hydrolysate_heating_heat_recovery": ("Hydrolysate heating heat recovery", "--"),
             "industrial.harvest.centrifuge_kWh_per_m3": ("Centrifugation", "kWh/m$^3$"),
             "industrial.solids_mixing_kWh_per_t": ("Solids mixing", "kWh/t"),
             "industrial.solution_dosing_kWh_per_m3": ("Solution dosing/pumping", "kWh/m$^3$"),
             "industrial.curing_chamber.U_W_m2K": ("Curing chamber U-value", "W/(m$^2$ K)"),
             "industrial.curing_chamber.chamber_m3_per_t_product": ("Chamber volume per t product", "m$^3$/t"),
             "industrial.curing_chamber.ambient_C": ("Ambient temperature", "$^{\\circ}$C"),
             "industrial.curing_chamber.air_handling_kWh_per_t_day": ("Air handling", "kWh/(t d)"),
             "industrial.drying.fan_kWh_per_t": ("Drying fan energy", "kWh/t"),
             "industrial.effluent.fraction_drained": ("Fraction of liquids drained", "--"),
             "industrial.effluent.basic_treatment_kWh_per_m3": ("Basic effluent treatment", "kWh/m$^3$"),
             "industrial.effluent.ammonia_stripping.electricity_kWh_per_kgN": ("NH$_3$ stripping electricity", "kWh/kg N"),
             "industrial.effluent.ammonia_stripping.efficiency": ("NH$_3$ stripping efficiency", "--"),
             "industrial.effluent.struvite.efficiency": ("Struvite precipitation efficiency", "--"),
             "industrial.nitrogen_fate.urea_hydrolysed_fraction": ("Urea hydrolysed fraction", "--"),
             "industrial.nitrogen_fate.nh3_volatilised_fraction_of_retained_N": ("NH$_3$ volatilised share of retained N", "--"),
             "industrial.nitrogen_fate.n2o_fraction_of_N": ("N$_2$O share of released N", "--"),
             "industrial.lactate_fate.oxidised_fraction": ("Lactate oxidised fraction", "--")}
    lines = ["\\begin{tabular}{l l r r r}", "\\toprule", "Parameter & Unit & Value & Min & Max \\\\ \\midrule"]
    rng = P.ranges("industrial")
    for k, (lab, unit) in names.items():
        if k in rng:
            v, lo, hi = rng[k]
            lines.append(f"{lab} & {unit} & {v:g} & {lo:g} & {hi:g} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (TAB / "tab_scaleup.tex").write_text("\n".join(lines), encoding="utf-8")


CITEMAP = {"FERTEUROPE2018": r"\cite{FertilizersEurope_2018}", "PORTER2021": r"\cite{Porter_2021}", "CORBION2020": r"\cite{Morao_2019}",
           "BECKER2023": r"\cite{Becker_2023}", "EMBER2024": r"\cite{Ember_2024}", "OBD2024II": r"\cite{OBD_2024}", "NEZERKA2023LCA": r"\cite{Nezerka_2023_RCF_blocks}",
           "AGRIBALYSE4": r"\cite{AGRIBALYSE_2025}", "ENVIRONDEC3048": r"\cite{Environdec_3048}", "OTTOVA2026": r"\cite{Ottova_2026_feather}",
           "DENG2021": r"\cite{Deng_2021}", "CARBONCLOUD2023": "CarbonCloud (2023)", "EEA2024": "EEA (2024)"}


def table_background(data) -> None:
    rows = []
    for pid in ["urea_EU", "calcium_chloride", "calcium_lactate_pentahydrate", "tryptone_casein", "peptone_generic", "yeast_extract", "beef_extract",
                "chicken_feathers", "electricity_CZ_lv", "heat_natural_gas", "sodium_chloride", "hydrochloric_acid", "sodium_hydroxide",
                "transport_truck", "landfill_inert", "water_tap", "aac_block_avg", "brick_clay_avg"]:
        if pid not in data.background:
            continue
        p = data.background[pid]
        rows.append(f"{tex(p.name[:52])}{'…' if len(p.name) > 52 else ''} & {p.unit} & {fmt3(p.gwp_any)} & {f'{fmt3(p.gwp_min)}--{fmt3(p.gwp_max)}' if p.gwp_min and p.gwp_max else '--'} & {p.data_type} & {','.join(map(str, p.pedigree))} & {pedigree_gsd(p.pedigree, p.basic_uncertainty):.2f} & {CITEMAP.get(p.source_id, tex(p.source_id))} \\\\")
    lines = ["\\begin{tabular}{p{7.2cm} l r l l l r l}", "\\toprule", "Dataset & Unit & GWP & Range & Type & Pedigree & $\\sigma_g$ & Source \\\\ \\midrule"] + rows + ["\\bottomrule", "\\end{tabular}"]
    (TAB / "tab_background.tex").write_text("\n".join(lines), encoding="utf-8")


def table_literature(comb: pd.DataFrame) -> None:
    lines = ["\\begin{tabular}{p{8.2cm} r r}", "\\toprule", "Item & Materials only & Full cradle-to-gate \\\\", " & kg CO$_2$ eq / kg CaCO$_3$ & kg CO$_2$ eq / kg CaCO$_3$ \\\\ \\midrule"]
    for _, r in comb.iterrows():
        full = fmt3(r["full"]) if r["kind"] != "literature" and r["full"] == r["full"] else "--"
        lines.append(f"{tex(r['item'])} & {fmt3(r['v'])} & {full} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (TAB / "tab_literature.tex").write_text("\n".join(lines), encoding="utf-8")


# ============================================================================================ main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-mc", action="store_true", help="reuse cached Monte Carlo samples")
    ap.add_argument("--no-screens", action="store_true")
    args = ap.parse_args()
    data = load_data()
    res_kg = {s: run_scenario(s, data, functional_unit="kg_product") for s in BLOCK + LIT + ["SP_lab_scale_energy_90d", "SP_lab_protocol_90d_WCFG", "GYP_WCFC_single_dose_EN15804"]}
    res_m3 = {s: run_scenario(s, data, functional_unit="m3_product") for s in BLOCK}
    res_mpa = {}
    for s in BLOCK:
        try:
            res_mpa[s] = run_scenario(s, data, functional_unit="m3_MPa")
        except ValueError:
            pass

    # database counts ----------------------------------------------------------------------
    macro("nBackground", len(data.background), "{:d}")
    macro("nObd", sum(p.data_type == "oekobaudat" for p in data.background.values()), "{:d}")
    macro("nAgri", sum(p.data_type == "agribalyse" for p in data.background.values()), "{:d}")
    macro("nLitFactors", sum(p.data_type in ("literature", "estimate", "proxy", "secondary_material") for p in data.background.values()), "{:d}")
    macro("nChemicals", len([k for k in data.chemicals if not k.startswith("_")]), "{:d}")
    macro("nMedia", len(data.media), "{:d}"); macro("nStrains", len(data.strains), "{:d}"); macro("nMaterials", len(data.materials), "{:d}")
    macro("nProtocols", len(data.protocols), "{:d}"); macro("nScenarios", len(data.scenarios["scenarios"]), "{:d}")
    macro("nBenchmarks", len(data.scenarios["benchmarks"]), "{:d}"); macro("nSources", len(data.sources), "{:d}")
    macro("nExperimental", len(data.experimental), "{:d}"); macro("nPrices", len(data.prices), "{:d}"); macro("nLitResults", len(data.literature_results), "{:d}")
    macro("nCFsubset", len(data.characterization_factors), "{:d}"); macro("nCFfull", len(data.cf_full()), "{:,d}")
    macro("nSweepParams", len(available_parameters("SP_lab_protocol_90d", data)), "{:d}")
    # what the Monte Carlo analysis samples (Section 3.6)
    macro("nScaleupRanges", len(Params(data.scaleup, "industrial").ranges("industrial")), "{:d}")
    macro("nLitRanges", sum(1 for q in data.background.values() if q.gwp_min and q.gwp_max and q.gwp_max > q.gwp_min > 0), "{:d}")
    obd_gsd = {round(pedigree_gsd(q.pedigree, q.basic_uncertainty), 2) for q in data.background.values() if q.data_type == "oekobaudat"}
    macro("gsdOBD", min(obd_gsd) if len(obd_gsd) == 1 else f"{min(obd_gsd):.2f}--{max(obd_gsd):.2f}", "{:.2f}")
    for s in ["GYP_WCFC_single_dose", "SP_lab_protocol_90d"]:
        used = [data.background[f.key] for f in build_inventory(s, data).flows if f.kind == "background"]
        used = {q.process_id: q for q in used}.values()
        macro(f"nMCbg{s}", sum(1 for q in used if q.data_type != "secondary_material" and q.gwp_any), "{:d}")
        macro(f"nMCbgLit{s}", sum(1 for q in used if q.gwp_min and q.gwp_max and q.gwp_max > q.gwp_min > 0), "{:d}")

    # headline numbers ---------------------------------------------------------------------
    for s, r in res_kg.items():
        t = r.totals(("A1", "A2", "A3"))
        c = r.totals(("C1", "C2", "C3", "C4"))
        macro(f"gwp{s}", float(t["GWP-total"])); macro(f"gwpc{s}", float(t["GWP-total"] + c["GWP-total"]))
        macro(f"ap{s}", float(t["AP"])); macro(f"ept{s}", float(t["EP-terrestrial"])); macro(f"wdp{s}", float(t["WDP"])); macro(f"adpf{s}", float(t["ADP-fossil"]))
        macro(f"caco{s}", 100 * r.meta["caco3_precipitated_kg_per_kg_solids"], "{:.2f}")
        macro(f"lsr{s}", r.meta["liquid_to_solid_L_per_kg"])
        macro(f"ndoses{s}", r.meta["n_doses"], "{:d}")
        macro(f"covAP{s}", 100 * r.coverage_native.get("AP", 0), "{:.0f}")
        macro(f"covGWP{s}", 100 * r.coverage_native.get("GWP-total", 0), "{:.0f}")
        if r.meta.get("urea_to_ca_molar_ratio"):
            macro(f"ureaCa{s}", r.meta["urea_to_ca_molar_ratio"])
    for s in BLOCK:
        if s in res_m3:
            r = res_m3[s]
            macro(f"gwpmc{s}", r.gwp() + float(r.totals(("C1", "C2", "C3", "C4"))["GWP-total"]), "{:.0f}")
        if s in res_mpa:
            r = res_mpa[s]
            macro(f"gwpmpa{s}", r.gwp() + float(r.totals(("C1", "C2", "C3", "C4"))["GWP-total"]), "{:.0f}")
    for b in BENCH:
        v = benchmark_impacts(b, data, functional_unit="kg_product", include_eol=False)
        vc = benchmark_impacts(b, data, functional_unit="kg_product", include_eol=True)
        vm = benchmark_impacts(b, data, functional_unit="m3_product", include_eol=True)
        vmpa = benchmark_impacts(b, data, functional_unit="m3_MPa", include_eol=True)
        macro(f"gwp{b}", float(v["GWP-total"])); macro(f"gwpc{b}", float(vc["GWP-total"])); macro(f"gwpmc{b}", float(vm["GWP-total"]), "{:.0f}"); macro(f"gwpmpa{b}", float(vmpa["GWP-total"]), "{:.0f}")
        macro(f"ap{b}", float(v["AP"]))
    # shares
    for s in ["SP_lab_protocol_90d", "BC_lactate_30d", "GYP_WCFC_single_dose", "SP_optimised_recirculation", "GYP_WCFC_single_dose_feather"]:
        r = res_kg[s]
        g = r.contrib[r.contrib.module.isin(["A1", "A2", "A3"])].groupby("group")["GWP-total"].sum()
        tot = g.sum()
        for grp, val in g.items():
            macro(f"share{s}{grp}", 100 * val / tot, "{:.0f}")
        ga = r.contrib[r.contrib.module.isin(["A1", "A2", "A3"])].groupby("group")["AP"].sum()
        for grp, val in ga.items():
            macro(f"shareAP{s}{grp}", 100 * val / ga.sum(), "{:.0f}")
        nf = r.meta.get("nitrogen_fate_kg_per_kg_solids") or {}
        for k, v in nf.items():
            macro(f"nfate{s}{k}", v * r.fu_factor)
        macro(f"nhyd{s}", r.meta["n_hydrolysed_kg_per_kg_solids"] * r.fu_factor)
        macro(f"cofoss{s}", r.meta["co2_fossil_direct_kg_per_kg_solids"] * r.fu_factor)
        macro(f"uptake{s}", r.meta["carbonation_uptake_kg_per_kg_solids"] * r.fu_factor)
    r = res_kg["SP_lab_scale_energy_90d"]
    macro("gwpLabEnergy", r.gwp(), "{:.0f}")
    sq = compare_with_status_quo(res_kg["GYP_WCFC_single_dose"], data, "AAC_block_ODB", "GWP-total")
    for k, v in sq.items():
        macro(f"sq{k}", v)
    sq2 = compare_with_status_quo(res_kg["BC_lactate_30d"], data, "AAC_block_ODB", "GWP-total")
    macro("sqBCdiff", sq2["difference_bio_minus_status_quo"])
    ref = benchmark_impacts("AAC_block_ODB", data, functional_unit="kg_product", include_eol=False)
    for s in ["GYP_WCFC_single_dose", "GYP_WCFC_single_dose_feather", "BC_lactate_30d", "SP_optimised_recirculation", "SP_lab_protocol_90d"]:
        macro(f"ratioAAC{s}", 100 * (1 - res_kg[s].gwp() / float(ref["GWP-total"])), "{:.0f}")
        macro(f"ratioAPAAC{s}", float(res_kg[s].totals(("A1", "A2", "A3"))["AP"]) / float(ref["AP"]), "{:.1f}")
    # derived numbers quoted in the text
    g_lab = res_kg["SP_lab_protocol_90d"].gwp()
    for s in ["SP_optimised_stoichiometric", "SP_optimised_recirculation", "SP_feather_media"]:
        macro(f"red{s}", 100 * (1 - res_kg[s].gwp() / g_lab), "{:.0f}")
    macro("timesAACSPlab", g_lab / float(ref["GWP-total"]), "{:.1f}")
    g = res_kg["GYP_WCFC_single_dose"]
    gg = g.contrib[g.contrib.module.isin(["A1", "A2", "A3"])].groupby("group")["GWP-total"].sum()
    macro("uptakeShareGYP", -100 * gg.get("Carbonation uptake", 0.0) / gg.sum(), "{:.0f}")
    macro("nhydRatioSPrecirc", res_kg["SP_lab_protocol_90d"].meta["n_hydrolysed_kg_per_kg_solids"] / res_kg["SP_optimised_recirculation"].meta["n_hydrolysed_kg_per_kg_solids"], "{:.0f}")
    macro("sqBenefitGYP", -sq["difference_bio_minus_status_quo"])
    macro("gypRepIncrease", 100 * (res_kg["GYP_WCFC_repeated"].gwp() / res_kg["GYP_WCFC_single_dose"].gwp() - 1), "{:.0f}")
    macro("eolShareGYP", 100 * float(res_kg["GYP_WCFC_single_dose"].totals(("C1", "C2", "C3", "C4"))["GWP-total"]) / float(res_kg["GYP_WCFC_single_dose"].totals()["GWP-total"]), "{:.0f}")
    macro("eolGWP", float(res_kg["GYP_WCFC_single_dose"].totals(("C1", "C2", "C3", "C4"))["GWP-total"]), "{:.3f}")

    # figures -------------------------------------------------------------------------------
    fig_system_boundary()
    fig_architecture(data)
    fig_modelling_chain(data, res_kg, res_m3, res_mpa)
    fig_pathways()
    fig_levers(data, res_kg)
    fig_database(data, res_kg)
    fig_gwp_per_kg(data, res_kg)
    fig_per_m3(data, res_m3, res_mpa)
    fig_contributions(data, res_kg)
    mat = fig_heatmap(data, res_kg)
    fig_n_c_balance(data, res_kg)
    sweeps = fig_sweeps(data, res_kg)
    comb = fig_literature(data, res_kg)
    unc = fig_uncertainty(data, res_kg, run_mc=not args.no_mc)
    cost_df = fig_cost(data, res_kg)
    if not args.no_screens:
        fig_app_screens()
    fig_report_gallery()

    # sweep numbers ------------------------------------------------------------------------
    for (s, key), ok in sweeps.items():
        d = describe_sweep(ok, "GWP-total")
        tag = key.split(":")[-1].split(".")[-1]
        macro(f"sw{tag}{s}ymin", d["y_min"]); macro(f"sw{tag}{s}ymax", d["y_max"]); macro(f"sw{tag}{s}xmin", d["x_of_y_min"])
        macro(f"sw{tag}{s}span", 100 * d["relative_span"], "{:.0f}"); macro(f"sw{tag}{s}rtwo", d["r2_linear"], "{:.2f}")
        macro(f"sw{tag}{s}yatlo", d["y_at_min_x"]); macro(f"sw{tag}{s}yathi", d["y_at_max_x"])
        da = describe_sweep(ok, "AP")
        macro(f"sw{tag}{s}apspan", 100 * da["relative_span"], "{:.0f}"); macro(f"sw{tag}{s}apyatlo", da["y_at_min_x"]); macro(f"sw{tag}{s}apyathi", da["y_at_max_x"])
        macro(f"sw{tag}{s}apred", 100 * (1 - da["y_min"] / da["y_max"]), "{:.0f}")
        macro(f"sw{tag}{s}apfactor", da["y_max"] / max(da["y_min"], 1e-12), "{:.1f}")
        macro(f"sw{tag}{s}gwpfactor", d["y_max"] / max(d["y_min"], 1e-12), "{:.1f}")
        if "cost_bulk_EUR" in ok:
            dc = describe_sweep(ok, "cost_bulk_EUR")
            macro(f"sw{tag}{s}costlo", dc["y_at_min_x"]); macro(f"sw{tag}{s}costhi", dc["y_at_max_x"])
    # OAT numbers
    for (kind, s), v in unc.items():
        if kind == "oat":
            top = v.iloc[0]
            macro(f"oatTop{s}", tex(top["input"].replace("bg:", "").replace("fg:industrial.", "")), "{}")
            macro(f"oatTopLo{s}", top["result_low"]); macro(f"oatTopHi{s}", top["result_high"])
            macro(f"oatTopDlo{s}", top["delta_low_%"], "{:+.0f}"); macro(f"oatTopDhi{s}", top["delta_high_%"], "{:+.0f}")
        if kind == "mc":
            sp = v["spearman"]
            macro(f"mcTop{s}", tex(sp.index[0].replace("bg:", "").replace("fg:industrial.", "")), "{}")
            macro(f"mcTopRho{s}", sp.iloc[0], "{:+.2f}")
    # cost numbers
    for _, r in cost_df.iterrows():
        macro(f"costBulk{r['id']}", r["bulk"]); macro(f"costLab{r['id']}", r["lab"]); macro(f"costRatio{r['id']}", r["lab"] / r["bulk"], "{:.1f}")
    # literature cross-check numbers
    for _, r in comb.iterrows():
        if r["kind"] != "literature":
            sid = [k for k, v in LABEL.items() if f"model {v} (materials only)" == r["item"]]
            if sid:
                macro(f"litMat{sid[0]}", r["v"]); macro(f"litFull{sid[0]}", r["full"])
    # heat map numbers
    for s in mat.index:
        pass

    # tables --------------------------------------------------------------------------------
    table_scenarios(data)
    table_results(data, res_kg)
    table_mc(unc, res_kg)
    table_cost(cost_df)
    table_scaleup(data)
    table_background(data)
    table_literature(comb)

    # numbers.tex ---------------------------------------------------------------------------
    lines = ["% generated by scripts/make_paper_figures.py; do not edit"]
    for k, v in NUM.items():
        lines.append(f"\\newcommand{{\\{k}}}{{{v}}}")
    (ROOT / "paper" / "numbers.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ROOT / "paper" / "numbers.json").write_text(json.dumps(NUM, indent=1), encoding="utf-8")
    print("macros:", len(NUM))


if __name__ == "__main__":
    main()
