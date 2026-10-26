"""参数敏感性分析。

提供三种互补的方法，输入都是一个向量化预测函数 ``predictor(matrix) -> (n, 7)``：

1. OAT 弹性系数（局部）：围绕当前方案，把每个参数在其区间的 ±10% 处取中心差分，
   计算无量纲弹性 E = (Δy / y) / (Δx / x)，逐指标输出，并给出综合重要度排序。
2. Morris 基本效应（全局筛选）：在参数区间构成的超立方体上生成 r 条轨迹，
   统计每个参数的 μ*（平均绝对效应）与 σ（效应离散度，反映非线性/交互强度）。
3. 偏依赖曲线（可视化）：固定其他参数，扫描单个参数，输出 7 项指标的响应曲线。
"""

from __future__ import annotations

import numpy as np

from .mechanism import clip_to_ranges, design_space_bounds
from .schemas import METRIC_KEYS, METRIC_LABELS, PARAM_KEYS, PARAM_LABELS, PARAM_RANGES, PARAM_UNITS


def _sample_vector(sample: dict) -> np.ndarray:
    return np.array([float(sample[key]) for key in PARAM_KEYS], dtype=float)


def oat_elasticity(predictor, sample: dict, step_ratio: float = 0.10) -> dict:
    """局部 OAT 弹性分析。

    返回::

        {
          "ranking": [{"key", "label", "score", "elasticity": {metric: E}}, ...],  # 综合重要度排序
          "matrix": {param: {metric: E}},                                            # 完整弹性矩阵
          "baseline": {metric: value}
        }
    """
    x0 = _sample_vector(sample)
    lows, highs = design_space_bounds()
    base = predictor(x0.reshape(1, -1))[0]

    plus = np.repeat(x0.reshape(1, -1), len(PARAM_KEYS), axis=0)
    minus = plus.copy()
    deltas = np.zeros(len(PARAM_KEYS))
    for i, key in enumerate(PARAM_KEYS):
        span = (highs[i] - lows[i]) * step_ratio
        if key == "cycles":
            span = max(1.0, round(span))
        hi = min(highs[i], x0[i] + span)
        lo = max(lows[i], x0[i] - span)
        plus[i, i] = hi
        minus[i, i] = lo
        deltas[i] = hi - lo
    y_plus = predictor(plus)
    y_minus = predictor(minus)

    matrix: dict[str, dict[str, float]] = {}
    ranking = []
    for i, key in enumerate(PARAM_KEYS):
        x_ref = x0[i] if abs(x0[i]) > 1e-9 else (deltas[i] or 1.0)
        elasticities = {}
        for j, metric in enumerate(METRIC_KEYS):
            y_ref = base[j] if abs(base[j]) > 1e-9 else 1.0
            dy = (y_plus[i, j] - y_minus[i, j]) / y_ref
            dx = deltas[i] / x_ref if deltas[i] else 1.0
            elasticities[metric] = round(float(dy / dx), 4) if dx else 0.0
        matrix[key] = elasticities
        importance = float(np.mean([abs(v) for v in elasticities.values()]))
        ranking.append({"key": key, "label": PARAM_LABELS[key], "unit": PARAM_UNITS[key], "raw": importance, "elasticity": elasticities})

    total = sum(item["raw"] for item in ranking) or 1.0
    for item in ranking:
        item["score"] = round(item.pop("raw") / total, 4)
    ranking.sort(key=lambda item: item["score"], reverse=True)
    return {
        "method": "OAT 弹性系数（±10% 区间，中心差分）",
        "ranking": ranking,
        "matrix": matrix,
        "baseline": {metric: round(float(v), 4) for metric, v in zip(METRIC_KEYS, base)},
    }


