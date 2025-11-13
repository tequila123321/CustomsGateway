# app/integration/gmail_reader.py
import os
import base64
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText

from app.Gmail_Authen.gmail_oauth import get_gmail_service

ATTACH_DIR = "attachments"


def fetch_latest_email_with_attachments():
    """
    获取 Gmail 中最新一封带附件的邮件。
    返回:
    {
        "from": "...",
        "subject": "...",
        "files": ["attachments/a.pdf", "attachments/b.xls"]
    }
    或 None
    """
    try:
        service = get_gmail_service()

        results = (
            service.users()
            .messages()
            .list(userId="me", q="has:attachment", maxResults=1)
            .execute()
        )

        messages = results.get("messages", [])
        if not messages:
            print("⚠ 没有找到带附件的邮件")
            return None

        msg_id = messages[0]["id"]
        msg = (
            service.users().messages().get(userId="me", id=msg_id).execute()
        )

        # ---------------------
        # 解析邮件头
        # ---------------------
        headers = msg["payload"]["headers"]
        msg_from = next(h["value"] for h in headers if h["name"] == "From")
        subject = next(h["value"] for h in headers if h["name"] == "Subject")

        # ---------------------
        # 下载附件
        # ---------------------
        saved_files = []

        parts = msg["payload"].get("parts", [])
        os.makedirs(ATTACH_DIR, exist_ok=True)

        for part in parts:
            if part.get("filename"):
                attach_id = part["body"]["attachmentId"]
                attach = (
                    service.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=msg_id, id=attach_id)
                    .execute()
                )
                file_data = base64.urlsafe_b64decode(attach["data"])
                save_path = os.path.join(ATTACH_DIR, part["filename"])

                with open(save_path, "wb") as f:
                    f.write(file_data)

                print(f"📥 下载成功: {save_path}")
                saved_files.append(save_path)

        return {
            "from": msg_from,
            "subject": subject,
            "files": saved_files,
        }

    except Exception as e:
        print("❌ Gmail 读取错误:", e)
        return None
