import { reactive, computed } from 'vue'
import { featureConfig as defaultFeatureConfig } from './config'

const CFG_KEY = 'bot_connect_cfg_v3'

function cloneFeatureFlags(source = {}) {
  return { ...defaultFeatureConfig, ...(source || {}) }
}

function normalizeWsUrl(url) {
  const value = String(url || '').trim()
  if (!value) return ''
  return value.replace(/^ws:\/\/0\.0\.0\.0(?::\d+)?/i, 'ws://127.0.0.1')
}

function defaultAppConfig() {
  return {
    version: 0,
    network: {
      robot_host: '192.168.88.88',
    },
    frontend: {
      controller_robot_id: 'controller',
      role: 'controller',
      ws_url: '',
      auto_reconnect: true,
      targets: {
        brain_robot_id: 'master-01',
        control_robot_id: 'slave-01',
      },
      display: {
        auto_scroll: true,
      },
      feature_flags: cloneFeatureFlags(),
    },
    backend: {
      auto_ai_reply: false,
      ai_prefix: '收到：',
      tts_robot_id: 'master-01',
    },
    master: {
      robot_id: 'master-01',
      ai: {
        enabled: false,
        auto_tts: true,
        allow_action_execution: false,
        forward_action_to_slave: false,
        forward_action_target: 'slave-01',
        tts_target_robot: 'slave-01',
        trigger_on_partial: false,
        behavior_lock_enabled: true,
        behavior_lock_timeout_sec: 20,
      },
    },
    slave: {
      robot_id: 'slave-01',
    },
  }
}

const state = reactive({
  wsUrl: '',
  robotId: 'controller',
  role: 'controller',
  brainTargetRobot: 'master-01',
  controlTargetRobot: 'slave-01',
  targetRobot: 'master-01',
  networkRobotHost: '192.168.88.88',
  connected: false,
  autoReconnect: true,
  ws: null,
  reconnectTimer: null,
  logs: [],
  results: [],
  asr: [],
  audio: [],
  vision: [],
  visionLatest: {},
  online: {},
  robots: {},
  aiResults: [],
  configVersion: 0,
  lastConfigSyncAt: 0,
  recordingActive: false,
  recordingSession: '',
  featureFlags: cloneFeatureFlags(),
  settings: {
    autoAiReply: false,
    aiPrefix: '收到：',
    ttsRobotId: 'master-01',
    masterAiEnabled: false,
    masterAiAutoTts: true,
    masterAiAllowActionExecution: false,
    masterAiForward: false,
    masterAiForwardTarget: 'slave-01',
    masterAiTtsTarget: 'slave-01',
    masterAiBehaviorLockEnabled: true,
    masterAiBehaviorLockTimeoutSec: 20,
    uiAutoScroll: true,
  },
})

function nowTs() {
  return new Date().toLocaleTimeString()
}

function isObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value)
}

function mergeDeep(base, extra) {
  const result = { ...(isObject(base) ? base : {}) }
  if (!isObject(extra)) return result
  Object.entries(extra).forEach(([key, value]) => {
    if (isObject(result[key]) && isObject(value)) {
      result[key] = mergeDeep(result[key], value)
    } else {
      result[key] = value
    }
  })
  return result
}

