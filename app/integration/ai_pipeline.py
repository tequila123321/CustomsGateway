# ai_pipeline.py  ← 终极简化版（只用 Vision）
from app.integration.gmail_reader import fetch_latest_email_with_attachments
from app.integration.analyze_vision import analyze_with_vision  # 唯一王者
import os


async def process_gmail_attachments():
    msg = fetch_latest_email_with_attachments()
    if not msg or "files" not in msg:
        return {"status": "no email or attachments"}

    file_paths = msg["files"]
    print(f"发现 {len(file_paths)} 个附件，开始解析...")

    # 一行搞定全部！
    result = analyze_with_vision(file_paths)

    return {
        "status": "ok",
        "processed_files": len(file_paths),
        "files": [os.path.basename(p) for p in file_paths],
        "parsed_result": result
    }