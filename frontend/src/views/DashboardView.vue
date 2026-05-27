<template>
  <section class="status-stage">
    <article v-if="!state.connected" class="card status-landing">
      <div class="status-landing-inner">
        <div>
          <div class="eyebrow">REALTIME TELEMETRY</div>
          <h2>主机 / 从机状态总览</h2>
          <p class="lead">
            连接后自动显示主机和从机的实时状态、能力、模块链路、动作执行与本地模拟传感器摘要。
          </p>
        </div>
        <div class="status-landing-actions">
          <button class="btn dark" @click="connect" :disabled="state.connected">连接</button>
          <button class="btn ghost" @click="showAdvanced = !showAdvanced">
            {{ showAdvanced ? '收起连接设置' : '展开连接设置' }}
          </button>
        </div>
        <div v-if="lastConnectHint" class="hint" style="max-width:820px;">
          {{ lastConnectHint }}
        </div>
        <div class="hint" style="max-width:820px;">
          debug: connected={{ state.connected }} wsUrl={{ state.wsUrl || '(empty)' }} robotId={{ state.robotId }} brain={{ state.brainTargetRobot }} control={{ state.controlTargetRobot }}
        </div>
        <div v-if="showAdvanced" class="card status-advanced">
          <div class="field">
            <label>WebSocket 地址</label>
            <input v-model="state.wsUrl" :placeholder="defaultWs" />
          </div>
          <div class="field">
            <label>快速选择</label>
            <select v-model="state.wsUrl">
              <option v-for="p in presets" :key="p.value" :value="p.value">{{ p.label }}</option>
            </select>
          </div>
          <div class="field duo">
            <div><label>本端 robot_id</label><input v-model="state.robotId" placeholder="controller" /></div>
            <div><label>大脑 master</label><input v-model="state.brainTargetRobot" placeholder="master-01" /></div>
          </div>
          <div class="field">
            <label>控制 slave</label>
            <input v-model="state.controlTargetRobot" placeholder="slave-01" />
          </div>
          <div class="field">
            <label><input type="checkbox" v-model="state.autoReconnect" /> 自动重连</label>
          </div>
          <div class="hint">WSL 访问宿主请用 172.19.0.1；浏览器本机用 127.0.0.1。</div>
        </div>
      </div>
    </article>

    <template v-else>
      <article class="card status-hero">
        <div class="status-hero-copy">
          <div class="eyebrow">LOCAL OPS CENTER</div>
          <h2>本地联调状态总台</h2>
          <p class="lead">
            已连接后端中继，当前面板会实时汇总主机与从机上报的状态、模块能力、运动动作、音频链路和 AI 结果。
          </p>
        </div>
        <div class="status-summary">
          <div class="summary-item">
            <span class="summary-label">连接</span>
            <strong>{{ state.connected ? '已连接' : '未连接' }}</strong>
          </div>
          <div class="summary-item">
            <span class="summary-label">在线机器人</span>
            <strong>{{ onlineCount }}</strong>
          </div>
          <div class="summary-item">
            <span class="summary-label">主机在线</span>
            <strong>{{ masterCount }}</strong>
          </div>
          <div class="summary-item">
            <span class="summary-label">从机在线</span>
            <strong>{{ slaveCount }}</strong>
          </div>
          <div class="summary-item wide">
            <span class="summary-label">最近 ASR</span>
            <strong>{{ lastAsr }}</strong>
          </div>
          <div class="summary-item wide">
            <span class="summary-label">最近 AI</span>
            <strong>{{ lastAi }}</strong>
          </div>
        </div>
      </article>

      <section class="status-columns">
        <div class="status-column">
          <div class="section-head">
            <div>
              <div class="eyebrow">MASTER</div>
              <h3>主机状态</h3>
            </div>
            <span class="pill" :class="masterCount ? 'accent' : ''">
              {{ masterCount ? `${masterCount} 台在线` : '等待上报' }}
            </span>
          </div>

          <div v-if="masterRobots.length" class="panel-stack">
            <article v-for="robot in masterRobots" :key="robot.robot_id" class="card status-panel">
              <div class="panel-head">
                <div>
                  <div class="panel-id">{{ robot.robot_id }}</div>
                  <h4>{{ roleLabel(robot.role) }}</h4>
                </div>
                <div class="panel-badges">
                  <span class="pill" :class="isOnline(robot) ? 'accent' : ''">{{ isOnline(robot) ? '在线' : '离线' }}</span>
                  <span class="pill">{{ environmentLabel(robot) }}</span>
                </div>
              </div>

              <div class="metrics status-metrics">
                <div v-for="metric in heroMetrics(robot)" :key="metric.label" class="metric">
                  <div class="label">{{ metric.label }}</div>
                  <div class="value">{{ metric.value }}</div>
                </div>
              </div>

              <div class="telemetry-grid">
                <section v-for="section in robotSections(robot)" :key="section.title" class="telemetry-section">
                  <div class="telemetry-title">{{ section.title }}</div>
                  <div class="telemetry-list">
                    <div v-for="item in section.items" :key="item.label" class="telemetry-item">
                      <span>{{ item.label }}</span>
                      <strong>{{ item.value }}</strong>
                    </div>
                  </div>
                </section>
              </div>

              <div v-if="moduleChips(robot).length" class="chip-row">
                <span v-for="chip in moduleChips(robot)" :key="chip" class="pill">{{ chip }}</span>
              </div>

              <div v-if="capabilityChips(robot).length" class="chip-row dim">
                <span v-for="chip in capabilityChips(robot)" :key="chip" class="pill">{{ chip }}</span>
              </div>
            </article>
          </div>

          <article v-else class="card status-empty">
            <div class="eyebrow">NO MASTER YET</div>
            <h4>还没有收到主机状态</h4>
            <p>请先启动主机，或确认主机已持续发送 `status` / `capabilities`。</p>
          </article>
        </div>

        <div class="status-column">
          <div class="section-head">
            <div>
              <div class="eyebrow">SLAVE</div>
              <h3>从机状态</h3>
            </div>
            <span class="pill" :class="slaveCount ? 'accent' : ''">
              {{ slaveCount ? `${slaveCount} 台在线` : '等待上报' }}
            </span>
          </div>

          <div v-if="slaveRobots.length" class="panel-stack">
            <article v-for="robot in slaveRobots" :key="robot.robot_id" class="card status-panel">
              <div class="panel-head">
                <div>
                  <div class="panel-id">{{ robot.robot_id }}</div>
                  <h4>{{ roleLabel(robot.role) }}</h4>
                </div>
                <div class="panel-badges">
                  <span class="pill" :class="isOnline(robot) ? 'accent' : ''">{{ isOnline(robot) ? '在线' : '离线' }}</span>
                  <span class="pill">{{ environmentLabel(robot) }}</span>
                </div>
              </div>

              <div class="metrics status-metrics">
                <div v-for="metric in heroMetrics(robot)" :key="metric.label" class="metric">
                  <div class="label">{{ metric.label }}</div>
                  <div class="value">{{ metric.value }}</div>
                </div>
              </div>

              <div class="telemetry-grid">
                <section v-for="section in robotSections(robot)" :key="section.title" class="telemetry-section">
                  <div class="telemetry-title">{{ section.title }}</div>
                  <div class="telemetry-list">
                    <div v-for="item in section.items" :key="item.label" class="telemetry-item">
                      <span>{{ item.label }}</span>
                      <strong>{{ item.value }}</strong>
                    </div>
                  </div>
                </section>
              </div>

              <div v-if="moduleChips(robot).length" class="chip-row">
                <span v-for="chip in moduleChips(robot)" :key="chip" class="pill">{{ chip }}</span>
              </div>
            </article>
          </div>

          <article v-else class="card status-empty">
            <div class="eyebrow">NO SLAVE YET</div>
            <h4>还没有收到从机状态</h4>
            <p>本地联调时可以额外启动一个 slave，Dashboard 会自动分栏显示。</p>
          </article>
        </div>
      </section>

      <div class="hero-actions" style="gap:8px;">
        <button class="btn ghost" @click="disconnect" :disabled="!state.connected">断开</button>
        <button class="btn ghost" @click="showAdvanced = !showAdvanced">
          {{ showAdvanced ? '收起连接设置' : '展开连接设置' }}
        </button>
      </div>

      <article v-if="showAdvanced" class="card status-advanced">
        <div class="field">
          <label>WebSocket 地址</label>
          <input v-model="state.wsUrl" :placeholder="defaultWs" />
        </div>
        <div class="field">
          <label>快速选择</label>
          <select v-model="state.wsUrl">
            <option v-for="p in presets" :key="p.value" :value="p.value">{{ p.label }}</option>
          </select>
        </div>
        <div class="field duo">
          <div><label>本端 robot_id</label><input v-model="state.robotId" placeholder="controller" /></div>
          <div><label>大脑 master</label><input v-model="state.brainTargetRobot" placeholder="master-01" /></div>
        </div>
        <div class="field">
          <label>控制 slave</label>
          <input v-model="state.controlTargetRobot" placeholder="slave-01" />
        </div>
        <div class="field">
          <label><input type="checkbox" v-model="state.autoReconnect" /> 自动重连</label>
        </div>
      </article>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useStore } from '../store'

