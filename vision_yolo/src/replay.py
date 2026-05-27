import argparse
import glob
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import cv2


def _expand_glob(path: str) -> List[str]:
    path = str(path or "").strip()
    if not path:
        return []
    if any(ch in path for ch in ["*", "?", "["]):
        return sorted(glob.glob(path))
    return [path]


def _load_jsonl_many(path_glob: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for path in _expand_glob(path_glob):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = (line or "").strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    return out


def _color_for(cls_id: int) -> Tuple[int, int, int]:
    # BGR
    v = int(cls_id) * 2654435761 & 0xFFFFFFFF
    return (int(v & 0xFF), int((v >> 8) & 0xFF), int((v >> 16) & 0xFF))


def _draw_dets(frame, dets: List[Dict[str, Any]], title: str = ""):
    if title:
        cv2.putText(frame, title, (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (240, 240, 240), 2, cv2.LINE_AA)
    for d in dets or []:
        try:
            cls_id = int(d.get("cls", -1))
            score = float(d.get("score", 0.0))
            x1, y1, x2, y2 = d.get("bbox", [0, 0, 0, 0])
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            c = _color_for(cls_id)
            cv2.rectangle(frame, (x1, y1), (x2, y2), c, 2)
            name = d.get("label") or d.get("name") or str(cls_id)
            label = f"{name}:{score:.2f}"
            cv2.putText(frame, label, (x1, max(16, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, c, 2, cv2.LINE_AA)
        except Exception:
            continue


@dataclass
class VisionIndex:
    left: Dict[int, Dict[str, Any]]
    right: Dict[int, Dict[str, Any]]


def build_index(rows: List[Dict[str, Any]]) -> VisionIndex:
    left: Dict[int, Dict[str, Any]] = {}
    right: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        if r.get("type") != "vision":
            continue
        payload = r.get("payload") or {}
        meta = payload.get("meta") or {}
        cam = str(meta.get("camera") or "").strip().lower()
        fi = meta.get("frame_index", None)
        if fi is None:
            continue
        try:
            fi = int(fi)
        except Exception:
            continue
        if cam == "left":
            left[fi] = r
        elif cam == "right":
            right[fi] = r
    return VisionIndex(left=left, right=right)


def parse_args():
    p = argparse.ArgumentParser(description="回放：视频 + vision jsonl 叠框（用于复盘/调参/训练前检查）")
    p.add_argument("--jsonl", type=str, required=True, help="dual_server 输出的 jsonl（含 meta.frame_index）")
    p.add_argument("--left-video", type=str, default="", help="左路录制视频（dual_server --record-left 输出）")
    p.add_argument("--right-video", type=str, default="", help="右路录制视频（dual_server --record-right 输出）")
    p.add_argument("--merged-video", type=str, default="", help="可选：左右拼接录制视频（dual_server --record-merged 输出）")
    p.add_argument("--out", type=str, default="", help="可选：导出叠框后的 merged mp4")
    p.add_argument("--max-frames", type=int, default=0, help="最多回放多少帧（0=不限）")
    p.add_argument("--show", action="store_true", help="是否弹窗显示（默认不显示，仅导出）")
    p.add_argument("--fps", type=float, default=0.0, help="导出/显示帧率（0=从视频读取，取不到则 10）")
    return p.parse_args()


def _open_cap(path: str) -> Optional[cv2.VideoCapture]:
    if not path:
        return None
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    return cap


class MultiVideoReader:
    def __init__(self, pattern: str):
        self.paths = _expand_glob(pattern)
        self.idx = -1
        self.cap: Optional[cv2.VideoCapture] = None
        self.open_next()

    def open_next(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self.idx += 1
        if self.idx >= len(self.paths):
            return False
        self.cap = cv2.VideoCapture(self.paths[self.idx])
        if not self.cap.isOpened():
            self.cap = None
            return self.open_next()
        return True

    def fps(self) -> float:
        if self.cap is None:
            return 0.0
        try:
            v = float(self.cap.get(cv2.CAP_PROP_FPS))
            return v if v > 1e-6 else 0.0
        except Exception:
            return 0.0

    def read(self):
        while True:
            if self.cap is None:
                return False, None
            ok, frame = self.cap.read()
            if ok:
                return True, frame
            if not self.open_next():
                return False, None

    def close(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None


def main():
    args = parse_args()
    rows = _load_jsonl_many(args.jsonl)
    idx = build_index(rows)

    vr_left = MultiVideoReader(args.left_video) if args.left_video else None
    vr_right = MultiVideoReader(args.right_video) if args.right_video else None
    vr_merged = MultiVideoReader(args.merged_video) if args.merged_video else None

    if not (vr_left and vr_left.paths) and not (vr_right and vr_right.paths) and not (vr_merged and vr_merged.paths):
        raise RuntimeError("至少提供一个视频：--left-video/--right-video/--merged-video")

    fps = float(args.fps or 0.0) or (vr_merged.fps() if vr_merged else 0.0) or (vr_left.fps() if vr_left else 0.0) or (vr_right.fps() if vr_right else 0.0) or 10.0
    out_writer = None
    if args.out:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        # 不要消耗 reader 的帧：单独 probe 第一段视频的首帧拿尺寸
        probe_path = ""
        if vr_merged and vr_merged.paths:
            probe_path = vr_merged.paths[0]
        elif vr_left and vr_left.paths:
            probe_path = vr_left.paths[0]
        elif vr_right and vr_right.paths:
            probe_path = vr_right.paths[0]
        cap_probe = cv2.VideoCapture(probe_path)
        ok, fr = cap_probe.read()
        cap_probe.release()
        if not ok:
            raise RuntimeError(f"无法读取视频首帧: {probe_path}")
        h, w = fr.shape[:2]
        out_writer = cv2.VideoWriter(args.out, fourcc, max(1.0, fps), (w, h))

    i = 0
    while True:
        if args.max_frames and i >= int(args.max_frames):
            break

        frame_out = None
        if vr_merged and vr_merged.paths:
            ok, frame = vr_merged.read()
            if not ok:
                break
            frame_out = frame
            # 拼接流没有区分左右，这里只叠加“按 frame_index”最近的两条（同 index）
            row_l = idx.left.get(i)
            row_r = idx.right.get(i)
            if row_l:
                _draw_dets(frame_out, (row_l.get("payload") or {}).get("dets") or [], title="left")
            if row_r:
                _draw_dets(frame_out, (row_r.get("payload") or {}).get("dets") or [], title="right")
        else:
            frame_l = None
            frame_r = None
            if vr_left and vr_left.paths:
                ok, frame_l = vr_left.read()
                if not ok:
                    break
                row_l = idx.left.get(i)
                if row_l:
                    meta = (row_l.get("payload") or {}).get("meta") or {}
                    title = f"left task={meta.get('task','')} fi={meta.get('frame_index',i)}"
                    _draw_dets(frame_l, (row_l.get("payload") or {}).get("dets") or [], title=title)
            if vr_right and vr_right.paths:
                ok, frame_r = vr_right.read()
                if not ok:
                    break
                row_r = idx.right.get(i)
                if row_r:
                    meta = (row_r.get("payload") or {}).get("meta") or {}
                    title = f"right task={meta.get('task','')} fi={meta.get('frame_index',i)}"
                    _draw_dets(frame_r, (row_r.get("payload") or {}).get("dets") or [], title=title)

            if frame_l is not None and frame_r is not None:
                h = max(frame_l.shape[0], frame_r.shape[0])
                w1 = int(frame_l.shape[1])
                w2 = int(frame_r.shape[1])
                lrs = cv2.resize(frame_l, (w1, h)) if frame_l.shape[0] != h else frame_l
                rrs = cv2.resize(frame_r, (w2, h)) if frame_r.shape[0] != h else frame_r
                frame_out = cv2.hconcat([lrs, rrs])
            else:
                frame_out = frame_l if frame_l is not None else frame_r

        if frame_out is None:
            break

        if out_writer is not None:
            out_writer.write(frame_out)

        if args.show:
            cv2.imshow("vision-replay", frame_out)
            if cv2.waitKey(int(1000 / max(1.0, fps))) & 0xFF == ord("q"):
                break

        i += 1

    if out_writer is not None:
        out_writer.release()
    if vr_left:
        vr_left.close()
    if vr_right:
        vr_right.close()
    if vr_merged:
        vr_merged.close()
    try:
        cv2.destroyAllWindows()
    except Exception:
        pass


if __name__ == "__main__":
    main()
