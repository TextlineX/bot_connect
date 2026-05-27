#!/usr/bin/env python3
# 从机示例：支持 config_sync 持久化，cmd_vel / TTS 执行并回传 result
import math
import os
import sys
import time
import signal
import subprocess
import shutil
import atexit
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "common"
if COMMON.as_posix() not in sys.path:
    sys.path.insert(0, COMMON.as_posix())

from ws_client import WsClient
from role_config import save_role_config
from runtime import build_runtime
from stream_info import build_stream_urls
from action_presets import canonical_action, resolve_preset
from motion_controller import MotionController
from motion_presets import resolve_motion_command, resolve_motion_preset_name

ROLE_STATE, config_provider, on_config_sync = build_runtime(
    "slave",
    {
        "robot_id": "slave-01",
        "config_version": 0,
        "routing": {
            "brain_robot_id": "master-01",
            "control_robot_id": "slave-01",
        },
    },
)

WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:8765")
ROBOT_ID = os.getenv("ROBOT_ID", str(ROLE_STATE.get("robot_id") or "slave-01"))
ROLE_STATE["robot_id"] = ROBOT_ID
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
SIM_MODE = os.getenv("SIM_MODE", "1") == "1"
START_TS = time.time()
MEDIAMTX_PROC = None
RELAY_PROC = None
MJPEG_PROCS: list[subprocess.Popen] = []
MJPEG_LOGS = []
STREAM_MODE = os.getenv("STREAM_MODE", "rtsp").lower()  # rtsp | http_mjpeg
STREAM_PRESETS: list[dict] = []

try:
    from tts_client import send_tts as ros_send_tts  # type: ignore
except Exception:
    ros_send_tts = None

try:
    from preset_motion_client import run_preset as ros_run_preset  # type: ignore
except Exception:
    ros_run_preset = None


def stop_stream_stack():
    global MEDIAMTX_PROC, RELAY_PROC, MJPEG_PROCS
    procs = [RELAY_PROC, MEDIAMTX_PROC] + MJPEG_PROCS
    for proc in procs:
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
    for proc in procs:
        if proc and proc.poll() is None:
            try:
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
    MEDIAMTX_PROC = None
    RELAY_PROC = None
    MJPEG_PROCS = []
    for f in list(MJPEG_LOGS):
        try:
            f.close()
        except Exception:
            pass
    MJPEG_LOGS.clear()


