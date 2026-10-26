"""MICP-椰壳纤维协同固化砂土分析预测算法包。

对外统一暴露面向接口层的高阶函数，内部模块划分：

    schemas      参数 / 指标 / 机理特征字典
    mechanism    机理特征工程与机理基线预测
    models       机理 + 残差混合模型、序列化
    evaluation   自适应 K 折交叉验证
    sensitivity  OAT 弹性、Morris 基本效应、偏依赖
    optimizer    拉丁超立方 + 局部细化的多目标配比优化
    statistics   异常值、描述统计、方差分析、相关、回归
    validators   行级校验与 CSV 解析
    synthetic    内置示范数据集
    report       含 SVG 图表的 HTML 报告
"""

from __future__ import annotations

from . import evaluation as _evaluation
from . import optimizer as _optimizer
from . import report as _report
from . import sensitivity as _sensitivity
from . import statistics as _statistics
from . import validators as _validators
from .mechanism import explain_mechanism, mechanism_baseline, mechanism_features
from .models import (
    LEARNER_LABELS,
    LEARNER_ORDER,
    MECHANISM_MODEL,
    MIN_TRAIN_SAMPLES,
    HybridModel,
    make_batch_predictor,
    mechanism_payload,
    predict_sample,
    resolve_model,
)
from .schemas import METRIC_KEYS, METRIC_LABELS, PARAM_KEYS, PARAM_LABELS, PARAM_RANGES, describe_dictionary
from .synthetic import DEFAULT_SCHEMES, generate_dataset

__version__ = "1.0.0"


# ---------------------------------------------------------------------------- 训练与评估
def train_models(dataset: list[dict], with_evaluation: bool = True) -> dict:
    """训练全部学习器。返回 ``{model_name: payload}``，payload 中含交叉验证指标。

    样本量不足时不训练，只返回机理模型占位，供接口层提示用户补充数据。
    """
    if len(dataset) < MIN_TRAIN_SAMPLES:
        payload = mechanism_payload()
        payload["metrics"] = {"note": f"样本量 {len(dataset)} 小于 {MIN_TRAIN_SAMPLES}，仅提供机理模型"}
        return {MECHANISM_MODEL: payload}
    evaluation = _evaluation.evaluate_all(dataset) if with_evaluation else {"reports": {}, "recommended": "ensemble"}
    result = {}
    for name in LEARNER_ORDER:
        model = HybridModel(name).fit(dataset)
        report = evaluation["reports"].get(name, {})
        metrics = {
            "sampleCount": len(dataset),
            "folds": report.get("folds"),
            "r2": report["validation"]["overall"]["r2"] if report.get("validation") else None,
            "rmse": report["validation"]["overall"]["rmse"] if report.get("validation") else None,
            "mape": report["validation"]["overall"]["mape"] if report.get("validation") else None,
            "trainR2": report["train"]["overall"]["r2"] if report.get("train") else None,
            "baselineR2": report.get("baseline", {}).get("overall", {}).get("r2"),
            "overfitGap": report.get("overfitGap"),
            "recommended": evaluation.get("recommended") == name,
        }
        result[name] = model.to_payload(metrics=metrics)
    return result


def evaluate_models(dataset: list[dict]) -> dict:
    return _evaluation.evaluate_all(dataset)


# ---------------------------------------------------------------------------- 预测
def predict(sample: dict, model_name: str, dataset: list[dict], stored_models: dict[str, dict], with_morris: bool = False) -> dict:
    model, payload = resolve_model(model_name, stored_models, dataset)
    predictor = make_batch_predictor(model)
    decomposition = model.decompose(sample)
    oat = _sensitivity.oat_elasticity(predictor, sample)
    result = {
        "model": payload.get("kind", model_name),
        "modelLabel": payload.get("label", LEARNER_LABELS.get(model_name, model_name)),
        "fallback": bool(payload.get("fallback")),
        "requested": payload.get("requested", model_name),
        "sampleCount": payload.get("sampleCount", 0),   # 模型训练时使用的样本数（纯机理模型为 0）
        "datasetSize": len(dataset),                     # 当前项目的历史样本数
        "trainedAt": payload.get("trainedAt"),
        "metrics": decomposition["final"],
        "decomposition": decomposition,
        "features": mechanism_features(sample),
        "mechanism": explain_mechanism(sample),
        "sensitivity": oat["ranking"],
        "sensitivityMatrix": oat["matrix"],
        "sensitivityMethod": oat["method"],
    }
    if with_morris:
        result["morris"] = _sensitivity.morris_effects(predictor)
    return result


