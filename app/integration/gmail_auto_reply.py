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
# from app.integration.post_entry_upload import upload_entry_from_gpt_result
from app.integration.post_entry_upload import process_entry_from_gpt


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

# async def process_latest_email_and_reply():
#     msg = fetch_latest_email_with_attachments()
#     if not msg:
#         return {"status": "no email"}
#
#     attachments = msg["files"]  # 这里已经是本地保存好的文件路径列表
#     from_addr = msg["from"]
#     subject = msg["subject"]
#
#     # 终极一键解析全部文件
#     final = analyze_with_vision(attachments)
#
#     # 保存结果
#     os.makedirs("attachments/results", exist_ok=True)
#     with open("attachments/results/latest.json", "w", encoding="utf-8") as f:
#         json.dump(final, f, indent=2, ensure_ascii=False)
#
#     # 回信
#     body = f"您好，系统已自动解析您的清关文件，结果如下：\n\n{json.dumps(final, indent=2, ensure_ascii=False)}\n\n—— Customs AI Gateway"
#     service = get_gmail_service()
#     send_email(from_addr, f"Re: {subject}", body, service)
#     send_email(MY_NOTIFY_EMAIL, f"[Copy] Re: {subject}", body, service)
#
#     return {"status": "ok", "result": final}
async def process_latest_email_and_reply():
    msg = fetch_latest_email_with_attachments()
    if not msg:
        return {"status": "no email"}

    attachments = msg["files"]
    raw_from = msg["from"]
    subject = msg["subject"]

    # 提取纯邮箱地址（防止 "Name <email>" 这种格式）
    import re
    m = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", raw_from)
    if m:
        from_addr = m.group(0)
    else:
        from_addr = MY_NOTIFY_EMAIL

    # 1️⃣ AI 解析清关文件
    final = analyze_with_vision(attachments)

    # 2️⃣ 保存解析结果 JSON
    os.makedirs("attachments/results", exist_ok=True)
    with open("attachments/results/latest.json", "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)

    # 3️⃣ 基于解析结果，尝试生成并上传 Entry 草稿
    # entry_upload_result = upload_entry_from_gpt_result(final)
    entry_upload_result = process_entry_from_gpt(final)

    # 4️⃣ 组织回信内容
    body_parts = []

    body_parts.append("您好，系统已自动解析您的清关文件，初步结果如下（仅供参考）：\n")
    body_parts.append(json.dumps(final, indent=2, ensure_ascii=False))

    # body_parts.append("\n\n--- NET CHB Entry 草稿上传结果（不会自动发送 CBP） ---\n")
    # body_parts.append(f"Status: {entry_upload_result.get('status')}\n")
    # if entry_upload_result.get("entry_no"):
    #     body_parts.append(f"Entry No: {entry_upload_result['entry_no']}\n")
    # if entry_upload_result.get("message"):
    #     body_parts.append(f"Message: {entry_upload_result['message']}\n")
    body_parts.append("\n\n--- NET CHB Entry 草稿上传结果（不会自动发送 CBP） ---\n")

    # ---- 确保 entry_upload_result 一定是 dict ----
    if not isinstance(entry_upload_result, dict):
        body_parts.append(f"Status: UNKNOWN (返回类型: {type(entry_upload_result)})\n")
        body_parts.append(str(entry_upload_result))
    else:
        status = entry_upload_result.get("status", "UNKNOWN")
        body_parts.append(f"Status: {status}\n")

        entry_no = entry_upload_result.get("entry_no")
        if entry_no:
            body_parts.append(f"Entry No: {entry_no}\n")

        msg = entry_upload_result.get("message") or entry_upload_result.get("error")
        if msg:
            body_parts.append(f"Message: {msg}\n")

        # 如果 NET CHB 返回完整 XML，也输出
        raw_resp = entry_upload_result.get("response")
        if raw_resp:
            body_parts.append("\nNET CHB Response:\n")
            body_parts.append(str(raw_resp) + "\n")

    body_parts.append(
        "\n说明：当前为草稿模式（transmitFlag=N），请登录 NET CHB 核对无误后再点击 Transmit 发送给海关。"
    )

    body = "\n".join(body_parts)

    service = get_gmail_service()
    # 回给客户
    send_email(from_addr, f"Re: {subject}", body, service)
    # 抄送给自己
    send_email(MY_NOTIFY_EMAIL, f"[Copy] Re: {subject}", body, service)

    return {
        "status": "ok",
        "result": final,
        "entry_upload": entry_upload_result,
    }
