// 基于 ws 的轻量 WebSocket 路由服务器
// 运行：npm install && npm start
// 环境变量：
//   WS_HOST (默认 0.0.0.0)
//   WS_PORT (默认 8765)
//   AUTH_TOKEN (可选，开启后客户端 hello 必须携带 token)
// 生产建议：前置 NGINX/Caddy 做 TLS 反代；或直接用 Cloudflare Tunnel。

require('dotenv').config();
const http = require('http');
const https = require('https');
const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');
const { spawn, spawnSync } = require('child_process');

const HOST = process.env.WS_HOST || '0.0.0.0';
const PORT = Number(process.env.WS_PORT || 8765);
const AUTH_TOKEN = process.env.AUTH_TOKEN || '';
const PING_INTERVAL = 20000; // ms
const DEFAULT_ROBOT_HOST = '192.168.88.88';
const MAX_PROXY_CONNECTIONS = Number(process.env.MAX_PROXY_CONNECTIONS || 20);
let activeProxyConnections = 0;

// Electron 打包场景：backend 代码可能在只读目录（如 resources/ 或 asar 外），
// 需要把 config/uploads 等可写数据放到用户数据目录。
const DATA_DIR = process.env.BOT_CONNECT_DATA_DIR
  ? path.resolve(process.env.BOT_CONNECT_DATA_DIR)
  : __dirname;

const CONFIG_PATH = path.join(DATA_DIR, 'config.json');
const uploadDir = path.join(DATA_DIR, 'uploads');
if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir, { recursive: true });

// 可选：由 Electron/部署脚本指定前端构建产物目录（用于 HTTP 静态托管）
const FRONTEND_DIST = process.env.BOT_CONNECT_FRONTEND_DIST
  ? path.resolve(process.env.BOT_CONNECT_FRONTEND_DIST)
  : path.join(__dirname, '..', 'frontend', 'dist');
const DEFAULT_FEATURE_FLAGS = {
  showControl: true,
  showTTS: true,
  showASR: true,
  showAI: true,
  showAudio: true,
  showLogs: true,
  showMonitor: true,
  showSettings: true,
};
const BROADCAST_TYPES = new Set([
  'status',
  'capabilities',
  'result',
  'ai_result',
  'master_config_ack',
  'audio_saved',
  'audio_available',
]);

function deepMerge(base, extra) {
  const merged = { ...(base || {}) };
  Object.entries(extra || {}).forEach(([key, value]) => {
    if (
      merged[key]
      && typeof merged[key] === 'object'
      && !Array.isArray(merged[key])
      && value
      && typeof value === 'object'
      && !Array.isArray(value)
    ) {
      merged[key] = deepMerge(merged[key], value);
      return;
    }
    merged[key] = value;
  });
  return merged;
}

function defaultConfig() {
  return {
    version: 1,
    updated_at: new Date().toISOString(),
    network: {
      // 机器人热点模式下，运控/开发计算单元默认 IP
      robot_host: DEFAULT_ROBOT_HOST,
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
      feature_flags: { ...DEFAULT_FEATURE_FLAGS },
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
  };
}

function normalizeConfig(raw) {
  const base = defaultConfig();
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return base;
  }
  const legacyBackend = {};
  if (raw.auto_ai_reply !== undefined) legacyBackend.auto_ai_reply = raw.auto_ai_reply;
  if (raw.ai_prefix !== undefined) legacyBackend.ai_prefix = raw.ai_prefix;
  if (raw.tts_robot_id !== undefined) legacyBackend.tts_robot_id = raw.tts_robot_id;
  const merged = deepMerge(base, raw);
  if (Object.keys(legacyBackend).length) {
    merged.backend = deepMerge(merged.backend, legacyBackend);
  }
  merged.version = Number(merged.version || 1);
  merged.updated_at = merged.updated_at || new Date().toISOString();
  return merged;
}

