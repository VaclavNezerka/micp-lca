# 2. System description

## 2.1 The technology in the papers

```
                 waste concrete / demolition fines (WCF-G, WCF-H, WCF-C, HM1, HM2)
                 recycling yard: crushing -> high-speed milling (6.25 kWh/t) -> screening
                                          |  (A1, A2: 70 km)
   waste gypsum plaster (10 wt%) ---------+
   (recycled plasterboard, ground)        v
                               +---------------------+
   bacterial suspension ------>|  casting / mixing   |<------ saline, HCl (pH 6.8)
   (OD600 = 5 in saline)       |  vibration 45 s     |
        ^                      +----------+----------+
        |                                 v
   cultivation (TSB/LB or        +---------------------+      biocementation solution (BS)
   feather hydrolysate;          |  biocementation     |<---- NB 4 g/L + urea 20 g/L + CaCl2 2.8 g/L   (ureolytic)
   24-48 h, 28-30 C,             |  14-90 d, 28-30 C   |<---- NB 4 g/L + Ca-lactate 11 g/L            (non-ureolytic)
   centrifugation)               |  single/repeated    |      single dose or every 48-72 h
                                 |  dosing             |----> effluent (NH4+, Cl-, residual organics)
                                 +----------+----------+
                                            v
                                 +---------------------+
                                 |  drying/conditioning|----> NH3 (ureolytic route), water vapour
                                 |  21-30 d, 28-30 C   |
                                 +----------+----------+
                                            v
                              biocemented block (fc 0.15-1.9 MPa, ~1100 kg/m3)
                                            |
                                 C1-C4: demolition, 50 km, inert landfill
```

### Materials (data/foreground/materials.yaml)

| id | Origin | Mean size | Portlandite | Notes |
|---|---|---|---|---|
| `wcf_g` | 3-year-old vibro-compacted concrete gutter, 0–0.25 mm ground | 5.1 µm | ~0.5 % | highly carbonated; finest; best stiffness with *S. pasteurii* |
| `wcf_h` | 60-year-old D1 highway concrete, hammer-crushed + high-speed milled | 7.3 µm | ~0.2 % | reference material of most papers |
| `wcf_c` | 1911 reinforced-concrete columns (Walter Motors), coarser | 15.9 µm | 5.5 % | contains gypsum; AFt formation; intrinsic self-cementing (1.9 MPa in abiotic controls) |
| `hm1` | concrete + AAC demolition mix, sub-mm | 223 µm | 0 | consolidates only with bacteria + gypsum |
| `hm2` | masonry mortar + clay brick mix, sub-mm | 226 µm | 0 | strongest heterogeneous residue (0.70 MPa, single dose) |

### Micro-organisms and cultivation (data/foreground/strains.yaml, media.yaml)

* *S. pasteurii* DSM 33: tryptone soya broth 30 g/L + urea 20 g/L, 48 h, 28 °C, 120 rpm; harvest
  by centrifugation; resuspended in saline to OD600 = 5.
* *S. cohnii* DSM 6307 / *A. pseudofirmus* DSM 8715: LB 25 g/L + sodium sesquicarbonate buffer
  (4.2 g/L NaHCO3 + 5.3 g/L Na2CO3), 24 h, 30 °C (or 20 °C), 120–150 rpm; centrifugation; OD600 = 5.
* *T. reesei* DSM 768: mycelial disc from malt extract agar; biocementation solution = malt
  extract broth 20 g/L + CaCl2 2.8 g/L or Ca-lactate 11 g/L.
* Feather hydrolysate (Ottová et al. 2026): feathers 15 g/L, KOH 8 g/L, 100 °C for 0.25 h,
  yeast extract 2–3 g/L, neutralised with HCl; replaces TSB/LB (cultivation) and, diluted 7×,
  NB (biocementation solution). Cost −80 %.

The volume of culture per volume of suspension is `target_OD600 / harvest_OD600` (harvest OD is not
reported; 2.5 assumed, range 1.5–4 in the sensitivity analysis).

### Protocols (data/foreground/protocols.yaml)

