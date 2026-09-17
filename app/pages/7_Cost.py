"""Indicative production cost per functional unit (bulk vs laboratory-grade inputs) across scenarios."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from micp_lca.cost import INDICATIVE_NOTE, cost_summary, cost_table
from utils import PALETTE, download_button, fu_label, get_data, run

st.set_page_config(page_title="Cost", page_icon="💶", layout="wide")
data = get_data()
st.title("Indicative cost (life-cycle costing light)")
st.caption(INDICATIVE_NOTE + " The cost covers the priced inventory flows only (materials, energy, water, transport, end-of-life fees, credits).")

if data.prices.empty:
    st.warning("No price table found (data/economics/prices.csv).")
    st.stop()

all_scen = list(data.scenarios["scenarios"])
default = [s for s in ("GYP_WCFC_single_dose", "GYP_WCFC_single_dose_feather", "BC_lactate_30d", "BC_feather_media", "SP_optimised_recirculation",
                       "SP_lab_protocol_90d", "LIT_SP_NH4YE_medium", "LIT_SP_corn_steep_liquor", "LIT_EICP") if s in all_scen]
c1, c2 = st.columns([3, 1])
chosen = c1.multiselect("Scenarios", all_scen, default=default)
fu = c2.selectbox("Functional unit", ["kg_product", "m3_product", "m3_MPa", "kg_caco3_precipitated", "kg_solids"], format_func=fu_label)

rows = []
results = {}
for s in chosen:
    try:
        r = run(s, fu)
        results[s] = r
        cb, cl = cost_summary(r, data, "bulk"), cost_summary(r, data, "lab")
        rows.append({"scenario": s, "bulk grade A1–A3": cb["total_A1-A3"], "laboratory grade A1–A3": cl["total_A1-A3"],
                     "C1–C4": cb["total_C1-C4"], "D": cb["total_D"], "GWP A1–A3 [kg CO2e]": r.gwp(), "unpriced flows": len(cb["unpriced"])})
    except Exception as exc:  # noqa: BLE001
        st.warning(f"{s}: {exc}")
if not rows:
    st.stop()
df = pd.DataFrame(rows).set_index("scenario")
st.subheader(f"Cost per {fu_label(fu)} (EUR)")
st.dataframe(df.style.format({c: "{:.3g}" for c in df.columns if c != "unpriced flows"}), width="stretch")
download_button(df.reset_index(), "Download (CSV)", f"cost_{fu}.csv")

log = st.checkbox("Logarithmic axis", value=False)
m = df.reset_index().melt(id_vars="scenario", value_vars=["bulk grade A1–A3", "laboratory grade A1–A3"], var_name="price level", value_name="EUR")
fig = px.bar(m, x="EUR", y="scenario", color="price level", barmode="group", orientation="h", color_discrete_sequence=PALETTE, log_x=log)
fig.update_layout(height=max(360, 40 * len(df) + 100), yaxis_title="", xaxis_title=f"EUR per {fu_label(fu)} (A1–A3)", margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, width="stretch")

st.subheader("Eco-efficiency: cost vs. climate impact")
fig = px.scatter(df.reset_index(), x="GWP A1–A3 [kg CO2e]", y="bulk grade A1–A3", text="scenario", log_x=log, log_y=log, color_discrete_sequence=PALETTE)
fig.update_traces(textposition="top center")
fig.update_layout(height=420, xaxis_title=f"GWP-total A1–A3 [kg CO2e per {fu_label(fu)}]", yaxis_title=f"cost, bulk grade [EUR per {fu_label(fu)}]", margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, width="stretch")

st.subheader("Cost breakdown of one scenario")
s = st.selectbox("Scenario", list(results))
grade = st.radio("Price level", ["bulk", "lab"], horizontal=True)
ct = cost_table(results[s], data, grade)
ct = ct[ct["module"].isin(["A1", "A2", "A3", "C1", "C2", "C3", "C4", "D"])]
agg = ct.groupby(["module", "group"])["cost_eur"].sum().reset_index()
agg = agg[agg["cost_eur"] != 0]
fig = px.bar(agg, x="cost_eur", y="group", color="module", orientation="h", color_discrete_sequence=PALETTE)
fig.update_layout(height=max(360, 26 * agg["group"].nunique() + 100), yaxis_title="", xaxis_title=f"EUR per {fu_label(fu)}", margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, width="stretch")
detail = ct.sort_values("cost_eur", ascending=False)
st.dataframe(detail.style.format({"amount": "{:.4g}", "price_eur": "{:.4g}", "cost_eur": "{:.4g}"}, na_rep="—"), width="stretch", hide_index=True, height=420)
unpriced = sorted(set(ct[~ct["priced"]]["process_id"]))
if unpriced:
    st.warning("Unpriced flows (add prices on the Data-editor page): " + ", ".join(unpriced))
download_button(ct, "Download cost table (CSV)", f"cost_table_{s}_{grade}.csv")
