"""Stoichiometry, carbon and nitrogen balances of the MICP pathways.

Pathways (see Nežerka et al. 2023, Rev Environ Sci Biotechnol; Kliková et al. 2025; Porter et al. 2021):

* **ureolytic** (Sporosarcina pasteurii; EICP with plant urease)::

      CO(NH2)2 + 2 H2O  --urease-->  2 NH4+ + CO3(2-)
      Ca2+ + CO3(2-)    -->  CaCO3
  Urea carbon is fossil (captured CO2 from ammonia synthesis, Fertilizers Europe 2018); the carbon
  precipitated as CaCO3 is stored, the rest of the hydrolysed urea carbon is released as CO2.
  Nitrogen leaves as NH4+ (effluent) or NH3 (volatilisation from the drying block) with a small
  N2O share.

* **organic-acid oxidation** (Sutcliffiella cohnii, Alkalihalobacillus pseudofirmus; "carbonic
  anhydrase pathway" in the papers; also Bacillus spp. on calcium acetate)::

      Ca(C3H5O3)2 + 6 O2  -->  CaCO3 + 5 CO2 + 5 H2O      (lactate: 1/6 of the carbon fixed)
      Ca(CH3COO)2 + 4 O2  -->  CaCO3 + 3 CO2 + 3 H2O      (acetate: 1/4 of the carbon fixed)
  Lactate carbon is biogenic (sugar fermentation); acetate carbon is fossil for petrochemical
  acetic acid or biogenic for bio-derived acetic acid (Choi et al. 2017).

* **denitrification** (Pseudomonas denitrificans, Castellaniella; van Paassen 2010 biogrout)::

      5 CH3COO- + 8 NO3-  -->  10 CO3(2-)/HCO3- + 4 N2 + ...   (acetate oxidised with nitrate)
  Nitrate-N leaves as N2 (no impact) with an N2O by-product share; residual nitrate to water.

* **photosynthesis** (cyanobacteria): CO2/bicarbonate as inorganic carbon source (atmospheric or
  purchased bicarbonate, geogenic); light energy modelled as electricity in the inventory.

* **metabolic** (fungi such as Trichoderma reesei on malt extract; carbonic-anhydrase-mediated
  hydration of metabolic CO2): carbonate carbon is biogenic and not limiting.
"""
from __future__ import annotations

from dataclasses import dataclass, field

M = {  # molar masses g/mol
    "urea": 60.06, "CaCl2": 110.98, "CaLac5": 308.30, "CaAc": 158.17, "CaNO3_4H2O": 236.15, "NaNO3": 84.99,
    "CaCO3": 100.09, "CO2": 44.01, "NH3": 17.03, "NH4": 18.04, "N2O": 44.01, "N": 14.007, "C": 12.011,
    "Ca": 40.08, "Cl": 35.45, "H2O": 18.015, "Ca(OH)2": 74.09, "HCl": 36.46, "lactate": 89.07,
    "lactic_acid": 90.08, "acetate": 59.04, "acetic_acid": 60.05, "NaCl": 58.44, "NO3": 62.00,
    "NaHCO3": 84.01,
}

CO2_PER_CAOH2 = M["CO2"] / M["Ca(OH)2"]        # 0.5940 kg CO2 per kg portlandite carbonated
CO2_PER_UREA_HYDROLYSED = M["CO2"] / M["urea"]  # 0.7328 kg CO2 per kg urea (IPCC 2019: 0.20 kg C/kg)
N_PER_UREA = 2 * M["N"] / M["urea"]             # 0.4665 kg N per kg urea

# carbon atoms per mole of organic substrate (per anion) and molar mass of the free acid (effluent flow)
ORGANIC_SUBSTRATES = {
    "lactate": {"c_per_mol": 3, "acid_molar_mass": M["lactic_acid"], "effluent_flow": "lactic acid"},
    "acetate": {"c_per_mol": 2, "acid_molar_mass": M["acetic_acid"], "effluent_flow": "acetic acid"},
}


