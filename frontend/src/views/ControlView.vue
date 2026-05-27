<template>
  <section class="grid">
    <article class="card">
      <div class="card-head">
        <h3>动作面板</h3>
        <span class="pill">官方映射</span>
      </div>
      <div class="actions">
        <div class="group">
          <div class="group-title">基础移动</div>
          <button class="btn dark small" v-for="a in moveActions" :key="a.label" @click="sendAction(a)">
            {{ a.label }}
          </button>
        </div>
        <div class="group">
          <div class="group-title">微动预设</div>
          <button class="btn dark small" v-for="a in macroActions" :key="a.label" @click="sendAction(a)">
            {{ a.label }}
          </button>
        </div>
        <div class="group">
          <div class="group-title">官方预设</div>
          <button class="btn dark small" v-for="a in presetActions" :key="a.label" @click="sendAction(a)">
            {{ a.label }}
          </button>
        </div>
      </div>
      <div class="hint">按钮 -> WS exec/cmd_vel，已与 master 动作路由官方预设对齐；如需再扩展可直接追加。</div>
    </article>

    <article class="card">
      <div class="card-head">
        <h3>运动控制</h3>
        <span class="pill">cmd_vel → {{ state.controlTargetRobot }}</span>
      </div>
      <div class="field duo">
        <div><label>线速度 (m/s)</label><input type="number" step="0.05" v-model.number="linear" /></div>
        <div><label>角速度 (rad/s)</label><input type="number" step="0.05" v-model.number="angular" /></div>
      </div>
      <button class="btn dark" style="width:100%;" @click="sendCmd" :disabled="!state.connected">发送 cmd_vel</button>
    </article>

    <article class="card">
      <div class="card-head">
        <h3>自定义 JSON</h3>
        <span class="pill muted">debug</span>
      </div>
      <textarea rows="6" v-model="customJson"></textarea>
      <button class="btn dark" style="margin-top:12px;width:100%;" @click="sendCustom" :disabled="!state.connected">发送</button>
    </article>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { useStore } from '../store'

const { state, send } = useStore()

const moveActions = [
  { label: '前进', payload: { linear: 0.2, angular: 0 } },
  { label: '后退', payload: { linear: -0.2, angular: 0 } },
  { label: '左转', payload: { linear: 0, angular: 0.3 } },
  { label: '右转', payload: { linear: 0, angular: -0.3 } },
  { label: '停止', payload: { action: 'motion.stop' } },
  { label: '急停', payload: { action: 'motion.estop' } },
  { label: '解除急停', payload: { action: 'motion.clear_estop' } },
]

// 自定义移动预设（由 slave 侧解析 preset/macro 字段执行定时移动）
const macroActions = [
  { label: '快走一步', payload: { action: 'motion.move', preset: 'step_fast' } },
  { label: '走一步', payload: { action: 'motion.move', preset: 'step' } },
  { label: '半步', payload: { action: 'motion.move', preset: 'half_step' } },
  { label: '走两步', payload: { action: 'motion.move', preset: 'step', repeat: 2 } },
  { label: '后退一步', payload: { action: 'motion.move', preset: 'step_back' } },
  { label: '后退半步', payload: { action: 'motion.move', preset: 'half_step_back' } },
  { label: '左移一步', payload: { action: 'motion.move', preset: 'strafe_left_step' } },
  { label: '右移一步', payload: { action: 'motion.move', preset: 'strafe_right_step' } },
  { label: '左转15°', payload: { action: 'motion.move', preset: 'turn_left_15' } },
  { label: '右转15°', payload: { action: 'motion.move', preset: 'turn_right_15' } },
  { label: '左转90°', payload: { action: 'motion.move', preset: 'turn_left_90' } },
  { label: '右转90°', payload: { action: 'motion.move', preset: 'turn_right_90' } },
]

// 官方/项目预设动作映射（含左右区分）
const presetActions = [
  { label: '挥手(右)', payload: { action: 'preset.run', name: 'wave', motion_id: 1002, area_id: 2 } },
  { label: '挥手(左)', payload: { action: 'preset.run', name: 'wave_left', motion_id: 1002, area_id: 1 } },
  { label: '握手(右)', payload: { action: 'preset.run', name: 'handshake', motion_id: 1003, area_id: 2 } },
  { label: '握手(左)', payload: { action: 'preset.run', name: 'handshake_left', motion_id: 1003, area_id: 1 } },
  { label: '举手(右)', payload: { action: 'preset.run', name: 'raise_hand', motion_id: 1001, area_id: 2 } },
  { label: '举手(左)', payload: { action: 'preset.run', name: 'raise_hand_left', motion_id: 1001, area_id: 1 } },
  { label: '飞吻(右)', payload: { action: 'preset.run', name: 'kiss', motion_id: 1004, area_id: 2 } },
  { label: '飞吻(左)', payload: { action: 'preset.run', name: 'kiss_left', motion_id: 1004, area_id: 1 } },
  { label: '敬礼(右)', payload: { action: 'preset.run', name: 'salute', motion_id: 1013, area_id: 2 } },
  { label: '敬礼(左)', payload: { action: 'preset.run', name: 'salute_left', motion_id: 1013, area_id: 1 } },
  { label: '鼓掌', payload: { action: 'preset.run', name: 'clap', motion_id: 3017, area_id: 11 } },
  { label: '加油', payload: { action: 'preset.run', name: 'cheer', motion_id: 3011, area_id: 11 } },
  { label: '鞠躬', payload: { action: 'preset.run', name: 'bow', motion_id: 3001, area_id: 11 } },
  { label: '跳舞', payload: { action: 'preset.run', name: 'dance', motion_id: 3007, area_id: 11 } },
]

const linear = ref(0.2)
const angular = ref(0.1)
const customJson = ref('{\n  "type": "ping",\n  "robot_id": "controller",\n  "ts": 0\n}')

function sendAction(a) {
  if (!state.connected) return
  if (a.payload.linear !== undefined) {
    send({
      type: 'cmd_vel',
      robot_id: state.robotId,
      target_robot: state.controlTargetRobot,
      payload: a.payload,
      ts: Date.now()/1000,
    })
  } else {
    send({
      type: 'exec',
      robot_id: state.robotId,
      target_robot: state.controlTargetRobot,
      payload: a.payload,
      ts: Date.now()/1000,
    })
  }
}

function sendCmd() {
  send({
    type: 'cmd_vel',
    robot_id: state.robotId,
    target_robot: state.controlTargetRobot,
    payload: { linear: Number(linear.value), angular: Number(angular.value) },
    ts: Date.now()/1000,
  })
}

function sendCustom() {
  try {
    const obj = JSON.parse(customJson.value)
    send(obj)
  } catch (e) {
    // ignore parse error; store logs "JSON 解析失败"?
  }
}
</script>

<style scoped>
.actions { display:flex; flex-wrap:wrap; gap:12px; }
.group { display:flex; flex-wrap:wrap; gap:10px; align-items:flex-start; }
.group-title { width:100%; font-size:13px; color:#666; font-weight:600; }
</style>
