# 1. Goal and scope definition (ISO 14040/14044, EN 15804+A2)

## 1.1 Goal

**Intended application.** Ex-ante (prospective) life-cycle assessment of *biocemented blocks* made
from waste concrete fines (WCF) and sub-sieve (0–4 mm) heterogeneous demolition residues by microbially induced
carbonate precipitation (MICP), as developed by the CTU Prague / UCT Prague group in the eight
papers stored in `papers/`:

| Route | Organism | Key reagents | Papers |
|---|---|---|---|
| Ureolytic | *Sporosarcina pasteurii* DSM 33 | urea + CaCl2 (+ nutrient broth) | Holeček 2024; Kliková 2025 (ESPR); Ottová 2026 |
| Organic-acid oxidation ("carbonic anhydrase") | *Sutcliffiella (Bacillus) cohnii* DSM 6307, *Alkalihalobacillus (Bacillus) pseudofirmus* DSM 8715 | calcium lactate (+ nutrient broth) | Kliková 2025 (CCC); Ottová 2026; Nežerka 2026 preprint |
| Gypsum-promoted (AFt-forming) | *S. cohnii* + 10 wt% waste gypsum plaster | calcium lactate, single dose | Nežerka 2026 preprint |
| Fungal | *Trichoderma reesei* DSM 768 | malt extract + CaCl2 / Ca-lactate | Kliková 2025 (JECE) |
| Alternative media | all | chicken-feather hydrolysate instead of TSB/LB/NB | Ottová 2026 |

**Reasons for carrying out the study.** All papers close with a call for a life-cycle assessment
("*assessing environmental performance through life-cycle analysis*" — Nežerka et al. 2026; "*a
detailed life-cycle analysis is necessary*" — Kliková et al. 2025). The critical review (Nežerka et al.
2023) states that the ureolytic route "*exceeds potential benefits*" environmentally and that
alternatives (waste-derived media, non-ureolytic pathways, effluent treatment) must be evaluated.
The purposes of the database and codebase are therefore:

1. to quantify the environmental profile of every published protocol *as performed* and after
   a transparent scale-up to industrial conditions (identification of hotspots);
2. to compare routes, media and process options (reagent dosing, recirculation, effluent
   treatment, curing temperature) on a consistent basis;
3. to benchmark against conventional masonry products (AAC, clay brick, concrete block,
   sand-lime brick, adobe) and against the group's own WCF–OPC foamed block (Nežerka et al. 2023);
4. to guide further R&D: which parameters must be improved/measured for the technology to be
   environmentally competitive (the *learning* function of ex-ante LCA, van der Giesen et al. 2020).

**Intended audience.** The research group (internal decision support, publication) and, after
critical review, funding bodies and industrial partners (recycling yards, block producers).

**Comparative assertions.** The results are *not* intended for comparative assertions disclosed to
the public in the sense of ISO 14044 §5.3 until (i) the data gaps flagged by the coverage
statistics are closed with licensed background data and (ii) a critical review by an independent
panel is performed. The technology is at TRL 3–4; results are indicative (Bergerson et al. 2020).

## 1.2 Functional unit and reference flows

The default functional unit is **1 kg of dry biocemented product** (cradle-to-gate, modules
A1–A3, plus end-of-life C1–C4 reported separately). Because the products differ in density and
strength, three additional units are implemented (`--fu`):

| FU | Use | Caveat |
|---|---|---|
| `kg_product` | default, EN 15804 declared unit of a masonry unit | ignores performance |
| `m3_product` | volume-based comparison with masonry blocks (walls are dimensioned by volume) | needs bulk density (1100 kg/m3 measured for lab cylinders; 1250 kg/m3 for coarse residues) |
| `m3_MPa` | strength-normalised (volume per MPa of compressive strength) | only for scenarios with measured *f*c; penalises low-strength materials whose use (infill, landscaping, non-load-bearing) does not require strength |
| `kg_caco3_precipitated` | pathway comparison compatible with Porter et al. (2021) and Deng et al. (2021) | only the microbially precipitated CaCO3, not the intrinsic hydration/carbonation |
| `kg_solids` | per kg of waste fines processed (waste-management perspective) | — |

The **reference flow** is the amount of dry input solids (waste fines + waste gypsum) that yields
the functional unit, computed from the protocol (`product_kg_per_kg_solids` = 1 + precipitated
CaCO3 + water bound in AFt phases + retained salts).

## 1.3 System boundary

