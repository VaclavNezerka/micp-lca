"""Published MICP LCA results side by side with the model (per kg of precipitated CaCO3)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import PALETTE, download_button, get_data, run

st.set_page_config(page_title="Literature", page_icon="📚", layout="wide")
data = get_data()
st.title("Literature LCA results and model cross-check")

lit = data.literature_results.copy()
if lit.empty:
    st.warning("No literature table found (data/literature/micp_lca_literature_results.csv).")
    st.stop()

st.subheader("Published results")
c1, c2, c3 = st.columns(3)
srcs = c1.multiselect("Source", sorted(lit["source_id"].unique()), default=[])
inds = c2.multiselect("Indicator", sorted(lit["indicator"].dropna().unique()), default=[])
paths = c3.multiselect("Pathway / variant", sorted(lit["pathway_or_variant"].dropna().unique()), default=[])
sel = lit
if srcs:
    sel = sel[sel["source_id"].isin(srcs)]
if inds:
    sel = sel[sel["indicator"].isin(inds)]
if paths:
    sel = sel[sel["pathway_or_variant"].isin(paths)]
st.dataframe(sel, width="stretch", hide_index=True, height=420)
download_button(sel, "Download (CSV)", "literature_results.csv")
with st.expander("References"):
    for sid in sorted(sel["source_id"].unique()):
        s = data.sources.get(sid)
        if s:
            st.markdown(f"* **{sid}** — {s['citation']}  \n  {s.get('doi_or_url', '')}")

# ------------------------------------------------------------------------------------------ per kg CaCO3 cross-check
st.subheader("Cross-check per kg of precipitated CaCO₃ (GWP, cradle-to-gate)")
st.markdown(
    "Published MICP LCAs use **1 kg of precipitated CaCO₃** as functional unit and mostly cover materials only "
    "(Porter et al. 2021) or materials + fermenter energy (Deng et al. 2021). The model can be evaluated with the same functional unit "
    "(`kg_caco3_precipitated`). Differences are expected: the block scenarios include nutrient media, casting, curing and drying "
    "energy, transport and direct process emissions, and the amount of CaCO₃ per kg of solids differs between protocols."
)
g = lit[(lit["indicator"] == "GWP") & (lit["functional_unit"].isin(["1 kg CaCO3", "1 t CaCO3"]))].copy()
g["kg CO2e per kg CaCO3"] = [v / 1000.0 if fu == "1 t CaCO3" else v for v, fu in zip(g["value"], g["functional_unit"])]
g["item"] = g["source_id"] + ": " + g["system"].str.slice(0, 70)
g["type"] = "literature"
g["pathway"] = g["pathway_or_variant"]

scen_all = list(data.scenarios["scenarios"])
default = [s for s in ("SP_lab_protocol_90d", "SP_optimised_stoichiometric", "SP_optimised_recirculation", "BC_lactate_30d",
                       "LIT_SP_NH4YE_medium", "LIT_SP_corn_steep_liquor", "LIT_EICP", "LIT_denitrification", "LIT_acetate_oxidation",
                       "LIT_photosynthetic") if s in scen_all]
chosen = st.multiselect("Model scenarios to evaluate per kg CaCO₃", scen_all, default=default)
st.caption("Not meaningful for the gypsum-promoted (GYP_*) and abiotic scenarios, whose strength comes from ettringite/hydration rather than "
           "from precipitated CaCO₃ (≈0.07 wt% CaCO₃ from a single nutrient dose).")
materials_only = st.checkbox("Model: reagents and media only (exclude energy, transport, direct emissions, carbonation) to mimic Porter et al. 2021", value=False)
rows = []
for s in chosen:
    try:
        r = run(s, "kg_caco3_precipitated")
        if materials_only:
            df = r.contrib
            keep = df["group"].str.contains("nutrient medium|calcium source|urea|Cultivation: media|Casting|Waste fines", case=False, regex=True) & df["module"].isin(["A1"])
            val = float(df[keep]["GWP-total"].sum())
        else:
            val = float(r.totals(("A1", "A2", "A3"))["GWP-total"])
        rows.append({"item": f"model: {s}", "kg CO2e per kg CaCO3": val, "type": "model", "pathway": r.meta.get("pathway", ""),
                     "CaCO3 per kg solids": r.meta.get("caco3_precipitated_kg_per_kg_solids")})
    except Exception as exc:  # noqa: BLE001
        st.warning(f"{s}: {exc}")
comb = pd.concat([g[["item", "kg CO2e per kg CaCO3", "type", "pathway"]], pd.DataFrame(rows)], ignore_index=True) if rows else g[["item", "kg CO2e per kg CaCO3", "type", "pathway"]]
comb = comb.sort_values("kg CO2e per kg CaCO3")
log = st.checkbox("Logarithmic axis", value=True)
fig = px.bar(comb, x="kg CO2e per kg CaCO3", y="item", color="type", orientation="h", hover_data=["pathway"],
             color_discrete_map={"literature": "#9e9e9e", "model": "#4c78a8"}, log_x=log)
fig.update_layout(height=max(420, 24 * len(comb) + 120), yaxis_title="", margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=-0.08))
st.plotly_chart(fig, width="stretch")
st.dataframe(comb.style.format({"kg CO2e per kg CaCO3": "{:.3g}", "CaCO3 per kg solids": "{:.3g}"}), width="stretch", hide_index=True)
download_button(comb, "Download cross-check (CSV)", "literature_crosscheck_per_kg_caco3.csv")

# ------------------------------------------------------------------------------------------ reagent benchmarks
st.subheader("Reagent benchmarks per kg of CaCO₃ (stoichiometry)")
st.markdown("Ureolytic MICP needs stoichiometrically 0.60 kg urea and 1.11 kg CaCl₂ per kg CaCO₃ (van Paassen et al. 2010); the laboratory "
            "protocols of the papers use urea : Ca ratios far above 1 and multiple doses, which is why the model's per-kg-CaCO₃ values for the "
            "lab protocols exceed the literature values, while the stoichiometric/optimised scenarios approach them.")
try:
    tab = []
    for s in chosen:
        r = run(s, "kg_caco3_precipitated")
        m = r.meta
        caco3 = max(float(m.get("caco3_precipitated_kg_per_kg_solids") or 0.0), 1e-9)
        tab.append({"scenario": s, "pathway": m.get("pathway"), "urea kg/kg CaCO3 (stoich. 0.60)": float(m.get("urea_kg_per_kg_solids") or 0.0) / caco3,
                    "Ca mol/kg CaCO3 (stoich. 9.99)": float(m.get("ca_mol_per_kg_solids") or 0.0) / caco3,
                    "urea : Ca molar ratio": m.get("urea_to_ca_molar_ratio"), "precipitation efficiency": m.get("precipitation_efficiency"),
                    "CaCO3 kg/kg solids": caco3, "liquid/solid L/kg": m.get("liquid_to_solid_L_per_kg")})
    tdf = pd.DataFrame(tab)
    st.dataframe(tdf.style.format({c: "{:.3g}" for c in tdf.columns if c not in ("scenario", "pathway")}, na_rep="n/a"), width="stretch", hide_index=True)
except Exception as exc:  # noqa: BLE001
    st.info(f"Reagent table not available: {exc}")
