# 3. Life-cycle inventory methodology

## 3.1 From laboratory protocol to inventory

`micp_lca.inventory.build_inventory()` computes every flow **per laboratory specimen** exactly as
described in the paper and normalises it **per kg of dry input solids**. The functional-unit
conversion is applied afterwards (`micp_lca.lcia.fu_conversion`). The chain of calculations is:

1. **Solids**: residue mass = solids × (1 − gypsum fraction); processing electricity and mill
   wear per tonne from `materials.yaml`; transport in t·km.
2. **Suspension**: culture volume = suspension volume × target OD / harvest OD. Medium components
   (g/L × L), supplements (urea 20 g/L or sesquicarbonate buffer), sterilisation heat, fermentation
   electricity, centrifugation, saline for resuspension.
3. **Casting**: saline, HCl (100 % mass = molarity × volume × 36.46 g/mol), water, mixing energy.
4. **Biocementation solution**: number of doses × dose volume; nutrient-broth base components,
   calcium source and urea; sterilisation heat and dosing energy. Reagent optimisation options:
   `urea_to_ca_molar_ratio` (the lab protocols use 13:1), `nutrient_broth_factor`,
   `solution_recirculation_fraction`.
5. **Chemistry** (`micp_lca.chemistry`): reagent balance → theoretical CaCO3 (limiting reagent),
   measured XRD gain (capped at the calcium supply) → precipitation efficiency; carbon balance;
   nitrogen balance; chloride and residual organics.
6. **Curing and drying**: steady-state heat loss of an insulated chamber
   (U·A·ΔT·t) + initial heating of the wet mass; air handling; fan drying (or thermal drying).
7. **Effluent**: drained fraction of the added liquids (40 %, range 20–70 %); treatment options.
8. **Product mass** = solids × (1 + CaCO3 gain + AFt-bound water + retained salts).
9. **End of life** per kg product.

## 3.2 Carbon accounting

| Carbon pool | Origin | Fate in the model |
|---|---|---|
| Urea carbon | fossil (CO2 captured in ammonia/urea synthesis; the Fertilizers Europe cradle-to-gate factor 0.878 kg CO2e/kg *excludes* this captured CO2) | hydrolysed fraction (90 %): carbon precipitated as CaCO3 is **stored** (fossil carbon storage, no emission); the remainder is emitted as **fossil CO2** (0.733 kg CO2 per kg urea hydrolysed, IPCC 2019 urea factor); unhydrolysed urea leaves with the effluent |
| Lactate carbon (calcium lactate) | biogenic (sugar fermentation) | oxidised fraction (90 %): 1/6 stored as biogenic CaCO3, 5/6 emitted as **biogenic CO2**; residual lactate to effluent |
| Media components (peptones, yeast extract, sugars) | biogenic | consumed by the micro-organisms; emitted as biogenic CO2 (EF 3.1: characterisation factor 0) |
| Portlandite in the fines | atmospheric CO2 uptake during curing | negative fossil CO2 flow, 70 % of the theoretical uptake (0.594 kg CO2 per kg Ca(OH)2) — EN 16757 Annex BB convention; sensitivity parameter |
| Limestone carbon in CaCO3 used to make calcium lactate | geogenic | released during neutralisation, included in the calcium-lactate factor |

Two conventions are implemented (`carbon_accounting`):

* **EF31** (default; Environmental Footprint 3.1 as used by EN 15804+A2 indicator *GWP-total*):
  biogenic CO2 uptake and emission have a characterisation factor of 0; only fossil CO2, CH4, N2O
  etc. count. GWP-biogenic contains only the biogenic CH4/CO of background datasets.
* **EN15804A2** (−1/+1): biogenic carbon entering with organic inputs is credited (−1) in A1,
  its emission in A3 counts +1, and the biogenic carbon stored in the product (CaCO3) is released
  by convention at C4 (+1) so that the life-cycle sum is zero (EN 15804+A2 §6.3.5.4). Permanent
  mineral storage credits (ISO 14067 Annex) are deliberately **not** claimed.

## 3.3 Nitrogen (ureolytic route)

Hydrolysed urea-N is partitioned into: N2O (0.2 % of N; IPCC EF1 = 1 % is the upper bound for
soils), drained effluent (40 %) → NH4+ to water unless treated (ammonia stripping to ammonium
sulfate, 90 % efficiency, 8 kWh + 1.5 kg NaOH + 3.5 kg H2SO4 per kg N; or struvite, 75 %, MgO +
H3PO4), retained pore water → 80 % volatilises as NH3 during drying of the alkaline porous block,
the rest stays in the product. EF 3.1 factors: NH3 to air 3.02 mol H+ eq/kg (AP), 13.47 mol N eq/kg
(EP-terrestrial), 0.092 kg N eq/kg (EP-marine); NH4+ to water 0.778 kg N eq/kg (EP-marine);
N2O 273 kg CO2e/kg.

## 3.4 Background data

| Type | Source | Use | Categories |
|---|---|---|---|
| Construction materials, energy carriers, transport, end of life | ÖKOBAUDAT OBD_2024_II (EN 15804+A2, EF 3.1; Sphera/GaBi) | electricity DE, heat (gas, oil), truck transport, landfill, rubble processing, CEM I, AAC, bricks, sand, lime, gypsum, tap water | full EN 15804 core set (+ additional set for EPD-type datasets) |
| Agro-food ingredients | AGRIBALYSE 4 (v3.2, EF 3.1; ADEME) | proxy profiles for peptones, yeast extract, sugars (agriculture + processing stages only) | full EF 3.1 set |
| Chemicals (urea, CaCl2, Ca-lactate, salts, acids, bases) | literature (Fertilizers Europe 2018, Porter et al. 2021, Deng et al. 2021, Corbion 2020) and engineering estimates | GWP (+ ADP-fossil where available) with min/max ranges; other categories filled from a **scaled proxy profile** (`profile_proxy`) and flagged | GWP native; others proxy |
| Czech electricity | Ember 2023 direct intensity × upstream factor; profile from ÖKOBAUDAT DE 2023 | 0.55 kg CO2e/kWh (0.45–0.75) | GWP native; others proxy |

The recommended ecoinvent dataset name is stored for every background process (`ecoinvent_proxy`)
so that licensed users can replace the open data (see `07_using_ecoinvent_brightway.md`). The
coverage statistics in every result distinguish *native* factors from *proxy-filled* ones.

## 3.5 Uncertainty and sensitivity

* Background: lognormal (pedigree → GSD, Ciroth et al. 2016) or log-triangular between the
  literature range; foreground: triangular between min/max of `scaleup.yaml`.
* `micp-lca monte-carlo <scenario> -n 1000` propagates both; Spearman rank correlations rank
  the inputs.
* `micp-lca sensitivity <scenario>` performs a one-at-a-time analysis (tornado) including discrete
  modelling choices (effluent treatment, lab vs industrial, electricity mix, carbon accounting).