function loadConfig() {
  try {
    const raw = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'));
    return normalizeConfig(raw);
  } catch {
    // Electron 打包：优先使用用户可写目录；若首次启动可用内置 config.json 做种子
    try {
      const fallbackPath = path.join(__dirname, 'config.json');
      if (DATA_DIR !== __dirname && fs.existsSync(fallbackPath)) {
        const raw = JSON.parse(fs.readFileSync(fallbackPath, 'utf-8'));
        const next = normalizeConfig(raw);
        saveConfig(next);
        return next;
      }
    } catch {
      // ignore
    }
    return defaultConfig();
  }
}

function saveConfig(cfg) {
  try {
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(cfg, null, 2));
  } catch (e) {
    log('save config error', e.message);
  }
}

function bumpConfigVersion(nextConfig) {
  const current = Number(config?.version || 0);
  const next = normalizeConfig(nextConfig);
  next.version = Math.max(current + 1, Number(next.version || 0) || 0);
  next.updated_at = new Date().toISOString();
  return next;
}

function backendConfig() {
  return normalizeConfig(config).backend || {};
}

let config = loadConfig();

function robotHost() {
  const fromEnv = (process.env.ROBOT_HOST || '').trim();
  if (fromEnv) return fromEnv;
  const fromCfg = (config?.network?.robot_host || '').trim();
  return fromCfg || DEFAULT_ROBOT_HOST;
}

function isHopByHopHeader(key = '') {
  const k = String(key || '').toLowerCase();
  return [
    'connection',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'te',
    'trailers',
    'transfer-encoding',
    'upgrade',
  ].includes(k);
}

function writeJson(res, code, payload) {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(payload));
}

function startProxyGuard(res) {
  if (activeProxyConnections >= MAX_PROXY_CONNECTIONS) {
    writeJson(res, 429, { ok: false, error: 'too many proxy connections' });
    return false;
  }
  activeProxyConnections += 1;
  const cleanup = () => {
    if (cleanup._done) return;
    cleanup._done = true;
    activeProxyConnections = Math.max(0, activeProxyConnections - 1);
  };
  res.on('close', cleanup);
  res.on('finish', cleanup);
  return true;
}

function proxyToTarget(req, res, target) {
  const allowedHost = robotHost();
  const proto = target.protocol || '';
  if (proto !== 'http:' && proto !== 'https:') {
    writeJson(res, 400, { ok: false, error: 'only http/https allowed' });
    return true;
  }
  if (target.hostname !== allowedHost) {
    writeJson(res, 403, { ok: false, error: `host not allowed (allowed=${allowedHost})` });
    return true;
  }

  if (!startProxyGuard(res)) return true;

  const client = proto === 'https:' ? https : http;
  const reqHeaders = { ...(req.headers || {}) };
  delete reqHeaders['accept-encoding'];
  delete reqHeaders['host'];

  const proxyReq = client.request(
    {
      method: req.method,
      hostname: target.hostname,
      port: target.port || (proto === 'https:' ? 443 : 80),
      path: `${target.pathname || '/'}${target.search || ''}`,
      headers: reqHeaders,
      timeout: 15000,
    },
    (proxyRes) => {
      const headers = {};
      Object.entries(proxyRes.headers || {}).forEach(([k, v]) => {
        if (!k || isHopByHopHeader(k)) return;
        headers[k] = v;
      });
      headers['Access-Control-Allow-Origin'] = '*';
      headers['X-Bot-Connect-Proxy'] = 'robot';
      res.writeHead(proxyRes.statusCode || 502, headers);
      proxyRes.pipe(res);
    }
  );

  proxyReq.on('timeout', () => {
    try { proxyReq.destroy(new Error('timeout')); } catch {}
  });
  proxyReq.on('error', (e) => {
    const msg = (e && e.message) ? e.message : 'proxy error';
    if (!res.headersSent) writeJson(res, 502, { ok: false, error: msg });
    else {
      try { res.end(); } catch {}
    }
  });

  req.pipe(proxyReq);
  return true;
}

