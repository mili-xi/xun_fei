"""Backend runtime configuration.

Configuration comes from the process environment or an explicit mapping passed
to load_settings(). Repository .env files are intentionally not loaded.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

from backend_errors import ConfigurationError, MissingConfigurationError


DEFAULT_OCR_URL = "https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm"
DEFAULT_SPARK_URL = "https://spark-api-open.xf-yun.com/v1/chat/completions"
DEFAULT_SPARK_WS_URL = "wss://spark-api.xf-yun.com/v3.1/chat"
DEFAULT_IAT_URL = "wss://iat-api.xfyun.cn/v2/iat"
DEFAULT_SMART_TTS_URL = "wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6"


@dataclass(frozen=True)
class Settings:
    iflytek_app_id: str
    iflytek_api_key: str
    iflytek_api_secret: str
    iflytek_spark_api_password: str
    xfyun_app_id: str
    xfyun_api_key: str
    xfyun_api_secret: str
    ocr_url: str
    spark_url: str
    spark_ws_url: str
    iat_url: str
    smart_tts_url: str
    iflytek_spark_model: str
    iflytek_spark_http_timeout: int
    web_ai_timeout: int
    ocr_http_timeout: int
    port: int
    ffmpeg_path: str

    @property
    def spark_configured(self) -> bool:
        return bool(self.iflytek_spark_api_password)

    @property
    def ocr_configured(self) -> bool:
        return bool(self.iflytek_app_id and self.iflytek_api_key and self.iflytek_api_secret)

    @property
    def voice_configured(self) -> bool:
        return bool(self.xfyun_app_id and self.xfyun_api_key and self.xfyun_api_secret)

    def missing(self, *names: str) -> list[str]:
        return [name for name in names if not getattr(self, _setting_attr(name), "")]

    def require(self, *names: str) -> None:
        missing = self.missing(*names)
        if missing:
            raise MissingConfigurationError("Missing configuration: " + ", ".join(missing))


def _setting_attr(name: str) -> str:
    mapping = {
        "IFLYTEK_APP_ID": "iflytek_app_id",
        "IFLYTEK_API_KEY": "iflytek_api_key",
        "IFLYTEK_API_SECRET": "iflytek_api_secret",
        "IFLYTEK_SPARK_API_PASSWORD": "iflytek_spark_api_password",
        "XFYUN_APPID": "xfyun_app_id",
        "XFYUN_API_KEY": "xfyun_api_key",
        "XFYUN_API_SECRET": "xfyun_api_secret",
    }
    return mapping.get(name, name.lower())


def _clean(mapping: Mapping[str, object], name: str, default: object = "") -> str:
    value = mapping.get(name, default)
    return "" if value is None else str(value).strip()


def _positive_int(
    mapping: Mapping[str, object],
    name: str,
    default: int,
    minimum: int = 1,
    maximum: int = 300,
) -> int:
    raw = _clean(mapping, name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


def _secure_url(
    mapping: Mapping[str, object],
    name: str,
    default: str,
    allowed_schemes: set[str],
) -> str:
    value = _clean(mapping, name, default)
    parsed = urlparse(value)
    if parsed.scheme not in allowed_schemes or not parsed.netloc:
        allowed = "/".join(sorted(allowed_schemes))
        raise ConfigurationError(f"{name} must be a secure {allowed} URL")
    return value


def _default_ffmpeg_path(mapping: Mapping[str, object]) -> str:
    configured = _clean(mapping, "FFMPEG_PATH")
    if configured:
        return configured
    local_ffmpeg = Path(__file__).resolve().parents[1] / "runtime" / "ffmpeg.exe"
    if local_ffmpeg.exists():
        return str(local_ffmpeg)
    return "ffmpeg"


def load_settings(environ: Mapping[str, object] | None = None) -> Settings:
    mapping = dict(os.environ if environ is None else environ)
    iflytek_app_id = _clean(mapping, "IFLYTEK_APP_ID")
    iflytek_api_key = _clean(mapping, "IFLYTEK_API_KEY")
    iflytek_api_secret = _clean(mapping, "IFLYTEK_API_SECRET")

    return Settings(
        iflytek_app_id=iflytek_app_id,
        iflytek_api_key=iflytek_api_key,
        iflytek_api_secret=iflytek_api_secret,
        iflytek_spark_api_password=_clean(mapping, "IFLYTEK_SPARK_API_PASSWORD"),
        xfyun_app_id=_clean(mapping, "XFYUN_APPID", iflytek_app_id),
        xfyun_api_key=_clean(mapping, "XFYUN_API_KEY", iflytek_api_key),
        xfyun_api_secret=_clean(mapping, "XFYUN_API_SECRET", iflytek_api_secret),
        ocr_url=_secure_url(mapping, "OCR_URL", DEFAULT_OCR_URL, {"https"}),
        spark_url=_secure_url(mapping, "SPARK_URL", DEFAULT_SPARK_URL, {"https"}),
        spark_ws_url=_secure_url(mapping, "SPARK_WS_URL", DEFAULT_SPARK_WS_URL, {"wss"}),
        iat_url=_secure_url(mapping, "IAT_URL", DEFAULT_IAT_URL, {"wss"}),
        smart_tts_url=_secure_url(mapping, "SMART_TTS_URL", DEFAULT_SMART_TTS_URL, {"wss"}),
        iflytek_spark_model=_clean(mapping, "IFLYTEK_SPARK_MODEL", "lite"),
        iflytek_spark_http_timeout=_positive_int(mapping, "IFLYTEK_SPARK_HTTP_TIMEOUT", 15),
        web_ai_timeout=_positive_int(mapping, "WEB_AI_TIMEOUT", 3),
        ocr_http_timeout=_positive_int(mapping, "OCR_HTTP_TIMEOUT", 15),
        port=_positive_int(mapping, "PORT", 5000, maximum=65535),
        ffmpeg_path=_default_ffmpeg_path(mapping),
    )


SETTINGS = load_settings()

IFLYTEK_APP_ID = SETTINGS.iflytek_app_id
IFLYTEK_API_KEY = SETTINGS.iflytek_api_key
IFLYTEK_API_SECRET = SETTINGS.iflytek_api_secret
IFLYTEK_SPARK_API_PASSWORD = SETTINGS.iflytek_spark_api_password
IFLYTEK_SPARK_HTTP_TIMEOUT = SETTINGS.iflytek_spark_http_timeout
WEB_AI_TIMEOUT = SETTINGS.web_ai_timeout
OCR_HTTP_TIMEOUT = SETTINGS.ocr_http_timeout
XFYUN_APPID = SETTINGS.xfyun_app_id
XFYUN_API_SECRET = SETTINGS.xfyun_api_secret
XFYUN_API_KEY = SETTINGS.xfyun_api_key
OCR_URL = SETTINGS.ocr_url
SPARK_URL = SETTINGS.spark_url
SPARK_WS_URL = SETTINGS.spark_ws_url
IAT_URL = SETTINGS.iat_url
SMART_TTS_URL = SETTINGS.smart_tts_url


def missing_required_settings(*names: str) -> list[str]:
    """Return required setting names whose values are blank."""
    return [name for name in names if not globals().get(name)]


def has_env_file() -> bool:
    """Runtime .env files are intentionally ignored."""
    return False


def ffmpeg_is_available() -> bool:
    """Return True when the configured ffmpeg binary can be resolved."""
    ffmpeg_path = SETTINGS.ffmpeg_path.strip()
    if not ffmpeg_path:
        return False
    if Path(ffmpeg_path).is_file():
        return True
    return shutil.which(ffmpeg_path) is not None
