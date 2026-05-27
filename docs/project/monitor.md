# 监控面板说明

## 页面概览

前端 `MonitorView.vue` 提供“监控面板式”的多路视频流监控：

- 左右双目合并展示（便于人看/录屏/截图）
- 后视单路
- 从机上报的流 presets 一键填充
- 可选：叠加 `vision_yolo` 推送的检测框（YOLO 结果）

## 视频流地址（推荐 MJPEG）

基础形态：

```text
MJPEG: http://<机器人IP>:8000/stream.mjpg
```

如果你是 **PC 双网**（PC 同时连机器人热点 + 正常局域网），其它设备无法访问 `192.168.88.88`，请使用 **PC 后端同源代理**：

```text
http://<PC_IP>:8765/proxy/robot?url=http%3A%2F%2F192.168.88.88%3A8000%2Fstream.mjpg
```

更安全的写法（不用传完整 URL）：

```text
http://<PC_IP>:8765/proxy/robot/mjpg?port=8000&path=/stream.mjpg
```

监控页会自动把指向 `192.168.88.88` 的 MJPEG 地址改写为代理地址，方便其它设备直接访问 `http://<PC_IP>:8765`。

## 推流依赖

- `ffmpeg`
- ROS 摄像头话题
- 如需 MJPEG：可用本项目的 `scripts/mjpeg_http_server.py`（已开启 CORS，支持截图/录屏）

## 截图/录屏

监控面板里的每个画面都支持：

- 截图（PNG）
- 录屏（WebM）

注意：截图/录屏依赖 MJPEG 服务端开启 CORS；本项目自带的 `scripts/mjpeg_http_server.py` 已开启。

## 叠框（Vision）

当你运行 `vision_yolo` 并向后端推送 `type=vision` 消息后，监控页支持在画面上叠加检测框：

- `action|left` → 叠在左半画面
- `object|right` → 叠在右半画面

并可在 “Vision 调试” 卡片中调整叠框阈值（score）。
