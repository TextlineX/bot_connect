# 运动控制（可扩展模块）

本项目把“移动”做成了一个**可扩展的统一模块**：既支持连续速度控制，也支持“走一步/半步/小角度转向”等**微动预设**与**分段脚本**，方便你后续逐步增强到更真实的步态与闭环控制。

---

## 1. 两种运动输出通道

从机（`slave/client.py`）内部通过 `common/motion_controller.py` 输出运动指令，支持两种通道：

- `cmd_vel`（默认）：发布 `geometry_msgs/msg/Twist` 到 `/cmd_vel`
- `mc_locomotion`（真机推荐）：发布 `aimdk_msgs/msg/McLocomotionVelocity` 到 `/aima/mc/locomotion/velocity`，并自动尝试注册输入源（`/aimdk_5Fmsgs/srv/SetMcInputSource`）

切换方式（从机环境变量）：

```bash
export MOTION_TRANSPORT=cmd_vel        # 默认
# 或：
export MOTION_TRANSPORT=mc_locomotion  # 走官方 MC 走跑话题
```

---

## 2. 你可以怎么“下发移动”

### 2.1 连续速度控制（WS `cmd_vel`）

前端“运动控制”面板发送：

```json
{
  "type": "cmd_vel",
  "target_robot": "slave-01",
  "payload": { "linear": 0.2, "lateral": 0.0, "angular": 0.3 }
}
```

从机会**定频持续发布**该速度，但有 **deadman 超时**：超过 `MOTION_CMD_TIMEOUT_SEC` 未收到新指令会自动刹停（默认 1 秒）。

### 2.2 微动预设（WS `exec` + `motion.move`）

微动预设由从机解析执行（见 `common/motion_presets.py`），例如：

```json
{
  "type": "exec",
  "target_robot": "slave-01",
  "payload": { "action": "motion.move", "preset": "step" }
}
```

常见预设键（可自行扩展）：

<!-- MOTION_PRESETS_START -->
> 本段由 `scripts/gen_motion_presets_doc.py` 自动生成，请勿手改。

| preset | 中文 | linear | lateral | angular | duration | angle_deg | pause_after |
|---|---|---:|---:|---:|---:|---:|---:|
| `half_step` | 半步 | 0.25 | 0 | 0 | 0.28 |  | 0.12 |
| `half_step_back` | 后退半步 | -0.22 | 0 | 0 | 0.28 |  | 0.12 |
| `step` | 走一步 | 0.25 | 0 | 0 | 0.55 |  | 0.15 |
| `step_back` | 后退一步 | -0.22 | 0 | 0 | 0.55 |  | 0.15 |
| `step_fast` | 快走一步 | 0.35 | 0 | 0 | 0.45 |  | 0.15 |
| `strafe_left_half` | 左移半步 | 0 | 0.25 | 0 | 0.28 |  | 0.1 |
| `strafe_left_step` | 左移一步 | 0 | 0.25 | 0 | 0.55 |  | 0.12 |
| `strafe_right_half` | 右移半步 | 0 | -0.25 | 0 | 0.28 |  | 0.1 |
| `strafe_right_step` | 右移一步 | 0 | -0.25 | 0 | 0.55 |  | 0.12 |
| `turn_left_15` | 左转15° | 0 | 0 | 0.9 |  | 15 | 0.15 |
| `turn_left_30` | 左转30° | 0 | 0 | 0.9 |  | 30 | 0.15 |
| `turn_left_90` | 左转90° | 0 | 0 | 1 |  | 90 | 0.2 |
| `turn_right_15` | 右转15° | 0 | 0 | -0.9 |  | 15 | 0.15 |
| `turn_right_30` | 右转30° | 0 | 0 | -0.9 |  | 30 | 0.15 |
| `turn_right_90` | 右转90° | 0 | 0 | -1 |  | 90 | 0.2 |

**常用中文别名（节选）**

- `走一步` → `step`
- `快走一步` → `step_fast`
- `半步` → `half_step`
- `后退一步` → `step_back`
- `左移一步` → `strafe_left_step`
- `右移一步` → `strafe_right_step`
<!-- MOTION_PRESETS_END -->

