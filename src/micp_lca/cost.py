"""Indicative production-cost estimate (life-cycle costing light) from the same inventory as the LCA.

Prices (EUR, indicative, editable) are stored in ``data/economics/prices.csv`` per background process
and unit. Two price levels are provided: ``bulk`` (industrial/technical grade) and ``lab``
(laboratory reagents), which reproduces the finding of the papers that laboratory-grade media
dominate the cost of MICP (Omoregie et al. 2019; Ottová et al. 2026: feather hydrolysate −80 %).

The cost covers only the priced inputs of the inventory (materials, energy, transport, water,
end-of-life fees, credits); labour, capital, maintenance and margins are excluded. Results are
reported per functional unit alongside the environmental indicators but never mixed with them.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .lcia import Results
from .loaders import DataBundle

INDICATIVE_NOTE = ("Indicative prices (data/economics/prices.csv); excludes labour, capital and margins. "
                   "Edit the file to use supplier quotations.")


def cost_table(result: Results, data: DataBundle, grade: str = "bulk", modules: tuple[str, ...] | None = None) -> pd.DataFrame:
    """Cost of the priced inventory flows per functional unit, by module and process group (EUR)."""
    prices = data.prices
    if prices.empty:
        return pd.DataFrame(columns=["module", "group", "process_id", "amount", "unit", "price_eur", "cost_eur", "priced"])
    col = "price_lab_eur" if grade == "lab" else "price_bulk_eur"
    price_by_id = {r["process_id"]: (float(r[col]), r["unit"]) for _, r in prices.iterrows()}
    rows: list[dict[str, Any]] = []
    for f in result.inventory.flows:
        if f.kind != "background":
            continue
        if modules and f.module not in modules:
            continue
        amount = f.amount * result.fu_factor
        price, unit = price_by_id.get(f.key, (float("nan"), ""))
        proc = data.background.get(f.key)
        priced = price == price and (not unit or not proc or unit == proc.unit)
        rows.append({"module": f.module, "group": f.group, "process_id": f.key, "amount": amount,
                     "unit": proc.unit if proc else f.unit, "price_eur": price if priced else float("nan"),
                     "cost_eur": amount * price if priced else 0.0, "priced": priced})
    return pd.DataFrame(rows)


def cost_summary(result: Results, data: DataBundle, grade: str = "bulk") -> dict[str, Any]:
    """Total cost per functional unit (A1–A3, C1–C4, D) and the unpriced flows."""
    df = cost_table(result, data, grade)
    if df.empty:
        return {"total_A1-A3": float("nan"), "unpriced": []}
    a13 = df[df["module"].isin(["A1", "A2", "A3"])]["cost_eur"].sum()
    c = df[df["module"].isin(["C1", "C2", "C3", "C4"])]["cost_eur"].sum()
    d = df[df["module"] == "D"]["cost_eur"].sum()
    by_group = df[df["module"].isin(["A1", "A2", "A3"])].groupby("group")["cost_eur"].sum().sort_values(ascending=False)
    return {"grade": grade, "total_A1-A3": float(a13), "total_C1-C4": float(c), "total_D": float(d),
            "by_group_A1-A3": by_group, "unpriced": sorted(set(df[~df["priced"]]["process_id"])),
            "functional_unit": result.functional_unit, "note": INDICATIVE_NOTE}
