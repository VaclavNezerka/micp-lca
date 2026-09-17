# 11. The interactive application

`app/` contains a multi-page **Streamlit** application built on the same `micp_lca` package and
database as the command-line interface. It is the intended way to *use* the model interactively:
configure a process, run the LCA, compare, quantify uncertainty, browse and extend the database.

```bash
pip install -e ".[app]"          # or: pip install streamlit plotly reportlab
streamlit run app/Home.py
```

The app opens at <http://localhost:8501>. All computations run locally; nothing is sent anywhere.
Every table and chart can be downloaded as CSV/PNG.

## Pages

| Page | Purpose | Main controls |
|---|---|---|
| **Home** | orientation, database counts, baseline snapshot | – |
| **Scenario builder** | six tabs: **Composition** (pre-defined: choose one of the 23 protocols, the waste material and the cultivation-medium variant and read the full recipe card, cultivation settings and media recipes, plus a table of all pre-defined compositions; custom: define your own composition from a template — waste material and its properties, dry solids and gypsum share, organism (existing or custom with any metabolic pathway: ureolytic, organic-acid, fungal, EICP, denitrification, photosynthetic), cultivation medium (existing or custom components in g/L), temperature/time/harvest OD, suspension, casting (saline, HCl, mixing), nutrient base of the biocementation solution (existing, custom or water only), reagents (calcium salts, urea, nitrate, bicarbonate … in g/L), dose volume and dosing schedule, curing, drying, specimen, expected strength, measured CaCO₃ cap, precipitation efficiency); **Technology & system** (energy model, electricity, effluent N treatment, end of life, module D, biogenic-carbon convention, site-specific factors, carbonation, temperature, transport distances, reagent optimisation, harvest OD, advanced scale-up parameters, abiotic control); **Results** (indicators with coverage, contributions, reagent/carbon/nitrogen balance, inventory, cost); **Parametric analysis** (one parameter varied between limits — see below); **PDF report**; **Save** (as a scenario with inline definitions or as protocol + media + organism entries of the user database) | all recipe, organism, media, technology and scale-up inputs |
| **Compare** | several scenarios vs benchmark products (AAC, clay brick, sand-lime brick, concrete block, adobe, WCF–OPC foamed block) per kg, per m³ or per m³·MPa; all core indicators; normalised heat map; system-expansion comparison with the status quo (conventional block + landfilling of the absorbed fines) | scenarios, benchmarks, functional unit, indicator, log axis |
| **Uncertainty** | one-at-a-time tornado of every ranged input (scale-up parameters, background factors with literature ranges, optional discrete scenario switches); Monte Carlo propagation (pedigree-based lognormal / log-triangular literature ranges / triangular parameters) with percentiles for all indicators and Spearman ranking; pedigree and range tables of the inputs used by the scenario | scenario (or the current builder configuration), indicator, functional unit, modules, sample size, seed, what to sample |
| **Database** | browse, filter, search and export: background datasets (161; impact-profile matrix; per-dataset details with source, pedigree, ecoinvent proxy, proxy-filled categories), EF 3.1 characterisation factors (curated subset and full-table search over 140 474 factors), chemicals, media (incl. cradle-to-gate GWP per litre), organisms, waste materials, protocols, scenarios and benchmarks, experimental results (with plot), prices, sources | free-text search and filters per tab |
| **Data editor** | forms that write to `data/user/` (never to the curated files): background factor (GWP ± other EF categories, pedigree, profile proxy), source, chemical, medium, protocol (YAML with validation and a test run), scenario, price; manage/remove user entries; reload | – |
| **Literature** | the 27 published MICP LCA results (Porter 2021, Deng 2021, Alotaibi 2022, Nežerka 2023, van Paassen 2010, Raymond 2025, cost studies) with references; cross-check of the model per kg of precipitated CaCO₃ (optionally "materials only" to mimic Porter et al.); reagent demand per kg CaCO₃ vs stoichiometry | scenarios, materials-only switch |
| **Cost** | indicative cost per functional unit for several scenarios at bulk vs laboratory-grade prices; eco-efficiency plot (cost vs GWP); cost breakdown by process group and module; unpriced flows | scenarios, functional unit, price level |

## Parametric analysis (one variable at a time)

