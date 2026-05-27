import argparse
import asyncio
import os
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import cv2
import websockets

from .inference import YoloDetector, warmup
from .tracker import IouStabilizer, PassthroughTracker


class _PostProcessor:
    def update(self, dets):
        raise NotImplementedError

    def meta(self) -> Dict[str, Any]:
        return {}


class _PassthroughPost(_PostProcessor):
    def __init__(self):
        self.tracker = PassthroughTracker()

    def update(self, dets):
        dets = dets or []
        return dets, self.tracker.track(dets)

    def meta(self) -> Dict[str, Any]:
        return {"stabilize": False}


class _StabilizePost(_PostProcessor):
    def __init__(self, *, iou_thresh: float, min_hits: int, max_miss: int, smooth: float):
        self.iou_thresh = float(iou_thresh)
        self.min_hits = int(min_hits)
        self.max_miss = int(max_miss)
        self.smooth = float(smooth)
        self.stab = IouStabilizer(iou_thresh=self.iou_thresh, min_hits=self.min_hits, max_miss=self.max_miss, smooth=self.smooth)

    def update(self, dets):
        return self.stab.update(dets or [])

    def meta(self) -> Dict[str, Any]:
        return {
            "stabilize": True,
            "iou_thresh": float(self.iou_thresh),
            "min_hits": int(self.min_hits),
            "max_miss": int(self.max_miss),
            "smooth": float(self.smooth),
        }


def _parse_source(source: str):
    source = str(source or "").strip()
    return int(source) if source.isdigit() else source


def _parse_classes(raw: str) -> Optional[List[int]]:
    raw = str(raw or "").strip()
    if not raw:
        return None
    out: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    return out or None


class FrameGrabber:
    def __init__(self, source: str, name: str, buffer_frames: int = 6):
        self.source_raw = source
        self.source = _parse_source(source)
        self.name = name
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开视频源({name}): {source}")
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        self._lock = threading.Lock()
        self._buf = deque()
        self._buf_max = max(2, int(buffer_frames or 6))
        self.grabbed = 0
        self.dropped_buffer = 0
        self.dropped_sync = 0

        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"grabber-{name}")

    def start(self):
        self._thread.start()

    def close(self):
        self._stop.set()
        try:
            self._thread.join(timeout=1.0)
        except Exception:
            pass
        try:
            self.cap.release()
        except Exception:
            pass

    def latest(self) -> Optional[Tuple[float, Any]]:
        with self._lock:
            if not self._buf:
                return None
            ts, frame = self._buf[-1]
            return ts, frame

    def _drop_oldest_unsafe(self, n: int):
        for _ in range(max(0, int(n))):
            if not self._buf:
                return
            self._buf.popleft()
            self.dropped_sync += 1

    def pop_aligned_pair(self, other: "FrameGrabber", max_dt_ms: float) -> Optional[Tuple[float, Any, float, Any, float]]:
        """
        返回 (ts_l, frame_l, ts_r, frame_r, dt_ms)。
        若无法对齐，会尝试丢弃更旧的一侧帧帮助追赶，并返回 None。
        """
        max_dt_sec = float(max_dt_ms or 0.0) / 1000.0
        if max_dt_sec <= 0:
            return None

        # 固定加锁顺序避免死锁
        first, second = (self, other) if id(self) < id(other) else (other, self)
        with first._lock:
            with second._lock:
                a = list(self._buf)
                b = list(other._buf)
                if not a or not b:
                    return None

                i = 0
                j = 0
                best = None  # (abs_dt, i, j, dt)
                while i < len(a) and j < len(b):
                    dt = a[i][0] - b[j][0]
                    abs_dt = abs(dt)
                    if best is None or abs_dt < best[0]:
                        best = (abs_dt, i, j, dt)
                    if dt < 0:
                        i += 1
                    else:
                        j += 1

                if best is None:
                    return None

                abs_dt, bi, bj, dt = best
                if abs_dt <= max_dt_sec:
                    # 选中 bi/bj，将更早的帧全部丢弃（不含被选中的帧本身）
                    self._drop_oldest_unsafe(bi)
                    other._drop_oldest_unsafe(bj)
                    ts_l, frame_l = self._buf.popleft()
                    ts_r, frame_r = other._buf.popleft()
                    return ts_l, frame_l, ts_r, frame_r, float(dt * 1000.0)

                # 无法对齐：丢弃时间更旧的一侧一帧，帮助追赶
                if a[0][0] < b[0][0]:
                    self._drop_oldest_unsafe(1)
                else:
                    other._drop_oldest_unsafe(1)
                return None

    def _run(self):
        while not self._stop.is_set():
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            ts = time.time()
            with self._lock:
                self.grabbed += 1
                if len(self._buf) >= self._buf_max:
                    self._buf.popleft()
                    self.dropped_buffer += 1
                self._buf.append((ts, frame))