def start_stream_stack():
    """自动拉起推流栈，默认开启，缺依赖会自动跳过。"""
    global MEDIAMTX_PROC, RELAY_PROC, MJPEG_PROCS, STREAM_PRESETS, MJPEG_LOGS
    if os.getenv("STREAM_AUTOSTART", "1").lower() not in {"1", "true", "yes"}:
        return

    if STREAM_MODE == "http_mjpeg":
        host = os.getenv("STREAM_PUBLIC_HOST") or build_stream_urls(default_name=ROBOT_ID).get("host") or "127.0.0.1"
        base_port = int(os.getenv("STREAM_HTTP_BASE", "8000"))
        topics_env = os.getenv("STREAM_TOPICS")
        topics = [t for t in (topics_env.split(",") if topics_env else []) if t.strip()]
        if not topics:
            topics = [
                "/aima/hal/sensor/rgb_head_rear/rgb_image/compressed",
                "/aima/hal/sensor/stereo_head_front_left/rgb_image/compressed",
                "/aima/hal/sensor/stereo_head_front_right/rgb_image/compressed",
                "/aima/hal/sensor/rgbd_head_front/rgb_image/compressed",
            ]
        STREAM_PRESETS = []
        port = base_port
        log_dir = ROOT / "runs" / "stream_logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            log_dir = None
        for topic in topics:
            cmd = [
                sys.executable,
                str(ROOT / "scripts" / "mjpeg_http_server.py"),
                "--topic",
                topic,
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
            ]
            try:
                log_f = None
                if log_dir:
                    safe_topic = "".join(c if (c.isalnum() or c in ("-", "_")) else "_" for c in str(topic).strip())
                    safe_topic = safe_topic.strip("_") or "topic"
                    log_path = log_dir / f"mjpeg_{port}_{safe_topic}.log"
                    log_f = open(log_path, "ab")
                    MJPEG_LOGS.append(log_f)
                proc = subprocess.Popen(
                    cmd,
                    stdout=(log_f if log_f else subprocess.DEVNULL),
                    stderr=(subprocess.STDOUT if log_f else subprocess.DEVNULL),
                )
                MJPEG_PROCS.append(proc)
                url = f"http://{host}:{port}/stream.mjpg"
                parts = [p for p in str(topic).split("/") if p]
                label = parts[-3] if len(parts) >= 3 else (parts[-1] if parts else str(topic))
                STREAM_PRESETS.append({"topic": topic, "url": url, "label": label})
                print(f"[STREAM] mjpeg started: {topic} -> {url}")
            except Exception as exc:
                print(f"[STREAM] mjpeg start failed ({topic}): {exc}")
            port += 1
        return

    mediamtx_bin = os.getenv("MEDIAMTX_BIN", "mediamtx")
    ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")
    stream = build_stream_urls(default_name=ROBOT_ID)
    rtsp_url = stream.get("rtsp_url") or f"rtsp://127.0.0.1:8554/{ROBOT_ID}"
    topic = os.getenv("STREAM_TOPIC", "/aima/hal/sensor/stereo_head_front_right/rgb_image/compressed")
    qos_rel = os.getenv("STREAM_QOS_RELIABILITY", "best_effort")
    qos_dur = os.getenv("STREAM_QOS_DURABILITY", "volatile")
    qos_depth = os.getenv("STREAM_QOS_DEPTH", "5")
    input_format = os.getenv("STREAM_INPUT_FORMAT", "mjpeg")

    mediamtx_path = shutil.which(mediamtx_bin)
    if mediamtx_path and MEDIAMTX_PROC is None:
        try:
            MEDIAMTX_PROC = subprocess.Popen(
                [mediamtx_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"[STREAM] mediamtx started: {mediamtx_path}")
        except Exception as exc:
            print(f"[STREAM] mediamtx start failed: {exc}")

    relay_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "camera_rtsp_relay.py"),
        "--ros-args",
        "-p",
        f"topic:={topic}",
        "-p",
        f"rtsp_url:={rtsp_url}",
        "-p",
        f"ffmpeg_bin:={ffmpeg_bin}",
        "-p",
        f"input_format:={input_format}",
        "-p",
        f"qos_reliability:={qos_rel}",
        "-p",
        f"qos_durability:={qos_dur}",
        "-p",
        f"qos_depth:={qos_depth}",
    ]
    if RELAY_PROC is None:
        try:
            RELAY_PROC = subprocess.Popen(
                relay_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"[STREAM] relay started: {topic} -> {rtsp_url}")
        except Exception as exc:
            print(f"[STREAM] relay start failed: {exc}")


def register_cleanup():
    def _cleanup():
        try:
            stop_stream_stack()
        except Exception:
            pass
        try:
            sdk.close()
        except Exception:
            pass

    atexit.register(_cleanup)
    signal.signal(signal.SIGTERM, lambda *_: (_cleanup(), sys.exit(0)))
    signal.signal(signal.SIGINT, lambda *_: (_cleanup(), sys.exit(0)))


