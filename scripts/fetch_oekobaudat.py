"""Download selected ÖKOBAUDAT datasets (EN 15804+A2 / EF 3.1 indicators) and store them as
normalised CSV tables under data/background/oekobaudat/.

ÖKOBAUDAT (German Federal Ministry for Housing, Urban Development and Building, BMWSB) is an
openly licensed database of EN 15804-compliant LCA datasets for construction materials, energy
carriers, transport and end-of-life processes (https://www.oekobaudat.de). The datasets used
here are from data stock OBD_2024_II (release of 2026-07-22, EN 15804+A2 with EF 3.1 methods).

The raw JSON documents are cached in data/background/oekobaudat/raw/ for provenance.
Re-run to refresh: python scripts/fetch_oekobaudat.py
"""
from __future__ import annotations

import csv
import gzip
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "background" / "oekobaudat"
RAW = OUT / "raw"
DATASTOCK = "cc64f7e1-14d8-4a57-b11b-2cf03d200c82"  # OBD_2024_II
BASE = f"https://oekobaudat.de/OEKOBAU.DAT/resource/datastocks/{DATASTOCK}/processes/"

# key -> (uuid, comment)
DATASETS = {
    "cem1_avg": ("87371640-546c-4d9c-84cc-c13b6be94146", "Portland cement CEM I, German average (VDZ), 2022"),
    "cement_avg_D": ("d368f4bb-ae22-4e33-b9e4-22a7b27966c6", "Average cement Germany (VDZ), 2022"),
    "aac_avg": ("e6819670-eb6c-4104-adea-f7f8bb2f49e6", "Autoclaved aerated concrete, German industry average"),
    "ytong_2.5_0.40": ("880239e9-ed96-404f-9184-bd4e004fd650", "Ytong AAC 2.5/0.40 blocks (Xella, RO plant)"),
    "gypsum_dihydrate_ground": ("d142da3c-dd3c-4b95-b500-9be21295b1d9", "Gypsum stone CaSO4.2H2O, ground"),
    "gypsum_beta_hemihydrate": ("69a2614b-ef34-4c3c-9221-963676658172", "Gypsum beta hemihydrate (calcined)"),
    "electricity_DE_2023": ("6edc9cb3-c65a-4b12-8eea-89064c9777d8", "Electricity grid mix Germany 2023, low voltage"),
    "electricity_DE_2022": ("1f732978-fc49-443a-acf7-76e55a915279", "Electricity grid mix Germany 2022, low voltage"),
    "heat_natural_gas": ("2561c686-875a-44e5-8abe-47ec392d16ff", "Thermal energy from natural gas (boiler)"),
    "heat_light_fuel_oil": ("38b9c0c6-bab8-4258-aab7-ada54f12e878", "Thermal energy from light fuel oil"),
    "truck": ("bb74d2a2-249a-4245-a1bb-7bde61f2f613", "Truck (generic lorry), per kg*km"),
    "truck_trailer": ("330f8948-8463-4b63-a14a-3fedcc175180", "Truck-trailer (articulated lorry), per kg*km"),
    "small_truck": ("96115e68-18fe-4cdb-a1e4-ef38d0965929", "Small truck, per kg*km"),
    "landfill_construction_rubble": ("9c1b485e-c801-42ad-bb59-fe209392fc98", "Construction rubble landfill (C4)"),
    "landfill_inert": ("16d08b28-16ca-4918-882f-a3fe11055cb4", "Inert matter landfill (C4)"),
    "rubble_processing": ("a28ca150-de06-4a99-9b8e-6dbb381f69e1", "Construction rubble processing (crushing/sorting, C3)"),
    "sand_0_2": ("286b0072-1001-4e5f-baa2-282230755243", "Sand 0/2, undried"),
    "gravel_2_32": ("d35a5f2a-d72c-41a3-9f64-ea1b1ec066d1", "Gravel 2/32, wet"),
    "crushed_stone_0_2": ("0d61ff01-935e-4934-befe-cb0b2ea18187", "Crushed stone 0/2"),
    "lime_CaO": ("e0673d46-3be4-43b5-af2b-eca25573b68a", "Quicklime CaO, fine lime"),
    "drinking_water": ("63f776af-c722-40f5-a03a-7dc8a438a3a3", "Drinking (tap) water"),
    "brick_unfilled_avg": ("30514538-fcb4-483b-b5d5-c108d2037536", "Clay masonry brick (unfilled), industry average"),
    "adobe_1200": ("4c009f04-44e1-42e3-a32e-4929294debab", "Adobe (unfired earth block) 1200 kg/m3"),
    "concrete_masonry_brick_2000": ("2cdcffc6-84e9-4238-b8af-beebabea9a2d", "Concrete masonry block 2000 kg/m3"),
    "sand_lime_brick_avg": ("cc0d7baa-755a-4a4a-baf3-4fe53d68a041", "Sand-lime brick, industry average"),
    "lwc_block_pumice": ("a1deced7-6fa9-4266-bc86-da75b3653b06", "Lightweight concrete block, natural pumice"),
    "landfill_municipal": ("0debb933-3fab-469d-bed8-a6277908c132", "Municipal waste landfill (C4)"),
    "clay_powder": ("a60489dc-32f2-4ff6-83d2-eb8f4f630ebd", "Clay powder"),
    "recycling_readymix_C20_25": ("8f11c179-e367-4833-93f3-10597923c79c", "Ready-mix concrete C20/25 with recycled aggregate"),
    # ---- extended set (registered automatically as obd_<key> background processes by the loader) ----
    "concrete_C8_10": ("83fae93c-605a-449c-8508-525ea1bc58ba", "Concrete C8/10, industry average (InformationsZentrum Beton)"),
    "concrete_C12_15": ("d9d204f1-453f-401e-8e48-7f078d30054f", "Concrete C12/15, industry average"),
    "concrete_C16_20": ("fee19a6f-6f79-4906-88fd-41e94757aa3c", "Concrete C16/20, industry average"),
    "concrete_C20_25": ("d5d98d4b-a9ba-4fb3-b2d2-6766f8ef5a59", "Concrete C20/25, industry average"),
    "concrete_C25_30": ("8347f9a7-f4ec-4a36-a266-a0281f5fd16d", "Concrete C25/30, industry average"),
    "concrete_C30_37": ("b3fb0ba9-2376-49bf-b21a-7f7a5cd97233", "Concrete C30/37, industry average"),
    "concrete_C35_45": ("90999905-ace2-49ee-90f0-f2a649c8989e", "Concrete C35/45, industry average"),
    "concrete_C50_60": ("5f9cf5f3-c5e1-4b32-8359-a9102f1483ec", "Concrete C50/60, industry average"),
    "readymix_C20_25": ("e3d7a045-ee91-43ac-8fb4-a5216c65ba0b", "Ready-mix concrete C20/25, generic"),
    "readymix_C30_37": ("d6f982e3-beda-49f0-a298-694fcbf3ba38", "Ready-mix concrete C30/37, generic"),
    "readymix_C50_60": ("0a1fa7f9-ad49-4942-a173-cb8c4ad99c9b", "Ready-mix concrete C50/60, generic"),
    "recycling_readymix_C30_37": ("3e15eb88-e824-4a81-972a-45e06930aa19", "Ready-mix concrete C30/37 with recycled aggregate"),
    "cement_CEM_II_32_5": ("0808539c-0cd5-4561-b4a0-058c6f4c7b04", "Cement CEM II 32.5, generic"),
    "cement_CEM_II_42_5": ("1f9e860b-307b-47c3-8cb7-83aff71b0494", "Cement CEM II 42.5, generic"),
    "cement_CEM_II_A": ("aaaedf41-a759-4756-bd55-cd2af3af17f4", "Cement CEM II/A, generic"),
    "cement_CEM_II_B": ("3be4fe78-86d4-4497-9e9d-173b87f321f4", "Cement CEM II/B, generic"),
    "cement_CEM_III_42_5": ("8f4e4fdb-fa6c-46b3-8680-57120c4bee5e", "Cement CEM III 42.5, generic"),
    "cement_CEM_III_A_avg": ("202fc149-0a84-40c8-a5d3-fbb5cdcb55a8", "Blast-furnace cement CEM III/A, industry average (VDZ)"),
    "cement_CEM_IV_32_5": ("75a02ed2-9e8d-4c49-add1-b41b85adf3e7", "Cement CEM IV 32.5, generic"),
    "cement_mortar": ("96171066-34d9-4b33-b1e6-3af1ea11db61", "Cement mortar, generic"),
    "lime_cement_mortar": ("af98c17b-b748-4d08-b5d5-9ff028ae7f25", "Lime cement mortar, generic"),
    "lime_plaster": ("ddc96ae4-086c-4033-9e45-c5589f1661ba", "Lime plaster, generic"),
    "lime_cement_plaster": ("dca9f05c-036b-40e5-ae81-c957c2420fd8", "Lime-cement plaster, generic"),
    "lime_interior_plaster": ("eea7e352-bf1d-4e6d-9029-689d7936e6a7", "Lime interior plaster, generic"),
    "masonry_mortar_lightweight": ("7c0535db-e6d1-4342-871d-74cde862d97a", "Lightweight masonry mortar, industry average"),
    "gypsum_interior_plaster": ("7e0c008a-009d-4357-92c1-afb2cec3bc0a", "Gypsum interior plaster 1000 kg/m3, generic"),
    "gypsum_blocks": ("49151a25-7935-49a4-beca-4422b158c405", "Massive gypsum blocks EN 12859, industry average"),
    "calcium_sulfate_screed": ("3abc810c-ef3a-4ab4-b6d8-0217716e213e", "Calcium sulfate screed, generic"),
    "brick_facing_generic": ("1401638f-b9d7-4b33-9444-b072e2756f49", "Facing brick, clay-based, generic"),
    "brick_facing_avg": ("127a23f5-d954-41c9-8f8a-ecca18aca691", "Facing bricks, industry average"),
    "brick_plan_filled": ("b822aa09-3cb6-49a3-98f6-a3ebf325a70b", "Plan bricks filled with polystyrene, generic"),
    "brick_reuse": ("7f453b20-5b30-4707-bf43-32e2d07a51f9", "DeFries Reuse-Brick (reclaimed brick)"),
    "clay_pavers": ("feaaff18-9f56-437b-aef1-3f63928c1138", "Clay pavers, industry average"),
    "aac_P2_04": ("c5310f2b-23a1-4059-ba25-80d9b3e933f5", "Aerated concrete P2 04, 380 kg/m3, generic"),
    "aac_P4_05": ("f1e6c40e-3f2e-4435-9fd8-abc2dd96c38c", "Aerated concrete P4 05, 500 kg/m3, generic"),
    "aac_granulate": ("01f45a03-460d-4e55-b5c9-72d3e8eda18e", "Aerated concrete granulate 400 kg/m3, generic"),
    "expanded_clay_block_inner": ("5c400482-2153-45e8-a4d2-e10a9338909b", "Expanded clay concrete block, inner wall, 700 kg/m3"),
    "expanded_clay_block_outer": ("23fc083c-960d-4d31-a509-f383e01c3179", "Expanded clay concrete block, outer wall, 500 kg/m3"),
    "expanded_clay_granulate": ("67c9d57a-872a-4614-8be8-37ecaf9952e4", "Expanded clay granulate 4/16"),
    "expanded_clay_sand": ("8ac5659c-5918-41bb-966d-91efdd6c4e50", "Expanded clay sand 0/4"),
    "sand_lime_brick_generic": ("c916ceb3-a44d-40b7-8984-861afa589956", "Sand-lime brick, generic"),
    "natural_aggregates_avg": ("cff84492-d5c8-4da9-a79b-aea5a8507d9d", "Natural aggregates (Naeppi T & N Oy)"),
    "crushed_stone_2_15": ("f501dc99-706c-4b15-aaec-2cca2b409b41", "Crushed stone 2/15"),
    "crushed_stone_16_32": ("f4461491-586a-4770-9a04-716565e58c24", "Crushed stone 16/32"),
    "sand_0_2_dried": ("0d027c8c-89dc-486e-8390-b4649f5e6ed8", "Sand 0/2, dried"),
    "fly_ash_hard_coal": ("90bd318e-7e72-47e7-bdfb-ed6c9309d68a", "Hard coal fly ash (SCM)"),
    "furnace_bottom_ash": ("38b91399-b79d-491a-b172-2343d7b65c0d", "Furnace bottom ash"),
    "reinforcement_steel_wire": ("f6861618-5a92-4c3a-94ba-9f7329b29662", "Reinforcement steel wire, generic"),
    "reinforcing_steel_bars_avg": ("a019c5d1-f6b5-47da-b842-ef094cba850d", "Reinforcing steel bars, industry average"),
    "rammed_earth_wall": ("4b42a944-ff7e-4540-a46b-c21074255143", "Rammed earth wall 2000 kg/m3"),
    "clay_plaster": ("422b2446-8a3f-457d-b47b-4728b2869d86", "Clay plaster 1600 kg/m3"),
    "concrete_paving_stones_avg": ("32d81066-a845-43d0-bd69-c63897f1496f", "Concrete paving stones/slabs, industry average"),
    "precast_concrete_wall_12cm": ("97b971c7-8d43-4650-bfd6-75fdcf9a2101", "Precast concrete wall 12 cm, 291.3 kg/m2"),
    "rail_transport": ("b04a12ef-0842-4ee9-b411-02d8073f0f96", "Rail transport, freight"),
    "barge_transport": ("5b617407-2029-4b47-84d0-2caf10937b1d", "Barge transport (average)"),
    "container_ship": ("c1bfdecc-e167-4c3a-8792-5dc06b97b4b8", "Container ship transport"),
    "excavator_100kW": ("6abf619b-9e1e-4c1d-996b-0458137d3303", "Excavator 100 kW (demolition / loading)"),
    "electricity_DE_2019": ("80e3d34e-6f37-4d1d-94fd-b9694b96223d", "Electricity grid mix Germany 2019"),
    "electricity_DE_2020": ("3981321a-5d7b-43bb-ad86-61c0e20e1359", "Electricity grid mix Germany 2020"),
    "electricity_DE_2021": ("669c531b-aa84-4d04-b96b-aa0f075952b3", "Electricity grid mix Germany 2021"),
    "electricity_DE_2030": ("1ba3d2bb-56ca-416d-866c-959f3e83ca77", "Electricity grid mix scenario 2030"),
    "electricity_DE_2040": ("ea0ec5fe-056c-488a-975e-a229a008f2c5", "Electricity grid mix scenario 2040"),
    "electricity_DE_2050": ("3e2e2e0d-957f-4c34-8a44-d0a177d7ab8e", "Electricity grid mix scenario 2050"),
    "electricity_wind": ("db3d76da-77ee-4e8a-a219-12448236ee27", "Electricity from wind power"),
    "electricity_hydro": ("c840b0e2-d518-48c9-b94f-fa5017872074", "Electricity from hydropower"),
    "electricity_pv": ("7f5a034f-5541-4ac4-90ff-c1c41d7c93db", "Electricity from photovoltaics"),
    "electricity_biogas": ("b4c942fd-5b75-44bd-b04d-0d52737410ea", "Electricity from biogas"),
    "electricity_biomass": ("f70619b5-cc1f-462f-9e98-fbd4bb6bbb2f", "Electricity from biomass"),
    "district_heat_mix_DE": ("bff1909a-5383-49bb-a450-aa9543e7a9ee", "District heating mix Germany"),
    "district_heat_natural_gas": ("b0c5883b-61a5-4855-a76a-73afd45e0da5", "District heating from natural gas"),
    "district_heat_biomass": ("a715dbb0-6fb7-41cb-b2df-d2834414224a", "District heating from solid biomass"),
    "district_heat_waste": ("62ecab6c-10e7-4888-a9ab-e5dbbacf0e93", "District heating from waste incineration"),
    "heat_wood_chips": ("99b94822-b67a-41e9-b97e-87506985f4d5", "Final energy from wood chips (1 kWh, GEG)"),
    "heat_wood_pellets": ("500e3171-60de-4694-ade3-bb0cd3013a17", "Final energy from wood pellets (1 kWh, GEG)"),
    "biogas": ("b1052ab1-97a9-45a1-810a-cdd0a3b1f07a", "Biogas (1 kg)"),
    "light_fuel_oil": ("de4f1273-f63f-4c2e-998c-639cb0e6e2c3", "Light fuel oil (fuel supply)"),
    "wood_incineration_msw": ("53945e96-502a-4c3f-b487-f087b1fabcb7", "Wood-based products incineration in MSW plant"),
    "incineration_domestic_waste": ("e7aeda5d-ac64-45c7-994d-50684b73308f", "Incineration of domestic waste"),
}

