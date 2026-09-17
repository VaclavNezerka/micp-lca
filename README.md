# micp-lca — life-cycle assessment of MICP-based recycling of waste concrete fines and sub-sieve demolition residues

Database and Python toolkit for the **ex-ante life-cycle assessment (LCA)** of biocemented blocks
made from waste concrete fines (WCF) and sub-sieve (0–4 mm) heterogeneous demolition residues by **microbially
induced carbonate precipitation (MICP)** — the technology developed in the papers in `papers/`
(CTU Prague / UCT Prague: Nežerka, Holeček, Kliková, Stiborová, Ottová et al., 2023–2026).

The model follows **ISO 14040/14044** and the modular structure and indicator set of
**EN 15804+A2** (Environmental Footprint 3.1), reproduces every published laboratory protocol
one-to-one, scales it to industrial conditions with a transparent engineering model (Piccinno et al.
2016), and benchmarks the results against conventional masonry products and the group's own
WCF–OPC foamed block (Nežerka et al. 2023).

**Try it online:** the application runs on Streamlit Community Cloud at **[APP-URL-TO-BE-INSERTED](https://APP-URL-TO-BE-INSERTED)**
(a hosted instance sleeps after a few days without visits and wakes on the next visit; data saved in it are not persistent,
so download the reports, CSVs and scenario files you want to keep).

```
streamlit run app/Home.py                  # interactive application (scenario builder, comparison, uncertainty, database, editor)
micp-lca run GYP_WCFC_single_dose          # prototype recipe: S. cohnii + 10 % waste gypsum, single dose
micp-lca run-all --fu m3_product           # all scenarios vs benchmarks per m3
micp-lca sensitivity SP_lab_protocol_90d   # tornado of the 90-day ureolytic protocol
micp-lca monte-carlo BC_lactate_30d -n 1000
micp-lca status-quo GYP_WCFC_single_dose   # vs "AAC block + landfilling the fines"
micp-lca parameters GYP_WCFC_single_dose   # parameters that can be varied (recipe, cultivation, system, scale-up)
micp-lca sweep GYP_WCFC_single_dose -p protocol:biocementation_solution.dose_mL --from 1 --to 20 --steps 11
micp-lca report GYP_WCFC_single_dose -p reagent:nutrient_broth_factor --mc 500 --compare BC_lactate_30d   # PDF report
micp-lca build-db && micp-lca sql "SELECT process_id, gwp_min, gwp_max FROM background_processes"
```

## Repository layout

| Path | Content |
|---|---|
| `papers/` | the eight source papers (PDF; not redistributed in the public repository, see `data/sources/sources.csv` for the citations) |
| `app/` | **interactive Streamlit application** (`streamlit run app/Home.py`): scenario builder, comparison with benchmarks, tornado/Monte Carlo uncertainty, database browser, data editor, literature cross-check, indicative cost — see `docs/11_application.md` |
| `data/foreground/` | **the technology database**: `chemicals.yaml` (48 reagents/media components: stoichiometry, carbon origin, N content), `media.yaml` (20 media: TSB, LB, NB, malt extract, feather hydrolysates, NH4-YE, corn steep liquor, lactose mother liquor, manure effluent, BG-11, denitrification medium), `strains.yaml` (9 organisms/catalysts: ureolytic, organic-acid, fungal, EICP, denitrifying, acetate-oxidising, cyanobacterial), `materials.yaml` (WCF-G/H/C, HM1, HM2, waste gypsum; processing chains), `protocols.yaml` (23 protocols: 18 from the papers + 5 literature pathways), `scaleup.yaml` (lab ↔ industrial energy/effluent parameters with ranges), `scenarios.yaml` (29 assessment scenarios + 8 benchmarks) |
| `data/background/` | **background LCI factors** (161 processes): 107 ÖKOBAUDAT EN 15804+A2/EF 3.1 datasets (cement, lime, aggregates, bricks, AAC, chemicals, energy, transport, waste; all auto-registered, raw JSON cached), 7 AGRIBALYSE 4 EF 3.1 proxy profiles, 47 literature/estimate factors for chemicals, media components and energy with pedigree scores, ranges and ecoinvent proxy names |
| `data/lcia/` | official **EF 3.1** impact categories and characterisation factors: curated subset for the foreground flows (incl. CZ site-specific factors) + the complete table (140 474 factors, GLO + CZ) |
| `data/experimental/` | 81 measured results from the papers (CaCO3 content, porosity, stiffness, strength, AFt) |
| `data/literature/` | 27 published MICP LCA and cost results (Porter 2021, Deng 2021, Alotaibi 2022, Nežerka 2023, van Paassen 2010, Raymond 2025 …) for cross-checks |
| `data/economics/` | 61 indicative prices (bulk vs laboratory grade) for the cost module |
| `data/user/` | your own factors, protocols, scenarios, prices (merged at load time; written by the application) |
| `data/sources/sources.csv` | 49 traceable sources (papers, standards, databases, reports) |
| `data/db/micp_lca.sqlite` | derived SQLite snapshot of everything above + stored results (`micp-lca build-db`) |
| `src/micp_lca/` | the model: `loaders`, `chemistry`, `inventory`, `lcia`, `benchmarks`, `uncertainty`, `sensitivity`, `parametric` (one-variable sweeps), `cost`, `figures`, `pdfreport` (PDF report with narrative and references), `db`, `export`, `report`, `cli` |
| `scripts/` | reproducible downloads: `extract_ef31_subset.py`, `fetch_oekobaudat.py`, `fetch_agribalyse_proxies.py`; `write_results_doc.py` |
| `docs/` | goal & scope, system description, LCI methodology, data quality, literature review, standards checklist, ecoinvent/Brightway guide, baseline results, database schema, how to extend, the application |
| `results/` | generated tables and figures (`micp-lca run-all`, `contributions`, `sensitivity`, `monte-carlo`) |
| `tests/` | 77 tests (data integrity, stoichiometry/mass balances, all pathways, model behaviour, uncertainty, DB, CLI, cost, user-data merge, custom compositions, parametric sweeps, figures, PDF report, every application page) |

## Installation

The `micp-lca` console script is installed into the Python `Scripts` directory; if that directory is not on your PATH, use `python -m micp_lca.cli …` instead.

```bash
pip install -e ".[app]"     # Python >= 3.10; numpy, pandas, pyyaml, click, matplotlib, reportlab + streamlit, plotly
streamlit run app/Home.py   # the interactive application (http://localhost:8501)
python -m pytest -q         # optional: pip install pytest
```

### Deploying the application (Streamlit Community Cloud)

The repository is ready for [Streamlit Community Cloud](https://share.streamlit.io): sign in with GitHub, choose
*Create app*, select this repository and branch, set the main file path to `app/Home.py` and deploy.
`requirements.txt` lists the dependencies, `.python-version` the Python version (3.12; choose the same version
under *Advanced settings* if it is not picked up automatically) and `.streamlit/config.toml` the theme.
No secrets or system packages are needed. The same files serve a Hugging Face Space with the Streamlit SDK
(app file `app/Home.py`).

## The application

`streamlit run app/Home.py` opens a local web application with seven pages (details in
`docs/11_application.md`):

* **Scenario builder** – *pre-defined compositions* (the 23 protocols with their recipe cards) or a
  *custom composition* (waste material, organism with any metabolic pathway, cultivation and
  nutrient media with editable components, reagents, dosing, curing, drying, specimen, expected
  performance); technology & system settings (energy model, electricity, effluent treatment, end of
  life, carbon accounting, scale-up parameters); all EF 3.1 indicators with data coverage,
  contribution analysis, reagent/carbon/nitrogen balance, inventory and indicative cost;
  **parametric analysis** of any single parameter between limits with response plots; a
  **PDF report** with figures, tables, data-driven scientific narrative and numbered references;
  saving as a user scenario or as database entries.
* **Compare** – scenarios vs AAC, bricks, concrete blocks and the WCF–OPC block per kg, m³ or
  m³·MPa; normalised indicator heat map; system-expansion comparison with the status quo.
* **Uncertainty** – tornado (one-at-a-time) and Monte Carlo with Spearman ranking.
* **Database** – browse/search/export every table incl. the full EF 3.1 factor table.
* **Data editor** – add background factors, sources, chemicals, media, protocols, scenarios and
  prices to `data/user/` with validation.
* **Literature** – published MICP LCA results and a per-kg-CaCO3 cross-check of the model.
* **Cost** – bulk vs laboratory-grade cost per functional unit and eco-efficiency plots.

## Python API

```python
from micp_lca import load_data, run_scenario
from micp_lca.benchmarks import compare_scenarios, compare_with_status_quo
from micp_lca.uncertainty import monte_carlo, MCSettings
from micp_lca.sensitivity import oat_sensitivity

data = load_data()
r = run_scenario("GYP_WCFC_single_dose", data, functional_unit="kg_product")
r.totals(("A1", "A2", "A3"))          # EF 3.1 indicators per kg product, cradle-to-gate
r.by_group()                          # contribution analysis by process group
r.by_module()                         # A1, A2, A3, C1–C4, D
r.coverage, r.coverage_native         # data coverage per impact category
r.meta                                # reagent balance, CaCO3 yield, N fate, volumes, energies

table = compare_scenarios([r], data)  # vs AAC, clay brick, concrete block, WCF-OPC block …
mc = monte_carlo("GYP_WCFC_single_dose", data, MCSettings(n=1000))
mc.percentiles(); mc.spearman("GWP-total")
oat_sensitivity("GYP_WCFC_single_dose", data, category="AP")
```

Scenario keys can be overridden on the fly: `run_scenario(name, data, overrides={"material": "wcf_g",
"scale": "lab", "effluent_treatment": "ammonia_stripping", "carbon_accounting": "EN15804A2",
"protocol_overrides": {"biocementation_solution": {"dosing": {"mode": "fixed", "n_doses": 5}}}},
param_overrides={"industrial.curing_chamber.U_W_m2K": 0.2})`. The indicative cost of a result:
`micp_lca.cost.cost_summary(r, data, "bulk" | "lab")`. Custom compositions are passed inline
(`overrides={"custom_protocol": {...}, "custom_media": {...}, "custom_strains": {...}}`); a
one-variable analysis: `micp_lca.parametric.sweep(name, data, "protocol:biocementation_solution.dose_mL", [1, 5, 10])`;
a PDF report: `micp_lca.pdfreport.build_report(name, data, "report.pdf", options=ReportOptions(sweep=df, sweep_parameter=p, mc=mc))`.

## What the model does (short version)

1. **Foreground inventory per specimen → per kg solids → per functional unit** (`inventory.py`):
   waste-fines processing (crushing, high-speed milling 6.25 kWh/t, wear parts), cultivation
   (medium, sterilisation heat with recovery, fermentation power, centrifugation), casting
   (saline, HCl, mixing), biocementation solution (doses × volume × concentrations), curing chamber
   heat loss, drying, effluent treatment, transport, end of life.
2. **Chemistry** (`chemistry.py`): limiting-reagent CaCO3 yield checked against the measured XRD
   gains; explicit carbon balance (urea carbon is fossil, lactate carbon is biogenic, portlandite
   carbonation is an uptake); nitrogen balance (NH4+ to water, NH3 to air, N2O, recovered N).
3. **LCIA** (`lcia.py`): EF 3.1 factors for direct emissions; per-unit EN 15804+A2 factors for
   background datasets; two biogenic-carbon conventions (EF 3.1 = default; EN 15804+A2 −1/+1);
   data-coverage statistics distinguishing native from proxy-filled factors.
4. **Interpretation**: contribution analysis, benchmarks, system-expansion comparison with the
   status quo, one-at-a-time tornado and Monte Carlo (pedigree-based lognormal + parameter ranges,
   Spearman ranking).

## Headline results (baseline, per kg dry product, cradle-to-gate A1–A3, EF 3.1 GWP-total)

| Scenario | kg CO2e/kg | Dominant contributors |
|---|---|---|
| Ureolytic 90-day lab protocol as performed (*S. pasteurii*, urea 13× excess) | **3.9** (AP 0.71 mol H+ eq) | NH3/NH4+/N2O and CO2 from urea hydrolysis, urea, TSB medium, 51 L of solution per kg solids |
| … with laboratory equipment energy | 179 | incubator/shaker idle energy — the lab-scale artefact |
| … stoichiometric urea, solution recirculation, NH3 stripping | 1.4 | cultivation medium (tryptone), CaCl2 |
| Non-ureolytic (*S. cohnii*, Ca-lactate, 30 d repeated dosing) | 0.84 | LB medium, calcium lactate, sterilisation heat |
| … with feather-hydrolysate media (28 d) | 0.44 | Ca-lactate, curing/fermentation energy |
| Gypsum-promoted, single dose (prototype recipe, 1.9 MPa) | **0.17** (188 kg CO2e/m3) | LB medium 71 %; curing heat; carbonation uptake −0.02 |
| … with feather-hydrolysate medium | 0.09 | curing/fermentation energy |
| Fungal (*T. reesei*, malt extract) | 0.33–0.36 | malt extract broth (30 mL/25 g) |
| Literature pathways (30 d, industrial energy): *S. pasteurii* on NH4-YE / corn steep liquor / manure effluent 1.0 / 0.9 / 0.9; EICP (jack-bean urease) 0.20; denitrification (Ca-acetate + Ca-nitrate) 1.8; acetate oxidation (fossil Ca-acetate) 1.0; photosynthetic (LED) 6.9 | | reagents and media; LED electricity for the photosynthetic route |
| Benchmarks: AAC 0.48 (207–232 kg/m3); WCF–OPC foamed block 0.31; clay brick 0.20; sand-lime brick 0.13; concrete block 0.11; adobe 0.08 | | |

Monte Carlo (500 runs) 95 % intervals: prototype recipe 0.14–0.27; 90-day ureolytic 3.7–5.4
kg CO2e/kg. The most influential inputs are the footprint of tryptone/peptone media (proxy data),
the N2O share for the ureolytic route, curing-chamber insulation and the reagent dosing.
Indicative cost (bulk prices, A1–A3): prototype recipe 0.26 EUR/kg (0.07 with feather hydrolysate),
Ca-lactate route 1.5, ureolytic lab protocol 3.6 EUR/kg; laboratory-grade reagents multiply these
by 4–5. See `docs/08_results_baseline.md` and `results/`.

## Data provenance and licences

* EF 3.1 characterisation factors: European Commission JRC (free use).
* ÖKOBAUDAT: BMWSB, free use with attribution.
* AGRIBALYSE 4: ADEME, Licence Ouverte / Etalab 2.0.
* Literature values: cited per row (`source_id` → `data/sources/sources.csv`).
* The code is released under the MIT licence (see `pyproject.toml`); the papers in `papers/`
  keep their publishers' copyrights.

## Citing

See `CITATION.cff`. Please also cite the underlying experimental papers (`data/sources/sources.csv`).