function handleRobotProxy(req, res, parsedRequestUrl) {
  // 形态：/proxy/robot?url=http%3A%2F%2F192.168.88.88%3A8000%2Fstream.mjpg
  if (parsedRequestUrl.pathname !== '/proxy/robot') return false;

  // CORS 预检（即便同源也没坏处）
  if ((req.method || '').toUpperCase() === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS',
      'Access-Control-Allow-Headers': '*',
      'Access-Control-Max-Age': '86400',
    });
    res.end();
    return true;
  }

  const rawUrl = parsedRequestUrl.searchParams.get('url') || '';
  if (!rawUrl) {
    writeJson(res, 400, { ok: false, error: 'missing url' });
    return true;
  }

  let target = null;
  try {
    target = new URL(rawUrl);
  } catch {
    writeJson(res, 400, { ok: false, error: 'invalid url' });
    return true;
  }

  return proxyToTarget(req, res, target);
}

function handleRobotProxyMjpg(req, res, parsedRequestUrl) {
  // 更安全的形态：/proxy/robot/mjpg?port=8000&path=/stream.mjpg
  if (parsedRequestUrl.pathname !== '/proxy/robot/mjpg') return false;

  if ((req.method || '').toUpperCase() === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS',
      'Access-Control-Allow-Headers': '*',
      'Access-Control-Max-Age': '86400',
    });
    res.end();
    return true;
  }

  const port = Number(parsedRequestUrl.searchParams.get('port') || 8000);
  let pathname = parsedRequestUrl.searchParams.get('path') || '';
  pathname = String(pathname || '').trim();
  if (!pathname) {
    writeJson(res, 400, { ok: false, error: 'missing path' });
    return true;
  }
  if (!pathname.startsWith('/')) pathname = '/' + pathname;
  const host = robotHost();
  const rawUrl = `http://${host}:${port}${pathname}`;
  let target = null;
  try {
    target = new URL(rawUrl);
  } catch {
    writeJson(res, 400, { ok: false, error: 'invalid path' });
    return true;
  }
  return proxyToTarget(req, res, target);
}

// robot_id -> ws
const clients = new Map();
// 缓存音频分片：robot_id -> {chunks:Buffer[], bytes:number, mime:string, ts:number, timer:Timeout, target:string, session:any, seq:any}
const pendingAudio = new Map();
const pythonBin = process.env.PYTHON_BIN || 'python';
const ffmpegBin = process.env.FFMPEG_BIN || 'ffmpeg';
const modelPath = process.env.MODEL_PATH;
const ASR_MODE = (process.env.ASR_MODE || 'auto').toLowerCase(); // auto | local | master | off
if (ASR_MODE === 'off') {
  console.log('[ASR] ASR_MODE=off，本地识别已禁用');
} else if (ASR_MODE === 'master') {
  console.log('[ASR] ASR_MODE=master，本地识别由 master 负责，后端不启 worker');
} else if (modelPath) {
  console.log(`[ASR] MODEL_PATH=${modelPath}, PYTHON_BIN=${pythonBin}`);
} else {
  console.log('[ASR] MODEL_PATH 未设置，本地识别禁用（若需本地识别请设置 MODEL_PATH 或 ASR_MODE=local）');
}

function guessRole(robotId = '') {
  const rid = String(robotId || '').trim().toLowerCase();
  if (rid.startsWith('master')) return 'master';
  if (rid.startsWith('slave')) return 'slave';
  if (rid.startsWith('controller')) return 'controller';
  return 'robot';
}

function buildRoleConfig(role) {
  if (role === 'master') {
    return {
      robot_id: config.master?.robot_id || 'master-01',
      config_version: config.version,
      ai: deepMerge({}, config.master?.ai || {}),
    };
  }
  if (role === 'slave') {
    return {
      robot_id: config.slave?.robot_id || 'slave-01',
      config_version: config.version,
      routing: {
        control_robot_id: config.frontend?.targets?.control_robot_id || 'slave-01',
        brain_robot_id: config.frontend?.targets?.brain_robot_id || 'master-01',
      },
    };
  }
  if (role === 'controller') {
    return {
      robot_id: config.frontend?.controller_robot_id || 'controller',
      config_version: config.version,
      frontend: deepMerge({}, config.frontend || {}),
      backend: deepMerge({}, config.backend || {}),
    };
  }
  return {
    config_version: config.version,
  };
}

