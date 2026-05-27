#!/usr/bin/env python3
"""
MJPEG 录制器：把一个或多个 HTTP MJPEG 流录制为 mp4 分段文件，并写 manifest。

设计目标：
- 在现场（连着机器人）一键采集，回到办公室直接用 runs/ 下的数据做复盘/训练/分析。
- 尽量只依赖 ffmpeg（最稳）而不是 OpenCV。

依赖：
- 本机可执行 ffmpeg（默认命令名：ffmpeg）

示例：
  python scripts/record_mjpeg.py --out-dir runs/20260424_1500/video ^
    --label left  --url "http://127.0.0.1:8765/proxy/robot/mjpg?port=8001&path=/stream.mjpg" ^
    --label right --url "http://127.0.0.1:8765/proxy/robot/mjpg?port=8002&path=/stream.mjpg" ^
    --duration-sec 1800
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


def _ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


@dataclass
class StreamSpec:
    label: str
    url: str


def _pair_streams(labels: list[str], urls: list[str]) -> list[StreamSpec]:
    if not urls:
        return []
    if labels and len(labels) != len(urls):
        raise SystemExit("--label 数量必须与 --url 数量一致（或不传 --label）")
    specs: list[StreamSpec] = []
    for i, url in enumerate(urls):
        label = labels[i] if labels else f"cam{i:02d}"
        label = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in label.strip()) or f"cam{i:02d}"
        specs.append(StreamSpec(label=label, url=str(url).strip()))
    return specs


def _build_ffmpeg_cmd(
    ffmpeg_bin: str,
    *,
    url: str,
    out_pattern: str,
    fps: float,
    crf: int,
    preset: str,
    segment_sec: int,
):
    # 说明：
    # - use_wallclock_as_timestamps：让输出更接近真实时间（便于与 WS 日志对齐）
    # - segment + strftime：按时间戳命名分片文件
    # - 统一输出 H264 mp4，离开现场后基本所有播放器/工具都能用
    return [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "info",
        "-y",
        "-fflags",
        "+genpts",
        "-use_wallclock_as_timestamps",
        "1",
        "-rw_timeout",
        "15000000",  # 15s
        "-i",
        url,
        "-an",
        "-r",
        str(float(fps)),
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(int(crf)),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-f",
        "segment",
        "-segment_time",
        str(int(segment_sec)),
        "-reset_timestamps",
        "1",
        "-strftime",
        "1",
        out_pattern,
    ]


def main():
    parser = argparse.ArgumentParser(description="HTTP MJPEG 录制（ffmpeg，多路可并行）")
    parser.add_argument("--out-dir", required=True, help="输出目录，例如 runs/20260424_1500/video")
    parser.add_argument("--url", action="append", default=[], help="输入 MJPEG URL，可重复多次")
    parser.add_argument("--label", action="append", default=[], help="每路视频标签，数量需与 --url 一致")
    parser.add_argument("--ffmpeg", default=os.getenv("FFMPEG_BIN", "ffmpeg"), help="ffmpeg 命令名/路径")
    parser.add_argument("--fps", type=float, default=15.0, help="输出帧率（建议 10~20）")
    parser.add_argument("--crf", type=int, default=23, help="H264 质量（越小越清晰/越大越省空间）")
    parser.add_argument("--preset", default="veryfast", help="H264 preset（越快越省 CPU）")
    parser.add_argument("--segment-sec", type=int, default=600, help="分段秒数（默认 10 分钟一段）")
    parser.add_argument("--duration-sec", type=float, default=0.0, help="录制总时长，0 表示一直录")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = _pair_streams(list(args.label), list(args.url))
    if not specs:
        raise SystemExit("缺少 --url")

    duration_sec = float(args.duration_sec or 0.0)
    duration_sec = 0.0 if duration_sec < 0 else duration_sec

    manifest = {
        "ts": _ts(),
        "out_dir": str(out_dir),
        "settings": {
            "ffmpeg": args.ffmpeg,
            "fps": float(args.fps),
            "crf": int(args.crf),
            "preset": str(args.preset),
            "segment_sec": int(args.segment_sec),
            "duration_sec": float(duration_sec),
        },
        "streams": [{"label": s.label, "url": s.url} for s in specs],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    procs: list[subprocess.Popen] = []
    try:
        for s in specs:
            out_pattern = str(out_dir / f"{s.label}_%Y%m%d_%H%M%S.mp4")
            cmd = _build_ffmpeg_cmd(
                args.ffmpeg,
                url=s.url,
                out_pattern=out_pattern,
                fps=float(args.fps),
                crf=int(args.crf),
                preset=str(args.preset),
                segment_sec=int(args.segment_sec),
            )
            log_path = out_dir / f"{s.label}_ffmpeg.log"
            log_f = log_path.open("ab")
            p = subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT)
            procs.append(p)
            print(f"[record] {s.label} pid={p.pid} url={s.url}")

        if duration_sec > 0:
            t_end = time.time() + duration_sec
            while time.time() < t_end:
                time.sleep(0.5)
        else:
            while True:
                time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        # 温和退出
        for p in procs:
            if p.poll() is None:
                try:
                    p.send_signal(signal.SIGINT)
                except Exception:
                    pass
        time.sleep(1.0)
        for p in procs:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        time.sleep(1.0)
        for p in procs:
            if p.poll() is None:
                try:
                    p.kill()
                except Exception:
                    pass


if __name__ == "__main__":
    main()

