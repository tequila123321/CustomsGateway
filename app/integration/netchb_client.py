# app/integration/netchb_client.py

import os
from dotenv import load_dotenv
from zeep import Client
from zeep.transports import Transport

load_dotenv()

NETCHB_USER = os.getenv("NETCHB_USER")
NETCHB_PASS = os.getenv("NETCHB_PASS")
WSDL_URL = os.getenv("NETCHB_ENTRY_WSDL")

if not WSDL_URL:
    raise ValueError("环境变量 NETCHB_ENTRY_WSDL 未设置")

transport = Transport(timeout=30)
client = Client(WSDL_URL, transport=transport)

def send_entry_to_netchb(entry_xml: str):
    """
    发送 entryXml 字符串到 NETCHB API
    """

    try:
        result = client.service.uploadEntry(NETCHB_USER, NETCHB_PASS, entry_xml)
        return {
            "status": "OK",
            "response": result
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e)
        }