function buildConfigSyncPayload(reason = 'sync', role = null) {
  return {
    type: 'config_sync',
    robot_id: 'server',
    role: 'server',
    config_version: Number(config.version || 0),
    ts: Date.now() / 1000,
    payload: {
      reason,
      version: Number(config.version || 0),
      updated_at: config.updated_at || new Date().toISOString(),
      config: deepMerge({}, config),
      role,
      role_config: buildRoleConfig(role),
    },
  };
}

function sendConfigSync(ws, reason = 'sync') {
  if (!ws) return;
  send(ws, buildConfigSyncPayload(reason, ws._role || guessRole(ws._rid)));
}

function syncAllClients(reason = 'sync') {
  for (const [, sock] of clients.entries()) {
    sendConfigSync(sock, reason);
  }
}

function decorateIncoming(fromRid, data) {
  const sender = clients.get(fromRid);
  const sourceRole = data.source_role || sender?._role || guessRole(fromRid);
  const decorated = { ...data };
  if (!decorated.robot_id) decorated.robot_id = fromRid;
  if (!decorated.source_robot_id) decorated.source_robot_id = fromRid || decorated.robot_id || '';
  if (!decorated.source_role) decorated.source_role = sourceRole;
  if (!decorated.config_version) {
    decorated.config_version = Number(sender?._configVersion || config.version || 0);
  }
  if (decorated.target_robot) {
    const targetWs = clients.get(decorated.target_robot);
    if (targetWs && !decorated.target_role) {
      decorated.target_role = targetWs._role || guessRole(decorated.target_robot);
    }
  }
  return decorated;
}

// 持久化 ASR worker
let asrWorker = null;
function startAsrWorker() {
  if (ASR_MODE === 'off' || ASR_MODE === 'master') return;
  if (!modelPath) {
    if (ASR_MODE === 'local') log('[ASR] 本地识别强制开启但 MODEL_PATH 缺失，跳过启动');
    return;
  }
  const workerPath = path.join(__dirname, 'asr_worker.py');
  asrWorker = spawn(pythonBin, [workerPath], {
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env, MODEL_PATH: modelPath },
  });
  asrWorker.on('error', (err) => log('asr_worker spawn error', err.message));
  let stderrBuf = '';
  asrWorker.stderr.on('data', c => { stderrBuf += c.toString(); });
  asrWorker.stdout.on('data', chunk => {
    chunk.toString().split(/\r?\n/).forEach(line => {
      if (!line.trim()) return;
      try {
        const res = JSON.parse(line);
        const text = (res.text || '').trim();
        if (res.error) {
          log('asr_worker error', res.error);
        }
        const payload = {
          type: 'asr_text',
          text,
          robot_id: res.robot_id || 'asr-local',
          ts: Date.now() / 1000,
          detail: text ? 'ok' : 'empty',
          session: res.session || null,
          seq: res.seq || null,
          final: Boolean(res.final),
        };
        log(`asr_text(local): ${text || '<empty>'}`);
        for (const [, sock] of clients.entries()) {
          send(sock, payload);
        }
      } catch (e) {
        log('asr_worker parse error', e.message);
      }
    });
  });
  asrWorker.on('close', (code) => {
    if (stderrBuf) log('asr_worker stderr', stderrBuf.trim());
    log(`asr_worker exit ${code}, respawn in 3s`);
    setTimeout(startAsrWorker, 3000);
  });
}
startAsrWorker();

function log(...args) { console.log(new Date().toISOString(), ...args); }

