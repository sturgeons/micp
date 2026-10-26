# MICP-椰壳纤维协同固化砂土性能分析与预测系统 V1.0

这是一个已经开始向正式系统升级的 MICP 软件工程版本，当前同时包含：

- 离线可运行的前端工作台
- Flask 后端 API 服务
- SQLite 数据库存储
- 可训练的真实 `scikit-learn` 集成模型 / BP(MLP) 模型
- 用户与项目管理
- 软著方向设计说明书文档

当前已实现以下模块：

- 试验参数管理：单组录入、批量 CSV 导入、模板保存、参数范围校验、参数表导出
- 固化性能预测：七项指标预测、双模型策略、参数敏感性分析、最优方案推荐
- 试验数据处理：历史样本导入、均值/标准差/变异系数、异常值剔除、单因素方差分析
- 可视化：参数-性能曲线、柱状图、箱线图、热力图
- 报告生成：自动汇总分析结果，并支持导出 `.doc` 和浏览器打印为 PDF
- 用户与项目：用户注册登录、项目创建、项目切换、项目级数据隔离

## 运行方式

### 方式一：完整系统模式

推荐直接启动后端，后端会同时托管前端页面和 API：

```bash
python3 /Users/xin/Documents/micp/backend/server.py
```

然后访问 <http://127.0.0.1:9000>。

在这个模式下可以直接使用：

- 数据库存储
- 模型训练
- 预测接口
- 统计分析接口
- 报告生成接口
- 用户与项目管理

### 方式一补充：云服务器发布

```bash
python3 -m pip install -r /Users/xin/Documents/micp/requirements.txt
python3 /Users/xin/Documents/micp/backend/bootstrap_admin.py
gunicorn -w 2 -b 0.0.0.0:9000 backend.wsgi:app
```

### 方式二：纯前端离线模式

直接双击 `index.html` 即可在浏览器中打开，或在当前目录启动任意静态文件服务。

例如：

```bash
python3 -m http.server 8080
```

然后访问 <http://localhost:8080>。

这个模式下仍可使用本地前端预测与图表功能，但不会启用后端数据库与模型训练。

## CSV 字段说明

### 批量参数导入

首行建议包含以下字段：

```text
schemeName,dryDensity,fiberContent,bacterialVolume,odValue,temperature,cementationDose,fixationVolume,cycles
```

### 历史样本导入

建议包含参数列与指标列：

```text
sampleId,dryDensity,fiberContent,bacterialVolume,odValue,temperature,cementationDose,fixationVolume,cycles,ucs,postDryDensity,disintegrationRate,permeability,frictionAngle,cohesion,caco3
```

## 说明

- 当前后端已使用 Flask 架构，便于整体打包和云端部署。
- 当前模型链路已切换为真实 `scikit-learn`，包含随机森林与 `MLPRegressor`。
- 建议首次登录后创建自己的项目，避免默认项目数据混用。
- 设计说明书位于 `/Users/xin/Documents/micp/docs/设计说明书.md`。
- 后端说明位于 `/Users/xin/Documents/micp/backend/README.md`。
- 流程图、测试用例、截图说明和材料清单位于 `/Users/xin/Documents/micp/docs/`。
- 截图文件可统一放在 `/Users/xin/Documents/micp/docs/截图资产/`。
