import os
import subprocess
import sys
import importlib.util
from openai import OpenAI


def check_python_version():
    print("🐍 Checking Python version...")
    version = sys.version.split()[0]
    print(f"✅ Python {version}")
    if not version.startswith("3.12"):
        print("⚠️  Warning: Recommended version is Python 3.12.x")


def check_pip():
    print("\n📦 Checking pip...")
    try:
        out = subprocess.check_output([sys.executable, "-m", "pip", "--version"]).decode()
        print("✅", out.strip())
    except Exception as e:
        print("❌ pip not working:", e)


def check_package(pkg):
    spec = importlib.util.find_spec(pkg)
    if spec is None:
        print(f"❌ {pkg} not installed")
        return False
    print(f"✅ {pkg} installed")
    return True


def test_fastapi():
    print("\n⚡ Checking FastAPI import...")
    try:
        import fastapi
        print(f"✅ FastAPI {fastapi.__version__}")
    except Exception as e:
        print("❌ FastAPI test failed:", e)


def test_openai_api():
    print("\n🧠 Testing ChatGPT API connection...")
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("⚠️  OPENAI_API_KEY not set in environment.")
        return
    try:
        client = OpenAI(api_key=key)
        response = client.models.list()
        print("✅ OpenAI API reachable. Found models:", [m.id for m in response.data[:3]], "...")
    except Exception as e:
        print("❌ OpenAI API test failed:", e)


def main():
    print("🚀 Customs AI Gateway Environment Check\n")
    check_python_version()
    check_pip()
    required = ["fastapi", "uvicorn", "openai", "lxml", "zeep", "requests"]
    print("\n📋 Checking required packages...\n")
    for pkg in required:
        check_package(pkg)
    test_fastapi()
    test_openai_api()
    print("\n✅ Environment check complete.")


if __name__ == "__main__":
    main()
