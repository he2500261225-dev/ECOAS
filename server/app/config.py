import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ASSET_DIR = DATA_DIR / "assets"
DATA_DIR.mkdir(parents=True, exist_ok=True)
ASSET_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.getenv("ECOA_DB_PATH", str(DATA_DIR / "ecoa.db")))
JWT_SECRET = os.getenv("ECOA_JWT_SECRET", "ecoa-demo-jwt-secret-please-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("ECOA_JWT_EXPIRE_MINUTES", "480"))

# 演示中新建任务的默认参数，可在系统配置中覆盖
DEFAULT_TASK_IMAGE_TIMEOUT = 300
DEFAULT_TASK_VIDEO_TIMEOUT = 600
DEFAULT_TASK_MAX_RETRY = 2
DEFAULT_QUEUE_CONCURRENCY = 2
DEFAULT_MEDIA_DELAY = "3-6"
DEFAULT_MEDIA_FAIL_RATE = 0.15
DEFAULT_HIGH_RISK_BUDGET = 5000
