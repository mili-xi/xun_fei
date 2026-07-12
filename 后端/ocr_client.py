"""
iFlytek general document OCR client.

The project uses the newer OCR large-model WebAPI endpoint shown in the
open-platform console, such as:
https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm
"""
import bootstrap
import base64
import hashlib
import hmac
import json
from datetime import datetime
from time import mktime
from urllib.parse import urlencode, urlparse
from wsgiref.handlers import format_date_time

import requests

from backend_errors import UpstreamServiceError
from config import IFLYTEK_APP_ID, IFLYTEK_API_KEY, IFLYTEK_API_SECRET, OCR_URL, OCR_HTTP_TIMEOUT


class IFlyTekOCRClient:
    def __init__(self, app_id=None, api_key=None, api_secret=None, url=None, timeout=None):
        self.app_id = app_id or IFLYTEK_APP_ID
        self.api_key = api_key or IFLYTEK_API_KEY
        self.api_secret = api_secret or IFLYTEK_API_SECRET
        self.url = url or OCR_URL
        self.timeout = timeout if timeout is not None else OCR_HTTP_TIMEOUT

    def recognize(self, image_path):
        """
        Recognize text from an image using iFlytek OCR large-model WebAPI.
        """
        self._require_credentials()
        image_base64 = self._read_image_base64(image_path)
        payload = self._build_payload(image_base64, self._image_encoding(image_path))
        response = requests.post(
            self._authenticated_url(),
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
            verify=True,
        )
        if response.status_code != 200:
            raise UpstreamServiceError(
                "ocr",
                "OCR service request failed",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise UpstreamServiceError("ocr", "OCR service returned invalid JSON") from exc

    def extract_text(self, image_path):
        """
        Extract plain text from OCR response.
        """
        result = self.recognize(image_path)
        self._raise_for_error(result)
        text = self._extract_new_model_text(result)
        if text:
            return text
        text = self._extract_legacy_text(result)
        if text:
            return text
        raise RuntimeError("OCR returned no recognizable text")

    def _require_credentials(self):
        missing = []
        if not self.app_id:
            missing.append("IFLYTEK_APP_ID")
        if not self.api_key:
            missing.append("IFLYTEK_API_KEY")
        if not self.api_secret:
            missing.append("IFLYTEK_API_SECRET")
        if missing:
            raise RuntimeError("Missing OCR credentials: " + ", ".join(missing))

    @staticmethod
    def _read_image_base64(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    @staticmethod
    def _image_encoding(image_path):
        suffix = str(image_path).rsplit(".", 1)[-1].lower() if "." in str(image_path) else "jpg"
        if suffix == "jpeg":
            return "jpg"
        if suffix in {"jpg", "png", "bmp", "webp"}:
            return suffix
        return "jpg"

    def _build_payload(self, image_base64, encoding="jpg"):
        return {
            "header": {"app_id": self.app_id, "status": 0},
            "parameter": {
                "ocr": {
                    "result": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "json",
                    }
                }
            },
            "payload": {
                "image": {
                    "encoding": encoding,
                    "image": image_base64,
                    "status": 0,
                }
            },
        }

    def _authenticated_url(self):
        parsed = urlparse(self.url)
        host = parsed.netloc
        path = parsed.path or "/"
        date = format_date_time(mktime(datetime.now().timetuple()))
        signature_origin = f"host: {host}\ndate: {date}\nPOST {path} HTTP/1.1"
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode("utf-8"),
                signature_origin.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        authorization_origin = (
            f'api_key="{self.api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
        return self.url + "?" + urlencode({"authorization": authorization, "date": date, "host": host})

    @staticmethod
    def _raise_for_error(result):
        header = result.get("header") if isinstance(result, dict) else None
        if isinstance(header, dict):
            code = header.get("code", 0)
            if code not in (0, "0"):
                message = header.get("message") or header.get("sid") or result
                raise UpstreamServiceError("ocr", f"OCR service returned error code {code}")
            return
        if result.get("code") not in (None, "0", 0):
            raise UpstreamServiceError("ocr", f"OCR service returned error code {result.get('code')}")

    @staticmethod
    def _extract_new_model_text(result):
        payload = result.get("payload", {})
        result_payload = payload.get("result") or payload.get("text") or {}
        encoded_text = result_payload.get("text") or result_payload.get("json") or ""
        if not encoded_text:
            return ""
        decoded = base64.b64decode(encoded_text).decode("utf-8", errors="replace")
        try:
            data = json.loads(decoded)
        except json.JSONDecodeError:
            return decoded.strip()
        return extract_text_from_nested_json(data)

    @staticmethod
    def _extract_legacy_text(result):
        data = result.get("data", {})
        document = data.get("document", {})
        blocks = document.get("blocks", [])
        lines_text = []
        for block in blocks:
            for line in block.get("lines", []):
                text = line.get("text", "")
                if text.strip():
                    lines_text.append(text.strip())
        return "\n".join(lines_text)


def extract_text_from_nested_json(value):
    texts = []

    def walk(node):
        if isinstance(node, dict):
            text = node.get("text") or node.get("content")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return "\n".join(dict.fromkeys(texts))
