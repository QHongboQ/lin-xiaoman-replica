# 插件与版本基线

下表来自 2026-10-06 正在运行的 AstrBot 实例。复刻时通过插件市场或上游仓库安装，避免把无关第三方源代码复制到本仓库。版本号是当时安装版本，不代表上游仍提供该版本。

| 功能 | 插件 | 运行版本 | 上游仓库 |
|---|---|---:|---|
| 小满个人接口 | `astrbot_plugin_xiaoman_personal_interface` | 0.2.2（本仓库源码） | [QHongboQ](https://github.com/QHongboQ/astrbot_plugin_xiaoman_personal_interface) |
| 主对话与唤醒 | `astrbot_plugin_angel_heart` | 2.2.7 | [kawayiYokami](https://github.com/kawayiYokami/astrbot_plugin_angel_heart) |
| 长期记忆 | `astrbot_plugin_angel_memory` | 1.6.14 | [kawayiYokami](https://github.com/kawayiYokami/astrbot_plugin_angel_memory) |
| 好感度与自主学习 | `astrbot_plugin_self_learning` | 4.4.8-explicit-affection-command-forms | [NickCharlie](https://github.com/NickCharlie/astrbot_plugin_self_learning) |
| 生活日程 | `astrbot_plugin_life_scheduler` | v2.8.2-visual-identity-anchor | [muyouzhi6](https://github.com/muyouzhi6/astrbot_plugin_life_scheduler) |
| 照片图库 | `astrbot_plugin_airi_gallery` | v2.11.15 | [Lidure](https://github.com/Lidure/astrbot_plugin_airi_gallery) |
| 语音路由 | `astrbot_plugin_tts_emotion_router` | 3.2.3 | [muyouzhi6](https://github.com/muyouzhi6/astrbot_plugin_tts_emotion_router) |
| 峰谷时段与日程播报 | `astrbot_plugin_fat_fish_wallet` | 1.2.0 | [foxchuqiao](https://github.com/foxchuqiao/astrbot_plugin_fat_fish_wallet) |
| 对话分段 | `astrbot_plugin_splitter` | v1.4.8 | [nuomicici](https://github.com/nuomicici/astrbot_plugin_splitter) |
| 点歌 | `astrbot_plugin_musicdl` | v0.3.0 | [guohuiyuan](https://github.com/guohuiyuan/astrbot_plugin_musicdl) |
| 图片理解与表情包 | `astrbot_plugin_smart_imagechat_hub` | v2.8.6 | [QingchenWait](https://github.com/QingchenWait/astrbot_plugin_smart_imagechat_hub) |
| 消息防抖 | `astrbot_plugin_continuous_message` | 2.9.1 | [aliveriver](https://github.com/aliveriver/astrbot_plugin_continuous_message) |

天气、平台适配、内容安全等辅助插件可按 [`docs/runtime-architecture.md`](runtime-architecture.md) 和个人部署需要补装。不要把插件运行数据当成插件源码上传。
