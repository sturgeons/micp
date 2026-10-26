"""Flask 接口层。

职责只有三件事：解析请求（用户 / 项目 / 参数）、调用 ``micp`` 算法包、
把结果序列化为 JSON。所有业务逻辑都不在这里实现。

接口一览（均以 /api 为前缀）：
    GET  /health                       服务与模型状态
    GET  /dictionary                   参数 / 指标 / 机理特征字典
    POST /auth/register|login          用户注册 / 登录
    GET  /auth/me                      当前用户
    GET|POST /projects                 项目列表 / 创建项目
    GET|POST /schemes                  方案列表 / 批量保存方案
    GET|POST /dataset                  样本列表 / 覆盖式保存样本
    POST /dataset/validate             校验样本或方案（JSON 行或 CSV 文本）
    POST /train                        训练全部学习器并写入模型库与历史
    POST /models/evaluate              交叉验证评估（不落库）
    GET  /models/history               模型训练历史
    POST /predict                      预测 + 机理分解 + OAT 敏感性
    POST /sensitivity/partial          偏依赖曲线
    POST /sensitivity/morris           Morris 全局敏感性
    POST /optimize                     多目标配比优化
    POST /schemes/rank                 方案综合评分排序
    POST /analyze                      统计分析（描述统计 / 异常值 / ANOVA / 回归）
    POST /statistics/correlation       相关矩阵
    POST /report                       生成 HTML 报告
    POST /seed                         载入示范数据
"""

from __future__ import annotations

import sys
import traceback
from functools import wraps
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEPS_DIR = ROOT / ".deps"
if DEPS_DIR.exists() and str(DEPS_DIR) not in sys.path:
    sys.path.insert(0, str(DEPS_DIR))

from flask import Flask, jsonify, render_template, request  # noqa: E402
from werkzeug.exceptions import HTTPException  # noqa: E402
from werkzeug.security import check_password_hash, generate_password_hash  # noqa: E402

try:
    from . import db
except ImportError:  # 直接 python backend/server.py
    import db  # type: ignore

ML_CACHE = None
ML_IMPORT_ERROR: str | None = None


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, detail=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.detail = detail


def get_ml():
    """惰性导入算法包：缺少 numpy / scikit-learn 时接口仍可启动并返回明确错误。"""
    global ML_CACHE, ML_IMPORT_ERROR
    if ML_CACHE is not None:
        return ML_CACHE
    try:
        try:
            from . import micp
        except ImportError:
            import micp  # type: ignore
        ML_CACHE = micp
        ML_IMPORT_ERROR = None
    except Exception as exc:  # pragma: no cover - 依赖缺失
        ML_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
        ML_CACHE = False
    return ML_CACHE


