# 配置与运行文件清单

此索引覆盖公开仓库中的全部 20 份 JSON 模板：1 份 AstrBot 命令/基础配置模板 + 19 份插件配置模板。21 个插件里，林小满个人接口不需要独立配置，AstrBot 内置命令扩展沿用 AstrBot 全局配置；其余涉及配置的组件均有对应模板。安装器只在目标文件不存在时复制，不会覆盖已有配置。对已有实例运行安装器时，请先备份并自行比对差异。

模板不是可直接登录运行的原机镜像。为公开分享，API 密钥、Cookie、令牌、账号/群号、管理员和白名单、真实端点/路径已清空或替换；插件的数据目录、数据库、定时任务和图库状态不在这些 JSON 中。首次部署建议让对应插件版本生成默认配置，再参考模板恢复非敏感设置。

## 全局模板

| 模板 | 复制目标 | 管理内容 | 新部署要做什么 |
|---|---|---|---|
| [`astrbot_cmd_config.example.json`](../configs/runtime/astrbot_cmd_config.example.json) | `AstrBot/data/cmd_config.json` | 模型提供方/模型选择、平台和管理员、人格、时区、Dashboard、安全、知识库和系统行为等 AstrBot 全局项 | 首选管理面板完成向导并重建 Provider/平台连接；把自己的管理员 ID、人格和时区填回去。不要直接把公开模板的空 Provider 凭据当成可用配置。 |

## 插件模板逐项清单

