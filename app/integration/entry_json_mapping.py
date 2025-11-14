# app/integration/entry_json_mapping.py
"""
把 GPT 解析结果 → 转成 Entry JSON，用来生成 Entry XML。
包含：
✔ 港口名称 → CBP code 自动转换
✔ Carrier 名称 → SCAC 自动转换
✔ 国家名称 → Country code 自动转换
✔ 安全提取字段（避免 dict/list）
"""

import os
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

BROKER_NO = os.getenv("NETCHB_BROKER_NO", "")

# -------------------- Port Code 映射表（CBP 官方代码） --------------------
PORT_CODES = {
    "LONG BEACH": "2709",
    "LOS ANGELES": "2704",
    "LA": "2704",
    "LAX": "2720",
    "SEATTLE": "3001",
    "TACOMA": "3002",
    "OAKLAND": "2811",
    "HOUSTON": "5301",
    "NEW YORK": "1001",
    "SAVANNAH": "1703",
    "MIAMI": "5201",
    "NORFOLK": "1401",
    "CHARLESTON": "1601",
}

# -------------------- SCAC 映射表 --------------------
SCAC_MAP = {
    "MATSON": "MATS",
    "MATS": "MATS",

    "MSC": "MSCU",
    "MEDITERRANEAN": "MSCU",

    "COSCO": "COSU",
    "CHINA COSCO": "COSU",
    "COSU": "COSU",

    "EVERGREEN": "EGLV",
    "EGLV": "EGLV",

    "ONE": "ONEY",
    "OCEAN NETWORK EXPRESS": "ONEY",
    "ONEY": "ONEY",

    "ZIM": "ZIMU",
    "ZIMU": "ZIMU",
}

# -------------------- 国家代码 ISO 映射 --------------------
COUNTRY_MAP = {
    "CHINA": "CN",
    "TAIWAN": "TW",
    "KOREA": "KR",
    "S. KOREA": "KR",
    "VIETNAM": "VN",
    "MEXICO": "MX",
    "USA": "US",
    "UNITED STATES": "US",
}


# -------------------- 安全取值函数 --------------------
def _safe_extract(v):
    """
    无论 GPT 返回 str / dict / list / None，都转换成安全 string。
    """
    if v is None:
        return None

    # Already string?
    if isinstance(v, str):
        return v.strip()

    # numbers
    if isinstance(v, (int, float)):
        return str(v)

    # dict
    if isinstance(v, dict):
        for k in ["value", "raw", "text", "name"]:
            if k in v:
                return _safe_extract(v[k])
        return str(v)

    # list
    if isinstance(v, list):
        if not v:
            return None
        return _safe_extract(v[0])

    # fallback
    return str(v)


# -------------------- 规范化港口（文本 → CBP code）--------------------
def normalize_port(v):
    v = _safe_extract(v)
    if not v:
        return None

    v = v.upper().replace(",", "").strip()

    if v in PORT_CODES:
        return PORT_CODES[v]

    for name, code in PORT_CODES.items():
        if name in v:
            return code

    # 未知港口（可能是代码本身）
    if v.isdigit() and len(v) in (4, 5):
        return v

    return None  # 返回 None 让 NET CHB 返回正确错误提示


# -------------------- 规范化 SCAC --------------------
def normalize_scac(v):
    v = _safe_extract(v)
    if not v:
        return None

    v = v.upper().strip()

    if v in SCAC_MAP:
        return SCAC_MAP[v]

    for k in SCAC_MAP:
        if k in v:
            return SCAC_MAP[k]

    # fallback: 取前4字符
    return v[:4]


# -------------------- 规范化国家代码 --------------------
def normalize_country(v):
    v = _safe_extract(v)
    if not v:
        return "CN"

    v = v.upper().strip()

    if v in COUNTRY_MAP:
        return COUNTRY_MAP[v]

    # fallback：如果是两位字母，可能已经是 ISO code
    if len(v) == 2 and v.isalpha():
        return v

    return "CN"


# -------------------- 主 mapping 函数 --------------------
def map_to_entry_json(raw: Dict[str, Any]) -> Dict[str, Any]:
    summary = raw.get("summary", {}) or {}
    bol = raw.get("bill_of_lading", {}) or {}
    inv = raw.get("commercial_invoice", {}) or {}
    pl = raw.get("packing_list", {}) or {}
    an = raw.get("arrival_notice", {}) or {}

    # --------------- Header 字段 ---------------

    entry_no = _safe_extract(raw.get("entry_no"))
    entry_type = _safe_extract(raw.get("entry_type")) or "01"

    importer_no = (
        _safe_extract(inv.get("importer_no"))
        or _safe_extract(inv.get("importer_id"))
        or _safe_extract(bol.get("importer_no"))
        or None
    )

    port_of_entry = normalize_port(
        bol.get("port_of_entry") or an.get("port_of_entry")
    )

    port_of_unlading = normalize_port(
        bol.get("port_of_discharge") or an.get("port_of_discharge")
    )

    carrier_scac = normalize_scac(
        bol.get("carrier_scac") or an.get("carrier_scac") or summary.get("carrier")
    )

    hbl = _safe_extract(
        bol.get("house_bl_no") or bol.get("hbl") or bol.get("hbl_no")
    )
    mbl = _safe_extract(
        bol.get("master_bl_no") or bol.get("mbl") or bol.get("mbl_no")
    )

    country_of_origin = normalize_country(
        inv.get("country_of_origin") or summary.get("country_of_origin")
    )

    total_value_usd = (
        summary.get("total_value_usd")
        or inv.get("total_value_usd")
        or inv.get("total_amount")
        or 0
    )

    # --------------- Line Items ---------------
    items_src = inv.get("items", []) or []
    items: List[Dict[str, Any]] = []

    for it in items_src:
        items.append({
            "hs_code": _safe_extract(it.get("hs_code") or it.get("hts") or it.get("tariff")),
            "origin": normalize_country(it.get("origin")),
            "value": _safe_extract(it.get("amount") or it.get("total") or it.get("line_total")),
            "qty": _safe_extract(it.get("qty") or it.get("quantity")),
            "uom": _safe_extract(it.get("uom") or it.get("unit") or "PCS"),
            "mid": _safe_extract(it.get("mid") or it.get("manufacturer_id")),
            "description": _safe_extract(it.get("description"))
        })

    entry_json = {
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
        "items": items,
    }

    return entry_json
