"""多目标配比优化。

问题定义：在 8 项参数的可行域内寻找一组配比，使加权归一化目标函数最大::

    J(x) = Σ_i w_i · g_i(x)
    g_i  = (y_i - min_i)/(max_i - min_i)         （越大越好的指标）
         = (max_i - y_i)/(max_i - min_i)         （越小越好的指标与成本）

目标包含 7 项性能指标与 1 项"相对成本指数"：

    cost = N · (0.4 · V_b·OD / (300·3) + 0.6 · C·V_f / (3·300)) · 100

即菌液（体积×浓度）与胶结液（浓度×体积）的加权消耗量，归一化到 0~100。

求解策略（无梯度、可解释、可复现）：
1. 拉丁超立方采样 (LHS) 在整个可行域撒点，保证各维度分层覆盖；
2. 对得分前 M 的候选做两轮高斯扰动局部细化（σ 逐轮缩小）；
3. 汇总所有评估点，输出 Top-N 与 UCS-成本 Pareto 前沿。
用户可以固定部分参数（例如实验室只有一种干密度制样条件），固定维度不参与采样。
"""

from __future__ import annotations

import numpy as np

from .mechanism import clip_to_ranges, design_space_bounds
from .schemas import METRIC_DIRECTION, METRIC_KEYS, METRIC_LABELS, PARAM_KEYS, PARAM_LABELS

DEFAULT_WEIGHTS = {
    "ucs": 0.30,
    "disintegrationRate": 0.15,
    "permeability": 0.10,
    "caco3": 0.10,
    "cohesion": 0.05,
    "frictionAngle": 0.05,
    "postDryDensity": 0.0,
    "cost": 0.25,
}

OBJECTIVE_LABELS = {**METRIC_LABELS, "cost": "相对成本指数"}


def cost_index(matrix: np.ndarray) -> np.ndarray:
    col = {key: matrix[:, i] for i, key in enumerate(PARAM_KEYS)}
    bacteria = col["bacterialVolume"] * col["odValue"] / (300.0 * 3.0)
    cementation = col["cementationDose"] * col["fixationVolume"] / (3.0 * 300.0)
    return np.maximum(col["cycles"], 1) * (0.4 * bacteria + 0.6 * cementation) * 100.0


def latin_hypercube(n: int, dims: int, rng: np.random.Generator) -> np.ndarray:
    """返回 (n, dims) 的 [0,1) 拉丁超立方样本。"""
    cut = np.linspace(0, 1, n + 1)
    u = rng.random((n, dims))
    points = cut[:-1][:, None] + u * (cut[1:] - cut[:-1])[:, None]
    for d in range(dims):
        points[:, d] = points[rng.permutation(n), d]
    return points


def _normalize_weights(weights: dict | None) -> dict:
    merged = {**DEFAULT_WEIGHTS, **{k: float(v) for k, v in (weights or {}).items() if k in DEFAULT_WEIGHTS}}
    total = sum(max(v, 0.0) for v in merged.values()) or 1.0
    return {k: max(v, 0.0) / total for k, v in merged.items()}


def _score(metrics: np.ndarray, cost: np.ndarray, weights: dict) -> tuple[np.ndarray, dict]:
    """加权归一化评分；返回分数与各目标的归一化区间（便于前端解释）。"""
    columns = {key: metrics[:, j] for j, key in enumerate(METRIC_KEYS)}
    columns["cost"] = cost
    scores = np.zeros(len(cost))
    ranges = {}
    for key, w in weights.items():
        if w <= 0:
            continue
        values = columns[key]
        lo, hi = float(values.min()), float(values.max())
        ranges[key] = {"min": round(lo, 4), "max": round(hi, 4)}
        if hi - lo < 1e-12:
            continue
        higher_better = METRIC_DIRECTION.get(key, False) if key != "cost" else False
        g = (values - lo) / (hi - lo) if higher_better else (hi - values) / (hi - lo)
        scores += w * g
    return scores, ranges


def pareto_front(ucs: np.ndarray, cost: np.ndarray) -> np.ndarray:
    """返回 UCS 最大化 / 成本最小化意义下非支配点的索引（按成本升序）。"""
    order = np.argsort(cost)
    best_ucs = -np.inf
    keep = []
    for idx in order:
        if ucs[idx] > best_ucs:
            keep.append(idx)
            best_ucs = ucs[idx]
    return np.array(keep, dtype=int)


def _snap(matrix: np.ndarray) -> np.ndarray:
    out = clip_to_ranges(matrix)
    out[:, PARAM_KEYS.index("cycles")] = np.round(out[:, PARAM_KEYS.index("cycles")])
    return out


def dataset_envelope(dataset: list[dict], margin: float = 0.05) -> dict[str, tuple[float, float]]:
    """历史样本在各参数上的覆盖包络（外扩 margin 倍区间宽度），用于限制优化不外推。"""
    if not dataset:
        return {}
    envelope = {}
    for key in PARAM_KEYS:
        values = np.array([float(row[key]) for row in dataset])
        lo, hi = float(values.min()), float(values.max())
        pad = (hi - lo) * margin
        envelope[key] = (lo - pad, hi + pad)
    return envelope


