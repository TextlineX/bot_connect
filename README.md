# Bot Connect 操作文档

## 目录结构
- backend/  
  Node WebSocket 服务器，负责路由消息、配置同步、音频桥接。
- frontend/ 
  Vue 控制台，区分 `master`（大脑）和 `slave`（控制端）目标。
- common/   
  通用模块：
  - ws_client.py：WebSocket 客户端封装
  - role_config.py：主从配置落盘与读取
  - tts_client.py：PlayTts 服务封装
- master/   
  主机执行逻辑（AI / ASR / 动作路由）。
- slave/    
  从机执行逻辑（控制 / TTS / 结果回传）。
- robot/
  统一机器人入口，依靠 `ROBOT_ROLE=master|slave` 切换模式。

机器人侧同步后路径示例：`/agibot/data/home/agi/bot_connect/...`

---
## 前后端栈与启动

### 后端 (Node，默认由 master 识别 ASR)
- 位置：backend/
- 依赖：`npm install`（首次）
- 运行：
  ```powershell
  cd H:\Project\Bot\bot_connect\backend
  # 如需后端本地识别，设置 MODEL_PATH 或 ASR_MODE=local；默认 ASR_MODE=master 由主机识别
  # set MODEL_PATH=H:\models\vosk-model-small-cn-0.22
  # set ASR_MODE=master | local | off
  node server.js                                       # 监听 ws://0.0.0.0:8765
  ```
- 需要本机可用 `ffmpeg`（用于 webm/mp3/ogg 等转码）。  
- WS_HOST / WS_PORT / AUTH_TOKEN 可选。
- 配置文件：`backend/config.json` 作为前端/后端/主从统一配置源，带 `version`。
- 行为：保存上传音频 -> ffmpeg 转 16k mono PCM；ASR 默认由 master 执行，后端仅转发；若设置 `MODEL_PATH` 则由后端本地 Vosk 识别并广播 `asr_text`。

#### 快速单文件测试
```powershell
set WS_URL=ws://192.168.31.170:8765
set ROBOT_ID=controller
python scripts\send_audio_ws.py test.wav   # 本地直连 WS 发送音频
```
或离线校验文件能否被识别：
```powershell
set MODEL_PATH=H:\models\vosk-model-small-cn-0.22
python scripts\test_asr_file.py backend\uploads\xxxx.raw --mime audio/pcm
```

### 前端 (Vue + Vite)
- 位置：frontend/
- 启动：
  ```powershell
  cd H:\Project\Bot\bot_connect\frontend
  npm install
  npm run dev -- --host --port 5173
  ```
- 浏览器：`http://<PC_IP>:5173`，WS 地址填 `ws://<PC_IP>:8765`。
- 功能：控制命令默认发给 `slave`，录音/ASR/AI 默认发给 `master`，并通过设置页统一同步配置。

---
## 机器人主机端

### 环境准备
```bash
source /opt/ros/humble/setup.bash
source /agibot/data/home/agi/aimdk/install/setup.bash
pip install websockets   # 如未装
```

### 统一机器人入口 (robot/client.py)
- 现在建议统一用 `robot/client.py` 启动，`ROBOT_ROLE=master|slave` 决定运行模式。
- `master/client.py` 和 `slave/client.py` 仍保留各自执行逻辑，但启动入口已统一。

### 主机客户端 (master/client.py)
- 行为：
  - 连接后端；负责 ASR / AI / 动作路由（ASR 使用 `MODEL_PATH` 指向的 Vosk 模型）。
  - 收到 `config_sync` 后会把主机配置落盘到 `config/master_config.json`。
  - 处理 exec.action==tts / action_router，将结果通过 `type: result` 回送前端。
- 运行：
```bash
cd /agibot/data/home/agi/bot_connect/master
source /opt/ros/humble/setup.bash
source /agibot/data/home/agi/aimdk/install/setup.bash
export WS_URL=ws://<PC_IP>:8765
export ROBOT_ID=master-01
export ROBOT_ROLE=master
export TTS_SERVICE=/aimdk_5Fmsgs/srv/PlayTts  # 如服务名不同替换
python ../robot/client.py
```

### Windows 一键模拟（仅 WS，不调用 ROS/TTS）
```powershell
cd H:\Project\Bot\bot_connect
.\scripts\start_master_sim.ps1   # 默认 WS_URL=ws://192.168.31.170:8765, ROBOT_ID=master-01
```
（需按需修改脚本里的默认地址）

### 通用模块 (common)
- ws_client.py：WebSocket 客户端封装。
- tts_client.py：封装 PlayTts 调用，支持环境变量 `TTS_SERVICE`。

