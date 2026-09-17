"""Publication-style matplotlib figures used by the PDF report and the CLI.

All functions write a PNG (or PDF/SVG by extension) and return the path. They only depend on the
result objects of :mod:`micp_lca.lcia`, so they can be reused outside the report.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .lcia import Results

MODULE_ORDER = ["A1", "A2", "A3", "C1", "C2", "C3", "C4", "D"]
MODULE_COLOURS = {"A1": "#4c78a8", "A2": "#9ecae9", "A3": "#f58518", "C1": "#54a24b", "C2": "#88d27a", "C3": "#b79a20", "C4": "#e45756", "D": "#72b7b2"}
PALETTE = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#72b7b2", "#b279a2", "#ff9da6", "#9d755d", "#bab0ac", "#eeca3b",
           "#4e79a7", "#a0cbe8", "#f28e2b", "#ffbe7d", "#59a14f", "#8cd17d", "#b6992d", "#f1ce63", "#499894", "#86bcb6"]


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8, "legend.fontsize": 7, "xtick.labelsize": 7,
                         "ytick.labelsize": 7, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 100,
                         "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5})
    return plt


def _save(fig, path: Path | str, dpi: int = 170) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return path


def _fmt_unit(u: str) -> str:
    return u.replace("CO2", "CO$_2$").replace("H+", "H$^+$").replace("m3", "m$^3$").replace("SO2", "SO$_2$").replace("NMVOC", "NMVOC")


# --------------------------------------------------------------------------------------------
# contribution analysis


def contribution_by_group(res: Results, category: str, unit: str, path: Path | str, title: str = "") -> Path:
    """Horizontal stacked bars: process groups (rows) × life-cycle modules (colours)."""
    plt = _plt()
    df = res.contrib.groupby(["group", "module"])[category].sum().unstack("module").fillna(0.0)
    df = df.loc[df.abs().sum(axis=1).sort_values().index]
    df = df[[m for m in MODULE_ORDER if m in df.columns]]
    fig, ax = plt.subplots(figsize=(6.6, max(2.6, 0.26 * len(df) + 0.9)))
    left_pos = np.zeros(len(df))
    left_neg = np.zeros(len(df))
    for m in df.columns:
        vals = df[m].to_numpy()
        pos, neg = np.clip(vals, 0, None), np.clip(vals, None, 0)
        ax.barh(df.index, pos, left=left_pos, color=MODULE_COLOURS.get(m, "#999"), label=m, height=0.7)
        ax.barh(df.index, neg, left=left_neg, color=MODULE_COLOURS.get(m, "#999"), height=0.7)
        left_pos += pos
        left_neg += neg
    total = float(df.to_numpy().sum())
    for i, (g, row) in enumerate(df.iterrows()):
        v = float(row.sum())
        if total and abs(v) / abs(total) >= 0.02:
            ax.text(max(left_pos[i], 0) + 0.01 * max(left_pos.max(), 1e-12), i, f"{100 * v / total:.0f} %", va="center", fontsize=6.5, color="#333")
    ax.axvline(0, color="k", lw=0.6)
    ax.set_xlabel(f"{category} [{_fmt_unit(unit)} per {res.functional_unit.replace('_', ' ')}]")
    ax.set_title(title or f"Contribution analysis – {category}")
    ax.legend(title="module", ncol=len(df.columns), loc="lower right", frameon=False)
    return _save(fig, path)


def indicator_profile(res: Results, categories: list[str], path: Path | str, modules: tuple[str, ...] = ("A1", "A2", "A3")) -> Path:
    """100 % stacked bars: share of each process group in every indicator (cradle-to-gate)."""
    plt = _plt()
    df = res.contrib[res.contrib["module"].isin(modules)].groupby("group")[categories].sum()
    denom = df.abs().sum(axis=0).replace(0, np.nan)
    share = (df / denom).fillna(0.0)
    order = df["GWP-total"].abs().sort_values(ascending=False).index if "GWP-total" in df else df.index
    share = share.loc[order]
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    x = np.arange(len(categories))
    bottom_pos, bottom_neg = np.zeros(len(categories)), np.zeros(len(categories))
    for i, g in enumerate(share.index):
        vals = share.loc[g].to_numpy()
        pos, neg = np.clip(vals, 0, None), np.clip(vals, None, 0)
        ax.bar(x, pos, bottom=bottom_pos, color=PALETTE[i % len(PALETTE)], label=g, width=0.75)
        ax.bar(x, neg, bottom=bottom_neg, color=PALETTE[i % len(PALETTE)], width=0.75)
        bottom_pos += pos
        bottom_neg += neg
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xticks(x, categories, rotation=35, ha="right")
    ax.set_ylabel("share of the cradle-to-gate result")
    ax.set_title("Process-group profile across the EF 3.1 indicators (A1–A3)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False, fontsize=6.2)
    return _save(fig, path)


# --------------------------------------------------------------------------------------------
# comparison and ratios


def benchmark_comparison(table: pd.DataFrame, category: str, unit: str, fu_label: str, path: Path | str, highlight: str | None = None) -> Path:
    """Stacked A1–A3 / C1–C4 bars of scenarios (blue) and benchmarks (grey)."""
    plt = _plt()
    col_a, col_c = f"{category} A1-A3", f"{category} A1-A3+C"
    df = table[table[col_a].notna()].sort_values(col_c)
    fig, ax = plt.subplots(figsize=(6.6, max(2.4, 0.27 * len(df) + 0.8)))
    y = np.arange(len(df))
    a = df[col_a].to_numpy(float)
    c = (df[col_c] - df[col_a]).to_numpy(float)
    cols = ["#e45756" if i == highlight else ("#4c78a8" if t == "scenario" else "#9e9e9e") for i, t in zip(df.index, df["type"])]
    ax.barh(y, a, color=cols, height=0.7, label="A1–A3")
    ax.barh(y, c, left=a, color=[c_ + "88" for c_ in cols], height=0.7, label="C1–C4", hatch="///", edgecolor="white", lw=0.3)
    for yi, (va, vc) in enumerate(zip(a, c)):
        ax.text(va + vc + 0.01 * (a + c).max(), yi, f"{va + vc:.3g}", va="center", fontsize=6.5)
    ax.set_yticks(y, df.index)
    ax.set_xlabel(f"{category} [{_fmt_unit(unit)} per {fu_label}]")
    ax.set_title("Comparison with benchmark products (blue: scenarios, red: this scenario, grey: benchmarks)")
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, path)


def ratio_to_reference(ratios: pd.Series, reference_name: str, path: Path | str) -> Path:
    """Indicator-wise ratio scenario/reference on a log axis (1 = equal)."""
    plt = _plt()
    r = ratios.replace([np.inf, -np.inf], np.nan).dropna()
    r = r[r > 0]
    fig, ax = plt.subplots(figsize=(6.6, max(2.2, 0.24 * len(r) + 0.8)))
    y = np.arange(len(r))
    ax.barh(y, r.to_numpy(), color=["#54a24b" if v < 1 else "#e45756" for v in r.to_numpy()], height=0.7)
    ax.axvline(1.0, color="k", lw=0.8, ls="--")
    ax.set_xscale("log")
    ax.set_yticks(y, r.index)
    for yi, v in enumerate(r.to_numpy()):
        ax.text(v * 1.08, yi, f"×{v:.2f}", va="center", fontsize=6.5)
    ax.set_xlabel(f"ratio to {reference_name} (A1–A3, per kg of product; log scale)")
    ax.set_title("Indicator-wise comparison with the reference product")
    return _save(fig, path)


# --------------------------------------------------------------------------------------------
# carbon and nitrogen


def carbon_waterfall(components: dict[str, float], unit: str, fu_label: str, path: Path | str) -> Path:
    """Waterfall of the climate-change result: background groups, direct emissions, uptake, EoL, credits → net."""
    plt = _plt()
    labels = list(components)
    vals = np.array([components[k] for k in labels], float)
    cum = np.concatenate([[0.0], np.cumsum(vals)])
    fig, ax = plt.subplots(figsize=(6.6, 3.2))
    for i, (lab, v) in enumerate(zip(labels, vals)):
        colour = "#e45756" if v > 0 else "#54a24b"
        ax.bar(i, v, bottom=cum[i], color=colour, width=0.65)
        ax.text(i, cum[i + 1] + (0.02 if v >= 0 else -0.02) * abs(vals).max(), f"{v:+.3g}", ha="center", va="bottom" if v >= 0 else "top", fontsize=6.5)
        if i < len(labels) - 1:
            ax.plot([i + 0.325, i + 0.675], [cum[i + 1], cum[i + 1]], color="#555", lw=0.6)
    net = float(vals.sum())
    ax.bar(len(labels), net, color="#4c78a8", width=0.65)
    ax.text(len(labels), net + 0.02 * abs(vals).max(), f"{net:.3g}", ha="center", va="bottom", fontsize=7, fontweight="bold")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xticks(range(len(labels) + 1), labels + ["net (A1–A3 + C + D)"], rotation=30, ha="right")
    ax.set_ylabel(f"GWP-total [{_fmt_unit(unit)} per {fu_label}]")
    ax.set_title("Climate-change balance of the life cycle")
    return _save(fig, path)


def nitrogen_fate(fate: dict[str, float], path: Path | str) -> Path:
    plt = _plt()
    items = [(k, v) for k, v in fate.items() if v > 0]
    fig, ax = plt.subplots(figsize=(5.2, 2.8))
    if items:
        total = sum(v for _, v in items)
        labels = [f"{k.replace('_', ' ')} ({100 * v / total:.1f} %)" for k, v in items]
        wedges, _ = ax.pie([v for _, v in items], colors=PALETTE[: len(items)], startangle=90, counterclock=False,
                           wedgeprops={"linewidth": 0.6, "edgecolor": "white"})
        ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=7)
    ax.set_title("Fate of the nitrogen released by urea hydrolysis")
    ax.grid(False)
    return _save(fig, path)


# --------------------------------------------------------------------------------------------
# parametric sweep, tornado, Monte Carlo


def sweep_panels(df: pd.DataFrame, x_label: str, current: float | None, panels: list[tuple[str, str]], path: Path | str,
                 fu_label: str = "") -> Path:
    """Small multiples: each panel = one response column vs the swept parameter."""
    plt = _plt()
    ok = df[df["error"] == ""] if "error" in df else df
    n = len(panels)
    ncol = 2 if n > 1 else 1
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(6.6, 2.3 * nrow), squeeze=False)
    for ax, (col, ylabel) in zip(axes.flat, panels):
        if col not in ok:
            ax.set_visible(False)
            continue
        ax.plot(ok["value"], ok[col], marker="o", ms=3.5, lw=1.2, color="#4c78a8")
        if current is not None:
            ax.axvline(current, color="#e45756", ls="--", lw=0.9, label="current value")
        ax.set_xlabel(x_label)
        ax.set_ylabel(_fmt_unit(ylabel))
        y = ok[col].to_numpy(float)
        if len(y) and np.nanmin(y) > 0 and np.nanmax(y) / max(np.nanmin(y), 1e-12) > 30:
            ax.set_yscale("log")
    for ax in list(axes.flat)[n:]:
        ax.set_visible(False)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper right", frameon=False, ncol=2)
    fig.suptitle(f"Parametric analysis: response per {fu_label}" if fu_label else "Parametric analysis", y=1.02)
    fig.tight_layout()
    return _save(fig, path)


def tornado(df: pd.DataFrame, category: str, unit: str, path: Path | str, top: int = 12) -> Path:
    plt = _plt()
    d = df.head(top).iloc[::-1]
    base = float(d["base"].iloc[0])
    fig, ax = plt.subplots(figsize=(6.6, max(2.4, 0.3 * len(d) + 0.9)))
    y = np.arange(len(d))
    ax.barh(y, d["result_low"] - base, color="#4c78a8", height=0.7, label="input at its low bound")
    ax.barh(y, d["result_high"] - base, color="#e45756", height=0.7, label="input at its high bound", alpha=0.85)
    labels = [i.replace("industrial.", "").replace("bg:", "background: ").replace("fg:", "parameter: ") for i in d["input"]]
    ax.set_yticks(y, labels)
    ax.axvline(0, color="k", lw=0.6)
    ax.set_xlabel(f"change of {category} [{_fmt_unit(unit)}] from the central value {base:.3g}")
    ax.set_title("One-at-a-time sensitivity (tornado)")
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, path)


def mc_panels(samples: pd.Series, unit: str, deterministic: float | None, spearman: pd.Series, path: Path | str) -> Path:
    plt = _plt()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.6, 2.8), gridspec_kw={"width_ratios": [1.1, 1]})
    ax1.hist(samples, bins=50, color="#4c78a8", alpha=0.85)
    med = float(samples.median())
    ax1.axvline(med, color="k", ls="--", lw=0.9, label=f"median {med:.3g}")
    lo, hi = samples.quantile(0.025), samples.quantile(0.975)
    ax1.axvspan(lo, hi, color="#4c78a8", alpha=0.12, label="95 % interval")
    if deterministic is not None:
        ax1.axvline(deterministic, color="#e45756", lw=0.9, label=f"deterministic {deterministic:.3g}")
    ax1.set_xlabel(f"GWP-total [{_fmt_unit(unit)}]")
    ax1.set_ylabel("samples")
    ax1.legend(frameon=False, fontsize=6.2)
    ax1.set_title("Monte Carlo distribution")
    s = spearman.iloc[::-1]
    ax2.barh(np.arange(len(s)), s.to_numpy(), color=["#e45756" if v > 0 else "#54a24b" for v in s.to_numpy()], height=0.7)
    ax2.set_yticks(np.arange(len(s)), [i.replace("industrial.", "").replace("bg:", "bg: ").replace("fg:", "fg: ")[:38] for i in s.index], fontsize=6)
    ax2.set_xlabel("Spearman ρ with the result")
    ax2.set_title("Global sensitivity")
    fig.tight_layout()
    return _save(fig, path)


def cost_by_group(by_group_bulk: pd.Series, by_group_lab: pd.Series, fu_label: str, path: Path | str) -> Path:
    plt = _plt()
    df = pd.DataFrame({"bulk / technical grade": by_group_bulk, "laboratory grade": by_group_lab}).fillna(0.0)
    df = df.loc[df.sum(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(6.6, max(2.2, 0.26 * len(df) + 0.8)))
    y = np.arange(len(df))
    ax.barh(y - 0.18, df.iloc[:, 0], height=0.36, color="#4c78a8", label=df.columns[0])
    ax.barh(y + 0.18, df.iloc[:, 1], height=0.36, color="#f58518", label=df.columns[1])
    ax.set_yticks(y, df.index)
    ax.set_xlabel(f"EUR per {fu_label} (A1–A3, indicative)")
    ax.set_title("Indicative cost by process group")
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, path)


def module_split(res: Results, categories: list[str], path: Path | str) -> Path:
    """Stacked 100 % bars of the modules A1, A2, A3, C1–C4 and D for each indicator."""
    plt = _plt()
    bm = res.by_module().reindex(MODULE_ORDER).dropna(how="all")[categories]
    denom = bm.abs().sum(axis=0).replace(0, np.nan)
    share = (bm / denom).fillna(0.0)
    fig, ax = plt.subplots(figsize=(6.6, 2.6))
    x = np.arange(len(categories))
    bp, bn = np.zeros(len(categories)), np.zeros(len(categories))
    for m in share.index:
        vals = share.loc[m].to_numpy()
        pos, neg = np.clip(vals, 0, None), np.clip(vals, None, 0)
        ax.bar(x, pos, bottom=bp, color=MODULE_COLOURS.get(m, "#999"), label=m, width=0.75)
        ax.bar(x, neg, bottom=bn, color=MODULE_COLOURS.get(m, "#999"), width=0.75)
        bp += pos
        bn += neg
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xticks(x, categories, rotation=35, ha="right")
    ax.set_ylabel("share of the total (A1–A3 + C + D)")
    ax.set_title("Life-cycle module split per indicator")
    ax.legend(ncol=len(share.index), frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.32), fontsize=6.5, title="module")
    return _save(fig, path)
