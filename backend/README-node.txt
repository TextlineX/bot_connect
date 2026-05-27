后端改为 Node.js 版本已就位：
- 位置：H:\Project\Bot\bot_connect\backend
  - server.js  (基于 ws)
  - package.json (依赖 ws + dotenv)

运行后端
1) cd H:\Project\Bot\bot_connect\backend
2) npm install
3) npm start   # 默认监听 ws://0.0.0.0:8765（并在同端口提供 http://0.0.0.0:8765/health）
可选环境变量：WS_HOST、WS_PORT、AUTH_TOKEN（开启鉴权）。
可选（打包/只读目录场景）：
- BOT_CONNECT_DATA_DIR：配置与 uploads 可写目录
- BOT_CONNECT_FRONTEND_DIST：前端构建产物目录（用于 HTTP 静态托管）

主/从客户端文件保持不变（Python），指向同一个 WS_URL 即可直接互通。

下一步可测试：
- 启动 server.js
- 启动 master/slave Python 客户端
- 用之前的控制脚本发送 cmd_vel，观察打印即可确认链路。