Eighteen protocols reproduce the papers one-to-one (solids per specimen, suspension volume,
saline, acid, dose volume and schedule, temperatures, durations, measured CaCO3 gain, porosity,
stiffness and compressive strength). The model derives the number of doses from the dosing
schedule (e.g. 90 d / 60 h = 36 doses) and the reagent balance from the concentrations:

| Protocol | Solids | BS per dose | Doses | BS volume per kg solids | Urea : Ca (mol) | Theoretical CaCO3 | Measured gain |
|---|---|---|---|---|---|---|---|
| `sp_wcf_90d` (Holeček 2024) | 7 g | 10 mL | 36 | 51 L | 13.2 | 13.0 wt% | 9.0 (H) / 11.1 (G) wt% |
| `bc_wcf_30d_ccc` (Kliková 2025) | 10 g | 10 mL | 12 | 12 L | – | 4.3 wt% | ~2 wt% |
| `pre_c_g_30_0` (preprint, prototype recipe) | 26.4 g | 5 mL | 1 | 0.19 L | – | 0.07 wt% | – (strength from gypsum/AFt + hydration) |

The comparison of the theoretical CaCO3 from the calcium supply with the XRD gains reported in the
papers gives precipitation efficiencies of 0.7–0.85 for the 90-day ureolytic protocol, i.e. the
stoichiometric model is consistent with the measurements. Where a reported gain exceeds the calcium
supply (28-day protocols with fewer doses), the model caps the microbial CaCO3 at the calcium supply
and reports a note — the excess is abiotic carbonation of the fines.

## 2.2 Modelling of the scale-up (data/foreground/scaleup.yaml)

Following Piccinno et al. (2016) the laboratory unit operations are translated into industrial
unit operations with physically based energy models (all parameters have ranges for the
uncertainty analysis):

| Lab operation | Industrial model | Central parameters |
|---|---|---|
| Autoclaving of media | continuous steam sterilisation with heat recovery | 15 → 121 °C, cp 4.18 kJ/kg K, 60 % recovery, natural-gas heat |
| Shaking incubator | stirred aerated fermenter | 1.5 kW/m3 (Doran 2013), 24–48 h; 2 kWh/m3/d temperature control |
| Bench centrifuge | disc-stack separator | 1 kWh/m3 |
| Feather hydrolysis on hotplate | heated hydrolysis tank | 15 → 100 °C, 50 % heat recovery |
| Hand mixing / vibration | mixer, vibrating table, moulds | 2.5 kWh/t solids |
| Pipetting of BS | dosing pumps | 0.3 kWh/m3 |
| Incubator at 28–30 °C | insulated curing chamber | U = 0.35 W/m2 K, 3 m2/m3, 2.5 m3/t, ambient 15 °C, 60 d; initial heating of the wet mass |
| Drying in incubator | ambient forced-air drying | 10 kWh/t (thermal drying as alternative) |
| Effluent to drain | basic treatment; optional ammonia stripping (NaOH, H2SO4) or struvite (MgO, H3PO4) | 0.5 kWh/m3; 8 kWh/kg N |

The `lab` parameter set (autoclave 2.2 kW/10 L, shaker 0.15 kW/2 L, incubator 0.08 kW/100
specimens) is kept to demonstrate why laboratory energy must not be used in an LCA: it yields
~180 kg CO2e/kg product (scenario `SP_lab_scale_energy_90d`) — a well-known artefact (Piccinno
et al. 2016; Tsoy et al. 2020).

## 2.3 Benchmarks (data/foreground/scenarios.yaml → benchmarks)

* AAC blocks: German industry average (ÖKOBAUDAT, 428 kg/m3, 207 kg CO2e/m3 A1–A3) and the
  Gasbeton EPD used by Nežerka et al. 2023 (580 kg/m3, 232 kg CO2e/m3).
* WCF–OPC foamed block 40/60 (Nežerka et al. 2023): 334 kg CO2e/t incl. end of life, 7.1 MPa.
* Clay brick, concrete masonry block, sand-lime brick, adobe (ÖKOBAUDAT).
* Status quo of the fines: inert landfill (C4, 0.015 kg CO2e/kg) — used in the system-expansion
  comparison `micp-lca status-quo`.
