"""机理-数据混合建模。

核心思想：机器学习模型不直接拟合性能指标，而是拟合
``残差 = 实测值 - 机理基线``。这样做的收益是：

- 小样本下模型退化为机理模型，而不是输出无物理意义的外推值；
- 学习器只需要刻画机理模型未覆盖的二阶效应（交互、批次差异），
  拟合难度和过拟合风险都显著降低；
- 任何一次预测都可以拆分为"机理解释部分 + 数据修正部分"，便于报告解释。

模型输入特征 = 8 项原始参数 + 8 项机理特征（共 16 维）。
"""

from __future__ import annotations

import base64
import io
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .mechanism import mechanism_baseline_matrix, mechanism_features_matrix
from .schemas import FEATURE_KEYS, METRIC_KEYS, PARAM_KEYS

MIN_TRAIN_SAMPLES = 8
MECHANISM_MODEL = "mechanism"

LEARNER_LABELS = {
    "ensemble": "随机森林残差模型",
    "gbrt": "梯度提升残差模型",
    "bp": "BP 神经网络残差模型",
    MECHANISM_MODEL: "纯机理模型",
}

LEARNER_ORDER = ["ensemble", "gbrt", "bp"]


def build_learner(name: str, sample_count: int):
    """根据学习器名称与样本规模构造 scikit-learn 估计器。"""
    if name == "ensemble":
        return MultiOutputRegressor(
            RandomForestRegressor(
                n_estimators=240,
                max_depth=None if sample_count >= 60 else 8,
                min_samples_leaf=2 if sample_count >= 30 else 1,
                max_features=0.6,
                random_state=42,
                n_jobs=1,
            )
        )
    if name == "gbrt":
        return MultiOutputRegressor(
            GradientBoostingRegressor(
                n_estimators=180,
                learning_rate=0.05,
                max_depth=3,
                subsample=0.85,
                random_state=42,
            )
        )
    if name == "bp":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "mlp",
                    MLPRegressor(
                        hidden_layer_sizes=(48, 24),
                        activation="relu",
                        solver="adam",
                        alpha=1e-3,
                        learning_rate_init=0.002,
                        max_iter=3000,
                        early_stopping=False,
                        random_state=42,
                    ),
                ),
            ]
        )
    raise ValueError(f"未知学习器: {name}")


def design_matrix(samples) -> np.ndarray:
    """原始参数 + 机理特征 → (n, 16) 特征矩阵。"""
    raw = np.array([[float(row[key]) for key in PARAM_KEYS] for row in samples], dtype=float) if not isinstance(samples, np.ndarray) else samples
    features, _ = mechanism_features_matrix(raw)
    return np.hstack([raw, features])


def target_matrix(dataset: list[dict]) -> np.ndarray:
    return np.array([[float(row[key]) for key in METRIC_KEYS] for row in dataset], dtype=float)


