"""内置示范数据集生成器。

系统出厂时没有真实试验数据，为了让模型训练、交叉验证、方差分析等功能在
首次启动时即可演示，这里按"试验设计 + 机理模型 + 受控噪声"生成 48 条样本：

- 纤维掺量取 5 个水平（0、0.2、0.4、0.6、0.8 %），每个水平 9~10 组，
  保证单因素方差分析有足够的组内自由度；
- 其余 7 个参数使用拉丁超立方分层采样，覆盖整个可行域；
- 性能指标 = 机理基线 × (1 + 二阶修正) × (1 + 测量噪声)，
  二阶修正包含温度-OD 交互与高干密度下的渗透衰减加速，用于模拟机理模型
  未覆盖的效应，使残差学习有"可学"的信号；
- 全部随机数由固定种子驱动，任何环境下生成结果一致。

生成的数据仅作演示与功能验证，不代表任何真实试验结论。
"""

from __future__ import annotations

import numpy as np

from .mechanism import mechanism_baseline_matrix
from .schemas import METRIC_KEYS, PARAM_KEYS, PARAM_RANGES

SEED = 20260623
SAMPLE_COUNT = 48
FIBER_LEVELS = (0.0, 0.2, 0.4, 0.6, 0.8)
NOISE_CV = {
    "ucs": 0.05,
    "postDryDensity": 0.012,
    "disintegrationRate": 0.08,
    "permeability": 0.06,
    "frictionAngle": 0.025,
    "cohesion": 0.06,
    "caco3": 0.05,
}
DECIMALS = {
    "ucs": 0,
    "postDryDensity": 3,
    "disintegrationRate": 1,
    "permeability": 2,
    "frictionAngle": 1,
    "cohesion": 1,
    "caco3": 2,
}


def _lhs(n: int, dims: int, rng: np.random.Generator) -> np.ndarray:
    cut = np.linspace(0, 1, n + 1)
    u = rng.random((n, dims))
    pts = cut[:-1][:, None] + u * (cut[1:] - cut[:-1])[:, None]
    for d in range(dims):
        pts[:, d] = pts[rng.permutation(n), d]
    return pts


def generate_dataset(count: int = SAMPLE_COUNT, seed: int = SEED) -> list[dict]:
    rng = np.random.default_rng(seed)
    unit = _lhs(count, len(PARAM_KEYS), rng)
    lows = np.array([PARAM_RANGES[k][0] for k in PARAM_KEYS])
    highs = np.array([PARAM_RANGES[k][1] for k in PARAM_KEYS])

    # 为了让示范数据集中在工程常用区间，而不是均匀铺满极端值，收缩采样区间
    shrink_low = np.array([1.45, 0.0, 60, 0.6, 22, 0.4, 50, 2])
    shrink_high = np.array([1.80, 1.0, 220, 2.2, 38, 1.8, 200, 8])
    X = shrink_low + unit * (shrink_high - shrink_low)
    X = np.clip(X, lows, highs)

    fiber_idx = PARAM_KEYS.index("fiberContent")
    X[:, fiber_idx] = np.array([FIBER_LEVELS[i % len(FIBER_LEVELS)] for i in range(count)])
    rng.shuffle(X[:, fiber_idx])
    cycles_idx = PARAM_KEYS.index("cycles")
    X[:, cycles_idx] = np.round(X[:, cycles_idx])
    X[:, PARAM_KEYS.index("dryDensity")] = np.round(X[:, PARAM_KEYS.index("dryDensity")], 2)
    X[:, PARAM_KEYS.index("bacterialVolume")] = np.round(X[:, PARAM_KEYS.index("bacterialVolume")] / 5) * 5
    X[:, PARAM_KEYS.index("odValue")] = np.round(X[:, PARAM_KEYS.index("odValue")], 2)
    X[:, PARAM_KEYS.index("temperature")] = np.round(X[:, PARAM_KEYS.index("temperature")])
    X[:, PARAM_KEYS.index("cementationDose")] = np.round(X[:, PARAM_KEYS.index("cementationDose")], 2)
    X[:, PARAM_KEYS.index("fixationVolume")] = np.round(X[:, PARAM_KEYS.index("fixationVolume")] / 5) * 5

    Y = mechanism_baseline_matrix(X)

    # 二阶修正：机理模型未显式刻画的效应
    temp = X[:, PARAM_KEYS.index("temperature")]
    od = X[:, PARAM_KEYS.index("odValue")]
    rho = X[:, PARAM_KEYS.index("dryDensity")]
    interaction = 0.06 * ((temp - 30) / 10) * ((od - 1.4) / 0.8)        # 温度-菌浓交互
    dense_penalty = 0.08 * np.clip((rho - 1.65) / 0.15, 0, 1)            # 高密实度下的渗透衰减加速
    Y[:, METRIC_KEYS.index("ucs")] *= 1 + interaction
    Y[:, METRIC_KEYS.index("caco3")] *= 1 + 0.5 * interaction
    Y[:, METRIC_KEYS.index("permeability")] *= 1 - dense_penalty
    Y[:, METRIC_KEYS.index("cohesion")] *= 1 + 0.8 * interaction

    # 测量噪声
    for j, key in enumerate(METRIC_KEYS):
        Y[:, j] *= 1 + rng.normal(0, NOISE_CV[key], size=count)

    dataset = []
    for i in range(count):
        row = {"sampleId": f"S{i + 1:02d}"}
        for j, key in enumerate(PARAM_KEYS):
            value = float(X[i, j])
            row[key] = int(round(value)) if key == "cycles" else round(value, 2)
        for j, key in enumerate(METRIC_KEYS):
            value = float(max(Y[i, j], 0.0))
            row[key] = int(round(value)) if DECIMALS[key] == 0 else round(value, DECIMALS[key])
        dataset.append(row)
    return dataset


DEFAULT_SCHEMES = [
    {"schemeName": "基准方案 A", "dryDensity": 1.60, "fiberContent": 0.0, "bacterialVolume": 120, "odValue": 1.20, "temperature": 30, "cementationDose": 0.80, "fixationVolume": 90, "cycles": 4},
    {"schemeName": "纤维增韧方案 B", "dryDensity": 1.60, "fiberContent": 0.40, "bacterialVolume": 120, "odValue": 1.20, "temperature": 30, "cementationDose": 0.80, "fixationVolume": 90, "cycles": 4},
    {"schemeName": "高胶结方案 C", "dryDensity": 1.64, "fiberContent": 0.40, "bacterialVolume": 150, "odValue": 1.50, "temperature": 32, "cementationDose": 1.20, "fixationVolume": 120, "cycles": 6},
    {"schemeName": "低成本方案 D", "dryDensity": 1.58, "fiberContent": 0.20, "bacterialVolume": 80, "odValue": 1.00, "temperature": 28, "cementationDose": 0.50, "fixationVolume": 70, "cycles": 3},
]


if __name__ == "__main__":
    import json

    print(json.dumps(generate_dataset()[:3], ensure_ascii=False, indent=2))
