<template>
  <div class="panel">
    <div class="head">
      <div class="title">
        <strong>{{ title }}</strong>
        <span class="meta" v-if="subtitle">{{ subtitle }}</span>
      </div>
      <div class="actions">
        <button class="btn tiny" @click="copyUrl" :disabled="!copyValue">复制 URL</button>
        <button class="btn tiny" @click="openUrl" :disabled="!copyValue">新窗口打开</button>
        <button class="btn tiny" @click="snapshot" :disabled="!ready">截图</button>
        <button class="btn tiny" @click="overlayOn = !overlayOn" :disabled="!ready">
          {{ overlayOn ? '关闭叠框' : '叠框' }}
        </button>
        <button class="btn tiny" @click="toggleRecord" :disabled="!ready || !canRecord">
          {{ recording ? `停止录制(${recordSec}s)` : '录制' }}
        </button>
      </div>
    </div>

    <div class="stage" ref="stage">
      <canvas ref="canvas" class="canvas"></canvas>
      <div class="placeholder" v-if="!ready">
        <div class="line">未检测到 MJPEG 流</div>
        <div class="line small">可在监控页里切换 preset 或手填地址</div>
      </div>
    </div>

    <div class="foot" v-if="showUrls">
      <div class="row" v-if="mode === 'hstack'">
        <span class="k">左</span><input class="url" v-model="left" placeholder="left mjpg url" />
      </div>
      <div class="row" v-if="mode === 'hstack'">
        <span class="k">右</span><input class="url" v-model="right" placeholder="right mjpg url" />
      </div>
      <div class="row" v-if="mode === 'single'">
        <span class="k">流</span><input class="url" v-model="single" placeholder="mjpg url" />
      </div>
      <div class="hint">
        说明：截图/录制依赖 MJPEG 服务端开启 CORS（本项目的 `scripts/mjpeg_http_server.py` 已开启）。
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  title: { type: String, default: '视频' },
  subtitle: { type: String, default: '' },
  mode: { type: String, default: 'single' }, // single | hstack
  url: { type: String, default: '' },
  leftUrl: { type: String, default: '' },
  rightUrl: { type: String, default: '' },
  fps: { type: Number, default: 15 },
  showUrls: { type: Boolean, default: false },
  overlays: { type: Array, default: () => [] }, // single 模式叠框
  leftOverlays: { type: Array, default: () => [] }, // hstack 左半叠框
  rightOverlays: { type: Array, default: () => [] }, // hstack 右半叠框
  overlayLabel: { type: String, default: '' },
})

const emit = defineEmits(['update:url', 'update:leftUrl', 'update:rightUrl'])

const stage = ref(null)
const canvas = ref(null)

const left = ref(props.leftUrl)
const right = ref(props.rightUrl)
const single = ref(props.url)

watch(
  () => props.leftUrl,
  (v) => (left.value = v || '')
)
watch(
  () => props.rightUrl,
  (v) => (right.value = v || '')
)
watch(
  () => props.url,
  (v) => (single.value = v || '')
)

watch(left, (v) => emit('update:leftUrl', (v || '').trim()))
watch(right, (v) => emit('update:rightUrl', (v || '').trim()))
watch(single, (v) => emit('update:url', (v || '').trim()))

const effectiveLeft = computed(() => (left.value || '').trim())
const effectiveRight = computed(() => (right.value || '').trim())
const effectiveSingle = computed(() => (single.value || '').trim())

const copyValue = computed(() => {
  if (props.mode === 'hstack') {
    const items = [effectiveLeft.value, effectiveRight.value].filter(Boolean)
    return items.join(' | ')
  }
  return effectiveSingle.value
})

const ready = computed(() => {
  if (props.mode === 'hstack') return Boolean(effectiveLeft.value && effectiveRight.value)
  return Boolean(effectiveSingle.value)
})

const canRecord = computed(() => typeof canvas.value?.captureStream === 'function' && typeof MediaRecorder !== 'undefined')

let ro = null
let raf = 0
let lastDrawAt = 0
let imgL = null
let imgR = null
let imgS = null

const recording = ref(false)
const recordSec = ref(0)
let recordTimer = 0
let recorder = null
let recordChunks = []
const overlayOn = ref(true)

