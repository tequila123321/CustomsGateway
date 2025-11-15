# app/integration/entry_json_mapping.py
import os
from dotenv import load_dotenv
from typing import Dict, Any, List

load_dotenv()
BROKER_NO = os.getenv("NETCHB_BROKER_NO", "D9V")  # 你最新设置的

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
    "Y309": "ZIMU",
}

def safe(v):
    if v is None: return ""
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, str): return v.strip()
    return str(v)

def normalize_port(v):
    if not v: return None
    v = safe(v).upper().replace(",", " ").replace("(", " ").replace(")", " ")
    v = " ".join(v.split())
    for name, code in PORT_CODES.items():
        if name in v:
            return code
    return None

def normalize_scac(v):
    if not v: return ""
    v = safe(v).upper()
    return SCAC_MAP.get(v, v[:4])

def normalize_country(v):
    if not v: return "CN"
    v = safe(v).upper()
    if len(v) == 2: return v
    if "CHINA" in v: return "CN"
    return "CN"


# ================================
# 🔥 FINAL FIX: 正确处理 Invoice / PL items
# ================================
def extract_items(inv: Dict[str, Any], pl: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    优先使用 commercial_invoice.items
    如果没有再 fallback 用 packing_list.items
    """

    items_raw = []

    # 优先取 invoice
    if inv and isinstance(inv, dict):
        items_raw = inv.get("items") or []

    # invoice 没有内容 → 使用 packing list
    if not items_raw and pl and isinstance(pl, dict):
        items_raw = pl.get("items") or []

    items = []

    for it in items_raw:
        hs = it.get("HS Code") or it.get("hs_code") or ""
        qty = it.get("Qty") or it.get("quantity") or 0
        val = it.get("Value") or it.get("value") or 0
        uom = it.get("UOM") or "PCS"
        desc = it.get("Description") or ""

        items.append({
            "hs_code": safe(hs),
            "origin": "CN",
            "value": safe(val),
            "qty": safe(qty),
            "uom": safe(uom),
            "mid": None,
            "description": safe(desc),
        })

    return items


# ================================
# 🔥 核心映射函数
# ================================
def map_to_entry_json(raw: Dict[str, Any]) -> Dict[str, Any]:
    summary = raw.get("summary", {}) or {}
    bol = raw.get("bill_of_lading", {}) or {}
    an = raw.get("arrival_notice", {}) or {}
    inv = raw.get("commercial_invoice", {}) or {}
    pl = raw.get("packing_list", {}) or {}

    # Header 字段
    port_of_entry = normalize_port(
        bol.get("port_of_loading")
        or an.get("port_of_loading")
        or summary.get("port_of_loading")
    )

    port_of_unlading = normalize_port(
        bol.get("port_of_discharge")
        or an.get("port_of_discharge")
        or summary.get("port_of_discharge")
    )

    carrier_scac = ""
    mbl = bol.get("master_bl_no") or an.get("master_bl_no") or summary.get("bl_no")

    if mbl:
        carrier_scac = mbl[:4]

    hbl = bol.get("house_bl_no") or an.get("house_bl_no")

    # items 处理
    items = extract_items(inv, pl)

    # 必须至少一项
    if not items:
        items.append({
            "hs_code": "9999.99.99",
            "origin": "CN",
            "value": safe(summary.get("total_value_usd") or 0),
            "qty": "1",
            "uom": "PCS",
            "description": "AUTO GENERATED — NO DETAIL",
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
        "invoice_number": summary.get("invoice_no") or "",
        "country_of_origin": "CN",
        "total_value_usd": summary.get("total_value_usd") or 0,
        "items": items
    }
