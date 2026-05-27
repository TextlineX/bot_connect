from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import time

try:
    import orjson as json_lib
except ImportError:
    import json as json_lib


@dataclass
class Detection:
    id: int
    cls: int
    label: Optional[str] = None
    score: float
    bbox: List[float]
    xywhn: Optional[List[float]] = None
    ts: Optional[float] = None


@dataclass
class Track:
    id: int
    cls: int
    score: float
    bbox: List[float]
    ts: Optional[float] = None


def vision_msg(robot_id: str, dets: List[Detection], tracks: Optional[List[Track]] = None, strategy: str = "top1",
               meta: Optional[Dict[str, Any]] = None) -> str:
    payload = {
        "dets": [asdict(d) for d in dets],
        "tracks": [asdict(t) for t in tracks] if tracks else [],
        "strategy": strategy,
        "meta": meta or {},
    }
    msg = {
        "type": "vision",
        "robot_id": robot_id,
        "ts": int(time.time() * 1000),
        "payload": payload,
    }
    return json_lib.dumps(msg).decode() if hasattr(json_lib, "dumps") and json_lib.__name__ == "orjson" else json_lib.dumps(msg, ensure_ascii=False)
