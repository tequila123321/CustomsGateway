# app/integration/netchb_aggregator.py
import os
from collections import defaultdict


def aggregate_results(results: list) -> list:
    """
    输入：每个附件的分析结果（list）
    输出：按柜号合并：每柜一个 dict
    """

    containers = defaultdict(lambda: {
        "container": None,
        "booking_numbers": [],
        "consignee": None,
        "invoice_items": [],
        "total_value": 0,
        "gross_weight": 0,
        "packing_list": [],
        "firms_code": None,
    })

    for item in results:
        path = item["file"]
        doc_type = item["doc_type"]
        data = item["data"]

        # ---------- BOL ----------
        if doc_type == "bill_of_lading":
            C = containers[data.get("container")]
            C["container"] = data.get("container")
            C["consignee"] = data.get("consignee")
            if data.get("booking_number"):
                C["booking_numbers"].append(data.get("booking_number"))
            C["packages"] = data.get("packages")

        # ---------- Commercial Invoice ----------
        elif doc_type == "commercial_invoice":
            C = containers[os.path.basename(path)[:12]]  # 若无法读取柜号，则用文件名前12位作为group
            C["invoice_items"].extend(data.get("invoice_items", []))
            if data.get("total_value"):
                C["total_value"] += data.get("total_value")

        # ---------- Packing List ----------
        elif doc_type == "packing_list":
            C = containers[os.path.basename(path)[:12]]
            C["packing_list"].extend(data.get("packing_rows", []))
            if data.get("gross_weight_total"):
                C["gross_weight"] += data.get("gross_weight_total")

        # ---------- Arrival Notice ----------
        elif doc_type == "arrival_notice":
            C = containers["unknown"]
            C["firms_code"] = data.get("firms_code")

    return list(containers.values())