function send(ws, obj) {
  if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function broadcast(obj, excludeRid = null) {
  for (const [rid, sock] of clients.entries()) {
    if (excludeRid && rid === excludeRid) continue;
    send(sock, obj);
  }
}

function isRawPcmMime(mime = '') {
  const lower = String(mime || '').toLowerCase();
  return lower.startsWith('audio/raw') || lower.startsWith('audio/pcm') || lower.includes('s16_le');
}

function register(ws, hello) {
  const { robot_id: rid, token } = hello;
  if (!rid) throw new Error('missing robot_id');
  if (AUTH_TOKEN && token !== AUTH_TOKEN) throw new Error('invalid token');
  clients.set(rid, ws);
  ws._rid = rid;
  ws._role = hello.role || guessRole(rid);
  ws._configVersion = Number(hello.config_version || 0);
  log(`robot ${rid} connected role=${ws._role} cfg=${ws._configVersion} online=${clients.size}`);
  send(ws, {
    type: 'ack',
    robot_id: rid,
    role: ws._role,
    config_version: Number(config.version || 0),
  });
  sendConfigSync(ws, ws._configVersion === Number(config.version || 0) ? 'hello' : 'stale');
}

function unregister(ws) {
  if (ws._rid && clients.get(ws._rid) === ws) {
    clients.delete(ws._rid);
    log(`robot ${ws._rid} disconnected, online=${clients.size}`);
  }
}

function route(fromRid, data) {
  const message = decorateIncoming(fromRid, data);
  const sender = clients.get(fromRid);
  if (sender && message.config_version !== undefined) {
    sender._configVersion = Number(message.config_version || sender._configVersion || 0);
  }

  if (
    sender
    && Number(message.config_version || 0) < Number(config.version || 0)
    && message.type !== 'config_sync_ack'
  ) {
    sendConfigSync(sender, 'stale');
  }

  if (message.type === 'audio_upload') {
    handleAudioUpload(fromRid, message);
    return;
  }
  if (message.type === 'config_get') {
    sendConfigSync(sender, 'requested');
    return;
  }
  if (message.type === 'config_sync_ack') {
    if (sender) {
      sender._configVersion = Number(message.config_version || sender._configVersion || config.version || 0);
    }
    return;
  }
  if (message.type === 'config_update') {
    if (message.payload && typeof message.payload === 'object') {
      const nextPayload = message.payload.app_config && typeof message.payload.app_config === 'object'
        ? message.payload.app_config
        : message.payload;
      config = bumpConfigVersion(deepMerge(config, nextPayload));
      saveConfig(config);
      log('config updated', JSON.stringify({ version: config.version, by: fromRid }));
      syncAllClients('config_update');
    }
    return;
  }
  if (message.type === 'master_config_update') {
    if (message.payload && typeof message.payload === 'object') {
      const partial = {
        master: {
          robot_id: config.master?.robot_id || 'master-01',
          ai: deepMerge({}, message.payload.ai || message.payload),
        },
      };
      config = bumpConfigVersion(deepMerge(config, partial));
      saveConfig(config);
      log('master config updated', JSON.stringify({ version: config.version, by: fromRid }));
      syncAllClients('master_config_update');
    }
    return;
  }
  if (message.type === 'asr_text') {
    const text = message.text || (message.payload && message.payload.text) || '';
    if (!text || !text.trim()) {
      // 空文本不广播，避免覆盖有效结果
      log(`asr_text from ${fromRid} skipped (empty)`);
      return;
    }
    log(`asr_text from ${fromRid}: ${text}`);
    for (const [, sock] of clients.entries()) send(sock, message);
    // 可选：自动 AI 回复 -> TTS
    const cfg = backendConfig();
    if (cfg.auto_ai_reply) {
      const ttsText = `${cfg.ai_prefix || ''}${text}`.trim();
      const target = cfg.tts_robot_id || 'master-01';
      const sock = clients.get(target);
      if (sock) {
        send(sock, {
          type: 'exec',
          action: 'tts',
          payload: { text: ttsText },
          robot_id: target,
          source_robot_id: fromRid,
          source_role: message.source_role,
          config_version: Number(config.version || 0),
          ts: Date.now() / 1000,
        });
        log(`auto TTS -> ${target}: ${ttsText}`);
      } else {
        log(`auto TTS target ${target} offline`);
      }
    }
    return;
  }
  if (BROADCAST_TYPES.has(message.type)) {
    broadcast(message, fromRid);
    log(`broadcast ${message.type} from ${fromRid}`);
    return;
  }
  const target = message.target_robot;
  if (target) {
    const t = clients.get(target);
    if (t) send(t, message);
    else log(`target ${target} offline, drop ${message.type}`);
  } else {
    log(`recv ${fromRid}: ${message.type}`);
  }
}

function guessContentType(filePath) {
  const ext = path.extname(filePath || '').toLowerCase();
  return {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webm': 'video/webm',
    '.mp4': 'video/mp4',
    '.ico': 'image/x-icon',
  }[ext] || 'application/octet-stream';
}

function serveFrontend(req, res) {
  try {
    const u = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);
    let pathname = decodeURIComponent(u.pathname || '/');

    // 机器人热点侧资源代理：让“其它设备只连正常网”也能看机器人视频/拉取资源
    if (pathname === '/proxy/robot') {
      if (handleRobotProxy(req, res, u)) return;
    }
    if (pathname === '/proxy/robot/mjpg') {
      if (handleRobotProxyMjpg(req, res, u)) return;
    }

    if (pathname === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: true, ts: Date.now() }));
      return;
    }

    if (!FRONTEND_DIST || !fs.existsSync(FRONTEND_DIST)) {
      res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Bot Connect backend is running.\nfrontend dist not found.\n');
      return;
    }

    if (pathname === '/' || pathname === '') pathname = '/index.html';

    // 防止目录穿越：只允许 dist 下的文件
    const abs = path.resolve(FRONTEND_DIST, '.' + pathname);
    const distAbs = path.resolve(FRONTEND_DIST);
    if (!abs.startsWith(distAbs)) {
      res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Forbidden');
      return;
    }

    // SPA：非文件请求回退 index.html
    let target = abs;
    if (!fs.existsSync(target) || fs.statSync(target).isDirectory()) {
      target = path.join(FRONTEND_DIST, 'index.html');
    }

    const buf = fs.readFileSync(target);
    res.writeHead(200, { 'Content-Type': guessContentType(target) });
    res.end(buf);
  } catch (e) {
    res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Internal Server Error');
  }
}

