# 5. Literature review: LCA of MICP / biocementation and related methods

Full citations are in `data/sources/sources.csv` (source ids in brackets).

## 5.1 LCA studies of MICP

| Study | Scope | Main findings relevant to this work |
|---|---|---|
| Porter, Mukherjee, Tuladhar, Dhami (2021), *Sustainability* [PORTER2021] | 1 kg CaCO3 via six metabolic pathways, lab- vs commercial-grade chemicals; SimaPro, ecoinvent v2.2, AUSLCI; carbon footprint, eutrophication, CED, cost | Ureolysis: 2.06 (lab) / 1.51 (commercial) kg CO2/kg CaCO3, eutrophication 0.24 kg SO4-eq (NH4+ waste), CED 28.4 MJ; carbonic-anhydrase route lowest (0.67 / 0.56 kg CO2/kg; 12.9 / 0.62 MJ); CaCl2 dominates embodied energy (44–98 %); recommends waste-derived nutrients and commercial-grade reagents; fermenter energy and transport excluded |
| Deng et al. (2021), *Sustainability* [DENG2021] | 1 t CaCO3 by ureolytic MICP (China; coal-based chemicals), incl. fermenter equipment | 3.4 t CO2 and 1.85 tce per t CaCO3; 80.4 % of CO2 from urea + CaCl2, 19.6 % from cultivation (585 kWh per m3 broth incl. a 15 kW compressor); MICP 3–7× the CO2 of conventional binders in five applications; alternative Ca/urea sources reduce impacts by 8–43 % |
| Alotaibi et al. (2022), *Sci Rep* [ALOTAIBI2022] | EICP vs Portland cement soil stabilisation (10 000 m2 road subgrade, 1.5 MPa); ecoinvent 3.0, CML | EICP −90 % abiotic depletion, −3 % GWP, but higher acidification/eutrophication from urea hydrolysis by-products; IPCC-based on-site N emissions (1 % N2O, 11 % NH3); waste non-fat milk lowers impacts; MICP/EICP better than PC only at low target strength |
| Raymond et al. (2025), *Appl Sci* [RAYMOND2025] | LCSA of augmented vs stimulated MICP in 3.7 m soil columns, NH4+ rinsing | biostimulation and lower ureolytic rates reduce impacts; NH4+ removal is a key cost/impact driver |
| Nežerka et al. (2023), *Rev Environ Sci Biotechnol* [NEZERKA2023REV] | critical review; Porter/Deng synthesis; van Paassen ratios; embodied energies (OPC 6.21, urea 30.54, CaCl2 11.76 MJ/kg) | ureolysis "unacceptable" with primary resources; use by-products (chicken manure effluent −88 % cost, corn steep liquor, lactose mother liquor, food-grade yeast extract), struvite / high-pH rinse for NH4+ (75–99 % removal), extract Ca2+ from WCF; carbonic anhydrase / methane oxidation pathways |
| Nežerka et al. (2023), *J Clean Prod* [NEZERKA2023LCA] | EN 15804+A2 LCA (GaBi) of foamed WCF–OPC blocks; RCF milling data; AAC EPD comparison | 334 kg CO2e/t (81 % from CEM I); linear with PC/RCF ratio (230–435); AAC EPD 232 kg CO2e/m3 — the group's own LCA conventions adopted here |

Other relevant LCAs: Raymond, Kendall & DeJong (2020, *J Geotech Geoenviron Eng*) on ground-improvement methods incl. MICP; bio-brick LCAs of bioMASON-type products (grey literature); "MICP for environmental protection and circular bioeconomy: a critical review" (*Processes* 2026) [MICPREVIEW2026].

**Gaps addressed by this codebase:** none of the published MICP LCAs (i) models the actual
laboratory dosing schedules and their stoichiometric excess, (ii) treats the fate of urea carbon
and nitrogen explicitly with EF 3.1 factors, (iii) covers non-ureolytic (Ca-lactate) and fungal
routes with waste-derived media, (iv) includes the gypsum-promoted AFt route, or (v) applies an
EN 15804+A2 modular structure with curing energy and end of life.

## 5.2 Alternative nutrients, reagents and effluent treatment (used for scenarios)

* Yoosathaporn et al. (2016) [YOOSATHAPORN2016] – chicken manure effluent medium, −88 % cost.
* Achal et al. (2009) [ACHAL2009] – lactose mother liquor; Achal et al. (2010) – corn steep liquor.
* Omoregie et al. (2019) [OMOREGIE2019] – food-grade yeast extract; media ≈ 60 % of MICP cost.
* Ottová et al. (2026) [OTTOVA2026] – feather hydrolysate (this project), −80 % cost.
* Choi et al. (2017) [CHOI2017] – limestone + bio-derived acetic acid as Ca source; eggshells (Choi 2016).
* Gowthaman et al. (2022) [GOWTHAMAN2022] – struvite precipitation of NH4+ (≈75 %); Lee et al. (2019)
  [LEE2019] – high-pH rinse removes up to 99 % aqueous NH4+; Yu et al. (2021) – struvite.
* van Paassen et al. (2010) [VANPAASSEN2010] – 0.6 kg urea + 1.1 kg CaCl2 per kg CaCO3.

## 5.3 Methods for ex-ante / prospective LCA of emerging technologies

* Cucurachi, van der Giesen & Guinée (2018) [CUCURACHI2018]; van der Giesen et al. (2020)
  [VDGIESEN2020] – definition and recommendations (define the future system, scale up, compare
  with the incumbent at the same maturity, uncertainty analysis).
* Piccinno et al. (2016) [PICCINNO2016] – scale-up framework for lab protocols (heating, stirring,
  separation, heat losses) — implemented in `scaleup.yaml` / `inventory.py`.
* Tsoy et al. (2020) [TSOY2020]; Thonemann, Schulte & Maga (2020) [THONEMANN2020];
  Bergerson et al. (2020) [BERGERSON2020] – upscaling methods, TRL-dependent practice.
* Parvatker & Eckelman (2019) – chemical LCI estimation methods (stoichiometric/proxy).

## 5.4 Standards and methods

* ISO 14040:2006, ISO 14044:2006(+A1/A2) [ISO14040]; ISO 14067:2018 [ISO14067].
* EN 15804:2012+A2:2019 [EN15804] (modules, core indicators = EF 3.1, biogenic carbon −1/+1,
  polluter-pays cut-off); EN 16757:2022 [EN16757] (carbonation of concrete products).
* EF 3.1 characterisation factors, JRC [EF31]; PEF Recommendation (EU) 2021/2279 [PEF2021].
* IPCC 2019 Refinement [IPCC2019] (urea CO2 0.20 kg C/kg, N2O EF1 = 1 %); IPCC AR6 GWP100 [IPCC2021].
* Pedigree matrix: Weidema & Wesnæs (1996) [WEIDEMA1996]; Ciroth et al. (2016) [CIROTH2016];
  Muller et al. (2016) [MULLER2016].

## 5.5 Open background databases used

* ÖKOBAUDAT OBD_2024_II (BMWSB, Germany) [OBD2024II] – EN 15804+A2 / EF 3.1 datasets (Sphera).
* AGRIBALYSE 4 (ADEME, France) [AGRIBALYSE4] – EF 3.1 profiles of agro-food products.
* Fertilizers Europe carbon-footprint reference values [FERTEUROPE2018].
* Ember European Electricity Review 2024 [EMBER2024]; EEA electricity intensity indicator [EEA2024].
* CarbonCloud ClimateHub (yeast extract) [CARBONCLOUD2023]; Corbion lactic acid/PLA LCA [CORBION2020].
