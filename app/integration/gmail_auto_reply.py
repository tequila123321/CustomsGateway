# app/integration/gmail_auto_reply.py
# import os
# import base64
# import json
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
#
# from app.integration.gmail_reader import fetch_latest_email_with_attachments
# from app.integration.netchb_aggregator import aggregate_results
# from app.analyze import analyze_file
#
# from googleapiclient.discovery import build
import os
import json
import pickle
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from app.integration.gmail_reader import fetch_latest_email_with_attachments
from app.integration.netchb_aggregator import aggregate_results
from app.analyze import analyze_file  # 注意你这里是 from app.analyze

MY_NOTIFY_EMAIL = os.getenv("MY_NOTIFY_EMAIL")
TOKEN_PATH = "token.pickle"


def send_email(to_addr, subject, body, service, attachment_path=None):
    msg = MIMEMultipart()
    msg["To"] = to_addr
    msg["From"] = MY_NOTIFY_EMAIL
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

#
# async def process_latest_email_and_reply():
#     """核心流程：抓最新 → 下载附件 → 分析 → 聚合 → 回信"""
#
#     msg = fetch_latest_email_with_attachments()
#     if msg is None:
#         return {"status": "no email"}
#
#     from_addr = msg["from"]
#     subject = msg["subject"]
#     attachments = msg["files"]
#
#     # 1. 逐个附件分析
#     parsed = []
#     for f in attachments:
#         r = analyze_file(f)
#         parsed.append(r)
#
#     # 2. 聚合成最终结构
#     final = aggregate_results(parsed)
#
#     # 3. 保存 JSON
#     os.makedirs("attachments/results", exist_ok=True)
#     result_path = "attachments/results/results.json"
#     with open(result_path, "w", encoding="utf-8") as f:
#         json.dump(final, f, indent=2, ensure_ascii=False)
#
#     # 4. 构造邮件内容
#     body = (
#         f"您好，系统已自动提取您发送的清关文件信息。\n\n"
#         f"主题: {subject}\n"
#         f"结果如下：\n\n"
#         f"{json.dumps(final, indent=2, ensure_ascii=False)}\n\n"
#         f"此邮件由 Customs AI Gateway 自动生成。"
#     )

async def process_latest_email_and_reply():
    """核心流程：抓最新 → 下载附件 → 分析 → 聚合 → 回信"""

    msg = fetch_latest_email_with_attachments()
    if msg is None:
        return {"status": "no email"}

    from_addr = msg["from"]
    subject = msg["subject"]
    attachments = msg["files"]

    # 1. 分析附件
    parsed = [analyze_file(f) for f in attachments]

    # 2. 聚合结果
    final = aggregate_results(parsed)

    # 3. 保存 JSON
    os.makedirs("attachments/results", exist_ok=True)
    result_path = "attachments/results/results.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)

    # 4. 构造邮件内容
    body = f"""您好，系统已自动提取您发送的清关文件信息。

主题: {subject}
结果如下：

{json.dumps(final, indent=2, ensure_ascii=False)}

此邮件由 Customs AI Gateway 自动生成。"""

    # 关键：先拿到 service 再发信！
    service = get_gmail_service()   # ← 移到这里来调用

    # 5. 回信给对方
    send_email(from_addr, f"Re: {subject}", body, service)

    # 6. 抄送给自己
    send_email(MY_NOTIFY_EMAIL, f"[Copy] Re: {subject}", body, service)

    # 最后一定要 return！
    return {"status": "ok", "processed": len(attachments), "result": final}

# Gmail API 服务
def get_gmail_service():
    token_path = "app/integration/token.pickle"
    creds_path = "app/Gmail_Authen/credentials.json"

    creds = None

    # 读取 token.pickle
    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    # 若 token 无效，则重新登录（你之前流程）
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                creds_path,
                ["https://www.googleapis.com/auth/gmail.modify"]
            )
            creds = flow.run_local_server(port=0)

        # 保存新 token
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    return build("gmail", "v1", credentials=creds)

    # 5. 发给对方
    send_email(from_addr, f"Re: {subject}", body, service)

    # 6. 同时发给自己
    send_email(MY_NOTIFY_EMAIL, f"[Copy] Re: {subject}", body, service)

    return {"status": "ok", "result": final}