const { state, connect, disconnect, presets } = useStore()
const showAdvanced = ref(false)
const now = ref(Date.now())
let timer = null
const ONLINE_TTL = 7000

const defaultWs = computed(() => {
  const host = window.location.hostname || '127.0.0.1'
  const safeHost = host === '0.0.0.0' ? '127.0.0.1' : host
  return `ws://${safeHost}:8765`
})

const robots = computed(() => Object.values(state.robots || {}))
const activeRobots = computed(() => robots.value.filter(robot => isOnline(robot)))
const masterRobots = computed(() =>
  activeRobots.value.filter(robot =>
    robot.role === 'master'
    || (robot.robot_id === state.brainTargetRobot && robot.role !== 'slave')
  )
)
const slaveRobots = computed(() => activeRobots.value.filter(robot => robot.role === 'slave'))
const onlineCount = computed(() => activeRobots.value.length)
const masterCount = computed(() => masterRobots.value.length)
const slaveCount = computed(() => slaveRobots.value.length)
const lastAsr = computed(() => state.asr[0] ? state.asr[0].split('|').slice(1).join('|').trim() : '—')
const lastAi = computed(() => {
  const item = state.aiResults[0]
  return item?.data?.message || item?.detail || '—'
})
const lastConnectHint = computed(() => {
  const first = state.logs?.[0]
  if (!first) return ''
  if (state.connected) return ''
  // 只展示可能与连接相关的提示，避免噪音
  const text = String(first.msg || '')
  const type = String(first.type || '')
  if (type === 'error' || type === 'warn') return `${first.ts} | ${text}`
  if (text.includes('已连接') || text.includes('连接关闭') || text.includes('缺少 WS')) {
    return `${first.ts} | ${text}`
  }
  return ''
})