class RobotSDK:
    def __init__(self):
        self.motion = MotionController(ROBOT_ID, sim_mode=SIM_MODE)
        self.motion.start()
        self.last_velocity = {"linear": 0.0, "lateral": 0.0, "angular": 0.0, "at": None}

    def close(self):
        try:
            self.motion.close()
        except Exception:
            pass

    def set_velocity(self, linear: float, angular: float, lateral: float = 0.0, duration: float | None = None, label: str | None = None):
        self.last_velocity = {
            "linear": float(linear),
            "lateral": float(lateral),
            "angular": float(angular),
            "at": time.time(),
        }
        self.motion.command(float(linear), float(angular), float(lateral), duration=duration, label=label)

    def run_script(self, script: list[dict], label: str | None = None):
        # 脚本执行期间，last_velocity 仅反映最后一次外部下发（用于可视化），实时速度以 controller.status 为准
        self.last_velocity = {"linear": 0.0, "lateral": 0.0, "angular": 0.0, "at": time.time()}
        self.motion.run_script(script, label=label)

    def status(self):
        now = time.time()
        elapsed = now - START_TS
        last_move_at = self.last_velocity.get("at")
        battery_ratio = round(0.8 - min(elapsed / 36000, 0.15), 2)
        streams = build_stream_urls(default_name=ROBOT_ID)
        if STREAM_PRESETS:
            streams["presets"] = STREAM_PRESETS
            if not streams.get("auto_url") and len(STREAM_PRESETS) > 0:
                streams["auto_url"] = STREAM_PRESETS[0].get("url")
        if STREAM_MODE == "http_mjpeg":
            streams["preferred_player"] = "mjpg"
        return {
            "ts": now,
            "battery": battery_ratio,
            "system": {
                "hostname": os.getenv("COMPUTERNAME") or os.getenv("HOSTNAME") or "slave-local",
                "ws_url": WS_URL,
                "sim_mode": SIM_MODE,
                "local_test": True,
                "runtime_label": "本地模拟从机",
                "uptime_sec": round(elapsed, 1),
            },
            "motion": {
                "linear": self.last_velocity.get("linear", 0.0),
                "lateral": self.last_velocity.get("lateral", 0.0),
                "angular": self.last_velocity.get("angular", 0.0),
                "last_command_age_sec": round(now - last_move_at, 1) if last_move_at else None,
                "controller": self.motion.status(),
            },
            "audio": {
                "tts_ready": bool(ros_send_tts),
                "asr_bridge_ready": False,
            },
            "sensors": {
                "battery_pct": int(battery_ratio * 100),
                "network_pct": 96,
                "audio_level_pct": int(24 + 10 * math.sin(elapsed / 4.2)),
                "imu_yaw_deg": round((elapsed * 9) % 360, 1),
                "lidar_distance_m": round(1.8 + 0.35 * math.sin(elapsed / 5.0), 2),
                "motor_temp_c": round(34 + 2.5 * math.sin(elapsed / 8.0), 1),
                "posture": "tracking",
            },
            "streams": streams,
        }


sdk = RobotSDK()


def on_cmd(data):
    payload = data.get("payload", {})
    sdk.set_velocity(payload.get("linear", 0), payload.get("angular", 0), payload.get("lateral", 0))
    return {
        "ok": True,
        "detail": "cmd_vel handled",
        "module": "slave",
        "action": "cmd_vel",
        "payload": payload,
    }


def _do_tts(text: str) -> dict:
    if ros_send_tts:
        try:
            ok = bool(ros_send_tts(text))
            return {"ok": ok, "detail": "tts ok" if ok else "tts failed"}
        except Exception as exc:
            return {"ok": False, "detail": f"tts error: {exc}"}
    return {"ok": False, "detail": "tts unavailable (no rclpy/tts_client)"}


def _do_preset(name: str, motion_id=None, area_id=None, interrupt=False) -> dict:
    if ros_run_preset:
        try:
            ok = bool(ros_run_preset(name, motion_id=motion_id, area_id=area_id, interrupt=interrupt))
            return {"ok": ok, "detail": "preset ok" if ok else "preset failed"}
        except Exception as exc:
            return {"ok": False, "detail": f"preset error: {exc}"}
    return {"ok": False, "detail": "preset unavailable (no rclpy/preset_motion_client)"}


