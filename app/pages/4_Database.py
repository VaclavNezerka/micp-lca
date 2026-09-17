"""Database browser: background datasets, characterisation factors, foreground tables, experimental data, prices, sources."""
from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st
import yaml

from utils import ADDITIONAL, CORE, PALETTE, download_button, get_data

st.set_page_config(page_title="Database", page_icon="🗄️", layout="wide")
data = get_data()
st.title("Database browser")

tabs = st.tabs(["Background datasets", "Characterisation factors (EF 3.1)", "Chemicals", "Media", "Organisms", "Waste materials",
                "Protocols", "Scenarios & benchmarks", "Experimental results", "Prices", "Sources"])


# ------------------------------------------------------------------------------------------ helpers
def _yaml(obj) -> str:
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=120)


def _src(sid: str) -> str:
    s = data.sources.get(sid)
    return f"**{sid}** — {s['citation']} ({s.get('doi_or_url', '')})" if s else f"**{sid}** (not in sources table)"


# ------------------------------------------------------------------------------------------ background datasets
with tabs[0]:
    rows = []
    for pid, p in data.background.items():
        rows.append({"process_id": pid, "name": p.name, "unit": p.unit, "category": p.category, "geography": p.geography,
                     "year": p.reference_year, "data_type": p.data_type, "source": p.source_id, "modules": ",".join(p.modules),
                     "GWP-total": p.gwp_any, "GWP min": p.gwp_min, "GWP max": p.gwp_max,
                     "n categories": len({c for m in p.impacts.values() for c in m}), "proxy-filled": len(p.proxy_filled),
                     "ecoinvent proxy": p.ecoinvent_proxy, "pedigree": ",".join(map(str, p.pedigree))})
    bg = pd.DataFrame(rows)
    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
    q = f1.text_input("Search (id, name, notes, ecoinvent proxy)", "")
    typ = f2.multiselect("Data type", sorted(bg["data_type"].unique()), default=[])
    catf = f3.multiselect("Category", sorted(bg["category"].unique()), default=[])
    unitf = f4.multiselect("Unit", sorted(bg["unit"].unique()), default=[])
    sel = bg
    if q:
        ql = q.lower()
        notes = {pid: (p.notes or "").lower() for pid, p in data.background.items()}
        mask = sel.apply(lambda r: ql in r["process_id"].lower() or ql in str(r["name"]).lower() or ql in str(r["ecoinvent proxy"]).lower() or ql in notes[r["process_id"]], axis=1)
        sel = sel[mask]
    if typ:
        sel = sel[sel["data_type"].isin(typ)]
    if catf:
        sel = sel[sel["category"].isin(catf)]
    if unitf:
        sel = sel[sel["unit"].isin(unitf)]
    st.caption(f"{len(sel)} of {len(bg)} datasets · sources: ÖKOBAUDAT 2024-II (EN 15804+A2, EF 3.1), AGRIBALYSE 4 (proxies), literature and documented estimates; "
               "ecoinvent activity names are stored for licensed users.")
    st.dataframe(sel.style.format({"GWP-total": "{:.4g}", "GWP min": "{:.4g}", "GWP max": "{:.4g}"}), width="stretch", hide_index=True, height=420)
    download_button(sel, "Download list (CSV)", "background_datasets.csv")

    st.subheader("Impact profile matrix")
    show_cats = st.multiselect("Indicators", CORE + ADDITIONAL, default=["GWP-total", "GWP-fossil", "GWP-biogenic", "AP", "EP-freshwater", "EP-marine", "EP-terrestrial", "POCP", "ADP-fossil", "WDP"])
    mat = []
    for pid in sel["process_id"]:
        p = data.background[pid]
        mat.append({"process_id": pid, "unit": p.unit, **{c: p.factor(c) for c in show_cats}})
    mdf = pd.DataFrame(mat).set_index("process_id")
    st.dataframe(mdf.style.format({c: "{:.3g}" for c in show_cats}), width="stretch", height=380)
    download_button(mdf.reset_index(), "Download matrix (CSV)", "background_impact_matrix.csv")

    st.subheader("Dataset details")
    pid = st.selectbox("Dataset", list(sel["process_id"]) if len(sel) else list(bg["process_id"]))
    p = data.background[pid]
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown(f"**{p.name}**  \nunit: `{p.unit}` · category: `{p.category}` · geography: `{p.geography}` · year: `{p.reference_year}` · type: `{p.data_type}`")
        st.markdown(_src(p.source_id))
        if p.ecoinvent_proxy:
            st.markdown(f"ecoinvent proxy activity: `{p.ecoinvent_proxy}`")
        if p.other_categories_from:
            st.markdown(f"Non-GWP categories scaled from `{p.other_categories_from}` (approximation; {len(p.proxy_filled)} categories).")
        st.markdown(f"Pedigree (R, C, T, G, F): `{p.pedigree}` · basic uncertainty: `{p.basic_uncertainty}` · GWP range: `{p.gwp_min}` – `{p.gwp_max}`")
        if p.notes:
            st.info(p.notes)
    with c2:
        imp = pd.DataFrame(p.impacts).reindex(data.category_codes)
        imp.insert(0, "unit", [data.category_unit(c) for c in imp.index])
        st.dataframe(imp.style.format({c: "{:.4g}" for c in imp.columns if c != "unit"}), width="stretch", height=560)

