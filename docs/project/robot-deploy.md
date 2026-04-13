# 机器人端部署

## 环境准备

```bash
source /opt/ros/humble/setup.bash
source /agibot/data/home/agi/aimdk/install/setup.bash
pip install websockets
```

## 主机 (Master)

```bash
cd /agibot/data/home/agi/bot_connect
export WS_URL=ws://<PC_IP>:8765
export ROBOT_ROLE=master
export ROBOT_ID=master-01
export TTS_SERVICE=/aimdk_5Fmsgs/srv/PlayTts
export SIM_MODE=0
python robot/client.py
```

## 从机 (Slave)

```bash
cd /agibot/data/home/agi/bot_connect
export WS_URL=ws://<PC_IP>:8765
export ROBOT_ROLE=slave
export ROBOT_ID=slave-01
export SIM_MODE=0
python robot/client.py
```

## 从机 + 摄像头推流

```bash
cd /agibot/data/home/agi/bot_connect
export WS_URL=ws://<PC_IP>:8765
export ROBOT_ROLE=slave
export ROBOT_ID=slave-01
export STREAM_AUTOSTART=1
export STREAM_MODE=http_mjpeg      # 当前默认 MJPEG
export STREAM_PUBLIC_HOST=<机器人IP>
export STREAM_TOPIC=/aima/hal/sensor/stereo_head_front_right/rgb_image/compressed
python robot/client.py
```

**推流地址：**

| 协议 | 地址 |
|------|------|
| MJPEG | `http://<机器人IP>:8000/stream.mjpg` |

## 常用相机话题

```bash
# 后视相机
STREAM_TOPIC=/aima/hal/sensor/rgb_head_rear/rgb_image/compressed

# RGB-D 彩图
STREAM_TOPIC=/aima/hal/sensor/rgbd_head_front/rgb_image/compressed
STREAM_QOS_RELIABILITY=reliable
```
