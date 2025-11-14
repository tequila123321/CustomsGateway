# # main.py
# from fastapi import FastAPI
# from app.integration.gmail_auto_reply import process_latest_email_and_reply
#
# app = FastAPI(title="Customs AI Gateway v3 - Vision Edition")
#
# @app.get("/process-emails")
# async def trigger():
#     result = await process_latest_email_and_reply()
#     return result
#







# -----------------------------------------------------------------------------------
# for debug

from app.integration.debug_xml_test import debug_generate_xml
import json

gpt_json = json.load(open("attachments/results/gpt_extracted_jason.json", "r", encoding="utf-8"))
debug_generate_xml(gpt_json)

# -----------------------------------------------------------------------------------