def build_vision_message(
    robot_id: str,
    task: str,
    camera: str,
    frame_index: int,
    dets: List[Dict[str, Any]],
    tracks: List[Dict[str, Any]],
    img_w: int,
    img_h: int,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    meta = {
        "task": task,
        "camera": camera,
        "frame_index": int(frame_index),
        "img_w": img_w,
        "img_h": img_h,
    }
    if extra_meta:
        meta.update(extra_meta)
    return {
        "type": "vision",
        "robot_id": robot_id,
        "ts": int(time.time() * 1000),
        "payload": {
            "dets": dets,
            "tracks": tracks,
            "strategy": "top1",
            "meta": meta,
        },
    }


def dump_json(obj: Dict[str, Any]) -> str:
    # 复用 schemas.py 的 orjson 优先策略
    try:
        import orjson

        return orjson.dumps(obj).decode()
    except Exception:
        import json

        return json.dumps(obj, ensure_ascii=False)


class JsonlWriter:
    def __init__(self, path: str):
        self.path = str(path or "").strip()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.fp = open(self.path, "a", encoding="utf-8")
        self._lock = threading.Lock()

    def write_obj(self, obj: Dict[str, Any]):
        line = dump_json(obj)
        with self._lock:
            self.fp.write(line + "\n")
            self.fp.flush()

    def close(self):
        try:
            self.fp.close()
        except Exception:
            pass


class VideoRecorder:
    def __init__(self, path: str, fps: float):
        self.path = str(path or "").strip()
        self.fps = float(fps or 10.0)
        self._writer = None

    def write(self, frame_bgr):
        if not self.path:
            return
        h, w = frame_bgr.shape[:2]
        if self._writer is None:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(self.path, fourcc, max(1.0, self.fps), (w, h))
        self._writer.write(frame_bgr)

    def close(self):
        if self._writer is not None:
            try:
                self._writer.release()
            except Exception:
                pass
            self._writer = None


def _segment_path(base_path: str, part: int) -> str:
    base_path = str(base_path or "").strip()
    root, ext = os.path.splitext(base_path)
    return f"{root}_part{int(part):04d}{ext or ''}"


class SegmentedJsonlWriter:
    def __init__(self, base_path: str, segment_sec: float):
        self.base_path = str(base_path or "").strip()
        self.segment_sec = float(segment_sec or 0.0)
        self.part = 0
        self.started_at = 0.0
        self._writer: Optional[JsonlWriter] = None
        self._lock = threading.Lock()

    def _ensure(self):
        now = time.time()
        if self._writer is None:
            self.part = 1
            self.started_at = now
            self._writer = JsonlWriter(_segment_path(self.base_path, self.part))
            return
        if self.segment_sec > 0 and (now - self.started_at) >= self.segment_sec:
            self._writer.close()
            self.part += 1
            self.started_at = now
            self._writer = JsonlWriter(_segment_path(self.base_path, self.part))

    def write_obj(self, obj: Dict[str, Any]):
        with self._lock:
            self._ensure()
            if self._writer:
                self._writer.write_obj(obj)

    def close(self):
        with self._lock:
            if self._writer:
                self._writer.close()
                self._writer = None


class SegmentedVideoRecorder:
    def __init__(self, base_path: str, fps: float, segment_sec: float):
        self.base_path = str(base_path or "").strip()
        self.fps = float(fps or 10.0)
        self.segment_sec = float(segment_sec or 0.0)
        self.part = 0
        self.started_at = 0.0
        self._rec: Optional[VideoRecorder] = None
        self._lock = threading.Lock()

    def _ensure(self):
        now = time.time()
        if self._rec is None:
            self.part = 1
            self.started_at = now
            self._rec = VideoRecorder(_segment_path(self.base_path, self.part), fps=self.fps)
            return
        if self.segment_sec > 0 and (now - self.started_at) >= self.segment_sec:
            self._rec.close()
            self.part += 1
            self.started_at = now
            self._rec = VideoRecorder(_segment_path(self.base_path, self.part), fps=self.fps)

    def write(self, frame_bgr):
        with self._lock:
            self._ensure()
            if self._rec:
                self._rec.write(frame_bgr)

    def close(self):
        with self._lock:
            if self._rec:
                self._rec.close()
                self._rec = None


async def push_loop(
    ws_url: str,
    ws_mode: str,
    robot_id: str,
    target_robot: str,
    left: FrameGrabber,
    right: FrameGrabber,
    left_detector: YoloDetector,
    right_detector: YoloDetector,
    left_task: str,
    right_task: str,
    fps: float,
    sync_ms: float,
    post_left: _PostProcessor,
    post_right: _PostProcessor,
    writer: Optional[Any] = None,
    rec_left: Optional[Any] = None,
    rec_right: Optional[Any] = None,
    rec_merged: Optional[Any] = None,
):
    sleep_sec = 1.0 / max(1.0, float(fps or 10))
    frame_i_left = 0
    frame_i_right = 0
    ema_fps = 0.0
    last_emit = 0.0

    async def connect_once():
        return await websockets.connect(ws_url, ping_interval=20, ping_timeout=20)

    backoff = 0.5
    while True:
        try:
            async with await connect_once() as ws:
                backoff = 0.5
                if ws_mode == "bot_connect":
                    hello = {
                        "type": "hello",
                        "robot_id": robot_id,
                        "role": "vision",
                        "config_version": 0,
                        "ts": time.time(),
                    }
                    await ws.send(dump_json(hello))

                while True:
                    pair = None
                    if sync_ms and sync_ms > 0:
                        for _ in range(6):
                            pair = left.pop_aligned_pair(right, max_dt_ms=float(sync_ms))
                            if pair:
                                break
                        if not pair:
                            await asyncio.sleep(0.01)
                            continue
                        ts_l, frame_l, ts_r, frame_r, sync_dt_ms = pair
                    else:
                        l = left.latest()
                        r = right.latest()
                        if not l or not r:
                            await asyncio.sleep(0.05)
                            continue
                        ts_l, frame_l = l
                        ts_r, frame_r = r
                        sync_dt_ms = float((ts_l - ts_r) * 1000.0)

                    t0 = time.perf_counter()
                    dets_l_raw = left_detector.infer(frame_l)
                    infer_l_ms = (time.perf_counter() - t0) * 1000.0
                    t1 = time.perf_counter()
                    dets_r_raw = right_detector.infer(frame_r)
                    infer_r_ms = (time.perf_counter() - t1) * 1000.0
                    dets_l, tracks_l = post_left.update(dets_l_raw)
                    dets_r, tracks_r = post_right.update(dets_r_raw)

                    now = time.time()
                    if last_emit > 0:
                        inst = 1.0 / max(1e-6, (now - last_emit))
                        ema_fps = inst if ema_fps <= 0 else (ema_fps * 0.9 + inst * 0.1)
                    last_emit = now

                    if rec_left:
                        rec_left.write(frame_l)
                    if rec_right:
                        rec_right.write(frame_r)
                    if rec_merged:
                        try:
                            h = max(frame_l.shape[0], frame_r.shape[0])
                            w1 = int(frame_l.shape[1])
                            w2 = int(frame_r.shape[1])
                            merged = cv2.resize(frame_l, (w1, h)) if frame_l.shape[0] != h else frame_l
                            right_rs = cv2.resize(frame_r, (w2, h)) if frame_r.shape[0] != h else frame_r
                            rec_merged.write(cv2.hconcat([merged, right_rs]))
                        except Exception:
                            pass

                    msg_l = build_vision_message(
                        robot_id=robot_id,
                        task=left_task,
                        camera="left",
                        frame_index=frame_i_left,
                        dets=[d.__dict__ for d in dets_l],
                        tracks=[t.__dict__ for t in tracks_l],
                        img_w=int(frame_l.shape[1]),
                        img_h=int(frame_l.shape[0]),
                        extra_meta={
                            "sync_dt_ms": float(sync_dt_ms),
                            "grab_age_ms": float((now - ts_l) * 1000.0),
                            "infer_ms": float(infer_l_ms),
                            "loop_fps": float(ema_fps),
                            "grabbed": int(left.grabbed),
                            "dropped_buffer": int(left.dropped_buffer),
                            "dropped_sync": int(left.dropped_sync),
                            "source_ts": float(ts_l),
                            **(post_left.meta() or {}),
                        },
                    )
                    msg_r = build_vision_message(
                        robot_id=robot_id,
                        task=right_task,
                        camera="right",
                        frame_index=frame_i_right,
                        dets=[d.__dict__ for d in dets_r],
                        tracks=[t.__dict__ for t in tracks_r],
                        img_w=int(frame_r.shape[1]),
                        img_h=int(frame_r.shape[0]),
                        extra_meta={
                            "sync_dt_ms": float(sync_dt_ms),
                            "grab_age_ms": float((now - ts_r) * 1000.0),
                            "infer_ms": float(infer_r_ms),
                            "loop_fps": float(ema_fps),
                            "grabbed": int(right.grabbed),
                            "dropped_buffer": int(right.dropped_buffer),
                            "dropped_sync": int(right.dropped_sync),
                            "source_ts": float(ts_r),
                            **(post_right.meta() or {}),
                        },
                    )

                    if target_robot:
                        msg_l["target_robot"] = target_robot
                        msg_r["target_robot"] = target_robot

                    if writer:
                        writer.write_obj(msg_l)
                        writer.write_obj(msg_r)

                    await ws.send(dump_json(msg_l))
                    await ws.send(dump_json(msg_r))
                    frame_i_left += 1
                    frame_i_right += 1
                    await asyncio.sleep(sleep_sec)
        except Exception:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.6, 8.0)