function normalizeAppConfig(raw) {
  const base = defaultAppConfig()
  if (!isObject(raw)) return base

  if (isObject(raw.settings)) {
    return mergeDeep(base, {
      version: Number(raw.configVersion || raw.version || 0),
      frontend: {
        controller_robot_id: raw.robotId || base.frontend.controller_robot_id,
        role: raw.role || base.frontend.role,
        ws_url: raw.wsUrl || base.frontend.ws_url,
        auto_reconnect: raw.autoReconnect ?? base.frontend.auto_reconnect,
        targets: {
          brain_robot_id: raw.brainTargetRobot || raw.targetRobot || base.frontend.targets.brain_robot_id,
          control_robot_id: raw.controlTargetRobot || base.frontend.targets.control_robot_id,
        },
        display: {
          auto_scroll: raw.settings.uiAutoScroll ?? base.frontend.display.auto_scroll,
        },
        feature_flags: raw.featureFlags || base.frontend.feature_flags,
      },
      backend: {
        auto_ai_reply: raw.settings.autoAiReply ?? base.backend.auto_ai_reply,
        ai_prefix: raw.settings.aiPrefix ?? base.backend.ai_prefix,
        tts_robot_id: raw.settings.ttsRobotId || base.backend.tts_robot_id,
      },
      master: {
        robot_id: raw.brainTargetRobot || raw.targetRobot || base.master.robot_id,
        ai: {
          enabled: raw.settings.masterAiEnabled ?? base.master.ai.enabled,
          auto_tts: raw.settings.masterAiAutoTts ?? base.master.ai.auto_tts,
          allow_action_execution: raw.settings.masterAiAllowActionExecution ?? base.master.ai.allow_action_execution,
          forward_action_to_slave: raw.settings.masterAiForward ?? base.master.ai.forward_action_to_slave,
          forward_action_target: raw.settings.masterAiForwardTarget || base.master.ai.forward_action_target,
          tts_target_robot: raw.settings.masterAiTtsTarget || base.master.ai.tts_target_robot,
          behavior_lock_enabled: raw.settings.masterAiBehaviorLockEnabled ?? base.master.ai.behavior_lock_enabled,
          behavior_lock_timeout_sec: raw.settings.masterAiBehaviorLockTimeoutSec ?? base.master.ai.behavior_lock_timeout_sec,
        },
      },
      slave: {
        robot_id: raw.controlTargetRobot || base.slave.robot_id,
      },
    })
  }

  const merged = mergeDeep(base, raw)
  if (raw.auto_ai_reply !== undefined || raw.ai_prefix !== undefined || raw.tts_robot_id !== undefined) {
    merged.backend = mergeDeep(merged.backend, {
      auto_ai_reply: raw.auto_ai_reply,
      ai_prefix: raw.ai_prefix,
      tts_robot_id: raw.tts_robot_id,
    })
  }
  merged.frontend.feature_flags = cloneFeatureFlags(merged.frontend.feature_flags)
  return merged
}

function buildAppConfigPayload() {
  return {
    version: Number(state.configVersion || 0),
    network: {
      robot_host: state.networkRobotHost || '192.168.88.88',
    },
    frontend: {
      controller_robot_id: state.robotId,
      role: state.role,
      ws_url: state.wsUrl,
      auto_reconnect: state.autoReconnect,
      targets: {
        brain_robot_id: state.brainTargetRobot,
        control_robot_id: state.controlTargetRobot,
      },
      display: {
        auto_scroll: state.settings.uiAutoScroll,
      },
      feature_flags: cloneFeatureFlags(state.featureFlags),
    },
    backend: {
      auto_ai_reply: state.settings.autoAiReply,
      ai_prefix: state.settings.aiPrefix,
      tts_robot_id: state.settings.ttsRobotId,
    },
    master: {
      robot_id: state.brainTargetRobot,
      ai: {
        enabled: state.settings.masterAiEnabled,
        auto_tts: state.settings.masterAiAutoTts,
        allow_action_execution: state.settings.masterAiAllowActionExecution,
        forward_action_to_slave: state.settings.masterAiForward,
        forward_action_target: state.settings.masterAiForwardTarget,
        tts_target_robot: state.settings.masterAiTtsTarget,
        behavior_lock_enabled: state.settings.masterAiBehaviorLockEnabled,
        behavior_lock_timeout_sec: Number(state.settings.masterAiBehaviorLockTimeoutSec || 20),
      },
    },
    slave: {
      robot_id: state.controlTargetRobot,
    },
  }
}

