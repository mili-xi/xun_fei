import base64
import importlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "后端"


class BackendConfigImportTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(BACKEND_DIR))
        for name in ("bootstrap", "config", "ocr_client", "llm_client"):
            sys.modules.pop(name, None)

    def tearDown(self):
        try:
            sys.path.remove(str(BACKEND_DIR))
        except ValueError:
            pass

    def test_config_exposes_backend_client_settings(self):
        config = importlib.import_module("config")

        expected_names = [
            "IFLYTEK_APP_ID",
            "IFLYTEK_API_KEY",
            "IFLYTEK_SPARK_API_PASSWORD",
            "OCR_URL",
            "SPARK_URL",
        ]

        for name in expected_names:
            self.assertTrue(hasattr(config, name), name)
            self.assertIsInstance(getattr(config, name), str)

    def test_clients_import_with_missing_environment_values(self):
        for name in [
            "IFLYTEK_APP_ID",
            "IFLYTEK_API_KEY",
            "IFLYTEK_SPARK_API_PASSWORD",
            "OCR_URL",
            "SPARK_URL",
        ]:
            os.environ.pop(name, None)

        ocr_client = importlib.import_module("ocr_client")
        llm_client = importlib.import_module("llm_client")

        self.assertTrue(hasattr(ocr_client, "IFlyTekOCRClient"))
        self.assertTrue(hasattr(llm_client, "SparkLLMClient"))

    def test_spark_client_accepts_openai_compatible_chat_response(self):
        llm_client = importlib.import_module("llm_client")
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "{\"questions\": []}",
                    }
                }
            ]
        }

        with patch.object(llm_client.requests, "post", return_value=response):
            result = llm_client.SparkLLMClient(api_password="token").chat(
                [{"role": "user", "content": "生成题目"}]
            )

        self.assertEqual(result, "{\"questions\": []}")

    def test_spark_client_uses_configured_http_timeout(self):
        os.environ["IFLYTEK_SPARK_HTTP_TIMEOUT"] = "7"
        sys.modules.pop("config", None)
        sys.modules.pop("llm_client", None)
        try:
            llm_client = importlib.import_module("llm_client")
            response = Mock()
            response.status_code = 200
            response.json.return_value = {
                "choices": [{"message": {"content": "ok"}}],
            }

            with patch.object(llm_client.requests, "post", return_value=response) as post:
                result = llm_client.SparkLLMClient(api_password="token").chat(
                    [{"role": "user", "content": "ping"}]
                )

            self.assertEqual(result, "ok")
            self.assertEqual(post.call_args.kwargs["timeout"], 7)
        finally:
            os.environ.pop("IFLYTEK_SPARK_HTTP_TIMEOUT", None)
            sys.modules.pop("config", None)
            sys.modules.pop("llm_client", None)

    def test_settings_ignore_repository_env_files(self):
        env_file = ROOT / ".env"
        original = env_file.read_text(encoding="utf-8") if env_file.exists() else None
        env_file.write_text("IFLYTEK_APP_ID=from-env-file\n", encoding="utf-8")
        sys.modules.pop("config", None)

        try:
            config = importlib.import_module("config")
            settings = config.load_settings({"IFLYTEK_APP_ID": "from-mapping"})

            self.assertEqual(settings.iflytek_app_id, "from-mapping")
            self.assertEqual(config.load_settings({}).iflytek_app_id, "")
        finally:
            sys.modules.pop("config", None)
            if original is None:
                env_file.unlink(missing_ok=True)
            else:
                env_file.write_text(original, encoding="utf-8")

    def test_settings_reject_insecure_service_urls(self):
        config = importlib.import_module("config")

        with self.assertRaisesRegex(config.ConfigurationError, "OCR_URL"):
            config.load_settings({"OCR_URL": "http://insecure.invalid"})

    def test_settings_aliases_prefer_xfyun_values(self):
        config = importlib.import_module("config")

        settings = config.load_settings({
            "IFLYTEK_APP_ID": "canonical",
            "IFLYTEK_API_KEY": "canonical-key",
            "IFLYTEK_API_SECRET": "canonical-secret",
            "XFYUN_APPID": "voice-alias",
            "XFYUN_API_KEY": "voice-key",
            "XFYUN_API_SECRET": "voice-secret",
        })

        self.assertEqual(settings.xfyun_app_id, "voice-alias")
        self.assertEqual(settings.xfyun_api_key, "voice-key")
        self.assertEqual(settings.xfyun_api_secret, "voice-secret")

    def test_config_reports_bundled_ffmpeg_when_present(self):
        sys.modules.pop("config", None)
        config = importlib.import_module("config")

        self.assertTrue(config.ffmpeg_is_available())

    def test_spark_client_can_override_timeout_per_instance(self):
        llm_client = importlib.import_module("llm_client")
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

        with patch.object(llm_client.requests, "post", return_value=response) as post:
            result = llm_client.SparkLLMClient(api_password="token", timeout=3).chat(
                [{"role": "user", "content": "ping"}]
            )

        self.assertEqual(result, "ok")
        self.assertEqual(post.call_args.kwargs["timeout"], 3)


    def test_ocr_client_uses_document_model_endpoint_and_hmac_auth(self):
        ocr_client = importlib.import_module("ocr_client")
        image_path = ROOT / "tests" / "sample_resume.png"
        image_path.write_bytes(b"fake image bytes")
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "header": {"code": 0},
            "payload": {
                "result": {
                    "text": "eyJwYWdlcyI6IFt7ImxpbmVzIjogW3sidGV4dCI6ICJIZWxsbyBPQ1IifV19XX0="
                }
            },
        }

        try:
            with patch.object(ocr_client.requests, "post", return_value=response) as post:
                result = ocr_client.IFlyTekOCRClient(
                    app_id="appid",
                    api_key="api-key",
                    api_secret="api-secret",
                    url="https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm",
                ).recognize(image_path)
        finally:
            image_path.unlink(missing_ok=True)

        self.assertEqual(result["header"]["code"], 0)
        called_url = post.call_args.args[0]
        self.assertIn("/v1/private/se75ocrbm", called_url)
        self.assertIn("authorization=", called_url)
        self.assertIn("date=", called_url)
        self.assertIn("host=", called_url)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["header"]["app_id"], "appid")
        self.assertEqual(payload["header"]["status"], 0)
        self.assertEqual(
            payload["parameter"]["ocr"]["result"],
            {
                "encoding": "utf8",
                "compress": "raw",
                "format": "json",
            },
        )
        self.assertEqual(payload["payload"]["image"]["status"], 0)
        self.assertIn("payload", payload)

    def test_ocr_client_extracts_text_from_document_model_response(self):
        ocr_client = importlib.import_module("ocr_client")
        image_path = ROOT / "tests" / "sample_resume.png"
        image_path.write_bytes(b"fake image bytes")
        response = Mock()
        response.status_code = 200
        encoded_result = base64.b64encode(
            json.dumps(
                {
                    "pages": [
                        {
                            "lines": [
                                {"text": "\u5927\u5b66\u6821\u56ed\u4e8c\u624b\u4ea4\u6613\u5e73\u53f0"},
                                {"text": "Spring Boot"},
                            ]
                        }
                    ]
                },
                ensure_ascii=False,
            ).encode("utf-8")
        ).decode("utf-8")
        response.json.return_value = {
            "header": {"code": 0},
            "payload": {"result": {"text": encoded_result}},
        }

        try:
            with patch.object(ocr_client.requests, "post", return_value=response):
                text = ocr_client.IFlyTekOCRClient(
                    app_id="appid",
                    api_key="api-key",
                    api_secret="api-secret",
                ).extract_text(image_path)
        finally:
            image_path.unlink(missing_ok=True)

        self.assertIn("\u5927\u5b66\u6821\u56ed\u4e8c\u624b\u4ea4\u6613\u5e73\u53f0", text)
        self.assertIn("Spring Boot", text)

    def test_ocr_client_uses_png_encoding_for_png_files(self):
        ocr_client = importlib.import_module("ocr_client")
        image_path = ROOT / "tests" / "sample_resume.png"
        image_path.write_bytes(b"fake image bytes")
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"header": {"code": 0}, "payload": {"result": {"text": ""}}}

        try:
            with patch.object(ocr_client.requests, "post", return_value=response) as post:
                ocr_client.IFlyTekOCRClient(app_id="appid", api_key="api-key", api_secret="api-secret").recognize(image_path)
        except RuntimeError:
            pass
        finally:
            image_path.unlink(missing_ok=True)

        self.assertEqual(post.call_args.kwargs["json"]["payload"]["image"]["encoding"], "png")

    def test_voice_chat_credentials_prefer_environment_values(self):
        os.environ["XFYUN_APPID"] = "env-appid"
        os.environ["XFYUN_API_SECRET"] = "env-secret"
        os.environ["XFYUN_API_KEY"] = "env-key"
        try:
            sys.modules.pop("voice_chat_flow", None)
            voice_chat_flow = importlib.import_module("voice_chat_flow")
            appid, api_secret, api_key = voice_chat_flow.get_xfyun_credentials()

            self.assertEqual(appid, "env-appid")
            self.assertEqual(api_secret, "env-secret")
            self.assertEqual(api_key, "env-key")
        finally:
            os.environ.pop("XFYUN_APPID", None)
            os.environ.pop("XFYUN_API_SECRET", None)
            os.environ.pop("XFYUN_API_KEY", None)

    def test_voice_chat_module_imports_without_credentials_until_runtime_use(self):
        os.environ.pop("XFYUN_APPID", None)
        os.environ.pop("XFYUN_API_SECRET", None)
        os.environ.pop("XFYUN_API_KEY", None)
        os.environ.pop("IFLYTEK_APP_ID", None)
        os.environ.pop("IFLYTEK_API_SECRET", None)
        os.environ.pop("IFLYTEK_API_KEY", None)
        try:
            sys.modules.pop("config", None)
            sys.modules.pop("voice_chat_flow", None)
            config = importlib.import_module("config")
            config.XFYUN_APPID = ""
            config.XFYUN_API_SECRET = ""
            config.XFYUN_API_KEY = ""
            config.IFLYTEK_APP_ID = ""
            config.IFLYTEK_API_SECRET = ""
            config.IFLYTEK_API_KEY = ""

            voice_chat_flow = importlib.import_module("voice_chat_flow")

            self.assertTrue(hasattr(voice_chat_flow, "recognize_pcm"))
            with self.assertRaisesRegex(RuntimeError, "未找到讯飞密钥"):
                voice_chat_flow.get_xfyun_credentials()
        finally:
            sys.modules.pop("voice_chat_flow", None)
            sys.modules.pop("config", None)


if __name__ == "__main__":
    unittest.main()