class HybridModel:
    """机理基线 + 残差学习器的组合模型。"""

    def __init__(self, learner_name: str):
        self.learner_name = learner_name
        self.estimator = None
        self.residual_scale = np.ones(len(METRIC_KEYS))
        self.trained_at = None
        self.sample_count = 0

    # ------------------------------------------------------------------ 训练
    def fit(self, dataset: list[dict]) -> "HybridModel":
        raw = np.array([[float(row[key]) for key in PARAM_KEYS] for row in dataset], dtype=float)
        y = target_matrix(dataset)
        baseline = mechanism_baseline_matrix(raw)
        residual = y - baseline
        # 残差按指标尺度归一化，避免 UCS(kPa) 支配 MLP 的损失函数
        self.residual_scale = np.where(np.std(y, axis=0) > 1e-9, np.std(y, axis=0), 1.0)
        X = design_matrix(raw)
        self.estimator = build_learner(self.learner_name, len(dataset))
        self.estimator.fit(X, residual / self.residual_scale)
        self.sample_count = len(dataset)
        self.trained_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        return self

    # ------------------------------------------------------------------ 推理
    def predict_matrix(self, samples) -> np.ndarray:
        raw = samples if isinstance(samples, np.ndarray) else np.array(
            [[float(row[key]) for key in PARAM_KEYS] for row in samples], dtype=float
        )
        if raw.ndim == 1:
            raw = raw.reshape(1, -1)
        baseline = mechanism_baseline_matrix(raw)
        if self.estimator is None:
            return baseline
        correction = self.estimator.predict(design_matrix(raw)) * self.residual_scale
        return self._physical_clip(baseline + correction)

    def decompose(self, sample: dict) -> dict:
        """把单次预测拆分为机理基线与数据修正两部分。"""
        raw = np.array([[float(sample[key]) for key in PARAM_KEYS]], dtype=float)
        baseline = mechanism_baseline_matrix(raw)[0]
        final = self.predict_matrix(raw)[0]
        return {
            "baseline": {k: round(float(v), 4) for k, v in zip(METRIC_KEYS, baseline)},
            "correction": {k: round(float(f - b), 4) for k, f, b in zip(METRIC_KEYS, final, baseline)},
            "final": {k: round(float(v), 4) for k, v in zip(METRIC_KEYS, final)},
        }

    @staticmethod
    def _physical_clip(matrix: np.ndarray) -> np.ndarray:
        """物理可行域约束：强度/含量非负，崩解率 0~100%，渗透系数为正。"""
        out = matrix.copy()
        idx = {key: i for i, key in enumerate(METRIC_KEYS)}
        out[:, idx["ucs"]] = np.maximum(out[:, idx["ucs"]], 0.0)
        out[:, idx["caco3"]] = np.clip(out[:, idx["caco3"]], 0.0, 60.0)
        out[:, idx["disintegrationRate"]] = np.clip(out[:, idx["disintegrationRate"]], 0.0, 100.0)
        out[:, idx["permeability"]] = np.maximum(out[:, idx["permeability"]], 0.01)
        out[:, idx["frictionAngle"]] = np.clip(out[:, idx["frictionAngle"]], 10.0, 60.0)
        out[:, idx["cohesion"]] = np.maximum(out[:, idx["cohesion"]], 0.0)
        out[:, idx["postDryDensity"]] = np.clip(out[:, idx["postDryDensity"]], 1.0, 2.6)
        return out

    # ------------------------------------------------------------------ 序列化
    def to_payload(self, metrics: dict | None = None, version: int = 1) -> dict:
        buffer = io.BytesIO()
        joblib.dump({"estimator": self.estimator, "scale": self.residual_scale}, buffer)
        return {
            "kind": self.learner_name,
            "label": LEARNER_LABELS.get(self.learner_name, self.learner_name),
            "blob": base64.b64encode(buffer.getvalue()).decode("utf-8"),
            "featureNames": PARAM_KEYS + FEATURE_KEYS,
            "targetNames": METRIC_KEYS,
            "trainedAt": self.trained_at,
            "sampleCount": self.sample_count,
            "version": version,
            "fallback": False,
            "metrics": metrics or {},
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "HybridModel":
        model = cls(payload.get("kind", "ensemble"))
        if payload.get("blob"):
            bundle = joblib.load(io.BytesIO(base64.b64decode(payload["blob"].encode("utf-8"))))
            if isinstance(bundle, dict):
                model.estimator = bundle.get("estimator")
                model.residual_scale = np.asarray(bundle.get("scale", np.ones(len(METRIC_KEYS))))
            else:  # 兼容旧版直接存 estimator 的格式
                model.estimator = bundle
        model.trained_at = payload.get("trainedAt")
        model.sample_count = int(payload.get("sampleCount", 0))
        return model


def mechanism_payload() -> dict:
    return {
        "kind": MECHANISM_MODEL,
        "label": LEARNER_LABELS[MECHANISM_MODEL],
        "blob": "",
        "featureNames": PARAM_KEYS,
        "targetNames": METRIC_KEYS,
        "trainedAt": None,
        "sampleCount": 0,
        "version": 0,
        "fallback": True,
        "metrics": {},
    }


def resolve_model(model_name: str, stored_models: dict[str, dict], dataset: list[dict]) -> tuple[HybridModel, dict]:
    """按优先级解析可用模型：已存模型 → 临时训练 → 纯机理回退。"""
    if model_name == MECHANISM_MODEL:
        return HybridModel(MECHANISM_MODEL), mechanism_payload()
    payload = stored_models.get(model_name)
    # featureNames 缺失说明是旧版（仅 8 维原始特征）模型，与当前 16 维设计矩阵不兼容，视为未训练
    if payload and payload.get("blob") and payload.get("featureNames"):
        return HybridModel.from_payload(payload), payload
    if len(dataset) >= MIN_TRAIN_SAMPLES and model_name in LEARNER_ORDER:
        model = HybridModel(model_name).fit(dataset)
        return model, model.to_payload()
    fallback = mechanism_payload()
    fallback["requested"] = model_name
    return HybridModel(MECHANISM_MODEL), fallback


def make_batch_predictor(model: HybridModel):
    """返回 ``f(matrix) -> (n, 7)`` 的向量化预测函数，供敏感性与优化模块调用。"""

    def predictor(matrix: np.ndarray) -> np.ndarray:
        return model.predict_matrix(np.asarray(matrix, dtype=float))

    return predictor


def predict_sample(model: HybridModel, sample: dict) -> dict:
    values = model.predict_matrix(sample)[0]
    return {key: round(float(value), 4) for key, value in zip(METRIC_KEYS, values)}
