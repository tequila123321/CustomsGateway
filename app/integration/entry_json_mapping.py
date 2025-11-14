# 完全适配你当前 GPT 输出结构的 mapping（最终版）

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
    "YANTIAN": "58201",   # optional, CBP often maps CN ports differently
}

# ------------ SCAC codes ------------
SCAC_MAP = {
    "ZIM": "ZIMU",
    "ZIMU": "ZIMU",
    "MATSON": "MATS",
    "MATS": "MATS",
    "COSCO": "COSU",
    "COSU": "COSU",
    "ONE": "ONEY",
    "ONEY": "ONEY",
}

def safe(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return str(v)
    return str(v).strip()

def normalize_port(v):
    if not v:
        return None
    v = safe(v).upper()
    # 去掉括号内容
    v = v.replace("(", " ").replace(")", " ")
    v = " ".join(v.split())
    for name, code in PORT_CODES.items():
        if name in v:
            return code
    return None

def normalize_scac(v):
    if not v:
        return None
    v = safe(v).upper()
    for k, scac in SCAC_MAP.items():
        if k in v:
            return scac
    return v[:4]

def normalize_country(v):
    if not v:
        return "CN"
    v = safe(v).upper()
    if len(v) == 2:
        return v
    if v == "CHINA":
        return "CN"
    return "CN"


def map_to_entry_json(raw: Dict[str, Any]) -> Dict[str, Any]:

    summary = raw.get("summary", {}) or {}
    bol = raw.get("bill_of_lading", {}) or {}
    an = raw.get("arrival_notice", {}) or {}
    inv = raw.get("commercial_invoice", {}) or {}

    # ---------------- Header ----------------
    entry_no = None
    entry_type = "01"

    importer_no = None  # 你 JSON 里暂时没有 importer

    # port_of_entry (from port_of_loading)
    port_of_entry = normalize_port(
        bol.get("port_of_loading") or an.get("port_of_loading")
    )

    # port_of_unlading (from port_of_discharge)
    port_of_unlading = normalize_port(
        bol.get("port_of_discharge") or an.get("port_of_discharge")
    )

    # carrier SCAC （从 vessel 或 summary 或 PDF）
    carrier_scac = normalize_scac(
        bol.get("ocean_vessel_voy_no") or
        summary.get("carrier") or
        an.get("vessel_info")
    )

    # BL numbers
    hbl = bol.get("house_bl_no") or an.get("house_bl_no")
    mbl = bol.get("bl_no") or an.get("master_bl_no")

    country_of_origin = "CN"

    total_value_usd = summary.get("total_value_usd") or 0

    # ---------------- Items ----------------
    items_src = inv.get("items", []) or []
    items = []

    for it in items_src:
        items.append({
            "hs_code": safe(it.get("hs_code")),
            "origin": normalize_country("CN"),
            "value": safe(it.get("total_value_usd")),
            "qty": safe(it.get("qty_pcs")),
            "uom": "PCS",
            "mid": None,
            "description": safe(it.get("description_english")),
        })

    return {
        "entry_no": entry_no,
        "entry_type": entry_type,
        "importer_no": importer_no,
        "broker_no": BROKER_NO,
        "port_of_entry": port_of_entry,
        "port_of_unlading": port_of_unlading,
        "carrier_scac": carrier_scac,
        "hbl": hbl,
        "mbl": mbl,
        "country_of_origin": country_of_origin,
        "total_value_usd": total_value_usd,
        "items": items
    }