| 插件 | 模板文件 | 配置范围 / 复刻时注意 |
|---|---|---|
| Airi Gallery | [`astrbot_plugin_airi_gallery_config.example.json`](../configs/runtime/astrbot_plugin_airi_gallery_config.example.json) | 浏览命令模式、单次/多张上限、LLM 工具、`林小满` 分类别名、权限、云图库与 Git 同步。重新填上传/Git Token、仓库地址、管理员/白名单；分类名需与导入图库一致。 |
| 天使之心 | [`astrbot_plugin_angel_heart_config.example.json`](../configs/runtime/astrbot_plugin_angel_heart_config.example.json) | 轻量分析模型、能量/节奏、回复长度、离场/回声、唤醒、群聊增强、人格规则、上下文压缩、输出清理。填实际 Provider ID 并实测群聊提及门控。 |
| 天使之魂 | [`astrbot_plugin_angel_memory_config.example.json`](../configs/runtime/astrbot_plugin_angel_memory_config.example.json) | 向量检索、会话范围、记忆行为、灵魂系统、笔记工具。配置 embedding Provider/模型及存储目录，验证不同用户/群的记忆隔离。 |
| 阿瓦隆安全守卫 | [`astrbot_plugin_content_safety_guard_config.example.json`](../configs/runtime/astrbot_plugin_content_safety_guard_config.example.json) | 输入/输出审核、群聊限制、关键词、LLM 审核、白名单、黑名单、拦截回复。配置自己的审核模型与名单，避免默认策略误拦或漏拦。 |
| 消息防抖 | [`astrbot_plugin_continuous_message_config.example.json`](../configs/runtime/astrbot_plugin_continuous_message_config.example.json) | 私聊/群聊合并窗口、白黑名单、输入状态、引用/转发、图片/VLM、QQ 卡片和链接解析。校验消息等待时间、媒体体积和需要立即响应的用户名单。 |
| Cost Control | [`astrbot_plugin_cost_control_config.example.json`](../configs/runtime/astrbot_plugin_cost_control_config.example.json) | 模板仅含启用开关；上游基线功能包括 token/费用预算、预警/停止/回退、价格规则、缓存诊断、用量归因和报告。更多策略存于插件 `plugin_data` 私有配置，不在本仓库。本机 0.4.1 有 4 处未分发源码改动，重装上游不等同原环境。 |
| Essential | [`astrbot_plugin_essential_config.example.json`](../configs/runtime/astrbot_plugin_essential_config.example.json) | 仅含字体相关设置；上游提供搜番、随机动漫图、喜报/悲报图、Minecraft 状态、一言、今日吃什么、Epic 喜加一及早晚安统计等工具，具体服务依赖和命令以安装版本 README 为准。 |
| 大肥鱼钱包 | [`astrbot_plugin_fat_fish_wallet_config.example.json`](../configs/runtime/astrbot_plugin_fat_fish_wallet_config.example.json) | 峰谷时段、受影响 Provider、管理员绕过/白名单、切换播报、提醒、事件报告及本地报告润色。检查时区、供应商、周几、时段和播报会话，避免把机器人误设成全天停机。 |
| 画境拾珍 | [`astrbot_plugin_get_px_config.example.json`](../configs/runtime/astrbot_plugin_get_px_config.example.json) | 插画来源与过滤、去重、频率限制、签到/主题商店、背景/卡片、群/私聊安全策略。Pixiv Refresh Token 等只在本机配置；核对群范围和内容过滤。 |
| Life Scheduler | [`astrbot_plugin_life_scheduler_config.example.json`](../configs/runtime/astrbot_plugin_life_scheduler_config.example.json) | 日程参考窗口、Provider、地理/视觉锚点、每周日程、旅行规则、衣柜和提示词模板。把地点控制在公开地点粒度；将衣柜视觉锚点与人格卡保持一致。 |
| Music Pro | [`astrbot_plugin_music_pro_config.example.json`](../configs/runtime/astrbot_plugin_music_pro_config.example.json) | 音源 API、音质、搜索条数。重新填 API Key/URL；公用音源可用性和音乐授权不由仓库保证。 |
| MusicDL | [`astrbot_plugin_musicdl_config.example.json`](../configs/runtime/astrbot_plugin_musicdl_config.example.json) | 下载目录、分页、并发、发送方式、转发歌曲信息、探测并发、Cookie。仅在确实需要时填 Cookie；检查下载存储空间。 |
| 羽笔 QuillPlus | [`astrbot_plugin_quillplus_config.example.json`](../configs/runtime/astrbot_plugin_quillplus_config.example.json) | RAG、本地向量检索、自主反思/聊天日志、世界书、写作素材、状态栏、拒绝规则、权限。决定是否保留聊天日志，配置向量模型和可见范围，并避免与其他记忆库重复。 |
| Scheduled Sender | [`astrbot_plugin_scheduled_sender_config.example.json`](../configs/runtime/astrbot_plugin_scheduled_sender_config.example.json) | 时区、管理员限制、每会话任务数、最小间隔和错过任务宽限时间。支持一次性、每日、工作日、间隔和 Cron 计划及候选消息轮换；任务状态保存在私有 `plugin_data`，配置模板不包含原设备具体任务。新部署应重新建立并复核收件人。 |
| Self Learning | [`astrbot_plugin_self_learning_config.example.json`](../configs/runtime/astrbot_plugin_self_learning_config.example.json) | 消息采集、自动学习、目标会话、模型、审核/过滤、风格与黑话、好感度、情绪、社交上下文、数据库、备份和记忆委托。填自己的 Provider/管理员范围；决定原始消息是否落盘与保留期限。 |
| Smart ImageChat Hub | [`astrbot_plugin_smart_imagechat_hub_config.example.json`](../configs/runtime/astrbot_plugin_smart_imagechat_hub_config.example.json) | 图库标签/检索、主动表情、采集、斗图规则、发送样式、自动备份、外部图床导入。把表情图库与角色图库分开；审查自动采集与自动接受策略。 |
| Splitter | [`astrbot_plugin_splitter_config.example.json`](../configs/runtime/astrbot_plugin_splitter_config.example.json) | 简单/高级拆分、群聊拆分、分段策略、清理、媒体回复和发送延迟。按聊天平台调整每段字数和等待间隔。 |
| TTS Emotion Router | [`astrbot_plugin_tts_emotion_router_config.example.json`](../configs/runtime/astrbot_plugin_tts_emotion_router_config.example.json) | TTS 引擎、服务商、情绪/音色映射、按会话策略的文字/语音/分段/概率输出、情绪标记。文件较大是因为包含情绪映射表；重新填 API Token/音色 ID 并审查哪些会话自动发语音。 |
| TimeAwareness | [`time_awareness_config.example.json`](../configs/runtime/time_awareness_config.example.json) | 现实时间引导、上次聊天间隔、静态/AI 日程、日历、节假日/农历/节气。设置正确时区，并与 Life Scheduler 对齐，避免时间状态矛盾。 |

## 配置复刻顺序

1. 启动 AstrBot 完成 Dashboard 首次初始化、Provider、平台和管理员设置。
2. 停止 AstrBot，执行 `bash scripts/install-runtime.sh deployment/runtime-data` 安装源码及缺失模板。
3. 启动后安装锁定清单中需单独安装的插件，让其生成正确版本配置；对照以上模板补入非敏感选项。
4. 在管理面板或本地配置文件填入真实密钥、账号 ID、白名单和收件目标；不要把这些值贴进 README 或提交到 Git。
5. 运行 [`acceptance.md`](acceptance.md) 对应验收项；确认日志中插件均成功加载。

## 不在 JSON 模板中的状态

以下不是“配置丢失”，而是有意不公开：AstrBot 数据库和 Provider/平台登录凭据，`plugin_data/` 中的对话记忆/好感度/学习结果、表情包图库与标签、Life Scheduler 今日状态、Scheduled Sender 任务状态、Airi 在线/同步凭据、下载缓存和日志。若要迁移自己的这些状态，请加密备份本机 `AstrBot/data/`，不要提交到公开 GitHub。参见 [`restore-and-backup.md`](restore-and-backup.md)。
