# app/integration/analyze_vision.py
# 终极稳定版（含 Excel 多 Sheet 自动识别 — Invoice / Packing List）

import base64
import os
import re
import json
import io
from typing import List, Dict, Any

import fitz  # PyMuPDF
from PIL import Image
import pandas as pd

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

# 全局安全参数
MAX_PDF_PAGES_TEXT = 10
MAX_PDF_PAGES_IMAGES = 4
MAX_IMAGES_TOTAL = 8
MIN_TEXT_CHARS_FOR_TEXT_MODE = 80
MAX_RAW_IN_ERROR = 800


def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        pass


# ---------------------- PDF → 文本 ---------------------- #

def pdf_to_text(path: str) -> str:
    try:
        doc = fitz.open(path)
    except Exception as e:
        safe_print(f"[PDF] 打开失败: {path} -> {e}")
        return ""

    texts = []
    try:
        for i, page in enumerate(doc):
            if i >= MAX_PDF_PAGES_TEXT:
                break
            try:
                t = page.get_text("text") or ""
                texts.append(t)
            except Exception as e_page:
                safe_print(f"[PDF] 文本提取失败 page {i+1}: {e_page}")
        doc.close()
    except Exception as e:
        safe_print(f"[PDF] 文本抽取崩溃: {path} -> {e}")
        return ""

    return "\n\n".join(texts).strip()


# ---------------------- PDF → 图片（fallback） ---------------------- #

def pdf_to_images(path: str, remaining_quota: int) -> List[Dict[str, Any]]:
    items = []
    if remaining_quota <= 0:
        return items

    try:
        doc = fitz.open(path)
    except Exception as e:
        safe_print(f"[PDF] 打开失败(转图片): {path} -> {e}")
        return items

    max_pages = min(MAX_PDF_PAGES_IMAGES, remaining_quota)

    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        try:
            try:
                pix = page.get_pixmap(dpi=220, alpha=False)
            except Exception:
                pix = page.get_pixmap(alpha=False)

            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

            MAX_W = 2000
            if img.width > MAX_W:
                ratio = MAX_W / img.width
                img = img.resize((MAX_W, int(img.height * ratio)))

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()

            items.append({
                "b64": b64,
                "hint": f"PDF {os.path.basename(path)} 第 {i+1} 页（扫描件）"
            })
        except Exception as e_page:
            safe_print(f"[PDF] 图片转换失败 page {i+1}: {e_page}")
            continue

    doc.close()
    return items


# ---------------------- Excel 自动识别（Invoice / PL） ---------------------- #

def excel_to_sheet_info(path: str):
    """
    返回 Excel 多 Sheet 内容 + 自动识别类型（invoice / packing / unknown）
    """
    try:
        xls = pd.ExcelFile(path)
    except Exception as e:
        safe_print(f"[Excel] 打开失败: {path} -> {e}")
        return []

    results = []

    for sheet_name in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            df = df.fillna("")
            df_head = df.head(20)  # 只取前20行
            text_table = df_head.to_csv(index=False)

            # 自动识别 sheet 类型
            content_str = " ".join(df_head.astype(str).values.flatten()).upper()

            invoice_keywords = [
                "INVOICE", "UNIT PRICE", "PRICE", "AMOUNT",
                "TOTAL", "USD", "HS CODE", "VALUE"
            ]
            packing_keywords = [
                "PACKING", "CARTON", "CARTONS", "GW", "NW",
                "CBM", "DIMENSION", "PACKAGE", "PCS"
            ]

            score_invoice = sum(1 for kw in invoice_keywords if kw in content_str)
            score_packing = sum(1 for kw in packing_keywords if kw in content_str)

            if score_invoice > score_packing and score_invoice > 0:
                sheet_type = "invoice"
            elif score_packing > score_invoice and score_packing > 0:
                sheet_type = "packing_list"
            else:
                sheet_type = "unknown"

            results.append({
                "sheet_name": sheet_name,
                "type": sheet_type,
                "text": text_table
            })

        except Exception as e_sheet:
            safe_print(f"[Excel] 读取 sheet 失败 {sheet_name}: {e_sheet}")
            continue

    return results


# ---------------------- 图片文件 → base64 ---------------------- #

def image_file_to_b64(path: str) -> Dict[str, Any]:
    item = {
        "b64": "",
        "hint": f"图片 {os.path.basename(path)}（扫描件）"
    }
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        item["b64"] = b64
    except Exception as e:
        safe_print(f"[Image] 打开失败: {path} -> {e}")
        item["hint"] += " ⚠️读取失败"
    return item


# ---------------------- 收集附件 payload ---------------------- #

def build_file_payloads(file_paths: List[str]) -> Dict[str, Any]:
    text_chunks = []
    images = []
    remaining_image_quota = MAX_IMAGES_TOTAL

    for path in file_paths:
        ext = os.path.splitext(path)[1].lower()
        safe_print(f"[处理附件] {path}")

        if ext == ".pdf":
            txt = pdf_to_text(path)
            if txt:
                text_chunks.append(
                    f"PDF 文件 {os.path.basename(path)} 的文本内容：\n{txt}\n"
                )

            if len(txt) < MIN_TEXT_CHARS_FOR_TEXT_MODE and remaining_image_quota > 0:
                pdf_imgs = pdf_to_images(path, remaining_image_quota)
                images.extend(pdf_imgs)
                remaining_image_quota -= len(pdf_imgs)

        elif ext in [".xls", ".xlsx"]:
            sheets = excel_to_sheet_info(path)
            for s in sheets:
                if s["type"] == "invoice":
                    tag = "这是一张 Commercial Invoice（商业发票）"
                elif s["type"] == "packing_list":
                    tag = "这是一张 Packing List（装箱单）"
                else:
                    tag = "请判断该表格是发票还是装箱单"

                text_chunks.append(
                    f"Excel {os.path.basename(path)} - Sheet {s['sheet_name']}（自动识别类型：{s['type']}）\n"
                    f"{tag}\n"
                    f"内容（前20行CSV）：\n{s['text']}\n"
                )

        else:
            if remaining_image_quota > 0:
                img_item = image_file_to_b64(path)
                images.append(img_item)
                remaining_image_quota -= 1
            else:
                text_chunks.append(
                    f"图片 {os.path.basename(path)} 被忽略（超过图片上限）。"
                )

    if not text_chunks and not images:
        text_chunks.append("⚠️ 所有附件无法解析，请返回空结构 JSON。")

    return {"text_chunks": text_chunks, "images": images}


