# Master 模块能力清单

## 模块列表

| 模块 | 功能 |
|------|------|
| `ai_assistant` | AI 指令解析（接入 MiniMax/Anthropic 兼容 API） |
| `action_router` | 动作统一路由（tts/move/stop/preset） |
| `audio_asr` | ASR 音频识别结果处理 |
| `motion` | 运动控制（支持 cmd_vel / 官方 MC、微动预设、脚本、IMU 闭环转向） |
| `voice` | TTS 语音播报 |
| （外部）`vision_yolo` | 视觉推理独立服务（双路 YOLO、去抖、落盘/回放），详见[视觉](/project/vision) |

## AI 配置

AI 配置位于 `config/master_config.json`：

```json
{
  "ai": {
    "enabled": true,
    "auto_tts": true,
    "forward_action_to_slave": true,
    "forward_action_target": "slave-01",
    "provider": "anthropic_compatible",
    "api_base": "https://api.minimaxi.com/anthropic",
    "model": "MiniMax-M2",
    "temperature": 0.2
  }
}
```

## 模块注册

模块通过 `MasterContext` 上下文共享状态，通过 `registry.py` 的 `build_modules()` 统一注册。
