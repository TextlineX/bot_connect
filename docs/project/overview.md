# 总览与架构

## 系统架构

Bot Connect 是一个实时机器人控制与通信平台，采用 **主从（Master-Slave）架构**：

```
┌─────────────────────────────────────────────────────────────┐
│                    前端 (Vue 控制台)                        │
│              http://<PC_IP>:5173  (或 Electron)             │
└──────────────────────────┬──────────────────────────────────┘
                           │ WebSocket  (ws://<PC_IP>:8765)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  后端 (Node.js WS 中转)                      │
│                   backend/server.js                           │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────────┐  │
│  │ 音频转码    │  │ ASR 路由    │  │ 消息路由广播        │  │
│  │ (ffmpeg)    │  │ (Vosk/API) │  │ (config_sync)      │  │
│  └─────────────┘  └─────────────┘  └────────────────────┘  │
└──────────┬─────────────────────────────────┬────────────────┘
           │                                 │
           ▼                                 ▼
┌─────────────────────┐            ┌─────────────────────┐
│   Master (主机)      │  ◄──────► │   Slave (从机)       │
│   AI / ASR / TTS    │  WebSocket│   运动执行 / 视频流  │
└─────────────────────┘            └─────────────────────┘
           │                                 │
           ▼                                 ▼
      ROS 2 / AIMDK                    ROS 2 / AIMDK
      PlayTts Srv                      cmd_vel Topic
                                      摄像头 → MJPEG（HTTP）
```

## 角色说明

| 角色 | Robot ID | 职责 | 运行位置 |
|------|----------|------|----------|
| **Master** | `master-01` | 大脑：AI 指令解析、ASR、TTS、预设动作路由 | 机器人主机 |
| **Slave** | `slave-01` | 身体：cmd_vel 运动、TTS、摄像头推流 | 机器人从机/同一机器人 |
| **Controller** | `controller` | 前端控制台身份标识 | PC 浏览器 |

## 目录结构

```
bot_connect/
├── backend/              Node.js WebSocket 中转 + ASR
│   ├── server.js        主入口
│   ├── config.json       配置文件
│   ├── asr_worker.py     Vosk ASR worker
│   └── uploads/          上传音频存储
│
├── frontend/             Vue 3 前端控制台
│   ├── src/
│   │   ├── views/        页面组件（Dashboard/Control/TTS/ASR/...）
│   │   └── components/    公共组件（WebRTC 播放器等）
│   └── package.json
│
├── master/               Master 机器人客户端
│   ├── client.py         主入口
│   └── handlers/         模块化处理器
│       ├── ai_assistant.py    AI 解析
│       ├── action_router.py   动作路由
│       ├── audio_asr.py       ASR
│       ├── motion.py          运动
│       └── voice.py           TTS
│
├── slave/                Slave 机器人客户端
│   └── client.py         主入口（cmd_vel / TTS / 视频流）
│
├── common/               共享模块
│   ├── ws_client.py      WebSocket 封装
│   ├── action_presets.py 预设动作定义
│   ├── stream_info.py    视频流 URL 构造
│   └── ...
│
├── electron/             Electron 桌面客户端壳
│   ├── main.cjs          主进程
│   └── preload.cjs       安全桥接
│
└── scripts/              一键启动脚本
```

## 通信协议

### WebSocket 消息类型

**客户端 → 服务端：**
- `hello` — 连接注册
- `config_sync` — 配置同步
- `audio_upload` — 音频上传
- `cmd_vel` — 运动指令
- `exec` — 执行动作
- `status` — 状态上报

**服务端 → 客户端：**
- `ack` — 连接确认
- `asr_text` — ASR 识别结果
- `ai_result` — AI 处理结果
- `config_sync` — 配置下发
- `result` — 动作执行结果

### 动作类型

| 动作 | 说明 |
|------|------|
| `voice.tts` | 文字转语音播放 |
| `motion.move` | 线速度 + 角速度运动 |
| `motion.stop` | 停止运动 |
| `preset.run` | 执行预设动作（挥手/握手/敬礼等） |