def optimize(
    predictor,
    weights: dict | None = None,
    fixed: dict | None = None,
    bounds: dict | None = None,
    samples: int = 400,
    top_n: int = 8,
    refine_rounds: int = 2,
    refine_candidates: int = 6,
    refine_size: int = 40,
    seed: int = 7,
) -> dict:
    rng = np.random.default_rng(seed)
    weights = _normalize_weights(weights)
    lows, highs = design_space_bounds()
    lows, highs = lows.copy(), highs.copy()
    for key, (lo, hi) in (bounds or {}).items():
        if key in PARAM_KEYS:
            i = PARAM_KEYS.index(key)
            lows[i], highs[i] = max(lows[i], float(lo)), min(highs[i], float(hi))
    fixed = {k: float(v) for k, v in (fixed or {}).items() if k in PARAM_KEYS}
    for key, value in fixed.items():
        i = PARAM_KEYS.index(key)
        lows[i] = highs[i] = value

    # 1. 拉丁超立方全局采样
    unit = latin_hypercube(samples, len(PARAM_KEYS), rng)
    pool = _snap(lows + unit * (highs - lows))

    # 2. 局部细化
    evaluated = [pool]
    for round_idx in range(refine_rounds):
        all_points = np.vstack(evaluated)
        metrics = predictor(all_points)
        scores, _ = _score(metrics, cost_index(all_points), weights)
        top_idx = np.argsort(scores)[::-1][:refine_candidates]
        sigma = (highs - lows) * (0.08 / (round_idx + 1))
        children = []
        for idx in top_idx:
            noise = rng.normal(0.0, 1.0, size=(refine_size, len(PARAM_KEYS))) * sigma
            children.append(all_points[idx] + noise)
        child_matrix = np.clip(np.vstack(children), lows, highs)
        evaluated.append(_snap(child_matrix))

    all_points = np.unique(np.vstack(evaluated), axis=0)
    metrics = predictor(all_points)
    cost = cost_index(all_points)
    scores, ranges = _score(metrics, cost, weights)

    # 3. 结果整理
    order = np.argsort(scores)[::-1]
    top = []
    seen = set()
    for idx in order:
        signature = tuple(np.round(all_points[idx], 2))
        if signature in seen:
            continue
        seen.add(signature)
        top.append(_describe(all_points[idx], metrics[idx], cost[idx], scores[idx], len(top) + 1))
        if len(top) >= top_n:
            break

    front_idx = pareto_front(metrics[:, METRIC_KEYS.index("ucs")], cost)
    front = [
        {
            "ucs": round(float(metrics[i, METRIC_KEYS.index("ucs")]), 2),
            "cost": round(float(cost[i]), 2),
            "params": {key: _fmt(key, v) for key, v in zip(PARAM_KEYS, all_points[i])},
        }
        for i in front_idx
    ]
    cloud = rng.choice(len(all_points), size=min(160, len(all_points)), replace=False)
    scatter = [
        {"ucs": round(float(metrics[i, METRIC_KEYS.index("ucs")]), 2), "cost": round(float(cost[i]), 2)} for i in cloud
    ]

    return {
        "method": "拉丁超立方采样 + 高斯局部细化",
        "evaluated": int(len(all_points)),
        "weights": {k: round(v, 4) for k, v in weights.items()},
        "weightLabels": OBJECTIVE_LABELS,
        "fixed": fixed,
        "bounds": {key: [round(float(lows[i]), 3), round(float(highs[i]), 3)] for i, key in enumerate(PARAM_KEYS)},
        "objectiveRanges": ranges,
        "topSchemes": top,
        "pareto": front,
        "scatter": scatter,
    }


def _fmt(key: str, value: float):
    return int(round(float(value))) if key == "cycles" else round(float(value), 3)


def _describe(point: np.ndarray, metrics: np.ndarray, cost: float, score: float, rank: int) -> dict:
    return {
        "rank": rank,
        "schemeName": f"优化配比 {rank}",
        "params": {key: _fmt(key, v) for key, v in zip(PARAM_KEYS, point)},
        "paramLabels": PARAM_LABELS,
        "metrics": {key: round(float(v), 4) for key, v in zip(METRIC_KEYS, metrics)},
        "cost": round(float(cost), 2),
        "score": round(float(score), 4),
    }


def rank_schemes(predictor, schemes: list[dict], weights: dict | None = None) -> list[dict]:
    """对用户自建的方案列表按同一评分体系排序（替代旧版硬编码权重的推荐逻辑）。"""
    if not schemes:
        return []
    weights = _normalize_weights(weights)
    matrix = np.array([[float(s[key]) for key in PARAM_KEYS] for s in schemes], dtype=float)
    metrics = predictor(matrix)
    cost = cost_index(matrix)
    if len(schemes) == 1:
        scores = np.ones(1)
    else:
        scores, _ = _score(metrics, cost, weights)
    order = np.argsort(scores)[::-1]
    ranking = []
    for rank, idx in enumerate(order, 1):
        ranking.append(
            {
                "rank": rank,
                "scheme": schemes[idx],
                "schemeName": schemes[idx].get("schemeName", f"方案{idx + 1}"),
                "metrics": {key: round(float(v), 4) for key, v in zip(METRIC_KEYS, metrics[idx])},
                "cost": round(float(cost[idx]), 2),
                "score": round(float(scores[idx]), 4),
            }
        )
    return ranking
