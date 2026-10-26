"""模型评估：自适应 K 折交叉验证与多指标误差统计。

小样本工程数据集的规模差异很大，因此折数根据样本量自适应：
    n < 8   : 不做交叉验证，只报告机理模型拟合误差
    8 ≤ n<15: 3 折
    15≤ n<60: 5 折
    n ≥ 60  : 10 折
对每一项性能指标分别输出 R²、RMSE、MAE、MAPE，并给出训练集与验证集
（out-of-fold）的对比，用于判断过拟合程度。
"""

from __future__ import annotations

import math

import numpy as np
from sklearn.model_selection import KFold

from .mechanism import mechanism_baseline_matrix
from .models import LEARNER_ORDER, MIN_TRAIN_SAMPLES, HybridModel, target_matrix
from .schemas import METRIC_KEYS, METRIC_LABELS, METRIC_UNITS, PARAM_KEYS


def choose_folds(sample_count: int) -> int:
    if sample_count < MIN_TRAIN_SAMPLES:
        return 0
    if sample_count < 15:
        return 3
    if sample_count < 60:
        return 5
    return 10


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot <= 1e-12:
        return 0.0
    return 1.0 - ss_res / ss_tot


def metric_table(y_true: np.ndarray, y_pred: np.ndarray) -> list[dict]:
    rows = []
    for idx, key in enumerate(METRIC_KEYS):
        truth = y_true[:, idx]
        pred = y_pred[:, idx]
        err = pred - truth
        denom = np.where(np.abs(truth) > 1e-9, np.abs(truth), np.nan)
        mape = float(np.nanmean(np.abs(err) / denom) * 100.0) if np.any(~np.isnan(denom)) else 0.0
        rows.append(
            {
                "key": key,
                "label": METRIC_LABELS[key],
                "unit": METRIC_UNITS[key],
                "r2": round(_safe_r2(truth, pred), 4),
                "rmse": round(float(math.sqrt(np.mean(err ** 2))), 4),
                "mae": round(float(np.mean(np.abs(err))), 4),
                "mape": round(mape, 2),
            }
        )
    return rows


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {"r2": 0.0, "rmse": 0.0, "mae": 0.0, "mape": 0.0}
    return {
        "r2": round(float(np.mean([r["r2"] for r in rows])), 4),
        "rmse": round(float(np.mean([r["rmse"] for r in rows])), 4),
        "mae": round(float(np.mean([r["mae"] for r in rows])), 4),
        "mape": round(float(np.mean([r["mape"] for r in rows])), 2),
    }


def cross_validate(dataset: list[dict], learner_name: str, folds: int | None = None) -> dict:
    """对指定学习器执行 K 折交叉验证，返回逐指标与汇总误差。"""
    n = len(dataset)
    y = target_matrix(dataset)
    raw = np.array([[float(row[key]) for key in PARAM_KEYS] for row in dataset], dtype=float)
    k = folds if folds is not None else choose_folds(n)

    result: dict = {
        "learner": learner_name,
        "sampleCount": n,
        "folds": k,
    }

    # 机理基线自身的误差，作为所有学习器的对照组
    baseline_pred = mechanism_baseline_matrix(raw)
    result["baseline"] = {"perMetric": metric_table(y, baseline_pred)}
    result["baseline"]["overall"] = summarize(result["baseline"]["perMetric"])

    if k == 0 or learner_name not in LEARNER_ORDER:
        result["validation"] = None
        result["train"] = None
        result["note"] = "样本量不足或学习器不支持交叉验证，仅给出机理模型误差。"
        return result

    oof = np.zeros_like(y)
    splitter = KFold(n_splits=k, shuffle=True, random_state=42)
    fold_scores = []
    for fold_idx, (train_idx, test_idx) in enumerate(splitter.split(raw), 1):
        train_rows = [dataset[i] for i in train_idx]
        model = HybridModel(learner_name).fit(train_rows)
        pred = model.predict_matrix(raw[test_idx])
        oof[test_idx] = pred
        fold_scores.append(
            {
                "fold": fold_idx,
                "testSize": int(len(test_idx)),
                "r2": round(float(np.mean([_safe_r2(y[test_idx, j], pred[:, j]) for j in range(y.shape[1])])), 4),
            }
        )

    full_model = HybridModel(learner_name).fit(dataset)
    train_pred = full_model.predict_matrix(raw)

    validation_rows = metric_table(y, oof)
    train_rows_table = metric_table(y, train_pred)
    result["validation"] = {"perMetric": validation_rows, "overall": summarize(validation_rows), "folds": fold_scores}
    result["train"] = {"perMetric": train_rows_table, "overall": summarize(train_rows_table)}
    gap = result["train"]["overall"]["r2"] - result["validation"]["overall"]["r2"]
    result["overfitGap"] = round(gap, 4)
    result["note"] = (
        "训练集与验证集 R² 差距较大，存在过拟合风险，建议增加样本或提高正则化。"
        if gap > 0.25
        else "训练集与验证集误差接近，模型泛化能力可接受。"
    )
    return result


def evaluate_all(dataset: list[dict], learners: list[str] | None = None) -> dict:
    """评估全部学习器并给出推荐。推荐依据：验证集平均 R² 最高，若并列取 RMSE 更小者。"""
    learners = learners or LEARNER_ORDER
    reports = {name: cross_validate(dataset, name) for name in learners}
    ranking = []
    for name, report in reports.items():
        if report.get("validation"):
            ranking.append((report["validation"]["overall"]["r2"], -report["validation"]["overall"]["rmse"], name))
    ranking.sort(reverse=True)
    recommended = ranking[0][2] if ranking else "mechanism"
    return {"reports": reports, "recommended": recommended, "ranking": [item[2] for item in ranking]}