@dataclass
class ReagentBalance:
    """Molar balance of the biocementation reagents for one specimen (mol)."""

    ca_mol: float = 0.0
    urea_mol: float = 0.0
    organic_mol: float = 0.0          # mol organic substrate anions (lactate, acetate)
    organic_kind: str = "lactate"     # key of ORGANIC_SUBSTRATES
    organic_c_origin: str = "biogenic"  # biogenic | fossil
    nitrate_mol: float = 0.0          # mol NO3- (denitrification electron acceptor)
    bicarbonate_mol: float = 0.0      # mol HCO3-/CO3(2-) supplied as inorganic carbon (photosynthesis, geogenic)
    chloride_mol: float = 0.0
    carbonate_source: str = "none"    # urea | organic | inorganic | metabolic
    ca_source: str = "none"

    # backwards compatibility with the first data model (lactate only)
    @property
    def lactate_mol(self) -> float:
        return self.organic_mol if self.organic_kind == "lactate" else 0.0

    @lactate_mol.setter
    def lactate_mol(self, value: float) -> None:
        self.organic_mol, self.organic_kind = value, "lactate"


@dataclass
class ReactionOutcome:
    """Fate of the reagents for one specimen (kg unless noted)."""

    caco3_precipitated_kg: float
    caco3_theoretical_kg: float
    precipitation_efficiency: float
    co2_fossil_kg: float = 0.0        # net fossil CO2 emitted (urea hydrolysis, fossil acetate oxidation)
    co2_biogenic_kg: float = 0.0      # biogenic CO2 from lactate / metabolic oxidation
    c_stored_fossil_kg: float = 0.0   # fossil carbon stored in CaCO3 (as kg CO2)
    c_stored_biogenic_kg: float = 0.0 # biogenic carbon stored in CaCO3 (as kg CO2)
    c_stored_geogenic_kg: float = 0.0 # carbon from purchased bicarbonate stored in CaCO3 (as kg CO2)
    n_total_kg: float = 0.0           # nitrogen in dosed urea
    n_hydrolysed_kg: float = 0.0
    urea_unhydrolysed_kg: float = 0.0
    organic_unoxidised_kg: float = 0.0   # residual organic substrate as free acid
    organic_effluent_flow: str = "lactic acid"
    nitrate_n_denitrified_kg: float = 0.0
    nitrate_residual_kg: float = 0.0  # kg NO3- not denitrified (to effluent)
    chloride_kg: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def lactate_unoxidised_kg(self) -> float:  # backwards compatibility
        return self.organic_unoxidised_kg


def caco3_stoichiometry(balance: ReagentBalance, efficiency: float = 1.0) -> tuple[float, float]:
    """Return (theoretical, expected) CaCO3 mass in kg for the reagent balance (limiting reagent)."""
    if balance.carbonate_source == "urea":
        carbonate = balance.urea_mol
    elif balance.carbonate_source == "organic":
        carbonate = balance.organic_mol * ORGANIC_SUBSTRATES[balance.organic_kind]["c_per_mol"]
    elif balance.carbonate_source == "inorganic":
        carbonate = balance.bicarbonate_mol
    else:  # metabolic / atmospheric CO2 assumed non-limiting
        carbonate = float("inf")
    mol = min(balance.ca_mol, carbonate)
    theoretical = mol * M["CaCO3"] / 1000.0
    return theoretical, theoretical * efficiency


