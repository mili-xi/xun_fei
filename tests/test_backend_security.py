import importlib
import os
import ssl
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "后端"
TEST_SECRET = "unit-test-secret-sentinel"


class BackendSecurityTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(BACKEND_DIR))
        for name in ("app", "backend_errors", "config", "llm_client", "ocr_client", "voice_chat_flow"):
            sys.modules.pop(name, None)

    def tearDown(self):
        try:
            sys.path.remove(str(BACKEND_DIR))
        except ValueError:
            pass
        os.environ.pop("XUNFEI_LAUNCH_TOKEN", None)

    def test_llm_upstream_error_redacts_response_body_and_enforces_tls(self):
        backend_errors = importlib.import_module("backend_errors")
        llm_client = importlib.import_module("llm_client")
        response = Mock(status_code=401, text=f"opaque {TEST_SECRET}")
        response.json.side_effect = ValueError("not json")

        with patch.object(llm_client.requests, "post", return_value=response) as post:
            with self.assertRaises(backend_errors.UpstreamServiceError) as caught:
                llm_client.SparkLLMClient(api_password="test-password").chat(
                    [{"role": "user", "content": "ping"}]
                )

        self.assertNotIn(TEST_SECRET, str(caught.exception))
        self.assertEqual(caught.exception.status_code, 401)
        self.assertIs(post.call_args.kwargs["verify"], True)

    def test_ocr_upstream_error_redacts_response_body_and_enforces_tls(self):
        backend_errors = importlib.import_module("backend_errors")
        ocr_client = importlib.import_module("ocr_client")
        response = Mock(status_code=502, text=f"provider failed {TEST_SECRET}")
        response.json.side_effect = ValueError("not json")

        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.png"
            image_path.write_bytes(b"not-a-real-image")
            client = ocr_client.IFlyTekOCRClient(
                app_id="app-id",
                api_key="api-key",
                api_secret="api-secret",
            )
            with patch.object(ocr_client.requests, "post", return_value=response) as post:
                with self.assertRaises(backend_errors.UpstreamServiceError) as caught:
                    client.recognize(image_path)

        self.assertNotIn(TEST_SECRET, str(caught.exception))
        self.assertEqual(caught.exception.status_code, 502)
        self.assertIs(post.call_args.kwargs["verify"], True)

    def test_voice_websocket_requires_certificate_validation(self):
        voice_chat_flow = importlib.import_module("voice_chat_flow")

        class FakeWebSocketApp:
            def __init__(self, url, **callbacks):
                self.url = url
                self.callbacks = callbacks
                self.run_forever_kwargs = None

            def send(self, _payload):
                pass

            def close(self):
                close_callback = self.callbacks.get("on_close")
                if close_callback:
                    close_callback(self, None, None)

            def run_forever(self, **kwargs):
                self.run_forever_kwargs = kwargs
                close_callback = self.callbacks.get("on_close")
                if close_callback:
                    close_callback(self, None, None)

        created = []

        def make_fake_ws(url, **callbacks):
            fake = FakeWebSocketApp(url, **callbacks)
            created.append(fake)
            return fake

        with tempfile.NamedTemporaryFile(suffix=".pcm") as audio:
            audio.write(b"\x00\x01")
            audio.flush()
            with patch.object(voice_chat_flow, "get_xfyun_credentials", return_value=("appid", "secret", "key")):
                with patch.object(voice_chat_flow.websocket, "WebSocketApp", side_effect=make_fake_ws):
                    voice_chat_flow.recognize_pcm(audio.name)

        fake_ws = created[0]
        self.assertEqual(fake_ws.run_forever_kwargs["sslopt"]["cert_reqs"], ssl.CERT_REQUIRED)
        self.assertIs(fake_ws.run_forever_kwargs["sslopt"]["check_hostname"], True)

    def test_health_requires_launch_token_when_configured(self):
        os.environ["XUNFEI_LAUNCH_TOKEN"] = "expected-token"
        app_module = importlib.import_module("app")
        client = app_module.create_app({"TESTING": True}).test_client()

        missing = client.get("/api/health")
        invalid = client.get("/api/health", headers={"X-Xunfei-Launch-Token": "wrong"})
        valid = client.get("/api/health", headers={"X-Xunfei-Launch-Token": "expected-token"})

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(valid.status_code, 200)
        self.assertNotIn("env_file_present", valid.get_json()["data"])


if __name__ == "__main__":
    unittest.main()
