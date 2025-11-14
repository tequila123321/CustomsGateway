# app/integration/post_entry_upload.py

import json
from app.integration.entry_xml_builder import build_entry_upload_xml
from app.integration.netchb_client import send_entry_to_netchb
from app.integration.entry_json_mapping import map_to_entry_json  # 正確導入！


def process_entry_from_gpt(gpt_result):
    """ 從 GPT 解析結果生成 entryUpload XML，並提交給 NET CHB """

    # 1. 解析 GPT 結果
    if isinstance(gpt_result, str):
        try:
            gpt = json.loads(gpt_result)
        except Exception as e:
            return {"status": "ERROR", "error": f"解析 GPT 結果失敗: {e}"}
    elif isinstance(gpt_result, dict):
        gpt = gpt_result
    else:
        return {"status": "ERROR", "error": f"不支持的類型: {type(gpt_result)}"}

    # 2. 使用你自己的映射函數！
    try:
        entry_json = map_to_entry_json(gpt)
        print("MAPPED ENTRY_JSON:")
        print(json.dumps(entry_json, indent=2, ensure_ascii=False))
    except Exception as e:
        return {"status": "ERROR", "error": f"映射失敗: {e}"}

    # 3. 生成 XML
    try:
        entry_xml = build_entry_upload_xml(entry_json)
        print("========== entryUpload XML ==========")
        print(entry_xml)
        print("=====================================")
    except Exception as e:
        return {"status": "ERROR", "error": f"生成 XML 失敗: {e}"}

    if not entry_xml or "<entryUpload" not in entry_xml:
        return {"status": "ERROR", "error": "XML 結構不完整"}

    # 4. 發送
    try:
        res = send_entry_to_netchb(entry_xml)
        print("========== NET CHB RESPONSE =========")
        print(res)
        print("=====================================")
        return res
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}