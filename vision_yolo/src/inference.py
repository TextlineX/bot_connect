from typing import List, Optional
import cv2
import numpy as np
import torch
from ultralytics import YOLO

from .schemas import Detection


class YoloDetector:
    def __init__(self, weight: str, device: str = "cuda", imgsz: int = 640, conf: float = 0.35,
                 classes: Optional[List[int]] = None):
        self.model = YOLO(weight)
        self.model.to(device)
        self.device = device
        self.imgsz = imgsz
        self.conf = conf
        self.classes = classes
        # ultralytics: model.names 可能是 dict 或 list
        self.names = getattr(self.model, "names", None)

    def infer(self, frame_bgr) -> List[Detection]:
        res = self.model.predict(
            frame_bgr,
            imgsz=self.imgsz,
            conf=self.conf,
            classes=self.classes,
            device=self.device,
            verbose=False,
        )[0]
        dets = []
        h, w = frame_bgr.shape[:2]
        for i, b in enumerate(res.boxes):
            x1, y1, x2, y2 = b.xyxy[0].tolist()
            cx = (x1 + x2) / 2 / w
            cy = (y1 + y2) / 2 / h
            bw = (x2 - x1) / w
            bh = (y2 - y1) / h
            cls_id = int(b.cls)
            label = None
            try:
                if isinstance(self.names, dict):
                    label = self.names.get(cls_id)
                elif isinstance(self.names, (list, tuple)):
                    label = self.names[cls_id] if 0 <= cls_id < len(self.names) else None
            except Exception:
                label = None
            dets.append(
                Detection(
                    id=i,
                    cls=cls_id,
                    label=str(label) if label else None,
                    score=float(b.conf),
                    bbox=[float(x1), float(y1), float(x2), float(y2)],
                    xywhn=[cx, cy, bw, bh],
                    ts=res.speed.get("inference", 0.0),
                )
            )
        return dets


def warmup(detector: YoloDetector, img_size: int = 640):
    dummy = np.zeros((img_size, img_size, 3), dtype=np.uint8)
    detector.infer(dummy)
