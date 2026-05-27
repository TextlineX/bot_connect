# Vision YOLO 模块（独立子项目）

## 目标
- 独立跑 YOLO 推理与目标追踪，输出标准化的 `VisionMsg`。
- 通过 WebSocket 将检测/追踪结果推送给主机（master）或被主动拉取。
- 保持纯 Python，后续可换成 TensorRT/ONNX/NCNN 版本而不改接口。

## 目录
- `requirements.txt`：默认依赖（CPU/GPU 通用）。如需 TensorRT 可自行替换为 `tensorrt`/`onnxruntime-gpu` 等。
- `models/`：权重文件（示例：`yolov8n.pt`、`best.engine`）。
- `src/`
  - `inference.py`：YOLO 加载与推理接口。
  - `tracker.py`：可选追踪器封装（ByteTrack/OC-SORT 占位）。
  - `calib.py`：像素坐标到机器人坐标系转换。
  - `schemas.py`：数据结构定义与序列化。
  - `server.py`：WebSocket 推送服务，读取相机/RTSP → 推理 → 发送 `VisionMsg`。

## 快速开始
```bash
cd vision_yolo
python -m venv .venv
.\.venv\Scripts\activate     # Windows，Linux 用 source .venv/bin/activate
pip install -r requirements.txt
python -m src.server --ws-url ws://127.0.0.1:8765 --source 0 --weight models/yolov8n.pt --ws-mode bot_connect --target-robot controller
```

## 双路（左右双目）+ 两套 YOLO（动作/物体分开）

适合你现在的思路：**先独立跑、便于调试**，后面再封装成模块。

```bash
cd vision_yolo
.\.venv\Scripts\activate

# 推送到 bot_connect 后端（会先发 hello，再发 vision 消息）
# 你可以先把 target_robot 指向 controller，让前端日志里能看到 vision 消息。
python -m src.dual_server ^
  --ws-url ws://<PC_IP>:8765 ^
  --ws-mode bot_connect ^
  --target-robot controller ^
  --left-source "http://<PC_IP>:8765/proxy/robot?url=http%3A%2F%2F192.168.88.88%3A8000%2Fstereo_left.mjpg" ^
  --right-source "http://<PC_IP>:8765/proxy/robot?url=http%3A%2F%2F192.168.88.88%3A8000%2Fstereo_right.mjpg" ^
  --left-weight models/action.pt ^
  --right-weight models/object.pt ^
  --left-task action ^
  --right-task object ^
  --fps 10 ^
  --sync-ms 80 ^
  --stabilize 1 ^
  --out-jsonl runs/vision_dual.jsonl ^
  --record-left runs/left.mp4 ^
  --record-right runs/right.mp4 ^
  --record-merged runs/merged.mp4
```

提示：
- **算法建议吃左右两路原始流**；“左右合并”只用于人看监控/录屏，不建议把合并大图再喂 YOLO。
- 如果运行 YOLO 的设备不在机器人热点网段，用 `http://<PC_IP>:8765/proxy/robot?...` 这种同源代理地址就行。
- `--out-jsonl` 会把每条 vision 消息落盘（jsonl），便于你后面做回放/标注/训练。
- `--record-left/--record-right/--record-merged` 会录制“推理时实际用到的帧”，配合回放脚本能做到叠框复盘。
- `--segment-sec 600` 可让 jsonl/mp4 每 10 分钟分一段（文件名自动追加 `_part0001`），适合长时间跑。
- 检测结果现在会带 `label`（类别名）；前端叠框/回放会优先显示 `label`，没有则显示 `cls` 数字。
- 默认开启“去抖/稳定输出”：连续 `--min-hits` 帧命中才输出，短暂漏检 `--max-miss` 帧内保持输出（避免闪烁）。要看原始结果可加 `--stabilize 0`。

## 回放（叠框复盘）

```bash
cd vision_yolo
.\.venv\Scripts\activate

# 直接弹窗看（按 q 退出）
python -m src.replay --jsonl runs/vision_dual.jsonl --left-video runs/left.mp4 --right-video runs/right.mp4 --show

# 或导出叠框后的 merged 视频
python -m src.replay --jsonl runs/vision_dual.jsonl --left-video runs/left.mp4 --right-video runs/right.mp4 --out runs/annotated.mp4

# 如果你启用了分段（_part0001），回放支持通配符：
python -m src.replay --jsonl "runs/vision_dual_part*.jsonl" --left-video "runs/left_part*.mp4" --right-video "runs/right_part*.mp4" --out runs/annotated.mp4
```

## 消息格式
- `VisionMsg`（JSON）
```json
{
  "type": "vision",
  "robot_id": "vision-01",
  "ts": 1710000000000,
  "payload": {
    "dets": [
      {"id": 3, "cls": 0, "score": 0.91, "bbox": [x1,y1,x2,y2], "xywhn": [cx,cy,w,h]},
      ...
    ],
    "tracks": [
      {"id": 7, "cls": 1, "score": 0.88, "bbox": [...], "ts": 1710000000123}
    ],
    "strategy": "top1",
    "meta": {"img_w": 640, "img_h": 480}
  }
}
```
- 坐标转换：在主机侧或本模块调用 `calib.pixel_to_robot(det)` 得到 `{x,y,z,rz}`。

## 对接建议
1) 在 master 上新增 `type == "vision"` 分支，读取 `payload.dets/ tracks`，完成任务选择后调用现有 `exec` 下发给 slave。  
2) 若需要主动拉取，可在 master 建立到 vision 模块的 WS 连接，直接收流。  
3) 若需要分布式：vision 模块运行在从机旁边，主机只收 JSON，不耦合摄像头驱动。

## TODO（留给后续）
- tracker 集成 ByteTrack/OC-SORT。
- TensorRT/ONNX 版本加载。
- 深度/标定自动化校验脚本。
