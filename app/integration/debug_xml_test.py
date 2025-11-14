# app/integration/debug_xml_test.py
"""
调试专用：
把 GPT 解析结果 → Entry JSON → Entry XML
并输出到 debug_output/entry_test.xml
"""

import os
import json
from datetime import datetime

from app.integration.entry_json_mapping import map_to_entry_json
from app.integration.entry_xml_builder import build_entry_upload_xml

DEBUG_DIR = "debug_output"
os.makedirs(DEBUG_DIR, exist_ok=True)


def debug_generate_xml(gpt_json: dict):
    print("\n============================")
    print("DEBUG: INPUT GPT JSON")
    print("============================\n")
    print(json.dumps(gpt_json, indent=2, ensure_ascii=False))

    # Step 1️⃣: JSON → Entry JSON
    entry_json = map_to_entry_json(gpt_json)

    print("\n============================")
    print("DEBUG: MAPPED ENTRY JSON")
    print("============================\n")
    print(json.dumps(entry_json, indent=2, ensure_ascii=False))

    # Step 2️⃣: Entry JSON → Entry Upload XML
    xml_string = build_entry_upload_xml(entry_json)

    print("\n============================")
    print("DEBUG: GENERATED XML")
    print("============================\n")
    print(xml_string)

    # Step 3️⃣: 保存到文件（自动覆盖）
    out_path = os.path.join(DEBUG_DIR, "entry_test.xml")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml_string)

    print(f"\nXML 已写入： {out_path}\n（可用浏览器打开检查是否为空）")

    return xml_string


# ================================
# 允许直接运行调试
# ================================
if __name__ == "__main__":
    test_json_path = "attachments/results/gpt_extracted_jason.json"

    if not os.path.exists(test_json_path):
        print(f"❌ 找不到 GPT JSON：{test_json_path}")
    else:
        data = json.load(open(test_json_path, "r", encoding="utf-8"))
        debug_generate_xml(data)
