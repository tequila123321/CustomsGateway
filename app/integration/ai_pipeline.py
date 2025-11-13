from app.analyze import analyze_file
from app.integration.gmail_reader import fetch_latest_email_with_attachments
import os


async def process_gmail_attachments():
    attachments = fetch_latest_email_with_attachments()
    results = []
    for path in attachments:
        print(f"🧠 解析文件: {path}")
        try:
            if path.lower().endswith(".pdf") or path.lower().endswith(".txt"):
                result = analyze_file(path)
                results.append({"file": path, "result": result})
        except Exception as e:
            print(f"❌ 解析失败 {path}: {e}")
    return results