Every configuration exposes a registry of *sweepable* parameters with default limits
(`micp_lca.parametric.available_parameters`), grouped into recipe (solids, gypsum share, suspension
volume and OD, harvest OD, saline, acid, dose volume, dosing interval/period/number, every reagent
concentration, urea : Ca ratio, recirculation, nutrient-base factor, temperature, curing and drying
periods, precipitation efficiency), cultivation (every component of the cultivation medium, cultivation
time, light energy), system (carbonation fraction, portlandite content, transport distances) and
scale-up (all ranged parameters of `scaleup.yaml`). The user picks one parameter, the limits and the
number of steps; the model is evaluated at every step with everything else fixed, and the response of
the selected indicators, the indicative cost and the CaCO₃ yield is plotted (optionally relative to the
current configuration) and tabulated, with a short description (monotonicity, span, location of the
minimum, linearity). The sweep is stored for the PDF report. The same analysis is available from the
CLI: `micp-lca parameters SCENARIO` lists the keys, `micp-lca sweep SCENARIO -p KEY --from A --to B --steps N`
writes a CSV and a figure. Parameter keys use namespaces (`protocol:`, `scenario:`, `reagent:`,
`scaleup:`, `medium:<id>.<component>`, `strain:<id>.<path>`, `material:<id>.<key>`, `harvest_od600`).

## PDF report

The **PDF report** tab (and `micp-lca report SCENARIO [-p KEY] [--mc N] [--compare OTHER …]`) writes a
self-contained report with ReportLab and matplotlib (`micp_lca.pdfreport`, `micp_lca.figures`):

1. Summary with the key figures and the comparison with a reference product.
2. Goal and scope (functional unit, boundary, conventions, geography, cut-off, data quality) with
   citations of ISO 14040/14044, EN 15804+A2, EF 3.1, PEF and the prospective-LCA literature.
3. System description: composition/protocol table, pathway chemistry paragraph, technology settings.
4. Life-cycle inventory: liquid/solid ratios, reagent/carbon/nitrogen balance per kg solids and per
   functional unit, nitrogen-fate chart, main background flows ranked by GWP, direct flows.
5. Impact assessment: all EF 3.1 indicators with coverage, contribution analysis (group × module),
   process-group profile across the indicators, module split, climate-change waterfall.
6. Comparison with benchmarks (figure and table per kg and per m³), indicator-wise ratio to the
   reference product, system-expansion comparison with the status quo.
7. Parametric analysis (from tab 4), one-at-a-time tornado, optional Monte Carlo with percentiles and
   Spearman ranking.
8. Indicative cost (bulk vs laboratory grade) by process group.
9. Data quality (datasets with pedigree scores and σg, proxy-filled categories) and limitations.
10. Interpretation and conclusions generated from the results, notes, numbered references resolved
    from `data/sources/sources.csv`.

Every number in the narrative is taken from the same result objects as the tables, so text, tables and
figures are always consistent.

## How the application maps onto the model

* Every run goes through `micp_lca.lcia.run_scenario(scenario, data, functional_unit, overrides,
  param_overrides)`; the UI only assembles the `overrides` dictionary (scenario keys such as
  `protocol`, `material`, `scale`, `effluent_treatment`, `reagent_optimisation`,
  `protocol_overrides` — a deep merge into the protocol — `harvest_od600_override`, and for custom
  compositions the inline definitions `custom_protocol`, `custom_media`, `custom_strains`,
  `custom_materials`) and the `param_overrides` (dotted scale-up paths such as
  `industrial.curing_chamber.U_W_m2K`). A saved user scenario therefore reproduces exactly what the
  builder showed, also from the CLI.
* Results are cached per configuration (`st.cache_data`); the database is loaded once
  (`st.cache_resource`) and reloaded after every edit.
* User additions are merged by `micp_lca.loaders.load_data()` from `data/user/` (same file formats
  as the curated tables; identical ids override curated entries; extra CSV columns named like
  impact-category codes are read as native factors). `MICP_LCA_DATA` can point the whole
  application to another data root.

## Typical workflows

1. **Optimise a recipe** – Scenario builder: start from `GYP_WCFC_single_dose`, change the medium
   variant to `feather`, lower the curing temperature, reduce the LB concentration with the
   nutrient-broth factor, watch GWP/AP/EP and the cost update; save as `USER_…`; then Compare it
   with AAC and the WCF–OPC block per m³·MPa.
2. **Check robustness** – Uncertainty: run the tornado for AP or EP-terrestrial of a ureolytic
   scenario with the `effluent_treatment` switch enabled; run 1000 Monte Carlo samples and read the
   Spearman ranking to see which background factor deserves better data.
3. **Bring your own data** – Data editor: enter an ecoinvent or EPD factor for CaCl₂ or peptone
   (with pedigree scores), a supplier price and a source; the entry appears immediately in the
   Database page and in every new run.
4. **Position against the literature** – Literature page: compare the model's per-kg-CaCO₃ values
   with Porter et al. (2021) and Deng et al. (2021) and see how far the protocols are from
   stoichiometric reagent use.

## Testing

`tests/test_parametric_report.py` covers custom compositions, the parameter registry and sweeps, the
figures, the PDF report (structure and citation integrity) and the builder page in custom mode;
`tests/test_app_cost_userdata.py` runs every page headlessly with Streamlit's `AppTest`
(no exceptions/errors), exercises the builder, the strength-normalised comparison, the Monte Carlo
button and the data-editor forms against a temporary copy of the data folder.
