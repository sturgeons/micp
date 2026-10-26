"""试验数据统计分析。

- 异常值：IQR 规则（稳健、对分布无假设）+ Grubbs 检验（正态假设、给出显著性），
  两者取并集并记录每条被剔除样本的原因；
- 描述统计：均值、标准差、变异系数、极值、中位数、四分位、偏度；
- 单因素方差分析：F 值、p 值（F 分布右尾）、η²；因素水平过多时自动按分位数分箱；
- 相关分析：Pearson r 与双侧 p 值矩阵，覆盖 8 参数 + 7 指标；
- 回归拟合：UCS-CaCO₃ 线性与幂函数（对数线性化）拟合，返回方程、R²。
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats

from .schemas import METRIC_KEYS, METRIC_LABELS, METRIC_UNITS, PARAM_KEYS, PARAM_LABELS


# ---------------------------------------------------------------------------- 异常值
def iqr_bounds(values: np.ndarray, k: float = 1.5) -> tuple[float, float]:
    q1, q3 = np.percentile(values, [25, 75])
    iqr = q3 - q1
    return float(q1 - k * iqr), float(q3 + k * iqr)


def grubbs_outliers(values: np.ndarray, alpha: float = 0.05, max_iter: int = 5) -> list[int]:
    """迭代 Grubbs 检验，返回被判定为异常的原始索引。"""
    idx = np.arange(len(values))
    data = values.astype(float).copy()
    flagged: list[int] = []
    for _ in range(max_iter):
        n = len(data)
        if n < 7:
            break
        mean, sd = data.mean(), data.std(ddof=1)
        if sd <= 1e-12:
            break
        deviations = np.abs(data - mean)
        pos = int(np.argmax(deviations))
        g = deviations[pos] / sd
        t_crit = stats.t.ppf(1 - alpha / (2 * n), n - 2)
        g_crit = (n - 1) / math.sqrt(n) * math.sqrt(t_crit ** 2 / (n - 2 + t_crit ** 2))
        if g > g_crit:
            flagged.append(int(idx[pos]))
            data = np.delete(data, pos)
            idx = np.delete(idx, pos)
        else:
            break
    return flagged


def detect_outliers(dataset: list[dict], metric: str = "ucs") -> tuple[list[dict], list[dict]]:
    """返回 (清洗后样本, 剔除明细)。样本不足 4 条时不做剔除。"""
    if len(dataset) < 4:
        return list(dataset), []
    values = np.array([float(row[metric]) for row in dataset])
    lower, upper = iqr_bounds(values)
    removed: dict[int, dict] = {}
    for i, v in enumerate(values):
        if v < lower or v > upper:
            removed[i] = {
                "sampleId": dataset[i].get("sampleId", f"#{i + 1}"),
                "metric": metric,
                "value": float(v),
                "method": "IQR",
                "reason": f"超出 [{lower:.2f}, {upper:.2f}]",
            }
    for i in grubbs_outliers(values):
        if i not in removed:
            removed[i] = {
                "sampleId": dataset[i].get("sampleId", f"#{i + 1}"),
                "metric": metric,
                "value": float(values[i]),
                "method": "Grubbs",
                "reason": "Grubbs 检验 α=0.05 显著",
            }
    clean = [row for i, row in enumerate(dataset) if i not in removed]
    return clean, [removed[i] for i in sorted(removed)]


# ---------------------------------------------------------------------------- 描述统计
def describe(values: np.ndarray) -> dict:
    if len(values) == 0:
        return {"count": 0}
    mean = float(values.mean())
    sd = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    return {
        "count": int(len(values)),
        "mean": round(mean, 4),
        "std": round(sd, 4),
        "cv": round(sd / mean, 4) if abs(mean) > 1e-12 else 0.0,
        "min": round(float(values.min()), 4),
        "q1": round(float(np.percentile(values, 25)), 4),
        "median": round(float(np.median(values)), 4),
        "q3": round(float(np.percentile(values, 75)), 4),
        "max": round(float(values.max()), 4),
        "skew": round(float(stats.skew(values, bias=False)), 4) if len(values) > 2 else 0.0,
    }


# ---------------------------------------------------------------------------- 方差分析
def _bin_factor(values: list[float], max_levels: int = 5) -> list[str]:
    unique = sorted(set(values))
    if len(unique) <= max_levels:
        return [f"{v:g}" for v in values]
    edges = np.quantile(values, np.linspace(0, 1, max_levels + 1))
    labels = []
    for v in values:
        pos = int(np.searchsorted(edges[1:-1], v, side="right"))
        labels.append(f"[{edges[pos]:.2f}, {edges[pos + 1]:.2f}]")
    return labels


def one_way_anova(dataset: list[dict], factor: str = "fiberContent", response: str = "ucs") -> dict:
    groups: dict[str, list[float]] = {}
    factor_values = [float(row[factor]) for row in dataset]
    order: dict[str, float] = {}
    for label, value, row in zip(_bin_factor(factor_values), factor_values, dataset):
        groups.setdefault(label, []).append(float(row[response]))
        order[label] = min(order.get(label, value), value)
    groups = dict(sorted(groups.items(), key=lambda item: order[item[0]]))  # 按因素水平升序排列
    arrays = [np.array(v) for v in groups.values() if len(v) > 0]
    flat = np.concatenate(arrays) if arrays else np.array([])
    k, n = len(arrays), len(flat)
    if k < 2 or n <= k:
        return {"factor": factor, "response": response, "groups": [], "fValue": 0.0, "pValue": 1.0, "eta2": 0.0, "effect": 0.0, "significant": False, "conclusion": "样本或分组数量不足，无法进行方差分析。"}
    grand = flat.mean()
    ss_between = float(sum(len(g) * (g.mean() - grand) ** 2 for g in arrays))
    ss_within = float(sum(((g - g.mean()) ** 2).sum() for g in arrays))
    df_b, df_w = k - 1, n - k
    ms_b, ms_w = ss_between / df_b, ss_within / df_w if df_w else 0.0
    f_value = ms_b / ms_w if ms_w > 1e-12 else float("inf")
    p_value = float(stats.f.sf(f_value, df_b, df_w)) if math.isfinite(f_value) else 0.0
    eta2 = ss_between / (ss_between + ss_within) if (ss_between + ss_within) > 0 else 0.0
    return {
        "factor": factor,
        "factorLabel": PARAM_LABELS.get(factor, factor),
        "response": response,
        "responseLabel": METRIC_LABELS.get(response, response),
        "groups": [
            {"level": label, "count": len(v), "mean": round(float(np.mean(v)), 4), "std": round(float(np.std(v, ddof=1)) if len(v) > 1 else 0.0, 4)}
            for label, v in groups.items()
        ],
        "dfBetween": df_b,
        "dfWithin": df_w,
        "ssBetween": round(ss_between, 4),
        "ssWithin": round(ss_within, 4),
        "fValue": round(f_value, 4) if math.isfinite(f_value) else None,
        "pValue": round(p_value, 6),
        "eta2": round(eta2, 4),
        "effect": round(eta2, 4),
        "significant": p_value < 0.05,
        "conclusion": (
            f"{PARAM_LABELS.get(factor, factor)}对{METRIC_LABELS.get(response, response)}影响显著（p={p_value:.4f} < 0.05），效应量 η²={eta2:.3f}。"
            if p_value < 0.05
            else f"{PARAM_LABELS.get(factor, factor)}对{METRIC_LABELS.get(response, response)}影响不显著（p={p_value:.4f}）。"
        ),
    }


# ---------------------------------------------------------------------------- 相关分析
def correlation_matrix(dataset: list[dict], keys: list[str] | None = None) -> dict:
    keys = keys or (PARAM_KEYS + METRIC_KEYS)
    labels = {**PARAM_LABELS, **METRIC_LABELS}
    matrix = np.array([[float(row.get(key, np.nan)) for key in keys] for row in dataset], dtype=float)
    n = len(dataset)
    r = np.zeros((len(keys), len(keys)))
    p = np.ones((len(keys), len(keys)))
    for i in range(len(keys)):
        for j in range(len(keys)):
            if i == j:
                r[i, j], p[i, j] = 1.0, 0.0
                continue
            x, y = matrix[:, i], matrix[:, j]
            if n < 3 or np.std(x) < 1e-12 or np.std(y) < 1e-12:
                continue
            res = stats.pearsonr(x, y)
            r[i, j], p[i, j] = float(res.statistic), float(res.pvalue)
    strongest = []
    for i, pk in enumerate(PARAM_KEYS):
        if pk not in keys:
            continue
        for mk in METRIC_KEYS:
            if mk not in keys:
                continue
            j = keys.index(mk)
            strongest.append({"param": pk, "metric": mk, "paramLabel": labels[pk], "metricLabel": labels[mk], "r": round(float(r[keys.index(pk), j]), 4), "p": round(float(p[keys.index(pk), j]), 6)})
    strongest.sort(key=lambda item: abs(item["r"]), reverse=True)
    return {
        "keys": keys,
        "labels": [labels.get(k, k) for k in keys],
        "r": np.round(r, 4).tolist(),
        "p": np.round(p, 6).tolist(),
        "sampleSize": n,
        "topPairs": strongest[:10],
    }


# ---------------------------------------------------------------------------- 回归拟合
def fit_relationship(dataset: list[dict], x_key: str = "caco3", y_key: str = "ucs") -> dict:
    x = np.array([float(row[x_key]) for row in dataset])
    y = np.array([float(row[y_key]) for row in dataset])
    out = {"x": x_key, "y": y_key, "xLabel": METRIC_LABELS.get(x_key, PARAM_LABELS.get(x_key, x_key)), "yLabel": METRIC_LABELS.get(y_key, y_key), "n": int(len(x))}
    if len(x) < 3 or np.std(x) < 1e-12:
        out["linear"] = out["power"] = None
        return out
    lin = stats.linregress(x, y)
    out["linear"] = {
        "slope": round(float(lin.slope), 4),
        "intercept": round(float(lin.intercept), 4),
        "r2": round(float(lin.rvalue ** 2), 4),
        "p": round(float(lin.pvalue), 6),
        "equation": f"{y_key} = {lin.slope:.3f}·{x_key} {'+' if lin.intercept >= 0 else '-'} {abs(lin.intercept):.2f}",
    }
    mask = (x > 0) & (y > 0)
    if mask.sum() >= 3:
        pw = stats.linregress(np.log(x[mask]), np.log(y[mask]))
        a, b = math.exp(pw.intercept), pw.slope
        pred = a * np.power(x[mask], b)
        ss_res = float(np.sum((y[mask] - pred) ** 2))
        ss_tot = float(np.sum((y[mask] - y[mask].mean()) ** 2))
        out["power"] = {
            "a": round(a, 4),
            "b": round(float(b), 4),
            "r2": round(1 - ss_res / ss_tot if ss_tot > 0 else 0.0, 4),
            "equation": f"{y_key} = {a:.3f}·{x_key}^{b:.3f}",
        }
    else:
        out["power"] = None
    return out


# ---------------------------------------------------------------------------- 组合入口
def analyze_dataset(dataset: list[dict], factor: str = "fiberContent", response: str = "ucs") -> dict:
    clean, removed = detect_outliers(dataset, response)
    metric_stats = []
    for metric in METRIC_KEYS:
        values = np.array([float(row[metric]) for row in clean]) if clean else np.array([])
        entry = {"key": metric, "label": METRIC_LABELS[metric], "unit": METRIC_UNITS[metric]}
        entry.update(describe(values))
        metric_stats.append(entry)
    anova = one_way_anova(clean, factor, response) if len(clean) >= 3 else one_way_anova([], factor, response)
    regression = fit_relationship(clean, "caco3", "ucs") if len(clean) >= 3 else None
    return {
        "metricStats": metric_stats,
        "removed": len(removed),
        "removedDetails": removed,
        "sampleSize": len(clean),
        "rawSampleSize": len(dataset),
        "anova": anova,
        "regression": regression,
        "factor": factor,
        "response": response,
    }
