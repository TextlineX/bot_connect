import json
import time

from .base import MasterModule


class MotionModule(MasterModule):
    name = "motion"

    def capabilities(self) -> dict:
        return {
            "motion": {
                "cmd_vel": {
                    "available": True,
                    "transport": "sdk",
                }
            }
        }

    def status(self) -> dict:
        return {"cmd_vel_available": True}

    async def execute_move(self, linear: float, angular: float, lateral: float = 0.0) -> dict:
        self.context.sdk.set_velocity(linear, angular, lateral=lateral)
        return {
            "ok": True,
            "detail": "motion move ok",
            "module": self.name,
            "action": "motion.move",
            "payload": {
                "linear": linear,
                "lateral": lateral,
                "angular": angular,
            },
        }

    async def execute_stop(self) -> dict:
        self.context.sdk.set_velocity(0, 0, lateral=0)
        return {
            "ok": True,
            "detail": "motion stop ok",
            "module": self.name,
            "action": "motion.stop",
            "payload": {
                "linear": 0,
                "lateral": 0,
                "angular": 0,
            },
        }

    async def handle(self, ws, data: dict) -> bool:
        if data.get("type") != "cmd_vel":
            return False

        payload = data.get("payload", {})
        result = await self.execute_move(
            payload.get("linear", 0),
            payload.get("angular", 0),
            payload.get("lateral", 0),
        )
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
        return True
