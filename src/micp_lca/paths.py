"""Location of the data directory.

The canonical data live in ``<repo>/data``. The location can be overridden with the environment
variable ``MICP_LCA_DATA`` (e.g. when the package is installed outside the repository).
"""
from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    env = os.environ.get("MICP_LCA_DATA")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data"
        if (candidate / "foreground" / "protocols.yaml").exists():
            return candidate
    raise FileNotFoundError(
        "Could not locate the micp_lca data directory. Set MICP_LCA_DATA to the path of the 'data' folder."
    )


def results_dir() -> Path:
    d = data_dir().parent / "results"
    d.mkdir(parents=True, exist_ok=True)
    return d