# ------------------------------------------------------------------------------------------ CFs
with tabs[1]:
    st.markdown("Official **EF 3.1** characterisation factors (European Commission JRC, EF reference package 3.1). "
                "The curated subset covers the elementary flows of the foreground model; the full table (≈140 000 rows, GLO + CZ) is searchable below.")
    ic = data.impact_categories.copy()
    st.dataframe(ic, width="stretch", hide_index=True)
    st.subheader("Curated subset (foreground flows)")
    cf = data.characterization_factors
    c1, c2, c3 = st.columns(3)
    flow_q = c1.text_input("Flow name contains", "")
    comp = c2.multiselect("Compartment", sorted(cf["compartment"].unique()), default=[])
    catc = c3.multiselect("Category", sorted(cf["category_code"].unique()), default=[])
    sel = cf
    if flow_q:
        sel = sel[sel["flow_name"].str.contains(flow_q, case=False, na=False)]
    if comp:
        sel = sel[sel["compartment"].isin(comp)]
    if catc:
        sel = sel[sel["category_code"].isin(catc)]
    st.dataframe(sel, width="stretch", hide_index=True, height=360)
    download_button(sel, "Download subset (CSV)", "ef31_cf_subset.csv")
    st.subheader("Full EF 3.1 table search")
    fq = st.text_input("Search the full table by flow name (e.g. 'nitrous oxide', 'chloride', 'lactic acid')", "")
    if fq:
        full = data.cf_full()
        if full.empty:
            st.warning("Full table not found (data/lcia/ef31_characterization_factors_full.csv.gz).")
        else:
            hits = full[full["flow_name_lc"].str.contains(fq.lower(), na=False)].drop(columns=["flow_name_lc"])
            st.caption(f"{len(hits)} rows")
            st.dataframe(hits.head(2000), width="stretch", hide_index=True, height=400)
            download_button(hits, "Download hits (CSV)", "ef31_cf_search.csv")

# ------------------------------------------------------------------------------------------ chemicals
with tabs[2]:
    rows = []
    for cid, c in data.chemicals.items():
        if cid.startswith("_"):
            continue
        bp = c.get("background_process")
        proc = data.background.get(bp) if bp else None
        rows.append({"id": cid, "name": c.get("name"), "formula": c.get("formula"), "molar_mass": c.get("molar_mass"),
                     "C content": c.get("carbon_content"), "C origin": c.get("carbon_origin"), "N content": c.get("nitrogen_content"),
                     "background_process": bp, "GWP of background [kg CO2e/kg]": proc.gwp_any if proc else None,
                     "background type": proc.data_type if proc else None, "notes": c.get("notes")})
    cdf = pd.DataFrame(rows)
    q = st.text_input("Search chemicals", "", key="chem_q")
    if q:
        cdf = cdf[cdf.apply(lambda r: q.lower() in str(r["id"]).lower() or q.lower() in str(r["name"]).lower(), axis=1)]
    st.dataframe(cdf.style.format({"molar_mass": "{:.2f}", "GWP of background [kg CO2e/kg]": "{:.3g}"}), width="stretch", hide_index=True, height=520)
    download_button(cdf, "Download (CSV)", "chemicals.csv")

