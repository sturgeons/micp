# MICP-椰壳纤维协同固化砂土性能分析与预测系统 V1.0

面向微生物诱导碳酸钙沉淀（MICP）与椰壳纤维协同固化砂土试验的分析预测平台。
系统以 **MICP 机理模型为先验、历史样本残差学习为修正** 的混合建模思路为核心，提供：

- 试验参数管理：单组录入、模板复用、CSV 批量导入（中英文表头自动映射）、逐行校验
- 固化性能预测：7 项指标，预测结果拆分为"机理基线 + 数据修正"，附机理解释链条
- 模型训练与评估：随机森林 / 梯度提升 / BP 三种残差学习器，自适应 K 折交叉验证，模型版本历史
- 参数敏感性：OAT 弹性系数、Morris 全局筛选、偏依赖曲线
- 多目标配比优化：拉丁超立方采样 + 局部细化，可调权重，UCS-成本 Pareto 前沿
- 试验数据处理：IQR + Grubbs 异常值检测、描述统计、单因素方差分析（含 p 值）、UCS-CaCO₃ 回归
- 相关性分析：参数-指标 Pearson 相关矩阵及显著性
- 可视化：趋势散点、分组柱状、箱线图、热力图
- 报告生成：含 SVG 图表的 HTML 报告，可导出 `.doc` 或打印 PDF
- 用户与项目：注册登录、项目空间、项目级数据隔离

## 目录结构

```text
backend/
  server.py          Flask 接口层（22 个 REST 端点）
  db.py              SQLite 数据访问层（8 张表）
  ml.py              向后兼容入口（转发到 micp 包）
  wsgi.py            Gunicorn 入口
  bootstrap_admin.py 初始化管理员账号
  micp/              算法包
    schemas.py       参数 / 指标 / 机理特征字典
    mechanism.py     MICP 机理特征工程与机理基线预测
    models.py        机理 + 残差混合模型、序列化
    evaluation.py    自适应 K 折交叉验证
    sensitivity.py   OAT 弹性、Morris、偏依赖
    optimizer.py     多目标配比优化
    statistics.py    异常值、ANOVA、相关、回归
    validators.py    行级校验与 CSV 解析
    synthetic.py     内置示范数据集（48 条）
    report.py        含 SVG 图表的 HTML 报告
  templates/index.html  前端页面
  static/app.js         前端逻辑（含机理模型 JS 版，用于离线回退）
  static/styles.css
docs/                软著申报材料（设计说明书、用户手册、测试报告、截图等）
scripts/             材料生成脚本（Word 汇编、登记表、验收测试）
```

## 运行

```bash
# 安装依赖（Python 3.10+）
python3 -m pip install -r requirements.txt

# 本地启动
python3 backend/server.py
# 访问 http://127.0.0.1:9000

# 生产部署
python3 backend/bootstrap_admin.py          # 创建 admin / Admin@123456
gunicorn -w 2 -b 0.0.0.0:9000 backend.wsgi:app
```

首次启动会自动建库，并在默认项目中写入 4 个示范方案与 48 条示范样本。
点击页面上的"训练并交叉验证"即可完成模型训练；未训练时预测自动使用纯机理模型。

当浏览器无法连接后端时，前端会切换到"离线机理模式"：参数管理、机理预测、
OAT 敏感性、偏依赖曲线与图表仍可用，但不包含残差学习、交叉验证与配比优化。

## CSV 字段

批量参数导入（表头可用英文键名或中文名称，如 `干密度`、`纤维掺量`、`胶结液浓度`）：

```text
schemeName,dryDensity,fiberContent,bacterialVolume,odValue,temperature,cementationDose,fixationVolume,cycles
```

历史样本导入：

```text
sampleId,dryDensity,fiberContent,bacterialVolume,odValue,temperature,cementationDose,fixationVolume,cycles,ucs,postDryDensity,disintegrationRate,permeability,frictionAngle,cohesion,caco3
```

参数单位与合理区间见 `docs/设计说明书.md` 第 4 章数据字典，或访问 `GET /api/dictionary`。

## 验收与材料生成

```bash
python3 scripts/run_acceptance.py          # 全链路接口验收，生成 docs/测试报告.md
python3 scripts/build_word_docs.py         # 生成 docs/word/ 下的材料汇编与源程序鉴别材料
python3 scripts/build_registration_form.py # 生成软著信息登记表
```
