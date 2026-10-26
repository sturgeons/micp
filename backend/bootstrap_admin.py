from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEPS_DIR = ROOT / ".deps"
if DEPS_DIR.exists():
    sys.path.insert(0, str(DEPS_DIR))

from werkzeug.security import generate_password_hash

try:
    from .db import create_user, get_user_by_username, init_db
except ImportError:
    from db import create_user, get_user_by_username, init_db


DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "Admin@123456"


def main() -> None:
    init_db()
    existing = get_user_by_username(DEFAULT_USERNAME)
    if existing:
      print(f"admin user already exists: {existing['username']}")
      return
    user = create_user(DEFAULT_USERNAME, generate_password_hash(DEFAULT_PASSWORD), role="admin")
    print(f"created admin user: {user['username']}")
    print(f"default password: {DEFAULT_PASSWORD}")


if __name__ == "__main__":
    main()
