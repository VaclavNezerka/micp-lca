# 10. How to add data and scenarios

All inputs are plain-text files; after editing, run `python -m pytest -q` (integrity tests) and
`micp-lca build-db` to refresh the SQLite snapshot.

## Add a new laboratory protocol

Append to `data/foreground/protocols.yaml`:

```yaml
my_new_protocol:
  name: S. cohnii, HM2 + 10 % gypsum, 20 °C, single dose (my experiment 2026-10)
  source_id: MYLABBOOK2026          # add the source to data/sources/sources.csv
  strain: sutcliffiella_cohnii_DSM6307
  material: hm2
  solids_g: 26.4
  gypsum_fraction: 0.0909
  suspension: {volume_mL: 10.0, od600: 5.0}
  saline_mL: 6.0
  hcl: {molarity: 2.0, volume_mL: 0.0}
  biocementation_solution:
    base_medium: nb_4
    supplements: {calcium_lactate_pentahydrate: 11.0}
    dose_mL: 5.0
    dosing: {mode: single}          # or {mode: repeated, interval_h: 60, duration_d: 30} / {mode: fixed, n_doses: 14}
  incubation: {temperature_C: 20, duration_d: 30}
  drying: {temperature_C: 20, duration_d: 30}
  results: {fc_MPa: 0.6, caco3_gain_wt_abs: null}
```

Then add a scenario in `scenarios.yaml`:

```yaml
  MY_SCENARIO:
    description: …
    protocol: my_new_protocol
    effluent_treatment: none
```

`micp-lca run MY_SCENARIO` prints totals and contributions.

## Add a new medium or chemical

1. `chemicals.yaml`: id, molar mass, element contents (carbon/nitrogen/calcium/chloride), carbon
   origin, `background_process`.
2. `data/background/background_processes_literature.csv`: the cradle-to-gate factor per kg
   (GWP, optional ADP-fossil, min/max, pedigree R,C,T,G,F, `ecoinvent_proxy`, optional
   `profile_proxy` for the other categories, `source_id`).
3. `media.yaml`: recipe in g/L, sterilisation method (`autoclave`, `filtration`, `none`) and, for
   hydrolysates, the heating step.

## Add a new material (waste stream)

`materials.yaml`: composition (XRF), portlandite and CaCO3 content (XRD/TGA), particle size,
processing steps (kWh/t), transport distance, bulk density of the consolidated product.

## Add a benchmark

Either reference an ÖKOBAUDAT dataset (add it to `scripts/fetch_oekobaudat.py` → `DATASETS`, run the
script, map it in `background_processes_oekobaudat.csv`) or give fixed impacts from an EPD in
`scenarios.yaml → benchmarks` (`fixed_impacts_per_m3` or `fixed_impacts_per_t`).

## Change scale-up assumptions

Edit `scaleup.yaml` (every `{value, min, max}` entry is automatically part of the Monte Carlo and
tornado analyses). Discrete choices (drying mode, heat carrier, water source) are text keys.

## Regenerate open background data

```bash
python scripts/extract_ef31_subset.py path/to/EF-LCIAMethod_CF(EF-v3.1).xlsx
python scripts/fetch_oekobaudat.py
python scripts/fetch_agribalyse_proxies.py
```

## Command-line entry point

If `micp-lca` is not on your PATH (Windows user installs), use `python -m micp_lca.cli …`.

## Use the application instead of editing files

Everything above can also be done from the **Data editor** page of the application
(`streamlit run app/Home.py`): background factors (with pedigree scores and an optional
profile proxy for the non-GWP categories), sources, chemicals, media, protocols (YAML with
validation and a test run), scenarios and prices. The entries are written to `data/user/` and
merged at load time; identical ids override the curated entries, so a licensed ecoinvent value
for, e.g., `calcium_chloride` replaces the literature factor everywhere. The **Scenario builder**
saves its current configuration (including `protocol_overrides` and `scaleup_overrides`) as a
user scenario that the CLI (`micp-lca run USER_…`) evaluates identically. See
`11_application.md`.

## Custom compositions, parametric analysis and reports

The Scenario builder's *Custom composition* mode builds a complete protocol (plus inline media,
organisms and material overrides) interactively; it can be saved either as a scenario with inline
definitions (`custom_protocol`, `custom_media`, `custom_strains`, `custom_materials`) or as
separate entries of the user database. The same keys can be written by hand in
`data/user/scenarios.yaml`. One parameter of any configuration can be varied between limits
(`micp-lca parameters`, `micp-lca sweep`, tab 4 of the builder) and a full PDF report can be
generated (`micp-lca report`, tab 5 of the builder); see `11_application.md`.
