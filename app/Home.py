"""MICP-LCA application – home page.  Run with:  streamlit run app/Home.py"""
from __future__ import annotations

import streamlit as st

from utils import get_data, run, CORE

st.set_page_config(page_title="MICP LCA", page_icon="🧫", layout="wide")
data = get_data()

st.title("MICP-LCA — life-cycle assessment of biocemented blocks from waste concrete fines and demolition residues")
st.markdown(
    """
An interactive, database-backed **LCA workbench** for microbially induced carbonate precipitation (MICP)
recycling of waste concrete fines and sub-sieve (0–4 mm) demolition residues. It reproduces the published laboratory
protocols of the CTU Prague / UCT Prague group, scales them to industrial conditions and assesses
them with the **EF 3.1** method in the modular structure of **EN 15804+A2** (ISO 14040/14044).

Use the pages in the sidebar:

| Page | What you can do |
|---|---|
| **Scenario builder** | pre-defined compositions (recipe cards of all protocols) or your own composition (material, organism and pathway, media, reagents, dosing, curing); technology and system settings; impacts, contributions, mass balances and cost; **parametric analysis** of one variable between limits; **PDF report** with figures, narrative and references; save as a user scenario |
| **Compare** | compare scenarios with each other and with benchmark products (AAC, bricks, concrete blocks, the WCF–OPC block) per kg, per m³ or per m³·MPa; system-expansion comparison with the status quo |
| **Uncertainty** | one-at-a-time tornado analysis and Monte Carlo propagation with global sensitivity ranking |
| **Database** | browse and search all background datasets (ÖKOBAUDAT, AGRIBALYSE, literature), EF 3.1 characterisation factors, chemicals, media, strains, materials, protocols, experimental results, prices and sources; export CSV |
| **Data editor** | add your own background factors, protocols and scenarios (stored in `data/user/`) |
| **Literature** | published MICP LCA results side by side with the model (per kg CaCO₃) |
| **Cost** | indicative cost per functional unit (bulk vs laboratory-grade inputs) |
    """
)

st.subheader("Database at a glance")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Background datasets", len(data.background))
c2.metric("Chemicals / media components", len([k for k in data.chemicals if not k.startswith("_")]))
c3.metric("Protocols", len(data.protocols))
c4.metric("Scenarios / benchmarks", f"{len(data.scenarios['scenarios'])} / {len(data.scenarios['benchmarks'])}")
c5.metric("Sources", len(data.sources))

st.subheader("Baseline snapshot (kg CO₂e per kg of dry product, cradle-to-gate A1–A3)")
snap = {
    "Ureolytic 90-d lab protocol (S. pasteurii)": "SP_lab_protocol_90d",
    "Ureolytic, stoichiometric + recirculation + NH₃ stripping": "SP_optimised_recirculation",
    "Non-ureolytic Ca-lactate (S. cohnii), 30 d": "BC_lactate_30d",
    "Gypsum-promoted single dose (prototype recipe)": "GYP_WCFC_single_dose",
    "Prototype recipe with feather-hydrolysate medium": "GYP_WCFC_single_dose_feather",
    "Abiotic control (gypsum + hydration only)": "ABIOTIC_WCFC_gypsum",
}
cols = st.columns(len(snap))
for col, (label, name) in zip(cols, snap.items()):
    try:
        res = run(name)
        col.metric(label, f"{res.gwp():.3f}")
    except Exception as exc:  # noqa: BLE001
        col.error(f"{name}: {exc}")
st.caption("Benchmarks per kg: AAC 0.40–0.48 · WCF–OPC foamed block 0.31 · clay brick 0.20 · sand-lime brick 0.13 · concrete block 0.11 · adobe 0.08. "
           "Full details: docs/08_results_baseline.md.")
st.caption("Scenarios and data saved in the application go to `data/user/` of the running instance; on a hosted instance they are "
           "not persistent, so download the reports, CSV exports and scenario files you want to keep.")

with st.expander("Method summary"):
    st.markdown(
        """
* **Functional units**: 1 kg or 1 m³ of dry product, 1 m³·MPa (strength-normalised), 1 kg of precipitated CaCO₃, 1 kg of fines processed.
* **System boundary**: A1 (waste-fines processing, reagents, media, water) – A2 (transport) – A3 (cultivation, casting, dosing, curing, drying, effluent treatment, direct emissions, carbonation uptake) – C1–C4 (demolition, transport, landfill or recycling) – D (optional credits).
* **Chemistry**: limiting-reagent CaCO₃ yield checked against measured XRD gains; urea carbon is fossil, lactate carbon is biogenic; NH₃/NH₄⁺/N₂O fate; chloride and residual organics in the effluent.
* **Impact assessment**: EF 3.1 (official characterisation factors, optional Czech site-specific factors); EN 15804+A2 biogenic-carbon convention switchable.
* **Data quality**: every factor carries a source, pedigree scores and a range; coverage of each impact category (native vs proxy) is reported with every result.
        """
    )
