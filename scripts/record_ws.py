#!/usr/bin/env python3
"""
WS 录制器：连接 bot_connect 后端 WebSocket，把收到的消息落盘为 JSONL。

用途：
- 运动/视频联调时，留一份“事实日志”，离开机器人后可复盘。
- 可选过滤消息 type（例如只留 result/status/vision）。

依赖：
  pip install websockets

示例：
  python scripts/record_ws.py ws://127.0.0.1:8765 --out runs/ws_001.jsonl
  python scripts/record_ws.py ws://192.168.1.10:8765 --out runs/ws.jsonl --token xxx --types status,result,vision
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import websockets


def _now() -> float:
    return time.time()


def _parse_types(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    items = [x.strip() for x in str(raw).split(",") if x.strip()]
    return set(items) if items else None


async def record_ws(
    ws_url: str,
    out_path: Path,
    *,
    robot_id: str,
    role: str,
    token: str | None,
    types: set[str] | None,
    duration_sec: float | None,
):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    start_at = _now()
    written = 0

    async with websockets.connect(
        ws_url,
        ping_interval=20,
        ping_timeout=20,
        max_size=32 * 1024 * 1024,
    ) as ws:
        hello = {
            "type": "hello",
            "robot_id": robot_id,
            "role": role,
            "config_version": 0,
            "ts": start_at,
        }
        if token:
            hello["token"] = token
        await ws.send(json.dumps(hello, ensure_ascii=False))

        # 主动拉一次 config，便于把当时配置也写进日志
        await ws.send(
            json.dumps(
                {
                    "type": "config_get",
                    "robot_id": robot_id,
                    "role": role,
                    "config_version": 0,
                    "ts": _now(),
                },
                ensure_ascii=False,
            )
        )

        with out_path.open("a", encoding="utf-8") as f:
            while True:
                if duration_sec is not None and (_now() - start_at) >= duration_sec:
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                except websockets.ConnectionClosed:
                    break

                recv_at = _now()
                try:
                    obj = json.loads(raw)
                except Exception:
                    obj = {"type": "non_json", "raw": raw}

                msg_type = str(obj.get("type") or "")
                if types is not None and msg_type not in types:
                    continue

                line = {
                    "recv_at": recv_at,
                    "recv_at_ms": int(recv_at * 1000),
                    "ws_url": ws_url,
                    "data": obj,
                }
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
                written += 1

    return {"ok": True, "written": written, "out": str(out_path)}


def main():
    parser = argparse.ArgumentParser(description="bot_connect WebSocket 消息录制（JSONL）")
    parser.add_argument("ws_url", help="例如 ws://127.0.0.1:8765")
    parser.add_argument("--out", required=True, help="输出 JSONL 路径，例如 runs/2026xxxx/ws.jsonl")
    parser.add_argument("--rid", default=os.getenv("ROBOT_ID", "recorder"), help="录制器 robot_id")
    parser.add_argument("--role", default="controller", help="角色（通常用 controller）")
    parser.add_argument("--token", default=os.getenv("AUTH_TOKEN", ""), help="鉴权 token（对应后端 AUTH_TOKEN）")
    parser.add_argument("--types", default="", help="只录指定 type，用逗号分隔，例如 status,result,vision")
    parser.add_argument("--duration-sec", type=float, default=0.0, help="录制时长（秒），0 表示一直录")
    args = parser.parse_args()

    duration = float(args.duration_sec or 0.0)
    duration = None if duration <= 0 else duration
    types = _parse_types(args.types)
    token = str(args.token).strip() or None

    out_path = Path(args.out)
    res = asyncio.run(
        record_ws(
            args.ws_url,
            out_path,
            robot_id=str(args.rid).strip() or "recorder",
            role=str(args.role).strip() or "controller",
            token=token,
            types=types,
            duration_sec=duration,
        )
    )
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()

