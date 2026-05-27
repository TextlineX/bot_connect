<template>
  <section class="settings page">
    <div class="card-head">
      <h2>设置</h2>
      <span class="pill">config v{{ state.configVersion || 0 }}</span>
    </div>

    <div class="card-grid">
      <div class="card">
        <div class="card-head"><h3>连接与角色</h3></div>
        <div class="field">
          <label>WS 地址</label>
          <input v-model="state.wsUrl" placeholder="ws://127.0.0.1:8765" />
        </div>
        <div class="field">
          <label>机器人热点 IP（从机）</label>
          <input v-model="state.networkRobotHost" placeholder="192.168.88.88" />
        </div>
        <div class="field duo">
          <div>
            <label>本机 ID</label>
            <input v-model="state.robotId" placeholder="controller" />
          </div>
          <div>
            <label>本机角色</label>
            <select v-model="state.role">
              <option value="controller">controller</option>
              <option value="master">master</option>
              <option value="slave">slave</option>
            </select>
          </div>
        </div>
        <div class="field duo">
          <div>
            <label>大脑 master</label>
            <input v-model="state.brainTargetRobot" placeholder="master-01" />
          </div>
          <div>
            <label>控制 slave</label>
            <input v-model="state.controlTargetRobot" placeholder="slave-01" />
          </div>
        </div>
        <div class="field row switch-line">
          <label>自动重连 WS</label>
          <button class="toggle-btn" :class="{on: state.autoReconnect}" @click="toggleReconnect">
            <span class="knob"></span>
          </button>
        </div>
        <div class="hint">
          说明：该 IP 用于 `http://<PC_IP>:8765/proxy/robot?...` 视频/资源代理白名单。
          控制/动作默认发给 slave，ASR/AI 默认发给 master。保存会写入后端 config.json 并同步主从。
        </div>
        <button class="primary" @click="syncAllConfig">保存并同步全部配置</button>
      </div>

      <div class="card">
        <div class="card-head"><h3>主机 AI</h3></div>
        <div class="field row switch-line">
          <label>启用主机 AI 解析</label>
          <button class="toggle-btn" :class="{on: state.settings.masterAiEnabled}" @click="toggleMasterAi">
            <span class="knob"></span>
          </button>
        </div>
        <div class="field row switch-line">
          <label>message 自动 TTS 播报</label>
          <button class="toggle-btn" :class="{on: state.settings.masterAiAutoTts}" @click="toggleMasterAiAutoTts">
            <span class="knob"></span>
          </button>
        </div>
        <div class="field row switch-line">
          <label>允许 AI 执行动作（危险）</label>
          <button class="toggle-btn" :class="{on: state.settings.masterAiAllowActionExecution}" @click="toggleMasterAiAllowActionExecution">
            <span class="knob"></span>
          </button>
        </div>
        <div class="field row switch-line">
          <label>AI 动作转发到 slave</label>
          <button class="toggle-btn" :class="{on: state.settings.masterAiForward}" @click="toggleMasterAiForward">
            <span class="knob"></span>
          </button>
        </div>
        <div class="field row switch-line">
          <label>AI 行为锁</label>
          <button class="toggle-btn" :class="{on: state.settings.masterAiBehaviorLockEnabled}" @click="toggleMasterAiLock">
            <span class="knob"></span>
          </button>
        </div>
        <div class="field duo">
          <div>
            <label>锁超时 (秒)</label>
            <input type="number" min="1" max="120" v-model.number="state.settings.masterAiBehaviorLockTimeoutSec" />
          </div>
          <div>
            <label>转发目标 robot_id</label>
            <input v-model="state.settings.masterAiForwardTarget" placeholder="slave-01" />
          </div>
        </div>
        <div class="field">
          <label>AI TTS 目标 robot_id</label>
          <input v-model="state.settings.masterAiTtsTarget" placeholder="slave-01" />
        </div>
        <div class="hint">
          行为锁开启后，上一次 AI 产生的 slave 请求未返回 result 前，新的 ASR/AI 动作会被跳过。
          开关对应 config/master_config.json 与 backend/config.json → master.ai.* 字段。
        </div>
        <button class="primary" @click="syncAllConfig">保存并同步全部配置</button>
      </div>

      <div class="card">
        <div class="card-head"><h3>后端自动语音回复</h3></div>
        <div class="field row switch-line">
          <label>启用自动语音回复</label>
          <button class="toggle-btn" :class="{on: state.settings.autoAiReply}" @click="toggleAi">
            <span class="knob"></span>
          </button>
        </div>
        <div class="field">
          <label>回复前缀</label>
          <input v-model="state.settings.aiPrefix" placeholder="收到：" />
        </div>
        <div class="field">
          <label>TTS 目标机器人</label>
          <input v-model="state.settings.ttsRobotId" placeholder="master-01" />
        </div>
        <div class="hint">这是后端的旧式自动回复开关，AI 主流程仍由 master 负责。</div>
        <button class="primary" @click="syncAllConfig">保存并同步全部配置</button>
      </div>

      <div class="card">
        <div class="card-head"><h3>显示</h3></div>
        <div class="field row">
          <label><input type="checkbox" v-model="state.settings.uiAutoScroll" /> 自动滚动日志/ASR</label>
        </div>
        <div class="divider"></div>
        <div class="field row switch-line" v-for="flag in featureFlagList" :key="flag.key">
          <label>{{ flag.label }}</label>
          <button class="toggle-btn" :class="{on: state.featureFlags[flag.key] !== false}" @click="toggleFeatureFlag(flag.key)">
            <span class="knob"></span>
          </button>
        </div>
        <div class="hint">
          显隐开关会写入 backend/config.json → frontend.feature_flags.*，前端导航与面板按此锁定/隐藏。
        </div>
        <button class="primary" @click="syncAllConfig">保存并同步全部配置</button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { useStore } from '../store'

