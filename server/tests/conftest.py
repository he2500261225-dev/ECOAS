"""测试使用独立的临时 SQLite，避免污染演示数据库，也避免被运行中的服务锁住。"""

import os
import tempfile
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="ecoa-test-")
os.environ["ECOA_DB_PATH"] = str(Path(_TMP_DIR) / "ecoa_test.db")
