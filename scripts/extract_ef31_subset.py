"""Extract the subset of EF 3.1 characterization factors used by micp_lca.

Source: European Commission JRC, Environmental Footprint reference package 3.1,
"EF-LCIAMethod_CF(EF-v3.1).xlsx" (https://eplca.jrc.ec.europa.eu/permalink/EF3_1/EF-LCIAMethod_CF(EF-v3.1).xlsx).
The full workbook (~30 MB) is not committed; run this script with the path to the
downloaded file to regenerate data/lcia/ef31_*.csv.

Usage: python scripts/extract_ef31_subset.py path/to/EF-LCIAMethod_CF(EF-v3.1).xlsx
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "lcia"

# EF 3.1 method name -> (micp_lca code, unit); the codes follow EN 15804+A2 indicator naming.
CATEGORIES = {
    "Climate change": ("GWP-total", "kg CO2 eq"),
    "Climate change-Fossil": ("GWP-fossil", "kg CO2 eq"),
    "Climate change-Biogenic": ("GWP-biogenic", "kg CO2 eq"),
    "Climate change-Land use and land use change": ("GWP-luluc", "kg CO2 eq"),
    "Ozone depletion": ("ODP", "kg CFC-11 eq"),
    "Acidification": ("AP", "mol H+ eq"),
    "Eutrophication, freshwater": ("EP-freshwater", "kg P eq"),
    "Eutrophication marine": ("EP-marine", "kg N eq"),
    "Eutrophication, terrestrial": ("EP-terrestrial", "mol N eq"),
    "Photochemical ozone formation - human health": ("POCP", "kg NMVOC eq"),
    "Resource use, minerals and metals": ("ADP-minerals&metals", "kg Sb eq"),
    "Resource use, fossils": ("ADP-fossil", "MJ"),
    "Water use": ("WDP", "m3 world eq deprived"),
    "EF-particulate Matter": ("PM", "disease incidence"),
    "Ionising radiation, human health": ("IRP", "kBq U-235 eq"),
    "Ecotoxicity, freshwater": ("ETP-fw", "CTUe"),
    "Human toxicity, cancer": ("HTP-c", "CTUh"),
    "Human toxicity, non-cancer": ("HTP-nc", "CTUh"),
    "Land use": ("SQP", "Pt"),
}
CORE = {"GWP-total", "GWP-fossil", "GWP-biogenic", "GWP-luluc", "ODP", "AP", "EP-freshwater",
        "EP-marine", "EP-terrestrial", "POCP", "ADP-minerals&metals", "ADP-fossil", "WDP"}

AIR = ["carbon dioxide (fossil)", "carbon dioxide (biogenic)", "Carbon dioxide (land use change)",
       "methane (fossil)", "methane (biogenic)", "nitrous oxide", "ammonia", "nitrogen dioxide",
       "sulfur dioxide", "particles (PM2.5)", "particles (PM10)", "non-methane volatile organic compounds",
       "carbon monoxide (fossil)", "carbon monoxide (biogenic)", "hydrogen chloride", "urea"]
WATER = ["ammonium", "ammonia", "nitrate", "nitrite", "nitrogen, total (excluding N2)", "phosphate",
         "phosphorus", "phosphorus, total", "chloride", "calcium", "sodium", "potassium", "lactic acid",
         "urea", "nickel (ii)", "sodium chloride", "calcium dichloride", "sodium hydrogen carbonate",
         "potassium chloride", "sodium hydroxide", "hydrogen chloride", "calcium carbonate",
         "calcium hydroxide", "calcium sulfate"]
RESOURCE = ["water", "freshwater", "ground water", "river water", "lake water"]


def main(xlsx: str) -> None:
    import openpyxl

    wb = openpyxl.load_workbook(xlsx, read_only=True)
    ws = wb["lciamethods_CF"]
    rows = [r for r in ws.iter_rows(min_row=2, values_only=True)]
    uuid_by_name: dict[str, str] = {}
    out = []
    for (fuuid, fname, muuid, mname, cf, loc, c0, c1, c2, deriv, _direction) in rows:
        uuid_by_name.setdefault(mname, muuid)
        if mname not in CATEGORIES:
            continue
        loc = loc or ""
        comp = None
        if c0 == "Emissions" and c1 == "Emissions to air" and c2 == "Emissions to air, unspecified" and fname in AIR and loc == "":
            comp = "air"
        elif c0 == "Emissions" and c1 == "Emissions to water" and c2 in ("Emissions to water, unspecified", "Emissions to fresh water") and fname in WATER and loc == "":
            comp = "water" if "unspecified" in c2 else "freshwater"
        elif c0 == "Resources" and fname in RESOURCE and loc in ("", "CZ"):
            comp = "resource"
        if comp is None:
            continue
        out.append(dict(flow_uuid=fuuid, flow_name=fname, compartment=comp, ef31_class2=c2,
                        category_code=CATEGORIES[mname][0], cf=cf, location=loc or "GLO",
                        method_uuid=muuid, derivation=deriv))
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "ef31_impact_categories.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "ef31_name", "unit", "ef31_method_uuid", "en15804_a2_indicator", "core_or_additional"])
        for name, (code, unit) in CATEGORIES.items():
            w.writerow([code, name, unit, uuid_by_name.get(name, ""), code, "core" if code in CORE else "additional"])
    with open(OUT / "ef31_characterization_factors.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"wrote {len(CATEGORIES)} categories and {len(out)} characterization factors to {OUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
