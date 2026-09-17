"""Fetch cradle-to-factory-gate EF 3.1 profiles of selected agro-food products from AGRIBALYSE
(ADEME, open licence "Licence Ouverte / Etalab 2.0") and store them as proxy profiles for the
biological media components (peptones, yeast extract, sugars) used in the MICP protocols.

Only the *agriculture* and *transformation* stages are summed (packaging, transport, retail and
consumption are excluded) so that the profiles represent an industrial ingredient at the factory
gate. The profiles are used in two ways:

1. directly as background datasets (``agb_*`` process ids), and
2. as *category profiles* that are scaled by the GWP of a literature-based factor to fill the
   non-GWP impact categories of chemicals whose full EF profile is not openly available
   (``profile_proxy`` column in data/background/background_processes_literature.csv).

Re-run: python scripts/fetch_agribalyse_proxies.py
Data source: AGRIBALYSE 4 (v3.2, EF 3.1) – https://data.ademe.fr (dataset 7yjrtdnoq-ip4mgab1srophe).
"""
from __future__ import annotations

import csv
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "background" / "agribalyse_proxy_profiles.csv"
RAW = ROOT / "data" / "background" / "raw_agribalyse4_detail_par_etape.csv"
URL = "https://data.ademe.fr/data-fair/api/v1/datasets/7yjrtdnoq-ip4mgab1srophe/lines?size=10000&format=csv"

PRODUCTS = {  # AGRIBALYSE code -> (process_id, comment)
    "19054": ("agb_skimmed_milk_powder", "Milk, powder, skimmed – proxy profile for casein-derived peptone/tryptone"),
    "11007": ("agb_gelatine_dried", "Gelatine, dried – proxy profile for animal by-product peptone / beef extract"),
    "20900": ("agb_soya_flour", "Soya flour – proxy profile for soy peptone"),
    "9510": ("agb_maize_starch", "Maize/corn starch – proxy profile for glucose"),
    "31016": ("agb_sugar_white", "Sugar, white – proxy profile for yeast extract, malt extract and lactic acid / calcium lactate (sugar-based fermentation products)"),
    "22004": ("agb_egg_white_powder", "Egg white, powder – alternative animal protein powder profile"),
    "20591_2": ("agb_soy_protein_textured", "Soy protein, textured, dehydrated – alternative plant protein profile"),
}
# French indicator label (prefix before ' - <stage>') -> micp_lca code
CATS = {
    "Changement climatique": "GWP-total",   # the stage table gives only the total climate change indicator
    "Appauvrissement de la couche d'ozone": "ODP",
    "Acidification terrestre et eaux douces": "AP",
    "Eutrophisation eaux douces": "EP-freshwater",
    "Eutrophisation marine ": "EP-marine",   # note the trailing space in the source column
    "Eutrophisation terrestre": "EP-terrestrial",
    "Formation photochimique d'ozone": "POCP",
    "Épuisement des ressources minéraux": "ADP-minerals&metals",
    "Épuisement des ressources énergétiques": "ADP-fossil",
    "Épuisement des ressources eau": "WDP",
    "Particules fines": "PM",
    "Rayonnements ionisants": "IRP",
    "Écotoxicité pour écosystèmes aquatiques d'eau douce": "ETP-fw",
    "Effets toxicologiques sur la santé humaine : substances cancérogènes": "HTP-c",
    "Effets toxicologiques sur la santé humaine : substances non-cancérogènes": "HTP-nc",
    "Utilisation du sol": "SQP",
}
STAGES = ("Agriculture", "Transformation")


def main() -> None:
    if not RAW.exists():
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (micp_lca)"})
        RAW.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    df = pd.read_csv(RAW, encoding="utf-8")
    df["Code AGB"] = df["Code AGB"].astype(str)
    rows = []
    for code, (pid, comment) in PRODUCTS.items():
        sel = df[df["Code AGB"] == code]
        if sel.empty:
            print("not found:", code)
            continue
        r = sel.iloc[0]
        for label, cat in CATS.items():
            total = 0.0
            found = False
            for stage in STAGES:
                col = f"{label} - {stage}"
                if col in df.columns:
                    total += float(r[col])
                    found = True
            if found:
                rows.append(dict(process_id=pid, agribalyse_code=code, lci_name=r["LCI Name"], comment=comment,
                                 category_code=cat, value_per_kg=total, stages="+".join(STAGES)))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(PRODUCTS)} products, {len(rows)} values -> {OUT}")


if __name__ == "__main__":
    main()
