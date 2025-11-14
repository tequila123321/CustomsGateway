# app/integration/post_entry_upload.py

import json
from app.integration.entry_xml_builder import build_entry_upload_xml
from app.integration.netchb_client import send_entry_to_netchb


def process_entry_from_gpt(gpt_result):
    """
    从 GPT 解析结果生成 entryUpload XML，并提交给 NET CHB。
    一定返回一个 dict: {"status": "...", "response": "...", "error": "..."}
    """

    # gpt_result 可能是 str（JSON 字符串），也可能已经是 dict
    if isinstance(gpt_result, str):
        try:
            gpt = json.loads(gpt_result)
        except Exception as e:
            return {"status": "ERROR", "error": f"解析 GPT 结果出错: {e}", "response": None}
    elif isinstance(gpt_result, dict):
        gpt = gpt_result
    else:
        return {"status": "ERROR", "error": f"不支持的 gpt_result 类型: {type(gpt_result)}", "response": None}

    # 这里按你之前的结构取 entry 部分（根据你实际字段名调整）
    # 比如你在 GPT 里叫 "entry_json" / "entry_upload" / "entry"
    entry_json = (
        gpt.get("entry_json")
        or gpt.get("entry_upload")
        or gpt.get("entry")
        or {}
    )

    try:
        entry_xml = build_entry_upload_xml(entry_json)
    except Exception as e:
        return {"status": "ERROR", "error": f"生成 XML 失败: {e}", "response": None}

    print("========== entryUpload XML ==========")
    print(entry_xml)
    print("=====================================")

    try:
        res = send_entry_to_netchb(entry_xml)
        # send_entry_to_netchb 已经返回 {"status": "...", "response": "...", "error": "..."} 这样的结构
        print("========== NET CHB RESPONSE =========")
        print(res)
        print("=====================================")
        return res
    except Exception as e:
        return {"status": "ERROR", "error": str(e), "response": None}