def partial_dependence(sample: dict, model_name: str, dataset: list[dict], stored_models: dict[str, dict], param: str | None = None) -> dict:
    model, payload = resolve_model(model_name, stored_models, dataset)
    predictor = make_batch_predictor(model)
    if param:
        data = _sensitivity.partial_dependence(predictor, sample, param)
    else:
        data = {"curves": _sensitivity.full_partial_dependence(predictor, sample)}
    data["model"] = payload.get("kind", model_name)
    data["fallback"] = bool(payload.get("fallback"))
    return data


def morris(model_name: str, dataset: list[dict], stored_models: dict[str, dict], trajectories: int = 12) -> dict:
    model, payload = resolve_model(model_name, stored_models, dataset)
    data = _sensitivity.morris_effects(make_batch_predictor(model), trajectories=trajectories)
    data["model"] = payload.get("kind", model_name)
    return data


# ---------------------------------------------------------------------------- 优化与推荐
def optimize(model_name: str, dataset: list[dict], stored_models: dict[str, dict], weights: dict | None = None, fixed: dict | None = None, bounds: dict | None = None, restrict_to_data: bool = True, top_n: int = 8) -> dict:
    model, payload = resolve_model(model_name, stored_models, dataset)
    effective_bounds = dict(_optimizer.dataset_envelope(dataset)) if (restrict_to_data and dataset) else {}
    for key, value in (bounds or {}).items():
        if isinstance(value, (list, tuple)) and len(value) == 2:
            effective_bounds[key] = (float(value[0]), float(value[1]))
    result = _optimizer.optimize(make_batch_predictor(model), weights=weights, fixed=fixed, bounds=effective_bounds, top_n=top_n)
    result["model"] = payload.get("kind", model_name)
    result["fallback"] = bool(payload.get("fallback"))
    result["restrictedToData"] = bool(restrict_to_data and dataset)
    return result


def rank_schemes(schemes: list[dict], dataset: list[dict], stored_models: dict[str, dict], model_name: str = "ensemble", weights: dict | None = None) -> list[dict]:
    model, _ = resolve_model(model_name, stored_models, dataset)
    return _optimizer.rank_schemes(make_batch_predictor(model), schemes, weights)


def recommend_best_scheme(schemes: list[dict], dataset: list[dict], stored_models: dict[str, dict], weights: dict | None = None) -> dict | None:
    ranking = rank_schemes(schemes, dataset, stored_models, weights=weights)
    return ranking[0] if ranking else None


# ---------------------------------------------------------------------------- 统计
def analyze_dataset(dataset: list[dict], factor: str = "fiberContent", response: str = "ucs") -> dict:
    return _statistics.analyze_dataset(dataset, factor, response)


def correlation(dataset: list[dict]) -> dict:
    return _statistics.correlation_matrix(dataset)


def validate_rows(rows: list[dict], kind: str = "sample") -> dict:
    return _validators.validate_rows(rows, kind)


def parse_csv(text: str):
    return _validators.parse_csv(text)


# ---------------------------------------------------------------------------- 报告
def build_report_html(scheme, prediction, analysis, recommendation, evaluation=None, optimization=None, dataset=None, project_name: str = "默认项目") -> str:
    return _report.build_report_html(scheme, prediction, analysis, recommendation, evaluation, optimization, dataset, project_name)


__all__ = [
    "DEFAULT_SCHEMES",
    "LEARNER_LABELS",
    "LEARNER_ORDER",
    "MECHANISM_MODEL",
    "METRIC_KEYS",
    "METRIC_LABELS",
    "MIN_TRAIN_SAMPLES",
    "PARAM_KEYS",
    "PARAM_LABELS",
    "PARAM_RANGES",
    "analyze_dataset",
    "build_report_html",
    "correlation",
    "describe_dictionary",
    "evaluate_models",
    "explain_mechanism",
    "generate_dataset",
    "mechanism_baseline",
    "mechanism_features",
    "morris",
    "optimize",
    "parse_csv",
    "partial_dependence",
    "predict",
    "predict_sample",
    "rank_schemes",
    "recommend_best_scheme",
    "train_models",
    "validate_rows",
]
