<template>
  <section class="monitor-grid">
    <article class="card wide">
      <div class="card-head">
        <h3>协同监控面板</h3>
        <span class="pill">mjpeg</span>
      </div>
      <div class="hint">建议：前端看合并画面；左右原始流留给两路 YOLO 调试。</div>

      <div class="panes">
        <div class="pane">
          <MjpegCanvasPanel
            title="左右合并"
            subtitle="stereo L + stereo R"
            mode="hstack"
            v-model:leftUrl="stereoLeftUrl"
            v-model:rightUrl="stereoRightUrl"
            :left-overlays="visionLeftDets"
            :right-overlays="visionRightDets"
            overlay-label="YOLO"
            :show-urls="showAdvanced"
          />
        </div>
        <div class="pane">
          <MjpegCanvasPanel
            title="后视"
            subtitle="rear"
            mode="single"
            v-model:url="rearUrl"
            :show-urls="showAdvanced"
          />
        </div>
      </div>

      <div class="preset-row" v-if="slaveStream.presets && slaveStream.presets.length">
        <div class="preset-title">从机 presets：</div>
        <button class="preset-btn" v-for="p in slaveStream.presets" :key="p.url" @click="applyPreset(p)">
          {{ p.label || p.topic || p.url }}
        </button>
        <button class="preset-btn" @click="showAdvanced = !showAdvanced">{{ showAdvanced ? '收起高级' : '展开高级' }}</button>
      </div>
    </article>

    <article class="card">
      <div class="card-head">
        <h3>自定义/调试流</h3>
        <span class="pill muted">debug</span>
      </div>
      <StreamBox v-model:url="customUrl" placeholder="任意可直接在浏览器播放的流" />
    </article>

    <article class="card">
      <div class="card-head">
        <h3>Vision 调试</h3>
        <span class="pill muted">vision</span>
      </div>
      <div class="hint">当 `vision_yolo` 推送 `type=vision` 时，这里会显示最近一条。</div>
      <div class="field">
        <label class="hint">叠框阈值（score ≥ {{ Number(overlayConf || 0).toFixed(2) }}）</label>
        <input class="slider" type="range" min="0" max="0.9" step="0.01" v-model.number="overlayConf" />
      </div>
      <div class="kv">
        <div class="k">action|left</div>
        <div class="v">{{ visionActionLeft?.payload?.meta?.loop_fps?.toFixed?.(1) || '-' }} fps / {{ visionLeftDets.length }} dets</div>
      </div>
      <div class="kv">
        <div class="k">object|right</div>
        <div class="v">{{ visionObjectRight?.payload?.meta?.loop_fps?.toFixed?.(1) || '-' }} fps / {{ visionRightDets.length }} dets</div>
      </div>
      <div class="hint small" v-if="visionActionLeft?.payload?.meta">
        sync={{ Number(visionActionLeft.payload.meta.sync_dt_ms || 0).toFixed(0) }}ms
        infer={{ Number(visionActionLeft.payload.meta.infer_ms || 0).toFixed(0) }}ms
        age={{ Number(visionActionLeft.payload.meta.grab_age_ms || 0).toFixed(0) }}ms
      </div>
    </article>

    <article class="card">
      <div class="card-head">
        <h3>主机摄像头（可选）</h3>
        <span class="pill">master</span>
      </div>
      <StreamBox
        v-model:url="masterUrl"
        :auto-url="masterStream.autoUrl"
        :stream-info="masterStream"
        placeholder="主机或额外机位流"
      />
    </article>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useStore } from '../store'
import StreamBox from '../components/StreamBox.vue'
import MjpegCanvasPanel from '../components/MjpegCanvasPanel.vue'

const { state } = useStore()

const masterUrl = ref(load('monitor_master') || '')
const customUrl = ref(load('monitor_custom') || '')

const stereoLeftUrl = ref(load('monitor_stereo_left') || '')
const stereoRightUrl = ref(load('monitor_stereo_right') || '')
const rearUrl = ref(load('monitor_rear') || '')
const showAdvanced = ref(false)
const overlayConf = ref(Number(load('monitor_overlay_conf') || 0.35))

const visionActionLeft = computed(() => state.visionLatest?.['action|left'] || null)
const visionObjectRight = computed(() => state.visionLatest?.['object|right'] || null)
const visionLeftDets = computed(() => {
  const dets = visionActionLeft.value?.payload?.dets || []
  const th = Number(overlayConf.value || 0)
  return dets.filter((d) => Number(d?.score || 0) >= th)
})
const visionRightDets = computed(() => {
  const dets = visionObjectRight.value?.payload?.dets || []
  const th = Number(overlayConf.value || 0)
  return dets.filter((d) => Number(d?.score || 0) >= th)
})

