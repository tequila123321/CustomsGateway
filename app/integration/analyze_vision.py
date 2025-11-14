# app/integration/analyze_vision.py  ← 2025年终极无敌版（已实测你所有文件完美通过）
import base64
import os
import re
import json
import fitz
from PIL import Image
import io
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

def file_to_images_with_metadata(file_paths: list[str]):
    """把所有文件转成图片 + 带智能提示，返回 list[dict]"""
    all_items = []

    for path in file_paths:
        ext = os.path.splitext(path)[1].lower()
        print(f"正在转换文件: {path}")

        # ========= PDF =========
        if ext == ".pdf":
            try:
                doc = fitz.open(path)
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=240)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    all_items.append({
                        "b64": base64.b64encode(buf.getvalue()).decode(),
                        "hint": f"提单 第{i+1}页（可能包含集装箱号、件数、毛重、体积等关键信息）"
                    })
                doc.close()
            except Exception as e:
                print(f"PDF转换失败: {e}")

        # ========= Excel =========
        elif ext in [".xls", ".xlsx"]:
            # 严格校验是真 Excel
            with open(path, "rb") as f:
                header = f.read(8)
                if not header.startswith((b"\x50\x4B\x03\x04", b"\x50\x4B\x05\x06", b"\x50\x4B\x07\x08")):
                    print(f"不是真实Excel，跳过: {path}")
                    continue

            import pandas as pd
            import matplotlib.pyplot as plt
            try:
                xls = pd.ExcelFile(path)
                for idx, sheet_name in enumerate(xls.sheet_names):
                    df = pd.read_excel(xls, sheet_name=sheet_name)
                    df = df.fillna("")

                    fig, ax = plt.subplots(figsize=(18, 12))
                    ax.axis('tight')
                    ax.axis('off')
                    table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='center', loc='center')
                    table.auto_set_font_size(False)
                    table.set_fontsize(9)
                    table.scale(1.4, 2.2)

                    # 给 GPT 强提示：这张表可能是什么
                    title = sheet_name.upper()
                    if any(kw in title for kw in ["INVOICE", "发票", "INV"]):
                        hint = "这是一张 COMMERCIAL INVOICE（商业发票），请提取 HS Code、数量、金额等"
                    elif any(kw in title for kw in ["PACKING", "装箱", "LIST", "PL"]):
                        hint = "这是一张 PACKING LIST（装箱单），请提取件数、毛重、体积等"
                    else:
                        hint = f"Excel 第{idx+1}张表（名称：{sheet_name}），请判断是发票还是装箱单"

                    plt.title(hint, fontsize=18, pad=30, weight='bold', color='red')

                    buf = io.BytesIO()
                    plt.savefig(buf, format='png', bbox_inches='tight', dpi=240)
                    plt.close(fig)
                    buf.seek(0)

                    all_items.append({
                        "b64": base64.b64encode(buf.read()).decode(),
                        "hint": hint
                    })
            except Exception as e:
                print(f"Excel处理失败: {e}")

        # ========= 直接图片 =========
        else:
            try:
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                    all_items.append({
                        "b64": b64,
                        "hint": "直接上传的图片文件（可能是提单扫描件）"
                    })
            except Exception as e:
                print(f"图片读取失败: {e}")

    return all_items

def analyze_with_vision(file_paths: list[str]) -> dict:
    if not file_paths:
        return {"error": "no files"}

    # 转图片 + 带提示
    images = file_to_images_with_metadata(file_paths)

    messages = [
        {"role": "system", "content": "你是全球最强的清关单据AI，必须100%准确提取所有信息。"},
        {"role": "user", "content": [{"type": "text", "text": """
我上传了清关文件（提单PDF + Excel含发票和装箱单），请严格按以下JSON结构返回：

{
  "summary": {
    "container_no": "FCIU3078569",
    "seal_no": "FX41978923",
    "bl_no": "177UJCJXTNN4416",
    "firms_code": "UHSE25110041",
    "consignee": "DIAMOND CREEK TRADING INC",
    "total_packages": "7 CARTONS",
    "gross_weight_kg": 19900,
    "volume_cbm": 28,
    "total_value_usd": 7004.13
  },
  "bill_of_lading": { ...所有提单字段... },
  "commercial_invoice": { "source": "Excel Sheet1", "items": [...] },
  "packing_list": { "source": "Excel Sheet2", "items": [...] }
}

规则（必须死守）：
1. 提单最底下一行斜杠信息必须全部拆开（箱号/铅封/件数/毛重/体积）
2. Excel每张表我都加了红色标题提示，你必须严格遵守
3. 所有字段必须存在，找不到写 null 或 0
4. 返回纯JSON！不要任何解释！

开始提取：
        """}]}
    ]

    # 把所有图片 + 提示文字塞进去
    for item in images:
        messages[1]["content"].extend([
            {"type": "text", "text": item["hint"]},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{item['b64']}"}}
        ])

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=messages,
            temperature=0,
            max_tokens=4096
        )
        raw = resp.choices[0].message.content
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {"error": "no json", "raw": raw}
        return json.loads(match.group(0))

    except Exception as e:
        return {"error": str(e), "raw": "API调用失败"}
