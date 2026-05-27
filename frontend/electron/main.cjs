// Electron 主进程（用于打包 EXE 与本地一键启动）
const { app, BrowserWindow, shell } = require('electron')
const path = require('path')
const fs = require('fs')
const { spawn } = require('child_process')

const IS_DEV = !app.isPackaged
const WS_HOST = process.env.WS_HOST || '0.0.0.0'
const WS_PORT = Number(process.env.WS_PORT || 8765)

let win = null
let backendProc = null
let viteProc = null

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

function appPaths() {
  // app.getAppPath():
  // - dev：frontend/
  // - packaged：app.asar 内的 frontend（取决于 electron-builder 的 app 目录）
  const appPath = app.getAppPath()
  const repoRoot = path.resolve(appPath, '..') // dev: <repo>/

  const backendDirDev = path.join(repoRoot, 'backend')
  const frontendDistDev = path.join(repoRoot, 'frontend', 'dist')

  // packaged：extraResources
  const backendDirProd = path.join(process.resourcesPath, 'backend')
  const frontendDistProd = path.join(process.resourcesPath, 'frontend_dist')

  const dataRoot = path.join(app.getPath('userData'), 'bot_connect')
  const backendDataDir = path.join(dataRoot, 'backend')

  return {
    backendDir: app.isPackaged ? backendDirProd : backendDirDev,
    frontendDist: app.isPackaged ? frontendDistProd : frontendDistDev,
    backendDataDir,
  }
}

async function waitForBackendReady(port) {
  const url = `http://127.0.0.1:${port}/health`
  for (let i = 0; i < 50; i++) {
    try {
      const res = await fetch(url, { method: 'GET' })
      if (res && res.ok) return true
    } catch {
      // ignore
    }
    await sleep(200)
  }
  return false
}

function findVitePort(repoRoot) {
  try {
    const viteConfigPath = path.join(repoRoot, 'frontend', 'vite.config.js')
    if (fs.existsSync(viteConfigPath)) {
      const content = fs.readFileSync(viteConfigPath, 'utf-8')
      const m = content.match(/port:\s*(\d+)/)
      if (m) return parseInt(m[1])
    }
  } catch {
    // ignore
  }
  return 5173
}

function startVite() {
  const repoRoot = path.resolve(app.getAppPath(), '..')
  const vitePort = findVitePort(repoRoot)
  const isWin = process.platform === 'win32'
  const viteBin = isWin ? 'vite.cmd' : 'vite'
  const viteScript = path.join(repoRoot, 'frontend', 'node_modules', '.bin', viteBin)

  const args = ['--host', '127.0.0.1', '--port', String(vitePort)]
  const spawnArgs = isWin ? args : [viteScript, ...args]
  const cmd = isWin ? viteScript : 'node'

  return new Promise((resolve, reject) => {
    viteProc = spawn(cmd, spawnArgs, {
      cwd: path.join(repoRoot, 'frontend'),
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: isWin,
      detached: false,
    })

    let resolved = false
    viteProc.stdout.on('data', (data) => {
      const line = data.toString()
      process.stdout.write('[vite] ' + line)
      if (!resolved && (line.includes('Local:') || line.includes('ready in'))) {
        resolved = true
        resolve(`http://127.0.0.1:${vitePort}`)
      }
    })
    viteProc.stderr.on('data', (data) => {
      process.stderr.write('[vite] ' + data.toString())
    })
    viteProc.on('error', reject)

    setTimeout(() => {
      if (!resolved) resolve(`http://127.0.0.1:${vitePort}`)
    }, 15000)
  })
}

function startBackend() {
  const { backendDir, frontendDist, backendDataDir } = appPaths()
  const entry = path.join(backendDir, 'server.js')
  if (!fs.existsSync(entry)) {
    console.log('[electron] backend server.js not found, skipping:', entry)
    return
  }

  fs.mkdirSync(backendDataDir, { recursive: true })

  // 用 Electron 自己的二进制当 Node 跑（避免用户本地没装 node）
  const repoRoot = path.resolve(app.getAppPath(), '..')
  const fallbackNodePath = [
    path.join(backendDir, 'node_modules'),
    path.join(repoRoot, 'frontend', 'node_modules'),
  ].join(path.delimiter)

  const env = {
    ...process.env,
    ELECTRON_RUN_AS_NODE: '1',
    WS_HOST,
    WS_PORT: String(WS_PORT),
    BOT_CONNECT_DATA_DIR: backendDataDir,
    BOT_CONNECT_FRONTEND_DIST: frontendDist,
    NODE_PATH: [process.env.NODE_PATH || '', fallbackNodePath].filter(Boolean).join(path.delimiter),
  }

  backendProc = spawn(process.execPath, [entry], {
    cwd: backendDir,
    env,
    stdio: 'inherit',
    windowsHide: true,
  })

  backendProc.on('exit', (code) => {
    console.log('[electron] backend exited', code)
    backendProc = null
  })
  backendProc.on('error', (e) => console.error('[electron] backend error:', e))
  console.log('[electron] backend started')
}

function stopBackend() {
  if (!backendProc) return
  try {
    backendProc.kill()
  } catch {
    // ignore
  }
  backendProc = null
}

function stopVite() {
  if (!viteProc) return
  try {
    viteProc.kill()
  } catch {
    // ignore
  }
  viteProc = null
}

function createWindow(url) {
  win = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 980,
    minHeight: 680,
    title: 'Bot Connect',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  win.webContents.setWindowOpenHandler(({ url: u }) => {
    shell.openExternal(u)
    return { action: 'deny' }
  })

  win.loadURL(url)
  win.on('closed', () => {
    win = null
  })

  if (IS_DEV && process.env.ELECTRON_OPEN_DEVTOOLS === '1') {
    win.webContents.openDevTools()
  }
}

app.whenReady().then(async () => {
  // 给渲染进程一个“默认 WS 地址”（开发模式下 Vite 与后端端口不同）
  if (!process.env.BOT_CONNECT_DEFAULT_WS_URL) {
    process.env.BOT_CONNECT_DEFAULT_WS_URL = `ws://127.0.0.1:${WS_PORT}`
  }

  if (IS_DEV) {
    // 开发：Vite 热更新 + 本地后端（WS:8765）
    startBackend()
    const url = await startVite()
    createWindow(url)
    return
  }

  // 生产：Electron 启动后端，然后加载 http://127.0.0.1:<port>/
  // 这样同一台机器上其他设备也能直接访问：http://<PC_IP>:<port>/
  startBackend()
  await waitForBackendReady(WS_PORT)
  createWindow(`http://127.0.0.1:${WS_PORT}/`)
})

app.on('before-quit', () => {
  stopVite()
  stopBackend()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow(`http://127.0.0.1:${WS_PORT}/`)
})