def require_ml():
    ml = get_ml()
    if not ml:
        raise ApiError("算法依赖未就绪", 503, ML_IMPORT_ERROR)
    return ml


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    db.init_db()

    # ------------------------------------------------------------------ 公共工具
    def body() -> dict:
        return request.get_json(force=True, silent=True) or {}

    def resolve_user():
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return db.get_user_by_token(auth.split(" ", 1)[1])
        return None

    def resolve_project_id(user=None) -> int:
        project_id = request.args.get("projectId", type=int)
        if project_id and db.user_can_access_project(user["id"] if user else None, project_id):
            return project_id
        return db.get_default_project_id()

    def context():
        user = resolve_user()
        project_id = resolve_project_id(user)
        return user, project_id

    def ensure_writable(user, project_id):
        if not db.user_can_access_project(user["id"] if user else None, project_id):
            raise ApiError("无权访问该项目", 403)

    def stored_models(project_id: int) -> dict:
        return {name: db.load_model(project_id, name) for name in db.list_models(project_id)}

    def pick_scheme(project_id: int, payload: dict) -> dict | None:
        scheme = payload.get("scheme")
        if scheme:
            return scheme
        name = payload.get("schemeName")
        schemes = db.list_schemes(project_id)
        if name:
            for item in schemes:
                if item.get("schemeName") == name:
                    return item
        return schemes[0] if schemes else None

    def auth_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = resolve_user()
            if not user:
                raise ApiError("Unauthorized", 401)
            request.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    # ------------------------------------------------------------------ 错误处理
    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return jsonify({"error": exc.message, "detail": exc.detail}), exc.status

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        return jsonify({"error": exc.name, "detail": exc.description}), exc.code

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        app.logger.error("Unhandled error: %s\n%s", exc, traceback.format_exc())
        return jsonify({"error": "服务内部错误", "detail": f"{type(exc).__name__}: {exc}"}), 500

    # ------------------------------------------------------------------ 基础
    @app.get("/api/health")
    def health():
        user, project_id = context()
        ml = get_ml()
        return jsonify(
            {
                "ok": True,
                "version": getattr(ml, "__version__", None) if ml else None,
                "projectId": project_id,
                "trainedModels": db.list_models(project_id),
                "models": db.list_models_with_metrics(project_id),
                "sampleCount": len(db.list_dataset(project_id)),
                "minTrainSamples": getattr(ml, "MIN_TRAIN_SAMPLES", None) if ml else None,
                "mlAvailable": bool(ml),
                "mlError": ML_IMPORT_ERROR,
                "user": user,
            }
        )

    @app.get("/api/dictionary")
    def dictionary():
        return jsonify(require_ml().describe_dictionary())

    # ------------------------------------------------------------------ 认证
    @app.post("/api/auth/register")
    def register():
        payload = body()
        username = (payload.get("username") or "").strip()
        password = (payload.get("password") or "").strip()
        if not username or not password:
            raise ApiError("用户名和密码不能为空")
        if len(password) < 6:
            raise ApiError("密码长度至少 6 位")
        if db.get_user_by_username(username):
            raise ApiError("用户名已存在", 409)
        user = db.create_user(username, generate_password_hash(password))
        return jsonify({"ok": True, "user": user})

    @app.post("/api/auth/login")
    def login():
        payload = body()
        username = (payload.get("username") or "").strip()
        password = (payload.get("password") or "").strip()
        user = db.get_user_by_username(username)
        if not user or not check_password_hash(user["password_hash"], password):
            raise ApiError("用户名或密码错误", 401)
        token = db.create_session(user["id"])
        return jsonify({"ok": True, "token": token, "user": {k: user[k] for k in ("id", "username", "role", "created_at")}})

    @app.get("/api/auth/me")
    @auth_required
    def me():
        return jsonify({"user": request.current_user})

    # ------------------------------------------------------------------ 项目
    @app.get("/api/projects")
    @auth_required
    def projects():
        return jsonify({"projects": db.list_projects_for_user(request.current_user["id"])})

    @app.post("/api/projects")
    @auth_required
    def create_project_endpoint():
        payload = body()
        name = (payload.get("name") or "").strip()
        if not name:
            raise ApiError("项目名称不能为空")
        project = db.create_project(name, (payload.get("description") or "").strip(), request.current_user["id"])
        return jsonify({"ok": True, "project": project})

    # ------------------------------------------------------------------ 方案与样本
    @app.get("/api/schemes")
    def schemes():
        _, project_id = context()
        return jsonify({"schemes": db.list_schemes(project_id)})

    @app.post("/api/schemes")
    def upsert_schemes_endpoint():
        user, project_id = context()
        ensure_writable(user, project_id)
        rows = body().get("schemes", [])
        validation = require_ml().validate_rows(rows, "scheme")
        if validation["rejected"]:
            raise ApiError(f"{validation['rejected']} 条方案未通过校验", 422, validation)
        db.upsert_schemes(project_id, validation["valid"])
        return jsonify({"ok": True, "schemes": db.list_schemes(project_id), "warnings": validation["warnings"]})

    @app.get("/api/dataset")
    def dataset():
        _, project_id = context()
        return jsonify({"rows": db.list_dataset(project_id)})

    @app.post("/api/dataset")
    def dataset_upsert():
        user, project_id = context()
        ensure_writable(user, project_id)
        rows = body().get("rows", [])
        validation = require_ml().validate_rows(rows, "sample")
        if validation["rejected"] and not body().get("skipInvalid"):
            raise ApiError(f"{validation['rejected']} 条样本未通过校验", 422, validation)
        db.replace_dataset(project_id, validation["valid"])
        return jsonify({"ok": True, "rows": db.list_dataset(project_id), "warnings": validation["warnings"], "rejected": validation["rejected"]})

    @app.post("/api/dataset/validate")
    def dataset_validate():
        ml = require_ml()
        payload = body()
        kind = payload.get("kind", "sample")
        unknown = []
        rows = payload.get("rows")
        if rows is None and payload.get("csv"):
            rows, unknown = ml.parse_csv(payload["csv"])
        result = ml.validate_rows(rows or [], kind)
        result["unknownHeaders"] = unknown
        return jsonify(result)

    # ------------------------------------------------------------------ 训练与评估
    @app.post("/api/train")
    def train():
        ml = require_ml()
        user, project_id = context()
        ensure_writable(user, project_id)
        rows = db.list_dataset(project_id)
        models = ml.train_models(rows)
        versions = {}
        for name, payload in models.items():
            if payload.get("blob"):
                versions[name] = db.save_model(project_id, name, payload, payload.get("metrics"))
        recommended = next((name for name, p in models.items() if p.get("metrics", {}).get("recommended")), None)
        return jsonify(
            {
                "ok": True,
                "trainedModels": list(versions.keys()),
                "versions": versions,
                "recommended": recommended,
                "sampleCount": len(rows),
                "metrics": {name: payload["metrics"] for name, payload in models.items()},
            }
        )

    @app.post("/api/models/evaluate")
    def evaluate():
        ml = require_ml()
        _, project_id = context()
        rows = db.list_dataset(project_id)
        return jsonify(ml.evaluate_models(rows))

    @app.get("/api/models/history")
    def model_history():
        _, project_id = context()
        return jsonify({"history": db.list_model_history(project_id), "current": db.list_models_with_metrics(project_id)})

    # ------------------------------------------------------------------ 预测与敏感性
    @app.post("/api/predict")
    def predict_endpoint():
        ml = require_ml()
        _, project_id = context()
        payload = body()
        scheme = pick_scheme(project_id, payload)
        if not scheme:
            raise ApiError("当前项目没有可用方案")
        result = ml.predict(
            scheme,
            payload.get("model", "ensemble"),
            db.list_dataset(project_id),
            stored_models(project_id),
            with_morris=bool(payload.get("withMorris")),
        )
        result["schemeName"] = scheme.get("schemeName")
        return jsonify(result)

    @app.post("/api/sensitivity/partial")
    def partial_dependence_endpoint():
        ml = require_ml()
        _, project_id = context()
        payload = body()
        scheme = pick_scheme(project_id, payload)
        if not scheme:
            raise ApiError("当前项目没有可用方案")
        return jsonify(
            ml.partial_dependence(scheme, payload.get("model", "ensemble"), db.list_dataset(project_id), stored_models(project_id), payload.get("param"))
        )

    @app.post("/api/sensitivity/morris")
    def morris_endpoint():
        ml = require_ml()
        _, project_id = context()
        payload = body()
        trajectories = int(payload.get("trajectories", 12))
        if not 4 <= trajectories <= 60:
            raise ApiError("轨迹数需在 4~60 之间")
        return jsonify(ml.morris(payload.get("model", "ensemble"), db.list_dataset(project_id), stored_models(project_id), trajectories))

    # ------------------------------------------------------------------ 优化与排序
    @app.post("/api/optimize")
    def optimize_endpoint():
        ml = require_ml()
        _, project_id = context()
        payload = body()
        result = ml.optimize(
            payload.get("model", "ensemble"),
            db.list_dataset(project_id),
            stored_models(project_id),
            weights=payload.get("weights"),
            fixed=payload.get("fixed"),
            bounds=payload.get("bounds"),
            restrict_to_data=payload.get("restrictToData", True),
            top_n=int(payload.get("topN", 8)),
        )
        return jsonify(result)

    @app.post("/api/schemes/rank")
    def rank_endpoint():
        ml = require_ml()
        _, project_id = context()
        payload = body()
        schemes = payload.get("schemes") or db.list_schemes(project_id)
        ranking = ml.rank_schemes(schemes, db.list_dataset(project_id), stored_models(project_id), payload.get("model", "ensemble"), payload.get("weights"))
        return jsonify({"ranking": ranking, "best": ranking[0] if ranking else None})

    # ------------------------------------------------------------------ 统计
    @app.post("/api/analyze")
    def analyze():
        ml = require_ml()
        _, project_id = context()
        payload = body()
        return jsonify(ml.analyze_dataset(db.list_dataset(project_id), payload.get("factor", "fiberContent"), payload.get("response", "ucs")))

    @app.post("/api/statistics/correlation")
    def correlation_endpoint():
        ml = require_ml()
        _, project_id = context()
        rows = db.list_dataset(project_id)
        if len(rows) < 3:
            raise ApiError("样本数不足 3 条，无法计算相关矩阵")
        return jsonify(ml.correlation(rows))

    # ------------------------------------------------------------------ 报告
    @app.post("/api/report")
    def report():
        ml = require_ml()
        _, project_id = context()
        payload = body()
        schemes = db.list_schemes(project_id)
        rows = db.list_dataset(project_id)
        stored = stored_models(project_id)
        project = db.get_project(project_id) or {}

        scheme = pick_scheme(project_id, {"schemeName": (payload.get("prediction") or {}).get("schemeName")})
        prediction = payload.get("prediction") or (ml.predict(scheme, payload.get("model", "ensemble"), rows, stored) if scheme else None)
        analysis = payload.get("analysis") or ml.analyze_dataset(rows)
        recommendation = ml.recommend_best_scheme(schemes, rows, stored)
        evaluation = payload.get("evaluation")
        if evaluation is None and payload.get("includeEvaluation", True) and len(rows) >= ml.MIN_TRAIN_SAMPLES:
            evaluation = ml.evaluate_models(rows)
        optimization = payload.get("optimization")
        if optimization is None and payload.get("includeOptimization", True):
            optimization = ml.optimize(payload.get("model", "ensemble"), rows, stored)
        html = ml.build_report_html(scheme, prediction, analysis, recommendation, evaluation, optimization, rows, project.get("name", "默认项目"))
        return jsonify({"html": html})

    @app.post("/api/seed")
    def seed():
        user, project_id = context()
        ensure_writable(user, project_id)
        db.seed_defaults(project_id)
        return jsonify({"ok": True, "schemes": db.list_schemes(project_id), "rows": db.list_dataset(project_id)})

    @app.get("/")
    def root():
        return render_template("index.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=9000, debug=False)
