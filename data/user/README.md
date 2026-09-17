# User data (merged automatically at load time)

Put your own additions here; they are merged into the database without touching the curated files:

| File | Content | Format |
|---|---|---|
| `protocols.yaml` | additional laboratory protocols | same keys as `data/foreground/protocols.yaml` |
| `scenarios.yaml` | `scenarios:` and/or `benchmarks:` blocks | same keys as `data/foreground/scenarios.yaml` |
| `materials.yaml`, `media.yaml`, `strains.yaml`, `chemicals.yaml` | additional entries (same ids override the curated ones) | same keys as the curated files |
| `background_processes.csv` | additional/overriding background factors (e.g. licensed ecoinvent results) | same columns as `data/background/background_processes_literature.csv`; extra columns named like impact-category codes are read as native factors |
| `sources.csv` | references for the additions | same columns as `data/sources/sources.csv` |

The Streamlit application (`streamlit run app/Home.py`) writes to these files when you save a
scenario, protocol or background factor from the *Data editor* page.