function applyAppConfig(rawConfig, options = {}) {
  const { persist = false, source = 'local' } = options
  const next = normalizeAppConfig(rawConfig)
  const network = next.network || {}
  const frontend = next.frontend || {}
  const targets = frontend.targets || {}
  const backend = next.backend || {}
  const master = next.master || {}
  const masterAi = master.ai || {}
  const slave = next.slave || {}

  state.configVersion = Number(next.version || state.configVersion || 0)
  state.lastConfigSyncAt = Date.now()

  state.networkRobotHost = network.robot_host || state.networkRobotHost || '192.168.88.88'

  if (frontend.controller_robot_id) state.robotId = frontend.controller_robot_id
  if (frontend.role) state.role = frontend.role
  if (source !== 'remote' || frontend.ws_url) state.wsUrl = normalizeWsUrl(frontend.ws_url ?? state.wsUrl)
  state.autoReconnect = frontend.auto_reconnect ?? state.autoReconnect

  state.brainTargetRobot = targets.brain_robot_id || master.robot_id || state.brainTargetRobot
  state.controlTargetRobot = targets.control_robot_id || slave.robot_id || state.controlTargetRobot
  state.targetRobot = state.brainTargetRobot
  state.featureFlags = cloneFeatureFlags(frontend.feature_flags)

  state.settings.uiAutoScroll = frontend.display?.auto_scroll ?? state.settings.uiAutoScroll
  state.settings.autoAiReply = backend.auto_ai_reply ?? state.settings.autoAiReply
  state.settings.aiPrefix = backend.ai_prefix ?? state.settings.aiPrefix
  state.settings.ttsRobotId = backend.tts_robot_id || state.settings.ttsRobotId
  state.settings.masterAiEnabled = masterAi.enabled ?? state.settings.masterAiEnabled
  state.settings.masterAiAutoTts = masterAi.auto_tts ?? state.settings.masterAiAutoTts
  state.settings.masterAiAllowActionExecution = masterAi.allow_action_execution ?? state.settings.masterAiAllowActionExecution
  state.settings.masterAiForward = masterAi.forward_action_to_slave ?? state.settings.masterAiForward
  state.settings.masterAiForwardTarget = masterAi.forward_action_target || state.settings.masterAiForwardTarget
  state.settings.masterAiTtsTarget = masterAi.tts_target_robot || state.settings.masterAiTtsTarget
  state.settings.masterAiBehaviorLockEnabled = masterAi.behavior_lock_enabled ?? state.settings.masterAiBehaviorLockEnabled
  state.settings.masterAiBehaviorLockTimeoutSec = Number(
    masterAi.behavior_lock_timeout_sec ?? state.settings.masterAiBehaviorLockTimeoutSec
  )

  if (persist) saveConfig()
}

function loadConfig() {
  try {
    const raw = localStorage.getItem(CFG_KEY)
    if (raw) {
      applyAppConfig(JSON.parse(raw))
      return
    }
    const legacy = localStorage.getItem('bot_connect_cfg_v2')
    if (legacy) {
      applyAppConfig(JSON.parse(legacy))
      saveConfig()
    }
  } catch {
    // ignore parse errors
  }
}

function saveConfig() {
  localStorage.setItem(CFG_KEY, JSON.stringify(buildAppConfigPayload()))
}

function pushLog(entry) {
  const log = { ts: nowTs(), ...entry }
  // 尝试从 msg 里提取元数据，便于过滤
  if (!log.robot_id || !log.msg_type || !log.source_role || !log.target_role) {
    const meta = extractLogMeta(log.msg)
    Object.entries(meta).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '' && log[k] == null) {
        log[k] = v
      }
    })
  }
  state.logs.unshift(log)
  if (state.logs.length > 1000) state.logs.pop()
}

function extractLogMeta(msg) {
  if (!msg) return {}
  let obj = null
  if (typeof msg === 'string') {
    try { obj = JSON.parse(msg) } catch { obj = null }
  } else if (typeof msg === 'object') {
    obj = msg
  }
  if (!obj || Array.isArray(obj)) return {}
  return {
    msg_type: obj.type,
    robot_id: obj.robot_id,
    source_robot_id: obj.source_robot_id,
    source_role: obj.source_role || obj.role,
    target_robot: obj.target_robot,
    target_role: obj.target_role,
    config_version: obj.config_version,
    action: obj.action,
  }
}

function inferRole(robotId, payload = {}, fallbackRole = '') {
  if (fallbackRole) return fallbackRole
  if (payload?.role) return payload.role
  if (!robotId) return 'robot'
  if (robotId === state.robotId) return state.role || 'controller'
  if (String(robotId).startsWith('master')) return 'master'
  if (String(robotId).startsWith('slave')) return 'slave'
  return 'robot'
}

function ensureRobot(robotId) {
  if (!robotId) return null
  if (!state.robots[robotId]) {
    state.robots[robotId] = {
      robot_id: robotId,
      role: inferRole(robotId),
      lastSeen: 0,
      lastRobotTs: 0,
      lastType: '',
      configVersion: 0,
      status: {},
      capabilities: {},
      modules: {},
      enabledModules: [],
    }
  }
  return state.robots[robotId]
}

function updateRobotRecord(data) {
  const robotId = data?.robot_id
  if (!robotId || robotId === 'server') return
  const record = ensureRobot(robotId)
  if (!record) return

  const payload = isObject(data.payload) ? data.payload : {}
  record.lastSeen = Date.now()
  record.lastRobotTs = Number(data.ts || 0)
  record.lastType = data.type || ''
  record.configVersion = Number(data.config_version || payload.config_version || record.configVersion || 0)
  record.role = inferRole(robotId, payload, data.role || data.source_role || '')

  if (data.type === 'status') {
    record.status = mergeDeep(record.status, payload)
    record.modules = isObject(payload.modules) ? payload.modules : (record.modules || {})
    record.enabledModules = Array.isArray(payload.enabled_modules)
      ? payload.enabled_modules.slice()
      : (record.enabledModules || [])
  } else if (data.type === 'capabilities') {
    record.capabilities = mergeDeep(record.capabilities, payload)
    record.enabledModules = Array.isArray(payload.enabled_modules)
      ? payload.enabled_modules.slice()
      : (record.enabledModules || [])
  }

  state.online[robotId] = record.lastSeen
}

