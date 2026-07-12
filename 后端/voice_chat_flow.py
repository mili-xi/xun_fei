
import argparse
import base64
import hashlib
import hmac
import json
import logging
import os
import ssl
import subprocess
import threading
import time

from datetime import datetime
from pathlib import Path
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

import websocket

import config


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_AUDIO = PROJECT_DIR / "demo.pcm"
DEFAULT_REPORT = PROJECT_DIR / "chat_report.md"

IAT_URL = config.IAT_URL
SPARK_URL = "wss://spark-api.xf-yun.com/v3.1/chat"
SPARK_DOMAIN = "generalv3"
SMART_TTS_URL = config.SMART_TTS_URL

STATUS_FIRST_FRAME = 0
STATUS_CONTINUE_FRAME = 1
STATUS_LAST_FRAME = 2
WS_TIMEOUT_SECONDS = 20
LOGGER = logging.getLogger(__name__)


SECURE_WEBSOCKET_OPTIONS = {
    "cert_reqs": ssl.CERT_REQUIRED,
    "check_hostname": True,
}


def load_xfyun_credentials():
    appid = config.XFYUN_APPID or config.IFLYTEK_APP_ID
    api_secret = config.XFYUN_API_SECRET or config.IFLYTEK_API_SECRET
    api_key = config.XFYUN_API_KEY or config.IFLYTEK_API_KEY
    if appid and api_secret and api_key:
        return appid, api_secret, api_key

    LOGGER.error("Missing XFYUN credentials for voice pipeline")
    raise RuntimeError(
        "未找到讯飞密钥。请设置 XFYUN_APPID、XFYUN_API_SECRET、XFYUN_API_KEY。"
    )


def get_xfyun_credentials():
    return load_xfyun_credentials()


def rfc1123_now():
    now = datetime.now()
    return format_date_time(mktime(now.timetuple()))


def assemble_ws_auth_url(request_url, method="GET", api_key="", api_secret=""):
    schema_sep = request_url.index("://")
    host_and_path = request_url[schema_sep + 3:]
    path_start = host_and_path.index("/")
    host = host_and_path[:path_start]
    path = host_and_path[path_start:]

    date = rfc1123_now()
    signature_origin = f"host: {host}\ndate: {date}\n{method} {path} HTTP/1.1"
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    return request_url + "?" + urlencode({"host": host, "date": date, "authorization": authorization})


def create_iat_url():
    _, api_secret, api_key = get_xfyun_credentials()
    return assemble_ws_auth_url(IAT_URL, "GET", api_key, api_secret)


def _wait_for_ws_completion(done_event, timeout_seconds, label):
    if done_event.wait(timeout=timeout_seconds):
        return
    raise RuntimeError(f"{label} websocket timeout after {timeout_seconds}s")


