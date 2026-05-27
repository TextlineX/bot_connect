# PC 端部署

## 后端 (Node.js)

```powershell
cd H:\Project\Bot\bot_connect\backend
npm install
node server.js
```

默认监听 `ws://0.0.0.0:8765`（并在同端口提供 `http://0.0.0.0:8765/health`）。

如果你已构建前端（`frontend/dist` 存在），后端也会在 **同一个端口** 托管前端页面：

- 浏览器：`http://<PC_IP>:8765`
- WebSocket：`ws://<PC_IP>:8765`

**环境变量：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WS_HOST` | `0.0.0.0` | 监听地址 |
| `WS_PORT` | `8765` | 监听端口 |
| `AUTH_TOKEN` | — | 开启鉴权 |
| `MODEL_PATH` | — | Vosk 模型路径，开启本地 ASR |
| `PYTHON_BIN` | `python` | Python 解释器路径 |
| `FFMPEG_BIN` | `ffmpeg` | ffmpeg 路径 |
| `ROBOT_HOST` | `192.168.88.88` | 机器人热点侧 IP（用于视频/资源代理） |
| `MAX_PROXY_CONNECTIONS` | `20` | `/proxy/robot*` 最大并发连接数（避免被视频流拖垮） |

## 机器人热点侧资源代理（解决双网问题）

你的 PC 同时连接：

- 正常局域网（其它设备在这里）
- 机器人热点（`192.168.88.0/24`，机器人常见为 `192.168.88.88`，不上网）

其它设备无法直连 `http://192.168.88.88:xxxx/...`。本项目后端提供同源代理：

```text
http://<PC_IP>:8765/proxy/robot?url=<ENCODED_TARGET_URL>
```

例：

```text
http://<PC_IP>:8765/proxy/robot?url=http%3A%2F%2F192.168.88.88%3A8000%2Fstream.mjpg
```

更安全的写法（不用传完整 URL）：

```text
http://<PC_IP>:8765/proxy/robot/mjpg?port=8000&path=/stream.mjpg
```

监控面板会自动把 `192.168.88.88` 的 MJPEG 地址改成走代理（方便其它设备直接打开 `http://<PC_IP>:8765` 看视频/截图/录屏）。

## 前端 (Vue + Vite)

```powershell
cd H:\Project\Bot\bot_connect\frontend
npm install
npm run dev -- --host --port 5173
```

浏览器访问 `http://<PC_IP>:5173`。

## 一键启动

```powershell
cd H:\Project\Bot\bot_connect
.\scripts\start_relay.ps1 -ModelPath "H:\models\vosk-model-small-cn-0.22" -PythonBin "C:\Python314\python.exe" -WsPort 8765 -DevPort 5173
```

## Electron 客户端（可选）

解决浏览器 HTTP 环境下的音频 API 限制：

```powershell
cd H:\Project\Bot\bot_connect\frontend
npm install
npm run electron:dev
```

- `electron:dev` — 开发模式
- `electron:preview` — 预览已构建产物
- `electron:dist` — 打包 Windows 安装包（NSIS，产物在 `frontend\release\`）

### 打包 EXE（推荐）

```powershell
cd H:\Project\Bot\bot_connect\backend
npm install

cd H:\Project\Bot\bot_connect\frontend
npm install
npm run electron:dist
```

打包后的程序启动后会自动拉起后端，并加载 `http://127.0.0.1:8765/`；同一局域网的其他设备也能访问 `http://<PC_IP>:8765/`（记得放行防火墙端口）。

## 防火墙

确保 Windows 防火墙放行 **8765** 端口。

## 全模拟模式（无 ROS）

```powershell
# 后端 + 前端
.\scripts\start_relay.ps1 ...

# 主机模拟
$env:WS_URL="ws://<PC_IP>:8765"
$env:ROBOT_ID="master-01"
$env:SIM_MODE="1"
python H:\Project\Bot\bot_connect\master\client.py

# 从机模拟
$env:WS_URL="ws://<PC_IP>:8765"
$env:ROBOT_ID="slave-01"
python H:\Project\Bot\bot_connect\slave\client.py
```