async def stdout_loop(
    left: FrameGrabber,
    right: FrameGrabber,
    left_detector: YoloDetector,
    right_detector: YoloDetector,
    robot_id: str,
    left_task: str,
    right_task: str,
    fps: float,
    sync_ms: float,
    post_left: _PostProcessor,
    post_right: _PostProcessor,
    writer: Optional[Any] = None,
    rec_left: Optional[Any] = None,
    rec_right: Optional[Any] = None,
    rec_merged: Optional[Any] = None,
):
    sleep_sec = 1.0 / max(1.0, float(fps or 10))
    frame_i_left = 0
    frame_i_right = 0
    ema_fps = 0.0
    last_emit = 0.0
    while True:
        pair = None
        if sync_ms and sync_ms > 0:
            for _ in range(6):
                pair = left.pop_aligned_pair(right, max_dt_ms=float(sync_ms))
                if pair:
                    break
            if not pair:
                await asyncio.sleep(0.01)
                continue
            ts_l, frame_l, ts_r, frame_r, sync_dt_ms = pair
        else:
            l = left.latest()
            r = right.latest()
            if not l or not r:
                await asyncio.sleep(0.05)
                continue
            ts_l, frame_l = l
            ts_r, frame_r = r
            sync_dt_ms = float((ts_l - ts_r) * 1000.0)

        t0 = time.perf_counter()
        dets_l_raw = left_detector.infer(frame_l)
        infer_l_ms = (time.perf_counter() - t0) * 1000.0
        t1 = time.perf_counter()
        dets_r_raw = right_detector.infer(frame_r)
        infer_r_ms = (time.perf_counter() - t1) * 1000.0
        dets_l, tracks_l = post_left.update(dets_l_raw)
        dets_r, tracks_r = post_right.update(dets_r_raw)

        now = time.time()
        if last_emit > 0:
            inst = 1.0 / max(1e-6, (now - last_emit))
            ema_fps = inst if ema_fps <= 0 else (ema_fps * 0.9 + inst * 0.1)
        last_emit = now

        if rec_left:
            rec_left.write(frame_l)
        if rec_right:
            rec_right.write(frame_r)
        if rec_merged:
            try:
                h = max(frame_l.shape[0], frame_r.shape[0])
                w1 = int(frame_l.shape[1])
                w2 = int(frame_r.shape[1])
                merged = cv2.resize(frame_l, (w1, h)) if frame_l.shape[0] != h else frame_l
                right_rs = cv2.resize(frame_r, (w2, h)) if frame_r.shape[0] != h else frame_r
                rec_merged.write(cv2.hconcat([merged, right_rs]))
            except Exception:
                pass

        msg_l = build_vision_message(
            robot_id=robot_id,
            task=left_task,
            camera="left",
            frame_index=frame_i_left,
            dets=[d.__dict__ for d in dets_l],
            tracks=[t.__dict__ for t in tracks_l],
            img_w=int(frame_l.shape[1]),
            img_h=int(frame_l.shape[0]),
            extra_meta={
                "sync_dt_ms": float(sync_dt_ms),
                "grab_age_ms": float((now - ts_l) * 1000.0),
                "infer_ms": float(infer_l_ms),
                "loop_fps": float(ema_fps),
                "grabbed": int(left.grabbed),
                "dropped_buffer": int(left.dropped_buffer),
                "dropped_sync": int(left.dropped_sync),
                "source_ts": float(ts_l),
                **(post_left.meta() or {}),
            },
        )
        msg_r = build_vision_message(
            robot_id=robot_id,
            task=right_task,
            camera="right",
            frame_index=frame_i_right,
            dets=[d.__dict__ for d in dets_r],
            tracks=[t.__dict__ for t in tracks_r],
            img_w=int(frame_r.shape[1]),
            img_h=int(frame_r.shape[0]),
            extra_meta={
                "sync_dt_ms": float(sync_dt_ms),
                "grab_age_ms": float((now - ts_r) * 1000.0),
                "infer_ms": float(infer_r_ms),
                "loop_fps": float(ema_fps),
                "grabbed": int(right.grabbed),
                "dropped_buffer": int(right.dropped_buffer),
                "dropped_sync": int(right.dropped_sync),
                "source_ts": float(ts_r),
                **(post_right.meta() or {}),
            },
        )

        if writer:
            writer.write_obj(msg_l)
            writer.write_obj(msg_r)

        print(dump_json(msg_l), flush=True)
        print(dump_json(msg_r), flush=True)
        frame_i_left += 1
        frame_i_right += 1
        await asyncio.sleep(sleep_sec)


