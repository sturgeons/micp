"""向后兼容入口。

早期版本的算法实现集中在本文件；现已拆分到 ``micp`` 包。保留此模块仅为兼容
旧脚本中的 ``from backend import ml`` / ``import ml`` 写法，新代码请直接使用 ``micp``。
"""

from __future__ import annotations

try:
    from .micp import *  # noqa: F401,F403
    from .micp import __all__  # noqa: F401
except ImportError:  # 脚本方式运行
    from micp import *  # type: ignore # noqa: F401,F403
    from micp import __all__  # type: ignore # noqa: F401