function proxyRobotUrl(rawUrl) {
  const input = String(rawUrl || '').trim()
  if (!input) return ''
  try {
    const u = new URL(input)
    const robotHost = String(state.networkRobotHost || '192.168.88.88').trim() || '192.168.88.88'
    if ((u.protocol === 'http:' || u.protocol === 'https:') && u.hostname === robotHost) {
      const origin = typeof location !== 'undefined' && location.origin ? location.origin : ''
      const prefix = origin || ''
      return `${prefix}/proxy/robot?url=${encodeURIComponent(input)}`
    }
  } catch {
    // ignore
  }
  return input
}

function normalizeStreamInfo(raw = {}) {
  const presets = Array.isArray(raw.presets) ? raw.presets : []
  const autoFromPreset = presets.length ? (presets[0].url || '') : ''
  return {
    autoUrl: raw.webrtc_whep_url || raw.webrtc_page_url || raw.auto_url || autoFromPreset || '',
    rtspUrl: raw.rtsp_url || '',
    pageUrl: raw.webrtc_page_url || '',
    hlsUrl: raw.hls_url || '',
    topic: raw.topic || '',
    preferredPlayer: raw.preferred_player || '',
    presets,
    enabled: Boolean(raw.enabled),
  }
}

const slaveStream = computed(() => {
  const robotId = state.controlTargetRobot
  return normalizeStreamInfo(state.robots?.[robotId]?.status?.streams || {})
})

const masterStream = computed(() => {
  const robotId = state.brainTargetRobot
  return normalizeStreamInfo(state.robots?.[robotId]?.status?.streams || {})
})

function load(key) {
  if (typeof localStorage === 'undefined') return ''
  return localStorage.getItem(key) || ''
}
function save(key, value) {
  if (typeof localStorage === 'undefined') return
  if (value) localStorage.setItem(key, value)
  else localStorage.removeItem(key)
}

;[
  ['monitor_master', masterUrl],
  ['monitor_custom', customUrl],
  ['monitor_stereo_left', stereoLeftUrl],
  ['monitor_stereo_right', stereoRightUrl],
  ['monitor_rear', rearUrl],
  ['monitor_overlay_conf', overlayConf],
].forEach(([k, r]) => {
  watch(r, (v) => save(k, v))
})

// 只要用户输入/机器人上报的是热点侧 `192.168.88.88`，就强制走同源代理。
;[stereoLeftUrl, stereoRightUrl, rearUrl].forEach((r) => {
  watch(r, (v) => {
    const next = proxyRobotUrl(v)
    if (next && next !== v) r.value = next
  })
})

function pickPreset(presets, predicate) {
  return (presets || []).find((p) => predicate(String(p.topic || ''), String(p.label || ''), String(p.url || '')))
}

function autoFillFromPresets() {
  const presets = slaveStream.value.presets || []
  if (!stereoLeftUrl.value) {
    const p = pickPreset(presets, (topic, label) => topic.includes('stereo_head_front_left') || label.includes('front_left') || label.endsWith('front_left'))
    if (p?.url) stereoLeftUrl.value = proxyRobotUrl(p.url)
  }
  if (!stereoRightUrl.value) {
    const p = pickPreset(presets, (topic, label) => topic.includes('stereo_head_front_right') || label.includes('front_right') || label.endsWith('front_right'))
    if (p?.url) stereoRightUrl.value = proxyRobotUrl(p.url)
  }
  if (!rearUrl.value) {
    const p = pickPreset(presets, (topic, label) => topic.includes('rgb_head_rear') || label.includes('head_rear') || label.endsWith('head_rear'))
    if (p?.url) rearUrl.value = proxyRobotUrl(p.url)
  }
}

watch(slaveStream, () => autoFillFromPresets(), { immediate: true })

function applyPreset(p) {
  const topic = String(p.topic || '')
  const nextUrl = proxyRobotUrl(p.url)
  if (topic.includes('stereo_head_front_left')) stereoLeftUrl.value = nextUrl
  else if (topic.includes('stereo_head_front_right')) stereoRightUrl.value = nextUrl
  else if (topic.includes('rgb_head_rear')) rearUrl.value = nextUrl
  else rearUrl.value = nextUrl
}

// 本地历史若是直连机器人热点 IP，也统一转为同源代理，避免其它设备无法访问。
;[stereoLeftUrl, stereoRightUrl, rearUrl].forEach((r) => {
  const v = proxyRobotUrl(r.value)
  if (v && v !== r.value) r.value = v
})
</script>

<style scoped>
.monitor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 18px;
}
.wide { grid-column: 1 / -1; }
.panes { display:grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
.pane { display:block; }
.preset-row {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.preset-title { font-size: 12px; color: #9aa0a6; margin-right: 6px; }
.preset-btn {
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.06);
  color: var(--text);
  cursor: pointer;
}
.kv { display:flex; justify-content:space-between; gap: 10px; padding: 6px 0; border-bottom: 1px dashed rgba(255,255,255,0.08); }
.kv .k { color: #9aa0a6; font-size: 12px; }
.kv .v { color: var(--text); font-size: 12px; text-align:right; }
.hint.small { font-size: 11px; }
.slider { width: 100%; }
</style>
