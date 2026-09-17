"""Scenario builder: pre-defined or custom compositions, technology settings, results, parametric analysis, PDF report."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml
from plotly.subplots import make_subplots

from micp_lca.inventory import Params
from micp_lca.parametric import available_parameters, describe_sweep, find_parameter, sweep
from utils import (ADDITIONAL, CORE, PALETTE, category_label, contribution_figure, cost_block, download_button, fu_label, get_data,
                   impacts_table, reload_data, run)

st.set_page_config(page_title="Scenario builder", page_icon="🧪", layout="wide")
data = get_data()
st.title("Scenario builder")

PATHWAYS = ["ureolytic", "organic_acid", "fungal", "eicp", "denitrification", "photosynthetic"]
CHEM_IDS = sorted(k for k in data.chemicals if not k.startswith("_"))
MEDIA_IDS = list(data.media)


def chem_name(cid: str) -> str:
    return (data.chemicals.get(cid) or {}).get("name", cid).split(" (")[0]


def med_label(mid: str) -> str:
    return f"{mid} — {data.media[mid].get('name', '')}" if mid in data.media else mid


# ============================================================================================ sidebar
with st.sidebar:
    st.header("Composition")
    mode = st.radio("Mode", ["Pre-defined composition", "Custom composition"])
    scen_names = list(data.scenarios["scenarios"])
    base = st.selectbox("Base scenario" if mode.startswith("Pre") else "Template scenario (start from)", scen_names,
                        index=scen_names.index("GYP_WCFC_single_dose") if "GYP_WCFC_single_dose" in scen_names else 0)
    base_cfg = data.scenario_config(base)
    st.caption(data.scenarios["scenarios"][base].get("description", ""))
    fu = st.selectbox("Functional unit", ["kg_product", "m3_product", "m3_MPa", "kg_caco3_precipitated", "kg_solids"], format_func=fu_label)
    st.markdown("---")
    st.caption("Results update automatically. Use the tabs to define the composition and the technology, to run a parametric "
               "analysis and to generate the PDF report.")

overrides: dict = {}
params: dict[str, float] = {}
tab_comp, tab_tech, tab_res, tab_sweep, tab_report, tab_save = st.tabs(
    ["1 · Composition", "2 · Technology & system", "3 · Results", "4 · Parametric analysis", "5 · PDF report", "6 · Save"])

# ============================================================================================ 1 composition
with tab_comp:
    if mode.startswith("Pre"):
        c1, c2, c3 = st.columns(3)
        protocol = c1.selectbox("Protocol (laboratory recipe)", list(data.protocols), index=list(data.protocols).index(base_cfg["protocol"]),
                                format_func=lambda k: f"{k} — {data.protocols[k].get('name', '')[:70]}")
        proto = data.protocols[protocol]
        material = c2.selectbox("Waste material", list(data.materials), index=list(data.materials).index(base_cfg.get("material") or proto["material"]),
                                format_func=lambda k: f"{k} — {data.materials[k].get('name', '')[:50]}")
        strain_id = proto["strain"]
        strain = data.strains[strain_id]
        variants = ["(protocol default)"] + list((strain.get("alternative_cultivation_media") or {}).keys())
        cv = c3.selectbox("Cultivation medium variant", variants,
                          index=variants.index(base_cfg["cultivation_variant"]) if base_cfg.get("cultivation_variant") in variants else 0)
        overrides.update({"protocol": protocol, "material": material, "cultivation_variant": None if cv == "(protocol default)" else cv})
        # composition card ---------------------------------------------------------------------
        cult = dict(strain.get("cultivation") or {})
        if cv != "(protocol default)":
            cult.update(strain["alternative_cultivation_media"][cv])
        bs = proto.get("biocementation_solution") or {}
        dosing = bs.get("dosing") or {}
        left, right = st.columns(2)
        with left:
            st.markdown("**Recipe per specimen**")
            rows = [("Dry solids", f"{proto.get('solids_g')} g (gypsum {100 * float(proto.get('gypsum_fraction', 0) or 0):.1f} %)"),
                    ("Organism / catalyst", f"{strain.get('name', strain_id)} — {strain.get('pathway')}"),
                    ("Suspension", f"{(proto.get('suspension') or {}).get('volume_mL', 0)} mL at OD600 {(proto.get('suspension') or {}).get('od600', 'n/a')}"),
                    ("Casting", f"saline {proto.get('saline_mL', 0)} mL; HCl {(proto.get('hcl') or {}).get('molarity', 0)} M × {(proto.get('hcl') or {}).get('volume_mL', 0)} mL"),
                    ("Biocementation solution", f"{med_label(bs.get('base_medium', ''))}"),
                    ("Reagents", ", ".join(f"{chem_name(k)} {v} g/L" for k, v in (bs.get("supplements") or {}).items()) or "none"),
                    ("Dosing", f"{dosing.get('mode', 'repeated')} — {bs.get('dose_mL')} mL"
                     + (f" every {dosing.get('interval_h')} h for {dosing.get('duration_d', (proto.get('incubation') or {}).get('duration_d'))} d" if dosing.get("mode", "repeated") == "repeated"
                        else (f" × {dosing.get('n_doses')}" if dosing.get("mode") == "fixed" else ""))),
                    ("Incubation", f"{(proto.get('incubation') or {}).get('temperature_C')} °C, {(proto.get('incubation') or {}).get('duration_d')} d"),
                    ("Drying", f"{(proto.get('drying') or {}).get('temperature_C', 'ambient')} °C, {(proto.get('drying') or {}).get('duration_d', 0)} d"),
                    ("Specimen", f"{(proto.get('specimen') or {}).get('shape', '')} {(proto.get('specimen') or {}).get('diameter_mm', '')}×{(proto.get('specimen') or {}).get('height_mm', '')} mm"),
                    ("Measured results", ", ".join(f"{k} = {v}" for k, v in (proto.get("results") or {}).items() if v is not None) or "n/a"),
                    ("Source", str(proto.get("source_id", "")))]
            st.table(pd.DataFrame(rows, columns=["item", "value"]).set_index("item"))
        with right:
            st.markdown("**Cultivation**")
            st.table(pd.DataFrame([("medium", med_label(cult.get("medium", ""))), ("temperature", f"{cult.get('temperature_C')} °C"), ("duration", f"{cult.get('duration_h')} h"),
                                   ("harvest OD600", str(cult.get("harvest_od600"))), ("harvest", str(cult.get("harvest", "none"))),
                                   ("supplements", ", ".join(f"{chem_name(k)} {v} g/L" for k, v in (cult.get("supplements") or {}).items()) or "none")],
                                  columns=["item", "value"]).set_index("item"))
            st.markdown("**Media recipes (g/L)**")
            meds = [mm for mm in (cult.get("medium"), cult.get("supplements_medium"), bs.get("base_medium")) if mm and mm in data.media]
            mdf = pd.DataFrame({mm: (data.media[mm].get("components") or {}) for mm in dict.fromkeys(meds)}).fillna(0.0)
            mdf.index = [chem_name(i) for i in mdf.index]
            st.dataframe(mdf.style.format("{:.3g}"), width="stretch")
        with st.expander("All pre-defined compositions (protocols of the papers and literature pathways)"):
            rows = []
            for pid, p in data.protocols.items():
                b = p.get("biocementation_solution") or {}
                dsg = b.get("dosing") or {}
                rows.append({"protocol": pid, "organism": data.strains.get(p["strain"], {}).get("name", p["strain"])[:40], "pathway": data.strains.get(p["strain"], {}).get("pathway"),
                             "material": p.get("material"), "gypsum %": 100 * float(p.get("gypsum_fraction", 0) or 0), "solids g": p.get("solids_g"),
                             "BS base medium": b.get("base_medium"), "reagents": ", ".join(f"{k} {v}" for k, v in (b.get("supplements") or {}).items()),
                             "dose mL": b.get("dose_mL"), "dosing": dsg.get("mode"), "interval h": dsg.get("interval_h"), "days": (p.get("incubation") or {}).get("duration_d"),
                             "T °C": (p.get("incubation") or {}).get("temperature_C"), "fc MPa": (p.get("results") or {}).get("fc_MPa"),
                             "CaCO3 gain wt%": (p.get("results") or {}).get("caco3_gain_wt_abs"), "source": p.get("source_id")})
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=420)
    else:
        # ------------------------------------------------------------------------------ custom composition editor
        tproto = copy.deepcopy(data.protocols[base_cfg["protocol"]])
        st.markdown("Define the composition and the technology of your own recipe. Fields are pre-filled from the template scenario; "
                    "every item can be changed, including the organism, the media and the reagents.")
        cA, cB, cC = st.columns(3)
        material = cA.selectbox("Waste material", list(data.materials), index=list(data.materials).index(base_cfg.get("material") or tproto["material"]),
                                format_func=lambda k: f"{k} — {data.materials[k].get('name', '')[:50]}")
        solids_g = cB.number_input("Dry solids per specimen (g)", 1.0, 5000.0, float(tproto.get("solids_g", 25.0)), 0.5)
        gypsum_pct = cC.number_input("Waste gypsum (% of solids)", 0.0, 50.0, 100 * float(tproto.get("gypsum_fraction", 0.0) or 0.0), 0.5)
        mat0 = data.materials[material]
        with st.expander("Material properties (override)"):
            m1, m2, m3 = st.columns(3)
            portlandite = m1.number_input("Portlandite content (wt%)", 0.0, 30.0, float(mat0.get("portlandite_wt", 0.0)), 0.1)
            mat_km = m2.number_input("Transport of the fines (km)", 0.0, 2000.0, float(mat0.get("transport_km", 70)), 5.0)
            density = m3.number_input("Product bulk density (kg/m³)", 300.0, 2500.0, float(mat0.get("product_bulk_density_kg_m3", 1100)), 10.0)
        custom_materials = {}
        if (portlandite, mat_km, density) != (float(mat0.get("portlandite_wt", 0.0)), float(mat0.get("transport_km", 70)), float(mat0.get("product_bulk_density_kg_m3", 1100))):
            mm = copy.deepcopy(mat0)
            mm.update({"portlandite_wt": portlandite, "transport_km": mat_km, "product_bulk_density_kg_m3": density})
            custom_materials[material] = mm

        st.markdown("#### Organism and cultivation")
        o1, o2 = st.columns([1, 2])
        strain_opts = list(data.strains) + ["(custom organism)"]
        strain_choice = o1.selectbox("Organism / catalyst", strain_opts, index=strain_opts.index(tproto["strain"]) if tproto["strain"] in strain_opts else 0,
                                     format_func=lambda k: k if k.startswith("(") else f"{k} — {data.strains[k].get('name', '')[:45]}")
        custom_strains: dict = {}
        custom_media: dict = {}
        if strain_choice == "(custom organism)":
            strain_id = "custom_organism"
            s0 = copy.deepcopy(data.strains[tproto["strain"]])
            sname = o2.text_input("Name of the organism / catalyst", s0.get("name", "Custom organism"))
            pathway = st.selectbox("Metabolic pathway", PATHWAYS, index=PATHWAYS.index(s0.get("pathway")) if s0.get("pathway") in PATHWAYS else 0,
                                   help="Determines how the carbonate is formed: urea hydrolysis (N by-products), oxidation of an organic calcium salt, "
                                        "fungal metabolism, free urease (no cultivation), nitrate reduction or photosynthesis (bicarbonate, light energy).")
            s0.update({"name": sname, "pathway": pathway})
            s0.pop("alternative_cultivation_media", None)
            cult0 = dict(s0.get("cultivation") or {"medium": "lb_25", "temperature_C": 30, "duration_h": 24, "harvest_od600": 2.5, "harvest": "centrifugation"})
        else:
            strain_id = strain_choice
            s0 = copy.deepcopy(data.strains[strain_id])
            pathway = s0.get("pathway")
            cult0 = dict(s0.get("cultivation") or {})
        no_cultivation = pathway == "eicp" or not cult0
        if not no_cultivation:
            k1, k2, k3, k4, k5 = st.columns(5)
            med_opts = MEDIA_IDS + ["(custom medium)"]
            cult_medium = k1.selectbox("Cultivation medium", med_opts, index=med_opts.index(cult0.get("medium")) if cult0.get("medium") in med_opts else 0, format_func=med_label)
            cult_T = k2.number_input("Cultivation T (°C)", 10.0, 45.0, float(cult0.get("temperature_C", 30)), 1.0)
            cult_h = k3.number_input("Cultivation time (h)", 4.0, 240.0, float(cult0.get("duration_h", 24)), 1.0)
            harvest_od = k4.number_input("Harvest OD600", 0.3, 20.0, float(cult0.get("harvest_od600") or 2.5), 0.1)
            harvest = k5.selectbox("Harvest", ["centrifugation", "none"], index=0 if cult0.get("harvest", "centrifugation") == "centrifugation" else 1)
            if cult_medium == "(custom medium)":
                st.markdown("Custom cultivation medium (g/L)")
                base_m = data.media.get(cult0.get("medium"), {"components": {}})
                comps = st.multiselect("Components", CHEM_IDS, default=[c for c in (base_m.get("components") or {}) if c in CHEM_IDS], format_func=chem_name, key="cult_comps")
                cols = st.columns(4)
                cm = {}
                for i, c in enumerate(comps):
                    cm[c] = cols[i % 4].number_input(f"{chem_name(c)} (g/L)", 0.0, 500.0, float((base_m.get("components") or {}).get(c, 1.0)), 0.1, key=f"cult_{c}")
                ster = st.selectbox("Sterilisation of the cultivation medium", ["autoclave", "filter", "none"], key="cult_ster")
                custom_media["custom_cultivation_medium"] = {"name": "Custom cultivation medium", "components": cm, "sterilisation": ster}
                cult_medium = "custom_cultivation_medium"
            cult_new = {**cult0, "medium": cult_medium, "temperature_C": cult_T, "duration_h": cult_h, "harvest_od600": harvest_od, "harvest": harvest}
            if cult_medium != cult0.get("medium"):
                cult_new.pop("supplements_medium", None)
            s0["cultivation"] = cult_new
            if pathway == "photosynthetic":
                s0["light_kWh_per_L_day"] = st.number_input("Light energy of the phototrophic culture (kWh per L and day)", 0.0, 1.0,
                                                            float(s0.get("light_kWh_per_L_day", 0.03) or 0.03), 0.005, format="%.3f")
        if strain_choice == "(custom organism)" or s0 != data.strains.get(strain_id):
            custom_strains[strain_id] = s0
        q1, q2 = st.columns(2)
        susp_mL = q1.number_input("Bacterial suspension per specimen (mL)", 0.0, 1000.0, float((tproto.get("suspension") or {}).get("volume_mL", 10.0)), 0.5)
        susp_od = q2.number_input("Suspension OD600", 0.1, 30.0, float((tproto.get("suspension") or {}).get("od600", 2.0) or 2.0), 0.1)

        st.markdown("#### Casting")
        r1, r2, r3, r4 = st.columns(4)
        saline_mL = r1.number_input("Extra saline (mL)", 0.0, 1000.0, float(tproto.get("saline_mL", 0.0) or 0.0), 0.5)
        hcl_M = r2.number_input("HCl molarity (M)", 0.0, 12.0, float((tproto.get("hcl") or {}).get("molarity", 0.0) or 0.0), 0.5)
        hcl_mL = r3.number_input("HCl volume (mL)", 0.0, 100.0, float((tproto.get("hcl") or {}).get("volume_mL", 0.0) or 0.0), 0.1)
        vib = r4.number_input("Vibration / mixing (s)", 0.0, 600.0, float((tproto.get("mixing") or {}).get("vibration_s", 45) or 45), 5.0)

        st.markdown("#### Biocementation solution and dosing")
        tbs = tproto.get("biocementation_solution") or {}
        b1, b2 = st.columns([1, 2])
        bs_opts = MEDIA_IDS + ["(custom medium)", "(water only)"]
        bs_medium = b1.selectbox("Nutrient base of the solution", bs_opts, index=bs_opts.index(tbs.get("base_medium")) if tbs.get("base_medium") in bs_opts else 0, format_func=med_label)
        if bs_medium == "(custom medium)":
            base_m = data.media.get(tbs.get("base_medium"), {"components": {}})
            comps = b2.multiselect("Components of the nutrient base", CHEM_IDS, default=[c for c in (base_m.get("components") or {}) if c in CHEM_IDS], format_func=chem_name, key="bs_comps")
            cols = st.columns(4)
            cm = {}
            for i, c in enumerate(comps):
                cm[c] = cols[i % 4].number_input(f"{chem_name(c)} (g/L)", 0.0, 500.0, float((base_m.get("components") or {}).get(c, 1.0)), 0.1, key=f"bs_{c}")
            ster = st.selectbox("Sterilisation of the biocementation solution", ["autoclave", "filter", "none"], key="bs_ster")
            custom_media["custom_bs_medium"] = {"name": "Custom nutrient base", "components": cm, "sterilisation": ster}
            bs_medium = "custom_bs_medium"
        elif bs_medium == "(water only)":
            custom_media["water_only"] = {"name": "Water only (no nutrient base)", "components": {}, "sterilisation": "none"}
            bs_medium = "water_only"
        default_supp = [c for c in (tbs.get("supplements") or {}) if c in CHEM_IDS]
        supp_sel = st.multiselect("Reagents (calcium source, urea, nitrate, bicarbonate …)", CHEM_IDS, default=default_supp, format_func=chem_name,
                                  help="Recognised reagents: calcium_chloride, calcium_lactate_pentahydrate, calcium_acetate(_bio), calcium_nitrate_tetrahydrate, "
                                       "sodium_nitrate, sodium_bicarbonate, urea. Other chemicals are counted as inputs without stoichiometric role.")
        cols = st.columns(4)
        supp = {}
        for i, c in enumerate(supp_sel):
            supp[c] = cols[i % 4].number_input(f"{chem_name(c)} (g/L)", 0.0, 1000.0, float((tbs.get("supplements") or {}).get(c, 10.0)), 0.1, key=f"supp_{c}")
        d1, d2, d3, d4 = st.columns(4)
        dose_mL = d1.number_input("Dose volume (mL per specimen)", 0.1, 5000.0, float(tbs.get("dose_mL", 5.0)), 0.5)
        tdos = tbs.get("dosing") or {}
        dmode = d2.selectbox("Dosing mode", ["single", "repeated", "fixed"], index=["single", "repeated", "fixed"].index(tdos.get("mode", "single")))
        if dmode == "repeated":
            interval = d3.number_input("Interval (h)", 1.0, 720.0, float(tdos.get("interval_h", 48)), 1.0)
            dur = d4.number_input("Dosing period (d)", 1.0, 365.0, float(tdos.get("duration_d", (tproto.get("incubation") or {}).get("duration_d", 30))), 1.0)
            dosing_new = {"mode": "repeated", "interval_h": interval, "duration_d": dur}
        elif dmode == "fixed":
            n = d3.number_input("Number of doses", 1, 500, int(tdos.get("n_doses", 5)))
            dosing_new = {"mode": "fixed", "n_doses": int(n)}
        else:
            dosing_new = {"mode": "single"}

        st.markdown("#### Curing, drying, specimen and expected performance")
        e1, e2, e3, e4 = st.columns(4)
        inc_T = e1.number_input("Curing temperature (°C)", 5.0, 60.0, float((tproto.get("incubation") or {}).get("temperature_C", 30)), 1.0)
        inc_d = e2.number_input("Curing period (d)", 0.5, 365.0, float((tproto.get("incubation") or {}).get("duration_d", 30)), 0.5)
        dry_T = e3.number_input("Drying temperature (°C)", 5.0, 105.0, float((tproto.get("drying") or {}).get("temperature_C", 30) or 30), 1.0)
        dry_d = e4.number_input("Drying period (d)", 0.0, 365.0, float((tproto.get("drying") or {}).get("duration_d", 0) or 0), 0.5)
        f1, f2, f3, f4 = st.columns(4)
        fc = f1.number_input("Expected compressive strength (MPa, 0 = unknown)", 0.0, 100.0, float((tproto.get("results") or {}).get("fc_MPa") or 0.0), 0.1)
        caco3_meas = f2.number_input("Measured CaCO₃ gain (wt% of solids, 0 = model)", 0.0, 60.0, float((tproto.get("results") or {}).get("caco3_gain_wt_abs") or 0.0), 0.1,
                                     help="Caps the stoichiometric CaCO₃ yield at the measured value (XRD/TGA).")
        p_eff = f3.number_input("Precipitation efficiency (–)", 0.05, 1.0, float(tproto.get("precipitation_efficiency", 1.0)), 0.05)
        aft = f4.number_input("Water bound in AFt (kg per kg solids, gypsum recipes)", 0.0, 0.2, float(tproto.get("aft_water_binding_fraction", 0.0) or 0.0), 0.005, format="%.3f")
        g1, g2, g3 = st.columns(3)
        shape = g1.selectbox("Specimen shape", ["cylinder", "cube", "prism"], index=0)
        diam = g2.number_input("Diameter / width (mm)", 5.0, 500.0, float((tproto.get("specimen") or {}).get("diameter_mm", 25) or 25), 1.0)
        height = g3.number_input("Height (mm)", 5.0, 500.0, float((tproto.get("specimen") or {}).get("height_mm", 50) or 50), 1.0)
        cname = st.text_input("Name of the composition", f"Custom composition based on {tproto.get('name', base)[:60]}")

        custom_protocol = {
            "name": cname, "source_id": "USER", "strain": strain_id, "material": material, "solids_g": solids_g, "gypsum_fraction": gypsum_pct / 100.0,
            "suspension": {"volume_mL": susp_mL, "od600": susp_od}, "saline_mL": saline_mL, "hcl": {"molarity": hcl_M, "volume_mL": hcl_mL},
            "biocementation_solution": {"base_medium": bs_medium, "supplements": supp, "dose_mL": dose_mL, "dosing": dosing_new},
            "incubation": {"temperature_C": inc_T, "duration_d": inc_d}, "drying": {"temperature_C": dry_T, "duration_d": dry_d},
            "mixing": {"vibration_s": vib}, "specimen": {"shape": shape, "diameter_mm": diam, "height_mm": height},
            "results": {"fc_MPa": fc or None, "caco3_gain_wt_abs": caco3_meas or None}, "precipitation_efficiency": p_eff,
            "aft_water_binding_fraction": aft,
        }
        if tproto.get("inoculum_agar_L") and pathway == "fungal":
            custom_protocol["inoculum_agar_L"] = tproto["inoculum_agar_L"]
        overrides.update({"custom_protocol": custom_protocol, "material": material, "cultivation_variant": None})
        if custom_media:
            overrides["custom_media"] = custom_media
        if custom_strains:
            overrides["custom_strains"] = custom_strains
        if custom_materials:
            overrides["custom_materials"] = custom_materials
        protocol = base_cfg["protocol"]
        proto = custom_protocol
        strain = s0

# ============================================================================================ 2 technology
with tab_tech:
    t1, t2, t3, t4 = st.columns(4)
    scale = t1.radio("Energy model", ["industrial", "lab"], index=0 if base_cfg.get("scale", "industrial") == "industrial" else 1, horizontal=True,
                     help="industrial = scale-up process model (curing chamber, sterilisation with heat recovery, fermenter); lab = laboratory equipment as used in the papers")
    elec_opts = [k for k, p in data.background.items() if p.unit == "kWh" and p.category == "energy" and "heat" not in k]
    electricity = t2.selectbox("Electricity", elec_opts, index=elec_opts.index(base_cfg.get("electricity", "electricity_CZ_lv")) if base_cfg.get("electricity") in elec_opts else 0,
                               format_func=lambda k: f"{k} ({data.background[k].gwp_any:.2f} kg CO₂e/kWh)")
    effluent = t3.selectbox("Effluent N treatment (ureolytic)", ["none", "ammonia_stripping", "struvite"],
                            index=["none", "ammonia_stripping", "struvite"].index(base_cfg.get("effluent_treatment", "none")))
    eol = t4.radio("End of life", ["landfill", "recycling"], index=0 if base_cfg.get("eol", "landfill") == "landfill" else 1, horizontal=True)
    u1, u2, u3, u4 = st.columns(4)
    module_d = u1.checkbox("Module D credits (recovered N)", value=bool(base_cfg.get("module_d", False)))
    carbon = u2.radio("Biogenic carbon", ["EF31", "EN15804A2"], index=0 if base_cfg.get("carbon_accounting", "EF31") == "EF31" else 1, horizontal=True)
    site_cf = u3.checkbox("Czech site-specific EF factors (AP, EP)", value=bool(base_cfg.get("site_specific_cf", False)))
    abiotic = u4.checkbox("Abiotic control (no organism)", value=bool(base_cfg.get("abiotic", False)))
    v1, v2, v3, v4 = st.columns(4)
    carbonation = v1.slider("Carbonation uptake fraction of portlandite", 0.0, 1.0, float(base_cfg.get("carbonation_uptake_fraction", 0.7)), 0.05)
    t_default = int(base_cfg.get("temperature_override_C") or (proto.get("incubation") or {}).get("temperature_C", 30))
    temp = v2.slider("Cultivation & curing temperature (°C)", 15, 40, min(max(t_default, 15), 40), help="Overrides the protocol temperatures for cultivation and curing.")
    km_chem = v3.number_input("Transport of chemicals (km)", 0.0, 3000.0, float(base_cfg.get("transport_chemicals_km", 200)), 10.0)
    km_gyp = v4.number_input("Transport of waste gypsum (km)", 0.0, 3000.0, float(base_cfg.get("transport_gypsum_km", 100)), 10.0)
    st.markdown("**Reagent optimisation**")
    w1, w2, w3, w4 = st.columns(4)
    ropt = dict(base_cfg.get("reagent_optimisation") or {})
    urea_ratio = w1.number_input("Urea : Ca molar ratio (0 = as in recipe)", 0.0, 20.0, float(ropt.get("urea_to_ca_molar_ratio") or 0.0), 0.1)
    recirc = w2.slider("Recirculated share of the biocementation solution", 0.0, 0.9, float(ropt.get("solution_recirculation_fraction") or 0.0), 0.05)
    nb_factor = w3.slider("Nutrient-base strength factor", 0.0, 3.0, float(ropt.get("nutrient_broth_factor") or 1.0), 0.1)
    harvest_over = w4.number_input("Harvest OD600 override (0 = organism default)", 0.0, 20.0, float(base_cfg.get("harvest_od600_override") or 0.0), 0.1)
    with st.expander("Advanced scale-up parameters (industrial energy model)"):
        P0 = data.scaleup["industrial"]
        a1, a2, a3, a4 = st.columns(4)
        params["industrial.curing_chamber.U_W_m2K"] = a1.slider("Chamber U-value (W/m²K)", 0.1, 1.5, float(P0["curing_chamber"]["U_W_m2K"]["value"]), 0.05)
        params["industrial.curing_chamber.ambient_C"] = a2.slider("Ambient temperature (°C)", 0.0, 25.0, float(P0["curing_chamber"]["ambient_C"]["value"]), 1.0)
        params["industrial.medium_sterilisation.heat_recovery"] = a3.slider("Sterilisation heat recovery", 0.0, 0.9, float(P0["medium_sterilisation"]["heat_recovery"]["value"]), 0.05)
        params["industrial.fermentation.power_kW_per_m3"] = a4.slider("Fermenter power (kW/m³)", 0.2, 5.0, float(P0["fermentation"]["power_kW_per_m3"]["value"]), 0.1)
        a5, a6, a7, a8 = st.columns(4)
        params["industrial.effluent.fraction_drained"] = a5.slider("Effluent drained fraction", 0.0, 1.0, float(P0["effluent"]["fraction_drained"]["value"]), 0.05)
        params["industrial.nitrogen_fate.n2o_fraction_of_N"] = a6.slider("N₂O share of N", 0.0, 0.02, float(P0["nitrogen_fate"]["n2o_fraction_of_N"]["value"]), 0.0005, format="%.4f")
        params["industrial.nitrogen_fate.nh3_volatilised_fraction_of_retained_N"] = a7.slider("NH₃ volatilised share of retained N", 0.0, 1.0, float(P0["nitrogen_fate"]["nh3_volatilised_fraction_of_retained_N"]["value"]), 0.05)
        params["industrial.drying.fan_kWh_per_t"] = a8.slider("Drying fan energy (kWh/t)", 0.0, 60.0, float(P0["drying"]["fan_kWh_per_t"]["value"]), 1.0)
    overrides.update({
        "scale": scale, "electricity": electricity, "effluent_treatment": effluent, "eol": eol, "module_d": module_d, "carbon_accounting": carbon,
        "site_specific_cf": site_cf, "carbonation_uptake_fraction": carbonation, "temperature_override_C": temp, "abiotic": abiotic,
        "transport_chemicals_km": km_chem, "transport_gypsum_km": km_gyp,
        "reagent_optimisation": {k: v for k, v in {"urea_to_ca_molar_ratio": urea_ratio or None, "solution_recirculation_fraction": recirc or None,
                                                   "nutrient_broth_factor": nb_factor if nb_factor != 1.0 else None}.items() if v is not None},
    })
    if harvest_over:
        overrides["harvest_od600_override"] = harvest_over

# only keep scale-up parameters that differ from the defaults
P_default = Params(data.scaleup, "industrial")
params = {k: v for k, v in params.items() if abs(float(v) - P_default.get(k)) > 1e-12}
st.session_state["builder"] = {"base": base, "fu": fu, "overrides": overrides, "params": params}

try:
    res = run(base, fu, overrides, params)
except Exception as exc:  # noqa: BLE001
    st.error(f"The scenario could not be evaluated: {exc}")
    st.stop()
m = res.meta
a13 = res.totals(("A1", "A2", "A3"))
c14 = res.totals(("C1", "C2", "C3", "C4"))


def _fmt(v):
    if isinstance(v, bool) or v is None:
        return "n/a" if v is None else str(v)
    if isinstance(v, (int, float)):
        return f"{v:.4g}"
    return str(v)


# ============================================================================================ 3 results
with tab_res:
    st.subheader(f"Results per {fu_label(fu)}")
    k1, k2, k3 = st.columns(3)
    k1.metric("GWP-total A1–A3", f"{a13['GWP-total']:.3g} kg CO₂e")
    k2.metric("GWP-total incl. C1–C4", f"{a13['GWP-total'] + c14['GWP-total']:.3g} kg CO₂e")
    k3.metric("Acidification (AP)", f"{a13['AP']:.3g} mol H⁺ eq")
    k4, k5, k6 = st.columns(3)
    k4.metric("Eutrophication, terrestrial", f"{a13['EP-terrestrial']:.3g} mol N eq")
    k5.metric("Water use (WDP)", f"{a13['WDP']:.3g} m³ eq")
    k6.metric("Precipitated CaCO₃ (of solids)", f"{100 * m['caco3_precipitated_kg_per_kg_solids']:.2f} wt%")
    if m.get("reaction_notes"):
        st.info(" ".join(m["reaction_notes"]))
    r_imp, r_contrib, r_bal, r_inv, r_cost = st.tabs(["Impact indicators", "Contributions", "Reagent & mass balance", "Inventory", "Cost (indicative)"])
    with r_imp:
        st.markdown("**EN 15804+A2 core indicators (EF 3.1)** — coverage = share of the background inventory with a native factor / including scaled proxy profiles")
        df = impacts_table(res, data, CORE)
        st.dataframe(df.style.format({"A1–A3": "{:.4g}", "C1–C4": "{:.4g}", "D": "{:.4g}", "A1–A3 + C": "{:.4g}", "coverage native": "{:.0%}", "coverage incl. proxies": "{:.0%}"}),
                     width="stretch", hide_index=True)
        st.markdown("**Additional indicators** (generic ÖKOBAUDAT datasets do not declare them; interpret with care)")
        df2 = impacts_table(res, data, ADDITIONAL)
        st.dataframe(df2.style.format({"A1–A3": "{:.3g}", "C1–C4": "{:.3g}", "D": "{:.3g}", "A1–A3 + C": "{:.3g}", "coverage native": "{:.0%}", "coverage incl. proxies": "{:.0%}"}),
                     width="stretch", hide_index=True)
        download_button(pd.concat([df, df2]), "Download indicators (CSV)", f"indicators_{base}.csv")
        with st.expander("Datasets with proxy-filled or missing factors, per category"):
            rows = [{"category": c, "proxy-filled": ", ".join(res.proxy_filled.get(c, [])), "missing": ", ".join(res.missing.get(c, []))} for c in CORE + ADDITIONAL]
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    with r_contrib:
        cat = st.selectbox("Impact category", CORE + ADDITIONAL, format_func=lambda c: category_label(c, data), key="contrib_cat")
        by = st.radio("Group by", ["group", "module"], horizontal=True)
        st.plotly_chart(contribution_figure(res, cat, data, by), width="stretch")
        g = res.by_group()[[cat]]
        g["share"] = g[cat] / g[cat].sum() if g[cat].sum() else float("nan")
        st.dataframe(g.style.format({cat: "{:.4g}", "share": "{:.1%}"}), width="stretch")
    with r_bal:
        left, right = st.columns(2)
        keys = ["material", "strain", "pathway", "scale", "solids_kg_per_specimen", "gypsum_fraction", "n_doses", "V_suspension_L", "V_culture_L",
                "V_biocementation_solution_L", "liquid_to_solid_L_per_kg", "T_cultivation_C", "T_incubation_C", "incubation_d", "drying_d"]
        left.markdown("**Process description**")
        left.table(pd.DataFrame({"value": [_fmt(m.get(k)) for k in keys]}, index=keys))
        keys2 = ["carbonate_source", "organic_substrate", "urea_kg_per_kg_solids", "ca_mol_per_kg_solids", "urea_to_ca_molar_ratio", "caco3_theoretical_kg_per_kg_solids",
                 "caco3_precipitated_kg_per_kg_solids", "precipitation_efficiency", "co2_fossil_direct_kg_per_kg_solids", "co2_biogenic_direct_kg_per_kg_solids",
                 "c_stored_fossil_as_co2_kg_per_kg_solids", "c_stored_biogenic_as_co2_kg_per_kg_solids", "carbonation_uptake_kg_per_kg_solids",
                 "n_hydrolysed_kg_per_kg_solids", "product_kg_per_kg_solids", "effluent_L_per_kg_solids", "fc_MPa", "k_N_mm"]
        right.markdown("**Reagent, carbon and nitrogen balance (per kg of dry solids)**")
        right.table(pd.DataFrame({"value": [_fmt(m.get(k)) for k in keys2]}, index=keys2))
        if m.get("nitrogen_fate_kg_per_kg_solids") and sum(m["nitrogen_fate_kg_per_kg_solids"].values()) > 0:
            st.markdown("**Nitrogen fate (kg per kg solids)**")
            st.table(pd.DataFrame({"value": {k: _fmt(v) for k, v in m["nitrogen_fate_kg_per_kg_solids"].items()}}).T)
    with r_inv:
        inv = res.contrib.copy()
        st.dataframe(inv, width="stretch", hide_index=True, height=420)
        download_button(inv, "Download inventory + characterised flows (CSV)", f"inventory_{base}.csv")
    with r_cost:
        cost_block(res, data)

# ============================================================================================ 4 parametric analysis
with tab_sweep:
    st.markdown("Vary **one parameter** of the current composition/technology between limits; all other inputs stay as configured. "
                "The response of the indicators, the cost and the yields is plotted and can be included in the PDF report.")
    plist = available_parameters(base, data, overrides, params)
    groups = ["recipe", "cultivation", "system", "scale-up"]
    s1, s2 = st.columns([1, 2])
    grp = s1.selectbox("Parameter group", groups, index=0)
    cand = [p for p in plist if p.group == grp]
    sp = None
    if not cand:
        st.info("No parameters in this group for the current configuration.")
    else:
        labels = {p.key: f"{p.label} [{p.unit}] — current {p.value:.4g}" for p in cand}
        keys_ = [p.key for p in cand]
        default_key = "protocol:biocementation_solution.dose_mL" if "protocol:biocementation_solution.dose_mL" in keys_ else keys_[0]
        pkey = s2.selectbox("Parameter", keys_, index=keys_.index(default_key), format_func=lambda k: labels[k])
        sp = find_parameter(cand, pkey)
    if sp is not None:
        l1, l2, l3, l4 = st.columns(4)
        lo = l1.number_input("Lower limit", value=float(sp.lo), format="%.4g", key=f"lo_{sp.key}")
        hi = l2.number_input("Upper limit", value=float(sp.hi), format="%.4g", key=f"hi_{sp.key}")
        steps = l3.slider("Steps", 3, 41, 11)
        mods_choice = l4.selectbox("Modules", ["A1–A3", "A1–A3 + C1–C4"], key="sweep_mods")
        cats_sel = st.multiselect("Indicators to plot", CORE + ADDITIONAL, default=["GWP-total", "AP", "EP-terrestrial", "WDP"], format_func=lambda c: category_label(c, data))
        rel = st.checkbox("Show indicators relative to the current configuration", value=False)
        if hi <= lo:
            st.error("The upper limit must exceed the lower limit.")
        else:
            values = sp.values(steps, lo, hi)

            @st.cache_data(show_spinner="Running the parametric analysis …", max_entries=64)
            def _sweep(base: str, key: str, values: tuple, fu: str, overrides_json: str, params_json: str, modules: tuple) -> pd.DataFrame:
                return sweep(base, get_data(), key, list(values), overrides=json.loads(overrides_json), param_overrides=json.loads(params_json),
                             functional_unit=fu, modules=modules)

            modules = ("A1", "A2", "A3") if mods_choice == "A1–A3" else ("A1", "A2", "A3", "C1", "C2", "C3", "C4")
            sw = _sweep(base, sp.key, tuple(values), fu, json.dumps(overrides, sort_keys=True, default=str), json.dumps(params, sort_keys=True), modules)
            ok = sw[sw["error"] == ""]
            if ok.empty:
                st.error("No evaluable point: " + "; ".join(sw["error"].unique()[:3]))
            else:
                panels = [c for c in cats_sel if c in ok] + [c for c in ("cost_bulk_EUR", "caco3_kg_per_kg_solids") if c in ok]
                titles = {"cost_bulk_EUR": "cost, bulk grade [EUR]", "caco3_kg_per_kg_solids": "CaCO₃ [kg/kg solids]"}
                ncols = 3
                nrows = -(-len(panels) // ncols)
                fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=[titles.get(c, category_label(c, data)) for c in panels], vertical_spacing=0.18, horizontal_spacing=0.08)
                base_tot = res.totals(modules)
                for i, c in enumerate(panels):
                    r_, c_ = i // ncols + 1, i % ncols + 1
                    y = ok[c]
                    if rel and c in base_tot and float(base_tot[c]):
                        y = y / float(base_tot[c])
                    fig.add_trace(go.Scatter(x=ok["value"], y=y, mode="lines+markers", name=c, marker=dict(size=6), line=dict(color=PALETTE[i % len(PALETTE)])), row=r_, col=c_)
                    fig.add_vline(x=sp.value, line_dash="dash", line_color="#e45756", row=r_, col=c_)
                    fig.update_xaxes(title_text=f"{sp.label} [{sp.unit}]", row=r_, col=c_)
                fig.update_layout(height=300 * nrows + 60, showlegend=False, margin=dict(l=10, r=10, t=60, b=10),
                                  title=f"Response per {fu_label(fu)} ({mods_choice}); dashed line = current value")
                st.plotly_chart(fig, width="stretch")
                d = describe_sweep(ok, "GWP-total")
                if d:
                    st.markdown(f"**GWP-total** {d['monotonic']} from {d['y_at_min_x']:.4g} to {d['y_at_max_x']:.4g} kg CO₂e (span {100 * d['relative_span']:.0f} %); "
                                f"minimum {d['y_min']:.4g} at {d['x_of_y_min']:.4g} {sp.unit}; linear fit R² = {d['r2_linear']:.2f}.")
                show_cols = [c for c in ["value"] + cats_sel + ["cost_bulk_EUR", "cost_lab_EUR", "caco3_kg_per_kg_solids", "product_kg_per_kg_solids", "liquid_to_solid_L_per_kg", "n_doses", "urea_to_ca_molar_ratio"] if c in ok]
                st.dataframe(ok[show_cols].rename(columns={"value": f"{sp.label} [{sp.unit}]"}).style.format("{:.4g}", na_rep="n/a"), width="stretch", hide_index=True)
                download_button(sw, "Download sweep (CSV)", f"sweep_{base}_{sp.key.replace(':', '_').replace('.', '_')}.csv")
                st.session_state["sweep"] = {"df": sw, "parameter": sp}

# ============================================================================================ 5 report
with tab_report:
    st.markdown("Generate a **PDF report** of the current configuration: summary, goal and scope, system description, inventory, impact assessment "
                "with contribution and module analyses, comparison with benchmarks, parametric analysis (from tab 4), one-at-a-time sensitivity, "
                "optional Monte Carlo, indicative cost, data quality, interpretation and numbered references.")
    p1, p2, p3 = st.columns(3)
    rtitle = p1.text_input("Title", f"Life-cycle assessment of {base}" if mode.startswith("Pre") else f"Life-cycle assessment of {proto.get('name', base)[:60]}")
    author = p2.text_input("Author(s)", "")
    org = p3.text_input("Organisation", "")
    q1, q2, q3, q4 = st.columns(4)
    include_oat = q1.checkbox("One-at-a-time sensitivity (tornado)", value=True)
    n_mc = q2.select_slider("Monte Carlo samples", [0, 100, 250, 500, 1000], value=0)
    include_sweep = q3.checkbox("Include the parametric analysis of tab 4", value=True)
    ref_b = q4.selectbox("Reference product", [b for b in data.scenarios["benchmarks"] if b != "landfill_WCF_status_quo"], index=0)
    comp = st.multiselect("Other scenarios to show in the comparison", [s for s in scen_names if s != base],
                          default=[s for s in ("GYP_WCFC_single_dose", "BC_lactate_30d", "SP_optimised_recirculation") if s in scen_names and s != base])
    notes = st.text_area("Notes to include (optional)", "")
    if st.button("Generate PDF report", type="primary"):
        from micp_lca.pdfreport import ReportOptions, build_report
        from micp_lca.uncertainty import MCSettings, monte_carlo
        opt = ReportOptions(title=rtitle, author=author, organisation=org, functional_unit=fu, include_oat=include_oat, comparison_scenarios=comp,
                            reference_benchmark=ref_b, notes=notes)
        swp = st.session_state.get("sweep") if include_sweep else None
        if swp is not None:
            opt.sweep, opt.sweep_parameter = swp["df"], swp["parameter"]
        with st.spinner("Building the report (figures, sensitivity, layout) …"):
            if n_mc:
                bar = st.progress(0, text="Monte Carlo …")
                opt.mc = monte_carlo(base, data, MCSettings(n=int(n_mc)), functional_unit=fu, overrides=overrides,
                                     progress=lambda i: bar.progress(min(1.0, i / n_mc), text=f"Monte Carlo {i}/{n_mc}"))
            out_dir = Path(data.root).parent / "results"
            out_dir.mkdir(exist_ok=True)
            safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (base if mode.startswith("Pre") else "custom_" + base))
            out = build_report(base, data, out_dir / f"report_{safe}.pdf", overrides=overrides, param_overrides=params, options=opt)
        st.success(f"Report written to {out}")
        st.download_button("Download the PDF", out.read_bytes(), file_name=out.name, mime="application/pdf")

# ============================================================================================ 6 save
with tab_save:
    st.markdown("Save the current configuration to `data/user/` so that it is available on every page and to the CLI.")
    s1, s2 = st.columns(2)
    new_name = s1.text_input("Scenario id", value=f"USER_{protocol}" if mode.startswith("Pre") else "USER_custom_composition")
    desc = s2.text_input("Description", value=f"User scenario based on {base}" if mode.startswith("Pre") else proto.get("name", "custom composition"))
    how = st.radio("How to store a custom composition", ["as a scenario with inline definitions", "as protocol + media + organism entries in the database"],
                   horizontal=True, disabled=mode.startswith("Pre"))
    if st.button("Save", type="primary"):
        user_dir = data.root / "user"
        user_dir.mkdir(exist_ok=True)
        fn = user_dir / "scenarios.yaml"
        existing = (yaml.safe_load(fn.read_text(encoding="utf-8")) if fn.exists() else {}) or {}
        existing.setdefault("scenarios", {})
        cfg = {k: v for k, v in overrides.items() if v not in (None, {}, "")}
        if cfg.get("temperature_override_C") == (proto.get("incubation") or {}).get("temperature_C"):
            cfg.pop("temperature_override_C", None)
        cfg["description"] = desc
        cfg["functional_unit"] = fu
        if params:
            cfg["scaleup_overrides"] = params

        def _merge_user(name: str, entries: dict) -> None:
            f = user_dir / f"{name}.yaml"
            obj = (yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {}) or {}
            obj.update(json.loads(json.dumps(entries)))
            f.write_text(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")

        if not mode.startswith("Pre") and how.startswith("as protocol"):
            pid = new_name.lower()
            _merge_user("protocols", {pid: cfg.pop("custom_protocol")})
            if cfg.get("custom_media"):
                _merge_user("media", cfg.pop("custom_media"))
            if cfg.get("custom_strains"):
                _merge_user("strains", cfg.pop("custom_strains"))
            if cfg.get("custom_materials"):
                _merge_user("materials", {f"{k}_user": v for k, v in cfg.pop("custom_materials").items()})
                cfg["material"] = f"{cfg['material']}_user"
            cfg["protocol"] = pid
        else:
            cfg["protocol"] = base_cfg["protocol"]
        existing["scenarios"][new_name] = json.loads(json.dumps(cfg))
        fn.write_text(yaml.safe_dump(existing, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
        reload_data()
        st.success(f"Saved as {new_name} in {fn}")
    with st.expander("Current configuration (YAML)"):
        st.code(yaml.safe_dump({base: json.loads(json.dumps({k: v for k, v in overrides.items() if v not in (None, {}, "")}))}, sort_keys=False, allow_unicode=True, width=120),
                language="yaml")
