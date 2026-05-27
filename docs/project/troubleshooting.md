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
| `common/motion_controller.py` | 运动控制器（定频发布/安全/闭环转向） |
| `common/motion_presets.py` | 微动预设与脚本解析 |
| `config/master_config.json` | Master AI 配置 |
| `backend/send_exec.py` | 命令行触发 exec（移动/预设/tts） |

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

### 检查 IMU（闭环转向用）

```bash
ros2 topic echo /aima/hal/imu/torso/state --qos-durability transient_local --qos-reliability reliable
ros2 topic echo /aima/hal/imu/chest/state --qos-durability transient_local --qos-reliability reliable
```

如果收不到 IMU，可在从机环境里尝试调整：

```bash
export MOTION_IMU_QOS_DURABILITY=transient_local
export MOTION_IMU_QOS_RELIABILITY=reliable
```

### 检查官方 MC 输入源是否注册成功（仅 `mc_locomotion`）

```bash
ros2 service list | grep SetMcInputSource
ros2 service list | grep GetCurrentInputSource
```

### 检查视频流

```bash
ffplay http://<机器人IP>:8000/stream.mjpg
```

如果你是“PC 双网卡/双网络”（机器人热点 + 正常局域网），其它设备无法直接访问 `192.168.88.88`，请改用 PC 后端代理：

```bash
ffplay "http://<PC_IP>:8765/proxy/robot?url=http%3A%2F%2F192.168.88.88%3A8000%2Fstream.mjpg"
```

如果出现“打开太多路视频把后端拖慢”，可降低并发或增大连接上限：

```bash
export MAX_PROXY_CONNECTIONS=40
```