Cradle-to-gate with options, following the modular structure of EN 15804+A2 (Figure in
`02_system_description.md`):

* **A1** – waste fines after the end-of-waste point (crushing, high-speed milling 6.25 kWh/t and
  mill wear 0.268 kg/t from Nežerka et al. 2023, screening); waste gypsum plaster (grinding);
  production of all chemicals, media components and water.
* **A2** – transport of inputs (fines 70 km by truck-trailer, chemicals 200 km, feathers 80 km,
  gypsum 100 km; NEZERKA2023LCA distances).
* **A3** – cultivation of the microbial suspension (medium sterilisation, fermentation,
  centrifugation), casting/mixing, dosing of the biocementation solution, curing in a heated
  chamber (30 + 30 days at 28–30 °C), drying, effluent treatment, **direct process emissions**
  (CO2 from urea hydrolysis, NH3/NH4+/N2O, chloride, residual organics) and **carbonation uptake**
  of atmospheric CO2 by portlandite in the fines (EN 16757 Annex BB convention).
* **A4–A5, B1–B7** – excluded (identical for all alternatives; no use-phase impacts assumed).
* **C1–C4** – demolition (2 kWh/t), 50 km transport, inert landfill (or rubble processing).
* **D** – optional credits for recovered ammonium sulfate (off by default, reported separately
  as required by EN 15804).

**Cut-off and allocation.** Waste concrete fines, demolition residues, waste gypsum plaster and
chicken feathers are secondary materials entering the system free of upstream burdens
(EN 15804+A2 §6.3.4.6 polluter-pays principle; PEF "cut-off" for waste). Only their processing after
the end-of-waste point is included. Alternative allocation (economic allocation of feathers) is
available as a sensitivity via `gwp_max` of the feather dataset. No multi-output allocation is
needed in the foreground.

**Cut-off criteria.** Capital goods (fermenters, curing chambers, moulds) and laboratory
consumables are excluded; all mass and energy flows described in the protocols are included
(no mass cut-off applied). Infrastructure is expected to contribute < 2 % for a plant with a
multi-year lifetime and is listed as a limitation.

**Geographical/temporal scope.** Czech Republic, reference year 2023–2026; electricity: Czech
grid mix (0.55 kg CO2e/kWh life-cycle, Ember 2023 + upstream), sensitivity with the German 2023
mix; background data 2020–2025.

## 1.4 Impact assessment

The **Environmental Footprint 3.1** method (European Commission JRC), as mandated by EN 15804+A2
and the PEF Recommendation (EU) 2021/2279: 13 core indicators (GWP-total/fossil/biogenic/luluc,
ODP, AP, EP-freshwater, EP-marine, EP-terrestrial, POCP, ADP-minerals&metals, ADP-fossil, WDP)
and 6 additional indicators (PM, IRP, ETP-fw, HTP-c, HTP-nc, SQP). Characterisation factors for the
direct process emissions are the official EF 3.1 factors (`data/lcia`). Normalisation and weighting
are not applied (ISO 14044 optional elements).

**Biogenic carbon** is handled with two switchable conventions (`carbon_accounting`): EF 3.1
(biogenic CO2 = 0, default) and EN 15804+A2 (−1/+1 with release of the stored carbon at C4).
Urea carbon is fossil (captured CO2 of ammonia synthesis) and is modelled explicitly
(see `03_lci_methodology.md`).

## 1.5 Data quality requirements

Foreground data: measured quantities from the papers (recipes, dosing schedules, durations,
temperatures, CaCO3 gains, strengths). Scale-up parameters: engineering estimates with explicit
ranges (Piccinno et al. 2016 framework). Background data: openly licensed EN 15804+A2 datasets
(ÖKOBAUDAT 2024-II), AGRIBALYSE 4 (EF 3.1) and literature values with pedigree scores
(Weidema & Wesnæs 1996; Ciroth et al. 2016). Every value carries a `source_id`. Coverage of each
impact category (share of the inventory with native vs. proxy factors) is reported with every result.

## 1.6 Limitations

* TRL 3–4: no pilot-plant measurements exist; energy and effluent modelling are estimates.
* Non-GWP impact categories of chemicals and media are based on proxy profiles (flagged).
* Mechanical performance (0.15–1.9 MPa) is far below load-bearing masonry; strength-normalised
  comparisons are indicative only.
* Long-term durability (AFt stability, leaching of chlorides/ammonium) is not assessed.
