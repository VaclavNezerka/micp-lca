"""Sensitivity (OAT tornado) and Monte Carlo uncertainty analysis."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import ADDITIONAL, CORE, PALETTE, category_label, download_button, fu_label, get_data, run  # utils puts src/ on sys.path
from micp_lca.sensitivity import oat_sensitivity  # noqa: E402
from micp_lca.uncertainty import MCResult, MCSettings, monte_carlo  # noqa: E402

st.set_page_config(page_title="Uncertainty", page_icon="🎲", layout="wide")
data = get_data()
st.title("Sensitivity and uncertainty")

all_scen = list(data.scenarios["scenarios"])
builder = st.session_state.get("builder")
c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
with c1:
    options = all_scen + (["(current Scenario-builder configuration)"] if builder else [])
    choice = st.selectbox("Scenario", options, index=all_scen.index("GYP_WCFC_single_dose") if "GYP_WCFC_single_dose" in all_scen else 0)
with c2:
    cat = st.selectbox("Impact category", CORE + ADDITIONAL, format_func=lambda c: category_label(c, data))
with c3:
    fu = st.selectbox("Functional unit", ["kg_product", "m3_product", "m3_MPa", "kg_caco3_precipitated"], format_func=fu_label)
with c4:
    mods = st.selectbox("Modules", ["A1–A3", "A1–A3 + C1–C4"])
modules = ("A1", "A2", "A3") if mods == "A1–A3" else ("A1", "A2", "A3", "C1", "C2", "C3", "C4")

if choice.startswith("(current"):
    scenario, overrides = builder["base"], builder["overrides"]
    st.caption(f"Base scenario **{scenario}** with the overrides set on the Scenario-builder page.")
else:
    scenario, overrides = choice, None
    st.caption(data.scenarios["scenarios"][scenario].get("description", ""))

unit = data.category_unit(cat)
tab_oat, tab_mc, tab_pedigree = st.tabs(["One-at-a-time (tornado)", "Monte Carlo", "Pedigree & ranges of the inputs"])

# ------------------------------------------------------------------------------------------ OAT
with tab_oat:
    st.markdown("Every scale-up parameter with a **min/max** range and every background factor with a **literature range** "
                "is set to its bounds while everything else stays central. Bars show the resulting change of the indicator.")
    top = st.slider("Number of inputs shown", 5, 40, 15)
    extra = st.multiselect("Also test discrete scenario switches", ["effluent_treatment", "eol", "carbon_accounting", "electricity", "site_specific_cf"], default=[])
    extra_keys = {}
    if "effluent_treatment" in extra:
        extra_keys["effluent_treatment"] = ["none", "ammonia_stripping", "struvite"]
    if "eol" in extra:
        extra_keys["eol"] = ["landfill", "recycling"]
    if "carbon_accounting" in extra:
        extra_keys["carbon_accounting"] = ["EF31", "EN15804A2"]
    if "electricity" in extra:
        extra_keys["electricity"] = [k for k, p in data.background.items() if p.unit == "kWh" and p.category == "energy" and "heat" not in k][:6]
    if "site_specific_cf" in extra:
        extra_keys["site_specific_cf"] = [True, False]

    @st.cache_data(show_spinner="Running one-at-a-time sensitivity …", max_entries=64)
    def _oat(scenario: str, cat: str, fu: str, modules: tuple, overrides_json: str, top: int, extra_json: str) -> pd.DataFrame:
        import json
        ov = json.loads(overrides_json) if overrides_json else None
        ek = json.loads(extra_json) if extra_json else None
        return oat_sensitivity(scenario, get_data(), category=cat, modules=modules, functional_unit=fu, overrides=ov, top=top, extra_scenario_keys=ek)

    import json
    try:
        oat = _oat(scenario, cat, fu, modules, json.dumps(overrides or {}, sort_keys=True, default=str), top, json.dumps(extra_keys, sort_keys=True, default=str))
    except Exception as exc:  # noqa: BLE001
        st.error(f"Sensitivity analysis failed: {exc}")
        oat = pd.DataFrame()
    if not oat.empty:
        base = float(oat["base"].iloc[0])
        st.metric(f"Central result ({mods})", f"{base:.4g} {unit} / {fu_label(fu)}")
        df = oat.iloc[::-1]
        fig = go.Figure()
        fig.add_bar(y=df["input"], x=df["result_low"] - base, orientation="h", name="at low bound", marker_color="#4c78a8",
                    customdata=df[["low", "result_low"]], hovertemplate="%{y}<br>input = %{customdata[0]:.4g}<br>result = %{customdata[1]:.4g}<extra>low</extra>")
        fig.add_bar(y=df["input"], x=df["result_high"] - base, orientation="h", name="at high bound", marker_color="#e45756",
                    customdata=df[["high", "result_high"]], hovertemplate="%{y}<br>input = %{customdata[0]:.4g}<br>result = %{customdata[1]:.4g}<extra>high</extra>")
        fig.update_layout(barmode="overlay", height=max(400, 26 * len(df) + 120), xaxis_title=f"change of {cat} [{unit}] from the central value",
                          yaxis_title="", margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=-0.08))
        st.plotly_chart(fig, width="stretch")
        show = oat[["input", "central", "low", "high", "result_low", "result_high", "swing", "delta_low_%", "delta_high_%"]]
        st.dataframe(show.style.format({c: "{:.4g}" for c in show.columns if c != "input"}), width="stretch", hide_index=True)
        download_button(oat, "Download tornado table (CSV)", f"oat_{scenario}_{cat}.csv")

# ------------------------------------------------------------------------------------------ Monte Carlo
with tab_mc:
    st.markdown("Background factors are sampled **log-normally** from their pedigree scores (Ciroth et al. 2016) or **log-triangularly** "
                "within the literature range; foreground scale-up parameters are sampled **triangularly** within min/max. "
                "Spearman rank correlations rank the inputs by their influence on the result.")
    s1, s2, s3, s4 = st.columns(4)
    n = s1.select_slider("Samples", [100, 200, 500, 1000, 2000, 5000], value=500)
    seed = s2.number_input("Random seed", 0, 10_000, 42)
    sample_bg = s3.checkbox("Sample background factors", value=True)
    sample_fg = s4.checkbox("Sample foreground parameters", value=True)
    use_lit = st.checkbox("Use literature ranges where available (otherwise pedigree only)", value=True)
    go_mc = st.button("Run Monte Carlo", type="primary")
    key = f"mc::{scenario}::{fu}::{modules}::{n}::{seed}::{sample_bg}::{sample_fg}::{use_lit}::{hash(str(overrides))}"
    if go_mc:
        bar = st.progress(0, text="Sampling …")
        settings = MCSettings(n=int(n), seed=int(seed), sample_background=sample_bg, sample_foreground=sample_fg, use_literature_ranges=use_lit)
        try:
            mc = monte_carlo(scenario, data, settings, functional_unit=fu, modules=modules, overrides=overrides,
                             progress=lambda i: bar.progress(min(1.0, i / n), text=f"{i}/{n} samples"))
            bar.progress(1.0, text="done")
            st.session_state[key] = mc
        except Exception as exc:  # noqa: BLE001
            st.error(f"Monte Carlo failed: {exc}")
    mc: MCResult | None = st.session_state.get(key)
    if mc is None:
        st.info("Set the options and press *Run Monte Carlo*. 500 samples take a few seconds to a minute depending on the scenario.")
    else:
        y = mc.category_samples[cat]
        p = y.quantile([0.025, 0.25, 0.5, 0.75, 0.975])
        try:
            central = float(run(scenario, fu, overrides).totals(modules)[cat])
        except Exception:  # noqa: BLE001
            central = float("nan")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Deterministic", f"{central:.4g}")
        m2.metric("Median", f"{p[0.5]:.4g}")
        m3.metric("2.5 %", f"{p[0.025]:.4g}")
        m4.metric("97.5 %", f"{p[0.975]:.4g}")
        m5.metric("CV", f"{y.std() / y.mean():.1%}" if y.mean() else "n/a")
        h = px.histogram(y, nbins=60, labels={"value": f"{cat} [{unit}] per {fu_label(fu)}"}, color_discrete_sequence=PALETTE)
        h.add_vline(x=p[0.5], line_dash="dash", annotation_text="median")
        if central == central:
            h.add_vline(x=central, line_color="#e45756", annotation_text="deterministic", annotation_position="top left")
        h.update_layout(height=360, showlegend=False, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="samples")
        st.plotly_chart(h, width="stretch")

        st.subheader("Percentiles of all impact categories")
        pct = mc.percentiles()
        pct.columns = [f"P{q * 100:g}" for q in pct.columns]
        pct.insert(0, "unit", [data.category_unit(c) for c in pct.index])
        st.dataframe(pct.style.format({c: "{:.4g}" for c in pct.columns if c != "unit"}), width="stretch")

        st.subheader("Global sensitivity (Spearman rank correlation with the result)")
        sp = mc.spearman(cat, top=40)
        thr = 2.0 / (len(y) ** 0.5)          # ≈ 95 % noise level of a rank correlation with n samples
        sp = sp[sp.abs() >= thr].head(20)
        if len(sp):
            sdf = sp.reset_index()
            sdf.columns = ["input", "rho"]
            fig = px.bar(sdf.iloc[::-1], x="rho", y="input", orientation="h", color="rho", color_continuous_scale="RdBu_r", range_color=(-1, 1))
            fig.update_layout(height=max(360, 24 * len(sdf) + 100), yaxis_title="", coloraxis_showscale=False, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, width="stretch")
            st.caption(f"bg: background factor multiplier (sampled from pedigree/literature range); fg: foreground scale-up parameter. "
                       f"Inputs with |ρ| < {thr:.2f} (noise level for n = {len(y)}) are not shown.")
        else:
            st.info("No input correlates significantly with the result at this sample size.")
        out = mc.category_samples.copy()
        out.insert(0, "sample", range(1, len(out) + 1))
        download_button(out, "Download samples (CSV)", f"mc_{scenario}_{fu}.csv")
        download_button(pd.concat([mc.category_samples, mc.input_samples], axis=1), "Download samples incl. inputs (CSV)", f"mc_{scenario}_{fu}_inputs.csv")

# ------------------------------------------------------------------------------------------ pedigree overview
with tab_pedigree:
    st.markdown("Uncertainty information of the background datasets used by the selected scenario.")
    try:
        res = run(scenario, fu, overrides)
        used = sorted({f.key for f in res.inventory.flows if f.kind == "background"})
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
        used = []
    from micp_lca.uncertainty import pedigree_gsd
    rows = []
    for pid in used:
        p = data.background[pid]
        rows.append({"process_id": pid, "name": p.name, "unit": p.unit, "data_type": p.data_type, "source": p.source_id,
                     "GWP": p.gwp_any, "GWP min": p.gwp_min, "GWP max": p.gwp_max,
                     "pedigree (R,C,T,G,F)": ",".join(str(x) for x in p.pedigree), "σg (pedigree)": pedigree_gsd(p.pedigree, p.basic_uncertainty),
                     "proxy-filled categories": len(p.proxy_filled)})
    if rows:
        pdf = pd.DataFrame(rows)
        st.dataframe(pdf.style.format({"GWP": "{:.4g}", "GWP min": "{:.4g}", "GWP max": "{:.4g}", "σg (pedigree)": "{:.3f}"}), width="stretch", hide_index=True)
        download_button(pdf, "Download (CSV)", f"pedigree_{scenario}.csv")
    st.markdown("**Foreground scale-up parameter ranges**")
    from micp_lca.inventory import Params
    scale = (overrides or {}).get("scale") or data.scenario_config(scenario).get("scale", "industrial")
    rng = Params(data.scaleup, scale).ranges(scale)
    rdf = pd.DataFrame([{"parameter": k, "value": v[0], "min": v[1], "max": v[2]} for k, v in rng.items()])
    st.dataframe(rdf.style.format({"value": "{:.4g}", "min": "{:.4g}", "max": "{:.4g}"}), width="stretch", hide_index=True)