# ------------------------------------------------------------------------------------------ media
with tabs[3]:
    rows = []
    for mid, m in data.media.items():
        comps = m.get("components") or {}
        rows.append({"id": mid, "name": m.get("name"), "components": ", ".join(f"{k} {v} g/L" for k, v in comps.items()),
                     "total g/L": sum(float(v) for v in comps.values()), "sterilisation": m.get("sterilisation"), "source": m.get("source_id")})
    mdf = pd.DataFrame(rows)
    st.dataframe(mdf.style.format({"total g/L": "{:.1f}"}), width="stretch", hide_index=True, height=480)
    st.subheader("Cradle-to-gate GWP of 1 L of medium (components only)")
    med_rows = []
    for mid, m in data.media.items():
        g = 0.0
        missing = []
        for cid, gl in (m.get("components") or {}).items():
            chem = data.chemicals.get(cid, {})
            proc = data.background.get(chem.get("background_process", ""))
            if proc is None or proc.gwp_any != proc.gwp_any:
                missing.append(cid)
                continue
            g += float(gl) / 1000.0 * proc.gwp_any
        med_rows.append({"medium": mid, "kg CO2e per L": g, "unresolved components": ", ".join(missing)})
    gdf = pd.DataFrame(med_rows).sort_values("kg CO2e per L", ascending=False)
    fig = px.bar(gdf, x="kg CO2e per L", y="medium", orientation="h", color_discrete_sequence=PALETTE)
    fig.update_layout(height=max(360, 22 * len(gdf) + 80), yaxis_title="", margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, width="stretch")
    st.dataframe(gdf.style.format({"kg CO2e per L": "{:.4g}"}), width="stretch", hide_index=True)

# ------------------------------------------------------------------------------------------ strains
with tabs[4]:
    sid = st.selectbox("Organism / catalyst", list(data.strains), format_func=lambda k: f"{k} — {data.strains[k].get('name', '')}")
    s = data.strains[sid]
    st.markdown(f"**{s.get('name')}** · pathway: `{s.get('pathway')}` · source: {_src(s.get('source_id', ''))}")
    st.code(_yaml(s), language="yaml")

# ------------------------------------------------------------------------------------------ materials
with tabs[5]:
    rows = []
    for mid, m in data.materials.items():
        ox = m.get("oxides_wt") or {}
        rows.append({"id": mid, "name": m.get("name"), "CaO wt%": ox.get("CaO"), "SiO2 wt%": ox.get("SiO2"), "portlandite wt%": m.get("portlandite_wt"),
                     "CaCO3 wt%": m.get("caco3_wt"), "gypsum wt%": m.get("gypsum_wt"), "mean particle µm": m.get("mean_particle_um"),
                     "processing kWh/t": sum(float(s.get("electricity_kWh_per_t", 0)) for s in (m.get("processing") or [])),
                     "transport km": m.get("transport_km"), "bulk density kg/m3": m.get("product_bulk_density_kg_m3"), "source": m.get("source_id")})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    mid = st.selectbox("Details", list(data.materials))
    st.code(_yaml(data.materials[mid]), language="yaml")

