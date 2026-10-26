"""分析报告生成（HTML + 内嵌 SVG 图表，不依赖 matplotlib）。

报告章节：
1. 试验方案参数表
2. 机理解释链条
3. 性能预测结果（机理基线 / 数据修正 / 最终值）与柱状对比图
4. 参数敏感性（OAT 排序条形图）
5. 模型评估（交叉验证指标表）
6. 数据统计（描述统计、异常值、方差分析、UCS-CaCO₃ 回归散点图）
7. 配比优化与方案推荐（Top-N 表、Pareto 前沿图）
8. 结论与建议
"""

from __future__ import annotations

import html
from datetime import datetime

from .schemas import METRIC_KEYS, METRIC_LABELS, METRIC_UNITS, PARAM_KEYS, PARAM_LABELS, PARAM_UNITS

PALETTE = ["#0f6a52", "#d97706", "#2563eb", "#9333ea", "#dc2626", "#0891b2", "#65a30d", "#475569"]


def esc(value) -> str:
    return html.escape(str(value))


def fmt(value, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


# ---------------------------------------------------------------------------- SVG 组件
def svg_bar_chart(items: list[tuple[str, float]], title: str, width: int = 640, color: str = PALETTE[0], unit: str = "") -> str:
    if not items:
        return ""
    row_h, left, top = 26, 150, 36
    height = top + row_h * len(items) + 24
    max_v = max(abs(v) for _, v in items) or 1.0
    bars = []
    for i, (label, value) in enumerate(items):
        y = top + i * row_h
        w = abs(value) / max_v * (width - left - 90)
        bars.append(
            f'<text x="{left - 8}" y="{y + 17}" text-anchor="end" font-size="12" fill="#334155">{esc(label)}</text>'
            f'<rect x="{left}" y="{y + 4}" width="{w:.1f}" height="{row_h - 8}" rx="3" fill="{color}" opacity="0.85"/>'
            f'<text x="{left + w + 6:.1f}" y="{y + 17}" font-size="11" fill="#0f172a">{fmt(value, 3)}{esc(unit)}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="font-family:sans-serif">'
        f'<text x="{width / 2}" y="20" text-anchor="middle" font-size="14" font-weight="bold" fill="#0f172a">{esc(title)}</text>'
        + "".join(bars)
        + "</svg>"
    )


def svg_scatter(points: list[tuple[float, float]], title: str, x_label: str, y_label: str, line: tuple[float, float] | None = None, highlight: list[tuple[float, float]] | None = None, width: int = 640, height: int = 360) -> str:
    if not points:
        return ""
    left, right, top, bottom = 64, 24, 36, 48
    xs = [p[0] for p in points] + [p[0] for p in (highlight or [])]
    ys = [p[1] for p in points] + [p[1] for p in (highlight or [])]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if x1 - x0 < 1e-9:
        x1 = x0 + 1
    if y1 - y0 < 1e-9:
        y1 = y0 + 1
    pad_x, pad_y = (x1 - x0) * 0.06, (y1 - y0) * 0.08
    x0, x1, y0, y1 = x0 - pad_x, x1 + pad_x, y0 - pad_y, y1 + pad_y

    def sx(v):
        return left + (v - x0) / (x1 - x0) * (width - left - right)

    def sy(v):
        return height - bottom - (v - y0) / (y1 - y0) * (height - top - bottom)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="font-family:sans-serif">',
        f'<text x="{width / 2}" y="20" text-anchor="middle" font-size="14" font-weight="bold" fill="#0f172a">{esc(title)}</text>',
        f'<line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="#94a3b8"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" stroke="#94a3b8"/>',
        f'<text x="{width / 2}" y="{height - 12}" text-anchor="middle" font-size="12" fill="#475569">{esc(x_label)}</text>',
        f'<text x="16" y="{height / 2}" text-anchor="middle" font-size="12" fill="#475569" transform="rotate(-90 16 {height / 2})">{esc(y_label)}</text>',
    ]
    for i in range(5):
        gx = x0 + (x1 - x0) * i / 4
        gy = y0 + (y1 - y0) * i / 4
        parts.append(f'<text x="{sx(gx):.1f}" y="{height - bottom + 16}" text-anchor="middle" font-size="10" fill="#64748b">{fmt(gx, 1)}</text>')
        parts.append(f'<text x="{left - 6}" y="{sy(gy) + 4:.1f}" text-anchor="end" font-size="10" fill="#64748b">{fmt(gy, 1)}</text>')
        parts.append(f'<line x1="{left}" y1="{sy(gy):.1f}" x2="{width - right}" y2="{sy(gy):.1f}" stroke="#e2e8f0"/>')
    for x, y in points:
        parts.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4" fill="{PALETTE[2]}" opacity="0.7"/>')
    if line:
        slope, intercept = line
        parts.append(
            f'<line x1="{sx(x0):.1f}" y1="{sy(slope * x0 + intercept):.1f}" x2="{sx(x1):.1f}" y2="{sy(slope * x1 + intercept):.1f}" stroke="{PALETTE[4]}" stroke-width="2" stroke-dasharray="6 4"/>'
        )
    if highlight:
        path = " ".join(f"{'M' if i == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for i, (x, y) in enumerate(highlight))
        parts.append(f'<path d="{path}" fill="none" stroke="{PALETTE[1]}" stroke-width="2"/>')
        for x, y in highlight:
            parts.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="5" fill="{PALETTE[1]}"/>')
    parts.append("</svg>")
    return "".join(parts)


def svg_grouped_bars(labels: list[str], series: dict[str, list[float]], title: str, width: int = 680, height: int = 320) -> str:
    """多序列柱状图（每个指标独立归一化到自身最大值，用于量纲不同的指标对比）。"""
    if not labels or not series:
        return ""
    left, right, top, bottom = 40, 20, 40, 70
    n, m = len(labels), len(series)
    group_w = (width - left - right) / n
    bar_w = group_w / (m + 1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="font-family:sans-serif">',
        f'<text x="{width / 2}" y="20" text-anchor="middle" font-size="14" font-weight="bold" fill="#0f172a">{esc(title)}</text>',
        f'<line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="#94a3b8"/>',
    ]
    for j, label in enumerate(labels):
        col_max = max(abs(values[j]) for values in series.values()) or 1.0
        for s_idx, (name, values) in enumerate(series.items()):
            h = abs(values[j]) / col_max * (height - top - bottom)
            x = left + j * group_w + bar_w * (s_idx + 0.5)
            y = height - bottom - h
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{PALETTE[s_idx % len(PALETTE)]}" opacity="0.85"/>')
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 3:.1f}" text-anchor="middle" font-size="9" fill="#0f172a">{fmt(values[j], 1)}</text>')
        parts.append(f'<text x="{left + j * group_w + group_w / 2:.1f}" y="{height - bottom + 16}" text-anchor="middle" font-size="10" fill="#334155">{esc(label)}</text>')
    for s_idx, name in enumerate(series):
        lx = left + s_idx * 150
        parts.append(f'<rect x="{lx}" y="{height - 26}" width="12" height="12" fill="{PALETTE[s_idx % len(PALETTE)]}"/>')
        parts.append(f'<text x="{lx + 16}" y="{height - 16}" font-size="11" fill="#334155">{esc(name)}</text>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------- HTML 组件
def table(headers: list[str], rows: list[list], caption: str | None = None) -> str:
    thead = "".join(f"<th>{esc(h)}</th>" for h in headers)
    tbody = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows)
    cap = f"<caption>{esc(caption)}</caption>" if caption else ""
    return f"<table>{cap}<thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>"