const server = http.createServer(serveFrontend);
const wss = new WebSocket.Server({ server });
server.listen(PORT, HOST, () => {
  log(`HTTP+WebSocket server on http://${HOST}:${PORT} (ws on same port)`);
});

function handleAudioUpload(fromRid, data) {
  try {
    const payload = data.payload || {};
    const b64 = payload.data;
    if (!b64) {
      log('audio_upload missing data');
      return;
    }
    const mime = (payload.mime || '').toLowerCase();
    const isFinal = payload.final === true;
    const buf = Buffer.from(b64, 'base64');

    if (isRawPcmMime(mime)) {
      handleRawPcmUpload(fromRid, data, payload, buf, mime, isFinal);
      return;
    }

    let entry = pendingAudio.get(fromRid);
    if (!entry) {
      entry = {
        chunks: [],
        bytes: 0,
        mime,
        ts: Date.now(),
        timer: null,
        target: data.target_robot || 'master-01',
        session: payload.session || null,
        seq: payload.seq || null,
      };
    }
    entry.chunks.push(buf);
    entry.bytes += buf.length;
    if (mime) entry.mime = mime;
    entry.ts = Date.now();
    entry.target = data.target_robot || entry.target || 'master-01';
    entry.session = payload.session ?? entry.session ?? null;
    entry.seq = payload.seq ?? entry.seq ?? null;
    pendingAudio.set(fromRid, entry);

    if (entry.timer) clearTimeout(entry.timer);
    // 若前端未标记 final，则在 1200ms 未收到新分片时自动终止，避免长时间挂起
    entry.timer = setTimeout(() => finalizePendingAudio(fromRid, entry, 'timeout'), 1200);

    if (!isFinal) {
      log(`audio_upload chunk from ${fromRid} bytes=${buf.length} cached total=${entry.bytes}`);
      return;
    }

    finalizePendingAudio(fromRid, entry, 'final');
  } catch (e) {
    log('audio_upload error', e.message);
  }
}