def react(balance: ReagentBalance, *, precipitation_efficiency: float = 1.0,
          measured_caco3_kg: float | None = None, urea_hydrolysed_fraction: float = 0.9,
          lactate_oxidised_fraction: float = 0.9, nitrate_denitrified_fraction: float = 0.9) -> ReactionOutcome:
    """Compute the fate of the reagents.

    ``measured_caco3_kg`` (from XRD gains reported in the papers) overrides the stoichiometric
    estimate but is capped at the theoretical maximum from the calcium supply.
    ``lactate_oxidised_fraction`` applies to any organic substrate (lactate or acetate).
    """
    theoretical, expected = caco3_stoichiometry(balance, precipitation_efficiency)
    notes = []
    if measured_caco3_kg is not None:
        if theoretical > 0 and measured_caco3_kg > theoretical:
            notes.append(f"measured CaCO3 gain {measured_caco3_kg:.4g} kg exceeds the calcium supply "
                         f"({theoretical:.4g} kg); capped (part of the gain is abiotic carbonation).")
            precipitated = theoretical
        else:
            precipitated = measured_caco3_kg
        eff = precipitated / theoretical if theoretical > 0 else float("nan")
    else:
        precipitated, eff = expected, precipitation_efficiency
    out = ReactionOutcome(caco3_precipitated_kg=precipitated, caco3_theoretical_kg=theoretical,
                          precipitation_efficiency=eff, notes=notes)
    caco3_mol = precipitated * 1000.0 / M["CaCO3"]
    if balance.carbonate_source == "urea":
        urea_hydrolysed = balance.urea_mol * urea_hydrolysed_fraction
        c_to_caco3 = min(caco3_mol, urea_hydrolysed)
        out.c_stored_fossil_kg = c_to_caco3 * M["CO2"] / 1000.0
        out.co2_fossil_kg = max(urea_hydrolysed - c_to_caco3, 0.0) * M["CO2"] / 1000.0
        out.n_total_kg = balance.urea_mol * 2 * M["N"] / 1000.0
        out.n_hydrolysed_kg = urea_hydrolysed * 2 * M["N"] / 1000.0
        out.urea_unhydrolysed_kg = (balance.urea_mol - urea_hydrolysed) * M["urea"] / 1000.0
    elif balance.carbonate_source == "organic":
        sub = ORGANIC_SUBSTRATES[balance.organic_kind]
        oxidised = balance.organic_mol * lactate_oxidised_fraction
        c_oxidised = oxidised * sub["c_per_mol"]
        c_to_caco3 = min(caco3_mol, c_oxidised)
        co2_kg = max(c_oxidised - c_to_caco3, 0.0) * M["CO2"] / 1000.0
        stored_kg = c_to_caco3 * M["CO2"] / 1000.0
        if balance.organic_c_origin == "fossil":
            out.co2_fossil_kg, out.c_stored_fossil_kg = co2_kg, stored_kg
        else:
            out.co2_biogenic_kg, out.c_stored_biogenic_kg = co2_kg, stored_kg
        out.organic_unoxidised_kg = (balance.organic_mol - oxidised) * sub["acid_molar_mass"] / 1000.0
        out.organic_effluent_flow = sub["effluent_flow"]
        if balance.nitrate_mol > 0:   # denitrification: nitrate-N to N2 (+ N2O share handled in the inventory)
            denit = balance.nitrate_mol * nitrate_denitrified_fraction
            out.nitrate_n_denitrified_kg = denit * M["N"] / 1000.0
            out.nitrate_residual_kg = (balance.nitrate_mol - denit) * M["NO3"] / 1000.0
    elif balance.carbonate_source == "inorganic":
        out.c_stored_geogenic_kg = min(caco3_mol, balance.bicarbonate_mol) * M["CO2"] / 1000.0
    else:  # metabolic CO2 from the organic medium (biogenic), not limiting
        out.c_stored_biogenic_kg = caco3_mol * M["CO2"] / 1000.0
    out.chloride_kg = balance.chloride_mol * M["Cl"] / 1000.0
    return out


def nitrogen_fate(n_hydrolysed_kg: float, *, fraction_drained: float, nh3_volatilised_fraction: float,
                  n2o_fraction: float, treatment_efficiency: float = 0.0) -> dict[str, float]:
    """Partition hydrolysed urea-N (kg N) into environmental flows.

    Returns kg of substance (not N) for: ``nh4_to_water`` (NH4+), ``nh3_to_air`` (NH3),
    ``n2o_to_air`` (N2O), and kg N for ``n_recovered`` (as fertiliser product) and
    ``n_retained_in_product``.
    """
    n2o_n = n_hydrolysed_kg * n2o_fraction
    n_rest = n_hydrolysed_kg - n2o_n
    n_drained = n_rest * fraction_drained
    n_recovered = n_drained * treatment_efficiency
    n_to_water = n_drained - n_recovered
    n_retained = n_rest - n_drained
    n_volatilised = n_retained * nh3_volatilised_fraction
    n_in_product = n_retained - n_volatilised
    return {
        "nh4_to_water": n_to_water * M["NH4"] / M["N"],
        "nh3_to_air": n_volatilised * M["NH3"] / M["N"],
        "n2o_to_air": n2o_n * M["N2O"] / (2 * M["N"]),
        "n_recovered": n_recovered,
        "n_retained_in_product": n_in_product,
        "n_drained": n_drained,
    }


def carbonation_uptake_kg(portlandite_kg: float, fraction: float) -> float:
    """CO2 taken up from the atmosphere by carbonation of portlandite (kg CO2)."""
    return portlandite_kg * CO2_PER_CAOH2 * fraction
