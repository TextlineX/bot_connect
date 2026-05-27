import argparse
import asyncio
import cv2
import websockets
import time

from .inference import YoloDetector, warmup
from .tracker import IouStabilizer, PassthroughTracker
from .schemas import vision_msg


def dump_json(obj):
    try:
        import orjson

        return orjson.dumps(obj).decode()
    except Exception:
        import json

        return json.dumps(obj, ensure_ascii=False)


async def stream(
    ws_url: str,
    source: str,
    detector: YoloDetector,
    robot_id: str,
    tracker: PassthroughTracker,
    ws_mode: str = "bot_connect",
    target_robot: str = "",
    stabilize: bool = True,
    min_hits: int = 2,
    max_miss: int = 2,
    iou_thresh: float = 0.5,
    smooth: float = 0.6,
):
    cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频源: {source}")
    post = IouStabilizer(iou_thresh=float(iou_thresh), min_hits=int(min_hits), max_miss=int(max_miss), smooth=float(smooth)) if stabilize else None
    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
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
            ok, frame = cap.read()
            if not ok:
                await asyncio.sleep(0.05)
                continue
            dets_raw = detector.infer(frame)
            if post:
                dets, tracks = post.update(dets_raw)
            else:
                dets = dets_raw
                tracks = tracker.track(dets)
            msg = vision_msg(
                robot_id=robot_id,
                dets=dets,
                tracks=tracks,
                meta={
                    "img_w": frame.shape[1],
                    "img_h": frame.shape[0],
                    "stabilize": bool(post is not None),
                    "min_hits": int(min_hits),
                    "max_miss": int(max_miss),
                    "iou_thresh": float(iou_thresh),
                    "smooth": float(smooth),
                },
            )
            if target_robot:
                try:
                    obj = msg
                    if isinstance(msg, str):
                        import json

                        obj = json.loads(msg)
                    if isinstance(obj, dict):
                        obj["target_robot"] = target_robot
                        msg = dump_json(obj)
                except Exception:
                    pass
            try:
                await ws.send(msg)
            except Exception:
                await asyncio.sleep(0.2)
                continue
            await asyncio.sleep(0)


def parse_args():
    p = argparse.ArgumentParser(description="YOLO vision WebSocket 推流")
    p.add_argument("--ws-url", type=str, required=True, help="WebSocket 目标，如 ws://127.0.0.1:8765")
    p.add_argument("--source", type=str, default="0", help="视频源：摄像头索引或 RTSP/文件路径")
    p.add_argument("--weight", type=str, default="models/yolov8n.pt")
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--conf", type=float, default=0.35)
    p.add_argument("--robot-id", type=str, default="vision-01")
    p.add_argument("--stabilize", type=int, default=1, help="检测结果去抖/稳定输出：1=开（默认），0=关")
    p.add_argument("--min-hits", type=int, default=2, help="连续命中多少帧后才输出（默认 2）")
    p.add_argument("--max-miss", type=int, default=2, help="最多允许漏检多少帧仍保持输出（默认 2）")
    p.add_argument("--iou-thresh", type=float, default=0.5, help="IoU 匹配阈值（默认 0.5）")
    p.add_argument("--smooth", type=float, default=0.6, help="bbox 平滑系数 0~1（默认 0.6）")
    p.add_argument(
        "--ws-mode",
        type=str,
        default="bot_connect",
        choices=["bot_connect", "raw"],
        help="bot_connect=先发 hello，再发消息；raw=直接发消息（兼容自建 WS）",
    )
    p.add_argument("--target-robot", type=str, default="", help="可选：走 bot_connect 转发到指定机器人（如 controller/master-01）")
    return p.parse_args()


def main():
    args = parse_args()
    detector = YoloDetector(args.weight, device=args.device, imgsz=args.imgsz, conf=args.conf)
    warmup(detector, img_size=args.imgsz)
    tracker = PassthroughTracker()
    asyncio.run(
        stream(
            args.ws_url,
            args.source,
            detector,
            args.robot_id,
            tracker,
            ws_mode=args.ws_mode,
            target_robot=args.target_robot,
            stabilize=bool(int(args.stabilize or 0) == 1),
            min_hits=int(args.min_hits or 2),
            max_miss=int(args.max_miss or 2),
            iou_thresh=float(args.iou_thresh or 0.5),
            smooth=float(args.smooth or 0.6),
        )
    )


if __name__ == "__main__":
    main()