### 可选 TTS 代理 (x2_bot/tts_proxy)
- 订阅 `/ws_bridge/tts_proxy`，调用 PlayTts。
- 构建/运行：
  ```bash
  cd ~/aimdk
  source /opt/ros/humble/setup.bash
  colcon build --packages-select x2_bot
  source install/setup.bash
  ros2 run x2_bot tts_proxy --ros-args -p tts_service:=/aimdk_5Fmsgs/srv/PlayTts
  ```
- 测试：`ros2 topic pub /ws_bridge/tts_proxy std_msgs/String "data: '你好，测试 TTS'" -1`

---
## 从机端 (可选示例)
```bash
cd /agibot/data/home/agi/bot_connect
source /opt/ros/humble/setup.bash
source /agibot/data/home/agi/aimdk/install/setup.bash
export WS_URL=ws://<PC_IP>:8765
export ROBOT_ID=slave-01
export ROBOT_ROLE=slave
# 默认会同时打开 MJPEG 视频流（mjpeg_http_server），如需关闭设 STREAM_ENABLE=0
export STREAM_ENABLE=1
python robot/client.py   # 或直接 ./scripts/start_slave.sh（默认 MJPEG 推流）
```

- 从机配置会落盘到 `config/slave_config.json`。

### 从机摄像头实时流（MJPEG HTTP，当前默认）
- 现阶段默认采用 MJPEG HTTP 推流（`STREAM_MODE=http_mjpeg`），不启用 RTSP / MediaMTX；浏览器可直接播放 `stream.mjpg`。
- 依赖：
  - Python：项目自带 `websockets`；脚本 `scripts/mjpeg_http_server.py`
  - 系统二进制：`ffmpeg`（用于转码为 MJPEG）
  - ROS 环境：`rclpy`、`sensor_msgs`（订阅压缩图像话题）
- 最小启动示例：
  ```bash
  cd /agibot/data/home/agi/bot_connect
  export ROBOT_ID=slave-01
  export ROBOT_ROLE=slave
  export STREAM_AUTOSTART=1
  export STREAM_MODE=http_mjpeg
  export STREAM_PUBLIC_HOST=<机器人IP>
  export STREAM_HTTP_PORT=8000          # 默认 8000
  export STREAM_TOPIC=/aima/hal/sensor/stereo_head_front_right/rgb_image/compressed
  python robot/client.py                # 或 ./scripts/start_slave.sh
  ```
- 访问地址：
  - MJPEG：`http://<机器人IP>:8000/stream.mjpg`
- 常用环境变量：
  - `STREAM_PUBLIC_HOST`：前端访问 MJPEG 时使用的 IP，建议显式设置
  - `STREAM_TOPIC`：相机话题
  - `STREAM_NAME`：流名称，默认与 `ROBOT_ID` 一致
  - `STREAM_HTTP_PORT`：MJPEG 端口，默认 `8000`
  - `STREAM_MODE`：默认 `http_mjpeg`；如后续恢复 RTSP，可改为 `rtsp`
- 前端监控页会优先读取机器人 `status.payload.streams` 上报的 `mjpeg_url/auto_url`；监控输入框留空时会自动显示默认 MJPEG 画面。
- 如需重新启用 RTSP/WebRTC/HLS，请部署 `mediamtx`，并将 `STREAM_MODE` 改为 `rtsp`，再参考脚本 `scripts/start_slave_camera_stream.sh`。

---
## 常见排查
- 后端日志出现 `target ... offline`：主机/从机未连接后端。
- 前端设置已保存但机器人没同步：检查 `config_sync` / `config_sync_ack` 是否出现，或查看 `backend/config.json` 的 `version` 是否递增。
- TTS failed/timeout：
  1) `ros2 service list | grep PlayTts` 是否有服务；
  2) `TTS_SERVICE` 是否匹配；
  3) 已 source ROS 环境。
- 前端连不上：确认 `node server.js` 在跑、Windows 防火墙放行 8765、`WS_URL` IP 正确。
- WebRTC 无画面：
  1) 先用 `ffplay http://<机器人IP>:8000/stream.mjpg` 确认 MJPEG 有画面；
  2) 确认 `STREAM_PUBLIC_HOST` 填的是前端机器能访问到的机器人 IP；
  3) 如果自定义端口，确认防火墙已放行对应 `STREAM_HTTP_PORT`；
  4) 若使用 RGB-D，相机订阅建议设置 `STREAM_QOS_RELIABILITY=reliable`。
