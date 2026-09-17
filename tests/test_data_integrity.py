"""Referential integrity of the data files: every id referenced somewhere must exist."""
from __future__ import annotations

import math


def test_sources_referenced_exist(data):
    ids = set(data.sources)
    for p in data.background.values():
        assert p.source_id in ids, f"background {p.process_id}: unknown source {p.source_id}"
    for name, block in (("protocols", data.protocols), ("materials", data.materials), ("strains", data.strains), ("media", data.media)):
        for k, v in block.items():
            if isinstance(v, dict) and v.get("source_id"):
                assert v["source_id"] in ids, f"{name}/{k}: unknown source {v['source_id']}"


def test_chemicals_link_to_background(data):
    for cid, c in data.chemicals.items():
        if cid.startswith("_") or not isinstance(c, dict):
            continue
        assert c["background_process"] in data.background, f"{cid} -> {c['background_process']} missing"


def test_media_components_are_chemicals(data):
    for mid, m in data.media.items():
        for cid in (m.get("components") or {}):
            assert cid in data.chemicals, f"medium {mid}: unknown chemical {cid}"


def test_protocols_reference_known_entities(data):
    for pid, p in data.protocols.items():
        assert p["strain"] in data.strains, pid
        assert p["material"] in data.materials, pid
        bs = p["biocementation_solution"]
        assert bs["base_medium"] in data.media, pid
        for cid in (bs.get("supplements") or {}):
            assert cid in data.chemicals, f"{pid}: {cid}"
        assert p["incubation"]["duration_d"] > 0


def test_scenarios_reference_known_entities(data):
    for sid, s in data.scenarios["scenarios"].items():
        cfg = data.scenario_config(sid)
        assert cfg["protocol"] in data.protocols, sid
        if cfg.get("material"):
            assert cfg["material"] in data.materials, sid
        assert cfg["electricity"] in data.background, sid
    for bid, b in data.scenarios["benchmarks"].items():
        if "background_process" in b:
            assert b["background_process"] in data.background, bid


def test_background_factors_finite_and_positive(data):
    for p in data.background.values():
        g = p.gwp_any
        assert not math.isnan(g), p.process_id
        if p.data_type != "credit" and not p.process_id.startswith("obd_"):   # biogenic fuels (e.g. biogas) may be negative in ÖKOBAUDAT
            assert g >= 0 or p.process_id.endswith("_credit"), p.process_id
        if p.gwp_min is not None and p.gwp_max is not None and p.gwp > 0:
            assert p.gwp_min <= p.gwp <= p.gwp_max, p.process_id


def test_ef31_characterisation_factors_present(data):
    # key EF 3.1 factors (official values)
    assert data.cf("ammonia", "air", "AP") == 3.02
    assert data.cf("ammonia", "air", "EP-terrestrial") == 13.47
    assert data.cf("ammonium", "water", "EP-marine") == 0.778
    assert data.cf("nitrous oxide", "air", "GWP-total") == 273
    assert data.cf("methane (fossil)", "air", "GWP-total") == 29.8
    assert data.cf("carbon dioxide (fossil)", "air", "GWP-total") == 1.0
    assert data.cf("carbon dioxide (biogenic)", "air", "GWP-total") == 0.0
    assert data.cf("water", "resource", "WDP", location="CZ") == 1.79
    assert data.cf("water", "resource", "WDP") == 42.95


def test_oekobaudat_reference_values(data):
    """Spot checks against the ÖKOBAUDAT datasets (OBD_2024_II)."""
    assert abs(data.background["cement_CEM_I"].gwp - 0.665) < 1e-6           # 665 kg CO2e / t CEM I
    assert abs(data.background["electricity_DE_lv"].gwp - 0.4855) < 1e-3      # kg CO2e / kWh
    assert abs(data.background["transport_truck"].gwp - 0.1107) < 1e-3        # kg CO2e / tkm
    assert abs(data.background["landfill_inert"].factor("GWP-total", "C4") - 0.01496) < 1e-4
    assert abs(data.background["aac_block_avg"].gwp - 206.94 / 428) < 1e-3
    assert abs(data.background["lime_CaO"].gwp - 1.463) < 1e-2


def test_experimental_table_loaded(data):
    assert len(data.experimental) > 50
    assert {"source_id", "property", "value"} <= set(data.experimental.columns)
