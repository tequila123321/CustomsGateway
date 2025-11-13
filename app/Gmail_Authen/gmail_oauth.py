# app/Gmail_Authen/gmail_oauth.py

import os
import pickle                      # ✅ 关键：补上这个 import
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# 只读 Gmail 的 scope
SCOPES = ["https://mail.google.com/"]

def get_gmail_service():
    """
    使用本地 token.pickle + credentials.json 获取 Gmail service。
    只在第一次时会打开浏览器让你授权，之后都复用 token.pickle。
    """

    # 以项目根目录为基准，构造相对路径
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    token_path = os.path.join(base_dir, "integration", "token.pickle")
    creds_path = os.path.join(base_dir, "Gmail_Authen", "credentials.json")

    creds = None

    # 1) 先尝试读取 token.pickle
    if os.path.exists(token_path):
        with open(token_path, "rb") as token_file:
            creds = pickle.load(token_file)

    # 2) 如果没有 token，或者过期，就重新走 OAuth 流程
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # 过期但有 refresh_token，直接刷新
            creds.refresh(Request())
        else:
            # 没有 token，走完整的浏览器授权流程
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # 写回 token.pickle，方便下次直接用
        with open(token_path, "wb") as token_file:
            pickle.dump(creds, token_file)

    # 3) 创建 Gmail API 客户端
    service = build("gmail", "v1", credentials=creds)
    return service


if __name__ == "__main__":
    # 单独运行这个文件可以测试是否能正常连接 Gmail
    srv = get_gmail_service()
    print("Gmail service OK:", srv is not None)