function ensureImages() {
  if (props.mode === 'hstack') {
    if (!imgL) imgL = new Image()
    if (!imgR) imgR = new Image()
    imgL.crossOrigin = 'anonymous'
    imgR.crossOrigin = 'anonymous'
    imgL.decoding = 'async'
    imgR.decoding = 'async'
    imgL.src = effectiveLeft.value || ''
    imgR.src = effectiveRight.value || ''
    return
  }
  if (!imgS) imgS = new Image()
  imgS.crossOrigin = 'anonymous'
  imgS.decoding = 'async'
  imgS.src = effectiveSingle.value || ''
}

function setCanvasSize() {
  const el = stage.value
  const cv = canvas.value
  if (!el || !cv) return
  const rect = el.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  const w = Math.max(2, Math.floor(rect.width * dpr))
  const h = Math.max(2, Math.floor(rect.height * dpr))
  if (cv.width !== w) cv.width = w
  if (cv.height !== h) cv.height = h
}

function drawCover(ctx, img, x, y, w, h) {
  const iw = img.naturalWidth || img.width || 0
  const ih = img.naturalHeight || img.height || 0
  if (!iw || !ih) return false
  const scale = Math.max(w / iw, h / ih)
  const sw = iw * scale
  const sh = ih * scale
  const dx = x + (w - sw) / 2
  const dy = y + (h - sh) / 2
  ctx.drawImage(img, dx, dy, sw, sh)
  return { ok: true, dx, dy, scale }
}

function drawBoxes(ctx, dets, map, label = '') {
  if (!overlayOn.value || !map || !map.ok) return
  if (!Array.isArray(dets) || !dets.length) return
  ctx.save()
  ctx.lineWidth = 2
  ctx.font = '14px sans-serif'
  ctx.textBaseline = 'top'
  for (const d of dets) {
    const bbox = d?.bbox
    if (!Array.isArray(bbox) || bbox.length < 4) continue
    const [x1, y1, x2, y2] = bbox.map((v) => Number(v || 0))
    const sx1 = map.dx + x1 * map.scale
    const sy1 = map.dy + y1 * map.scale
    const sx2 = map.dx + x2 * map.scale
    const sy2 = map.dy + y2 * map.scale
    const w = Math.max(1, sx2 - sx1)
    const h = Math.max(1, sy2 - sy1)
    ctx.strokeStyle = 'rgba(0,255,120,0.95)'
    ctx.strokeRect(sx1, sy1, w, h)
    const cls = (d?.label || d?.name || d?.cls) ?? ''
    const score = d?.score != null ? Number(d.score).toFixed(2) : ''
    const text = `${label ? label + ' ' : ''}${cls}${score ? ' ' + score : ''}`
    if (text.trim()) {
      const pad = 4
      const tw = ctx.measureText(text).width
      ctx.fillStyle = 'rgba(0,0,0,0.55)'
      ctx.fillRect(sx1, Math.max(0, sy1 - 18), tw + pad * 2, 18)
      ctx.fillStyle = '#eafff2'
      ctx.fillText(text, sx1 + pad, Math.max(0, sy1 - 18) + 2)
    }
  }
  ctx.restore()
}

function loop(ts) {
  raf = requestAnimationFrame(loop)
  const cv = canvas.value
  if (!cv || !ready.value) return
  const interval = 1000 / Math.max(1, props.fps || 15)
  if (ts - lastDrawAt < interval) return
  lastDrawAt = ts

  const ctx = cv.getContext('2d')
  if (!ctx) return
  const w = cv.width
  const h = cv.height
  ctx.fillStyle = '#000'
  ctx.fillRect(0, 0, w, h)

  try {
    if (props.mode === 'hstack') {
      const half = Math.floor(w / 2)
      const mapL = imgL ? drawCover(ctx, imgL, 0, 0, half, h) : null
      const mapR = imgR ? drawCover(ctx, imgR, half, 0, w - half, h) : null
      const okL = Boolean(mapL && mapL.ok)
      const okR = Boolean(mapR && mapR.ok)
      if (!okL || !okR) {
        ctx.fillStyle = 'rgba(255,255,255,0.75)'
        ctx.font = `${Math.max(12, Math.floor(h / 24))}px sans-serif`
        ctx.fillText('等待左右画面...', 20, 40)
      }
      drawBoxes(ctx, props.leftOverlays || [], mapL, props.overlayLabel || 'L')
      drawBoxes(ctx, props.rightOverlays || [], mapR, props.overlayLabel || 'R')
      return
    }
    if (imgS) {
      const map = drawCover(ctx, imgS, 0, 0, w, h)
      const ok = Boolean(map && map.ok)
      if (!ok) {
        ctx.fillStyle = 'rgba(255,255,255,0.75)'
        ctx.font = `${Math.max(12, Math.floor(h / 24))}px sans-serif`
        ctx.fillText('等待画面...', 20, 40)
      }
      drawBoxes(ctx, props.overlays || [], map, props.overlayLabel || '')
    }
  } catch (e) {
    // 可能因 CORS tainted 导致绘制/导出失败
  }
}

