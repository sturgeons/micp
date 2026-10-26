"""SQLite 数据访问层。

表结构（7 张表）：
    users           用户账号（密码哈希）
    user_sessions   登录令牌
    projects        项目空间（默认公共项目 is_default=1）
    project_members 项目成员关系
    schemes         试验方案（JSON payload，按项目 + 方案名唯一）
    dataset         历史样本（JSON payload，按项目 + 样本编号唯一）
    model_store     当前生效模型（按项目 + 模型名唯一）
    model_history   模型训练历史（版本号递增，保留指标与时间）

方案与样本以 JSON 文本存储，字段结构由 ``micp.schemas`` 约束，便于后续扩展字段
而无需迁移表结构。
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEPS_DIR = ROOT.parent / ".deps"
if DEPS_DIR.exists() and str(DEPS_DIR) not in sys.path:
    sys.path.insert(0, str(DEPS_DIR))

try:
    from .micp.schemas import METRIC_KEYS, PARAM_KEYS
    from .micp.synthetic import DEFAULT_SCHEMES, generate_dataset
except ImportError:  # 以脚本方式直接运行 server.py 时
    from micp.schemas import METRIC_KEYS, PARAM_KEYS
    from micp.synthetic import DEFAULT_SCHEMES, generate_dataset

DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("MICP_DB_PATH") or (DATA_DIR / "micp.db"))

__all__ = [
    "DEFAULT_SCHEMES",
    "METRIC_KEYS",
    "PARAM_KEYS",
    "create_project",
    "create_session",
    "create_user",
    "default_dataset",
    "get_default_project_id",
    "get_project",
    "get_user_by_id",
    "get_user_by_token",
    "get_user_by_username",
    "init_db",
    "list_dataset",
    "list_model_history",
    "list_models",
    "list_models_with_metrics",
    "list_projects_for_user",
    "list_schemes",
    "load_model",
    "replace_dataset",
    "save_model",
    "seed_defaults",
    "upsert_schemes",
    "user_can_access_project",
]

_DEFAULT_DATASET_CACHE: list[dict] | None = None


def default_dataset() -> list[dict]:
    """内置示范数据集（48 条，确定性生成，首次调用后缓存）。"""
    global _DEFAULT_DATASET_CACHE
    if _DEFAULT_DATASET_CACHE is None:
        _DEFAULT_DATASET_CACHE = generate_dataset()
    return [dict(row) for row in _DEFAULT_DATASET_CACHE]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'researcher',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    owner_id INTEGER,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS project_members (
    project_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'owner',
    PRIMARY KEY (project_id, user_id),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS schemes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    scheme_name TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE(project_id, scheme_name),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS dataset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    sample_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE(project_id, sample_id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS model_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    model_name TEXT NOT NULL,
    payload TEXT NOT NULL,
    metrics TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(project_id, model_name),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS model_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    model_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    metrics TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
CREATE INDEX IF NOT EXISTS idx_model_history_project ON model_history(project_id, model_name, version);
"""


def init_db() -> None:
    migrate_legacy_schema_if_needed()
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    ensure_default_project()


