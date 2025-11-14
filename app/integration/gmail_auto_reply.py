# app/integration/gmail_auto_reply.py
import os
import json
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import pickle

from app.integration.gmail_reader import fetch_latest_email_with_attachments
from app.integration.analyze_vision import analyze_with_vision   # ← 改成 Vision 版

MY_NOTIFY_EMAIL = os.getenv("MY_NOTIFY_EMAIL")

def send_email(to_addr, subject, body, service):
    msg = MIMEMultipart()
    msg["To"] = to_addr
    msg["From"] = MY_NOTIFY_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

def get_gmail_service():
    token_path = "app/integration/token.pickle"
    creds_path = "app/Gmail_Authen/credentials.json"
    creds = None
    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, ["https://www.googleapis.com/auth/gmail.modify"])
            creds = flow.run_local_server(port=0)
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
    return build("gmail", "v1", credentials=creds)

async def process_latest_email_and_reply():
    msg = fetch_latest_email_with_attachments()
    if not msg:
        return {"status": "no email"}

    attachments = msg["files"]  # 这里已经是本地保存好的文件路径列表
    from_addr = msg["from"]
    subject = msg["subject"]

    # 终极一键解析全部文件
    final = analyze_with_vision(attachments)

    # 保存结果
    os.makedirs("attachments/results", exist_ok=True)
    with open("attachments/results/latest.json", "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)

    # 回信
    body = f"您好，系统已自动解析您的清关文件，结果如下：\n\n{json.dumps(final, indent=2, ensure_ascii=False)}\n\n—— Customs AI Gateway"
    service = get_gmail_service()
    send_email(from_addr, f"Re: {subject}", body, service)
    send_email(MY_NOTIFY_EMAIL, f"[Copy] Re: {subject}", body, service)

    return {"status": "ok", "result": final}