"""Tables and figures for reporting (CSV/Markdown/PNG)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .lcia import Results
from .paths import results_dir

CORE = ["GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP", "EP-freshwater", "EP-marine",
        "EP-terrestrial", "POCP", "ADP-minerals&metals", "ADP-fossil", "WDP"]


def en15804_table(results: list[Results], categories: list[str] | None = None) -> pd.DataFrame:
    """EN 15804-style declaration table: scenario × (category, module block)."""
    cats = categories or CORE
    frames = []
    for r in results:
        a = r.totals(("A1", "A2", "A3"))[cats]
        c = r.totals(("C1", "C2", "C3", "C4"))[cats]
        d = r.totals(("D",))[cats]
        df = pd.DataFrame({"A1-A3": a, "C1-C4": c, "D": d, "unit": [r.units[k] + " / " + r.functional_unit for k in cats]})
        df.insert(0, "scenario", r.scenario)
        frames.append(df.reset_index().rename(columns={"index": "indicator"}))
    return pd.concat(frames, ignore_index=True)


def write_results(results: list[Results], out_dir: Path | str | None = None, prefix: str = "results") -> dict[str, Path]:
    """Write summary, EN 15804 table and per-scenario contribution tables as CSV files."""
    out = Path(out_dir) if out_dir else results_dir()
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    summary = pd.DataFrame([r.summary() for r in results])
    paths["summary"] = out / f"{prefix}_summary.csv"
    summary.to_csv(paths["summary"], index=False)
    paths["en15804"] = out / f"{prefix}_en15804_table.csv"
    en15804_table(results).to_csv(paths["en15804"], index=False)
    for r in results:
        p = out / f"{prefix}_contrib_{r.scenario}.csv"
        r.contrib.to_csv(p, index=False)
        paths[f"contrib_{r.scenario}"] = p
        pg = out / f"{prefix}_bygroup_{r.scenario}.csv"
        r.by_group().to_csv(pg)
        paths[f"bygroup_{r.scenario}"] = pg
    return paths


def markdown_table(df: pd.DataFrame, floatfmt: str = ".3g") -> str:
    """Render a DataFrame as a GitHub-flavoured Markdown table (no external dependency)."""
    df = df.copy()
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join([df.index.name or ""] + cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for idx, row in df.iterrows():
        vals = []
        for v in row.values:
            if isinstance(v, float):
                vals.append("n/a" if v != v else format(v, floatfmt))
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join([str(idx)] + vals) + " |")
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------ figures


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def plot_scenario_comparison(table: pd.DataFrame, category: str, unit: str, path: Path | str,
                             title: str | None = None) -> Path:
    """Horizontal bar chart of scenario/benchmark values (A1-A3 and A1-A3+C)."""
    plt = _plt()
    path = Path(path)
    col_c, col_a = f"{category} A1-A3+C", f"{category} A1-A3"
    df = table[table[col_a].notna()].sort_values(col_c)
    fig, ax = plt.subplots(figsize=(10, 0.42 * len(df) + 1.6))
    y = range(len(df))
    colors = ["#4c78a8" if t == "scenario" else "#9e9e9e" for t in df["type"]]
    ax.barh(list(y), df[col_c], color=colors, alpha=0.5, label="A1–A3 + C1–C4")
    ax.barh(list(y), df[col_a], color=colors, label="A1–A3")
    ax.set_yticks(list(y))
    ax.set_yticklabels(df.index)
    ax.set_xlabel(f"{category} [{unit}]")
    positive = df[col_c] > 0
    if positive.all() and df[col_c].max() / max(df[col_c].min(), 1e-12) > 50:
        ax.set_xscale("log")   # very different orders of magnitude (e.g. lab-scale energy artefact)
        ax.set_xlabel(f"{category} [{unit}] (log scale)")
    else:
        ax.axvline(0, color="k", lw=0.8)
    for i, v in enumerate(df[col_c]):
        ax.annotate(f"{v:.3g}", (v, i), xytext=(3, 0), textcoords="offset points", va="center", fontsize=8)
    ax.legend(loc="lower right")
    ax.set_title(title or f"{category} per functional unit — scenarios (blue) vs benchmarks (grey)")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def plot_contributions(result: Results, category: str, path: Path | str) -> Path:
    """Stacked contribution bar by process group for one scenario."""
    plt = _plt()
    path = Path(path)
    g = result.by_group()[category]
    g = g[g != 0]
    fig, ax = plt.subplots(figsize=(9, 0.4 * len(g) + 1.5))
    colors = ["#d62728" if v > 0 else "#2ca02c" for v in g.values]
    ax.barh(g.index[::-1], g.values[::-1], color=colors[::-1])
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel(f"{category} [{result.units[category]} per {result.functional_unit}]")
    ax.set_title(f"{result.scenario}: contributions by process group\n"
                 f"(total {g.sum():.3g} {result.units[category]} per {result.functional_unit})", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def plot_tornado(df: pd.DataFrame, category: str, unit: str, path: Path | str, top: int = 15) -> Path:
    plt = _plt()
    path = Path(path)
    d = df.head(top).iloc[::-1]
    base = float(d["base"].iloc[0]) if len(d) else 0.0
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(d) + 1.5))
    for i, (_, row) in enumerate(d.iterrows()):
        lo, hi = row["result_low"], row["result_high"]
        ax.barh(i, hi - base, left=base, color="#d62728", alpha=0.8)
        ax.barh(i, lo - base, left=base, color="#1f77b4", alpha=0.8)
    ax.set_yticks(range(len(d)))
    ax.set_yticklabels([str(x).replace("industrial.", "") for x in d["input"]])
    ax.axvline(base, color="k", lw=0.8)
    ax.set_xlabel(f"{category} [{unit}] (blue: low bound, red: high bound)")
    ax.set_title("One-at-a-time sensitivity (tornado)")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def plot_mc_histogram(samples: pd.Series, unit: str, path: Path | str, title: str = "") -> Path:
    plt = _plt()
    path = Path(path)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(samples.values, bins=40, color="#4c78a8", alpha=0.85)
    for q, ls in ((0.025, ":"), (0.5, "-"), (0.975, ":")):
        ax.axvline(samples.quantile(q), color="k", ls=ls, lw=1)
    ax.set_xlabel(f"{samples.name} [{unit}]")
    ax.set_ylabel("count")
    ax.set_title(title or f"Monte Carlo ({len(samples)} runs): median {samples.median():.3g}, 95 % interval "
                          f"{samples.quantile(0.025):.3g}–{samples.quantile(0.975):.3g}")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path
