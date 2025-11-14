# app/integration/analyze_vision.py
# 终极稳定版：本地抽取文本 + Vision 兜底 + 强健错误处理

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
MAX_PDF_PAGES_TEXT = 10          # 每个 PDF 抽取文本页数上限
MAX_PDF_PAGES_IMAGES = 4         # 每个 PDF 转成图片的页数上限
MAX_IMAGES_TOTAL = 8             # 所有附件总图片数上限
MIN_TEXT_CHARS_FOR_TEXT_MODE = 80  # PDF 文本长度阈值，太短则认为是扫描件
MAX_RAW_IN_ERROR = 800           # 错误信息里 raw 文本截断长度


def safe_print(*args, **kwargs):
    """避免某些环境下编码问题导致再次异常"""
    try:
        print(*args, **kwargs)
    except Exception:
        pass


# ---------------------- 基础工具函数 ---------------------- #

def pdf_to_text(path: str) -> str:
    """从 PDF 抽取前几页的文本，失败则返回空字符串"""
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
                safe_print(f"[PDF] 抽取文本失败 {path} page {i+1}: {e_page}")
        doc.close()
    except Exception as e:
        safe_print(f"[PDF] 抽取文本整体失败: {path} -> {e}")
        return ""

    return "\n\n".join(texts).strip()


def pdf_to_images(path: str, remaining_quota: int) -> List[Dict[str, Any]]:
    """
    将 PDF 的前几页转成 PNG base64。
    remaining_quota 表示还允许多少张图片（避免无限膨胀）。
    """
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
            # 尝试高分辨率
            try:
                pix = page.get_pixmap(dpi=220, alpha=False)
            except Exception:
                # fallback
                pix = page.get_pixmap(alpha=False)

            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            # 适当压缩尺寸，避免图片过大
            MAX_W = 2000
            if img.width > MAX_W:
                ratio = MAX_W / img.width
                img = img.resize((MAX_W, int(img.height * ratio)))

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()

            items.append({
                "b64": b64,
                "hint": f"PDF 文件 {os.path.basename(path)} 第 {i+1} 页，可能是提单或到货通知等。"
            })
        except Exception as e_page:
            safe_print(f"[PDF] 转图片失败 {path} page {i+1}: {e_page}")
            continue

    doc.close()
    return items


def excel_to_text(path: str) -> str:
    """
    将 Excel 的每个 sheet 简要转成文本描述：
    Sheet 名 + 前几行的“表格内容”。
    """
    try:
        xls = pd.ExcelFile(path)
    except Exception as e:
        safe_print(f"[Excel] 打开失败: {path} -> {e}")
        return ""

    sheets_text = []
    for sheet_name in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            df = df.fillna("")

            # 只取前 N 行，避免太大
            head_rows = 15
            df_head = df.head(head_rows)

            text_table = df_head.to_csv(index=False)
            sheets_text.append(
                f"Sheet: {sheet_name}\n"
                f"内容预览(前 {head_rows} 行, CSV 格式):\n{text_table}\n"
            )
        except Exception as e_sheet:
            safe_print(f"[Excel] 读取 sheet 失败: {path} sheet={sheet_name} -> {e_sheet}")
            continue

    return "\n\n".join(sheets_text).strip()


def image_file_to_b64(path: str) -> Dict[str, Any]:
    """普通图片文件转 base64，失败返回 hint 提示。"""
    item: Dict[str, Any] = {
        "b64": "",
        "hint": f"图片文件 {os.path.basename(path)}（可能是提单、装箱单或到货通知扫描件）"
    }
    try:
        with open(path, "rb") as f:
            data = f.read()
        # 可以在这里做压缩/缩放，但先简单处理
        b64 = base64.b64encode(data).decode()
        item["b64"] = b64
    except Exception as e:
        safe_print(f"[Image] 打开失败: {path} -> {e}")
        item["hint"] += "，⚠️ 读取失败，请忽略此图。"
    return item


# ---------------------- 聚合所有附件信息 ---------------------- #

def build_file_payloads(file_paths: List[str]) -> Dict[str, Any]:
    """
    综合处理所有附件：
    - text_chunks: 纯文本（PDF 文本、Excel 表格摘要等）
    - images: Vision 用的图片（PDF 扫描件 / 图片附件）
    """
    text_chunks: List[str] = []
    images: List[Dict[str, Any]] = []
    remaining_image_quota = MAX_IMAGES_TOTAL

    for path in file_paths:
        ext = os.path.splitext(path)[1].lower()
        safe_print(f"[处理附件] {path}")

        if ext == ".pdf":
            # 先抽文本
            txt = pdf_to_text(path)
            if txt:
                text_chunks.append(
                    f"以下是 PDF 文件 {os.path.basename(path)} 的文本内容（前 {MAX_PDF_PAGES_TEXT} 页）：\n{txt}\n"
                )

            # 如果文本很短，认为是扫描件，再加图片给 Vision
            if len(txt) < MIN_TEXT_CHARS_FOR_TEXT_MODE and remaining_image_quota > 0:
                pdf_imgs = pdf_to_images(path, remaining_image_quota)
                images.extend(pdf_imgs)
                remaining_image_quota -= len(pdf_imgs)

        elif ext in [".xls", ".xlsx"]:
            txt = excel_to_text(path)
            if txt:
                # 给 GPT 强提示：这是 Invoice / Packing List
                upper_name = os.path.basename(path).upper()
                if any(k in upper_name for k in ["INVOICE", "INV"]):
                    tag = "这应该是 COMMERCIAL INVOICE（商业发票）"
                elif any(k in upper_name for k in ["PACKING", "PL", "装箱"]):
                    tag = "这应该是 PACKING LIST（装箱单）"
                else:
                    tag = "请判断该表格是发票还是装箱单"

                text_chunks.append(
                    f"以下是 Excel 文件 {os.path.basename(path)} 的内容摘要（{tag}）：\n{txt}\n"
                )

        else:
            # 其它视为图片
            if remaining_image_quota > 0:
                img_item = image_file_to_b64(path)
                images.append(img_item)
                remaining_image_quota -= 1
            else:
                text_chunks.append(
                    f"有一个图片附件 {os.path.basename(path)}，但已超过最大图片数量限制，请你根据其他信息完成提取。"
                )

    if not text_chunks and not images:
        text_chunks.append("⚠️ 所有附件都无法解析，请你根据有限信息返回空字段 JSON。")

    return {"text_chunks": text_chunks, "images": images}


