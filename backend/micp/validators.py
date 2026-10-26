"""输入校验与 CSV 解析。

校验规则分三层：
1. 结构层：必填字段是否存在、是否能转换为数值；
2. 区间层：是否落在参数字典的合理区间（硬约束），指标是否为非负（软约束→警告）；
3. 一致性层：固化后干密度应不低于初始干密度、碳酸钙含量与 UCS 的关系是否明显偏离
   机理模型（偏离超过 60% 给出警告，不拦截）。

所有错误/警告都带行号与字段，便于前端逐行高亮。
"""

from __future__ import annotations

import csv
import io

from .mechanism import mechanism_baseline
from .schemas import METRIC_KEYS, METRIC_LABELS, PARAM_BY_KEY, PARAM_KEYS, PARAM_LABELS, canonical_key


def _to_number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("，", "").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def validate_row(row: dict, kind: str, index: int) -> dict:
    """校验单行。``kind`` 为 ``scheme``（仅参数）或 ``sample``（参数 + 指标）。"""
    errors: list[dict] = []
    warnings: list[dict] = []
    normalized: dict = {}

    name_key = "schemeName" if kind == "scheme" else "sampleId"
    name = str(row.get(name_key) or "").strip()
    if not name:
        name = (f"方案{index}" if kind == "scheme" else f"S{index:02d}")
        warnings.append({"row": index, "field": name_key, "message": f"缺少{name_key}，已自动命名为 {name}"})
    normalized[name_key] = name

    for key in PARAM_KEYS:
        spec = PARAM_BY_KEY[key]
        value = _to_number(row.get(key))
        if value is None:
            errors.append({"row": index, "field": key, "message": f"{spec.label}缺失或不是数值"})
            continue
        if value < spec.low or value > spec.high:
            errors.append({"row": index, "field": key, "message": f"{spec.label} {value:g} 超出范围 [{spec.low:g}, {spec.high:g}] {spec.unit}"})
            continue
        if spec.integer and abs(value - round(value)) > 1e-9:
            warnings.append({"row": index, "field": key, "message": f"{spec.label}应为整数，已取整为 {round(value)}"})
        normalized[key] = int(round(value)) if spec.integer else value

    if kind == "sample":
        for key in METRIC_KEYS:
            value = _to_number(row.get(key))
            if value is None:
                errors.append({"row": index, "field": key, "message": f"{METRIC_LABELS[key]}缺失或不是数值"})
                continue
            if value < 0:
                errors.append({"row": index, "field": key, "message": f"{METRIC_LABELS[key]}不能为负数"})
                continue
            normalized[key] = value
        if "disintegrationRate" in normalized and normalized["disintegrationRate"] > 100:
            errors.append({"row": index, "field": "disintegrationRate", "message": "浸水崩解率不能超过 100%"})
        if "postDryDensity" in normalized and "dryDensity" in normalized and normalized["postDryDensity"] < normalized["dryDensity"] - 0.02:
            warnings.append({"row": index, "field": "postDryDensity", "message": "固化后干密度低于初始干密度，请核对测量值"})
        if not errors and all(k in normalized for k in PARAM_KEYS) and "ucs" in normalized:
            base = mechanism_baseline(normalized)
            if base["ucs"] > 0 and abs(normalized["ucs"] - base["ucs"]) / base["ucs"] > 0.6:
                warnings.append({"row": index, "field": "ucs", "message": f"UCS 实测 {normalized['ucs']:.0f} kPa 与机理估算 {base['ucs']:.0f} kPa 偏差超过 60%，请确认单位是否为 kPa"})

    # 透传额外字段（如备注）
    for key, value in row.items():
        if key not in normalized and key not in PARAM_KEYS and key not in METRIC_KEYS and key != name_key:
            normalized[key] = value
    return {"index": index, "ok": not errors, "row": normalized, "errors": errors, "warnings": warnings}


def validate_rows(rows: list[dict], kind: str = "sample") -> dict:
    results = [validate_row(row, kind, i) for i, row in enumerate(rows, 1)]
    valid = [r["row"] for r in results if r["ok"]]
    errors = [e for r in results for e in r["errors"]]
    warnings = [w for r in results for w in r["warnings"]]
    ids = [r["row"].get("sampleId" if kind == "sample" else "schemeName") for r in results if r["ok"]]
    duplicates = sorted({x for x in ids if ids.count(x) > 1})
    if duplicates:
        warnings.append({"row": 0, "field": "sampleId" if kind == "sample" else "schemeName", "message": f"存在重复编号：{', '.join(map(str, duplicates))}，后者将覆盖前者"})
    return {
        "kind": kind,
        "total": len(rows),
        "accepted": len(valid),
        "rejected": len(rows) - len(valid),
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "fieldLabels": {**PARAM_LABELS, **METRIC_LABELS},
    }


def parse_csv(text: str) -> tuple[list[dict], list[str]]:
    """解析 CSV 文本，表头自动映射为标准键名；返回 (rows, 无法识别的表头)。"""
    text = text.lstrip("\ufeff")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return [], []
    mapped = [canonical_key(h) for h in header]
    unknown = [h for h, m in zip(header, mapped) if m is None and h.strip()]
    rows = []
    for raw in reader:
        if not any(cell.strip() for cell in raw):
            continue
        row = {}
        for key, cell in zip(mapped, raw):
            if key:
                row[key] = cell.strip()
        rows.append(row)
    return rows, unknown
