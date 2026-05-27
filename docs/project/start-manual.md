# 启动手册

本文档用于本地开发、联调和截图展示。默认使用本机地址，避免把内网配置直接写进公开文档。

## 快速启动

### 1. 启动后端

```powershell
cd H:\Project\Bot\bot_connect\backend
npm install
node server.js
```

默认监听 `ws://127.0.0.1:8765`。

### 2. 启动前端

```powershell
cd H:\Project\Bot\bot_connect\frontend
npm install
npm run dev -- --host --port 5173
```

浏览器打开 `http://127.0.0.1:5173`。

### 3. 启动主机模拟

```powershell
cd H:\Project\Bot\bot_connect
.\scripts\start_master_sim.ps1
```

如果需要同时启动更多服务，可以使用：

```powershell
.\scripts\start_full_stack.ps1
```

## 截图前检查

- 前端能打开并正常显示控制台页面。
- 后端终端中能看到连接和消息日志。
- 设置页里的 WebSocket 地址与机器人 ID 正确。
- 如果要展示视频流，先确认监控页能拉到画面。
- 如果要展示动作控制，确认模拟客户端已连接。

## 常见问题

| 问题 | 常见原因 | 处理方式 |
|------|----------|----------|
| 前端打不开 | 端口被占用或依赖未装 | 检查 `npm install` 和端口 `5173` |
| 后端连不上 | WS 地址配置不一致 | 确认前端设置中的 WS 地址 |
| 机器人不在线 | 模拟客户端没启动 | 先运行 `start_master_sim.ps1` |
| 视频流无画面 | 流地址或服务未启动 | 先检查监控页和流服务 |