def table_has_column(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except sqlite3.OperationalError:
        return False
    return any(row["name"] == column_name for row in rows)


def migrate_legacy_schema_if_needed() -> None:
    """兼容最早期无项目维度的单表结构：发现旧结构时整体重建。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        legacy = False
        if table_has_column(conn, "schemes", "scheme_name") and not table_has_column(conn, "schemes", "project_id"):
            legacy = True
        if table_has_column(conn, "dataset", "sample_id") and not table_has_column(conn, "dataset", "project_id"):
            legacy = True
        if legacy:
            conn.executescript(
                """
                DROP TABLE IF EXISTS schemes;
                DROP TABLE IF EXISTS dataset;
                DROP TABLE IF EXISTS model_store;
                DROP TABLE IF EXISTS project_members;
                DROP TABLE IF EXISTS projects;
                DROP TABLE IF EXISTS user_sessions;
                DROP TABLE IF EXISTS users;
                """
            )
            conn.commit()


# ---------------------------------------------------------------------------- 项目
def ensure_default_project() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM projects WHERE is_default = 1 LIMIT 1").fetchone()
        if row:
            project_id = row["id"]
        else:
            conn.execute(
                "INSERT INTO projects (name, description, owner_id, is_default, created_at) VALUES (?, ?, ?, ?, ?)",
                ("默认项目", "系统默认公共项目", None, 1, now_iso()),
            )
            project_id = conn.execute("SELECT id FROM projects WHERE is_default = 1 LIMIT 1").fetchone()["id"]
            conn.commit()
    if not list_schemes(project_id):
        upsert_schemes(project_id, DEFAULT_SCHEMES)
    if not list_dataset(project_id):
        replace_dataset(project_id, default_dataset())
    return project_id


def get_default_project_id() -> int:
    return ensure_default_project()


def create_project(name: str, description: str, owner_id: int) -> dict:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO projects (name, description, owner_id, is_default, created_at) VALUES (?, ?, ?, 0, ?)",
            (name, description, owner_id, now_iso()),
        )
        project_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        conn.execute(
            "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, ?)",
            (project_id, owner_id, "owner"),
        )
        conn.commit()
    return get_project(project_id)


def get_project(project_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, description, owner_id, is_default, created_at FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    return dict(row) if row else None


def list_projects_for_user(user_id: int | None = None) -> list[dict]:
    default_id = get_default_project_id()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, description, owner_id, is_default, created_at FROM projects WHERE id = ? ORDER BY id ASC",
            (default_id,),
        ).fetchall()
        projects = [dict(row) for row in rows]
        if user_id:
            user_rows = conn.execute(
                """
                SELECT p.id, p.name, p.description, p.owner_id, p.is_default, p.created_at
                FROM projects p
                JOIN project_members pm ON pm.project_id = p.id
                WHERE pm.user_id = ? AND p.id != ?
                ORDER BY p.id ASC
                """,
                (user_id, default_id),
            ).fetchall()
            projects.extend(dict(row) for row in user_rows)
    return projects


def user_can_access_project(user_id: int | None, project_id: int) -> bool:
    project = get_project(project_id)
    if not project:
        return False
    if project["is_default"]:
        return True
    if not user_id:
        return False
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------- 用户
def create_user(username: str, password_hash: str, role: str = "researcher") -> dict:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, role, now_iso()),
        )
        conn.commit()
        user_id = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]
    return get_user_by_id(user_id)


def get_user_by_username(username: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT id, username, password_hash, role, created_at FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT id, username, role, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def create_session(user_id: int) -> str:
    token = secrets.token_hex(24)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO user_sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, now_iso()),
        )
        conn.commit()
    return token


def get_user_by_token(token: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.role, u.created_at
            FROM user_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------- 方案与样本
def upsert_schemes(project_id: int, schemes: list[dict]) -> None:
    with get_connection() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO schemes (project_id, scheme_name, payload) VALUES (?, ?, ?)",
            [(project_id, item["schemeName"], json.dumps(item, ensure_ascii=False)) for item in schemes],
        )
        conn.commit()


def list_schemes(project_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT payload FROM schemes WHERE project_id = ? ORDER BY id DESC",
            (project_id,),
        ).fetchall()
    return [json.loads(row["payload"]) for row in rows]


def replace_dataset(project_id: int, rows: list[dict]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM dataset WHERE project_id = ?", (project_id,))
        conn.executemany(
            "INSERT OR REPLACE INTO dataset (project_id, sample_id, payload) VALUES (?, ?, ?)",
            [(project_id, item["sampleId"], json.dumps(item, ensure_ascii=False)) for item in rows],
        )
        conn.commit()


def list_dataset(project_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT payload FROM dataset WHERE project_id = ? ORDER BY sample_id ASC",
            (project_id,),
        ).fetchall()
    return [json.loads(row["payload"]) for row in rows]


# ---------------------------------------------------------------------------- 模型
def save_model(project_id: int, model_name: str, payload: dict, metrics: dict | None = None) -> int:
    """保存当前模型并追加一条历史记录，返回新版本号。"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS v FROM model_history WHERE project_id = ? AND model_name = ?",
            (project_id, model_name),
        ).fetchone()
        version = int(row["v"]) + 1
        payload = {**payload, "version": version}
        stamp = now_iso()
        conn.execute(
            "INSERT OR REPLACE INTO model_store (project_id, model_name, payload, metrics, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, model_name, json.dumps(payload, ensure_ascii=False), json.dumps(metrics or {}, ensure_ascii=False), stamp),
        )
        conn.execute(
            "INSERT INTO model_history (project_id, model_name, version, sample_count, metrics, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, model_name, version, int(payload.get("sampleCount", 0)), json.dumps(metrics or {}, ensure_ascii=False), stamp),
        )
        conn.commit()
    return version


def load_model(project_id: int, model_name: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT payload FROM model_store WHERE project_id = ? AND model_name = ?",
            (project_id, model_name),
        ).fetchone()
    return json.loads(row["payload"]) if row else None


def list_models(project_id: int) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT model_name FROM model_store WHERE project_id = ? ORDER BY model_name ASC",
            (project_id,),
        ).fetchall()
    return [row["model_name"] for row in rows]


def list_models_with_metrics(project_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT model_name, metrics, created_at FROM model_store WHERE project_id = ? ORDER BY model_name ASC",
            (project_id,),
        ).fetchall()
    result = []
    for row in rows:
        payload = load_model(project_id, row["model_name"]) or {}
        result.append(
            {
                "name": row["model_name"],
                "label": payload.get("label", row["model_name"]),
                "version": payload.get("version"),
                "sampleCount": payload.get("sampleCount"),
                "trainedAt": row["created_at"],
                "metrics": json.loads(row["metrics"] or "{}"),
            }
        )
    return result


def list_model_history(project_id: int, limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT model_name, version, sample_count, metrics, created_at
            FROM model_history WHERE project_id = ?
            ORDER BY created_at DESC, id DESC LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
    return [
        {
            "name": row["model_name"],
            "version": row["version"],
            "sampleCount": row["sample_count"],
            "metrics": json.loads(row["metrics"] or "{}"),
            "trainedAt": row["created_at"],
        }
        for row in rows
    ]


def seed_defaults(project_id: int | None = None) -> int:
    target = project_id or get_default_project_id()
    upsert_schemes(target, DEFAULT_SCHEMES)
    replace_dataset(target, default_dataset())
    return target
