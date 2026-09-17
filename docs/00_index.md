# Documentation index

| Document | Content |
|---|---|
| [01_goal_and_scope.md](01_goal_and_scope.md) | Goal, functional units, system boundary, cut-off/allocation, impact assessment method, data-quality requirements, limitations (ISO 14044 §4.2) |
| [02_system_description.md](02_system_description.md) | The MICP technology as published; materials, strains, media, protocols; the lab → industrial scale-up model; benchmarks |
| [03_lci_methodology.md](03_lci_methodology.md) | How the inventory is generated from the protocols; carbon accounting (fossil urea-C, biogenic lactate-C, carbonation); nitrogen fate; background data; uncertainty |
| [04_data_quality.md](04_data_quality.md) | Pedigree matrix, quality of the main inputs, coverage statistics, assumptions not given in the papers, measurements recommended to the group |
| [05_literature_review.md](05_literature_review.md) | Annotated bibliography: MICP LCAs (Porter 2021, Deng 2021, Alotaibi 2022, Raymond 2025 …), alternative nutrients/effluent treatment, ex-ante LCA methodology, standards, open databases |
| [06_standards_checklist.md](06_standards_checklist.md) | Compliance checklist against ISO 14044, EN 15804+A2, PEF and ex-ante LCA good practice; next steps before publication |
| [07_using_ecoinvent_brightway.md](07_using_ecoinvent_brightway.md) | Replacing the open background data by ecoinvent; Brightway and openLCA export |
| [08_results_baseline.md](08_results_baseline.md) | Generated baseline results: per kg and per m3 comparisons, core indicators, contribution analyses, system expansion, reagent diagnostics, Monte Carlo, interpretation |
| [09_database_schema.md](09_database_schema.md) | Tables of the SQLite database and the data files they are built from |
| [10_how_to_extend.md](10_how_to_extend.md) | Adding protocols, scenarios, background factors and pathways; user data folder |
| [11_application.md](11_application.md) | The interactive Streamlit application: pages, controls, workflows, how it maps onto the model |

Start the application with `streamlit run app/Home.py`. Regenerate 08 with `python scripts/write_results_doc.py` after changing data or running Monte Carlo.