def recognize_pcm(audio_file):
    audio_path = Path(audio_file)
    temp_audio_path = None
    appid, _, _ = get_xfyun_credentials()
    LOGGER.info("Starting IAT recognition source=%s suffix=%s", audio_path.name, audio_path.suffix.lower())
    # 如果是mp3，自动转临时pcm
    if audio_path.suffix.lower() == ".mp3":
        tmp_pcm = PROJECT_DIR / "_tmp_convert.pcm"
        ffmpeg_exe = os.getenv("FFMPEG_PATH", "ffmpeg")
        cmd = [
            ffmpeg_exe, "-y", "-i", str(audio_path),
            "-f", "s16le", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(tmp_pcm)
        ]
        LOGGER.info("Converting MP3 to PCM source=%s target=%s", audio_path.name, tmp_pcm.name)
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            LOGGER.error("MP3 to PCM conversion failed source=%s", audio_path.name)
            raise RuntimeError(f"ffmpeg 转换失败: {result.stderr.decode('utf-8', errors='replace')}")
        audio_path = tmp_pcm
        temp_audio_path = tmp_pcm
        LOGGER.info("Converted MP3 to PCM target=%s", audio_path.name)

    try:
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        if audio_path.stat().st_size == 0:
            raise RuntimeError(f"音频文件为空 (0 字节): {audio_path}")

        result_parts = []
        done = threading.Event()
        errors = []

        common_args = {"app_id": appid}
        business_args = {
            "domain": "iat",
            "language": "zh_cn",
            "accent": "mandarin",
            "vinfo": 1,
            "vad_eos": 10000,
        }

        def on_message(ws, message):
            try:
                msg = json.loads(message)
                code = msg.get("code")
                sid = msg.get("sid", "")
                if code != 0:
                    errors.append(f"IAT error sid={sid}: {msg.get('message')} code={code}")
                    ws.close()
                    return

                data = msg.get("data", {}).get("result", {}).get("ws", [])
                for item in data:
                    for candidate in item.get("cw", []):
                        result_parts.append(candidate.get("w", ""))
            except Exception as exc:
                errors.append(f"IAT parse error: {exc}")
                ws.close()

        def on_error(ws, error):
            if isinstance(error, websocket.ABNF):
                return
            errors.append(f"IAT websocket error: {error}")
            done.set()

        def on_close(ws, *args):
            done.set()

        def on_open(ws):
            def send_audio():
                try:
                    frame_size = 3200
                    interval = 0.04
                    status = STATUS_FIRST_FRAME

                    with audio_path.open("rb") as fp:
                        while True:
                            buf = fp.read(frame_size)
                            if not buf:
                                if status == STATUS_FIRST_FRAME:
                                    payload = {
                                        "common": common_args,
                                        "business": business_args,
                                        "data": {
                                            "status": 0,
                                            "format": "audio/L16;rate=16000",
                                            "audio": base64.b64encode(buf).decode("utf-8"),
                                            "encoding": "raw",
                                        },
                                    }
                                    ws.send(json.dumps(payload))
                                payload = {
                                    "data": {
                                        "status": 2,
                                        "format": "audio/L16;rate=16000",
                                        "audio": "",
                                        "encoding": "raw",
                                    },
                                }
                                ws.send(json.dumps(payload))
                                break

                            if status == STATUS_FIRST_FRAME:
                                payload = {
                                    "common": common_args,
                                    "business": business_args,
                                    "data": {
                                        "status": 0,
                                        "format": "audio/L16;rate=16000",
                                        "audio": base64.b64encode(buf).decode("utf-8"),
                                        "encoding": "raw",
                                    },
                                }
                                ws.send(json.dumps(payload))
                                status = STATUS_CONTINUE_FRAME
                            elif status == STATUS_CONTINUE_FRAME:
                                payload = {
                                    "data": {
                                        "status": 1,
                                        "format": "audio/L16;rate=16000",
                                        "audio": base64.b64encode(buf).decode("utf-8"),
                                        "encoding": "raw",
                                    }
                                }
                                ws.send(json.dumps(payload))
                            time.sleep(interval)
                except Exception as exc:
                    errors.append(f"IAT send error: {exc}")
                    done.set()
                    ws.close()

            send_audio()

        ws = websocket.WebSocketApp(
            create_iat_url(),
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open,
        )
        ws.run_forever(sslopt=SECURE_WEBSOCKET_OPTIONS)
        _wait_for_ws_completion(done, WS_TIMEOUT_SECONDS, "IAT")

        if errors:
            LOGGER.error("IAT recognition failed source=%s errors=%s", audio_path.name, len(errors))
            raise RuntimeError("; ".join(errors))
        result_text = "".join(result_parts).strip()
        LOGGER.info("IAT recognition completed source=%s chars=%s", audio_path.name, len(result_text))
        return result_text
    finally:
        if temp_audio_path is not None:
            temp_audio_path.unlink(missing_ok=True)


