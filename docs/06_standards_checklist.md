# 6. Compliance checklist (ISO 14044, EN 15804+A2, PEF) and best practices

| Requirement | Where addressed | Status |
|---|---|---|
| **ISO 14044 §4.2** goal, intended application, audience, comparative assertions | `01_goal_and_scope.md` | done; comparative assertions explicitly excluded until critical review |
| §4.2.3.2 functional unit and reference flow | `01_goal_and_scope.md` §1.2, `lcia.fu_conversion` | 5 functional units implemented |
| §4.2.3.3 system boundary and cut-off criteria | §1.3; modules A1–A3, C1–C4, D | capital goods excluded (documented) |
| §4.2.3.4 allocation | secondary materials burden-free (EN 15804 polluter-pays); sensitivity on feathers | done |
| §4.2.3.6 data quality requirements | `04_data_quality.md`, pedigree scores per dataset | done |
| §4.3 LCI: data collection, calculation, validation | `data/foreground/*.yaml` (traceable to papers), `chemistry.py` mass balances, `tests/` (balance closure) | done |
| §4.4 LCIA: selection of categories, models, factors | EF 3.1 official CFs (`data/lcia`), EN 15804+A2 indicator set | done; no normalisation/weighting |
| §4.5 interpretation: significant issues, completeness, sensitivity, consistency | contribution analysis, coverage statistics, OAT + Monte Carlo (`sensitivity.py`, `uncertainty.py`) | done |
| §6 critical review | not performed | **open** (required before public comparative assertions) |
| **EN 15804+A2** declared unit / functional unit | 1 kg or 1 m3 of product | done |
| modules and separate reporting of D | `Results.summary()`, `report.en15804_table()` | done |
| core EF indicators (GWP-total/fossil/biogenic/luluc, ODP, AP, EP×3, POCP, ADP×2, WDP) | `data/lcia/ef31_impact_categories.csv` | done |
| additional indicators (PM, IRP, ETP-fw, HTP-c, HTP-nc, SQP) | implemented; coverage limited for generic datasets | partial (flagged) |
| resource-use / waste / output-flow indicators (PERE … EET) | stored for ÖKOBAUDAT datasets (`background_impacts`) | stored, not aggregated for the foreground (foreground energy is modelled from energy carriers) |
| biogenic carbon −1/+1 and declaration of biogenic carbon content | `carbon_accounting: EN15804A2` | done |
| carbonation (EN 16757 Annex BB) | `carbonation_uptake_fraction` | done (A3) |
| polluter-pays for secondary materials | `data_type: secondary_material` | done |
| **PEF (EU 2021/2279)** EF 3.1 method, DQR | EF 3.1; pedigree-based data quality | DQR not computed in PEF format (could be derived from pedigree) |
| **Ex-ante LCA good practice** (van der Giesen 2020; Thonemann 2020) | scale-up model with ranges; lab-energy artefact shown; incumbent benchmarks; uncertainty | done |
| **Reproducibility / FAIR** | plain-text data with `source_id`, scripts to regenerate downloads (EF 3.1, ÖKOBAUDAT, AGRIBALYSE), SQLite snapshot, tests | done |
| **Transparency of proxies** | `profile_proxy`, `proxy_filled`, `coverage_native` | done |

## Recommended next steps before publication

1. Replace literature/proxy factors by ecoinvent 3.11 (cut-off, EF 3.1) datasets using the
   `ecoinvent_proxy` names — see `07_using_ecoinvent_brightway.md`.
2. Measure the items listed in `04_data_quality.md` §4.5 (harvest OD, effluent composition,
   N mass balance, prototype density/strength, pilot curing energy).
3. Add A4/A5 and the use phase if the comparison is extended to a wall element (EN 15978).
4. Commission a critical review (ISO 14044 §6.2) for comparative assertions.