def parse_args():
    p = argparse.ArgumentParser(description="双路视频流 + 两套 YOLO（独立运行，先方便调试）")
    p.add_argument("--left-source", type=str, required=True, help="左路视频源：摄像头索引或 RTSP/MJPEG/文件路径")
    p.add_argument("--right-source", type=str, required=True, help="右路视频源：摄像头索引或 RTSP/MJPEG/文件路径")
    p.add_argument("--left-weight", type=str, required=True, help="左路 YOLO 权重（建议动作/姿态相关）")
    p.add_argument("--right-weight", type=str, required=True, help="右路 YOLO 权重（建议物体检测相关）")

    p.add_argument("--left-task", type=str, default="action", help="左路任务名（写到 meta.task）")
    p.add_argument("--right-task", type=str, default="object", help="右路任务名（写到 meta.task）")

    p.add_argument("--device", type=str, default="cuda", help="cuda/cpu/0/1 ...")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--conf", type=float, default=0.35)
    p.add_argument("--left-classes", type=str, default="", help="可选：只检测某些类别，如 0,1,2")
    p.add_argument("--right-classes", type=str, default="", help="可选：只检测某些类别，如 0,1,2")

    p.add_argument("--fps", type=float, default=10.0, help="处理帧率（推理节流），默认 10")
    p.add_argument("--sync-ms", type=float, default=80.0, help="左右帧最大对齐时间差（毫秒）；0=不对齐直接取最新")
    p.add_argument("--buffer-frames", type=int, default=6, help="每路帧缓冲数量（对齐用），默认 6")
    p.add_argument("--stabilize", type=int, default=1, help="检测结果去抖/稳定输出：1=开（默认），0=关")
    p.add_argument("--min-hits", type=int, default=2, help="连续命中多少帧后才输出（默认 2）")
    p.add_argument("--max-miss", type=int, default=2, help="最多允许漏检多少帧仍保持输出（默认 2）")
    p.add_argument("--iou-thresh", type=float, default=0.5, help="IoU 匹配阈值（默认 0.5）")
    p.add_argument("--smooth", type=float, default=0.6, help="bbox 平滑系数 0~1（默认 0.6）")
    p.add_argument("--robot-id", type=str, default="vision-dual-01", help="对外发布时的 robot_id")
    p.add_argument("--out-jsonl", type=str, default="", help="可选：把每条 vision 消息追加写入 jsonl（便于复盘/训练）")
    p.add_argument("--record-left", type=str, default="", help="可选：录制左路原始视频（mp4），便于回放叠框")
    p.add_argument("--record-right", type=str, default="", help="可选：录制右路原始视频（mp4），便于回放叠框")
    p.add_argument("--record-merged", type=str, default="", help="可选：录制左右拼接原始视频（mp4），便于快速浏览")
    p.add_argument("--segment-sec", type=float, default=0.0, help="可选：落盘分段时长（秒），0=不分段")

    p.add_argument("--ws-url", type=str, default="", help="可选：推送到 WebSocket（如 ws://<PC_IP>:8765）")
    p.add_argument(
        "--ws-mode",
        type=str,
        default="bot_connect",
        choices=["bot_connect", "raw"],
        help="bot_connect=先发 hello，再发消息；raw=直接发消息（兼容自建 WS）",
    )
    p.add_argument("--target-robot", type=str, default="master-01", help="可选：走 bot_connect 转发到指定机器人")
    return p.parse_args()


