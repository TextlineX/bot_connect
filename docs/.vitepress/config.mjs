import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Bot Connect',
  description: '机器人控制与通信平台文档',
  lang: 'zh-CN',
  ignoreDeadLinks: true,

  head: [
    ['link', { rel: 'icon', href: '/favicon.ico' }],
    ['meta', { name: 'theme-color', content: '#3eaf7c' }],
  ],

  themeConfig: {
    siteTitle: 'Bot Connect',

    nav: [
      { text: '首页', link: '/' },
      { text: '连接', link: '/connection/' },
      { text: '优化体验', link: '/experience/' },
      { text: '基础使用', link: '/usage/' },
      { text: '项目结构', link: '/architecture/' },
      { text: '高级进阶', link: '/advanced/' },
      { text: '更多', link: '/more/' },
      { text: '官方文档', link: '/official/' },
    ],

    sidebar: {
      '/connection/': [
        {
          text: '连接',
          items: [
            { text: 'App 连接', link: '/official/guide/robot_connection' },
            { text: '遥控手柄', link: '/official/guide/remote_controller' },
            { text: '有线网络', link: '/official/quickstart/prerequisites' },
          ],
        },
      ],
      '/experience/': [
        {
          text: '优化体验',
          items: [
            { text: 'VSCode SSH', link: '/experience/vscode-ssh' },
            { text: '双网段组网', link: '/experience/dual-network' },
          ],
        },
      ],
      '/usage/': [
        {
          text: '基础使用',
          items: [
            { text: '项目环境配置', link: '/project/overview' },
            { text: '运行示例', link: '/official/quickstart/run_example' },
            { text: '代码编写教程', link: '/official/quickstart/code_sample' },
            { text: 'ROS 2 指令', link: '/usage/ros2-commands' },
            { text: '容器环境修复', link: '/setup/container' },
            { text: '远程调试与同步', link: '/setup/remote-debug' },
          ],
        },
      ],
      '/project/': [
        {
          text: '项目文档',
          items: [
            { text: '总览与架构', link: '/project/overview' },
            { text: 'PC端部署', link: '/project/pc-deploy' },
            { text: '机器人端部署', link: '/project/robot-deploy' },
            { text: '真机启动手册', link: '/project/start-manual' },
            { text: '同步与运行指南', link: '/project/sync' },
            { text: '监控面板说明', link: '/project/monitor' },
            { text: '动作测试与映射', link: '/project/actions' },
            { text: '运动控制', link: '/project/motion' },
            { text: '视觉（YOLO）', link: '/project/vision' },
            { text: 'Master模块能力清单', link: '/project/modules' },
            { text: '目录与排查速查', link: '/project/troubleshooting' },
          ],
        },
      ],
      '/architecture/': [
        {
          text: '项目结构介绍',
          items: [
            { text: '总览与架构', link: '/architecture/overview' },
            { text: 'PC端部署', link: '/project/pc-deploy' },
            { text: '机器人端部署', link: '/project/robot-deploy' },
            { text: '真机启动手册', link: '/project/start-manual' },
            { text: '同步与运行指南', link: '/project/sync' },
            { text: '监控面板说明', link: '/project/monitor' },
            { text: '动作测试与映射', link: '/project/actions' },
            { text: '运动控制', link: '/project/motion' },
            { text: '视觉（YOLO）', link: '/project/vision' },
            { text: 'Master模块能力清单', link: '/project/modules' },
          ],
        },
      ],
      '/advanced/': [
        {
          text: '传感器',
          items: [
            { text: '常用话题速查', link: '/sensors/topic-cheatsheet' },
            { text: '3D激光雷达', link: '/sensors/lidar' },
            { text: '关节执行器', link: '/sensors/joints' },
            { text: '右目视觉相机', link: '/sensors/camera-right' },
            { text: '语音音频', link: '/sensors/audio' },
            { text: '胸部惯导', link: '/sensors/imu-chest' },
            { text: '躯干惯导', link: '/sensors/imu-torso' },
            { text: '传感器数据监控', link: '/sensors/sensor-monitor' },
            { text: '电池BMS', link: '/sensors/battery' },
            { text: '电源管理单元', link: '/sensors/pmu' },
            { text: '运动控制', link: '/sensors/motion' },
            { text: '系统监控诊断', link: '/sensors/diagnostics' },
          ],
        },
        {
          text: 'SLAM',
          items: [
            { text: 'FAST-LIO算法对接', link: '/slam/fast-lio' },
            { text: '雷达点云解码优化', link: '/slam/lidar-optimization' },
          ],
        },
        {
          text: '代码示例',
          items: [
            { text: 'Python 示例', link: '/official/examples/python/' },
            { text: 'C++ 示例', link: '/official/examples/cpp/' },
          ],
        },
      ],
      '/more/': [
        {
          text: '更多',
          items: [
            { text: '二次开发指南', link: '/development/guide' },
            { text: '传感器编程规范', link: '/development/sensor-code' },
            { text: '常见问题', link: '/official/faq/' },
          ],
        },
      ],
      '/slam/': [
        {
          text: 'SLAM算法',
          items: [
            { text: 'FAST-LIO算法对接', link: '/slam/fast-lio' },
            { text: '雷达点云解码优化', link: '/slam/lidar-optimization' },
          ],
        },
      ],
      '/development/': [
        {
          text: '开发规范',
          items: [
            { text: '二次开发指南', link: '/development/guide' },
            { text: '传感器编程规范', link: '/development/sensor-code' },
          ],
        },
      ],
      '/official/examples/python/': [
        {
          text: 'Python 示例',
          items: [
            { text: '总览', link: '/official/examples/python/' },
            { text: '获取机器人模式', link: '/official/examples/python/robot-mode-get' },
            { text: '设置机器人模式', link: '/official/examples/python/robot-mode-set' },
            { text: '设置机器人动作', link: '/official/examples/python/robot-action-set' },
            { text: '夹爪控制', link: '/official/examples/python/gripper' },
            { text: '灵巧手控制', link: '/official/examples/python/hand' },
            { text: '注册二开输入源', link: '/official/examples/python/input-register' },
            { text: '获取当前输入源', link: '/official/examples/python/input-get' },
            { text: '控制机器人走跑', link: '/official/examples/python/locomotion' },
            { text: '关节电机控制', link: '/official/examples/python/joint' },
            { text: '键盘控制机器人', link: '/official/examples/python/motion-keyboard' },
            { text: '拍照', link: '/official/examples/python/camera-photo' },
            { text: '相机推流示例集', link: '/official/examples/python/camera-stream' },
            { text: '头部触摸传感器数据订阅', link: '/official/examples/python/touch-sensor' },
            { text: '激光雷达数据订阅', link: '/official/examples/python/lidar' },
            { text: '播放视频', link: '/official/examples/python/video-playback' },
            { text: '媒体文件播放', link: '/official/examples/python/media-playback' },
            { text: 'TTS（文字转语音）', link: '/official/examples/python/tts' },
            { text: '麦克风数据接收', link: '/official/examples/python/microphone' },
            { text: '表情控制', link: '/official/examples/python/emoji' },
            { text: 'LED 灯带控制', link: '/official/examples/python/led' },
          ],
        },
      ],
      '/official/examples/cpp/': [
        {
          text: 'C++ 示例',
          items: [
            { text: '总览', link: '/official/examples/cpp/' },
            { text: '获取机器人模式', link: '/official/examples/cpp/robot-mode-get' },
            { text: '设置机器人模式', link: '/official/examples/cpp/robot-mode-set' },
            { text: '设置机器人动作', link: '/official/examples/cpp/robot-action-set' },
            { text: '夹爪控制', link: '/official/examples/cpp/gripper' },
            { text: '灵巧手控制', link: '/official/examples/cpp/hand' },
            { text: '注册二开输入源', link: '/official/examples/cpp/input-register' },
            { text: '获取当前输入源', link: '/official/examples/cpp/input-get' },
            { text: '机器人走跑控制', link: '/official/examples/cpp/locomotion' },
            { text: '关节电机控制', link: '/official/examples/cpp/joint' },
            { text: '键盘控制机器人', link: '/official/examples/cpp/motion-keyboard' },
            { text: '拍照', link: '/official/examples/cpp/camera-photo' },
            { text: '相机推流示例集', link: '/official/examples/cpp/camera-stream' },
            { text: '头部触摸传感器数据订阅', link: '/official/examples/cpp/touch-sensor' },
            { text: '激光雷达数据订阅', link: '/official/examples/cpp/lidar' },
            { text: '播放视频', link: '/official/examples/cpp/video-playback' },
            { text: '媒体文件播放', link: '/official/examples/cpp/media-playback' },
            { text: 'TTS（文字转语音）', link: '/official/examples/cpp/tts' },
            { text: '麦克风数据接收', link: '/official/examples/cpp/microphone' },
            { text: '表情控制', link: '/official/examples/cpp/emoji' },
            { text: 'LED 灯带控制', link: '/official/examples/cpp/led' },
          ],
        },
      ],
      '/official/examples/': [
        {
          text: '示例总览',
          items: [
            { text: '示例代码总览', link: '/official/examples/' },
            { text: 'Python 示例总览', link: '/official/examples/python/' },
            { text: 'C++ 示例总览', link: '/official/examples/cpp/' },
          ],
        },
      ],
      '/official/': [
        {
          text: '导览',
          items: [
            { text: '官方文档导览', link: '/official/' },
          ],
        },
        {
          text: '产品与硬件',
          items: [
            { text: '部件名称', link: '/official/about/part_name' },
            { text: '机器人规格', link: '/official/about/robot_specifications' },
            { text: '板载计算机', link: '/official/about/onboard_computer' },
            { text: '用户调试接口', link: '/official/about/user_debug_interface' },
            { text: 'SDK 接口', link: '/official/about/SDK_interface' },
            { text: '传感器视野', link: '/official/about/sensor_fov' },
            { text: '关节名称与限制', link: '/official/about/joint_name_and_limit' },
            { text: '坐标系统', link: '/official/about/coordinate_system' },
          ],
        },
        {
          text: '操作指南',
          items: [
            { text: '开机指南', link: '/official/guide/start_up_guide' },
            { text: '机器人连接', link: '/official/guide/robot_connection' },
            { text: '遥控器', link: '/official/guide/remote_controller' },
            { text: '关机', link: '/official/guide/shutdown' },
          ],
        },
        {
          text: '快速开始',
          items: [
            { text: '准备与依赖', link: '/official/quickstart/prerequisites' },
            { text: '运行示例', link: '/official/quickstart/run_example' },
            { text: '代码编写教程', link: '/official/quickstart/code_sample' },
          ],
        },
        {
          text: '接口参考',
          items: [
            { text: '模式切换', link: '/official/interface/control_mod/modeswitch' },
            { text: '走跑控制', link: '/official/interface/control_mod/locomotion' },
            { text: 'MC 控制信号', link: '/official/interface/control_mod/MC_control' },
            { text: '预设动作', link: '/official/interface/control_mod/preset_motion' },
            { text: '末端执行器', link: '/official/interface/control_mod/endeffector' },
            { text: '关节控制', link: '/official/interface/control_mod/joint_control' },
            { text: '灯光控制', link: '/official/interface/interactor/lights' },
            { text: '屏幕控制', link: '/official/interface/interactor/screen' },
            { text: '语音控制', link: '/official/interface/interactor/voice' },
            { text: '传感器 HAL', link: '/official/interface/hal/sensor' },
            { text: '电源管理 HAL', link: '/official/interface/hal/pmu' },
            { text: '故障管理', link: '/official/interface/FASM/fault' },
            { text: 'Sudo 工具', link: '/official/interface/FASM/sudo' },
            { text: '视觉感知', link: '/official/interface/perception/vision' },
            { text: 'SLAM 感知', link: '/official/interface/perception/SLAM' },
          ],
        },
        {
          text: '代码示例',
          items: [
            { text: '示例代码总览', link: '/official/examples/' },
            { text: 'Python 示例总览', link: '/official/examples/python/' },
            { text: '获取机器人模式（Python）', link: '/official/examples/python/robot-mode-get' },
            { text: '设置机器人模式（Python）', link: '/official/examples/python/robot-mode-set' },
            { text: '设置机器人动作（Python）', link: '/official/examples/python/robot-action-set' },
            { text: '夹爪控制（Python）', link: '/official/examples/python/gripper' },
            { text: '灵巧手控制（Python）', link: '/official/examples/python/hand' },
            { text: '注册二开输入源（Python）', link: '/official/examples/python/input-register' },
            { text: '获取当前输入源（Python）', link: '/official/examples/python/input-get' },
            { text: '控制机器人走跑（Python）', link: '/official/examples/python/locomotion' },
            { text: '关节电机控制（Python）', link: '/official/examples/python/joint' },
            { text: '键盘控制机器人（Python）', link: '/official/examples/python/motion-keyboard' },
            { text: '拍照（Python）', link: '/official/examples/python/camera-photo' },
            { text: '相机推流示例集（Python）', link: '/official/examples/python/camera-stream' },
            { text: '头部触摸传感器数据订阅（Python）', link: '/official/examples/python/touch-sensor' },
            { text: '激光雷达数据订阅（Python）', link: '/official/examples/python/lidar' },
            { text: '播放视频（Python）', link: '/official/examples/python/video-playback' },
            { text: '媒体文件播放（Python）', link: '/official/examples/python/media-playback' },
            { text: 'TTS（Python）', link: '/official/examples/python/tts' },
            { text: '麦克风数据接收（Python）', link: '/official/examples/python/microphone' },
            { text: '表情控制（Python）', link: '/official/examples/python/emoji' },
            { text: 'LED 灯带控制（Python）', link: '/official/examples/python/led' },
            { text: 'C++ 示例总览', link: '/official/examples/cpp/' },
            { text: '获取机器人模式（C++）', link: '/official/examples/cpp/robot-mode-get' },
            { text: '设置机器人模式（C++）', link: '/official/examples/cpp/robot-mode-set' },
            { text: '设置机器人动作（C++）', link: '/official/examples/cpp/robot-action-set' },
            { text: '夹爪控制（C++）', link: '/official/examples/cpp/gripper' },
            { text: '灵巧手控制（C++）', link: '/official/examples/cpp/hand' },
            { text: '注册二开输入源（C++）', link: '/official/examples/cpp/input-register' },
            { text: '获取当前输入源（C++）', link: '/official/examples/cpp/input-get' },
            { text: '机器人走跑控制（C++）', link: '/official/examples/cpp/locomotion' },
            { text: '关节电机控制（C++）', link: '/official/examples/cpp/joint' },
            { text: '键盘控制机器人（C++）', link: '/official/examples/cpp/motion-keyboard' },
            { text: '拍照（C++）', link: '/official/examples/cpp/camera-photo' },
            { text: '相机推流示例集（C++）', link: '/official/examples/cpp/camera-stream' },
            { text: '头部触摸传感器数据订阅（C++）', link: '/official/examples/cpp/touch-sensor' },
            { text: '激光雷达数据订阅（C++）', link: '/official/examples/cpp/lidar' },
            { text: '播放视频（C++）', link: '/official/examples/cpp/video-playback' },
            { text: '媒体文件播放（C++）', link: '/official/examples/cpp/media-playback' },
            { text: 'TTS（C++）', link: '/official/examples/cpp/tts' },
            { text: '麦克风数据接收（C++）', link: '/official/examples/cpp/microphone' },
            { text: '表情控制（C++）', link: '/official/examples/cpp/emoji' },
            { text: 'LED 灯带控制（C++）', link: '/official/examples/cpp/led' },
          ],
        },
        {
          text: 'FAQ',
          items: [
            { text: '常见问题', link: '/official/faq/' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/TextlineX/bot-connect-docs' },
    ],

    search: {
      provider: 'local',
      options: { detailedView: true },
    },

    editLink: {
      pattern: 'https://github.com/TextlineX/bot-connect-docs/edit/main/docs/:path',
      text: '在 GitHub 上编辑此页',
    },

    footer: {
      message: '📡 Gitee 私有仓库 | 📖 Cloudflare Pages | 基于 AGIBOT X2 平台构建',
      copyright: 'MIT License',
    },
  },

  vue: {
    template: {
      transformAssetUrls: false,
    },
  },
  markdown: {
    lineNumbers: true,
    config(md) {
      // 允许 Markdown 中的内联 HTML，用于首页提示等自定义块
      md.set({ html: true })
    },
  },
  cleanUrls: true,
})