# ÖKOBAUDAT indicator label (EN) -> micp_lca code (EN 15804+A2 / EF 3.1)
LCIA_MAP = {
    "Global Warming Potential total (GWP-total)": "GWP-total", "Climate change": "GWP-total",
    "Global Warming Potential fossil fuels (GWP-fossil)": "GWP-fossil", "Climate change-Fossil": "GWP-fossil",
    "Global Warming Potential biogenic (GWP-biogenic)": "GWP-biogenic", "Climate change-Biogenic": "GWP-biogenic",
    "Global Warming Potential luluc (GWP-luluc)": "GWP-luluc", "Climate change-Land use and land use change": "GWP-luluc",
    "Depletion potential of the stratospheric ozone layer (ODP)": "ODP", "Depletion potenzial of the stratospheric ozone layer (ODP)": "ODP",
    "Acidification potential of land and water (AP)": "AP", "Acidifcation potential, Accumulated Exceedance (AP)": "AP",
    "Eutrophication potential aquatic freshwater (EP-freshwater)": "EP-freshwater", "Eutrophication, freshwater": "EP-freshwater",
    "Eutrophication potential aquatic marine (EP-marine)": "EP-marine", "Eutrophication marine": "EP-marine",
    "Eutrophication potential terrestrial (EP-terrestrial)": "EP-terrestrial", "Eutrophication terrestrial": "EP-terrestrial",
    "Eutrophication, terrestrial": "EP-terrestrial",
    "Formation potential of tropospheric ozone photochemical oxidants (POCP)": "POCP", "Photochemical Ozone Creation Potential  (POCP)": "POCP",
    "Abiotic depletion potential for non fossil resources (ADPE)": "ADP-minerals&metals", "Resource use, minerals and metals": "ADP-minerals&metals",
    "Abiotic depletion potential for fossil resources (ADPF)": "ADP-fossil", "Resource use, fossils": "ADP-fossil",
    "Water use (WDP)": "WDP", "Water use": "WDP",
    "Incidence of disease due to PM emissions (PM)": "PM", "Particulate matter": "PM",
    "Human exposure efficiency relative to U235 (IR)": "IRP", "Ionising radiation, human health": "IRP",
    "Comparative toxic unit for ecosystems (ETP-fw)": "ETP-fw", "Ecotoxicity, freshwater": "ETP-fw",
    "Comparative toxic unit for humans (HTP-c)": "HTP-c", "Human toxicity, cancer": "HTP-c",
    "Comparative toxic unit for humans (HTP-nc)": "HTP-nc", "Human toxicity, non-cancer": "HTP-nc",
    "Soil quality index (SQP)": "SQP", "Land use": "SQP",
}
# fallback: EN 15804 short codes given in parentheses at the end of an indicator label, e.g. "... (GWP-total)"
PAREN_CODES = {"GWP-total": "GWP-total", "GWP-fossil": "GWP-fossil", "GWP-biogenic": "GWP-biogenic", "GWP-luluc": "GWP-luluc",
               "ODP": "ODP", "AP": "AP", "EP-freshwater": "EP-freshwater", "EP-marine": "EP-marine", "EP-terrestrial": "EP-terrestrial",
               "POCP": "POCP", "ADPE": "ADP-minerals&metals", "ADPF": "ADP-fossil", "WDP": "WDP", "PM": "PM", "IRP": "IRP", "IR": "IRP",
               "ETP-fw": "ETP-fw", "HTP-c": "HTP-c", "HTP-nc": "HTP-nc", "SQP": "SQP"}


