"""Uncertainty analysis: pedigree matrix, Monte Carlo simulation and global sensitivity ranking.

* Background factors: lognormal distributions whose geometric standard deviation is derived from
  the pedigree scores (reliability, completeness, temporal, geographical, technological
  correlation) with the empirically based uncertainty factors of Ciroth et al. (2016) and the
  basic uncertainty of the flow, following the ecoinvent v3 procedure (Muller et al. 2016).
  When a literature range (``gwp_min``/``gwp_max``) is available it is used instead
  (log-uniform between the bounds, central value preserved as the mode).
* Foreground parameters: triangular distributions between the ``min``/``max`` bounds in
  ``scaleup.yaml`` (mode = central value).
* Sensitivity: Spearman rank correlation between sampled inputs and the result (global,
  variance-based screening), plus a one-at-a-time tornado analysis in :mod:`micp_lca.sensitivity`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd

from .inventory import Params, build_inventory
from .lcia import Results, assess
from .loaders import BackgroundProcess, DataBundle

# Ciroth et al. (2016) uncertainty factors (GSD) per pedigree score 1..5
CIROTH_2016 = {
    "R": (1.00, 1.54, 1.61, 1.69, 1.69),
    "C": (1.00, 1.03, 1.04, 1.08, 1.08),
    "T": (1.00, 1.03, 1.10, 1.19, 1.29),
    "G": (1.00, 1.04, 1.08, 1.11, 1.11),
    "F": (1.00, 1.18, 1.65, 2.08, 2.80),
}
# Original ecoinvent v2 factors (Weidema & Wesnæs 1996 / Frischknecht et al. 2005) for comparison
ECOINVENT_V2 = {
    "R": (1.00, 1.05, 1.10, 1.20, 1.50),
    "C": (1.00, 1.02, 1.05, 1.10, 1.20),
    "T": (1.00, 1.03, 1.10, 1.20, 1.50),
    "G": (1.00, 1.01, 1.02, 1.05, 1.10),
    "F": (1.00, 1.05, 1.20, 1.50, 2.00),
}


def pedigree_gsd(scores: tuple[int, int, int, int, int], basic_uncertainty: float = 1.05,
                 factors: dict[str, tuple[float, ...]] = CIROTH_2016) -> float:
    """Geometric standard deviation σg from pedigree scores: ln²σg = Σ ln²UF_i + ln²UB."""
    s = math.log(basic_uncertainty) ** 2
    for key, score in zip("RCTGF", scores):
        s += math.log(factors[key][max(1, min(5, int(score))) - 1]) ** 2
    return math.exp(math.sqrt(s))


@dataclass
class MCSettings:
    n: int = 1000
    seed: int = 42
    sample_background: bool = True
    sample_foreground: bool = True
    use_literature_ranges: bool = True
    pedigree_factors: dict[str, tuple[float, ...]] | None = None


def sample_background_multipliers(data: DataBundle, rng: np.random.Generator, n: int,
                                  settings: MCSettings) -> dict[str, np.ndarray]:
    """Multiplicative samples (median 1) for every background process used in the model."""
    out: dict[str, np.ndarray] = {}
    factors = settings.pedigree_factors or CIROTH_2016
    for pid, proc in data.background.items():
        g = proc.gwp_any
        if proc.data_type == "secondary_material" or g == 0 or math.isnan(g):
            out[pid] = np.ones(n)
            continue
        if settings.use_literature_ranges and proc.gwp_min and proc.gwp_max and proc.gwp_max > proc.gwp_min > 0:
            lo, hi = math.log(proc.gwp_min / g), math.log(proc.gwp_max / g)
            # triangular in log space with mode at the central value
            out[pid] = np.exp(rng.triangular(lo, 0.0, hi, n))
        else:
            gsd = pedigree_gsd(proc.pedigree, proc.basic_uncertainty, factors)
            out[pid] = np.exp(rng.normal(0.0, math.log(gsd), n))
    return out


def sample_foreground_parameters(data: DataBundle, rng: np.random.Generator, n: int,
                                 scale: str = "industrial") -> dict[str, np.ndarray]:
    """Triangular samples of every {value,min,max} parameter under ``scaleup[scale]``."""
    P = Params(data.scaleup, scale)
    out: dict[str, np.ndarray] = {}
    for path, (v, lo, hi) in P.ranges(scale).items():
        if hi > lo:
            v = min(max(v, lo), hi)
            out[path] = rng.triangular(lo, v, hi, n)
    return out


@dataclass
class MCResult:
    scenario: str
    category_samples: pd.DataFrame        # n × categories (per functional unit, modules A1–A3 unless stated)
    input_samples: pd.DataFrame           # n × inputs (background multipliers and foreground parameters)
    modules: tuple[str, ...]

    def percentiles(self, q: tuple[float, ...] = (0.025, 0.25, 0.5, 0.75, 0.975)) -> pd.DataFrame:
        return self.category_samples.quantile(list(q)).T

    def spearman(self, category: str = "GWP-total", top: int = 15) -> pd.Series:
        """Rank correlation of inputs with the result: a global sensitivity screening."""
        y = self.category_samples[category].rank()
        rows = {}
        for col in self.input_samples.columns:
            x = self.input_samples[col]
            if x.std() == 0:
                continue
            rows[col] = float(np.corrcoef(x.rank(), y)[0, 1])
        s = pd.Series(rows).sort_values(key=lambda v: -v.abs())
        return s.head(top)


def monte_carlo(scenario: str, data: DataBundle, settings: MCSettings | None = None, *,
                functional_unit: str | None = None, modules: tuple[str, ...] = ("A1", "A2", "A3"),
                overrides: dict[str, Any] | None = None, progress: Callable[[int], None] | None = None) -> MCResult:
    """Monte Carlo propagation of background and foreground uncertainties for one scenario."""
    settings = settings or MCSettings()
    rng = np.random.default_rng(settings.seed)
    cfg = data.scenario_config(scenario)
    if overrides:
        cfg.update(overrides)
    scale = cfg.get("scale", "industrial")
    bg = sample_background_multipliers(data, rng, settings.n, settings) if settings.sample_background else {}
    fg = sample_foreground_parameters(data, rng, settings.n, scale) if settings.sample_foreground else {}
    base_inv = build_inventory(scenario, data, overrides=overrides)
    used = {f.key for f in base_inv.flows if f.kind == "background"}
    bg = {k: v for k, v in bg.items() if k in used}
    cats = data.category_codes
    samples = np.zeros((settings.n, len(cats)))
    for i in range(settings.n):
        p_over = {k: float(v[i]) for k, v in fg.items()}
        b_over = {k: float(v[i]) for k, v in bg.items()}
        inv = build_inventory(scenario, data, overrides=overrides, param_overrides=p_over)
        fu = functional_unit or inv.config.get("functional_unit", "kg_product")
        res = assess(inv, data, functional_unit=fu, bg_factor_overrides=b_over)
        samples[i] = res.totals(modules).values
        if progress and (i + 1) % 100 == 0:
            progress(i + 1)
    inputs = pd.DataFrame({**{f"bg:{k}": v for k, v in bg.items()}, **{f"fg:{k}": v for k, v in fg.items()}})
    return MCResult(scenario=scenario, category_samples=pd.DataFrame(samples, columns=cats), input_samples=inputs, modules=modules)
