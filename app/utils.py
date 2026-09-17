"""Shared helpers for the Streamlit application (data loading, cached model runs, charts)."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from micp_lca import load_data, run_scenario  # noqa: E402
from micp_lca.benchmarks import benchmark_impacts, compare_scenarios, compare_with_status_quo  # noqa: E402
from micp_lca.cost import cost_summary, cost_table  # noqa: E402
from micp_lca.lcia import FU_LABELS, Results  # noqa: E402

CORE = ["GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP", "EP-freshwater", "EP-marine",
        "EP-terrestrial", "POCP", "ADP-minerals&metals", "ADP-fossil", "WDP"]
ADDITIONAL = ["PM", "IRP", "ETP-fw", "HTP-c", "HTP-nc", "SQP"]
MODULES = ["A1", "A2", "A3", "C1", "C2", "C3", "C4", "D"]
PALETTE = px.colors.qualitative.Safe


@st.cache_resource(show_spinner="Loading the MICP LCA database …")
def get_data():
    return load_data()


def reload_data() -> None:
    """Clear caches after the user edited data files."""
    get_data.clear()
    run_cached.clear()


def _hashable(cfg: dict[str, Any]) -> str:
    return json.dumps(cfg, sort_keys=True, default=str)


@st.cache_data(show_spinner=False, max_entries=256)
def run_cached(scenario: str, functional_unit: str, overrides_json: str, params_json: str) -> Results:
    data = get_data()
    overrides = json.loads(overrides_json) if overrides_json else None
    params = json.loads(params_json) if params_json else None
    return run_scenario(scenario, data, functional_unit=functional_unit, overrides=overrides, param_overrides=params)


def run(scenario: str, functional_unit: str = "kg_product", overrides: dict[str, Any] | None = None,
        param_overrides: dict[str, float] | None = None) -> Results:
    return run_cached(scenario, functional_unit, _hashable(overrides or {}), _hashable(param_overrides or {}))


def fu_label(fu: str) -> str:
    return FU_LABELS.get(fu, fu)


def category_label(code: str, data) -> str:
    return f"{code} [{data.category_unit(code)}]"


def impacts_table(res: Results, data, categories: list[str] | None = None) -> pd.DataFrame:
    cats = categories or (CORE + ADDITIONAL)
    a13 = res.totals(("A1", "A2", "A3"))
    c = res.totals(("C1", "C2", "C3", "C4"))
    d = res.totals(("D",))
    df = pd.DataFrame({
        "indicator": cats,
        "unit": [data.category_unit(k) for k in cats],
        "A1–A3": [float(a13[k]) for k in cats],
        "C1–C4": [float(c[k]) for k in cats],
        "D": [float(d[k]) for k in cats],
        "A1–A3 + C": [float(a13[k] + c[k]) for k in cats],
        "coverage native": [res.coverage_native.get(k, float("nan")) for k in cats],
        "coverage incl. proxies": [res.coverage.get(k, float("nan")) for k in cats],
    })
    return df


def contribution_figure(res: Results, category: str, data, by: str = "group") -> go.Figure:
    df = res.contrib.copy()
    df = df[df[category] != 0]
    if by == "group":
        g = df.groupby(["group", "module"])[category].sum().reset_index()
        order = g.groupby("group")[category].sum().sort_values().index.tolist()
        fig = px.bar(g, x=category, y="group", color="module", orientation="h",
                     category_orders={"group": order, "module": MODULES}, color_discrete_sequence=PALETTE)
    else:
        g = df.groupby(["module", "group"])[category].sum().reset_index()
        fig = px.bar(g, x="module", y=category, color="group", category_orders={"module": MODULES}, color_discrete_sequence=PALETTE)
    fig.update_layout(height=max(380, 26 * df["group"].nunique() + 120), xaxis_title=f"{category} [{data.category_unit(category)} per {res.functional_unit}]",
                      yaxis_title="", legend_title="", margin=dict(l=10, r=10, t=30, b=10))
    return fig


def comparison_figure(table: pd.DataFrame, category: str, unit: str, fu: str, log: bool = False) -> go.Figure:
    col_a, col_c = f"{category} A1-A3", f"{category} A1-A3+C"
    df = table[table[col_a].notna()].sort_values(col_c).reset_index()
    fig = go.Figure()
    fig.add_bar(y=df["item"], x=df[col_a], orientation="h", name="A1–A3",
                marker_color=["#4c78a8" if t == "scenario" else "#9e9e9e" for t in df["type"]])
    fig.add_bar(y=df["item"], x=df[col_c] - df[col_a], orientation="h", name="C1–C4",
                marker_color=["#a6c8e8" if t == "scenario" else "#cfcfcf" for t in df["type"]])
    fig.update_layout(barmode="stack", height=max(400, 24 * len(df) + 120), xaxis_title=f"{category} [{unit}] per {fu_label(fu)}",
                      yaxis_title="", margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=-0.1))
    if log:
        fig.update_xaxes(type="log")
    return fig


def deep_update(base: dict[str, Any], upd: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in upd.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_update(out[k], v)
        else:
            out[k] = v
    return out


def download_button(df: pd.DataFrame, label: str, filename: str) -> None:
    st.download_button(label, df.to_csv(index=False).encode("utf-8"), file_name=filename, mime="text/csv")


def cost_block(res: Results, data) -> None:
    """Indicative cost summary (bulk vs laboratory grade) for a result."""
    if data.prices.empty:
        st.info("No price table found (data/economics/prices.csv).")
        return
    cb, cl = cost_summary(res, data, "bulk"), cost_summary(res, data, "lab")
    c1, c2, c3 = st.columns(3)
    c1.metric("Cost A1–A3, bulk/technical grade", f"{cb['total_A1-A3']:.3f} EUR / {res.functional_unit}")
    c2.metric("Cost A1–A3, laboratory grade", f"{cl['total_A1-A3']:.3f} EUR / {res.functional_unit}")
    c3.metric("End of life (C1–C4)", f"{cb['total_C1-C4']:.3f} EUR / {res.functional_unit}")
    df = pd.DataFrame({"bulk grade": cb["by_group_A1-A3"], "laboratory grade": cl["by_group_A1-A3"]}).fillna(0.0)
    st.plotly_chart(px.bar(df.reset_index().melt(id_vars="group", var_name="price level", value_name="EUR"),
                           x="EUR", y="group", color="price level", barmode="group", orientation="h",
                           color_discrete_sequence=PALETTE).update_layout(height=max(320, 24 * len(df) + 100), yaxis_title="", margin=dict(l=10, r=10, t=30, b=10)),
                    width="stretch")
    st.caption(cb["note"])
    if cb["unpriced"]:
        st.warning("Unpriced flows: " + ", ".join(cb["unpriced"]))
