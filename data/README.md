# Data directory

| Folder / file | What it is | Origin / how to regenerate |
|---|---|---|
| `foreground/chemicals.yaml` | reagents and media components: formulae, molar masses, C/N/Ca/Cl contents, carbon origin, link to background factor | transcribed from the papers and chemistry |
| `foreground/media.yaml` | recipes of TSB, LB, NB, malt extract broth, saline, sesquicarbonate buffer, feather hydrolysates (g/L) | papers + manufacturers' formulations (Oxoid/HiMedia) |
| `foreground/strains.yaml` | cultivation protocols of *S. pasteurii*, *S. cohnii*, *A. pseudofirmus*, *T. reesei* | papers (harvest OD assumed) |
| `foreground/materials.yaml` | WCF-G, WCF-H, WCF-C, HM1, HM2, waste gypsum: composition, portlandite, particle size, processing chain, transport | papers; milling energy from NEZERKA2023LCA |
| `foreground/protocols.yaml` | 23 biocementation protocols (per specimen) with dosing schedules and measured results; 18 from the papers + 5 literature pathways (alternative media, EICP, denitrification, acetate oxidation, photosynthetic) | papers, literature |
| `foreground/scaleup.yaml` | laboratory vs industrial energy/effluent parameters with ranges | engineering estimates (Piccinno et al. 2016 framework) |
| `foreground/scenarios.yaml` | 29 assessment scenarios and 8 benchmarks with modelling choices | this study |
| `background/oekobaudat/` | 107 EN 15804+A2 datasets (EF 3.1; 15 996 indicator values) from ÖKOBAUDAT OBD_2024_II: raw JSON (gzip) + normalised CSV; all are available as `obd_<key>` background processes | `python scripts/fetch_oekobaudat.py` |
| `background/background_processes_oekobaudat.csv` | mapping of ÖKOBAUDAT datasets to model process ids (unit conversions, ecoinvent proxies, pedigree) | manual |
| `background/background_processes_literature.csv` | 47 chemicals, media components, energy, secondary materials: GWP (+ADP-fossil) with ranges, pedigree, `profile_proxy`, ecoinvent proxy, source | literature (see `source_id`) |
| `background/agribalyse_proxy_profiles.csv` (+ raw CSV) | EF 3.1 cradle-to-factory-gate profiles of 7 agro-food products (AGRIBALYSE 4) used as proxies | `python scripts/fetch_agribalyse_proxies.py` |
| `lcia/ef31_impact_categories.csv`, `lcia/ef31_characterization_factors.csv`, `lcia/ef31_characterization_factors_full.csv.gz` | official EF 3.1 method: 19 categories, 120 curated characterisation factors for the foreground flows (incl. CZ factors) and the complete table (140 474 rows, GLO + CZ) used for any other flow | `python scripts/extract_ef31_subset.py <EF-LCIAMethod_CF(EF-v3.1).xlsx>` |
| `experimental/experimental_results.csv` | 81 measured values (CaCO3, porosity, stiffness, strength, AFt) from the papers | transcribed |
| `literature/micp_lca_literature_results.csv` | 27 published MICP LCA / cost results (Porter 2021, Deng 2021, Alotaibi 2022, Nežerka 2023, van Paassen 2010, Raymond 2025 …) | transcribed |
| `economics/prices.csv` | 61 indicative EUR prices (bulk/technical and laboratory grade) per background process for the cost module | indicative (edit with quotations) |
| `user/` | your own additions (same formats), merged at load time; written by the application | see `user/README.md` |
| `sources/sources.csv` | 49 references (papers, standards, databases, reports) with DOIs/URLs | manual |
| `db/micp_lca.sqlite` | derived SQLite snapshot (+ stored results) | `micp-lca build-db`, `micp-lca run-all --store` |

Conventions: masses in kg, volumes in L (media) or mL (recipes as in the papers), energy in kWh,
distances in km, impact factors per declared unit of the background dataset (kg, kWh, tkm).
Every quantitative row carries a `source_id`; assumptions are marked in the `notes` columns.
