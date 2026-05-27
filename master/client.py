#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from websockets.exceptions import ConnectionClosed

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "common"
MASTER_DIR = ROOT / "master"
HANDLERS = MASTER_DIR / "handlers"
for candidate in (ROOT, COMMON, MASTER_DIR, HANDLERS):
    if candidate.as_posix() not in sys.path:
        sys.path.insert(0, candidate.as_posix())

from runtime import build_runtime
from ws_client import WsClient
from master.handlers.base import MasterContext
from master.handlers.registry import build_modules, module_catalog

SIM_MODE = os.getenv("SIM_MODE", "0") == "1"
send_tts = None
tts_shutdown = None
run_preset = None
preset_shutdown = None

if not SIM_MODE:
    try:
        from tts_client import send_tts, shutdown as tts_shutdown  # type: ignore

        print("[master] ROS/TTS 模式")
    except Exception as exc:
        print(f"[master] ROS/TTS 不可用，切换模拟模式: {exc}")
        SIM_MODE = True

if not SIM_MODE:
    try:
        from preset_motion_client import run_preset, shutdown as preset_shutdown  # type: ignore

        print("[master] 预设动作服务已连接")
    except Exception as exc:
        print(f"[master] preset motion 不可用，回退到 stub: {exc}")

if SIM_MODE:
    print("[master] SIM 模式（仅 WS，不调用 ROS/TTS）")

    def send_tts(text: str):
        print(f"[SIM TTS] {text}")
        return True

    def tts_shutdown():
        pass

if run_preset is None:

    def run_preset(name: str, motion_id: int | None = None, area_id: int | None = None, interrupt: bool = False):
        if SIM_MODE:
            print(
                "[SIM PRESET]",
                f"name={name}",
                f"motion_id={motion_id}",
                f"area_id={area_id}",
                f"interrupt={interrupt}",
            )
            return True
        print(
            "[master] preset runner unavailable",
            f"name={name}",
            f"motion_id={motion_id}",
            f"area_id={area_id}",
        )
        return False

if preset_shutdown is None:

    def preset_shutdown():
        pass


def merge_dict(base: dict, extra: dict) -> dict:
    for key, value in (extra or {}).items():
        if isinstance(base.get(key), dict) and isinstance(value, dict):
            base[key] = {**base[key], **value}
        else:
            base[key] = value
    return base


ROLE_STATE, config_provider, on_config_sync = build_runtime(
    "master",
    {
        "robot_id": "master-01",
        "config_version": 0,
    },
)

WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:8765")
ROBOT_ID = os.getenv("ROBOT_ID", str(ROLE_STATE.get("robot_id") or "master-01"))
ROLE_STATE["robot_id"] = ROBOT_ID
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
TTS_SERVICE = os.getenv("TTS_SERVICE", "/aimdk_5Fmsgs/srv/PlayTts")
AUDIO_TOPIC = os.getenv("AUDIO_TOPIC", "/aima/hal/audio/capture")
START_TS = time.time()
STATUS_HOOK = os.getenv("MASTER_STATUS_HOOK", "master.status_hook_example")


class RobotSDK:
    def __init__(self):
        self.last_velocity = {"linear": 0.0, "angular": 0.0, "at": None}
        self.last_preset = {"name": "", "motion_id": None, "area_id": None, "at": None}

    def set_velocity(self, linear: float, angular: float, lateral: float = 0.0):
        self.last_velocity = {
            "linear": float(linear),
            "lateral": float(lateral),
            "angular": float(angular),
            "at": time.time(),
        }
        print(f"[MASTER SDK] set_velocity linear={linear} lateral={lateral} angular={angular}")

    def run_preset(
        self,
        name: str,
        motion_id: int | None = None,
        area_id: int | None = None,
        interrupt: bool = False,
    ):
        ok = run_preset(name, motion_id=motion_id, area_id=area_id, interrupt=interrupt)
        if ok:
            self.last_preset = {
                "name": name,
                "motion_id": motion_id,
                "area_id": area_id,
                "at": time.time(),
            }
        return ok

    def status(self):
        now = time.time()
        elapsed = now - START_TS
        last_motion_at = self.last_velocity.get("at")
        last_preset_at = self.last_preset.get("at")
        last_action_at = max(last_motion_at or 0, last_preset_at or 0) or None
        return {
            "ts": now,
            "system": {
                "hostname": os.getenv("COMPUTERNAME") or os.getenv("HOSTNAME") or "master-local",
                "ws_url": WS_URL,
                "sim_mode": SIM_MODE,
                "local_test": True,
                "runtime_label": "本地模拟" if SIM_MODE else "本地真机桥接",
                "uptime_sec": round(elapsed, 1),
            },
            "motion": {
                "linear": self.last_velocity.get("linear", 0.0),
                "lateral": self.last_velocity.get("lateral", 0.0),
                "angular": self.last_velocity.get("angular", 0.0),
                "last_preset": self.last_preset.get("name") or "",
                "last_motion_id": self.last_preset.get("motion_id"),
                "last_area_id": self.last_preset.get("area_id"),
                "last_command_age_sec": round(now - last_action_at, 1) if last_action_at else None,
            },
            "audio": {
                "tts_ready": bool(send_tts),
                "asr_bridge_ready": bool(handle_audio_upload),
                "tts_service": TTS_SERVICE,
                "audio_topic": AUDIO_TOPIC,
            },
        }


