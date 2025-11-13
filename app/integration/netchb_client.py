# app/integration/netchb_client.py
from zeep import Client
from lxml import etree
import os, datetime, json


# --- 生成 Entry XML ---------------------------------------------------------
def generate_entry_xml(data: dict) -> str:
    """根据 AI 提取结果构建 NetCHB entry XML"""
    ns = "http://www.netchb.com/xml/entry"
    entry = etree.Element("{%s}entry" % ns, nsmap={None: ns})

    etree.SubElement(entry, "transmit-3461")
    etree.SubElement(entry, "via-ace")

    header = etree.SubElement(entry, "header")
    etree.SubElement(header, "entry-type").text = data.get("entry_type", "86")
    etree.SubElement(header, "entry-port").text = data.get("entry_port", "8888")
    etree.SubElement(header, "importer-tax-id").text = data.get("importer_tax_id", "11-2222222")

    invoices = etree.SubElement(entry, "invoices")
    invoice = etree.SubElement(invoices, "invoice")
    etree.SubElement(invoice, "invoice-no").text = data.get("invoice_no", "AUTO01")

    line_items = etree.SubElement(invoice, "line-items")
    line_item = etree.SubElement(line_items, "line-item")
    etree.SubElement(line_item, "country-origin").text = data.get("country_of_origin", "CN")

    tariffs = etree.SubElement(line_item, "tariffs")
    tariff = etree.SubElement(tariffs, "tariff")
    etree.SubElement(tariff, "tariff-no").text = data.get("hs_code", "12345678")
    etree.SubElement(tariff, "value").text = str(data.get("cargo_value_usd", "100"))

    return etree.tostring(entry, pretty_print=True,
                          xml_declaration=True, encoding="UTF-8").decode()


# --- 上传 Entry -------------------------------------------------------------
def upload_entry(username: str, password: str, entry_xml: str) -> str:
    """调用 NetCHB SOAP uploadEntry 接口"""
    wsdl = "https://www.netchb.com:443/main/services/entry/EntryUploadService?wsdl"
    client = Client(wsdl)
    print("📤 Uploading entry to NetCHB...")
    response = client.service.uploadEntry(username, password, entry_xml)
    print("📥 Response received.")
    return response


# --- 解析返回结果 -----------------------------------------------------------
def parse_netchb_response(xml_response: str) -> dict:
    """解析 NetCHB 返回的 XML"""
    root = etree.fromstring(xml_response.encode("utf-8"))
    tag = etree.QName(root).localname.lower()
    if tag == "accepted":
        entry_no = root.findtext(".//entry-no")
        return {"status": "success", "entry_no": entry_no}
    elif tag == "rejected":
        return {"status": "error", "message": root.text}
    else:
        return {"status": "unknown", "raw": xml_response}


# --- 日志保存 ---------------------------------------------------------------
def save_upload_log(entry_xml: str, response: dict):
    os.makedirs("logs", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"logs/netchb_upload_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"entry_xml": entry_xml, "response": response}, f, indent=2)
    print(f"🧾 Log saved: {path}")
