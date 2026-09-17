"""Compare scenarios with each other and with benchmark products."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (ADDITIONAL, CORE, PALETTE, category_label, comparison_figure, compare_scenarios, compare_with_status_quo,
                   download_button, fu_label, get_data, run)

st.set_page_config(page_title="Compare", page_icon="📊", layout="wide")
data = get_data()
st.title("Compare scenarios and benchmarks")

all_scen = list(data.scenarios["scenarios"])
default = [s for s in ("GYP_WCFC_single_dose", "GYP_WCFC_single_dose_feather", "BC_lactate_30d", "BC_feather_media",
                       "SP_optimised_recirculation", "SP_lab_protocol_90d", "TR_fungal_lactate", "ABIOTIC_WCFC_gypsum") if s in all_scen]
left, right = st.columns([2, 1])
with left:
    chosen = st.multiselect("Scenarios", all_scen, default=default)
with right:
    fu = st.selectbox("Functional unit", ["kg_product", "m3_product", "m3_MPa"], format_func=fu_label)
    cat = st.selectbox("Impact category", CORE + ADDITIONAL, format_func=lambda c: category_label(c, data))
bench_all = list(data.scenarios["benchmarks"])
benchmarks = st.multiselect("Benchmarks", bench_all, default=[b for b in bench_all if b != "landfill_WCF_status_quo"])
log = st.checkbox("Logarithmic axis", value=False)

results = []
failed = []
for s in chosen:
    try:
        results.append(run(s, fu))
    except Exception as exc:  # noqa: BLE001
        failed.append(f"{s}: {exc}")
if failed:
    st.warning("Not evaluable for this functional unit: " + "; ".join(failed))
if not results:
    st.stop()

table = compare_scenarios(results, data, benchmarks=benchmarks, category=cat, functional_unit=fu)
st.plotly_chart(comparison_figure(table, cat, data.category_unit(cat), fu, log=log), width="stretch")
st.dataframe(table.style.format({f"{cat} A1-A3": "{:.4g}", f"{cat} A1-A3+C": "{:.4g}", "fc_MPa": "{:.2f}", "bulk_density_kg_m3": "{:.0f}", "coverage": "{:.0%}"}),
             width="stretch")
download_button(table.reset_index(), "Download comparison (CSV)", f"comparison_{cat}_{fu}.csv")

st.subheader("All core indicators (A1–A3) of the selected scenarios")
rows = {}
for r in results:
    t = r.totals(("A1", "A2", "A3"))
    rows[r.scenario] = {c: float(t[c]) for c in CORE}
df = pd.DataFrame(rows).T
df.columns = [category_label(c, data) for c in df.columns]
st.dataframe(df.style.format("{:.4g}"), width="stretch")

st.subheader("Relative profile (each indicator normalised to the maximum among the selected scenarios)")
rel = df / df.abs().max()
fig = px.imshow(rel.T, color_continuous_scale="Blues", aspect="auto", labels=dict(color="share of max"))
fig.update_layout(height=520, margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, width="stretch")

st.subheader("System expansion: block + disposal of the fines (status quo basket)")
st.markdown("A biocemented block absorbs waste fines; the fair comparison is with *a conventional block* **plus** *landfilling of the same mass of fines* (per kg of product, A1–A3 + C1–C4, GWP-total).")
bench = st.selectbox("Conventional block", [b for b in bench_all if b != "landfill_WCF_status_quo"], index=0)
sq_rows = []
for r in results:
    try:
        r_kg = run(r.scenario, "kg_product")
        sq = compare_with_status_quo(r_kg, data, bench, "GWP-total")
        sq_rows.append({"scenario": r.scenario, **sq})
    except Exception as exc:  # noqa: BLE001
        st.warning(f"{r.scenario}: {exc}")
if sq_rows:
    sdf = pd.DataFrame(sq_rows).set_index("scenario")
    st.dataframe(sdf.style.format("{:.4g}"), width="stretch")
    fig = px.bar(sdf.reset_index().melt(id_vars="scenario", value_vars=["biocemented_block", "status_quo_basket"], var_name="system", value_name="kg CO2e / kg"),
                 x="scenario", y="kg CO2e / kg", color="system", barmode="group", color_discrete_sequence=PALETTE)
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, width="stretch")
