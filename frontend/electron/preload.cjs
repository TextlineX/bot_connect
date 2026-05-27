// preload.js - 安全桥接主进程和渲染进程
const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  arch: process.arch,
  versions: process.versions,
  defaultWsUrl: process.env.BOT_CONNECT_DEFAULT_WS_URL || '',
})