def synthesize_mp3(text, output_file):
    appid, api_secret, api_key = get_xfyun_credentials()
    output_path = Path(output_file)
    LOGGER.info("Starting TTS synthesis output=%s text_chars=%s", output_path.name, len(text))
    if output_path.exists():
        output_path.unlink()

    done = threading.Event()
    errors = []

    header = {"app_id": appid, "status": 2}
    parameter = {
        "tts": {
            "vcn": "x6_lingfeiyi_pro",
            "volume": 50,
            "rhy": 0,
            "speed": 50,
            "pitch": 50,
            "bgs": 0,
            "reg": 0,
            "rdn": 0,
            "audio": {
                "encoding": "lame",
                "sample_rate": 24000,
                "channels": 1,
                "bit_depth": 16,
                "frame_size": 0,
            },
        }
    }
    payload = {
        "text": {
            "encoding": "utf8",
            "compress": "raw",
            "format": "plain",
            "status": 2,
            "seq": 0,
            "text": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
        }
    }

    def on_message(ws, message):
        try:
            msg = json.loads(message)
            header_msg = msg.get("header", {})
            code = header_msg.get("code", 0)
            sid = header_msg.get("sid", "")
            if code != 0:
                errors.append(f"TTS error sid={sid}: {msg} code={code}")
                ws.close()
                return

            audio_payload = msg.get("payload", {}).get("audio")
            if not audio_payload:
                return

            audio = base64.b64decode(audio_payload["audio"])
            with output_path.open("ab") as fp:
                fp.write(audio)

            if audio_payload.get("status") == 2:
                ws.close()
        except Exception as exc:
            errors.append(f"TTS parse error: {exc}")
            ws.close()

    def on_error(ws, error):
        if isinstance(error, websocket.ABNF):
            return
        errors.append(f"TTS websocket error: {error}")
        done.set()

    def on_close(ws, *args):
        done.set()

    def on_open(ws):
        ws.send(json.dumps({"header": header, "parameter": parameter, "payload": payload}))

    ws_url = assemble_ws_auth_url(SMART_TTS_URL, "GET", api_key, api_secret)
    ws = websocket.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
    )
    ws.run_forever(sslopt=SECURE_WEBSOCKET_OPTIONS)
    _wait_for_ws_completion(done, WS_TIMEOUT_SECONDS, "TTS")

    if errors:
        LOGGER.error("TTS synthesis failed output=%s errors=%s", output_path.name, len(errors))
        raise RuntimeError("; ".join(errors))
    if not output_path.exists() or output_path.stat().st_size == 0:
        LOGGER.error("TTS synthesis produced empty output=%s", output_path.name)
        raise RuntimeError(f"TTS 没有生成有效音频: {output_path}")
    LOGGER.info("TTS synthesis completed output=%s bytes=%s", output_path.name, output_path.stat().st_size)
    return output_path