sdk = RobotSDK()


def load_status_hook():
    path = (STATUS_HOOK or "").strip()
    if not path:
        return None
    try:
        module = __import__(path, fromlist=["get_status"])
        return getattr(module, "get_status", None)
    except Exception as exc:
        print(f"[master] status hook load failed: {exc}")
        return None


status_hook = load_status_hook()

try:
    from audio_upload_handler import handle_audio_upload
except Exception as exc:
    print(f"[master] audio_upload_handler unavailable: {exc}")
    handle_audio_upload = None

context = MasterContext(
    robot_id=ROBOT_ID,
    sim_mode=SIM_MODE,
    tts_service=TTS_SERVICE,
    audio_topic=AUDIO_TOPIC,
    sdk=sdk,
    send_tts=send_tts,
    handle_audio_upload=handle_audio_upload,
)
modules, enabled_module_names = build_modules(context)
module_map = {module.name: module for module in modules}
context.motion_module = module_map.get("motion")
context.voice_module = module_map.get("voice")
action_router = module_map.get("action_router")
if action_router:
    context.execute_action = action_router.execute_action
print(f"[master] enabled modules: {', '.join(enabled_module_names) or 'none'}")


def build_capability_payload() -> dict:
    payload = {
        "sim_mode": SIM_MODE,
        "enabled_modules": enabled_module_names,
        "module_catalog": module_catalog(),
    }
    for module in modules:
        merge_dict(payload, module.capabilities())
    return payload


async def capability_loop(ws):
    while True:
        caps = {
            "type": "capabilities",
            "robot_id": ROBOT_ID,
            "ts": time.time(),
            "payload": build_capability_payload(),
        }
        try:
            await ws.send(json.dumps(caps, ensure_ascii=False))
        except ConnectionClosed:
            break
        except Exception as exc:
            print("capabilities send error", exc)
        await asyncio.sleep(10)


def status_provider():
    base = {
        "role": "master",
        "config_version": config_provider().get("config_version", 0),
        "enabled_modules": enabled_module_names,
        "modules": {module.name: module.status() for module in modules},
        **sdk.status(),
    }
    if status_hook:
        try:
            extra = status_hook(sdk) or {}
            if isinstance(extra, dict):
                base = merge_dict(base, extra)
        except Exception as exc:
            print(f"[master] status hook error: {exc}")
    return base


async def main_async():
    client = WsClient(
        ROBOT_ID,
        WS_URL,
        AUTH_TOKEN,
        status_provider=status_provider,
        on_open=capability_loop,
        role="master",
        config_provider=config_provider,
        on_config_sync=on_config_sync,
        verbose=True,
    )
    default_handle = client.handle_message

    async def wrapped_handle(ws, data):
        handled = False
        for module in modules:
            result = module.handle(ws, data)
            if asyncio.iscoroutine(result):
                result = await result
            handled = handled or bool(result)
        # config_sync 需要继续走默认处理，给后端发送 ack。
        if data.get("type") == "config_sync":
            await default_handle(ws, data)
            return
        if handled:
            return
        await default_handle(ws, data)

    client.handle_message = wrapped_handle
    try:
        await client.run()
    finally:
        preset_shutdown()
        tts_shutdown()


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
