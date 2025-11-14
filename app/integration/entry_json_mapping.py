# app/integration/entry_json_mapping.py

import os
from dotenv import load_dotenv
from typing import Dict, Any, List

load_dotenv()
BROKER_NO = os.getenv("NETCHB_BROKER_NO", "")

# ------------ Port codes ------------
PORT_CODES = {
    "LOS ANGELES": "2704",
    "LONG BEACH": "2709",
    "LA": "2704",
    "LAX": "2720",
    "YANTIAN": "58201",
    "YANTIAN PT": "58201",
}

# ------------ SCAC codes ------------
SCAC_MAP = {
    "ZIM": "ZIMU", "ZIMU": "ZIMU",
    "MATSON": "MATS", "MATS": "MATS",
    "COSCO": "COSU", "COSU": "COSU",
    "ONE": "ONEY", "ONEY": "ONEY",
    "Y309": "ZIMU",  # 你的 firms_code
}


def safe(v):
    if v is None: return None
    if isinstance(v, (int, float)): return str(v)
    return str(v).strip() if isinstance(v, str) else str(v)


def normalize_port(v):
    if not v: return None
    v = safe(v).upper().replace(",", " ").replace("(", " ").replace(")", " ")
    v = " ".join(v.split())
    for name, code in PORT_CODES.items():
        if name in v:
            return code
    return None


def normalize_scac(v):
    if not v: return None
    v = safe(v).upper()
    return SCAC_MAP.get(v, v[:4])


def normalize_country(v):
    v = safe(v).upper() if v else ""
    if len(v) == 2: return v
    if "CHINA" in v: return "CN"
    return "CN"


def map_to_entry_json(raw: Dict[str, Any]) -> Dict[str, Any]:
    summary = raw.get("summary", {}) or {}
    bol = raw.get("bill_of_lading", {}) or {}
    an = raw.get("arrival_notice", {}) or {}
    inv = raw.get("commercial_invoice", {}) or {}

    # Header 字段
    port_of_entry = normalize_port(bol.get("port_of_loading") or an.get("port_of_loading"))
    port_of_unlading = normalize_port(bol.get("port_of_discharge") or an.get("port_of_discharge"))

    carrier_scac = (
            normalize_scac(an.get("firms_code")) or
            normalize_scac(bol.get("ocean_vessel_voy_no")) or
            normalize_scac(summary.get("carrier"))
    )

    hbl = bol.get("house_bl_no") or an.get("house_bl_no") or summary.get("bl_no")
    mbl = bol.get("bl_no") or an.get("master_bl_no") or summary.get("bl_no")

    total_value_usd = summary.get("total_value_usd") or 0

    # Items
    items_src = inv.get("items", []) or []
    items = []
    for it in items_src:
        qty = it.get("quantity_pcs") or it.get("qty_pcs") or 0
        value = it.get("total_value_usd") or 0
        items.append({
            "hs_code": safe(it.get("hs_code")),
            "origin": normalize_country("CN"),
            "value": safe(value),
            "qty": safe(qty),
            "uom": "PCS",
            "mid": None,
            "description": safe(it.get("description_english")),
        })

    # 至少一筆
    if not items:
        items.append({
            "hs_code": "9999.99.99",
            "origin": "CN",
            "value": str(total_value_usd),
            "qty": "1",
            "uom": "PCS",
            "description": "AUTO GENERATED - NO ITEM DETAIL",
        })

    return {
        "entry_type": "01",
        "importer_no": None,
        "broker_no": BROKER_NO,
        "port_of_entry": port_of_entry,
        "port_of_unlading": port_of_unlading,
        "carrier_scac": carrier_scac,
        "hbl": hbl,
        "mbl": mbl,
        "country_of_origin": "CN",
        "total_value_usd": total_value_usd,
        "items": items
    }