def spark_chat(messages, temperature=0.5, max_tokens=1024):
    appid, api_secret, api_key = get_xfyun_credentials()
    done = threading.Event()
    errors = []
    answer_parts = []
    LOGGER.info(
        "Starting Spark chat message_count=%s temperature=%s max_tokens=%s",
        len(messages),
        temperature,
        max_tokens,
    )

    payload = {
        "header": {"app_id": appid, "uid": "voice_chat_cli"},
        "parameter": {
            "chat": {
                "domain": SPARK_DOMAIN,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        },
        "payload": {
            "message": {
                "text": messages,
            }
        },
    }

    def on_message(ws, message):
        try:
            msg = json.loads(message)
            header = msg.get("header", {})
            code = header.get("code", 0)
            if code != 0:
                errors.append(f"Spark error sid={header.get('sid', '')}: {header.get('message')} code={code}")
                ws.close()
                return

            choices = msg.get("payload", {}).get("choices", {})
            for item in choices.get("text", []):
                answer_parts.append(item.get("content", ""))

            if header.get("status") == 2 or choices.get("status") == 2:
                ws.close()
        except Exception as exc:
            errors.append(f"Spark parse error: {exc}")
            ws.close()

    def on_error(ws, error):
        errors.append(f"Spark websocket error: {error}")
        done.set()

    def on_close(ws, *args):
        done.set()

    def on_open(ws):
        ws.send(json.dumps(payload, ensure_ascii=False))

    ws_url = assemble_ws_auth_url(SPARK_URL, "GET", api_key, api_secret)
    ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.on_open = on_open
    ws.run_forever(sslopt=SECURE_WEBSOCKET_OPTIONS)
    _wait_for_ws_completion(done, WS_TIMEOUT_SECONDS, "Spark")

    if errors:
        LOGGER.error("Spark chat failed errors=%s", len(errors))
        raise RuntimeError("; ".join(errors))

    answer = "".join(answer_parts).strip()
    if not answer:
        LOGGER.error("Spark chat returned empty answer")
        raise RuntimeError("Spark 没有返回有效文本。")
    LOGGER.info("Spark chat completed chars=%s", len(answer))
    return answer


def build_reply(user_text):
    messages = [
        {
            "role": "user",
            "content": (
                "你是一个语音聊天机器人。请用自然、简短、口语化的中文回复用户，"
                "不要输出Markdown。用户刚才说："
                f"{user_text}"
            ),
        }
    ]
    return spark_chat(messages, temperature=0.5, max_tokens=512)


def build_report(conversation):
    transcript = "\n".join(
        f"第 {index} 轮\n用户：{turn['user']}\n机器人：{turn['assistant']}"
        for index, turn in enumerate(conversation, 1)
    )
    messages = [
        {
            "role": "user",
            "content": (
                "请根据以下语音聊天记录生成一份简洁的 Markdown 报告。"
                "报告必须包含：对话摘要、用户主要意图、机器人回应概述、后续建议。"
                "只输出报告正文，不要解释。\n\n"
                f"{transcript}"
            ),
        }
    ]
    return spark_chat(messages, temperature=0.4, max_tokens=1200)


def write_report(conversation, report_file):
    report_path = Path(report_file)
    report_body = build_report(conversation)
    audio_lines = "\n".join(f"- 第 {index} 轮语音回复：{turn['audio']}" for index, turn in enumerate(conversation, 1))
    content = (
        f"# 语音聊天报告\n\n"
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"{report_body.strip()}\n\n"
        f"## 音频文件\n\n"
        f"{audio_lines}\n"
    )
    report_path.write_text(content, encoding="utf-8-sig")
    return report_path


def main():
    parser = argparse.ArgumentParser(description="Run a minimal iFlytek voice-chat pipeline.")
    parser.add_argument("--audio", default=str(DEFAULT_AUDIO), help="16k/16bit/mono raw PCM input file")
    parser.add_argument("--reply-audio", default=str(PROJECT_DIR / "reply_1.mp3"), help="MP3 reply output path")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="Markdown report output path")
    args = parser.parse_args()

    try:
        print("[1/4] 语音听写中...")
        user_text = recognize_pcm(args.audio)
        print(f"识别结果：{user_text}")
    except RuntimeError as e:
        print(f"[错误] 语音听写失败: {e}")
        print("提示: 请检查讯飞 IAT 服务是否已开通，以及 APPID/APIKey/APISecret 是否正确。")
        return

    try:
        print("[2/4] 生成机器人回复...")
        reply = build_reply(user_text)
        print(f"机器人回复：{reply}")
    except RuntimeError as e:
        print(f"[错误] 生成回复失败: {e}")
        print("提示: 请检查讯飞 Spark 大模型服务是否已开通。")
        return

    try:
        print("[3/4] 合成机器人语音...")
        reply_audio = synthesize_mp3(reply, args.reply_audio)
        print(f"语音回复文件：{reply_audio}")
    except RuntimeError as e:
        print(f"[错误] 语音合成失败: {e}")
        print("提示: 请检查讯飞 TTS 服务是否已开通。")
        return

    try:
        print("[4/4] 生成报告...")
        report = write_report([{"user": user_text, "assistant": reply, "audio": str(reply_audio)}], args.report)
        print(f"报告文件：{report}")
    except RuntimeError as e:
        print(f"[错误] 生成报告失败: {e}")
        return

    print("完成。")


if __name__ == "__main__":
    main()