def main():
    args = parse_args()

    left = FrameGrabber(args.left_source, "left", buffer_frames=int(args.buffer_frames or 6))
    right = FrameGrabber(args.right_source, "right", buffer_frames=int(args.buffer_frames or 6))
    left.start()
    right.start()

    segment_sec = float(args.segment_sec or 0.0)

    writer = None
    if args.out_jsonl:
        writer = SegmentedJsonlWriter(args.out_jsonl, segment_sec=segment_sec) if segment_sec > 0 else JsonlWriter(args.out_jsonl)

    rec_left = None
    if args.record_left:
        rec_left = SegmentedVideoRecorder(args.record_left, fps=float(args.fps or 10.0), segment_sec=segment_sec) if segment_sec > 0 else VideoRecorder(args.record_left, fps=float(args.fps or 10.0))
    rec_right = None
    if args.record_right:
        rec_right = SegmentedVideoRecorder(args.record_right, fps=float(args.fps or 10.0), segment_sec=segment_sec) if segment_sec > 0 else VideoRecorder(args.record_right, fps=float(args.fps or 10.0))
    rec_merged = None
    if args.record_merged:
        rec_merged = SegmentedVideoRecorder(args.record_merged, fps=float(args.fps or 10.0), segment_sec=segment_sec) if segment_sec > 0 else VideoRecorder(args.record_merged, fps=float(args.fps or 10.0))

    if int(args.stabilize or 0) == 1:
        post_left = _StabilizePost(
            iou_thresh=float(args.iou_thresh or 0.5),
            min_hits=int(args.min_hits or 2),
            max_miss=int(args.max_miss or 2),
            smooth=float(args.smooth or 0.6),
        )
        post_right = _StabilizePost(
            iou_thresh=float(args.iou_thresh or 0.5),
            min_hits=int(args.min_hits or 2),
            max_miss=int(args.max_miss or 2),
            smooth=float(args.smooth or 0.6),
        )
    else:
        post_left = _PassthroughPost()
        post_right = _PassthroughPost()

    left_detector = YoloDetector(
        args.left_weight,
        device=args.device,
        imgsz=args.imgsz,
        conf=args.conf,
        classes=_parse_classes(args.left_classes),
    )
    right_detector = YoloDetector(
        args.right_weight,
        device=args.device,
        imgsz=args.imgsz,
        conf=args.conf,
        classes=_parse_classes(args.right_classes),
    )
    warmup(left_detector, img_size=args.imgsz)
    warmup(right_detector, img_size=args.imgsz)

    async def runner():
        if args.ws_url:
            await push_loop(
                ws_url=args.ws_url,
                ws_mode=args.ws_mode,
                robot_id=args.robot_id,
                target_robot=args.target_robot if args.ws_mode == "bot_connect" else "",
                left=left,
                right=right,
                left_detector=left_detector,
                right_detector=right_detector,
                left_task=args.left_task,
                right_task=args.right_task,
                fps=float(args.fps or 10.0),
                sync_ms=float(args.sync_ms or 0.0),
                post_left=post_left,
                post_right=post_right,
                writer=writer,
                rec_left=rec_left,
                rec_right=rec_right,
                rec_merged=rec_merged,
            )
        else:
            await stdout_loop(
                left=left,
                right=right,
                left_detector=left_detector,
                right_detector=right_detector,
                robot_id=args.robot_id,
                left_task=args.left_task,
                right_task=args.right_task,
                fps=float(args.fps or 10.0),
                sync_ms=float(args.sync_ms or 0.0),
                post_left=post_left,
                post_right=post_right,
                writer=writer,
                rec_left=rec_left,
                rec_right=rec_right,
                rec_merged=rec_merged,
            )

    try:
        asyncio.run(runner())
    finally:
        if writer:
            writer.close()
        if rec_left:
            rec_left.close()
        if rec_right:
            rec_right.close()
        if rec_merged:
            rec_merged.close()
        left.close()
        right.close()


if __name__ == "__main__":
    main()
