---
layout: home

hero:
  name: "Bot Connect"
  text: "机器人控制与通信平台"
  tagline: "Vue 前端 · WebSocket 通信 · 主从机器人架构"
  actions:
    - theme: brand
      text: 快速开始
      link: /project/overview
    - theme: alt
      text: 部署指南
      link: /project/pc-deploy

features:
  - title: 前后端分离
    details: Vue 3 前端控制台 + Node.js WebSocket 中转服务，浏览器或 Electron 客户端均可
    link: /project/overview
    linkText: 查看架构

  - title: 主从机器人架构
    details: Master（大脑）负责 AI/ASR/TTS，Slave（身体）负责执行运动和视频推流
    link: /project/overview
    linkText: 了解架构

  - title: 语音交互
    details: 麦克风录音 → ASR 语音识别 → AI 指令解析 → TTS 语音播报，端到端语音控制
    link: /project/monitor
    linkText: 了解 ASR/TTS

  - title: 视频推流
    details: Slave 摄像头通过 MJPEG HTTP 推流，浏览器直接播放 stream.mjpg
    link: /project/robot-deploy
    linkText: 配置视频流

  - title: 预设动作
    details: 挥手、握手、敬礼、鞠躬、跳舞等预设动作，通过 action_router 统一调度
    link: /project/actions
    linkText: 查看动作列表

  - title: Electron 客户端
    details: 可打包为桌面客户端，解决浏览器 HTTP 环境下的音频 API 限制问题
    link: /project/pc-deploy
    linkText: Electron 部署

footer:
  message: 本文档基于 AGIBOT X2 平台构建
  copyright: MIT License
---

<div style="text-align:center; padding: 2rem 0; color: #666;">
  <p>📡 项目代码托管于 <strong>Gitee 私有仓库</strong> | 📖 文档托管于 <strong>Cloudflare Pages</strong></p>
</div>