def morris_effects(predictor, trajectories: int = 12, levels: int = 6, seed: int = 42) -> dict:
    """Morris 基本效应法（全局敏感性筛选）。

    对每条轨迹：从网格上随机取起点，按随机顺序逐个参数增减 Δ = levels/(2(levels-1))
    （单位超立方尺度），每一步得到一个基本效应 EE = (y(x+Δe_i) - y(x)) / Δ。
    所有指标同时计算，返回每个指标下各参数的 μ* 与 σ。
    """
    rng = np.random.default_rng(seed)
    k = len(PARAM_KEYS)
    lows, highs = design_space_bounds()
    delta = levels / (2.0 * (levels - 1))
    grid = np.linspace(0.0, 1.0 - delta, levels // 2 if levels % 2 == 0 else levels // 2 + 1)

    effects = np.zeros((trajectories, k, len(METRIC_KEYS)))
    for t in range(trajectories):
        base = rng.choice(grid, size=k)
        order = rng.permutation(k)
        directions = rng.choice([-1.0, 1.0], size=k)
        points = [base.copy()]
        current = base.copy()
        for i in order:
            step = delta * directions[i]
            candidate = current[i] + step
            if candidate < 0.0 or candidate > 1.0:
                step = -step
            current = current.copy()
            current[i] = current[i] + step
            points.append(current)
        unit = np.array(points)
        physical = lows + unit * (highs - lows)
        physical[:, PARAM_KEYS.index("cycles")] = np.round(physical[:, PARAM_KEYS.index("cycles")])
        y = predictor(clip_to_ranges(physical))
        for step_idx, i in enumerate(order):
            dx = unit[step_idx + 1, i] - unit[step_idx, i]
            effects[t, i, :] = (y[step_idx + 1] - y[step_idx]) / dx

    # 用指标的全局响应幅度归一化，使不同量纲可比
    scale = np.maximum(np.abs(effects).reshape(-1, len(METRIC_KEYS)).max(axis=0), 1e-9)
    normalized = effects / scale

    by_metric = {}
    for j, metric in enumerate(METRIC_KEYS):
        rows = []
        for i, key in enumerate(PARAM_KEYS):
            ee = normalized[:, i, j]
            rows.append(
                {
                    "key": key,
                    "label": PARAM_LABELS[key],
                    "muStar": round(float(np.mean(np.abs(ee))), 4),
                    "mu": round(float(np.mean(ee)), 4),
                    "sigma": round(float(np.std(ee, ddof=1)) if len(ee) > 1 else 0.0, 4),
                }
            )
        rows.sort(key=lambda r: r["muStar"], reverse=True)
        by_metric[metric] = {"label": METRIC_LABELS[metric], "effects": rows}

    overall = []
    for i, key in enumerate(PARAM_KEYS):
        mu_star = float(np.mean(np.abs(normalized[:, i, :])))
        sigma = float(np.mean(np.std(normalized[:, i, :], axis=0, ddof=1)))
        overall.append({"key": key, "label": PARAM_LABELS[key], "muStar": round(mu_star, 4), "sigma": round(sigma, 4)})
    overall.sort(key=lambda r: r["muStar"], reverse=True)
    return {
        "method": f"Morris 基本效应法（{trajectories} 条轨迹，{levels} 水平）",
        "trajectories": trajectories,
        "levels": levels,
        "evaluations": int(trajectories * (k + 1)),
        "overall": overall,
        "byMetric": by_metric,
    }


def partial_dependence(predictor, sample: dict, param: str, points: int = 15) -> dict:
    """固定其他参数于当前方案，扫描 ``param`` 全区间，返回各指标响应曲线。"""
    if param not in PARAM_KEYS:
        raise ValueError(f"未知参数: {param}")
    x0 = _sample_vector(sample)
    low, high = PARAM_RANGES[param]
    idx = PARAM_KEYS.index(param)
    if param == "cycles":
        xs = np.arange(int(low), int(high) + 1, dtype=float)
    else:
        xs = np.linspace(low, high, points)
    grid = np.repeat(x0.reshape(1, -1), len(xs), axis=0)
    grid[:, idx] = xs
    ys = predictor(grid)
    curves = {
        metric: [round(float(v), 4) for v in ys[:, j]] for j, metric in enumerate(METRIC_KEYS)
    }
    # 标记当前方案所在位置
    current = predictor(x0.reshape(1, -1))[0]
    return {
        "param": param,
        "label": PARAM_LABELS[param],
        "unit": PARAM_UNITS[param],
        "x": [round(float(v), 4) for v in xs],
        "curves": curves,
        "current": {"x": float(x0[idx]), "y": {metric: round(float(v), 4) for metric, v in zip(METRIC_KEYS, current)}},
    }


def full_partial_dependence(predictor, sample: dict, points: int = 12) -> dict:
    return {key: partial_dependence(predictor, sample, key, points) for key in PARAM_KEYS}
