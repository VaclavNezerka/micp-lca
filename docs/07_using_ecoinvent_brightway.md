# 7. Using licensed background data (ecoinvent) with Brightway or openLCA

The open background data shipped with this repository (ÖKOBAUDAT, AGRIBALYSE, literature values)
are sufficient for hotspot analysis and for the climate-change indicator. For a publication-grade
assessment of all EF 3.1 categories, replace the literature/proxy factors with ecoinvent datasets.
Two workflows are supported.

## 7.1 Replace factors in the CSV tables (no extra software)

1. In your LCA software (openLCA, SimaPro, Brightway) compute the EF 3.1 impacts *per unit* of
   the datasets listed in the column `ecoinvent_proxy` of
   `data/background/background_processes_literature.csv` (e.g. `market for urea | urea | RER`).
2. Add the resulting values to `data/background/background_processes_literature.csv` as new
   columns named exactly like the category codes (`AP`, `EP-freshwater`, … see
   `data/lcia/ef31_impact_categories.csv`) and set `profile_proxy` empty for those rows. The loader
   (`micp_lca.loaders._load_literature`) reads any column whose header is a category code.
   *(A small extension: add `impacts["A1-A3"][code] = value` in `_load_literature` — the hook is
   marked in the code.)*
3. Re-run `micp-lca build-db` and `micp-lca run-all`; the coverage statistics will report
   100 % native coverage.

## 7.2 Export the foreground to Brightway 2.5

```python
from micp_lca import load_data, run_scenario
from micp_lca.export import to_brightway
import bw2data as bd, bw2io as bi

data = load_data()
res = run_scenario("GYP_WCFC_single_dose", data, functional_unit="kg_product")
db = to_brightway(res, data, db_name="micp_foreground", background_db="ecoinvent-3.11-cutoff")
# link technosphere exchanges by the ecoinvent dataset names stored in each exchange ('input' key),
# e.g. with bw2io.strategies or a small mapping loop, then:
bd.Database("micp_foreground").write(db)
```

Each technosphere exchange carries `name`, `unit`, `module`, `group` and the ecoinvent proxy name in
`input[1]`; biosphere exchanges use ecoinvent/biosphere3 flow names (`Carbon dioxide, fossil`,
`Ammonia`, `Ammonium, ion`, `Dinitrogen monoxide`, …). The EF 3.1 method is available in Brightway
through `bw2io` (`bi.add_ecoinvent_ef31_methods()` in recent versions) or via the ecoinvent LCIA
implementation.

## 7.3 openLCA

`micp-lca export <scenario> --format csv` writes `inventory_<scenario>.csv` (one row per exchange
with amount, unit, module, group and ecoinvent proxy). Create a process in openLCA, import the
exchanges (Excel/CSV import or manually), link providers, and calculate with the EF 3.1 method
package supplied with openLCA (`EF 3.1` in the openLCA LCIA methods pack).

## 7.4 Consistency notes

* Keep the **cut-off** system model (consistent with EN 15804 polluter-pays) unless you
  deliberately switch to APOS/consequential for the whole study.
* Use EF 3.1 characterisation factors for both foreground and background to keep the results
  additive with the ÖKOBAUDAT datasets.
* Electricity: `market for electricity, low voltage | CZ` (ecoinvent) replaces the
  Ember-based estimate; document the reference year.
* Urea: ecoinvent's urea dataset includes the CO2 captured in the product as an input; keep the
  explicit release modelled in `chemistry.py` (0.733 kg CO2 per kg hydrolysed urea minus the
  carbon fixed in CaCO3) to avoid double counting or omission.