async function copyUrl() {
  const v = copyValue.value
  if (!v) return
  try {
    await navigator.clipboard.writeText(v)
  } catch (e) {
    // fallback
    const ta = document.createElement('textarea')
    ta.value = v
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
}

function openUrl() {
  const v = copyValue.value
  if (!v) return
  const url = v.split('|')[0].trim()
  window.open(url, '_blank', 'noopener,noreferrer')
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 5000)
}

async function snapshot() {
  const cv = canvas.value
  if (!cv) return
  const now = new Date()
  const name = `snapshot_${props.title}_${now.toISOString().replace(/[:.]/g, '-')}.png`
  try {
    cv.toBlob((blob) => blob && downloadBlob(blob, name), 'image/png')
  } catch (e) {
    // ignore
  }
}

function pickMimeType() {
  const candidates = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm']
  for (const m of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) return m
  }
  return ''
}

function startRecord() {
  const cv = canvas.value
  if (!cv || recording.value || !canRecord.value) return
  recordChunks = []
  const stream = cv.captureStream(Math.max(5, props.fps || 15))
  const mimeType = pickMimeType()
  recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
  recorder.ondataavailable = (e) => e.data && e.data.size && recordChunks.push(e.data)
  recorder.onstop = () => {
    const blob = new Blob(recordChunks, { type: recorder?.mimeType || 'video/webm' })
    const now = new Date()
    const name = `record_${props.title}_${now.toISOString().replace(/[:.]/g, '-')}.webm`
    downloadBlob(blob, name)
  }
  recorder.start(500)
  recording.value = true
  recordSec.value = 0
  recordTimer = window.setInterval(() => (recordSec.value += 1), 1000)
}

function stopRecord() {
  if (!recording.value) return
  recording.value = false
  if (recordTimer) window.clearInterval(recordTimer)
  recordTimer = 0
  try {
    recorder?.stop()
  } catch (e) {
    // ignore
  }
  recorder = null
}

function toggleRecord() {
  if (recording.value) stopRecord()
  else startRecord()
}

onMounted(() => {
  ensureImages()
  setCanvasSize()
  raf = requestAnimationFrame(loop)
  if (stage.value && typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(() => setCanvasSize())
    ro.observe(stage.value)
  } else {
    window.addEventListener('resize', setCanvasSize)
  }
})

watch([effectiveLeft, effectiveRight, effectiveSingle, () => props.mode], () => {
  ensureImages()
})

onBeforeUnmount(() => {
  if (raf) cancelAnimationFrame(raf)
  raf = 0
  if (ro) ro.disconnect()
  ro = null
  window.removeEventListener('resize', setCanvasSize)
  stopRecord()
})
</script>

<style scoped>
.panel { display: grid; gap: 10px; }
.head { display:flex; justify-content:space-between; align-items:center; gap: 10px; }
.title { display:flex; align-items:baseline; gap: 10px; }
.meta { font-size: 12px; color: #9aa0a6; }
.actions { display:flex; gap: 8px; flex-wrap: wrap; justify-content:flex-end; }
.btn.tiny {
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.06);
  color: var(--text);
  cursor: pointer;
}
.btn.tiny:disabled { opacity: 0.5; cursor: not-allowed; }
.stage {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 12px;
  overflow: hidden;
  background: #0e0e0e;
  border: 1px solid var(--border);
  box-shadow: 0 12px 32px rgba(0,0,0,0.35);
}
.canvas { width: 100%; height: 100%; display: block; background: #000; }
.placeholder {
  position:absolute; inset:0;
  display:flex; flex-direction:column; justify-content:center; align-items:center;
  color: rgba(255,255,255,0.75);
  background: rgba(0,0,0,0.35);
  text-align:center;
  padding: 12px;
}
.placeholder .line { font-size: 14px; }
.placeholder .small { font-size: 12px; opacity: 0.8; margin-top: 4px; }
.foot { display: grid; gap: 6px; }
.row { display:flex; gap: 8px; align-items:center; }
.k { width: 28px; font-size: 12px; color: #9aa0a6; }
.url {
  flex: 1;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(20,20,20,0.7);
  color: var(--text);
}
.hint { font-size: 12px; color: #9aa0a6; }
</style>
