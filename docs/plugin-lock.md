# 当前插件锁定清单

来自 2026-10-06 正在运行的 AstrBot 实例。`已随仓库分发`表示 `plugins/bundled/` 中保存了该运行版本源码快照；安装器不会覆盖目标机器已有目录。`需单独安装`表示本项目没有分发该插件源码，部署者需从 AstrBot 插件市场/作者仓库安装。

| 功能 | 插件 | 当前运行版本 | 源码 | 上游 |
|---|---|---:|---|---|
| 主对话与唤醒 | `astrbot_plugin_angel_heart` | 2.2.7 | 已随仓库分发 | [kawayiYokami](https://github.com/kawayiYokami/astrbot_plugin_angel_heart) |
| 长期记忆 | `astrbot_plugin_angel_memory` | 1.6.14 | 已随仓库分发 | [kawayiYokami](https://github.com/kawayiYokami/astrbot_plugin_angel_memory) |
| 好感度与自主学习 | `astrbot_plugin_self_learning` | 4.4.8-explicit-affection-command-forms | 已随仓库分发（AGPL-3.0） | [NickCharlie](https://github.com/NickCharlie/astrbot_plugin_self_learning) |
| 生活日程 | `astrbot_plugin_life_scheduler` | v2.8.2-visual-identity-anchor | 已随仓库分发 | [muyouzhi6](https://github.com/muyouzhi6/astrbot_plugin_life_scheduler) |
| 照片图库 | `astrbot_plugin_airi_gallery` | v2.11.15 | 需单独安装 | [Lidure](https://github.com/Lidure/astrbot_plugin_airi_gallery) |
| 林小满照片接口 | `astrbot_plugin_xiaoman_personal_interface` | 0.2.2 | 已随仓库分发 | 本仓库 `plugins/astrbot_plugin_xiaoman_personal_interface/` |
| 语音路由 | `astrbot_plugin_tts_emotion_router` | 3.2.3 | 已随仓库分发（MIT） | [muyouzhi6](https://github.com/muyouzhi6/astrbot_plugin_tts_emotion_router) |
| 峰谷时段/播报 | `astrbot_plugin_fat_fish_wallet` | 1.2.0 | 已随仓库分发 | [foxchuqiao](https://github.com/foxchuqiao/astrbot_plugin_fat_fish_wallet) |
| 对话分段 | `astrbot_plugin_splitter` | v1.4.8 | 需单独安装 | [nuomicici](https://github.com/nuomicici/astrbot_plugin_splitter) |
| 点歌 | `astrbot_plugin_musicdl` | v0.3.0 | 已随仓库分发 | [guohuiyuan](https://github.com/guohuiyuan/astrbot_plugin_musicdl) |
| 图片理解/表情包 | `astrbot_plugin_smart_imagechat_hub` | v2.8.6 | 已随仓库分发 | [QingchenWait](https://github.com/QingchenWait/astrbot_plugin_smart_imagechat_hub) |
| 消息防抖 | `astrbot_plugin_continuous_message` | 2.9.1 | 已随仓库分发 | [aliveriver](https://github.com/aliveriver/astrbot_plugin_continuous_message) |
| 内容安全 | `astrbot_plugin_content_safety_guard` | 1.2.6 | 已随仓库分发 | [Kalospacer](https://github.com/Kalospacer/astrbot_plugin_content_safety_guard) |
| 生活时间感知 | `time_awareness` | v2.3.0 | 已随仓库分发 | [W-Wolfycz](https://github.com/W-Wolfycz/time_awareness) |
| 每日签到/查询 | `astrbot_plugin_get_px` | v3.8.0 | 已随仓库分发 | [shitianyaa](https://github.com/shitianyaa/astrbot_plugin_get_px) |
| 音乐增强 | `astrbot_plugin_music_pro` | 1.0.5 | 已随仓库分发 | [Dayanshifu](https://github.com/Dayanshifu/astrbot_plugin_music_pro) |
| 人设/知识库界面 | `astrbot_plugin_quillplus` | 5.3.1 | 已随仓库分发（AGPL-3.0） | [Nana7mi0721](https://github.com/Nana7mi0721/astrbot_plugin_quillplus) |
| 定时发送 | `astrbot_plugin_scheduled_sender` | v1.0.0 | 需单独安装 | [seelesyn](https://github.com/seelesyn/astrbot_plugin_scheduled_sender) |
| 基础命令扩展 | `builtin_commands_extension` | v0.1.0 | 已随仓库分发 | 随运行环境安装的插件包 |
| 成本控制 | `astrbot_plugin_cost_control` | 0.4.1 | 需单独安装；本地改动未分发 | [leafliber](https://github.com/leafliber/astrbot_plugin_cost_control) |
| AstrBot 必备扩展 | `astrbot_plugin_essential` | v1.1.0 | 需单独安装 | [Soulter](https://github.com/Soulter/astrbot_plugin_essential) |

源码快照不含 Git 历史。每个第三方源码目录保留上游 LICENSE；各插件按自己的许可证使用。本项目根目录 MIT 许可证只适用于林小满个人接口及本项目自有文档，不覆盖 AGPL 插件或其他第三方内容。未随仓库分发的插件需单独安装；若市场不再提供锁定版本，请从上游核对兼容版本。

当前安装的 Cost Control 工作目录基于上游提交 `2b53332`，另有 4 个本地改动文件：`_conf_schema.json`、`backend/auto_collection.py`、`backend/caption_library.py`、`backend/retrieval.py`。上游仓库没有可确认的再分发许可，因此本公开仓库不包含这 4 份派生代码；在新电脑安装的是上游插件版本，不能复现这些本地改动。Airi Gallery、Splitter、Scheduled Sender、Cost Control 和 Essential 的源码也需从各自作者渠道获取。
