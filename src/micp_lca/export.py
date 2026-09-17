"""Export of foreground inventories for other LCA software.

* :func:`inventory_table` – flat CSV/DataFrame of the foreground exchanges per functional unit,
  including the recommended ecoinvent dataset for every background flow (``ecoinvent_proxy`` in the
  background tables), so that the model can be re-computed with licensed background data.
* :func:`to_brightway` – a Brightway2/2.5 database dictionary (``{(db, code): {...}}``) that can be
  written with ``bw2data.Database(name).write(data)`` after linking the ``ecoinvent_proxy`` names
  to an installed ecoinvent database (see docs/07_using_ecoinvent_brightway.md).
* :func:`to_openlca_csv` – simplified process/exchange CSV pair for manual import into openLCA.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .lcia import Results
from .loaders import DataBundle

_ELEMENTARY_EI_NAMES = {
    ("carbon dioxide (fossil)", "air"): "Carbon dioxide, fossil",
    ("carbon dioxide (biogenic)", "air"): "Carbon dioxide, non-fossil",
    ("ammonia", "air"): "Ammonia",
    ("nitrous oxide", "air"): "Dinitrogen monoxide",
    ("ammonium", "water"): "Ammonium, ion",
    ("chloride", "water"): "Chloride",
    ("lactic acid", "water"): "Lactic acid",
    ("urea", "water"): "Urea",
}


def inventory_table(result: Results, data: DataBundle) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for f in result.inventory.flows:
        amount = f.amount * result.fu_factor
        if f.kind == "background":
            p = data.background[f.key]
            rows.append({"module": f.module, "group": f.group, "type": "technosphere", "name": p.name, "process_id": f.key,
                         "amount": amount, "unit": p.unit, "geography": p.geography, "data_type": p.data_type,
                         "source_id": p.source_id, "ecoinvent_proxy": p.ecoinvent_proxy, "bg_module": f.bg_module or ""})
        else:
            rows.append({"module": f.module, "group": f.group, "type": "biosphere", "name": f.key, "process_id": "",
                         "amount": amount, "unit": f.unit, "geography": "", "data_type": "EF 3.1 elementary flow",
                         "source_id": "EF31", "ecoinvent_proxy": _ELEMENTARY_EI_NAMES.get((f.key, f.compartment), f.key),
                         "bg_module": f.compartment})
    df = pd.DataFrame(rows)
    df.attrs["functional_unit"] = result.functional_unit
    return df


def to_brightway(result: Results, data: DataBundle, db_name: str = "micp_lca_foreground",
                 background_db: str = "ecoinvent") -> dict[tuple[str, str], dict[str, Any]]:
    """Brightway-style database dict for the foreground process (one activity per module)."""
    inv = result.inventory
    activities: dict[tuple[str, str], dict[str, Any]] = {}
    product_code = f"{inv.scenario}"
    exchanges: list[dict[str, Any]] = [{"input": (db_name, product_code), "amount": 1.0, "type": "production",
                                        "unit": result.functional_unit}]
    for f in inv.flows:
        amount = f.amount * result.fu_factor
        if f.kind == "background":
            p = data.background[f.key]
            exchanges.append({"input": (background_db, p.ecoinvent_proxy or p.process_id), "amount": amount, "unit": p.unit,
                              "type": "technosphere", "name": p.name, "module": f.module, "group": f.group,
                              "comment": f"micp_lca background id {f.key}; link to ecoinvent dataset '{p.ecoinvent_proxy}'"})
        else:
            exchanges.append({"input": ("biosphere3", _ELEMENTARY_EI_NAMES.get((f.key, f.compartment), f.key)),
                              "amount": amount, "unit": f.unit, "type": "biosphere", "categories": (f.compartment,),
                              "module": f.module, "group": f.group})
    activities[(db_name, product_code)] = {
        "name": f"biocemented block, {inv.scenario}", "unit": result.functional_unit, "location": "CZ",
        "reference product": "biocemented block", "exchanges": exchanges,
        "comment": json.dumps({k: v for k, v in inv.meta.items() if isinstance(v, (int, float, str))}),
    }
    return activities


def to_openlca_csv(result: Results, data: DataBundle, out_dir: Path | str) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = inventory_table(result, data)
    proc = out / f"openlca_process_{result.scenario}.csv"
    ex = out / f"openlca_exchanges_{result.scenario}.csv"
    pd.DataFrame([{"process": f"biocemented block, {result.scenario}", "reference_flow": "biocemented block",
                   "amount": 1.0, "unit": result.functional_unit, "location": "CZ"}]).to_csv(proc, index=False)
    df.to_csv(ex, index=False)
    return proc, ex