支持重复：

```json
{ "action": "motion.move", "preset": "step", "repeat": 2 }
```

### 2.3 分段脚本（高级）

当你想要更“像人”的动作（比如 起步→保持→收步→停顿），可以直接发脚本：

```json
{
  "type": "exec",
  "target_robot": "slave-01",
  "payload": {
    "action": "motion.move",
    "label": "右转两下",
    "script": [
      { "angular": -0.9, "duration": 0.25, "angle_rad": -0.26 },
      { "angular": 0.0, "duration": 0.15 },
      { "angular": -0.9, "duration": 0.25, "angle_rad": -0.26 }
    ]
  }
}
```

说明：
- `duration` 必填（每段持续多久）
- `angle_rad` 可选（仅转向段使用，配合闭环转向）

### 2.4 急停（E-Stop）

从机支持“急停锁”，一旦进入急停态会**立即输出 0 速度**，并拒绝后续 `motion.move/cmd_vel`，直到你显式解除。

```json
{ "type": "exec", "target_robot": "slave-01", "payload": { "action": "motion.estop", "reason": "manual" } }
```

解除：

```json
{ "type": "exec", "target_robot": "slave-01", "payload": { "action": "motion.clear_estop" } }
```

---

## 3. 闭环转向（IMU yaw）

转向类预设（如 `turn_left_15`）会携带目标转角，控制器会尽量按 **IMU yaw** 达到目标角度后提前停止；若 IMU 无数据/长时间不更新，会自动回退按 `duration` 切段。

相关环境变量：

```bash
export MOTION_CLOSED_LOOP_TURN=1
export MOTION_IMU_TOPIC=/aima/hal/imu/torso/state   # 或 chest/state

# IMU QoS（遇到收不到 IMU 时再调）
export MOTION_IMU_QOS_RELIABILITY=reliable          # 或 best_effort
export MOTION_IMU_QOS_DURABILITY=volatile           # 或 transient_local
export MOTION_IMU_QOS_DEPTH=10
```

---

## 4. 安全与调参（强烈建议认真看）

以下都在从机环境变量中可调（`common/motion_controller.py`）：

- deadman：`MOTION_CMD_TIMEOUT_SEC`（默认 1.0）
- 发布频率：`MOTION_PUB_HZ`（`mc_locomotion` 默认 50Hz，`cmd_vel` 默认 20Hz）
- 限速：`MOTION_MAX_LINEAR` / `MOTION_MAX_LATERAL` / `MOTION_MAX_ANGULAR`
- 斜坡（最大加速度）：`MOTION_MAX_ACCEL_LINEAR` / `MOTION_MAX_ACCEL_LATERAL` / `MOTION_MAX_ACCEL_ANGULAR`

建议流程：
1) 先在空旷环境用很小的速度/很短的 duration 测试。
2) 再逐步调大 `linear/angular` 与预设的 `duration/pause_after`。
3) 真机走官方 MC 时，确保输入源注册成功（见下节排查）。

---

## 5. 排查

### 5.1 看从机上报的运动状态

前端监控/日志中查看 `status.payload.motion.controller`，重点关注：

- `transport`：当前输出通道
- `mc.registered / mc.last_register_error`：官方 MC 输入源注册是否成功
- `feedback.yaw / yaw_age_sec`：IMU 是否有更新
- `script.active/index`：脚本是否在跑

### 5.2 不开前端直接触发预设

```bash
export WS_URL=ws://<PC_IP>:8765
export TARGET=slave-01
export PRESET=turn_left_15
python backend/send_exec.py
```

---

## 6. 人机协同建议（视频 + 移动）

如果你在构思“人机协同”（人看监控 + 机器人动作 + YOLO 感知），推荐把视频流按用途拆开：

- **人看/录制**：前端监控页把左右双目**合并成一个画面**（便于监控面板展示、截图、录屏）
- **算法输入**：左右原始流分别接入两路 YOLO（例如：一路做机器人动作识别，一路做物体识别）
- **后视**：单独一路（用于安全观察、倒退辅助）

前端的“左右合并”是纯前端 Canvas 合成，不影响你后续单独接入左右原始流做算法。
