# 视觉（Vision YOLO，独立项目）

本项目推荐把“视觉推理（YOLO）”先做成**独立服务**（好调试/好替换/不耦合机器人端），后续再按需要封装进 master 模块。

独立子项目位置：`vision_yolo/`

---

## 1. 推荐架构（与你当前目标最匹配）

你 PC 同时连接：

- 正常局域网（其它设备在这里）
- 机器人热点（通常 `192.168.88.88`，不上网）

推荐做法：

1) PC 上跑 `vision_yolo`（有 GPU 更好）  
2) `vision_yolo` 从 PC 后端代理读取机器人热点侧视频（避免直连 `192.168.88.88`）  
3) `vision_yolo` 把 `type=vision` 结果推送回 `bot_connect` 后端（WebSocket）  
4) 前端监控页可叠框显示（人看/录屏），master 后续可根据 vision 决策动作

---

## 2. 双路（左右双目）+ 两套 YOLO

推荐：左右双目两路原始流分别跑推理，“左右合并”只用于人看监控。

在 `vision_yolo/` 下：

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

启动双路（例子里把结果转发给 `controller`，便于你在前端日志/叠框里直接看到）：

```bash
python -m src.dual_server ^
  --ws-url ws://<PC_IP>:8765 ^
  --ws-mode bot_connect ^
  --target-robot controller ^
  --left-source "<LEFT_URL>" ^
  --right-source "<RIGHT_URL>" ^
  --left-weight yolov8n.pt ^
  --right-weight yolov8n.pt ^
  --left-task action ^
  --right-task object ^
  --fps 10 ^
  --sync-ms 80 ^
  --stabilize 1
```

### 2.1 双网场景建议用代理 URL

如果真实视频源在机器人热点侧（`192.168.88.88`），建议直接写成：

```text
http://<PC_IP>:8765/proxy/robot?url=<ENCODED_TARGET_URL>
```

或者（更安全）：

```text
http://<PC_IP>:8765/proxy/robot/mjpg?port=8000&path=/stream.mjpg
```

---

## 3. 去抖（稳定输出）

`dual_server` 默认开启“去抖/稳定输出”，用于减少闪烁：

- 连续 `--min-hits` 帧命中才输出（默认 2）
- 漏检 `--max-miss` 帧内继续保持输出（默认 2）
- 用 IoU 做匹配（`--iou-thresh`，默认 0.5），并对 bbox 做平滑（`--smooth`，默认 0.6）

如果你想看“原始结果”（会更抖），可关闭：

```bash
--stabilize 0
```

---

## 4. 落盘与回放（强烈建议）

为了后续做标注/复盘/训练，建议同时落盘：

- `--out-jsonl runs/vision.jsonl`（每条 vision 一行）
- `--record-left/right/merged runs/*.mp4`（推理时实际用到的帧）
- 长时间跑建议 `--segment-sec 600` 自动分段

回放叠框：

```bash
python -m src.replay --jsonl runs/vision*.jsonl --left-video runs/left*.mp4 --right-video runs/right*.mp4 --out runs/annotated.mp4
```

---

## 5. 前端叠框约定

监控页默认取这两路进行叠框：

- `meta.task=action, meta.camera=left`
- `meta.task=object, meta.camera=right`

你后面换成 pose/动作模型也不需要改前端，只要保持 `task/camera` 约定即可。

