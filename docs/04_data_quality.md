# 4. Data quality, pedigree and known gaps

## 4.1 Pedigree matrix

Every background dataset carries five pedigree scores (1 = best, 5 = worst) in the sense of
Weidema & Wesnæs (1996) as used in ecoinvent:

| Indicator | 1 | 3 | 5 |
|---|---|---|---|
| Reliability (R) | verified data based on measurements | non-verified data partly based on qualified estimates | non-qualified estimate |
| Completeness (C) | representative data from all relevant sites over an adequate period | representative data from only some sites / shorter period | unknown representativeness |
| Temporal correlation (T) | < 3 years difference | < 10 years | > 15 years or unknown |
| Geographical correlation (G) | data from the area under study | data from a larger area including the study area | data from an area with very different conditions |
| Further technological correlation (F) | same technology | related process or material | different technology (laboratory scale / different process) |

The uncertainty factors of Ciroth et al. (2016) convert the scores into a geometric standard
deviation: σg = exp√(Σ ln²UF_i + ln²UB) with the basic uncertainty UB (1.05 for most inputs).

## 4.2 Quality of the main inputs (GWP)

| Input | Central value | Range | Pedigree (R,C,T,G,F) | Comment |
|---|---|---|---|---|
| Urea, EU | 0.878 kg CO2e/kg | 0.75–1.27 | 2,2,3,2,1 | Fertilizers Europe (DNV GL validated); captured CO2 modelled explicitly |
| CaCl2, industrial | 0.854 | 0.30–2.79 | 3,3,4,2,2 | ecoinvent v2.2 (Porter 2021); China HCl route 2.79 (Deng 2021) |
| Calcium lactate pentahydrate | 1.0 | 0.6–3.0 | 3,3,2,2,3 | stoichiometric estimate from lactic acid (Corbion LCA) |
| Tryptone (casein digest) | 12 | 5–25 | 4,3,3,2,4 | **most uncertain and most influential input of the non-ureolytic route** (LB medium) |
| Yeast extract | 3.32 | 1.5–8 | 3,2,1,2,2 | CarbonCloud verified product report |
| Peptone / beef extract | 5 | 2–15 | 4,3,3,2,4 | animal by-product proxies |
| Electricity CZ | 0.55 kg CO2e/kWh | 0.45–0.75 | 2,2,1,1,2 | Ember 2023 + upstream |
| Heat, natural gas | 0.251 kg CO2e/kWh | pedigree | 1,1,1,2,1 | ÖKOBAUDAT |
| Truck transport | 0.111 kg CO2e/tkm | pedigree | 1,1,1,2,1 | ÖKOBAUDAT |
| Inert landfill (C4) | 0.015 kg CO2e/kg | pedigree | 1,1,1,2,1 | ÖKOBAUDAT |

## 4.3 Coverage of impact categories

Every `Results` object reports, per category, the GWP-weighted share of the background inventory
with a *native* factor and the share covered including scaled proxy profiles. Typical values for
the prototype recipe (`GYP_WCFC_single_dose`): GWP 100 % native; AP/EP/POCP/ODP/ADP-minerals/WDP
~28 % native, 100 % incl. proxies; additional indicators (PM, IRP, toxicity, land use) ~49 %
(generic ÖKOBAUDAT datasets do not declare them). **Non-GWP results of the chemical-dominated
scenarios must therefore be read as order-of-magnitude estimates** until licensed background data
are plugged in (`07_using_ecoinvent_brightway.md`).

## 4.4 Foreground assumptions not given in the papers

| Assumption | Value (range) | Why it matters |
|---|---|---|
| Harvest OD600 of the cultures | 2.5 (1.5–4) | scales the medium and fermentation energy per unit of suspension |
| Number of doses for "every 48–72 h" | 60 h interval | ±20 % on reagents and solution volumes |
| Drained effluent share | 40 % (20–70 %) | splits N between NH4+ (water) and NH3 (air) |
| NH3 volatilisation from the drying block | 80 % (50–95 %) | AP and terrestrial eutrophication of the ureolytic route |
| N2O share of hydrolysed N | 0.2 % (0.05–1 %) | 273 kg CO2e/kg — dominates GWP of direct emissions if 1 % |
| Urea hydrolysis extent | 90 % (70–100 %) | CO2 and N releases |
| Carbonation uptake of portlandite | 70 % (0–100 %) | −0.02 kg CO2e/kg for WCF-C |
| Bulk density of the product | 1100 (WCF) / 1250 (HM) kg/m3 | per-m3 comparisons |
| Chamber heat loss, ambient temperature | U 0.35 W/m2 K, 15 °C | curing heat |
| AFt-bound water in gypsum mixes | 3 % of solids | product mass |

## 4.5 Recommended measurements to reduce uncertainty (for the research group)

1. Harvest cell density (OD600 / dry cell weight) of the cultures and the actual volume of
   culture prepared per specimen.
2. Effluent volume and its NH4+, urea, lactate and chloride concentrations for each dosing
   scheme; NH3 emission from drying specimens (mass balance of N).
3. Water content and mass of the specimens before and after drying (bulk density, free water).
4. Energy of a pilot curing chamber (temperature logs) and of a pilot fermenter.
5. Compressive strength and dimensions of prototype blocks (to normalise per m3 and per MPa).
6. TGA/XRD CaCO3 gain for the single-dose gypsum protocol (currently no microbial CaCO3 gain
   is attributed to it; strength originates from AFt/hydration).
