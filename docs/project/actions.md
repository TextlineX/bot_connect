# 动作测试与映射

## 预设动作列表

| 动作名 | 中文 | motion_id | area_id |
|--------|------|-----------|---------|
| `wave` | 右手挥手 | 1002 | 2 |
| `wave_left` | 左手挥手 | 1002 | 1 |
| `handshake` | 右手握手 | 1003 | 2 |
| `handshake_left` | 左手握手 | 1003 | 1 |
| `raise_hand` | 右手举手 | 1001 | 2 |
| `raise_hand_left` | 左手举手 | 1001 | 1 |
| `kiss` | 右手飞吻 | 1004 | 2 |
| `kiss_left` | 左手飞吻 | 1004 | 1 |
| `salute` | 右手敬礼 | 1013 | 2 |
| `salute_left` | 左手敬礼 | 1013 | 1 |
| `clap` | 鼓掌 | 3017 | 11 |
| `cheer` | 加油 | 3011 | 11 |
| `bow` | 鞠躬 | 3001 | 11 |
| `dance` | 动感光波 | 3007 | 11 |

## 测试脚本

```bash
cd H:\Project\Bot\bot_connect
python scripts/test_actions.py
```

## 移动预设（微动）

移动预设用于“走一步/半步/小角度转向/侧移”等开环微动，便于后续叠加闭环与更复杂的步态控制。

触发方式（WS exec）：

```json
{
  "type": "exec",
  "target_robot": "slave-01",
  "payload": { "action": "motion.move", "preset": "step", "repeat": 2 }
}
```

更多说明与可用预设键见：[`/project/motion`](/project/motion)

## 急停（E-Stop）

从机支持“急停锁”：进入急停态后会拒绝后续 `motion.move/cmd_vel`，直到显式解除。

```json
{
  "type": "exec",
  "target_robot": "slave-01",
  "payload": { "action": "motion.estop", "reason": "manual" }
}
```

解除：

```json
{
  "type": "exec",
  "target_robot": "slave-01",
  "payload": { "action": "motion.clear_estop" }
}
```

## 动作执行流程

```
Controller → exec{action:"preset.run", payload:{name:"wave"}} → Backend → Master
                                                                        ↓
                                                              preset_motion_client
                                                                        ↓
                                                                   ROS 动作执行
```