function isOnline(robot) {
  return now.value - Number(robot?.lastSeen || 0) < ONLINE_TTL
}

function roleLabel(role) {
  if (role === 'master') return '主机'
  if (role === 'slave') return '从机'
  if (role === 'controller') return '控制端'
  return '机器人'
}

function environmentLabel(robot) {
  const system = robot?.status?.system || {}
  if (system.sim_mode) return '本地模拟'
  if (system.local_test) return '本地联调'
  return '在线环境'
}

function formatDuration(seconds) {
  const total = Number(seconds || 0)
  if (!Number.isFinite(total) || total <= 0) return '—'
  if (total < 60) return `${Math.round(total)} 秒`
  const mins = Math.floor(total / 60)
  const secs = Math.round(total % 60)
  if (mins < 60) return `${mins} 分 ${secs} 秒`
  const hours = Math.floor(mins / 60)
  return `${hours} 小时 ${mins % 60} 分`
}

function formatAge(lastSeen) {
  const delta = now.value - Number(lastSeen || 0)
  if (!lastSeen) return '—'
  if (delta < 1000) return '刚刚'
  if (delta < 60000) return `${Math.floor(delta / 1000)} 秒前`
  return `${Math.floor(delta / 60000)} 分钟前`
}

function formatValue(value, suffix = '') {
  if (value === '' || value == null) return '—'
  if (typeof value === 'boolean') return value ? '正常' : '关闭'
  if (typeof value === 'number') {
    const fixed = Math.abs(value) >= 100 ? Math.round(value) : Number(value.toFixed(1))
    return `${fixed}${suffix}`
  }
  return `${value}${suffix}`
}

