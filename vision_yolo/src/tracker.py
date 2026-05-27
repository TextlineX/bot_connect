from dataclasses import dataclass
from typing import List, Optional, Tuple

from .schemas import Detection, Track


class PassthroughTracker:
    def __init__(self):
        self.counter = 0

    def track(self, dets: List[Detection]) -> List[Track]:
        tracks = []
        for d in dets:
            self.counter += 1
            tracks.append(
                Track(
                    id=self.counter,
                    cls=d.cls,
                    score=d.score,
                    bbox=d.bbox,
                    ts=d.ts,
                )
            )
        return tracks


def _iou(a: List[float], b: List[float]) -> float:
    try:
        ax1, ay1, ax2, ay2 = [float(x) for x in a[:4]]
        bx1, by1, bx2, by2 = [float(x) for x in b[:4]]
    except Exception:
        return 0.0
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    if denom <= 0:
        return 0.0
    return float(inter / denom)


@dataclass
class _TrackState:
    id: int
    cls: int
    label: Optional[str]
    score: float
    bbox: List[float]
    hits: int = 0
    hit_streak: int = 0
    miss: int = 0
    confirmed: bool = False


class IouStabilizer:
    """
    轻量“去抖/稳定输出”：
    - 连续 min_hits 帧命中才输出（confirmed）
    - 短暂漏检 max_miss 帧内保持输出（避免闪烁）
    - 通过 IoU + cls 做匹配，track id 稳定
    """

    def __init__(
        self,
        *,
        iou_thresh: float = 0.5,
        min_hits: int = 2,
        max_miss: int = 2,
        smooth: float = 0.6,
    ):
        self.iou_thresh = float(iou_thresh)
        self.min_hits = max(1, int(min_hits))
        self.max_miss = max(0, int(max_miss))
        self.smooth = float(smooth)
        if self.smooth < 0:
            self.smooth = 0.0
        if self.smooth > 1:
            self.smooth = 1.0

        self._next_id = 1
        self._tracks: List[_TrackState] = []

    def reset(self):
        self._next_id = 1
        self._tracks = []

    def update(self, dets: List[Detection]) -> Tuple[List[Detection], List[Track]]:
        dets = dets or []
        tracks0 = self._tracks
        used_tracks = set()
        used_dets = set()

        # 生成候选匹配 (iou, ti, di)
        candidates: List[Tuple[float, int, int]] = []
        for ti, t in enumerate(tracks0):
            for di, d in enumerate(dets):
                if int(d.cls) != int(t.cls):
                    continue
                iou = _iou(t.bbox, d.bbox)
                if iou >= self.iou_thresh:
                    candidates.append((float(iou), ti, di))
        candidates.sort(key=lambda x: x[0], reverse=True)

        # 贪心匹配
        matches: List[Tuple[int, int]] = []
        for _, ti, di in candidates:
            if ti in used_tracks or di in used_dets:
                continue
            used_tracks.add(ti)
            used_dets.add(di)
            matches.append((ti, di))

        # 更新匹配到的 tracks
        for ti, di in matches:
            t = tracks0[ti]
            d = dets[di]
            t.hits += 1
            t.hit_streak += 1
            t.miss = 0
            t.score = float(d.score)
            if d.label:
                t.label = str(d.label)
            # bbox 平滑
            if self.smooth <= 0:
                t.bbox = list(d.bbox)
            elif self.smooth >= 1:
                t.bbox = [self.smooth * float(nb) + (1.0 - self.smooth) * float(ob) for ob, nb in zip(t.bbox, d.bbox)]
            else:
                alpha = self.smooth
                t.bbox = [alpha * float(nb) + (1.0 - alpha) * float(ob) for ob, nb in zip(t.bbox, d.bbox)]
            if not t.confirmed and t.hit_streak >= self.min_hits:
                t.confirmed = True

        # 未匹配到的 track -> miss（只处理旧 tracks0）
        alive: List[_TrackState] = []
        for ti, t in enumerate(tracks0):
            if ti in used_tracks:
                alive.append(t)
                continue
            t.miss += 1
            t.hit_streak = 0
            # 未确认的 track 一旦漏检就丢弃（避免噪声）
            if not t.confirmed:
                continue
            if t.miss <= self.max_miss:
                alive.append(t)
        self._tracks = alive

        # 未匹配到的 det -> 新 track（添加在 miss 处理之后）
        for di, d in enumerate(dets):
            if di in used_dets:
                continue
            self._tracks.append(
                _TrackState(
                    id=self._next_id,
                    cls=int(d.cls),
                    label=str(d.label) if d.label else None,
                    score=float(d.score),
                    bbox=list(d.bbox),
                    hits=1,
                    hit_streak=1,
                    miss=0,
                    confirmed=(self.min_hits <= 1),
                )
            )
            self._next_id += 1

        # 输出 confirmed tracks（含短暂 hold）
        stable_dets: List[Detection] = []
        stable_tracks: List[Track] = []
        for t in self._tracks:
            if not t.confirmed:
                continue
            stable_dets.append(
                Detection(
                    id=int(t.id),
                    cls=int(t.cls),
                    label=str(t.label) if t.label else None,
                    score=float(t.score),
                    bbox=list(t.bbox),
                    xywhn=None,
                    ts=None,
                )
            )
            stable_tracks.append(
                Track(
                    id=int(t.id),
                    cls=int(t.cls),
                    score=float(t.score),
                    bbox=list(t.bbox),
                    ts=None,
                )
            )
        return stable_dets, stable_tracks
