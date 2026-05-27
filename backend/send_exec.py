import asyncio
import json
import os
import time

import websockets

# 环境变量：
#   WS_URL    默认 ws://127.0.0.1:8765
#   TARGET    默认 slave-01
#   ROBOT_ID  默认 controller
#   ACTION    默认 motion.move（也可 motion.stop / preset.run / voice.tts）
#   PRESET    motion.move 的预设名（如 step / half_step / turn_left_15），不填则用 LIN/ANG/LAT
#   LIN/ANG/LAT  速度（m/s, rad/s）
#   DUR       持续时间（秒，可选）
url = os.getenv("WS_URL", "ws://127.0.0.1:8765")
target = os.getenv("TARGET", "slave-01")
rid = os.getenv("ROBOT_ID", "controller")

action = os.getenv("ACTION", "motion.move").strip() or "motion.move"
preset = (os.getenv("PRESET") or "").strip()
lin = float(os.getenv("LIN", "0"))
ang = float(os.getenv("ANG", "0"))
lat = float(os.getenv("LAT", "0"))
dur_raw = os.getenv("DUR")
dur = float(dur_raw) if dur_raw not in (None, "") else None


async def main():
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"type": "hello", "robot_id": rid, "ts": time.time()}))
        payload = {"action": action}
        if preset:
            payload["preset"] = preset
        else:
            payload.update({"linear": lin, "angular": ang, "lateral": lat})
        if dur is not None and dur > 0:
            payload["duration"] = dur

        msg = {
            "type": "exec",
            "robot_id": rid,
            "target_robot": target,
            "payload": payload,
            "ts": time.time(),
        }
        await ws.send(json.dumps(msg, ensure_ascii=False))
        print("sent", msg)


if __name__ == "__main__":
    asyncio.run(main())