function handleRawPcmUpload(fromRid, data, payload, buf, mime, isFinal) {
  try {
    log(`audio_upload pcm from ${fromRid} bytes=${buf.length} final=${isFinal}`);

    const ws = clients.get(fromRid);
    if (ws) {
      send(ws, {
        type: 'audio_saved',
        size: buf.length,
        robot_id: fromRid,
        session: payload.session || null,
        seq: payload.seq || null,
        final: isFinal,
      });
    }

    if (modelPath && asrWorker && asrWorker.stdin.writable) {
      log(`asr_worker pcm bytes=${buf.length} (raw ${mime || 'unknown'})`);
      asrWorker.stdin.write(JSON.stringify({
        data: buf.toString('base64'),
        robot_id: fromRid,
        session: payload.session || null,
        seq: payload.seq || null,
        final: isFinal,
      }) + '\n');
    }

    forwardMergedAudio(
      fromRid,
      buf,
      mime,
      data.target_robot || 'master-01',
      payload.session || null,
      payload.seq || null,
      isFinal
    );
  } catch (e) {
    log('audio_upload raw pcm error', e.message);
  }
}

function finalizePendingAudio(fromRid, entry, reason = 'final') {
  try {
    if (!entry || !entry.chunks || !entry.chunks.length) return;
    pendingAudio.delete(fromRid);
    if (entry.timer) clearTimeout(entry.timer);

    // 合并完整音频
    const merged = Buffer.concat(entry.chunks);
    const mime = entry.mime || 'audio/webm';
    const ext = mime.includes('webm') ? 'webm' : mime.includes('wav') ? 'wav' : mime.includes('ogg') ? 'ogg' : 'raw';
    const filename = `${Date.now()}_${fromRid}.${ext}`;
    const filepath = path.join(uploadDir, filename);
    fs.writeFileSync(filepath, merged);
    log(`audio_upload saved ${filename} (${merged.length} bytes, chunks=${entry.chunks.length}, reason=${reason})`);

    // 回发给发送方确认
    const ws = clients.get(fromRid);
    if (ws) {
      send(ws, { type: 'audio_saved', file: filename, size: merged.length, robot_id: fromRid });
    }
    // 广播给其他客户端有新音频（含完整数据，方便直连使用）
    const broadcastMsg = {
      type: 'audio_upload',
      robot_id: fromRid,
      payload: {
        mime,
        data: merged.toString('base64'),
        final: true,
        session: entry.session || null,
        seq: entry.seq || null,
      },
      saved_file: filename,
      ts: Date.now()/1000
    };
    for (const [rid, sock] of clients.entries()) {
      if (rid !== fromRid) {
        send(sock, broadcastMsg);
      }
    }
    // 本地调用 Python Vosk 识别并广播 asr_text（需要设置 MODEL_PATH）
    if (modelPath && asrWorker && asrWorker.stdin.writable) {
      const pcmB64 = transcodeToPcm(merged.toString('base64'), mime);
      if (pcmB64) {
        const pcmLen = Buffer.from(pcmB64, 'base64').length;
        log(`asr_worker pcm bytes=${pcmLen} (from ${merged.length} bytes ${mime || 'unknown'})`);
        asrWorker.stdin.write(JSON.stringify({
          data: pcmB64,
          robot_id: fromRid,
          session: entry.session || null,
          seq: entry.seq || null,
          final: true
        }) + '\n');
      } else {
        log('asr_worker transcode failed, skip');
      }
    }
    // 将合并后的完整音频直接转发给目标
    forwardMergedAudio(
      fromRid,
      merged,
      mime,
      entry.target || 'master-01',
      entry.session || null,
      entry.seq || null,
      true
    );
  } catch (e) {
    log('audio_upload error', e.message);
  }
}