function updateRecentAudioText(data, text) {
  const session = data.session ?? data?.payload?.session ?? null
  const seq = data.seq ?? data?.payload?.seq ?? null
  if (!session) return
  const item = state.audio.find((entry) => {
    if (entry.session !== session) return false
    if (seq == null || entry.seq == null) return true
    return String(entry.seq) === String(seq)
  })
  if (item) item.text = text
}

function applyRemoteConfigMessage(data) {
  const payload = isObject(data.payload) ? data.payload : {}
  const nextConfig = isObject(payload.config) ? payload.config : payload
  applyAppConfig(nextConfig, { persist: true, source: 'remote' })
  pushLog({
    type: 'info',
    dir: 'sys',
    msg: `配置已同步 version=${payload.version ?? data.config_version ?? state.configVersion}`,
  })
}

function connect(urlOverride) {
  let url = urlOverride || state.wsUrl
  if (!url && typeof window !== 'undefined' && window.electronAPI?.defaultWsUrl) {
    url = String(window.electronAPI.defaultWsUrl || '').trim()
    if (url) state.wsUrl = url
  }
  if (!url && typeof location !== 'undefined' && location.host) {
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
    url = `${scheme}://${location.host}`
    state.wsUrl = url
  }
  if (!url) {
    pushLog({ type: 'error', dir: 'out', msg: '缺少 WS 地址' })
    return
  }
  if (state.connected && state.ws) return
  saveConfig()
  try {
    state.ws = new WebSocket(url)
    state.ws.onopen = () => {
      state.connected = true
      clearTimeout(state.reconnectTimer)
      pushLog({ type: 'info', dir: 'sys', msg: '已连接', msg_type: 'open' })
      const hello = {
        type: 'hello',
        robot_id: state.robotId,
        role: state.role,
        config_version: state.configVersion,
        ts: Date.now() / 1000,
      }
      state.ws.send(JSON.stringify(hello))
      pushLog({ type: 'send', dir: 'out', msg: JSON.stringify(hello), msg_type: 'hello', robot_id: state.robotId, source_role: state.role })
      const cfgGet = {
        type: 'config_get',
        robot_id: state.robotId,
        role: state.role,
        config_version: state.configVersion,
        ts: Date.now() / 1000,
      }
      state.ws.send(JSON.stringify(cfgGet))
      pushLog({ type: 'send', dir: 'out', msg: JSON.stringify(cfgGet), msg_type: 'config_get', robot_id: state.robotId, source_role: state.role })
    }
    state.ws.onclose = (e) => {
      state.connected = false
      pushLog({ type: 'warn', dir: 'sys', msg: '连接关闭 ' + (e.reason || '') })
      if (state.autoReconnect) {
        clearTimeout(state.reconnectTimer)
        state.reconnectTimer = setTimeout(() => connect(), 3000)
      }
    }
    state.ws.onerror = (e) => {
      pushLog({ type: 'error', dir: 'sys', msg: e?.message || 'ws error' })
    }
    state.ws.onmessage = (e) => {
      let data = null
      try { data = JSON.parse(e.data) } catch { data = null }
      pushLog({
        type: 'recv',
        dir: 'in',
        msg: e.data,
        ...(data ? {
          msg_type: data.type,
          robot_id: data.robot_id,
          source_role: data.source_role || data.role,
          target_robot: data.target_robot,
          target_role: data.target_role,
        } : {})
      })
      if (!data) return

      if (data.type === 'config_sync') {
        applyRemoteConfigMessage(data)
        return
      }

      updateRobotRecord(data)

      if (data.type === 'result') {
        state.results.unshift({
          ts: nowTs(),
          ok: data.ok,
          detail: data.detail ?? '',
          robot_id: data.robot_id ?? '',
          action: data.action ?? '',
          module: data.module ?? '',
          text: data.text ?? '',
          request_id: data.request_id ?? '',
          source_role: data.source_role ?? '',
          target_role: data.target_role ?? '',
        })
        if (state.results.length > 200) state.results.pop()
      } else if (data.type === 'asr_text') {
        const txt = (data.text || '').trim()
        if (txt) {
          state.asr.unshift(`${nowTs()} | ${txt}`)
          if (state.asr.length > 500) state.asr.pop()
          updateRecentAudioText(data, txt)
        }
      } else if (data.type === 'ai_result') {
        state.aiResults.unshift({
          ts: nowTs(),
          robot_id: data.robot_id ?? '',
          source_robot_id: data.source_robot_id ?? '',
          source_session: data.source_session ?? null,
          source_seq: data.source_seq ?? null,
          stage: data.stage ?? 'completed',
          ok: data.ok,
          detail: data.detail ?? '',
          data: data.data ?? null,
          action_result: data.action_result ?? null,
          input_text: data.input_text ?? '',
          triggered: data.triggered ?? null,
          called: data.called ?? null,
          skip_reason: data.skip_reason ?? '',
        })
        if (state.aiResults.length > 200) state.aiResults.pop()
      } else if (data.type === 'audio_saved' || data.type === 'audio_available') {
        state.audio.unshift({ ts: nowTs(), detail: data })
        if (state.audio.length > 200) state.audio.pop()
      } else if (data.type === 'vision') {
        state.vision.unshift({ ts: nowTs(), detail: data })
        if (state.vision.length > 500) state.vision.pop()
        const meta = data?.payload?.meta || {}
        const key = `${meta.task || 'task'}|${meta.camera || 'cam'}`
        state.visionLatest[key] = data
      } else if (data.type === 'master_config_ack') {
        pushLog({
          type: 'info',
          dir: 'sys',
          msg: `主机配置已确认 version=${data.payload?.ai?.config_version ?? state.configVersion}`,
        })
      }

      if (data.robot_id) state.online[data.robot_id] = Date.now()
    }
  } catch (e) {
    pushLog({ type: 'error', dir: 'sys', msg: e.message })
  }
}

