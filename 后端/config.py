"""
Backend configuration.

Values are read from environment variables so local credentials do not need
to be committed to the repository.
"""
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
ROOT_ENV_FILE = ROOT_DIR / ".env"
BACKEND_ENV_FILE = Path(__file__).resolve().parent / ".env"

load_dotenv(ROOT_ENV_FILE, encoding="utf-8-sig")
# 也尝试从后端目录加载 .env（便携版分发时 .env 在后端/下）
if not os.getenv("IFLYTEK_SPARK_API_PASSWORD"):
    if BACKEND_ENV_FILE.exists():
        load_dotenv(BACKEND_ENV_FILE, encoding="utf-8-sig")

# FFMPEG 路径：优先环境变量，否则自动查找 runtime/ 目录
_FFMPEG_DEFAULT = os.getenv("FFMPEG_PATH", "")
if not _FFMPEG_DEFAULT:
    _LOCAL_FFMPEG = Path(__file__).resolve().parents[1] / "runtime" / "ffmpeg.exe"
    if _LOCAL_FFMPEG.exists():
        os.environ["FFMPEG_PATH"] = str(_LOCAL_FFMPEG)
    else:
        os.environ.setdefault("FFMPEG_PATH", "ffmpeg")


IFLYTEK_APP_ID = os.getenv("IFLYTEK_APP_ID", "")
IFLYTEK_API_KEY = os.getenv("IFLYTEK_API_KEY", "")
IFLYTEK_API_SECRET = os.getenv("IFLYTEK_API_SECRET", "")
IFLYTEK_SPARK_API_PASSWORD = os.getenv("IFLYTEK_SPARK_API_PASSWORD", "")
IFLYTEK_SPARK_HTTP_TIMEOUT = int(os.getenv("IFLYTEK_SPARK_HTTP_TIMEOUT", "15"))
WEB_AI_TIMEOUT = int(os.getenv("WEB_AI_TIMEOUT", "3"))
OCR_HTTP_TIMEOUT = int(os.getenv("OCR_HTTP_TIMEOUT", "15"))
XFYUN_APPID = os.getenv("XFYUN_APPID", IFLYTEK_APP_ID)
XFYUN_API_SECRET = os.getenv("XFYUN_API_SECRET", IFLYTEK_API_SECRET)
XFYUN_API_KEY = os.getenv("XFYUN_API_KEY", IFLYTEK_API_KEY)

OCR_URL = os.getenv("OCR_URL", "https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm")
SPARK_URL = os.getenv("SPARK_URL", "https://spark-api-open.xf-yun.com/v1/chat/completions")
IAT_URL = os.getenv("IAT_URL", "wss://iat-api.xfyun.cn/v2/iat")
SMART_TTS_URL = os.getenv("SMART_TTS_URL", "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6")


def missing_required_settings(*names):
    """Return required setting names whose values are blank."""
    return [name for name in names if not globals().get(name)]


def has_env_file():
    """Return True when a runtime .env file is available."""
    return ROOT_ENV_FILE.exists() or BACKEND_ENV_FILE.exists()


def ffmpeg_is_available():
    """Return True when the configured ffmpeg binary can be resolved."""
    ffmpeg_path = os.getenv("FFMPEG_PATH", "").strip()
    if not ffmpeg_path:
        return False
    if Path(ffmpeg_path).is_file():
        return True
    return shutil.which(ffmpeg_path) is not None