# ------------------------------------------------------------------------------------------ protocols
with tabs[6]:
    rows = []
    for pid, p in data.protocols.items():
        bs = p.get("biocementation_solution") or {}
        dosing = bs.get("dosing") or {}
        rows.append({"id": pid, "name": p.get("name"), "strain": p.get("strain"), "material": p.get("material"),
                     "specimen g": (p.get("specimen") or {}).get("solids_g"), "dose mL": bs.get("dose_mL"), "dosing": dosing.get("mode"),
                     "interval h": dosing.get("interval_h"), "duration d": (p.get("incubation") or {}).get("duration_d"),
                     "T °C": (p.get("incubation") or {}).get("temperature_C"), "gypsum": (p.get("casting") or {}).get("gypsum_wt_pct"),
                     "source": p.get("source_id")})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=480)
    pid = st.selectbox("Protocol details", list(data.protocols))
    st.code(_yaml(data.protocols[pid]), language="yaml")

# ------------------------------------------------------------------------------------------ scenarios
with tabs[7]:
    st.markdown("**Defaults**")
    st.code(_yaml(data.scenarios.get("defaults", {})), language="yaml")
    rows = []
    for sid, s in data.scenarios["scenarios"].items():
        rows.append({"id": sid, "protocol": s.get("protocol"), "scale": s.get("scale", "industrial"), "electricity": s.get("electricity"),
                     "effluent": s.get("effluent_treatment"), "eol": s.get("eol"), "cultivation variant": s.get("cultivation_variant"),
                     "abiotic": s.get("abiotic", False), "description": s.get("description")})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=420)
    st.markdown("**Benchmarks**")
    rows = []
    for bid, b in data.scenarios["benchmarks"].items():
        rows.append({"id": bid, "name": b.get("name"), "background_process": b.get("background_process"), "fc MPa": b.get("fc_MPa"),
                     "bulk density kg/m3": b.get("bulk_density_kg_m3"), "source": b.get("source_id"), "notes": b.get("notes")})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

# ------------------------------------------------------------------------------------------ experimental
with tabs[8]:
    ex = data.experimental
    c1, c2, c3 = st.columns(3)
    props = c1.multiselect("Property", sorted(ex["property"].unique()), default=[])
    orgs = c2.multiselect("Organism", sorted(ex["organism"].dropna().unique()), default=[])
    srcs = c3.multiselect("Source", sorted(ex["source_id"].unique()), default=[])
    sel = ex
    if props:
        sel = sel[sel["property"].isin(props)]
    if orgs:
        sel = sel[sel["organism"].isin(orgs)]
    if srcs:
        sel = sel[sel["source_id"].isin(srcs)]
    st.dataframe(sel, width="stretch", hide_index=True, height=420)
    download_button(sel, "Download (CSV)", "experimental_results.csv")
    prop = st.selectbox("Plot property", sorted(ex["property"].unique()), index=sorted(ex["property"].unique()).index("CaCO3_content") if "CaCO3_content" in set(ex["property"]) else 0)
    pdf = ex[ex["property"] == prop].copy()
    pdf["label"] = pdf["sample_code"].astype(str) + " (" + pdf["source_id"] + ")"
    fig = px.bar(pdf, x="label", y="value", error_y="sd", color="organism", hover_data=["material", "medium", "treatment", "duration_d"],
                 color_discrete_sequence=PALETTE, labels={"value": f"{prop} [{pdf['unit'].iloc[0] if len(pdf) else ''}]"})
    fig.update_layout(height=420, xaxis_title="", margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------------------------------------ prices
with tabs[9]:
    pr = data.prices.copy()
    if pr.empty:
        st.info("No price table.")
    else:
        pr["name"] = [data.background[p].name if p in data.background else "" for p in pr["process_id"]]
        st.dataframe(pr, width="stretch", hide_index=True, height=520)
        download_button(pr, "Download (CSV)", "prices.csv")
        st.caption("Indicative EUR prices (bulk/technical vs laboratory grade). Edit data/economics/prices.csv to use supplier quotations.")

# ------------------------------------------------------------------------------------------ sources
with tabs[10]:
    sdf = pd.DataFrame(list(data.sources.values()))
    q = st.text_input("Search sources", "", key="src_q")
    if q:
        sdf = sdf[sdf.apply(lambda r: q.lower() in " ".join(map(str, r.values)).lower(), axis=1)]
    st.dataframe(sdf, width="stretch", hide_index=True, height=560)
    download_button(sdf, "Download (CSV)", "sources.csv")