def build_report_html(
    scheme: dict | None,
    prediction: dict | None,
    analysis: dict | None,
    recommendation: dict | None,
    evaluation: dict | None = None,
    optimization: dict | None = None,
    dataset: list[dict] | None = None,
    project_name: str = "默认项目",
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    sections: list[str] = []

    # 1. 参数表
    if scheme:
        rows = [[PARAM_LABELS[k], scheme.get(k, "-"), PARAM_UNITS[k]] for k in PARAM_KEYS]
        sections.append(f"<h2>1. 试验方案参数</h2><p>方案名称：<strong>{esc(scheme.get('schemeName', '-'))}</strong></p>" + table(["参数", "取值", "单位"], rows))
    else:
        sections.append("<h2>1. 试验方案参数</h2><p>暂无方案。</p>")

    # 2. 机理解释
    if prediction and prediction.get("mechanism"):
        items = "".join(f"<li><strong>{esc(n['title'])}：</strong>{esc(n['text'])}</li>" for n in prediction["mechanism"])
        sections.append(f"<h2>2. 机理解释</h2><ol>{items}</ol>")

    # 3. 预测结果
    if prediction and prediction.get("metrics"):
        decomposition = prediction.get("decomposition") or {}
        base = decomposition.get("baseline", {})
        corr = decomposition.get("correction", {})
        rows = [
            [METRIC_LABELS[k], fmt(base.get(k)), fmt(corr.get(k), 3), fmt(prediction["metrics"].get(k)), METRIC_UNITS[k]]
            for k in METRIC_KEYS
        ]
        model_label = prediction.get("modelLabel") or prediction.get("model", "-")
        chart = ""
        if dataset:
            means = {k: sum(float(r[k]) for r in dataset) / len(dataset) for k in METRIC_KEYS}
            chart = svg_grouped_bars(
                [METRIC_LABELS[k] for k in METRIC_KEYS],
                {"预测值": [prediction["metrics"][k] for k in METRIC_KEYS], "历史样本均值": [means[k] for k in METRIC_KEYS]},
                "预测值与历史样本均值对比（各指标按自身最大值归一化）",
            )
        sections.append(
            f"<h2>3. 固化性能预测</h2><p>所用模型：{esc(model_label)}"
            + (f"；样本数 {prediction.get('sampleCount')}" if prediction.get("sampleCount") else "")
            + ("；<em>当前为机理模型回退结果</em>" if prediction.get("fallback") else "")
            + "</p>"
            + table(["指标", "机理基线", "数据修正", "最终预测", "单位"], rows)
            + chart
        )

    # 4. 敏感性
    if prediction and prediction.get("sensitivity"):
        items = [(s["label"], s["score"] * 100) for s in prediction["sensitivity"]]
        sections.append("<h2>4. 参数敏感性</h2><p>方法：" + esc(prediction.get("sensitivityMethod", "OAT 弹性系数")) + "</p>" + svg_bar_chart(items, "参数综合重要度（%）", unit="%"))
        morris = prediction.get("morris")
        if morris and morris.get("overall"):
            rows = [[m["label"], fmt(m["muStar"], 3), fmt(m["sigma"], 3)] for m in morris["overall"]]
            sections.append(table(["参数", "μ*（平均绝对效应）", "σ（非线性/交互）"], rows, morris.get("method")))

    # 5. 模型评估
    if evaluation and evaluation.get("reports"):
        rows = []
        for name, rep in evaluation["reports"].items():
            val = rep.get("validation")
            tr = rep.get("train")
            rows.append([
                rep.get("learner", name),
                rep.get("folds", "-"),
                fmt(val["overall"]["r2"], 3) if val else "-",
                fmt(val["overall"]["rmse"], 3) if val else "-",
                fmt(val["overall"]["mape"], 1) + "%" if val else "-",
                fmt(tr["overall"]["r2"], 3) if tr else "-",
                fmt(rep["baseline"]["overall"]["r2"], 3),
            ])
        sections.append(
            f"<h2>5. 模型评估</h2><p>推荐模型：<strong>{esc(evaluation.get('recommended', '-'))}</strong>（按交叉验证 R² 选择）。</p>"
            + table(["学习器", "折数", "验证 R²", "验证 RMSE", "验证 MAPE", "训练 R²", "机理基线 R²"], rows)
        )
        rec = evaluation["reports"].get(evaluation.get("recommended"))
        if rec and rec.get("validation"):
            rows = [[r["label"], fmt(r["r2"], 3), fmt(r["rmse"], 3), fmt(r["mae"], 3), fmt(r["mape"], 1) + "%"] for r in rec["validation"]["perMetric"]]
            sections.append(table(["指标", "R²", "RMSE", "MAE", "MAPE"], rows, "推荐模型逐指标验证误差"))

    # 6. 数据统计
    if analysis:
        rows = [[s["label"], s.get("count", "-"), fmt(s.get("mean")), fmt(s.get("std")), fmt(s.get("cv"), 3), fmt(s.get("min")), fmt(s.get("max"))] for s in analysis.get("metricStats", [])]
        block = f"<h2>6. 试验数据统计</h2><p>原始样本 {analysis.get('rawSampleSize', analysis.get('sampleSize'))} 条，剔除异常值 {analysis.get('removed', 0)} 条，有效样本 {analysis.get('sampleSize')} 条。</p>"
        block += table(["指标", "n", "均值", "标准差", "变异系数", "最小值", "最大值"], rows)
        if analysis.get("removedDetails"):
            block += table(["样本", "指标", "数值", "方法", "原因"], [[d["sampleId"], d["metric"], fmt(d["value"]), d["method"], d["reason"]] for d in analysis["removedDetails"]], "异常值剔除明细")
        anova = analysis.get("anova") or {}
        if anova.get("groups"):
            block += f"<h3>单因素方差分析</h3><p>{esc(anova.get('conclusion', ''))} F={fmt(anova.get('fValue'), 3)}，df=({anova.get('dfBetween')}, {anova.get('dfWithin')})，p={fmt(anova.get('pValue'), 4)}，η²={fmt(anova.get('eta2'), 3)}。</p>"
            block += table(["水平", "n", "均值", "标准差"], [[g["level"], g["count"], fmt(g["mean"]), fmt(g["std"])] for g in anova["groups"]])
        reg = analysis.get("regression")
        if reg and reg.get("linear") and dataset:
            pts = [(float(r["caco3"]), float(r["ucs"])) for r in dataset]
            block += f"<h3>UCS-碳酸钙含量关系</h3><p>线性：{esc(reg['linear']['equation'])}（R²={fmt(reg['linear']['r2'], 3)}）"
            if reg.get("power"):
                block += f"；幂函数：{esc(reg['power']['equation'])}（R²={fmt(reg['power']['r2'], 3)}）"
            block += "</p>" + svg_scatter(pts, "UCS 与碳酸钙含量散点及线性拟合", "碳酸钙含量 (%)", "UCS (kPa)", line=(reg["linear"]["slope"], reg["linear"]["intercept"]))
        sections.append(block)

    # 7. 优化与推荐
    block = "<h2>7. 配比优化与方案推荐</h2>"
    if recommendation:
        block += f"<p>在当前项目的方案中，综合评分最高的是 <strong>{esc(recommendation.get('schemeName') or recommendation.get('scheme', {}).get('schemeName', '-'))}</strong>（得分 {fmt(recommendation.get('score'), 3)}，预测 UCS {fmt(recommendation.get('metrics', {}).get('ucs'), 1)} kPa，相对成本 {fmt(recommendation.get('cost'), 1)}）。</p>"
    if optimization and optimization.get("topSchemes"):
        rows = []
        for item in optimization["topSchemes"][:5]:
            p = item["params"]
            rows.append([item["rank"], p["dryDensity"], p["fiberContent"], p["bacterialVolume"], p["odValue"], p["temperature"], p["cementationDose"], p["fixationVolume"], p["cycles"], fmt(item["metrics"]["ucs"], 0), fmt(item["cost"], 1), fmt(item["score"], 3)])
        block += f"<p>{esc(optimization.get('method', ''))}，共评估 {optimization.get('evaluated')} 组候选配比。</p>"
        block += table(["序", "干密度", "纤维%", "菌液mL", "OD", "温度", "浓度", "胶结液mL", "次数", "UCS", "成本", "得分"], rows, "优化配比 Top 5")
        if optimization.get("pareto"):
            front = [(p["cost"], p["ucs"]) for p in optimization["pareto"]]
            cloud = [(p["cost"], p["ucs"]) for p in optimization.get("scatter", [])]
            block += svg_scatter(cloud, "UCS-成本 Pareto 前沿", "相对成本指数", "UCS (kPa)", highlight=front)
    if not recommendation and not optimization:
        block += "<p>尚未执行方案评分与配比优化。</p>"
    sections.append(block)

    # 8. 结论
    conclusions = []
    if prediction and prediction.get("sensitivity"):
        top = prediction["sensitivity"][:3]
        conclusions.append("当前方案下，对固化性能影响最大的参数依次为：" + "、".join(s["label"] for s in top) + "。")
    if analysis and analysis.get("anova", {}).get("conclusion"):
        conclusions.append(analysis["anova"]["conclusion"])
    if evaluation and evaluation.get("recommended"):
        rep = evaluation["reports"].get(evaluation["recommended"], {})
        if rep.get("validation"):
            conclusions.append(f"推荐模型 {evaluation['recommended']} 的交叉验证平均 R² 为 {fmt(rep['validation']['overall']['r2'], 3)}，{esc(rep.get('note', ''))}")
    if optimization and optimization.get("topSchemes"):
        best = optimization["topSchemes"][0]["params"]
        conclusions.append(f"建议优先验证的配比：干密度 {best['dryDensity']} g/cm³、纤维掺量 {best['fiberContent']}%、菌液 {best['bacterialVolume']} mL（OD {best['odValue']}）、胶结液 {best['cementationDose']} mol/L × {best['fixationVolume']} mL、固化 {best['cycles']} 次。")
    if not conclusions:
        conclusions.append("请先执行预测、统计分析与配比优化以生成结论。")
    sections.append("<h2>8. 结论与建议</h2><ul>" + "".join(f"<li>{c}</li>" for c in conclusions) + "</ul>")

    body = "".join(sections)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<title>MICP-椰壳纤维协同固化砂土性能分析报告</title>
<style>
  body {{ font-family: 'Songti SC', 'SimSun', serif; padding: 36px 48px; color: #1f2f29; line-height: 1.75; max-width: 900px; margin: 0 auto; }}
  h1 {{ color: #0f6a52; font-size: 24px; border-bottom: 2px solid #0f6a52; padding-bottom: 8px; }}
  h2 {{ color: #0f6a52; font-size: 18px; margin-top: 28px; }}
  h3 {{ color: #1f4d78; font-size: 15px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 10px 0 16px; font-size: 12.5px; }}
  caption {{ caption-side: top; text-align: left; font-weight: bold; color: #334155; padding: 4px 0; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 5px 8px; text-align: center; }}
  th {{ background: #f1f5f9; }}
  svg {{ display: block; margin: 8px auto 16px; max-width: 100%; }}
  .meta {{ color: #64748b; font-size: 12px; }}
</style>
</head>
<body>
<h1>MICP-椰壳纤维协同固化砂土性能分析报告</h1>
<p class="meta">项目：{esc(project_name)} ｜ 生成时间：{now} ｜ 系统版本：V1.0</p>
{body}
</body>
</html>"""
