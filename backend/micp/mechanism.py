"""MICP-椰壳纤维协同固化砂土的机理模型。

本模块把 8 项试验参数转换为具有物理意义的中间量（机理特征），并由此推算
7 项固化性能指标的机理基线值。它承担三个角色：

1. 小样本（历史样本不足）时的独立预测器；
2. 机器学习模型的"先验"：学习器只拟合 ``实测值 - 机理基线`` 的残差，
   使模型在训练域外仍保持合理趋势；
3. 为敏感性分析、配比优化、报告解释提供可追溯的中间变量。

模型链条（所有系数见 ``MechanismConstants``）：

    菌液体积 × OD600 ─► 有效菌量 B_eff ─► 脲酶饱和项 s_B = B/(K_B + B)
    固化温度 T       ─► 高斯型活性因子 f_T = exp(-((T-T_opt)/σ_T)²)
    胶结液浓度 × 体积 ─► 单轮钙源 M_c = C·V_f/1000 (mol)
    干密度 ρ_d       ─► 孔隙率 n₀ = 1 - ρ_d/G_s ─► 孔隙体积 V_p
    V_p / V_f        ─► 灌注液利用率 u
    胶结液浓度 C     ─► 高浓度抑制因子 f_C = exp(-((C-C₀)⁺/σ_C)²)
    逐轮累加：ΔCaCO₃(k) = M_c·M_w·η_max·s_B·f_T·u·f_C·(1-φ_{k-1})³·exp(-k_clog·(k-1))
    CaCO₃ 质量 ─► 碳酸钙含量 w_c、孔隙填充率 φ、固化后干密度
    纤维掺量 f       ─► 桥接因子 F = (f/f_opt)·exp(1 - f/f_opt)
    w_c, φ, F, ρ_d   ─► UCS、黏聚力、内摩擦角、渗透系数（Kozeny-Carman）、崩解率
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .schemas import FEATURE_KEYS, METRIC_KEYS, PARAM_KEYS, PARAM_RANGES


@dataclass(frozen=True)
class MechanismConstants:
    """机理模型常数。数值依据 MICP 文献常见量级与本系统内置样本标定。"""

    # 颗粒与试样几何
    specific_gravity: float = 2.65        # 石英砂比重 G_s
    sample_volume_cm3: float = 96.0       # 标准三轴/UCS 试样 Φ39.1mm × 80mm 的体积
    calcite_density: float = 2.71         # 方解石密度 g/cm³
    calcite_molar_mass: float = 100.09    # CaCO₃ 摩尔质量 g/mol

    # 菌液与脲酶活性
    bacteria_half_saturation: float = 50.0  # K_B (mL·OD)：饱和项半饱和常数
    temperature_optimum: float = 30.0       # 巴氏芽孢杆菌脲酶活性最优温度 ℃
    temperature_sigma: float = 9.0          # 活性高斯分布标准差 ℃
    temperature_floor: float = 0.25         # 低温/高温下的活性下限

    # 钙源转化
    max_conversion: float = 0.85          # 理想条件下单轮钙源转化率上限 η_max
    clogging_decay: float = 0.03          # 逐轮注入通道衰减系数 k_clog
    clogging_exponent: float = 3.0        # 孔隙填充对后续轮次效率的抑制指数 (1-φ)^m
    utilization_scale: float = 2.4        # 灌注液利用率尺度：u = min(1, 2.4·V_p/V_f)，即 2.4 倍孔隙体积内完全利用
    utilization_floor: float = 0.35
    inhibition_onset: float = 0.75        # 胶结液浓度抑制起点 mol/L
    inhibition_sigma: float = 1.8         # 抑制高斯宽度 mol/L

    # 纤维
    fiber_optimum: float = 0.40           # 最优纤维掺量 %
    fiber_cluster_threshold: float = 0.75 # 超过该掺量出现团聚，桥接效果衰减
    fiber_cluster_penalty: float = 0.45

    # 强度与变形
    ucs_coefficient: float = 34.0
    ucs_exponent: float = 1.08
    ucs_density_exponent: float = 2.0
    ucs_fiber_gain: float = 0.35
    cohesion_base: float = 6.0
    cohesion_per_caco3: float = 3.0
    cohesion_fiber_gain: float = 10.0
    friction_base: float = 26.0
    friction_density_gain: float = 10.0
    friction_log_gain: float = 2.0
    friction_fiber_gain: float = 1.5

    # 渗透与崩解
    permeability_reference: float = 9.0   # 未固化、n₀=0.40 时的参考渗透系数 (×10⁻⁴ cm/s)
    permeability_reference_porosity: float = 0.40
    permeability_fiber_reduction: float = 0.10
    disintegration_base: float = 42.0     # 未固化砂柱的浸水崩解率 %
    disintegration_decay: float = 3.6     # 随孔隙填充率的指数衰减系数
    disintegration_fiber_gain: float = 0.30
    disintegration_floor: float = 1.5


CONST = MechanismConstants()


def _as_matrix(samples) -> np.ndarray:
    """把 dict / list[dict] / ndarray 统一为 (n, 8) 浮点矩阵，列顺序为 PARAM_KEYS。"""
    if isinstance(samples, dict):
        samples = [samples]
    if isinstance(samples, np.ndarray):
        matrix = np.asarray(samples, dtype=float)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        return matrix
    return np.array([[float(row[key]) for key in PARAM_KEYS] for row in samples], dtype=float)


def clip_to_ranges(matrix: np.ndarray) -> np.ndarray:
    lows = np.array([PARAM_RANGES[key][0] for key in PARAM_KEYS])
    highs = np.array([PARAM_RANGES[key][1] for key in PARAM_KEYS])
    return np.clip(matrix, lows, highs)


def mechanism_features_matrix(samples, const: MechanismConstants = CONST) -> tuple[np.ndarray, np.ndarray]:
    """计算机理特征。

    返回 ``(features, caco3_percent)``：
    - ``features``：(n, 8) 矩阵，列顺序为 FEATURE_KEYS；
    - ``caco3_percent``：(n,) 理论碳酸钙质量分数（%），是后续各指标的核心中间量。
    """
    X = _as_matrix(samples)
    col = {key: X[:, idx] for idx, key in enumerate(PARAM_KEYS)}

    rho_d = col["dryDensity"]
    fiber = col["fiberContent"]
    v_b = col["bacterialVolume"]
    od = col["odValue"]
    temp = col["temperature"]
    conc = col["cementationDose"]
    v_f = col["fixationVolume"]
    cycles = np.maximum(np.round(col["cycles"]), 1)

    # 1. 有效菌量与脲酶饱和
    effective_bacteria = v_b * od
    saturation = effective_bacteria / (const.bacteria_half_saturation + effective_bacteria)

    # 2. 温度活性因子（高斯型，带下限）
    temperature_factor = np.exp(-((temp - const.temperature_optimum) / const.temperature_sigma) ** 2)
    temperature_factor = const.temperature_floor + (1 - const.temperature_floor) * temperature_factor

    # 3. 孔隙结构
    initial_porosity = np.clip(1.0 - rho_d / const.specific_gravity, 0.05, 0.6)
    pore_volume = const.sample_volume_cm3 * initial_porosity

    # 4. 灌注液利用率：胶结液体积远大于孔隙体积时多余液体流失
    utilization = np.clip(const.utilization_scale * pore_volume / np.maximum(v_f, 1e-6), const.utilization_floor, 1.0)

    # 5. 高浓度胶结液对脲酶的抑制（>0.75 mol/L 后效率下降）
    inhibition = np.exp(-(np.maximum(conc - const.inhibition_onset, 0.0) / const.inhibition_sigma) ** 2)

    # 6. 逐轮钙源供给与累计 CaCO₃ 质量
    #    每一轮的转化效率 = 基础效率 × (1 - 上一轮孔隙填充率)^m × 轮次衰减
    #    即沉淀越多、孔隙越堵，后续灌注液越难进入并反应
    calcium_per_cycle = conc * v_f / 1000.0
    per_cycle_efficiency = const.max_conversion * saturation * temperature_factor * utilization * inhibition
    dry_mass = rho_d * const.sample_volume_cm3
    calcite_mass = np.zeros_like(rho_d)
    pore_filling = np.zeros_like(rho_d)
    for k in range(int(cycles.max())):
        active = (cycles > k).astype(float)
        efficiency_k = per_cycle_efficiency * (1.0 - pore_filling) ** const.clogging_exponent * np.exp(-const.clogging_decay * k)
        calcite_mass = calcite_mass + active * calcium_per_cycle * const.calcite_molar_mass * efficiency_k
        pore_filling = np.clip(calcite_mass / const.calcite_density / np.maximum(pore_volume, 1e-6), 0.0, 0.95)
    calcium_supply = calcium_per_cycle * cycles
    conversion_efficiency = calcite_mass / np.maximum(calcium_supply * const.calcite_molar_mass, 1e-9)

    # 6. 纤维桥接因子：单峰函数 + 团聚惩罚
    ratio = fiber / const.fiber_optimum
    bridging = ratio * np.exp(1.0 - ratio)
    over = np.clip((fiber - const.fiber_cluster_threshold) / (1.0 - const.fiber_cluster_threshold), 0.0, 1.0)
    bridging = bridging * (1.0 - const.fiber_cluster_penalty * over)

    features = np.column_stack(
        [
            effective_bacteria,
            temperature_factor,
            calcium_supply,
            conversion_efficiency,
            bridging,
            initial_porosity,
            pore_filling,
            utilization,
        ]
    )
    # 附加一列 CaCO₃ 质量分数供 baseline 使用（不属于 FEATURE_KEYS）
    caco3_percent = calcite_mass / np.maximum(dry_mass, 1e-6) * 100.0
    return features, caco3_percent


def mechanism_baseline_matrix(samples, const: MechanismConstants = CONST) -> np.ndarray:
    """由机理特征推算 7 项性能指标，返回 (n, 7) 矩阵，列顺序为 METRIC_KEYS。"""
    X = _as_matrix(samples)
    features, caco3 = mechanism_features_matrix(X, const)
    rho_d = X[:, PARAM_KEYS.index("dryDensity")]
    bridging = features[:, FEATURE_KEYS.index("fiberBridging")]
    n0 = features[:, FEATURE_KEYS.index("initialPorosity")]
    filling = features[:, FEATURE_KEYS.index("poreFillingRatio")]

    # 固化后干密度：CaCO₃ 沉积在孔隙中增加试样干质量
    post_density = rho_d * (1.0 + caco3 / 100.0)

    # UCS：对碳酸钙含量的幂律关系 × 密实度修正 × 纤维桥接增益
    ucs = (
        const.ucs_coefficient
        * np.power(np.maximum(caco3, 0.05), const.ucs_exponent)
        * np.power(rho_d / 1.6, const.ucs_density_exponent)
        * (1.0 + const.ucs_fiber_gain * bridging)
    )

    # 黏聚力：胶结贡献 + 纤维拉筋贡献
    cohesion = const.cohesion_base + const.cohesion_per_caco3 * caco3 + const.cohesion_fiber_gain * bridging

    # 内摩擦角：密实度 + 胶结粗糙化（对数饱和） + 纤维咬合
    friction = (
        const.friction_base
        + const.friction_density_gain * (rho_d - 1.4)
        + const.friction_log_gain * np.log1p(caco3)
        + const.friction_fiber_gain * bridging
    )

    # 渗透系数：Kozeny-Carman 孔隙率函数 n³/(1-n)² 的相对变化
    n_after = n0 * (1.0 - filling)

    def kc(n: np.ndarray) -> np.ndarray:
        return np.power(n, 3) / np.power(np.maximum(1.0 - n, 1e-6), 2)

    k_ref = const.permeability_reference * kc(n0) / kc(np.full_like(n0, const.permeability_reference_porosity))
    permeability = k_ref * kc(n_after) / kc(n0) * (1.0 - const.permeability_fiber_reduction * bridging)

    # 浸水崩解率：随孔隙填充率指数衰减，纤维约束进一步降低
    disintegration = (
        const.disintegration_base
        * np.exp(-const.disintegration_decay * filling)
        * (1.0 - const.disintegration_fiber_gain * bridging)
    )
    disintegration = np.maximum(disintegration, const.disintegration_floor)

    baseline = np.column_stack([ucs, post_density, disintegration, permeability, friction, cohesion, caco3])
    assert baseline.shape[1] == len(METRIC_KEYS)
    return baseline


def mechanism_features(sample: dict) -> dict:
    """单样本机理特征（带键名），用于接口返回与报告解释。"""
    features, caco3 = mechanism_features_matrix(sample)
    result = {key: round(float(value), 4) for key, value in zip(FEATURE_KEYS, features[0])}
    result["theoreticalCaco3"] = round(float(caco3[0]), 4)
    return result


def mechanism_baseline(sample: dict) -> dict:
    """单样本机理基线预测（带键名）。"""
    baseline = mechanism_baseline_matrix(sample)[0]
    return {key: round(float(value), 4) for key, value in zip(METRIC_KEYS, baseline)}


def explain_mechanism(sample: dict) -> list[dict]:
    """生成面向用户的机理解释条目，供前端和报告直接展示。"""
    feats = mechanism_features(sample)
    base = mechanism_baseline(sample)
    temp = float(sample["temperature"])
    fiber = float(sample["fiberContent"])
    notes = [
        {
            "title": "菌液活性",
            "text": f"有效菌量指数 {feats['effectiveBacteria']:.1f} mL·OD，脲酶饱和度 "
                    f"{feats['effectiveBacteria'] / (CONST.bacteria_half_saturation + feats['effectiveBacteria']):.2f}；"
                    f"{temp:.0f}℃ 对应温度活性因子 {feats['temperatureFactor']:.2f}。",
        },
        {
            "title": "钙源转化",
            "text": f"累计钙源 {feats['calciumSupply']:.3f} mol，平均转化效率 {feats['conversionEfficiency']:.2f}，"
                    f"理论碳酸钙含量 {feats['theoreticalCaco3']:.2f}%。",
        },
        {
            "title": "孔隙填充",
            "text": f"初始孔隙率 {feats['initialPorosity']:.3f}，碳酸钙填充孔隙 {feats['poreFillingRatio'] * 100:.1f}%，"
                    f"灌注液利用率 {feats['liquidUtilization']:.2f}。",
        },
        {
            "title": "纤维桥接",
            "text": (
                f"纤维掺量 {fiber:.2f}% 位于最优掺量 {CONST.fiber_optimum:.2f}% "
                + ("附近，桥接因子 " if abs(fiber - CONST.fiber_optimum) < 0.12 else ("以下，桥接因子 " if fiber < CONST.fiber_optimum else "以上，团聚效应显现，桥接因子 "))
                + f"{feats['fiberBridging']:.2f}。"
            ),
        },
        {
            "title": "机理基线",
            "text": f"由上述链条推算 UCS {base['ucs']:.0f} kPa、崩解率 {base['disintegrationRate']:.1f}%、"
                    f"渗透系数 {base['permeability']:.2f}×10⁻⁴ cm/s。",
        },
    ]
    return notes


def design_space_bounds() -> tuple[np.ndarray, np.ndarray]:
    lows = np.array([PARAM_RANGES[key][0] for key in PARAM_KEYS], dtype=float)
    highs = np.array([PARAM_RANGES[key][1] for key in PARAM_KEYS], dtype=float)
    return lows, highs


def matrix_to_samples(matrix: np.ndarray, prefix: str = "候选") -> list[dict]:
    """把 (n, 8) 矩阵转回方案字典列表，整数型参数四舍五入。"""
    samples = []
    for idx, row in enumerate(matrix, 1):
        sample = {"schemeName": f"{prefix}{idx:02d}"}
        for key, value in zip(PARAM_KEYS, row):
            sample[key] = int(round(float(value))) if key == "cycles" else round(float(value), 3)
        samples.append(sample)
    return samples


def soil_mass_g(dry_density: float) -> float:
    return dry_density * CONST.sample_volume_cm3


def pore_volume_cm3(dry_density: float) -> float:
    return CONST.sample_volume_cm3 * (1.0 - dry_density / CONST.specific_gravity)


__all__ = [
    "CONST",
    "MechanismConstants",
    "clip_to_ranges",
    "design_space_bounds",
    "explain_mechanism",
    "matrix_to_samples",
    "mechanism_baseline",
    "mechanism_baseline_matrix",
    "mechanism_features",
    "mechanism_features_matrix",
    "pore_volume_cm3",
    "soil_mass_g",
]