# ---------------------- 构造 messages ---------------------- #
def build_messages(payload: Dict[str, Any]):
    text_chunks = payload["text_chunks"]
    images = payload["images"]

    user_content = []

    # =========================== 主提示 ===========================
    user_content.append({
        "type": "text",
        "text": (
            "你是美国清关单据分析 AI，需要从以下文件中提取结构化信息：\n"
            "- 提单 Bill of Lading（Master / House）\n"
            "- 到货通知 Arrival Notice\n"
            "- 商业发票 Commercial Invoice\n"
            "- 装箱单 Packing List\n\n"

            "⚠️ 必须遵守的规则：\n"
            "1. Master BL Number 必须以 4 字母 SCAC 开头（如 ZIMUxxxx、COSUxxxx）。\n"
            "2. House BL Number 不以 4 字母开头，不能与 Master 混淆。\n"
            "3. SCAC = Master BL Number 的前 4 位。\n"
            "4. Arrival Notice 通常包含正确的 Master BL 和 FIRMS CODE → 必须优先使用。\n"
            "5. FIRMS CODE 是必填字段：格式类似 WAC8、Y309、SLB5。\n"
            "6. port_of_entry / port_of_unlading 必须是美国港口，不能输出中国港口（如 Ningbo、Yantian）。\n"
            "   示例：Los Angeles → 2704，Long Beach → 2709，LAX → 2720。\n"
            "7. Invoice items 必须提取：HS Code、Qty、UOM、Value、英文描述。\n"
            "8. 所有字段必须存在，缺失字段填 null 或空数组。\n"
            "9. 仅输出 JSON，不得包含任何解释文字。\n\n"

            "返回的 JSON 结构如下：\n"
            "{\n"
            '  "summary": {\n'
            '    "container_no": null,\n'
            '    "seal_no": null,\n'
            '    "bl_no": null,\n'
            '    "firms_code": null,\n'
            '    "consignee": null,\n'
            '    "invoice_no": null,\n'
            '    "total_packages": null,\n'
            '    "gross_weight_kg": 0,\n'
            '    "volume_cbm": 0,\n'
            '    "total_value_usd": 0\n'
            "  },\n"
            '  "bill_of_lading": {\n'
            '      "master_bl_no": null,\n'
            '      "house_bl_no": null,\n'
            '      "carrier_name": null,\n'
            '      "port_of_loading": null,\n'
            '      "port_of_discharge": null,\n'
            '      "container_no": null,\n'
            '      "seal_no": null,\n'
            '      "packages": null,\n'
            '      "gross_weight_kg": null,\n'
            '      "volume_cbm": null\n'
            "  },\n"
            '  "commercial_invoice": {\n'
            '      "source": null,\n'
            '      "items": []\n'
            "  },\n"
            '  "packing_list": {\n'
            '      "source": null,\n'
            '      "items": []\n'
            "  },\n"
            '  "arrival_notice": {\n'
            '      "master_bl_no": null,\n'
            '      "house_bl_no": null,\n'
            '      "firms_code": null,\n'
            '      "carrier_name": null,\n'
            '      "port_of_loading": null,\n'
            '      "port_of_discharge": null\n'
            "  }\n"
            "}\n"
        )
    })

    # =========================== 文本块 ===========================
    for i, chunk in enumerate(text_chunks, start=1):
        user_content.append({
            "type": "text",
            "text": f"==== 文本块 {i} ====\n{chunk}"
        })

    # =========================== 图片块 ===========================
    for img in images:
        if img.get("hint"):
            user_content.append({"type": "text", "text": img["hint"]})
        if img.get("b64"):
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img['b64']}"}
            })

    messages = [
        {"role": "system", "content": "你是严谨的清关单据结构化专家，只能输出 JSON。"},
        {"role": "user", "content": user_content},
    ]
    return messages

def call_gpt_and_parse_json(messages):
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=messages,
            temperature=0,
            max_tokens=8192
        )
    except Exception as e:
        return {"error": f"OpenAI API 调用失败: {e}"}

    raw = resp.choices[0].message.content or ""
    safe_print("[OpenAI] 返回前300：", raw[:300])

    # 直接解析
    try:
        return json.loads(raw)
    except:
        pass

    # 从 {} 中恢复
    try:
        s = raw.index("{")
        e = raw.rindex("}") + 1
        return json.loads(raw[s:e])
    except Exception as e:
        return {
            "error": f"JSON解析失败: {e}",
            "raw_preview": raw[:MAX_RAW_IN_ERROR]
        }


# ---------------------- 主入口 ---------------------- #

def analyze_with_vision(file_paths: List[str]) -> Dict[str, Any]:
    if not file_paths:
        return {"error": "no files"}

    try:
        payload = build_file_payloads(file_paths)
        messages = build_messages(payload)
        return call_gpt_and_parse_json(messages)
    except Exception as e:
        return {"error": f"analyze_with_vision 崩溃: {e}"}