const { state, pushConfigSync } = useStore()

const featureFlagList = [
  { key: 'showDashboard', label: '仪表盘' },
  { key: 'showAI', label: 'AI 面板' },
  { key: 'showControl', label: '控制面板' },
  { key: 'showASR', label: 'ASR 面板' },
  { key: 'showTTS', label: 'TTS 面板' },
  { key: 'showAudio', label: '音频区块' },
  { key: 'showMonitor', label: '监控区块' },
  { key: 'showLogs', label: '日志区块' },
  { key: 'showSettings', label: '设置入口' },
]

function toggleAi() {
  state.settings.autoAiReply = !state.settings.autoAiReply
}
function toggleMasterAi() {
  state.settings.masterAiEnabled = !state.settings.masterAiEnabled
}
function toggleMasterAiAutoTts() {
  state.settings.masterAiAutoTts = !state.settings.masterAiAutoTts
}
function toggleMasterAiAllowActionExecution() {
  state.settings.masterAiAllowActionExecution = !state.settings.masterAiAllowActionExecution
}
function toggleMasterAiForward() {
  state.settings.masterAiForward = !state.settings.masterAiForward
}
function toggleMasterAiLock() {
  state.settings.masterAiBehaviorLockEnabled = !state.settings.masterAiBehaviorLockEnabled
}
function toggleReconnect() {
  state.autoReconnect = !state.autoReconnect
}
function toggleFeatureFlag(key) {
  state.featureFlags[key] = state.featureFlags[key] === false ? true : !state.featureFlags[key]
}

function syncAllConfig() {
  state.targetRobot = state.brainTargetRobot
  pushConfigSync()
}
</script>

<style scoped>
.switch-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.toggle-btn {
  position: relative;
  width: 58px;
  height: 28px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.15);
  background: linear-gradient(145deg, #1a1f27, #11151c);
  cursor: pointer;
  transition: all .2s ease;
  padding: 0;
}
.toggle-btn .knob {
  position: absolute;
  top: 3px; left: 3px;
  width: 22px; height: 22px;
  border-radius: 50%;
  background: #d1d5db;
  box-shadow: 0 4px 14px rgba(0,0,0,0.3);
  transition: all .2s ease;
}
.toggle-btn.on {
  background: linear-gradient(145deg, #1ed760, #13c557);
  box-shadow: 0 6px 18px rgba(30,215,96,0.35);
}
.toggle-btn.on .knob { transform: translateX(30px); background: #fff; }
.divider {
  height: 1px;
  width: 100%;
  margin: 12px 0;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent);
}
</style>