// 将合并后的完整音频转发给目标（默认 master-01）；音频通常较小，直接单帧发送
function forwardMergedAudio(fromRid, buffer, mime, target, session = null, seq = null, final = true) {
  const sock = clients.get(target);
  if (!sock) {
    log(`target ${target} offline, drop merged audio_upload`);
    return;
  }
  let nextMime = mime || 'audio/webm';
  let nextBuffer = buffer;
  // master 侧 ASR 目前只吃 16k mono s16le PCM，这里统一转码，避免前端录音格式影响识别链路。
  if ((sock._role || guessRole(target)) === 'master' && !isRawPcmMime(nextMime)) {
    const pcmB64 = transcodeToPcm(buffer.toString('base64'), nextMime);
    if (pcmB64) {
      nextBuffer = Buffer.from(pcmB64, 'base64');
      nextMime = 'audio/raw;rate=16000;channels=1;format=S16_LE';
      log(`forward audio transcoded for ${target}: ${mime || 'unknown'} -> ${nextMime} (${nextBuffer.length} bytes)`);
    } else {
      log(`forward audio transcode failed for ${target}, keep original mime=${nextMime}`);
    }
  }
  send(sock, {
    type: 'audio_upload',
    robot_id: fromRid,
    source_robot_id: fromRid,
    source_role: guessRole(fromRid),
    target_robot: target,
    target_role: sock._role || guessRole(target),
    config_version: Number(config.version || 0),
    payload: {
      mime: nextMime,
      data: nextBuffer.toString('base64'),
      final,
      session,
      seq,
    },
    ts: Date.now() / 1000,
  });
}

// 将任意音频 Base64 转 16k mono s16le Base64。若已是 raw/pcm 直接返回原始。
function transcodeToPcm(b64, mime = '') {
  try {
    mime = mime.toLowerCase();
    if (mime.startsWith('audio/raw') || mime.startsWith('audio/pcm') || mime.includes('s16_le')) {
      return b64;
    }
    const buf = Buffer.from(b64, 'base64');
    const r = spawnSync(ffmpegBin, [
      '-y',
      '-i', 'pipe:0',
      '-f', 's16le',
      '-acodec', 'pcm_s16le',
      '-ar', '16000',
      '-ac', '1',
      'pipe:1'
    ], { input: buf, maxBuffer: 20 * 1024 * 1024 });
    if (r.status === 0 && r.stdout && r.stdout.length) {
      return r.stdout.toString('base64');
    }
    const stderrLine = (r.stderr ? r.stderr.toString() : '').split(/\r?\n/)[0] || 'no stderr';
    log(`ffmpeg transcode exit=${r.status} msg=${stderrLine}`);
    return null;
  } catch (e) {
    log('transcode error', e.message);
    return null;
  }
}

wss.on('connection', (ws) => {
  let alive = true;
  ws.on('pong', () => { alive = true; });

  ws.once('message', (raw) => {
    try {
      const hello = JSON.parse(raw);
      if (hello.type !== 'hello') throw new Error('first message must be hello');
      register(ws, hello);
    } catch (e) {
      log('init error', e.message);
      ws.close();
      return;
    }

    ws.on('message', (raw2) => {
      try {
        const data = JSON.parse(raw2);
        route(ws._rid, data);
      } catch (e) {
        log('msg error', e.message);
      }
    });

    ws.on('close', () => unregister(ws));
    ws.on('error', () => unregister(ws));
  });

  // 心跳保活
  const interval = setInterval(() => {
    if (!alive) {
      ws.terminate();
      clearInterval(interval);
      return;
    }
    alive = false;
    ws.ping();
  }, PING_INTERVAL);
});

process.on('SIGINT', () => { log('SIGINT, close'); try { server.close(); } catch {} wss.close(); process.exit(0); });
process.on('SIGTERM', () => { log('SIGTERM, close'); try { server.close(); } catch {} wss.close(); process.exit(0); });