def lcia_code(label: str) -> str:
    if label in LCIA_MAP:
        return LCIA_MAP[label]
    m = re.search(r"\(([A-Za-z&\-]+)\)\s*$", label or "")
    return PAREN_CODES.get(m.group(1), "") if m else ""


EXCHANGE_MAP = {  # resource-use and waste indicators of EN 15804 (declared as exchanges in ILCD/EPD format)
    "PERE": "PERE", "PERM": "PERM", "PERT": "PERT", "PENRE": "PENRE", "PENRM": "PENRM", "PENRT": "PENRT",
    "SM": "SM", "SF": "RSF", "RSF": "RSF", "NRSF": "NRSF", "FW": "FW", "HWD": "HWD", "NHWD": "NHWD",
    "RWD": "RWD", "CRU": "CRU", "MFR": "MFR", "MER": "MER", "EEE": "EEE", "EET": "EET",
}


def en(lst):
    for x in lst or []:
        if x.get("lang") == "en":
            return x.get("value")
    return (lst or [{}])[0].get("value")


def fetch(uuid: str) -> dict:
    """Return the dataset JSON, downloading it once and caching it gzip-compressed for provenance."""
    RAW.mkdir(parents=True, exist_ok=True)
    fn = RAW / f"{uuid}.json.gz"
    legacy = RAW / f"{uuid}.json"
    if legacy.exists() and not fn.exists():   # migrate an uncompressed cache file
        with gzip.open(fn, "wb") as f:
            f.write(legacy.read_bytes())
        legacy.unlink()
    if not fn.exists():
        req = urllib.request.Request(BASE + uuid + "?format=json&view=extended",
                                     headers={"User-Agent": "Mozilla/5.0 (micp_lca)"})
        with gzip.open(fn, "wb") as f:
            f.write(urllib.request.urlopen(req, timeout=60).read())
        time.sleep(0.4)
    with gzip.open(fn, "rb") as f:
        return json.loads(f.read().decode("utf-8"))