def on_exec(data):
    payload = data.get("payload", {})
    raw_action = payload.get("action") or data.get("action")
    raw_action = str(raw_action or "").strip()
    action = canonical_action(raw_action)
    if action == "voice.tts":
        text = payload.get("text") or payload.get("message") or "你好，我是从机。"
        result = _do_tts(str(text))
        result.update({"module": "slave", "action": "voice.tts", "text": text})
        return result

    if action in {"motion.move", "motion.macro", "motion.preset"}:
        if sdk.motion.is_estopped():
            return {
                "ok": False,
                "detail": "motion rejected: estop active",
                "module": "slave",
                "action": "motion.move",
                "payload": payload,
            }
        preset_from_action = resolve_motion_preset_name(raw_action)
        if preset_from_action and not any(k in payload for k in ("motion_preset", "preset", "macro", "pattern")):
            payload = {**payload, "preset": preset_from_action}
        cmd = resolve_motion_command(payload)
        if cmd.get("script"):
            sdk.run_script(cmd["script"], label=cmd.get("label") or cmd.get("preset"))
        else:
            sdk.set_velocity(
                cmd.get("linear", 0.0),
                cmd.get("angular", 0.0),
                cmd.get("lateral", 0.0),
                duration=cmd.get("duration"),
                label=cmd.get("label") or cmd.get("preset"),
            )
        return {
            "ok": True,
            "detail": "motion move ok" + (f" | {cmd.get('label')}" if cmd.get("label") else ""),
            "module": "slave",
            "action": "motion.move",
            "payload": {**payload, **{k: v for k, v in cmd.items() if v is not None}},
        }

    if action == "motion.estop":
        reason = payload.get("reason") or payload.get("detail") or ""
        sdk.motion.estop(reason=str(reason))
        return {
            "ok": True,
            "detail": "motion estop ok",
            "module": "slave",
            "action": "motion.estop",
            "payload": {"reason": str(reason)},
        }

    if action in {"motion.clear_estop", "motion.estop_clear"}:
        sdk.motion.clear_estop()
        return {
            "ok": True,
            "detail": "motion clear estop ok",
            "module": "slave",
            "action": "motion.clear_estop",
            "payload": {},
        }

    if action == "motion.stop":
        sdk.set_velocity(0, 0, 0, duration=None, label="stop")
        return {
            "ok": True,
            "detail": "motion stop ok",
            "module": "slave",
            "action": "motion.stop",
            "payload": {"linear": 0, "lateral": 0, "angular": 0},
        }

    if action == "preset.run":
        preset = resolve_preset(raw_action, payload)
        if not preset:
            print(f"[SLAVE EXEC] unsupported preset raw={raw_action} payload={payload}")
            return {
                "ok": False,
                "detail": f"unsupported preset: {raw_action}",
                "module": "slave",
                "action": "preset.run",
                "payload": payload,
            }
        res = _do_preset(
            str(preset["name"]),
            motion_id=preset["motion_id"],
            area_id=preset["area_id"],
            interrupt=preset["interrupt"],
        )
        res.update({
            "module": "slave",
            "action": "preset.run",
            "detail": f"{res.get('detail')} | {preset['label']}",
            "payload": {
                "name": preset["name"],
                "motion_id": preset["motion_id"],
                "area_id": preset["area_id"],
                "interrupt": preset["interrupt"],
                "label": preset["label"],
                "raw_action": raw_action,
            },
        })
        print(
            "[SLAVE EXEC] preset",
            f"raw={raw_action}",
            f"name={preset['name']}",
            f"motion_id={preset['motion_id']}",
            f"area_id={preset['area_id']}",
            f"interrupt={preset['interrupt']}",
            f"ok={res.get('ok')}",
        )
        return res

    print("[SLAVE EXEC] unsupported", data)
    return {
        "ok": False,
        "detail": f"unsupported action: {action}",
        "module": "slave",
        "action": action,
        "payload": payload,
    }


def status_provider():
    return {
        "role": "slave",
        "config_version": int(ROLE_STATE.get("config_version") or 0),
        **sdk.status()
    }


def main():
    register_cleanup()
    start_stream_stack()
    save_role_config("slave", ROLE_STATE)
    client = WsClient(
        ROBOT_ID,
        WS_URL,
        AUTH_TOKEN,
        on_cmd=on_cmd,
        on_exec=on_exec,
        status_provider=status_provider,
        role="slave",
        config_provider=config_provider,
        on_config_sync=on_config_sync,
        verbose=True,
    )
    import asyncio

    asyncio.run(client.run())


if __name__ == "__main__":
    main()
