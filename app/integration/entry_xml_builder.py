# app/integration/entry_xml_builder.py

import xml.etree.ElementTree as ET
from typing import Dict, Any

def to_str(v):
    if v is None:
        return ""
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        for k in ["value", "raw", "text", "name"]:
            if k in v:
                return to_str(v[k])
        return str(v)
    if isinstance(v, list):
        return to_str(v[0]) if v else ""
    return str(v)

def build_entry_upload_xml(entry_json: Dict[str, Any]) -> str:
    """
    生成 <entryUpload>...</entryUpload>，不帶 <uploadEntry>
    不包含 username / password
    """

    root = ET.Element("entryUpload")
    entry = ET.SubElement(root, "entry")

    # ---------------------- HEADER ----------------------
    header = ET.SubElement(entry, "entryHeader")

    # === 關鍵：使用 system-generated 讓 NET CHB 自動生成 entry-no ===
    entry_no_elem = ET.SubElement(header, "entry-no")
    ET.SubElement(entry_no_elem, "system-generated")

    ET.SubElement(header, "entryType").text = to_str(entry_json.get("entry_type"))
    ET.SubElement(header, "importerNo").text = to_str(entry_json.get("importer_no"))
    ET.SubElement(header, "brokerNo").text = to_str(entry_json.get("broker_no"))
    ET.SubElement(header, "portOfEntry").text = to_str(entry_json.get("port_of_entry"))
    ET.SubElement(header, "portOfUnlading").text = to_str(entry_json.get("port_of_unlading"))
    ET.SubElement(header, "carrierSCAC").text = to_str(entry_json.get("carrier_scac"))
    ET.SubElement(header, "houseBOLNumber").text = to_str(entry_json.get("hbl"))
    ET.SubElement(header, "masterBOLNumber").text = to_str(entry_json.get("mbl"))
    ET.SubElement(header, "countryOfOrigin").text = to_str(entry_json.get("country_of_origin"))

    # 🔥 必須是 N（不能自動傳輸）
    ET.SubElement(header, "transmitFlag").text = "N"

    # ---------------------- LINE ITEMS ----------------------
    lineItems = ET.SubElement(entry, "lineItems")
    items = entry_json.get("items") or []

    for idx, it in enumerate(items, start=1):
        li = ET.SubElement(lineItems, "lineItem")
        ET.SubElement(li, "lineNo").text = str(idx)
        ET.SubElement(li, "tariff").text = to_str(it.get("hs_code"))
        ET.SubElement(li, "countryOfOrigin").text = to_str(it.get("origin"))
        ET.SubElement(li, "value").text = to_str(it.get("value"))
        ET.SubElement(li, "quantity").text = to_str(it.get("qty"))
        ET.SubElement(li, "uom").text = to_str(it.get("uom"))
        ET.SubElement(li, "manufacturerId").text = to_str(it.get("mid"))

        if it.get("description"):
            ET.SubElement(li, "description").text = to_str(it.get("description"))

    # ---------------------- TOTALS ----------------------
    totals = ET.SubElement(entry, "totals")
    ET.SubElement(totals, "totalEnteredValue").text = to_str(entry_json.get("total_value_usd"))
    ET.SubElement(totals, "totalLineItems").text = to_str(len(items))

    return ET.tostring(root, encoding="unicode")