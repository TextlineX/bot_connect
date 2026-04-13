# 监控面板说明

## 页面概览

前端 `MonitorView.vue` 提供多路视频流监控。

## 视频流地址（当前默认 MJPEG）

```
MJPEG: http://<机器人IP>:8000/stream.mjpg
```

## 配置流地址

前端 Monitor 页面可填写机器人 IP + 端口，自动拼接 MJPEG 地址；留空时会使用机器人上报的 `auto_url/mjpeg_url`。

## 推流依赖

- `ffmpeg`
- ROS 摄像头话题
- 如需 MJPEG：`ffmpeg`（用于转码）
