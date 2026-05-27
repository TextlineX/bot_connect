import asyncio
import json
import time

from .base import MasterModule
from action_presets import ACTION_ALIASES, PRESET_DEFS, canonical_action, resolve_preset
from motion_presets import resolve_motion_command, resolve_motion_preset_name


class ActionRouterModule(MasterModule):
    name = "action_router"

    def __init__(self, context):
        super().__init__(context)
        self._stop_task = None

    def capabilities(self) -> dict:
        return {
            "actions": {
                "available": True,
                "supported": [
                    "voice.tts",
                    "motion.move",
                    "motion.stop",
                    "preset.run",
                ],
                "aliases": ACTION_ALIASES,
                "presets": list(PRESET_DEFS.keys()),
            }
        }

    def status(self) -> dict:
        return {"action_router_available": True}

    async def handle(self, ws, data: dict) -> bool:
        if data.get("type") != "exec":
            return False

        payload = data.get("payload", {})
        action = payload.get("action") or data.get("action")
        if not action or action == "tts":
            return False

        result = await self.execute_action(action, payload)
        reply = {
            "type": "result",
            "robot_id": self.context.robot_id,
            "ts": time.time(),
            "request_id": data.get("request_id") or payload.get("request_id"),
            "source_robot_id": data.get("source_robot_id") or data.get("robot_id"),
            "source_role": data.get("source_role"),
            "target_robot": data.get("target_robot"),
            **result,
        }
        try:
            await ws.send(json.dumps(reply, ensure_ascii=False))
        except Exception:
            pass
        return result.get("handled", False)

    async def execute_action(self, action: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        canonical = self._canonical_action(action)
        if canonical == "voice.tts":
            if not self.context.voice_module:
                return self._result(False, canonical, "voice module unavailable", handled=True)
            text = str(payload.get("text") or payload.get("message") or "").strip()
            if not text:
                return self._result(False, canonical, "missing text", handled=True)
            return self._result_from(await self.context.voice_module.execute_tts(text), handled=True)

        if canonical == "motion.stop":
            if not self.context.motion_module:
                return self._result(False, canonical, "motion module unavailable", handled=True)
            if self._stop_task:
                self._stop_task.cancel()
                self._stop_task = None
            return self._result_from(await self.context.motion_module.execute_stop(), handled=True)

        if canonical == "motion.move":
            if not self.context.motion_module:
                return self._result(False, canonical, "motion module unavailable", handled=True)

            preset_from_action = resolve_motion_preset_name(action)
            if preset_from_action and not any(k in payload for k in ("motion_preset", "preset", "macro", "pattern")):
                payload = {**payload, "preset": preset_from_action}

            use_rich_payload = bool(preset_from_action) or any(
                key in payload
                for key in (
                    "motion_preset",
                    "preset",
                    "macro",
                    "pattern",
                    "duration",
                    "duration_sec",
                    "distance",
                    "distance_m",
                    "angle_deg",
                    "angle_rad",
                    "repeat",
                    "times",
                )
            )
            if use_rich_payload:
                cmd = resolve_motion_command(payload)
                linear = cmd.get("linear", 0.0)
                lateral = cmd.get("lateral", 0.0)
                angular = cmd.get("angular", 0.0)
                duration = float(cmd.get("duration") or 0.0)
            else:
                linear, angular = self._resolve_motion_payload(action, payload)
                lateral = self._to_float(payload.get("lateral"), 0.0)
                duration = self._to_float(payload.get("duration"), 0)

            result = await self.context.motion_module.execute_move(linear, angular, lateral=lateral)
            if duration > 0:
                if self._stop_task:
                    self._stop_task.cancel()
                self._stop_task = asyncio.create_task(self._stop_after(duration))
                result["payload"]["duration"] = duration
                result["detail"] = f"{result['detail']} duration={duration}"
            return self._result_from(result, handled=True)

        if canonical == "preset.run":
            preset = self._resolve_preset_payload(action, payload)
            if not preset:
                return self._result(False, canonical, f"unsupported preset: {action}", handled=True)
            ok = bool(
                self.context.sdk.run_preset(
                    preset["name"],
                    motion_id=preset["motion_id"],
                    area_id=preset["area_id"],
                    interrupt=preset["interrupt"],
                )
            )
            detail = "preset ok" if ok else "preset failed"
            return self._result(
                ok,
                canonical,
                f"{detail}: {preset['label']}",
                handled=True,
                payload={
                    "name": preset["name"],
                    "motion_id": preset["motion_id"],
                    "area_id": preset["area_id"],
                    "interrupt": preset["interrupt"],
                    "label": preset["label"],
                },
            )

        return self._result(False, canonical, f"unsupported action: {action}", handled=False)

    async def _stop_after(self, duration: float):
        try:
            await asyncio.sleep(duration)
            await self.context.motion_module.execute_stop()
        except asyncio.CancelledError:
            return

    def _canonical_action(self, action: str) -> str:
        return canonical_action(action)

    def _resolve_motion_payload(self, action: str, payload: dict):
        linear = self._to_float(payload.get("linear"), 0)
        angular = self._to_float(payload.get("angular"), 0)
        alias = str(action or "").strip()
        if alias == "motion.move":
            alias = str(payload.get("keyword") or payload.get("intent") or alias).strip()
        if alias == "move_forward" and not linear:
            linear = self._to_float(payload.get("speed"), 0.2)
        elif alias == "move_backward" and not linear:
            linear = -abs(self._to_float(payload.get("speed"), 0.2))
        elif alias == "turn_left" and not angular:
            angular = abs(self._to_float(payload.get("speed"), 0.3))
        elif alias == "turn_right" and not angular:
            angular = -abs(self._to_float(payload.get("speed"), 0.3))
        elif alias == "前进" and not linear:
            linear = self._to_float(payload.get("speed"), 0.2)
        elif alias == "后退" and not linear:
            linear = -abs(self._to_float(payload.get("speed"), 0.2))
        elif alias == "左转" and not angular:
            angular = abs(self._to_float(payload.get("speed"), 0.3))
        elif alias == "右转" and not angular:
            angular = -abs(self._to_float(payload.get("speed"), 0.3))
        return linear, angular

    def _resolve_preset_payload(self, action: str, payload: dict) -> dict | None:
        return resolve_preset(action, payload)

    def _to_float(self, value, default: float) -> float:
        try:
            if value in ("", None):
                return default
            return float(value)
        except Exception:
            return default

    def _to_int(self, value):
        try:
            if value in ("", None):
                return None
            return int(value)
        except Exception:
            return None

    def _to_bool(self, value, default: bool) -> bool:
        if value in ("", None):
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _result(self, ok: bool, action: str, detail: str, handled: bool, payload: dict | None = None):
        return {
            "ok": ok,
            "detail": detail,
            "module": self.name,
            "action": action,
            "handled": handled,
            "payload": payload or {},
        }

    def _result_from(self, result: dict, handled: bool):
        merged = dict(result)
        merged["handled"] = handled
        return merged
