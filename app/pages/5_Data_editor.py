"""Data editor: add user-defined background factors, sources, chemicals, media, protocols, scenarios and prices.

Everything is written to ``data/user/`` (never to the curated files) and merged at load time.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
import yaml

from utils import get_data, reload_data

st.set_page_config(page_title="Data editor", page_icon="✏️", layout="wide")
data = get_data()
USER = data.root / "user"          # honours MICP_LCA_DATA (see micp_lca.paths.data_dir)
USER.mkdir(exist_ok=True)
st.title("Data editor (user additions)")
st.caption(f"Additions are stored in `{USER}` and merged into the database at load time; the curated files are never modified. "
           "Entries with the same id override the curated ones.")

LIT_COLUMNS = ["process_id", "name", "unit", "category", "geography", "reference_year", "data_type", "source_id", "gwp_fossil", "gwp_min",
               "gwp_max", "adp_fossil_MJ", "ecoinvent_proxy", "profile_proxy", "pedigree_R", "pedigree_C", "pedigree_T", "pedigree_G",
               "pedigree_F", "basic_uncertainty", "notes"]
EXTRA_CATS = ["GWP-biogenic", "GWP-luluc", "ODP", "AP", "EP-freshwater", "EP-marine", "EP-terrestrial", "POCP", "ADP-minerals&metals",
              "ADP-fossil", "WDP", "PM", "IRP", "ETP-fw", "HTP-c", "HTP-nc", "SQP"]


# ------------------------------------------------------------------------------------------ helpers
def _read_user_yaml(name: str) -> dict:
    fn = USER / f"{name}.yaml"
    return (yaml.safe_load(fn.read_text(encoding="utf-8")) or {}) if fn.exists() else {}


def _write_user_yaml(name: str, obj: dict) -> None:
    (USER / f"{name}.yaml").write_text(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")


def _append_csv(name: str, row: dict, columns: list[str]) -> None:
    fn = USER / f"{name}.csv"
    cols = list(columns) + [c for c in row if c not in columns]
    if fn.exists():
        df = pd.read_csv(fn)
        for c in cols:
            if c not in df.columns:
                df[c] = None
        df = df[df["process_id" if "process_id" in df.columns else "source_id"] != row.get("process_id", row.get("source_id"))]
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    else:
        df = pd.DataFrame([row], columns=cols)
    df.to_csv(fn, index=False)


def _remove_from_csv(name: str, key_col: str, key: str) -> None:
    fn = USER / f"{name}.csv"
    if fn.exists():
        df = pd.read_csv(fn)
        df[df[key_col] != key].to_csv(fn, index=False)


def _saved(msg: str) -> None:
    reload_data()
    st.success(msg + " Database reloaded.")


tabs = st.tabs(["Background factor", "Source", "Chemical", "Medium", "Protocol", "Scenario", "Price", "Manage user data"])

# ------------------------------------------------------------------------------------------ background factor
with tabs[0]:
    st.markdown("Add a cradle-to-gate factor for a chemical, energy carrier, material or service (e.g. an ecoinvent result you are licensed to use, "
                "an EPD, or a supplier value). Only the GWP is mandatory; other EF 3.1 indicators can be given natively or filled from a **profile proxy**.")
    with st.form("bg_form"):
        c1, c2, c3 = st.columns(3)
        pid = c1.text_input("process_id (snake_case, unique)", "")
        name = c2.text_input("Name", "")
        unit = c3.selectbox("Unit", ["kg", "kWh", "MJ", "m3", "tkm", "L", "item"])
        c1, c2, c3, c4 = st.columns(4)
        category = c1.selectbox("Category", ["chemical", "medium_component", "energy", "material", "transport", "water", "waste", "credit", "benchmark"])
        geo = c2.text_input("Geography", "RER")
        year = c3.number_input("Reference year", 1990, 2035, 2024)
        dtype = c4.selectbox("Data type", ["user", "literature", "estimate", "proxy", "ecoinvent", "epd"])
        c1, c2, c3, c4 = st.columns(4)
        gwp = c1.number_input("GWP-fossil (kg CO2e per unit)", value=1.0, format="%.5g")
        gmin = c2.number_input("GWP min (0 = none)", value=0.0, format="%.5g")
        gmax = c3.number_input("GWP max (0 = none)", value=0.0, format="%.5g")
        adp = c4.number_input("ADP-fossil (MJ per unit, 0 = none)", value=0.0, format="%.5g")
        src = st.selectbox("Source id", sorted(data.sources), index=sorted(data.sources).index("INDICATIVE") if "INDICATIVE" in data.sources else 0)
        c1, c2 = st.columns(2)
        eco = c1.text_input("ecoinvent activity name (documentation only)", "")
        proxy_opts = [""] + sorted(k for k, p in data.background.items() if p.impacts.get("A1-A3") and len(p.impacts["A1-A3"]) > 6)
        prof = c2.selectbox("Profile proxy for the other EF categories (scaled by GWP ratio)", proxy_opts)
        st.markdown("Pedigree scores (1 = best … 5 = worst): reliability, completeness, temporal, geographical, further technological correlation")
        p1, p2, p3, p4, p5, p6 = st.columns(6)
        ped = [p1.slider("R", 1, 5, 3), p2.slider("C", 1, 5, 3), p3.slider("T", 1, 5, 3), p4.slider("G", 1, 5, 3), p5.slider("F", 1, 5, 3)]
        bu = p6.number_input("Basic uncertainty", 1.0, 3.0, 1.05, 0.01)
        with st.expander("Native values for other EF 3.1 categories (optional; per unit)"):
            native = {}
            cols = st.columns(4)
            for i, cat in enumerate(EXTRA_CATS):
                v = cols[i % 4].text_input(f"{cat} [{data.category_unit(cat)}]", "", key=f"nat_{cat}")
                if v.strip():
                    native[cat] = v.strip()
        notes = st.text_area("Notes / documentation", "")
        ok = st.form_submit_button("Save background factor", type="primary")
    if ok:
        errors = []
        if not pid or not pid.replace("_", "").isalnum():
            errors.append("process_id must be a non-empty snake_case identifier")
        if not name:
            errors.append("name is required")
        if gwp <= 0 and category not in ("credit", "waste"):
            errors.append("GWP must be positive (use category 'credit' for negative factors)")
        for cat, v in native.items():
            try:
                float(v)
            except ValueError:
                errors.append(f"{cat}: '{v}' is not a number")
        if errors:
            st.error("; ".join(errors))
        else:
            row = {"process_id": pid, "name": name, "unit": unit, "category": category, "geography": geo, "reference_year": int(year),
                   "data_type": dtype, "source_id": src, "gwp_fossil": gwp, "gwp_min": gmin or "", "gwp_max": gmax or "",
                   "adp_fossil_MJ": adp or "", "ecoinvent_proxy": eco, "profile_proxy": prof, "pedigree_R": ped[0], "pedigree_C": ped[1],
                   "pedigree_T": ped[2], "pedigree_G": ped[3], "pedigree_F": ped[4], "basic_uncertainty": bu, "notes": notes}
            row.update({k: float(v) for k, v in native.items()})
            _append_csv("background_processes", row, LIT_COLUMNS)
            _saved(f"Background factor '{pid}' saved to data/user/background_processes.csv.")

# ------------------------------------------------------------------------------------------ source
with tabs[1]:
    with st.form("src_form"):
        c1, c2 = st.columns([1, 3])
        sid = c1.text_input("source_id (UPPERCASE key, e.g. SMITH2025)", "")
        stype = c1.selectbox("Type", ["paper", "database", "report", "standard", "supplier", "web", "book", "thesis"])
        cit = c2.text_input("Citation", "")
        doi = c2.text_input("DOI or URL", "")
        notes = c2.text_input("Notes", "")
        ok = st.form_submit_button("Save source", type="primary")
    if ok:
        if not sid or not cit:
            st.error("source_id and citation are required")
        else:
            _append_csv("sources", {"source_id": sid, "type": stype, "citation": cit, "doi_or_url": doi, "notes": notes},
                        ["source_id", "type", "citation", "doi_or_url", "notes"])
            _saved(f"Source '{sid}' saved to data/user/sources.csv.")

# ------------------------------------------------------------------------------------------ chemical
with tabs[2]:
    st.markdown("A chemical links a **medium component or reagent** to a background factor and carries the stoichiometric information used by the mass balance.")
    with st.form("chem_form"):
        c1, c2, c3 = st.columns(3)
        cid = c1.text_input("id (snake_case)", "")
        cname = c2.text_input("Name", "")
        formula = c3.text_input("Formula (optional)", "")
        c1, c2, c3, c4 = st.columns(4)
        mm = c1.number_input("Molar mass (g/mol, 0 = n/a)", 0.0, 2000.0, 0.0, 0.01)
        cc = c2.number_input("Carbon content (kg C / kg)", 0.0, 1.0, 0.0, 0.001, format="%.4f")
        corig = c3.selectbox("Carbon origin", ["fossil", "biogenic", "none"])
        nc = c4.number_input("Nitrogen content (kg N / kg)", 0.0, 1.0, 0.0, 0.001, format="%.4f")
        bp = st.selectbox("Background process", sorted(data.background))
        notes = st.text_area("Notes", "", key="chem_notes")
        ok = st.form_submit_button("Save chemical", type="primary")
    if ok:
        if not cid or not cname:
            st.error("id and name are required")
        else:
            entry = {"name": cname, "background_process": bp}
            if formula:
                entry["formula"] = formula
            if mm:
                entry["molar_mass"] = mm
            if cc:
                entry["carbon_content"] = cc
                entry["carbon_origin"] = corig
            if nc:
                entry["nitrogen_content"] = nc
            if notes:
                entry["notes"] = notes
            obj = _read_user_yaml("chemicals")
            obj[cid] = entry
            _write_user_yaml("chemicals", obj)
            _saved(f"Chemical '{cid}' saved to data/user/chemicals.yaml.")

# ------------------------------------------------------------------------------------------ medium
with tabs[3]:
    st.markdown("A cultivation or biocementation base medium is a list of components in g/L. Components must exist as chemicals.")
    chem_ids = sorted(k for k in data.chemicals if not k.startswith("_"))
    with st.form("med_form"):
        c1, c2 = st.columns([1, 2])
        mid = c1.text_input("id (snake_case)", "")
        mname = c2.text_input("Name", "")
        comps = st.multiselect("Components", chem_ids, default=[])
        amounts = {}
        cols = st.columns(4)
        for i, c in enumerate(comps):
            amounts[c] = cols[i % 4].number_input(f"{c} (g/L)", 0.0, 500.0, 1.0, 0.1, key=f"med_{c}")
        c1, c2 = st.columns(2)
        ster = c1.selectbox("Sterilisation", ["autoclave", "filter", "none"])
        msrc = c2.selectbox("Source id", sorted(data.sources), key="med_src")
        ok = st.form_submit_button("Save medium", type="primary")
    if ok:
        if not mid or not mname or not comps:
            st.error("id, name and at least one component are required")
        else:
            obj = _read_user_yaml("media")
            obj[mid] = {"name": mname, "source_id": msrc, "components": {k: float(v) for k, v in amounts.items()}, "sterilisation": ster}
            _write_user_yaml("media", obj)
            _saved(f"Medium '{mid}' saved to data/user/media.yaml.")

# ------------------------------------------------------------------------------------------ protocol
with tabs[4]:
    st.markdown("Start from an existing protocol, edit the YAML and save it under a new id. The structure is documented in `docs/09_database_schema.md`.")
    base = st.selectbox("Template protocol", list(data.protocols))
    new_id = st.text_input("New protocol id (snake_case)", f"{base}_custom")
    txt = st.text_area("Protocol YAML", yaml.safe_dump(data.protocols[base], sort_keys=False, allow_unicode=True, width=120), height=520)
    if st.button("Validate and save protocol", type="primary"):
        try:
            obj = yaml.safe_load(txt)
            assert isinstance(obj, dict), "protocol must be a mapping"
            for key in ("strain", "material", "solids_g", "suspension", "biocementation_solution", "incubation"):
                assert key in obj, f"missing key '{key}'"
            assert obj["strain"] in data.strains, f"unknown strain '{obj['strain']}'"
            assert obj["material"] in data.materials, f"unknown material '{obj['material']}'"
            bs = obj["biocementation_solution"]
            if bs.get("base_medium"):
                assert bs["base_medium"] in data.media, f"unknown base medium '{bs['base_medium']}'"
            for cid in (bs.get("supplements") or {}):
                assert cid in data.chemicals, f"unknown supplement chemical '{cid}'"
            assert new_id and new_id.replace("_", "").isalnum(), "invalid protocol id"
        except Exception as exc:  # noqa: BLE001
            st.error(f"Validation failed: {exc}")
        else:
            user = _read_user_yaml("protocols")
            user[new_id] = obj
            _write_user_yaml("protocols", user)
            # smoke-test the protocol through the model
            try:
                from micp_lca.lcia import run_scenario
                reload_data()
                d2 = get_data()
                res = run_scenario(list(d2.scenarios["scenarios"])[0], d2, overrides={"protocol": new_id})
                st.success(f"Protocol '{new_id}' saved to data/user/protocols.yaml and evaluated: GWP A1–A3 = {res.gwp():.3g} kg CO2e/kg. Database reloaded.")
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Protocol saved, but a test run failed: {exc}")

# ------------------------------------------------------------------------------------------ scenario
with tabs[5]:
    st.markdown("A scenario selects a protocol and the process/system assumptions. (The Scenario builder page can also save scenarios with detailed overrides.)")
    elec_opts = [k for k, p in data.background.items() if p.unit == "kWh" and p.category == "energy" and "heat" not in k]
    with st.form("scen_form"):
        c1, c2 = st.columns([1, 2])
        sid = c1.text_input("Scenario id", "MY_SCENARIO")
        desc = c2.text_input("Description", "")
        c1, c2, c3, c4 = st.columns(4)
        proto = c1.selectbox("Protocol", list(data.protocols))
        mat = c2.selectbox("Material (blank = protocol default)", [""] + list(data.materials))
        scale = c3.selectbox("Energy model", ["industrial", "lab"])
        elec = c4.selectbox("Electricity", elec_opts)
        c1, c2, c3, c4 = st.columns(4)
        eff = c1.selectbox("Effluent N treatment", ["none", "ammonia_stripping", "struvite"])
        eol = c2.selectbox("End of life", ["landfill", "recycling"])
        carbon = c3.selectbox("Biogenic carbon", ["EF31", "EN15804A2"])
        carbn = c4.slider("Carbonation uptake fraction", 0.0, 1.0, 0.7, 0.05)
        c1, c2, c3 = st.columns(3)
        modd = c1.checkbox("Module D credits")
        abiotic = c2.checkbox("Abiotic control")
        sitecf = c3.checkbox("Czech site-specific CFs")
        c1, c2, c3 = st.columns(3)
        urea_ratio = c1.number_input("Urea:Ca molar ratio (0 = protocol)", 0.0, 20.0, 0.0, 0.1)
        recirc = c2.slider("Solution recirculation fraction", 0.0, 0.9, 0.0, 0.05)
        nbf = c3.slider("Nutrient-broth strength factor", 0.0, 3.0, 1.0, 0.1)
        fu = st.selectbox("Default functional unit", ["kg_product", "m3_product", "m3_MPa", "kg_caco3_precipitated", "kg_solids"])
        ok = st.form_submit_button("Save scenario", type="primary")
    if ok:
        if not sid:
            st.error("scenario id is required")
        else:
            entry = {"description": desc, "protocol": proto, "scale": scale, "electricity": elec, "effluent_treatment": eff, "eol": eol,
                     "carbon_accounting": carbon, "carbonation_uptake_fraction": carbn, "module_d": modd, "abiotic": abiotic,
                     "site_specific_cf": sitecf, "functional_unit": fu}
            if mat:
                entry["material"] = mat
            ro = {k: v for k, v in {"urea_to_ca_molar_ratio": urea_ratio or None, "solution_recirculation_fraction": recirc or None,
                                    "nutrient_broth_factor": nbf if nbf != 1.0 else None}.items() if v is not None}
            if ro:
                entry["reagent_optimisation"] = ro
            user = _read_user_yaml("scenarios")
            user.setdefault("scenarios", {})[sid] = entry
            _write_user_yaml("scenarios", user)
            _saved(f"Scenario '{sid}' saved to data/user/scenarios.yaml.")

# ------------------------------------------------------------------------------------------ price
with tabs[6]:
    st.markdown("Override an indicative price with a supplier quotation (EUR per unit of the background process).")
    with st.form("price_form"):
        c1, c2 = st.columns([2, 1])
        ppid = c1.selectbox("Background process", sorted(data.background), format_func=lambda k: f"{k} [{data.background[k].unit}]")
        cy = c2.number_input("Currency year", 2000, 2035, 2025)
        c1, c2, c3, c4 = st.columns(4)
        pb = c1.number_input("Bulk price (EUR/unit)", 0.0, 1e6, 1.0, format="%.4g")
        pbmin = c2.number_input("Bulk min", 0.0, 1e6, 0.0, format="%.4g")
        pbmax = c3.number_input("Bulk max", 0.0, 1e6, 0.0, format="%.4g")
        pl = c4.number_input("Laboratory-grade price (EUR/unit)", 0.0, 1e6, 1.0, format="%.4g")
        pnotes = st.text_input("Notes (supplier, date)", "")
        ok = st.form_submit_button("Save price", type="primary")
    if ok:
        _append_csv("prices", {"process_id": ppid, "unit": data.background[ppid].unit, "price_bulk_eur": pb, "price_bulk_min": pbmin or "",
                               "price_bulk_max": pbmax or "", "price_lab_eur": pl, "currency_year": int(cy), "source_id": "USER", "notes": pnotes},
                    ["process_id", "unit", "price_bulk_eur", "price_bulk_min", "price_bulk_max", "price_lab_eur", "currency_year", "source_id", "notes"])
        _saved(f"Price for '{ppid}' saved to data/user/prices.csv.")

# ------------------------------------------------------------------------------------------ manage
with tabs[7]:
    st.markdown("Contents of `data/user/`. Remove entries you no longer need; the curated database is unaffected.")
    files = sorted(f for f in USER.iterdir() if f.suffix in (".csv", ".yaml"))
    if not files:
        st.info("No user data yet.")
    for f in files:
        with st.expander(f.name, expanded=False):
            if f.suffix == ".csv":
                df = pd.read_csv(f)
                st.dataframe(df, width="stretch", hide_index=True)
                key_col = "process_id" if "process_id" in df.columns else df.columns[0]
                rm = st.selectbox("Remove entry", [""] + list(df[key_col].astype(str)), key=f"rm_{f.name}")
                if rm and st.button(f"Remove '{rm}' from {f.name}", key=f"rmb_{f.name}"):
                    _remove_from_csv(f.stem, key_col, rm)
                    _saved(f"Removed '{rm}'.")
            else:
                obj = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
                st.code(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=120), language="yaml")
                if f.stem == "scenarios":
                    keys = list((obj.get("scenarios") or {}).keys())
                else:
                    keys = list(obj.keys())
                rm = st.selectbox("Remove entry", [""] + keys, key=f"rmy_{f.name}")
                if rm and st.button(f"Remove '{rm}' from {f.name}", key=f"rmyb_{f.name}"):
                    if f.stem == "scenarios":
                        obj["scenarios"].pop(rm, None)
                    else:
                        obj.pop(rm, None)
                    _write_user_yaml(f.stem, obj)
                    _saved(f"Removed '{rm}'.")
    if files and st.button("Reload database from disk"):
        _saved("Reloaded.")
