# 后端说明

## 启动

```bash
python3 backend/server.py            # 开发模式，监听 http://127.0.0.1:9000
gunicorn -w 2 -b 0.0.0.0:9000 backend.wsgi:app   # 生产模式
```

页面模板位于 `backend/templates/index.html`，静态资源位于 `backend/static/`，
数据库文件默认为 `backend/data/micp.db`（可通过环境变量 `MICP_DB_PATH` 覆盖）。

首次启动会自动建表，并在默认项目中写入 4 个示范方案与 48 条示范样本（由
`micp/synthetic.py` 按机理模型生成）。

## 初始化管理员

```bash
python3 backend/bootstrap_admin.py   # admin / Admin@123456
```

## 代码结构

| 模块 | 职责 |
| --- | --- |
| `server.py` | Flask 接口层，统一错误 JSON、项目上下文解析、22 个 REST 端点 |
| `db.py` | SQLite 数据访问层：users / projects / schemes / templates / dataset / models / model_history / reports |
| `micp/schemas.py` | 8 项参数、7 项指标、8 项机理特征的字典（键名、中文名、单位、合理区间、中英文表头别名） |
| `micp/mechanism.py` | 机理特征工程（有效菌量、温度因子、钙源、逐轮转化效率、孔隙填充、纤维桥接）与 7 项指标的机理基线 |
| `micp/models.py` | 机理基线 + 残差学习混合模型（随机森林 / 梯度提升 / BP），物理可行域裁剪，模型序列化 |
| `micp/evaluation.py` | 自适应 K 折交叉验证，逐指标 R² / RMSE / MAE / MAPE，与纯机理基线对照，过拟合差距 |
| `micp/sensitivity.py` | OAT 弹性系数、Morris 基本效应 (μ*, σ)、偏依赖曲线 |
| `micp/optimizer.py` | 拉丁超立方采样 + 高斯局部细化，多目标加权评分，成本指数，Pareto 前沿，样本包络约束 |
| `micp/statistics.py` | IQR + Grubbs 异常值、描述统计、单因素 ANOVA（F、p、η²）、Pearson 相关矩阵、UCS-CaCO₃ 回归 |
| `micp/validators.py` | 方案 / 样本逐行校验（类型、区间、物理一致性）与 CSV 解析（中英文表头映射） |
| `micp/synthetic.py` | 示范数据集与示范方案 |
| `micp/report.py` | 纯 Python 生成 SVG 图表与 HTML 报告 |
| `ml.py` | 兼容旧导入路径，转发到 `micp` 包 |

## API 一览

除 `/api/health`、`/api/dictionary`、`/api/auth/*` 外，所有端点均接受可选的
`projectId`（query 或 body）以及 `Authorization: Bearer <token>`，用于项目隔离。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 服务状态、已训练模型、样本数、最小训练样本数、版本 |
| GET | `/api/dictionary` | 参数 / 指标 / 机理特征字典 |
| POST | `/api/auth/register` `/api/auth/login` | 注册 / 登录，返回 token |
| GET | `/api/auth/me` | 当前用户 |
| GET / POST | `/api/projects` | 项目列表 / 创建项目 |
| GET / POST | `/api/schemes` | 方案列表 / 保存方案（经校验，422 返回 `detail`） |
| GET / POST | `/api/dataset` | 样本列表 / 覆盖写入样本（`skipInvalid` 跳过不合格行） |
| POST | `/api/dataset/validate` | 仅校验：传 `rows` 或 `csv`，返回逐行错误与警告 |
| POST | `/api/train` | 训练并保存三种残差模型，返回交叉验证指标与推荐模型 |
| POST | `/api/models/evaluate` | 仅交叉验证不落库 |
| GET | `/api/models/history` | 模型版本历史 |
| POST | `/api/predict` | 预测：`scheme` 或 `schemeName`、`model`、`withMorris` |
| POST | `/api/sensitivity/partial` | 偏依赖曲线 |
| POST | `/api/sensitivity/morris` | Morris 全局敏感性（`trajectories` 4~60） |
| POST | `/api/optimize` | 多目标配比优化（`weights`、`fixed`、`restrictToData`、`topN`） |
| POST | `/api/schemes/rank` | 多方案综合评分排序 |
| POST | `/api/analyze` | 异常值 / 描述统计 / ANOVA / 回归（`factor`、`response`） |
| POST | `/api/statistics/correlation` | 参数-指标相关矩阵 |
| POST | `/api/report` | 生成 HTML 报告（可带 `prediction` / `analysis` / `evaluation` / `optimization`） |
| POST | `/api/seed` | 恢复示范方案与样本 |

错误统一返回 `{ "error": "...", "detail": ... }`，状态码 400 / 401 / 404 / 422 / 500。
