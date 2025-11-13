# app/startup.py
from openai import OpenAI
from dotenv import load_dotenv
import os

# ✅ 自动定位项目根目录并加载 .env 文件
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
print(f"🔍 Loading .env from: {ENV_PATH}")
load_dotenv(dotenv_path=ENV_PATH)


def verify_openai_key():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("⚠️  No OPENAI_API_KEY found in environment variables!")
        return

    try:
        client = OpenAI(api_key=key)
        response = client.models.list()
        models = [m.id for m in response.data[:3]]
        print(f"✅ OpenAI key verified. Available models: {models}")
    except Exception as e:
        print(f"❌ Failed to verify OpenAI API key: {e}")