function disconnect() {
  clearTimeout(state.reconnectTimer)
  if (state.ws) state.ws.close()
  state.ws = null
  state.connected = false
}

function send(obj) {
  if (!state.connected || !state.ws) {
    pushLog({ type: 'warn', dir: 'out', msg: '未连接，无法发送' })
    return
  }
  const payload = {
    robot_id: state.robotId,
    role: state.role,
    config_version: state.configVersion,
    ts: Date.now() / 1000,
    ...obj,
  }
  state.ws.send(JSON.stringify(payload))
  pushLog({
    type: 'send',
    dir: 'out',
    msg: JSON.stringify(payload),
    msg_type: payload.type,
    robot_id: payload.robot_id,
    source_role: payload.role,
    target_robot: payload.target_robot,
    target_role: payload.target_role,
    action: payload.payload?.action,
  })
}

function pushConfigSync() {
  saveConfig()
  send({
    type: 'config_update',
    payload: {
      app_config: buildAppConfigPayload(),
    },
  })
}

function markRecording(active, session = '') {
  state.recordingActive = Boolean(active)
  state.recordingSession = active ? String(session || '') : ''
}

const presets = computed(() => {
  const host = window.location.hostname || '127.0.0.1'
  return [
    { label: '本机回环', value: 'ws://127.0.0.1:8765' },
    { label: '当前主机', value: `ws://${host === '0.0.0.0' ? '127.0.0.1' : host}:8765` },
    { label: 'WSL 宿主网关', value: 'ws://172.19.0.1:8765' },
  ]
})

export function useStore() {
  return {
    state,
    connect,
    disconnect,
    send,
    presets,
    loadConfig,
    saveConfig,
    pushConfigSync,
    buildAppConfigPayload,
    applyAppConfig,
    markRecording,
  }
}

if (typeof window !== 'undefined') {
  loadConfig()
}

if (typeof window !== 'undefined') {
  // 若用户未手动填写 WS 地址，则默认使用“当前页面同源 WS”或 Electron 注入的默认值，
  // 以便其它设备直接访问 http://<PC_IP>:8765 后能自动连上 ws://<PC_IP>:8765。
  if (!state.wsUrl) {
    const injected = window.electronAPI?.defaultWsUrl
    if (injected) {
      state.wsUrl = normalizeWsUrl(injected)
    } else if (location?.host) {
      const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
      const host = location.hostname === '0.0.0.0' ? '127.0.0.1' : location.hostname
      state.wsUrl = `${scheme}://${host}${location.port ? `:${location.port}` : ''}`
    }
  }

  window.addEventListener('load', () => {
    if (state.autoReconnect && state.wsUrl) {
      setTimeout(() => connect(), 300)
    }
  })
}
