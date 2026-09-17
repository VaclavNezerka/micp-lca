"""One-at-a-time (OAT) sensitivity analysis producing tornado-style tables.

Every scale-up parameter with a min/max range and every background factor with a literature
range is varied to its bounds while all other inputs stay at their central values.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .inventory import Params, build_inventory
from .lcia import assess
from .loaders import DataBundle


def oat_sensitivity(scenario: str, data: DataBundle, *, category: str = "GWP-total",
                    modules: tuple[str, ...] = ("A1", "A2", "A3"), functional_unit: str | None = None,
                    overrides: dict[str, Any] | None = None, top: int | None = 20,
                    extra_scenario_keys: dict[str, list[Any]] | None = None) -> pd.DataFrame:
    """Return a table with the result at the low/high bound of each input, sorted by swing."""
    base_inv = build_inventory(scenario, data, overrides=overrides)
    fu = functional_unit or base_inv.config.get("functional_unit", "kg_product")
    base = float(assess(base_inv, data, functional_unit=fu).totals(modules)[category])
    scale = base_inv.config.get("scale", "industrial")
    used = {f.key for f in base_inv.flows if f.kind == "background"}
    rows: list[dict[str, Any]] = []

    def run(param_overrides: dict[str, float] | None = None, bg: dict[str, float] | None = None,
            scen_over: dict[str, Any] | None = None) -> float:
        ov = dict(overrides or {})
        if scen_over:
            ov.update(scen_over)
        inv = build_inventory(scenario, data, overrides=ov, param_overrides=param_overrides)
        return float(assess(inv, data, functional_unit=fu, bg_factor_overrides=bg).totals(modules)[category])

    for path, (v, lo, hi) in Params(data.scaleup, scale).ranges(scale).items():
        if hi <= lo:
            continue
        r_lo, r_hi = run({path: lo}), run({path: hi})
        rows.append({"input": f"fg:{path}", "central": v, "low": lo, "high": hi, "result_low": r_lo, "result_high": r_hi})
    for pid in sorted(used):
        proc = data.background[pid]
        if proc.gwp_min is None or proc.gwp_max is None or proc.gwp <= 0:
            continue
        m_lo, m_hi = proc.gwp_min / proc.gwp, proc.gwp_max / proc.gwp
        rows.append({"input": f"bg:{pid}", "central": proc.gwp, "low": proc.gwp_min, "high": proc.gwp_max,
                     "result_low": run(bg={pid: m_lo}), "result_high": run(bg={pid: m_hi})})
    for key, values in (extra_scenario_keys or {}).items():
        for val in values:
            rows.append({"input": f"scenario:{key}={val}", "central": base_inv.config.get(key), "low": val, "high": val,
                         "result_low": run(scen_over={key: val}), "result_high": run(scen_over={key: val})})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["base"] = base
    df["swing"] = (df["result_high"] - df["result_low"]).abs()
    df["delta_low_%"] = (df["result_low"] / base - 1.0) * 100.0 if base else float("nan")
    df["delta_high_%"] = (df["result_high"] / base - 1.0) * 100.0 if base else float("nan")
    df = df.sort_values("swing", ascending=False).reset_index(drop=True)
    return df.head(top) if top else df
