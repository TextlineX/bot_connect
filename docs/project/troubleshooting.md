# 目录与排查速查

## 关键目录

| 路径 | 说明 |
|------|------|
| `backend/server.js` | WebSocket 中转服务 |
| `frontend/src/views/` | 前端页面组件 |
| `master/handlers/` | Master 模块处理器 |
| `slave/client.py` | Slave 主逻辑 |
| `common/ws_client.py` | WebSocket 封装 |
| `common/action_presets.py` | 预设动作定义 |
| `config/master_config.json` | Master AI 配置 |

## 排查命令

### 检查后端是否运行

```bash
curl -s http://<PC_IP>:8765 || echo "后端未运行"
```

### 检查 WebSocket 连接

前端"日志"标签页查看 WS 消息，或：

```bash
# 在机器人上测试 WS 连接
python -c "import websockets; import asyncio; asyncio.run(websockets.connect('ws://<PC_IP>:8765'))"
```

### 检查 ROS 服务

```bash
ros2 service list | grep PlayTts
ros2 topic list | grep cmd_vel
```

### 检查视频流

```bash
ffplay http://<机器人IP>:8000/stream.mjpg
```
