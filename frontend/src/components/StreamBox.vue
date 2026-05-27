<template>
  <div class="stream-box">
    <input class="url" :placeholder="placeholder" :value="url" @input="onInput" />
    <div class="preset-row" v-if="streamInfo.presets && streamInfo.presets.length">
      <button
        v-for="p in streamInfo.presets"
        :key="p.url"
        class="preset-btn"
        @click="$emit('update:url', proxyRobotUrl(p.url))"
      >
        {{ p.label || p.topic || p.url }}
      </button>
    </div>
    <div class="hint auto" v-if="usingAuto">未手动填写地址，自动使用机器人上报的默认流</div>
    <div class="preview" v-if="effectiveUrl">
      <WebRtcPlayer v-if="isWebRtc" :url="effectiveUrl" />
      <video v-else-if="isVideo" :src="effectiveUrl" autoplay playsinline controls muted></video>
      <img v-else-if="isMjpg" :src="effectiveUrl" alt="mjpg" />
      <iframe v-else :src="effectiveUrl" frameborder="0" allow="autoplay" referrerpolicy="no-referrer"></iframe>
    </div>
    <div class="stream-meta" v-if="streamInfo && (streamInfo.topic || streamInfo.rtspUrl || streamInfo.hlsUrl)">
      <div class="hint" v-if="streamInfo.topic">源话题：{{ streamInfo.topic }}</div>
      <div class="hint" v-if="streamInfo.rtspUrl">RTSP：{{ streamInfo.rtspUrl }}</div>
      <div class="hint" v-if="streamInfo.hlsUrl">HLS：{{ streamInfo.hlsUrl }}</div>
    </div>
    <div class="hint" v-else-if="!effectiveUrl">输入可直接在浏览器播放的 http(s)/whep/m3u8/mp4/webm/mjpg 地址</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useStore } from '../store'
import WebRtcPlayer from './WebRtcPlayer.vue'

const props = defineProps({
  url: { type: String, default: '' },
  autoUrl: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  streamInfo: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:url'])

const { state } = useStore()

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

const effectiveUrl = computed(() => proxyRobotUrl((props.url || props.autoUrl || '').trim()))
const isWebRtc = computed(() => effectiveUrl.value.toLowerCase().startsWith('http') && effectiveUrl.value.toLowerCase().includes('/whep'))
const isVideo = computed(() => {
  const u = effectiveUrl.value.toLowerCase()
  return u.startsWith('http') && (u.includes('.m3u8') || u.includes('.mp4') || u.includes('.webm'))
})
const isMjpg = computed(() => effectiveUrl.value.toLowerCase().includes('mjpg') || effectiveUrl.value.toLowerCase().includes('mjpeg'))
const usingAuto = computed(() => !props.url && !!props.autoUrl)

function onInput(e) {
  emit('update:url', proxyRobotUrl(e.target.value))
}
</script>

<style scoped>
.stream-box { display: grid; gap: 10px; }
.url {
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(20,20,20,0.7);
  color: var(--text);
}
.preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.preset-btn {
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.06);
  color: var(--text);
  cursor: pointer;
}
.preview {
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 12px;
  overflow: hidden;
  background: #0e0e0e;
  border: 1px solid var(--border);
  box-shadow: 0 12px 32px rgba(0,0,0,0.35);
}
.preview video,
.preview img,
.preview iframe {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  background: #000;
}
.hint { font-size: 12px; color: #9aa0a6; }
.hint.auto { color: #b6e3ff; }
.stream-meta { display: grid; gap: 4px; }
</style>
