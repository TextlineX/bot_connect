#!/usr/bin/env python3
"""
离线分析 runs/<run_id>：
- 读取 ws.jsonl（由 scripts/record_ws.py 生成）
- 汇总消息 type 计数、时间范围、关键机器人状态（motion/controller/streams）
- 输出 summary.json 与 summary.md，便于离开机器人后复盘

用法：
  python scripts/analyze_run.py runs/20260424_1500
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path


def _read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def _safe_get(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def main():
    parser = argparse.ArgumentParser(description="bot_connect 采集包离线分析")
    parser.add_argument("run_dir", help="runs/<run_id> 目录")
    parser.add_argument("--ws", default="", help="ws.jsonl 路径（默认自动在 run_dir 下找）")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        raise SystemExit(f"run_dir not found: {run_dir}")

    ws_path = Path(args.ws) if args.ws else (run_dir / "ws.jsonl")
    if not ws_path.exists():
        raise SystemExit(f"ws jsonl not found: {ws_path}")

    type_counter: Counter[str] = Counter()
    robot_counter: Counter[str] = Counter()
    by_robot_type: dict[str, Counter[str]] = defaultdict(Counter)
    ts_min = None
    ts_max = None

    latest_status_by_robot: dict[str, dict] = {}
    latest_cap_by_robot: dict[str, dict] = {}

    for item in _read_jsonl(ws_path):
        data = item.get("data") if isinstance(item, dict) else None
        if not isinstance(data, dict):
            continue
        t = str(data.get("type") or "")
        rid = str(data.get("robot_id") or "")
        if t:
            type_counter[t] += 1
        if rid:
            robot_counter[rid] += 1
            if t:
                by_robot_type[rid][t] += 1

        ts = data.get("ts")
        try:
            ts = float(ts)
        except Exception:
            ts = None
        if ts is not None:
            ts_min = ts if ts_min is None else min(ts_min, ts)
            ts_max = ts if ts_max is None else max(ts_max, ts)

        if t == "status" and rid:
            latest_status_by_robot[rid] = data
        if t == "capabilities" and rid:
            latest_cap_by_robot[rid] = data

    video_dir = run_dir / "video"
    videos = []
    if video_dir.exists():
        for p in sorted(video_dir.glob("*.mp4")):
            videos.append(
                {
                    "name": p.name,
                    "bytes": p.stat().st_size,
                }
            )

    # 提取常用字段（以 slave-01 为主，若不同名字也尽量容错）
    slave_candidates = [r for r in latest_status_by_robot.keys() if r.startswith("slave")] or list(latest_status_by_robot.keys())
    slave_id = slave_candidates[0] if slave_candidates else ""
    slave_status = latest_status_by_robot.get(slave_id, {}) if slave_id else {}

    motion = _safe_get(slave_status, "motion", default={}) or {}
    motion_controller = _safe_get(motion, "controller", default={}) or {}
    streams = _safe_get(slave_status, "streams", default={}) or {}

    summary = {
        "run_dir": str(run_dir),
        "ws_jsonl": str(ws_path),
        "time_range": {
            "ts_min": ts_min,
            "ts_max": ts_max,
            "duration_sec": (ts_max - ts_min) if (ts_min is not None and ts_max is not None) else None,
        },
        "counts": {
            "by_type": dict(type_counter),
            "by_robot": dict(robot_counter),
        },
        "latest": {
            "slave_id": slave_id,
            "slave_motion_controller": motion_controller,
            "slave_streams": streams,
        },
        "videos": videos,
        "notes": {
            "motion_sim_mode": motion_controller.get("sim_mode"),
            "motion_ros_ready": _safe_get(motion_controller, "ros", "ready"),
            "motion_transport": motion_controller.get("transport"),
        },
    }

    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append(f"# 采集包总结：{run_dir.name}")
    lines.append("")
    lines.append(f"- ws：`{ws_path}`")
    if ts_min is not None and ts_max is not None:
        lines.append(f"- 时间范围：ts={ts_min:.3f} ~ {ts_max:.3f} （约 {ts_max - ts_min:.1f}s）")
    lines.append(f"- 消息类型：{', '.join(sorted(type_counter.keys())) or '-'}")
    lines.append("")
    if slave_id:
        lines.append(f"## Slave：{slave_id}")
        lines.append(f"- motion.transport：`{motion_controller.get('transport')}`")
        lines.append(f"- motion.sim_mode：`{motion_controller.get('sim_mode')}`")
        lines.append(f"- motion.ros.ready：`{_safe_get(motion_controller, 'ros', 'ready')}`")
        lines.append(f"- streams.preferred_player：`{streams.get('preferred_player')}`")
        presets = streams.get("presets") if isinstance(streams, dict) else None
        if isinstance(presets, list) and presets:
            lines.append(f"- streams.presets：{len(presets)} 条（前 3 条示例）")
            for p in presets[:3]:
                if isinstance(p, dict):
                    lines.append(f"  - {p.get('label') or p.get('topic')}: {p.get('url')}")
    lines.append("")
    if videos:
        lines.append("## 视频文件")
        lines.append(f"- `{video_dir}` 下 mp4 数量：{len(videos)}")
    else:
        lines.append("## 视频文件")
        lines.append("- 未检测到 mp4（检查录制是否启动、URL 是否可达）")
    lines.append("")
    lines.append("## 离线复盘建议")
    lines.append("- 先看 `summary.json` 里 `motion_sim_mode/motion_ros_ready`：若 sim_mode=true 或 ros.ready=false，现场运动可能是“假成功”。")
    lines.append("- 看 `*_ffmpeg.log` 是否有 timeout/404/connection reset。")
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"ok": True, "out": str(run_dir / "summary.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

