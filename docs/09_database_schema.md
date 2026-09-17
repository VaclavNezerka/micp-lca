# 9. Database schema

The SQLite file `data/db/micp_lca.sqlite` is built by `micp-lca build-db` (or
`micp_lca.db.build_database()`) from the plain-text files, which remain the single source of
truth. Query it with `micp-lca sql "<SELECT …>"`, `micp_lca.db.query()`, or any SQLite client.

| Table | Built from | Key columns |
|---|---|---|
| `sources` | `data/sources/sources.csv` | `source_id` (PK), `type`, `citation`, `doi_or_url`, `notes` |
| `impact_categories` | `data/lcia/ef31_impact_categories.csv` | `code` (PK, e.g. `GWP-total`, `AP`), `ef31_name`, `unit`, `ef31_method_uuid`, `core_or_additional` |
| `characterization_factors` | `data/lcia/ef31_characterization_factors.csv` (curated subset; the complete table `ef31_characterization_factors_full.csv.gz`, 140 474 rows GLO + CZ, is consulted at run time for any other flow) | `flow_uuid`, `flow_name`, `compartment` (air/water/freshwater/resource), `category_code`, `cf`, `location` (GLO/CZ) |
| `background_processes` | `background_processes_oekobaudat.csv` (manual mapping) + every fetched ÖKOBAUDAT dataset auto-registered as `obd_<key>`, `background_processes_literature.csv`, `agribalyse_proxy_profiles.csv`, `data/user/background_processes.csv` | `process_id` (PK), `name`, `unit` (kg/kWh/tkm), `category`, `geography`, `reference_year`, `data_type` (oekobaudat/agribalyse/literature/estimate/proxy/secondary_material), `source_id`, `gwp_min`, `gwp_max`, `pedigree` (JSON [R,C,T,G,F]), `basic_uncertainty`, `ecoinvent_proxy`, `notes` |
| `background_impacts` | same | `process_id`, `module` (A1-A3, A4, B6, C1–C4, D, B1), `category_code`, `value` per declared unit, `unit` |
| `chemicals` | `chemicals.yaml` | `chemical_id` (PK), `formula`, `molar_mass`, `carbon_content`, `carbon_origin`, `nitrogen_content`, `calcium_content`, `chloride_content`, `background_process` |
| `media`, `medium_components` | `media.yaml` | `medium_id`, `sterilisation`, `hydrolysis_json`; components `g_per_L` |
| `strains` | `strains.yaml` | `strain_id`, `pathway` (ureolytic/organic_acid/fungal), `cultivation_json`, `alternatives_json` |
| `materials`, `material_processing` | `materials.yaml` | oxide composition (JSON), `portlandite_wt`, `caco3_wt`, `gypsum_wt`, particle sizes, `transport_km`, `product_bulk_density_kg_m3`; processing steps with `electricity_kWh_per_t`, `wear_parts_kg_per_t` |
| `protocols`, `protocol_reagents` | `protocols.yaml` | recipe per specimen (`solids_g`, `gypsum_fraction`, `suspension_mL/od600`, `saline_mL`, `hcl_molarity/mL`, `bs_base_medium`, `bs_dose_mL`, `bs_dosing_json`, temperatures, durations), measured results (`fc_MPa`, `k_N_mm`, `caco3_gain_wt_abs`, `porosity_pct`); reagent concentrations `g_per_L` |
| `scenarios` | `scenarios.yaml` | `scenario_id`, `description`, `protocol_id`, `config_json` (merged with defaults) |
| `benchmarks` | `scenarios.yaml` | `benchmark_id`, `definition_json` |
| `scaleup_parameters` | `scaleup.yaml` | `scale` (industrial/lab), `path` (dotted), `value`, `min`, `max` |
| `experimental_results` | `data/experimental/experimental_results.csv` | `source_id`, `sample_code`, `material`, `organism`, `medium`, `treatment`, `duration_d`, `temperature_C`, `gypsum_wt_pct`, `property`, `value`, `sd`, `unit` |
| `prices` | `data/economics/prices.csv` (+ `data/user/prices.csv`) | `process_id` (PK), `unit`, `price_bulk_eur`, `price_bulk_min`, `price_bulk_max`, `price_lab_eur`, `currency_year`, `source_id`, `notes` — indicative EUR prices for the cost module |
| `literature_results` | `data/literature/micp_lca_literature_results.csv` | `source_id`, `study`, `system`, `functional_unit`, `indicator`, `value`, `unit`, `pathway_or_variant`, `scope`, `notes` — published MICP LCA results |
| `results` | `micp-lca run-all --store` | `run_id`, `scenario`, `functional_unit`, `modules` (A1-A3 / C1-C4 / D), `category_code`, `value`, `unit`, `coverage`, `created` |
| `result_contributions` | same | per flow: `module`, `grp` (process group), `kind`, `key`, `amount`, `unit`, `category_code`, `value` |

Example queries:

```sql
-- climate-change factors of all chemicals with their sources
SELECT p.process_id, i.value AS gwp, p.gwp_min, p.gwp_max, s.citation
FROM background_processes p JOIN background_impacts i ON i.process_id = p.process_id
JOIN sources s ON s.source_id = p.source_id
WHERE i.category_code = 'GWP-total' AND i.module = 'A1-A3' AND p.category = 'chemical';

-- compressive strengths reported in the papers
SELECT source_id, sample_code, material, value, sd FROM experimental_results WHERE property = 'compressive_strength';

-- stored results of the latest run
SELECT scenario, category_code, value, unit FROM results WHERE modules = 'A1-A3' AND category_code IN ('GWP-total','AP')
ORDER BY scenario;
```

## Scenario keys understood by the model

Besides the keys listed in `scenarios.yaml` (`protocol`, `material`, `scale`, `electricity`,
`effluent_treatment`, `eol`, `module_d`, `carbon_accounting`, `site_specific_cf`,
`carbonation_uptake_fraction`, `temperature_override_C`, `abiotic`, `cultivation_variant`,
`reagent_optimisation`, transport distances, `functional_unit`), scenarios written by the
application may contain:

| Key | Meaning |
|---|---|
| `protocol_overrides` | nested dictionary deep-merged into the protocol (e.g. `biocementation_solution.dosing`, `dose_mL`, `supplements`, `incubation.duration_d`, `drying.duration_d`) |
| `scaleup_overrides` | `{dotted.path: value}` overrides of `scaleup.yaml` parameters (same syntax as `param_overrides` of the API/CLI) |
| `harvest_od600_override` | harvest optical density of the culture (changes the culture volume per specimen) |
| `custom_protocol` | a complete protocol mapping used instead of `protocol` (custom compositions of the application) |
| `custom_media`, `custom_strains`, `custom_materials`, `custom_chemicals` | inline entries (same structure as the YAML tables) merged over the loaded tables for this scenario only |

## User data folder

`data/user/` may contain `background_processes.csv`, `sources.csv`, `prices.csv`,
`chemicals.yaml`, `media.yaml`, `strains.yaml`, `materials.yaml`, `protocols.yaml` and
`scenarios.yaml`; they are merged at load time (identical ids override the curated entries) and
written by the application's Data editor and Scenario builder. The folder is ignored by the
SQLite build only in the sense that the merged tables are what gets stored.