# ---------------------- 调 GPT 获取结构化 JSON ---------------------- #

def build_messages(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """构造发给 GPT 的 messages（文本 + 可选图片）。"""
    text_chunks = payload["text_chunks"]
    images = payload["images"]

    user_content: List[Dict[str, Any]] = []

    # 说明任务 & 结构
    user_content.append({
        "type": "text",
        "text": (
            "你是专业的美国报关单据分析 AI，请根据我提供的所有文本和图片，"
            "提取提单(B/L)、商业发票(Commercial Invoice)、装箱单(Packing List)、"
            "以及到货通知(Arrival Notice)中的信息，并严格按以下 JSON 结构返回（字段全部保留）：\n\n"
            "{\n"
            '  "summary": {\n'
            '    "container_no": "...",\n'
            '    "seal_no": "...",\n'
            '    "bl_no": "...",\n'
            '    "firms_code": "...",\n'
            '    "consignee": "...",\n'
            '    "total_packages": "...",\n'
            '    "gross_weight_kg": 0,\n'
            '    "volume_cbm": 0,\n'
            '    "total_value_usd": 0\n'
            "  },\n"
            '  "bill_of_lading": { },\n'
            '  "commercial_invoice": { "source": null, "items": [] },\n'
            '  "packing_list": { "source": null, "items": [] },\n'
            '  "arrival_notice": { }\n'
            "}\n\n"
            "规则：\n"
            "1. 所有字段必须存在，找不到的写 null 或 0。\n"
            "2. summary 中的毛重、体积、件数等请尽量从提单/到货通知中汇总。\n"
            "3. 如果只有提单和到货通知，没有发票或装箱单，相应对象保持结构但字段为 null 或空数组。\n"
            "4. 只返回一段纯 JSON，不要任何解释，不要代码块标记。"
        )
    })

    # 附加所有文本块
    for i, chunk in enumerate(text_chunks, start=1):
        user_content.append({
            "type": "text",
            "text": f"\n\n==== 文本块 {i} 开始 ====\n{chunk}\n==== 文本块 {i} 结束 ===="
        })

    # 附加图片
    for img in images:
        if img.get("hint"):
            user_content.append({"type": "text", "text": img["hint"]})
        if img.get("b64"):
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img['b64']}"
                }
            })

    messages = [
        {"role": "system", "content": "你是一名严谨的清关单据结构化专家，输出必须是有效 JSON。"},
        {"role": "user", "content": user_content},
    ]
    return messages


def call_gpt_and_parse_json(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """调用 GPT 并尽量解析出 JSON。"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-2024-08-06",   # 支持 vision，也可换成 gpt-4.1 等
            messages=messages,
            temperature=0,
            max_tokens=8192,
        )
    except Exception as e:
        safe_print(f"[OpenAI] API 调用失败: {e}")
        return {"error": f"OpenAI API 调用失败: {e}"}

    raw = resp.choices[0].message.content or ""
    safe_print("[OpenAI] 原始返回前 400 字符：", raw[:400])

    # 1. 直接尝试整体解析
    raw_stripped = raw.strip()
    try:
        return json.loads(raw_stripped)
    except Exception:
        pass

    # 2. 从中间截取第一个 { 到最后一个 } 再解析（防止前后有注释）
    try:
        start = raw_stripped.index("{")
        end = raw_stripped.rindex("}") + 1
        candidate = raw_stripped[start:end]
        return json.loads(candidate)
    except Exception as e:
        safe_print(f"[JSON] 解析失败: {e}")
        return {
            "error": f"JSON 解析失败: {e}",
            "raw_preview": raw_stripped[:MAX_RAW_IN_ERROR]
        }


# ---------------------- 对外主函数 ---------------------- #

def analyze_with_vision(file_paths: List[str]) -> Dict[str, Any]:
    """
    主入口：
    - file_paths: 本地已下载好的附件路径
    - 返回：结构化 JSON 或带 error 的结果
    """
    if not file_paths:
        return {"error": "no files"}

    try:
        payload = build_file_payloads(file_paths)
        messages = build_messages(payload)
        result = call_gpt_and_parse_json(messages)
        return result
    except Exception as e:
        # 兜底，防止任何意外把上层搞挂
        safe_print(f"[analyze_with_vision] 致命异常: {e}")
        return {"error": f"analyze_with_vision 崩溃: {e}"}