function percent(value) {
  if (value === '' || value == null) return '—'
  return `${Math.round(Number(value))}%`
}

function heroMetrics(robot) {
  const system = robot?.status?.system || {}
  const sensors = robot?.status?.sensors || {}
  const motion = robot?.status?.motion || {}
  return [
    { label: '最近心跳', value: formatAge(robot?.lastSeen) },
    { label: '运行时长', value: formatDuration(system.uptime_sec) },
    { label: '电量', value: percent(sensors.battery_pct ?? robot?.status?.battery) },
    { label: '网络', value: percent(sensors.network_pct) },
    { label: '当前线速度', value: formatValue(motion.linear, ' m/s') },
    { label: '当前角速度', value: formatValue(motion.angular, ' rad/s') },
  ].filter(item => item.value !== '—')
}

function section(title, items) {
  const valid = items.filter(item => item.value !== '—')
  return valid.length ? { title, items: valid } : null
}

function robotSections(robot) {
  const status = robot?.status || {}
  const system = status.system || {}
  const sensors = status.sensors || {}
  const motion = status.motion || {}
  const audio = status.audio || {}
  const ai = status.modules?.ai_assistant || {}

  return [
    section('系统', [
      { label: '主机名', value: formatValue(system.hostname) },
      { label: 'WS 地址', value: formatValue(system.ws_url) },
      { label: '时间戳', value: formatValue(status.ts || robot?.lastRobotTs) },
      { label: '环境', value: formatValue(system.runtime_label || environmentLabel(robot)) },
    ]),
    section('音频 / AI', [
      { label: 'TTS', value: formatValue(audio.tts_ready) },
      { label: 'ASR 桥接', value: formatValue(audio.asr_bridge_ready) },
      { label: '音频话题', value: formatValue(audio.audio_topic) },
      { label: 'TTS 服务', value: formatValue(audio.tts_service) },
      { label: 'AI 开启', value: formatValue(ai.enabled) },
      { label: 'AI 自动播报', value: formatValue(ai.auto_tts) },
      { label: 'AI 动作执行', value: formatValue(ai.allow_action_execution) },
    ]),
    section('运动', [
      { label: '最后预设动作', value: formatValue(motion.last_preset) },
      { label: '动作 ID', value: formatValue(motion.last_motion_id) },
      { label: '动作区域', value: formatValue(motion.last_area_id) },
      { label: '上次动作时间', value: formatValue(motion.last_command_age_sec, ' 秒前') },
    ]),
    section('传感器', [
      { label: '网络质量', value: percent(sensors.network_pct) },
      { label: '音量电平', value: percent(sensors.audio_level_pct) },
      { label: 'IMU 偏航', value: formatValue(sensors.imu_yaw_deg, ' °') },
      { label: '障碍距离', value: formatValue(sensors.obstacle_distance_cm, ' cm') },
      { label: '雷达距离', value: formatValue(sensors.lidar_distance_m, ' m') },
      { label: '电机温度', value: formatValue(sensors.motor_temp_c, ' °C') },
      { label: '姿态', value: formatValue(sensors.posture) },
    ]),
  ].filter(Boolean)
}

function moduleChips(robot) {
  const enabledModules = Array.isArray(robot?.enabledModules) ? robot.enabledModules : []
  const statusModules = robot?.status?.modules || {}
  return enabledModules.slice(0, 12).map(name => {
    const detail = statusModules[name]
    const ready = detail && Object.values(detail).some(Boolean)
    return ready ? `${name} · ready` : name
  })
}

function capabilityChips(robot) {
  const caps = robot?.capabilities || {}
  const chips = []
  if (caps?.actions?.available) chips.push(`动作 ${caps.actions.supported?.length || 0}`)
  if (caps?.ai?.available) chips.push(`AI ${caps.ai.enabled ? 'on' : 'off'}`)
  if (caps?.asr?.available) chips.push('ASR')
  if (caps?.tts?.available) chips.push('TTS')
  if (caps?.topics?.audio_capture) chips.push('音频采集')
  return chips
}

onMounted(() => {
  if (!state.wsUrl) state.wsUrl = defaultWs.value
  timer = window.setInterval(() => {
    now.value = Date.now()
  }, 1000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>
