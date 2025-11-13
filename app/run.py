# app/run.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.integration.gmail_auto_reply import process_latest_email_and_reply

app = FastAPI(
    title="Customs AI Gateway",
    version="0.2.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------
# 测试 Root API
# ------------------------------
@app.get("/")
def root():
    return {"message": "Customs AI Gateway is running."}


# ------------------------------
# 主业务：处理最新邮件 → 下载附件 → 分析 → 聚合 → 自动回复
# ------------------------------
@app.get("/process-emails")
async def process_emails():
    """
    主流程：只处理最新邮件 + 自动回信
    """
    return await process_latest_email_and_reply()
