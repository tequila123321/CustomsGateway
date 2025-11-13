# app/integration/analyze.py
import os
import fitz
import pandas as pd
from openai import OpenAI


def _read_pdf(path: str) -> str:
    """PDF → text"""
    text = ""
    try:
        with fitz.open(path) as pdf:
            for pg in pdf:
                text += pg.get_text("text") + "\n"
    except Exception as e:
        print("❌ PDF读取失败:", path, e)
    return text.strip()


def _read_excel(path: str) -> str:
    """Excel → 用 pandas 合并所有 sheet → text"""
    text = f"[Excel File: {os.path.basename(path)}]\n\n"
    try:
        xls = pd.ExcelFile(path)
        for sheet in xls.sheet_names:
            text += f"--- Sheet: {sheet} ---\n"
            df = pd.read_excel(path, sheet_name=sheet, dtype=str)
            text += df.to_string() + "\n\n"
    except Exception as e:
        print("❌ EXCEL读取失败:", path, e)
    return text.strip()


def extract_file_content(path: str) -> str:
    """输入文件（xls/pdf）→ 返回纯文本"""
    low = path.lower()
    if low.endswith(".pdf"):
        return _read_pdf(path)
    if low.endswith(".xls") or low.endswith(".xlsx"):
        return _read_excel(path)
    return ""


def analyze_file(path: str) -> dict:
    """核心：GPT 按内容自动判断类型 + 抽取所需字段"""

    text = extract_file_content(path)
    if not text:
        return {"file": path, "doc_type": "unknown", "data": {}}

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""
You are an expert customs document analyzer.

Given the following document text, determine its type:
- bill_of_lading
- commercial_invoice
- packing_list
- arrival_notice
- or unknown

Then extract ONLY the following JSON fields depending on type:

For bill_of_lading:
{{
    "consignee": string or null,
    "container": string or null,
    "booking_number": string or null,
    "packages": string or null
}}

For commercial_invoice:
{{
    "invoice_items": [
        {{
            "english_desc": string,
            "qty": number,
            "hs_code": string or null,
            "total_value": number or null
        }}
    ],
    "total_value": number or null
}}

For packing_list:
{{
    "packing_rows": [
        {{
            "qty": number,
            "gross_weight": number,
            "volume": number or null
        }}
    ],
    "gross_weight_total": number or null
}}

For arrival_notice:
{{
    "firms_code": string or null
}}

Return JSON:
{{
    "doc_type": "...",
    "data": {{ ... }}
}}

Document text:
{text}
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        result = resp.choices[0].message.content
        import json
        clean = result.replace("```json", "").replace("```", "")
        clean = json.loads(clean)
        return {"file": path, **clean}
    except Exception as e:
        print("❌ GPT解析失败:", path, e)
        return {"file": path, "doc_type": "unknown", "data": {}}
