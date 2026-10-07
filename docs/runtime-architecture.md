# 当前运行架构

本说明根据 2026-10-06 的 WSL 运行实例整理。它概括插件协作关系，不是完整 AstrBot 配置导出。

| 层 | 插件/组件 | 责任 |
|---|---|---|
| 平台 | AstrBot + QQ 连接器 | 收发消息与插件运行 |
| 消息入口与主对话 | 消息防抖、天使之心、主模型、Splitter | 连续消息合并、群聊唤醒/是否接话、角色对话、长回复分段 |
| 记忆与关系 | 天使之魂、Self Learning、羽笔 | 用户记忆/笔记、好感度和情绪、表达学习、世界书/RAG/状态栏 |
| 现实时间与日常 | Life Scheduler、TimeAwareness | 每日活动/穿搭、当前时段、上次聊天间隔、日历/节假日 |
| 照片 | Airi Gallery + 林小满个人接口 | 保存图库；模型决定发送时由个人接口委托发送一张 |
| 图片与社区互动 | Smart ImageChat Hub、画境拾珍 | 表情包搜索/斗图/采集；外部插画检索、签到与排行 |
| 音频 | TTS Emotion Router、MusicDL、Music Pro | 情绪语音路由、音乐搜索/下载/发送 |
| 安全与成本 | 阿瓦隆、大肥鱼钱包、Cost Control | 输入/输出审核、关键词/重复拦截、峰谷模型调用管理和成本控制 |
| 定时发送 | Scheduled Sender | 一次性、周期性、Cron 计划和候选消息轮换 |
| 管理命令 | AstrBot + Builtin Commands Extension | 会话、模型、插件和管理员管理 |
| 娱乐与实用工具 | Essential | 搜番、动漫图片、喜报/悲报、Minecraft 状态、一言、吃什么、早晚安统计等 |

照片从图库静态挑选；当前方案不依赖实时文生图或改图链路。个人接口仅向 LLM 提供 `send_xiaoman_photo()`；具体发送由 Airi Gallery 完成。普通对话仍由主对话插件处理，图库浏览及管理员维护命令由 Airi 单独处理。

配置模板按插件维度放在 [`../configs/runtime/`](../configs/runtime/)，所有文件与职责见 [`configuration-reference.md`](configuration-reference.md)。

记忆库、好感度数据库、每日状态、用户会话和表情包学习结果是实例数据。复刻时创建空数据，让自己的机器人重新积累；不要导入本仓库操作者的实例数据。

按具体机制和当前配置逐项解释，见 [`mechanisms.md`](mechanisms.md)。
