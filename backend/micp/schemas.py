"""参数字典与指标字典。

本模块是整个算法层的"数据契约"：
- 试验参数（输入）：8 项，含单位、物理意义、合理区间、CSV 表头别名；
- 性能指标（输出）：7 项，含单位、优化方向（越大越好 / 越小越好）；
- 机理派生特征：由 ``mechanism`` 模块计算的 8 个中间量，供残差学习与报告解释使用。

所有模块一律通过这里的常量访问键名与区间，避免魔法字符串散落各处。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParamSpec:
    key: str
    label: str
    unit: str
    low: float
    high: float
    integer: bool = False
    meaning: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    unit: str
    higher_is_better: bool
    meaning: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)


PARAM_SPECS: tuple[ParamSpec, ...] = (
    ParamSpec("dryDensity", "砂土干密度", "g/cm³", 1.2, 2.2, False,
              "制样目标干密度，决定初始孔隙比与颗粒接触数", ("干密度", "砂土干密度", "rho_d", "rhod")),
    ParamSpec("fiberContent", "椰壳纤维掺量", "%", 0.0, 1.0, False,
              "纤维质量占干砂质量的百分比，存在最优掺量", ("纤维掺量", "椰壳纤维掺量", "fiber")),
    ParamSpec("bacterialVolume", "菌液用量", "mL", 10, 300, False,
              "单次灌注的巴氏芽孢杆菌菌液体积", ("菌液用量", "菌液体积", "bacteria")),
    ParamSpec("odValue", "菌液 OD600", "-", 0.2, 3.0, False,
              "菌液光密度，表征细胞浓度与脲酶活性", ("OD值", "OD600", "od")),
    ParamSpec("temperature", "固化温度", "℃", 20, 40, False,
              "养护环境温度，影响脲酶活性", ("温度", "固化温度", "temp")),
    ParamSpec("cementationDose", "胶结液浓度", "mol/L", 0.1, 3.0, False,
              "尿素-氯化钙等摩尔胶结液浓度", ("固化剂用量", "胶结液浓度", "胶结液", "dose")),
    ParamSpec("fixationVolume", "胶结液用量", "mL", 10, 300, False,
              "单次灌注胶结液体积", ("固定液用量", "胶结液用量", "fixation")),
    ParamSpec("cycles", "固化次数", "次", 1, 10, True,
              "菌液-胶结液交替灌注的总轮次", ("固化次数", "灌注次数", "n_cycles")),
)

METRIC_SPECS: tuple[MetricSpec, ...] = (
    MetricSpec("ucs", "无侧限抗压强度", "kPa", True, "固化体单轴受压峰值强度", ("UCS", "抗压强度", "无侧限抗压强度")),
    MetricSpec("postDryDensity", "固化后干密度", "g/cm³", True, "固化后试样干密度", ("固化后干密度", "rho_post")),
    MetricSpec("disintegrationRate", "浸水崩解率", "%", False, "浸水 24h 质量损失率", ("崩解率", "浸水崩解率")),
    MetricSpec("permeability", "渗透系数", "×10⁻⁴ cm/s", False, "常水头渗透试验渗透系数", ("渗透系数", "k")),
    MetricSpec("frictionAngle", "内摩擦角", "°", True, "直剪试验内摩擦角", ("内摩擦角", "phi")),
    MetricSpec("cohesion", "黏聚力", "kPa", True, "直剪试验黏聚力", ("黏聚力", "粘聚力", "c")),
    MetricSpec("caco3", "碳酸钙含量", "%", True, "酸洗法测得碳酸钙质量分数", ("碳酸钙含量", "CaCO3", "caco3Content")),
)

FEATURE_SPECS: tuple[tuple[str, str, str], ...] = (
    ("effectiveBacteria", "有效菌量指数", "mL·OD"),
    ("temperatureFactor", "脲酶温度活性因子", "-"),
    ("calciumSupply", "累计钙源供给量", "mol"),
    ("conversionEfficiency", "钙源转化效率", "-"),
    ("fiberBridging", "纤维桥接因子", "-"),
    ("initialPorosity", "初始孔隙率", "-"),
    ("poreFillingRatio", "孔隙填充率", "-"),
    ("liquidUtilization", "灌注液利用率", "-"),
)

PARAM_KEYS: list[str] = [spec.key for spec in PARAM_SPECS]
METRIC_KEYS: list[str] = [spec.key for spec in METRIC_SPECS]
FEATURE_KEYS: list[str] = [item[0] for item in FEATURE_SPECS]

PARAM_LABELS: dict[str, str] = {spec.key: spec.label for spec in PARAM_SPECS}
METRIC_LABELS: dict[str, str] = {spec.key: spec.label for spec in METRIC_SPECS}
FEATURE_LABELS: dict[str, str] = {key: label for key, label, _ in FEATURE_SPECS}

PARAM_UNITS: dict[str, str] = {spec.key: spec.unit for spec in PARAM_SPECS}
METRIC_UNITS: dict[str, str] = {spec.key: spec.unit for spec in METRIC_SPECS}

PARAM_RANGES: dict[str, tuple[float, float]] = {spec.key: (spec.low, spec.high) for spec in PARAM_SPECS}
METRIC_DIRECTION: dict[str, bool] = {spec.key: spec.higher_is_better for spec in METRIC_SPECS}

PARAM_BY_KEY: dict[str, ParamSpec] = {spec.key: spec for spec in PARAM_SPECS}
METRIC_BY_KEY: dict[str, MetricSpec] = {spec.key: spec for spec in METRIC_SPECS}


def _build_alias_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for spec in PARAM_SPECS:
        mapping[spec.key.lower()] = spec.key
        mapping[spec.label] = spec.key
        for alias in spec.aliases:
            mapping[alias.lower()] = spec.key
    for spec in METRIC_SPECS:
        mapping[spec.key.lower()] = spec.key
        mapping[spec.label] = spec.key
        for alias in spec.aliases:
            mapping[alias.lower()] = spec.key
    for alias in ("schemename", "方案名称", "方案名", "name"):
        mapping[alias] = "schemeName"
    for alias in ("sampleid", "样本编号", "编号", "id"):
        mapping[alias] = "sampleId"
    return mapping


HEADER_ALIASES: dict[str, str] = _build_alias_map()


def canonical_key(header: str) -> str | None:
    """把 CSV 表头（中英文、大小写不敏感、含空格/单位）映射为标准键名。"""
    token = header.strip()
    if not token:
        return None
    if token in HEADER_ALIASES:
        return HEADER_ALIASES[token]
    lowered = token.lower().replace(" ", "").replace("_", "")
    if lowered in HEADER_ALIASES:
        return HEADER_ALIASES[lowered]
    # 去掉括号中的单位，例如 "菌液用量(mL)"
    for sep in ("(", "（"):
        if sep in token:
            return canonical_key(token.split(sep, 1)[0])
    return None


def describe_dictionary() -> dict:
    """提供给前端 / 文档使用的完整数据字典。"""
    return {
        "params": [
            {
                "key": spec.key,
                "label": spec.label,
                "unit": spec.unit,
                "low": spec.low,
                "high": spec.high,
                "integer": spec.integer,
                "meaning": spec.meaning,
            }
            for spec in PARAM_SPECS
        ],
        "metrics": [
            {
                "key": spec.key,
                "label": spec.label,
                "unit": spec.unit,
                "higherIsBetter": spec.higher_is_better,
                "meaning": spec.meaning,
            }
            for spec in METRIC_SPECS
        ],
        "features": [
            {"key": key, "label": label, "unit": unit} for key, label, unit in FEATURE_SPECS
        ],
    }