def unit_of(anies):
    for a in anies:
        if isinstance(a, dict) and a.get("name") == "referenceToUnitGroupDataSet":
            return a["value"]["shortDescription"][0]["value"]
    return ""


def parse(key: str, uuid: str, comment: str, d: dict, meta_out: list, values_out: list) -> None:
    meta, values = [], []
    pi = d["processInformation"]
    di = pi["dataSetInformation"]
    ex = d.get("exchanges", {}).get("exchange", [])
    ref = [e for e in ex if e.get("referenceFlow")]
    unit = amount = mass_per_ref = None
    refname = ""
    if ref:
        r0 = ref[0]
        refname = en(r0["referenceToFlowDataSet"]["shortDescription"])
        for fp in r0.get("flowProperties", []):
            if fp.get("referenceFlowProperty"):
                unit = fp.get("referenceUnit")
                amount = r0.get("resultingflowAmount", (r0.get("meanAmount") or 1.0) * fp.get("meanValue", 1.0))
            if en(fp.get("name", [])) == "Mass":
                mass_per_ref = fp.get("meanValue")
        for mp in r0.get("materialProperties", []) or []:   # e.g. gross density of bricks declared per m3
            if mp.get("name") == "gross density" and mass_per_ref is None:
                try:
                    mass_per_ref = float(mp.get("value"))
                except (TypeError, ValueError):
                    pass
    if unit == "kgkm":  # transport datasets are declared per 1000 kg*km = 1 t*km
        unit, amount = "tkm", amount / 1000.0
    if unit == "MJ" and abs((amount or 0) - 3.6) < 1e-9:  # energy datasets declared per 3.6 MJ = 1 kWh
        unit, amount = "kWh", 1.0
    mv = d.get("modellingAndValidation", {})
    subtype = ""
    for a in (mv.get("LCIMethodAndAllocation", {}).get("other", {}) or {}).get("anies", []) or []:
        if isinstance(a, dict) and a.get("name") == "subType":
            subtype = a.get("value")
    meta.append(dict(
        key=key, uuid=uuid, name=en(di["name"]["baseName"]), comment=comment, subtype=subtype,
        reference_flow=refname, declared_unit=unit, declared_amount=amount,
        mass_kg_per_declared_unit=mass_per_ref,
        reference_year=pi.get("time", {}).get("referenceYear"),
        valid_until=pi.get("time", {}).get("dataSetValidUntil"),
        geography=pi.get("geography", {}).get("locationOfOperationSupplyOrProduction", {}).get("location"),
        dataset_version=d.get("version"), source_url=BASE + uuid))

    def add(kind, label, code, u, anies):
        for a in anies:
            if isinstance(a, dict) and "module" in a:
                try:
                    v = float(a.get("value"))
                except (TypeError, ValueError):
                    continue
                values.append(dict(key=key, uuid=uuid, kind=kind, indicator_label=label, code=code, unit=u,
                                   module=a["module"], scenario=a.get("scenario", ""), value=v,
                                   value_per_declared_unit=v / (amount or 1.0)))

    for e in ex:
        if e.get("referenceFlow"):
            continue
        label = en(e["referenceToFlowDataSet"]["shortDescription"]) or ""
        an = e.get("other", {}).get("anies", [])
        code = next((v for k, v in EXCHANGE_MAP.items() if f"({k})" in label), "")
        add("exchange", label, code, unit_of(an), an)
    for r in d.get("LCIAResults", {}).get("LCIAResult", []):
        label = en(r["referenceToLCIAMethodDataSet"]["shortDescription"]) or ""
        an = r.get("other", {}).get("anies", [])
        add("lcia", label, lcia_code(label), unit_of(an), an)
    meta_out.extend(meta)
    values_out.extend(values)


def main() -> None:
    meta, values = [], []
    for key, (uuid, comment) in DATASETS.items():
        try:
            parse(key, uuid, comment, fetch(uuid), meta, values)
        except Exception as exc:  # noqa: BLE001
            print("FAILED", key, exc)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "oekobaudat_datasets.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(meta[0].keys()))
        w.writeheader()
        w.writerows(meta)
    with open(OUT / "oekobaudat_indicators.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(values[0].keys()))
        w.writeheader()
        w.writerows(values)
    print(f"{len(meta)} datasets, {len(values)} indicator values written to {OUT}")


if __name__ == "__main__":
    main()
