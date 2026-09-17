"""Loading of the human-editable data files (YAML/CSV) into an in-memory bundle.

All quantitative modelling data are kept in ``data/`` as plain-text files so that every number is
traceable (``source_id`` -> ``data/sources/sources.csv``). The SQLite database built by
``micp_lca.db`` is a derived, query-friendly copy of the same content.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .paths import data_dir

# --------------------------------------------------------------------------------------------
# helpers


def _read_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _float(x: Any, default: float | None = None) -> float | None:
    if x is None or x == "":
        return default
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(v) else v


# --------------------------------------------------------------------------------------------
# background processes


@dataclass
class BackgroundProcess:
    """A cradle-to-gate (or gate-to-grave) background dataset with per-unit impact factors."""

    process_id: str
    name: str
    unit: str
    category: str
    geography: str
    reference_year: int | None
    data_type: str                      # oekobaudat | literature | estimate | proxy | secondary_material
    source_id: str
    impacts: dict[str, dict[str, float]] = field(default_factory=dict)  # module -> {category_code: value/unit}
    gwp_min: float | None = None
    gwp_max: float | None = None
    pedigree: tuple[int, int, int, int, int] = (3, 3, 3, 3, 3)
    basic_uncertainty: float = 1.05
    ecoinvent_proxy: str = ""
    notes: str = ""
    other_categories_from: str | None = None   # process id whose EF profile is scaled to fill missing categories
    proxy_filled: set[str] = field(default_factory=set)   # categories filled from the proxy profile (approximation)

    def production_modules(self) -> list[str]:
        """Modules that represent the cradle-to-gate supply of the dataset's reference flow.

        ``A1-A3`` when declared (EPD-type datasets); otherwise the separately declared A1, A2, A3;
        for transport, energy and machine datasets the module in which they are declared
        (A4, A5 or B6). End-of-life modules (C1–C4), D and use-phase carbonation (B1) are never
        included and must be requested explicitly.
        """
        mods = set(self.impacts)
        if "A1-A3" in mods:
            return ["A1-A3"]
        sub = [m for m in ("A1", "A2", "A3") if m in mods]
        if sub:
            return sub
        return [m for m in ("A4", "A5", "B6") if m in mods]

    def factor(self, category: str, module: str | None = None) -> float:
        """Impact per declared unit for ``category`` (production modules summed when ``module`` is None)."""
        if module is not None:
            return self.impacts.get(module, {}).get(category, float("nan"))
        vals = [self.impacts[m][category] for m in self.production_modules() if category in self.impacts[m]]
        return sum(vals) if vals else float("nan")

    def eol_factor(self, category: str) -> float:
        """Sum of the end-of-life modules C1–C4 declared by the dataset (NaN if none)."""
        vals = [self.impacts[m][category] for m in ("C1", "C2", "C3", "C4") if m in self.impacts and category in self.impacts[m]]
        return sum(vals) if vals else float("nan")

    @property
    def modules(self) -> list[str]:
        return list(self.impacts.keys())

    @property
    def gwp(self) -> float:
        return self.factor("GWP-total")

    @property
    def gwp_any(self) -> float:
        """GWP over the production modules, or over all declared modules for pure end-of-life datasets."""
        g = self.factor("GWP-total")
        if math.isnan(g):
            vals = [m["GWP-total"] for m in self.impacts.values() if "GWP-total" in m]
            g = sum(vals) if vals else float("nan")
        return g


_CATEGORY_CODES = {"GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP", "EP-freshwater", "EP-marine",
                   "EP-terrestrial", "POCP", "ADP-minerals&metals", "ADP-fossil", "WDP", "PM", "IRP", "ETP-fw", "HTP-c",
                   "HTP-nc", "SQP"}


def _load_oekobaudat(bg_dir: Path) -> dict[str, BackgroundProcess]:
    obd = bg_dir / "oekobaudat"
    meta = {m["key"]: m for m in _read_csv(obd / "oekobaudat_datasets.csv")}
    values = _read_csv(obd / "oekobaudat_indicators.csv")
    by_key: dict[str, dict[str, dict[str, float]]] = {}
    for r in values:
        if r["kind"] != "lcia" or not r["code"]:
            continue
        by_key.setdefault(r["key"], {}).setdefault(r["module"], {})[r["code"]] = float(r["value_per_declared_unit"])
    # EN 15804 resource-use / waste indicators (exchanges) are kept too, keyed by their codes
    for r in values:
        if r["kind"] == "exchange" and r["code"]:
            by_key.setdefault(r["key"], {}).setdefault(r["module"], {})[r["code"]] = float(r["value_per_declared_unit"])
    procs: dict[str, BackgroundProcess] = {}
    for row in _read_csv(bg_dir / "background_processes_oekobaudat.csv"):
        key = row["obd_key"]
        if key not in by_key:
            continue
        cf = _float(row["conversion_factor"], 1.0) or 1.0
        wanted = [m.strip() for m in row["modules"].split(";") if m.strip()]
        impacts: dict[str, dict[str, float]] = {}
        for module, cats in by_key[key].items():
            if wanted and module not in wanted and not (module in ("C1", "C2", "C3", "C4", "D", "B1")):
                continue
            impacts[module] = {c: v * cf for c, v in cats.items()}
        m = meta[key]
        procs[row["process_id"]] = BackgroundProcess(
            process_id=row["process_id"], name=row["name"], unit=row["unit"], category=row["category"],
            geography=m.get("geography") or "DE", reference_year=int(m["reference_year"]) if m.get("reference_year") else None,
            data_type="oekobaudat", source_id="OBD2024II", impacts=impacts,
            pedigree=tuple(int(row[f"pedigree_{k}"]) for k in "RCTGF"),  # type: ignore[arg-type]
            basic_uncertainty=_float(row["basic_uncertainty"], 1.05) or 1.05,
            ecoinvent_proxy=row.get("ecoinvent_proxy", ""), notes=row.get("notes", ""),
        )
    # every other fetched dataset is registered automatically as ``obd_<key>``; datasets declared per
    # m3 / m2 / piece are converted to 1 kg when the mass per declared unit is known (density)
    mapped = {row["obd_key"] for row in _read_csv(bg_dir / "background_processes_oekobaudat.csv")}
    for key, m in meta.items():
        if key in mapped or key not in by_key:
            continue
        unit = m.get("declared_unit") or ""
        amount = _float(m.get("declared_amount"), 1.0) or 1.0
        mass = _float(m.get("mass_kg_per_declared_unit"))
        cf, out_unit = 1.0, unit
        if unit == "kg" and abs(amount - 1.0) > 1e-9:      # e.g. declared per 1000 kg (already normalised per kg by the fetch script)
            cf, out_unit = 1.0, "kg"
        elif unit in ("m3", "qm", "m2", "piece", "pcs") and mass and mass > 0:
            cf, out_unit = 1.0 / mass, "kg"
        cat = ("energy" if unit == "kWh" else "transport" if unit == "tkm" else "waste" if "landfill" in m["name"].lower()
               or "incineration" in m["name"].lower() else "material")
        procs[f"obd_{key}"] = BackgroundProcess(
            process_id=f"obd_{key}", name=f"{m['name']} [ÖKOBAUDAT {m.get('subtype', '')}]", unit=out_unit, category=cat,
            geography=m.get("geography") or "DE", reference_year=int(m["reference_year"]) if m.get("reference_year") else None,
            data_type="oekobaudat", source_id="OBD2024II",
            impacts={mod: {c: v * cf for c, v in cats.items()} for mod, cats in by_key[key].items()},
            pedigree=(1, 1, 1, 2, 2), basic_uncertainty=1.05, ecoinvent_proxy="", notes=m.get("comment", ""),
        )
    return procs


def _load_literature(bg_dir: Path) -> dict[str, BackgroundProcess]:
    procs: dict[str, BackgroundProcess] = {}
    for row in _read_csv(bg_dir / "background_processes_literature.csv"):
        gwp = _float(row["gwp_fossil"], 0.0) or 0.0
        impacts = {"A1-A3": {"GWP-total": gwp, "GWP-fossil": gwp, "GWP-biogenic": 0.0, "GWP-luluc": 0.0}}
        adp = _float(row.get("adp_fossil_MJ"))
        if adp is not None:
            impacts["A1-A3"]["ADP-fossil"] = adp
        # hook for licensed data: any extra column named like an impact-category code (e.g. "AP",
        # "EP-freshwater") is read as a native per-unit factor (see docs/07_using_ecoinvent_brightway.md)
        for col, val in row.items():
            if col in _CATEGORY_CODES and col not in impacts["A1-A3"] and _float(val) is not None:
                impacts["A1-A3"][col] = _float(val)  # type: ignore[assignment]
        procs[row["process_id"]] = BackgroundProcess(
            process_id=row["process_id"], name=row["name"], unit=row["unit"], category=row["category"],
            geography=row["geography"], reference_year=int(row["reference_year"]) if row.get("reference_year") else None,
            data_type=row["data_type"], source_id=row["source_id"], impacts=impacts,
            gwp_min=_float(row["gwp_min"]), gwp_max=_float(row["gwp_max"]),
            pedigree=tuple(int(row[f"pedigree_{k}"]) for k in "RCTGF"),  # type: ignore[arg-type]
            basic_uncertainty=_float(row["basic_uncertainty"], 1.05) or 1.05,
            ecoinvent_proxy=row.get("ecoinvent_proxy", ""), notes=row.get("notes", ""),
        )
        if row.get("profile_proxy"):
            procs[row["process_id"]].other_categories_from = row["profile_proxy"]
    return procs


def _load_agribalyse(bg_dir: Path) -> dict[str, BackgroundProcess]:
    """AGRIBALYSE 4 (EF 3.1) cradle-to-factory-gate profiles of agro-food products (proxies for media components)."""
    fn = bg_dir / "agribalyse_proxy_profiles.csv"
    procs: dict[str, BackgroundProcess] = {}
    if not fn.exists():
        return procs
    for row in _read_csv(fn):
        pid = row["process_id"]
        if pid not in procs:
            procs[pid] = BackgroundProcess(process_id=pid, name=f"{row['lci_name']} (AGRIBALYSE 4, agriculture + processing)",
                                           unit="kg", category="agro_proxy", geography="FR", reference_year=2025,
                                           data_type="agribalyse", source_id="AGRIBALYSE4", impacts={"A1-A3": {}},
                                           pedigree=(2, 2, 1, 3, 3), basic_uncertainty=1.05,
                                           ecoinvent_proxy="", notes=row["comment"])
        procs[pid].impacts["A1-A3"][row["category_code"]] = float(row["value_per_kg"])
    for p in procs.values():
        g = p.impacts["A1-A3"].get("GWP-total")
        if g is not None:   # the stage table has no fossil/biogenic split: attribute the total to fossil
            p.impacts["A1-A3"].setdefault("GWP-fossil", g)
            p.impacts["A1-A3"].setdefault("GWP-biogenic", 0.0)
            p.impacts["A1-A3"].setdefault("GWP-luluc", 0.0)
    return procs


# --------------------------------------------------------------------------------------------
# bundle


@dataclass
class DataBundle:
    chemicals: dict[str, dict[str, Any]]
    media: dict[str, dict[str, Any]]
    strains: dict[str, dict[str, Any]]
    materials: dict[str, dict[str, Any]]
    protocols: dict[str, dict[str, Any]]
    scaleup: dict[str, Any]
    scenarios: dict[str, Any]
    background: dict[str, BackgroundProcess]
    impact_categories: pd.DataFrame
    characterization_factors: pd.DataFrame
    sources: dict[str, dict[str, str]]
    experimental: pd.DataFrame
    root: Path
    prices: pd.DataFrame = field(default_factory=pd.DataFrame)             # indicative prices (data/economics/prices.csv)
    literature_results: pd.DataFrame = field(default_factory=pd.DataFrame) # published MICP LCA results (data/literature)
    _cf_full: pd.DataFrame | None = None

    # convenience -----------------------------------------------------------------------------
    @property
    def category_codes(self) -> list[str]:
        return list(self.impact_categories["code"])

    def category_unit(self, code: str) -> str:
        row = self.impact_categories.loc[self.impact_categories["code"] == code]
        return str(row["unit"].iloc[0]) if len(row) else ""

    def cf(self, flow_name: str, compartment: str, category: str, location: str = "GLO") -> float:
        """Characterisation factor of an elementary flow (EF 3.1); memoised."""
        key = (flow_name, compartment, category, location)
        cache = self.__dict__.setdefault("_cf_cache", {})
        if key not in cache:
            cache[key] = self._cf_uncached(flow_name, compartment, category, location)
        return cache[key]

    def _cf_uncached(self, flow_name: str, compartment: str, category: str, location: str = "GLO") -> float:
        """Characterisation factor of an elementary flow (EF 3.1).

        Looks up the curated subset first and falls back to the complete EF 3.1 table
        (``ef31_characterization_factors_full.csv.gz``, unspecified sub-compartments) for any other
        flow. ``location`` selects country-specific factors (e.g. ``CZ``) when the method provides
        them (acidification, eutrophication, water use); otherwise the site-generic factor is used.
        """
        df = self.characterization_factors
        sel = df[(df["flow_name"] == flow_name) & (df["compartment"] == compartment) & (df["category_code"] == category)]
        if sel.empty or (location != "GLO" and not (sel["location"] == location).any()):
            full = self.cf_full()
            if not full.empty:
                unspecified = {"air": "Emissions to air, unspecified", "water": "Emissions to water, unspecified",
                               "freshwater": "Emissions to fresh water", "soil": "Emissions to non-agricultural soil"}
                comp = "water" if compartment == "freshwater" else compartment
                cand = full[(full["flow_name_lc"] == flow_name.lower()) & (full["compartment"] == comp) & (full["category_code"] == category)]
                if compartment in unspecified:
                    sub = cand[cand["ef31_class2"] == unspecified[compartment]]
                    cand = sub if len(sub) else cand
                if sel.empty or (cand["location"] == location).any():
                    sel = cand
        if location != "GLO" and (sel["location"] == location).any():
            sel = sel[sel["location"] == location]
        else:
            sel = sel[sel["location"] == "GLO"]
        return float(sel["cf"].iloc[0]) if len(sel) else 0.0

    def cf_full(self) -> pd.DataFrame:
        """The complete location-independent EF 3.1 characterisation-factor table (lazy-loaded, gzip CSV)."""
        if self._cf_full is None:
            fn = self.root / "lcia" / "ef31_characterization_factors_full.csv.gz"
            self._cf_full = pd.read_csv(fn, compression="gzip") if fn.exists() else pd.DataFrame()
            if not self._cf_full.empty:
                self._cf_full["flow_name_lc"] = self._cf_full["flow_name"].str.lower()
        return self._cf_full

    def cf_lookup(self, flow_name: str, compartment: str, category: str) -> float:
        """Characterisation factor from the full EF 3.1 table (any elementary flow; unspecified sub-compartment)."""
        df = self.cf_full()
        if df.empty:
            return self.cf(flow_name, compartment, category)
        sel = df[(df["flow_name_lc"] == flow_name.lower()) & (df["compartment"] == compartment) & (df["category_code"] == category)]
        return float(sel["cf"].iloc[0]) if len(sel) else 0.0

    def scenario_config(self, name: str) -> dict[str, Any]:
        """Scenario dictionary merged with the defaults."""
        if name not in self.scenarios.get("scenarios", {}):
            raise KeyError(f"Unknown scenario '{name}'. Available: {sorted(self.scenarios.get('scenarios', {}))}")
        cfg = dict(self.scenarios.get("defaults", {}))
        cfg.update(self.scenarios["scenarios"][name])
        cfg["name"] = name
        return cfg


def _merge_user(base: dict[str, Any], user_dir: Path, name: str) -> dict[str, Any]:
    """Merge ``data/user/<name>.yaml`` (user-defined entries) into a foreground table."""
    fn = user_dir / f"{name}.yaml"
    if fn.exists():
        extra = _read_yaml(fn)
        if name == "scenarios":
            base = dict(base)
            base["scenarios"] = {**base.get("scenarios", {}), **(extra.get("scenarios") or {})}
            base["benchmarks"] = {**base.get("benchmarks", {}), **(extra.get("benchmarks") or {})}
            return base
        return {**base, **extra}
    return base


def _load_user_background(user_dir: Path, template_columns: list[str]) -> dict[str, BackgroundProcess]:
    """User-defined background factors (data/user/background_processes.csv, same columns as the literature table)."""
    fn = user_dir / "background_processes.csv"
    if not fn.exists():
        return {}
    tmp = user_dir / "_tmp_literature"
    tmp.mkdir(exist_ok=True)
    (tmp / "background_processes_literature.csv").write_text(fn.read_text(encoding="utf-8"), encoding="utf-8")
    procs = _load_literature(tmp)
    for p in procs.values():
        p.data_type = p.data_type or "user"
        p.notes = "[user-defined] " + (p.notes or "")
    return procs


def load_data(root: Path | str | None = None) -> DataBundle:
    """Load every data file under ``data/`` (or ``root``), merging user additions from ``data/user/``."""
    root = Path(root) if root else data_dir()
    fg = root / "foreground"
    bg = root / "background"
    user = root / "user"
    background = {}
    background.update(_load_oekobaudat(bg))
    background.update(_load_agribalyse(bg))
    background.update(_load_literature(bg))
    if user.exists():
        background.update(_load_user_background(user, []))
    # fill missing impact categories from proxy profiles scaled by the GWP ratio (documented approximation;
    # the affected categories are flagged in ``proxy_filled`` and reported as such in the coverage statistics)
    for p in background.values():
        if p.other_categories_from and p.other_categories_from in background and p.gwp and not math.isnan(p.gwp):
            proxy = background[p.other_categories_from]
            pg = proxy.gwp
            if not pg or math.isnan(pg):
                continue
            ratio = p.gwp / pg
            target = p.impacts.setdefault("A1-A3", {})
            for c, v in proxy.impacts.get("A1-A3", proxy.impacts.get("B6", proxy.impacts.get("A4", {}))).items():
                if c not in target and c not in ("GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc"):
                    target[c] = v * ratio
                    p.proxy_filled.add(c)
    impact_categories = pd.read_csv(root / "lcia" / "ef31_impact_categories.csv")
    cfs = pd.read_csv(root / "lcia" / "ef31_characterization_factors.csv")
    sources = {r["source_id"]: r for r in _read_csv(root / "sources" / "sources.csv")}
    experimental = pd.read_csv(root / "experimental" / "experimental_results.csv")
    tables = {name: _read_yaml(fg / f"{name}.yaml") for name in ("chemicals", "media", "strains", "materials", "protocols", "scaleup", "scenarios")}
    if user.exists():
        for name in ("chemicals", "media", "strains", "materials", "protocols", "scenarios"):
            tables[name] = _merge_user(tables[name], user, name)
        if (user / "sources.csv").exists():
            sources.update({r["source_id"]: r for r in _read_csv(user / "sources.csv")})
    prices = pd.read_csv(root / "economics" / "prices.csv") if (root / "economics" / "prices.csv").exists() else pd.DataFrame()
    if (user / "prices.csv").exists():   # user prices override the indicative ones (matched by process_id)
        up = pd.read_csv(user / "prices.csv")
        prices = pd.concat([prices[~prices["process_id"].isin(up["process_id"])], up], ignore_index=True) if not prices.empty else up
    literature = (pd.read_csv(root / "literature" / "micp_lca_literature_results.csv")
                  if (root / "literature" / "micp_lca_literature_results.csv").exists() else pd.DataFrame())
    return DataBundle(
        chemicals=tables["chemicals"], media=tables["media"], strains=tables["strains"], materials=tables["materials"],
        protocols=tables["protocols"], scaleup=tables["scaleup"], scenarios=tables["scenarios"],
        background=background, impact_categories=impact_categories, characterization_factors=cfs,
        sources=sources, experimental=experimental, root=root, prices=prices, literature_results=literature,
    )
