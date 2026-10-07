# 林小满｜完整自托管复刻包

这不是只有角色卡或照片的示例，而是基于 **2026-10-06 WSL 实例**整理的 AstrBot 复刻项目：包含角色人格、21 个当前插件的版本清单、可分发的插件源码快照、20 份脱敏配置模板、37 张林小满图库图片、Docker 部署文件、安装脚本和全功能验收清单。

目标是在另一台 Linux/WSL2 电脑上重建一套可运行、可继续积累记忆和关系的林小满。它不是原设备的逐字节克隆：账号密钥、聊天历史、记忆/好感度数据库、QQ 登录态、定时任务状态等私有运行数据不会公开，需要在新实例重新配置或从自己的加密备份迁移。

## 目录

- [仓库交付内容](#仓库交付内容)
- [功能与插件全景](#功能与插件全景)
- [快速部署](#快速部署)
- [初始化和配置](#初始化和配置)
- [常用使用方式](#常用使用方式)
- [全功能验收](#全功能验收)
- [备份、安全与隐私](#备份安全与隐私)
- [已知限制](#已知限制)
- [故障排查](#故障排查)
- [文档索引与许可](#文档索引与许可)

## 仓库交付内容

| 内容 | 路径 | 用途 |
|---|---|---|
| 林小满人格卡 | [`docs/persona.md`](docs/persona.md) | 身份背景、语气、互动边界、隐私红线和地点锚点 |
| 插件源码 | [`plugins/`](plugins/) | 林小满个人照片接口和 15 个许可允许随包分发的插件源码快照 |
| 插件版本锁定 | [`docs/plugin-lock.md`](docs/plugin-lock.md) | 当前 21 个插件的版本、上游、分发状态与本地改动说明 |
| 运行配置模板 | [`configs/runtime/`](configs/runtime/) | 19 份脱敏插件 JSON + 1 份 AstrBot 命令配置模板 |
| 角色图库 | [`gallery/xiaoman/`](gallery/xiaoman/) | 当前 Airi Gallery「林小满」分类的 37 张图片 |
| 部署文件 | [`deployment/`](deployment/) | AstrBot Dockerfile、Compose 示例、环境变量模板和说明 |
| 安装脚本 | [`scripts/install-runtime.sh`](scripts/install-runtime.sh) | 安装插件源码和缺失的脱敏配置；不覆盖已有文件 |
| 创作素材 | [`creative-kit/`](creative-kit/) | 手动制作新图片时使用的视觉参考和提示材料 |

图片、第三方源代码和本项目文档有不同许可边界；请先阅读各目录内的 `LICENSE` 及 [分发限制](#已知限制)。

## 功能与插件全景

林小满的响应由多个机制协作。下表按当前运行插件说明“谁负责什么”；是否启用某个可选功能仍要看相应配置、模型、账号权限和外部服务。

| 功能/机制 | 组件 | 做什么 | 配置/说明 |
|---|---|---|---|
| 人格与互动边界 | 人格卡 + 主模型 + 阿瓦隆安全守卫 | 熟人调侃、嘴硬、面对严肃话题收敛；隐私和内容边界由提示词与安全审核共同约束 | [`persona.md`](docs/persona.md)、[`机制说明`](docs/mechanisms.md#2-人格与对话边界)、[阿瓦隆配置](configs/runtime/astrbot_plugin_content_safety_guard_config.example.json) |
| 群聊唤醒与回复节奏 | 天使之心 Angel Heart | 处理提及/召唤、群聊参与门控、是否接话、上下文整理和输出长度 | [天使之心配置](configs/runtime/astrbot_plugin_angel_heart_config.example.json) |
| 连续消息和长回复 | 消息防抖 + Splitter | 合并短时间连续输入，处理引用/媒体/链接，并将长回复按语义分段 | [防抖配置](configs/runtime/astrbot_plugin_continuous_message_config.example.json)、[Splitter 配置](configs/runtime/astrbot_plugin_splitter_config.example.json) |
| 个人记忆与笔记 | 天使之魂 Angel Memory | 用户范围记忆检索、向量搜索、记忆/回忆/笔记工具和后台整理 | [天使之魂配置](configs/runtime/astrbot_plugin_angel_memory_config.example.json) |
| 好感度、情绪与学习 | Self Learning | 按用户/群学习表达风格和黑话，维护关系/好感度、情绪及人格演化状态 | [学习配置](configs/runtime/astrbot_plugin_self_learning_config.example.json) |
| 世界书和知识库 | 羽笔 QuillPlus | 世界书、写作素材、角色卡、RAG/文档检索、动态记忆和状态栏 | [羽笔配置](configs/runtime/astrbot_plugin_quillplus_config.example.json) |
| 每日生活状态 | Life Scheduler | 生成日程/穿搭，将当前活动注入对话上下文，并支持维护衣柜方案 | [日程配置](configs/runtime/astrbot_plugin_life_scheduler_config.example.json) |
| 时间与日历 | TimeAwareness | 现实时间、上次聊天间隔、工作日/节气/日历、静态与人格日程 | [时间配置](configs/runtime/time_awareness_config.example.json) |
| 峰谷闸门和成本 | 大肥鱼钱包 + Cost Control | 钱包可按时段暂停/恢复模型调用并播报；Cost Control 上游基线提供 token/费用预算、预警/停止/回退、缓存与模型用量报告，当前机上版本有未分发改动 | [钱包配置](configs/runtime/astrbot_plugin_fat_fish_wallet_config.example.json)、[成本配置](configs/runtime/astrbot_plugin_cost_control_config.example.json)、[机制边界](docs/mechanisms.md#8-安全审核成本与管理) |
| 林小满角色照片 | Airi Gallery + 本仓库个人接口 | 模型可调用 `send_xiaoman_photo()`；Airi 还负责分类浏览、上传/删除、去重、重建索引和可选远程同步 | [Airi 配置](configs/runtime/astrbot_plugin_airi_gallery_config.example.json)、[接口说明](plugins/astrbot_plugin_xiaoman_personal_interface/README.md) |
| 表情包与斗图 | Smart ImageChat Hub | 独立的表情图库、标签/语义检索、主动表情、斗图、自动采集和备份 | [表情配置](configs/runtime/astrbot_plugin_smart_imagechat_hub_config.example.json) |
| 外部插画与签到 | 画境拾珍 Get PX | 外部插画检索/过滤、签到卡、排行、主题等社区互动 | [Get PX 配置](configs/runtime/astrbot_plugin_get_px_config.example.json) |
| 语音 | TTS Emotion Router | 情绪路由、按会话策略文字/语音/分段/概率输出和语音工具 | [TTS 配置](configs/runtime/astrbot_plugin_tts_emotion_router_config.example.json) |
| 音乐 | MusicDL + Music Pro | 多源搜索、下载、换源和发送；与角色回复 TTS 是不同能力 | [MusicDL 配置](configs/runtime/astrbot_plugin_musicdl_config.example.json)、[Music Pro 配置](configs/runtime/astrbot_plugin_music_pro_config.example.json) |
| 定时消息 | Scheduled Sender | 一次性、每日、工作日、间隔或 Cron 任务；可为消息轮换设定候选内容；原机任务状态不会随模板迁移 | [定时配置](configs/runtime/astrbot_plugin_scheduled_sender_config.example.json) |
| 管理命令 | AstrBot + Builtin Commands Extension | 会话、模型、插件、管理员和平台管理命令 | [全局配置](configs/runtime/astrbot_cmd_config.example.json) |
| 娱乐与实用工具 | Essential | 搜番、随机动漫图、喜报/悲报图、Minecraft 状态、一言、今天吃什么、Epic 喜加一和早晚安统计等 | [Essential 配置](configs/runtime/astrbot_plugin_essential_config.example.json)、[插件机制](docs/mechanisms.md#7-语音音乐与实用工具) |

更具体的事件链路、各能力的当前配置状态、依赖和非确定性边界见 [`docs/mechanisms.md`](docs/mechanisms.md)。完整逐插件版本及上游地址见 [`docs/plugin-lock.md`](docs/plugin-lock.md)。

### 重要行为边界

- **照片、表情包和外部插画是三套不同来源。** 林小满照片来自 Airi 的 `林小满` 分类；Smart ImageChat 负责表情图库；Get PX 查询外部插画。
- 自然对话中是否发照片、是否调用记忆工具、是否回复群聊由提示词/插件门控/模型共同决定；不是每次关键词命中都会执行。
- TTS 模板当前启用了若干自动/概率语音策略和 LLM 工具。部署后必须检查会话范围、音色和 API 凭据，避免没预期地发语音。
- 自动学习、图片采集、每日状态、定时发送和峰谷闸门依赖各自插件配置及本机运行数据。具体能力没有启用或外部服务不可用时，不应宣称验收通过。

## 快速部署

### 前置条件

- Linux 或 WSL2 主机；Windows 可通过 WSL2 + Docker Desktop 使用。安装 Docker Engine 和 Docker Compose v2。
- 能访问 Docker 镜像仓库、模型服务、AstrBot 插件市场及你选择的 QQ 连接器。
- 一套自己的模型 Provider/模型，以及可用的平台机器人账号。QQ 平台和登录方式须遵守对应服务条款。

### 1. 克隆并设置环境文件

```bash
git clone https://github.com/QHongboQ/lin-xiaoman-replica.git
cd lin-xiaoman-replica
cp deployment/compose.example.yaml deployment/compose.yaml
cp deployment/.env.example deployment/.env
```

编辑 `deployment/.env`：至少把 `VNC_PASSWD` 改成私有强密码。SnowLuma 是可选的 QQ 客户端，只有选择它时才会通过 `qq-client` profile 启动；若用其它适配器，无需启动该服务。不要提交 `deployment/.env` 或 `deployment/compose.yaml`。

### 2. 首次启动 AstrBot

在仓库根目录执行：

```bash
docker compose --env-file deployment/.env -f deployment/compose.yaml up -d --build astrbot
```

打开 `http://127.0.0.1:6185` 完成管理面板初始化，建立自己的模型 Provider、默认模型、平台适配器和管理员账号。Compose 只把面板端口绑定到本机回环地址。

### 3. 安装本仓库的插件源码和初始配置

停止 AstrBot 后，在 **Linux/WSL shell**（不要在纯 PowerShell 里直接运行 Bash 脚本）执行：

```bash
docker compose --env-file deployment/.env -f deployment/compose.yaml stop astrbot
bash scripts/install-runtime.sh deployment/runtime-data
docker compose --env-file deployment/.env -f deployment/compose.yaml up -d astrbot
```

安装脚本将本仓库个人接口和 `plugins/bundled/` 内的源码放进 `deployment/runtime-data/plugins/`，把脱敏 JSON 模板复制到对应配置位置。已有插件目录/配置会保留，不会覆盖。启动后查看 AstrBot 插件管理页和日志。

### 4. 安装未随仓库分发的插件并恢复图库

通过 AstrBot 插件市场或作者上游安装：Airi Gallery、Splitter、Scheduled Sender、Cost Control、Essential。当前版本和作者地址见 [`plugin-lock.md`](docs/plugin-lock.md)。然后在 Airi 创建 `林小满` 分类并导入 [`gallery/xiaoman/`](gallery/xiaoman/) 中的 37 张图片；启用 LLM 工具并确认注册 `gallery_send`。图库同步/上传凭据只填在本机。

### 5. 按配置清单完成初始化

按 [`docs/configuration-reference.md`](docs/configuration-reference.md) 逐项配置 20 份模板，按 [`docs/settings.md`](docs/settings.md) 检查模型、平台、各插件和权限。然后将 [`docs/persona.md`](docs/persona.md) 的人格加入主模型角色设置。

> 角色记忆、好感度、图库标签、QQ 登录状态和定时任务不在 GitHub；新实例初始状态为空。配置字段随插件版本变化，插件面板生成的当前版本配置优先于旧模板。

## 初始化和配置

完整文件索引和字段职责见 [`docs/configuration-reference.md`](docs/configuration-reference.md)。下面是迁移时最容易漏的内容：

1. **全局模型与平台：** 重新创建 Provider、模型、QQ 连接器、管理员 UID 和默认人格。不要把 API Key、QQ/群号或 Dashboard 凭据写进仓库。
2. **角色与群聊：** 检查 Angel Heart 的召唤/提及门控、分析模型、输出长度和上下文压缩；在小范围测试群先调节是否接话。
3. **隐私与状态：** 检查 Angel Memory 的用户/群范围、Self Learning 的消息采集/原始记录保留、QuillPlus 的聊天日志和 RAG 集合。决定谁能查看、保存多久、怎样备份。
4. **时间和主动任务：** 统一 AstrBot、Life Scheduler、TimeAwareness、Fat Fish Wallet、Scheduled Sender 的时区；分别复建日历、峰谷和定时目标。
5. **图片：** 保证林小满照片、表情包、外部插画各用各的图库和规则；检查 Smart ImageChat 自动采集/接受策略。
6. **语音与外部 API：** 配好 TTS Provider/音色、音乐服务、Pixiv/Lolicon 等需要的令牌或 URL；设置自动语音和外部图片的会话范围。
7. **权限和安全：** 重设管理员/白名单，核对群聊命令、审核、黑名单与工具权限。不要直接沿用个人 ID 或历史服务器地址。

## 常用使用方式

具体指令前缀受 AstrBot 和插件配置影响；先用 `/help` 查看部署实例实际注册的命令。

| 场景 | 示例 | 说明 |
|---|---|---|
| 查看会话/帮助 | `/help`、`/sid` | AstrBot 基础命令，便于检查帮助和会话 ID |
| 角色测试开关 | `/xiaoman_test status`、`/xiaoman_test on`、`/xiaoman_test off` | 仅 AstrBot 管理员；测试放行按会话隔离，重启后关闭。只在测试会话使用 |
| 显式浏览/维护角色图库 | `/看看小满`、`/看100-110`、`/分类列表`、`/画廊帮助` | Airi 浏览命令；上传、删除、去重和同步等管理命令请先看插件帮助并限制管理员权限 |
| 查看记忆/学习状态 | `/learning_status`、`/好感度` | Self Learning 状态/关系命令；不要在公开群暴露个人关系信息 |
| TTS | `/tts_status`、`/tts_say 你好`、`/tts_off` | 查看语音状态、明确合成一次或关闭；确认当前会话策略 |
| 插画与签到 | `/p`、`/签到`、`/签到帮助` | Get PX 的插画检索和签到功能，受外部服务、群策略和内容过滤影响 |
| 音乐 | `/music_help`、`/点歌 歌曲名` | MusicDL / Music Pro 的入口；音源可用性不由本仓库保证 |
| 定时任务 | `/定时 添加`、`/定时 列表`、`/定时 测试`、`/定时 删除` | Scheduled Sender；先确认实际帮助、时区及目标会话，只在测试群创建任务 |
| Essential 工具 | `/搜番`、`/moe`、`/喜报`、`/悲报`、`/一言`、`/今天吃什么`、`/早安`、`/晚安` | 具体命令以安装版本帮助为准；部分能力会访问外部服务 |
| 成本用量 | `/cost`、`/budget`、`/cache`、`/report` | Cost Control 上游基线命令；本机改版可能有差异，先检查配置/权限 |
| 峰谷状态 | `/峰谷` | 大肥鱼钱包状态；调整时段可能影响所有模型调用 |
| AstrBot 管理 | `/plugin`、`/model`、`/history`、`/new`、`/reset`、`/stop` | 部分由命令扩展提供；有副作用的命令仅在测试会话运行 |

## 全功能验收

验收不止图库。仓库提供覆盖 30 项核心链路的 [`docs/acceptance.md`](docs/acceptance.md)，包括启动/插件加载、人格、群聊门控、防抖、记忆/学习/RAG、日程/时间、峰谷与成本、图库浏览和维护、表情包/外部插画、TTS、音乐、Essential、定时消息、安全、权限、数据持久化和备份。建议逐项记录通过/失败/未配置；必须在测试账号、测试会话中执行，不能因为命令能运行就推断插件全功能正确。

## 备份、安全与隐私

- [`configs/runtime/`](configs/runtime/) 是可公开分享的脱敏模板，不是原设备私有配置的镜像。
- 已排除：模型/API 密钥、Airi Token、MusicDL Cookie、QQ/群号/管理员/白名单、Dashboard 凭据、数据库、聊天历史、好感度/学习状态、记忆/向量库、定时任务状态、运行日志和插件私有图库状态。
- `.gitignore` 排除 `deployment/runtime-data/`、数据库、日志和私有 `.env`。在 `git add` 前仍应自己检查 `git status` 和敏感文件。
- 若需要迁移个人状态，请在原机停止服务或使用插件的安全备份功能，将整个 `AstrBot/data/` 加密备份到私有介质；不要把原始数据推到这个公开仓库。先在新实例验证恢复，不要覆盖另一台运行中的数据目录。
- Self Learning/QuillPlus 等配置可能保存原始消息或聊天日志。部署者需自行设定留存、访问权限、加密和用户告知。

## 已知限制

1. **不是原机完整运行态：** 公开包创建的是干净实例；记忆、好感度、签到数据、QQ 登录、日历状态、插件图库索引和定时任务需自行恢复或新建。
2. **有 5 个第三方插件未镜像源码：** Airi Gallery、Splitter、Scheduled Sender、Cost Control、Essential 的本地源码没有可确认的再分发许可。请从作者渠道安装；版本或市场不可用时按上游许可处理。
3. **Cost Control 差异：** 本机 0.4.1 基于上游 `2b53332` 并含 `_conf_schema.json`、`backend/auto_collection.py`、`backend/caption_library.py`、`backend/retrieval.py` 四处本地修改。这些改动未公开随包分发，不能由新部署精确复刻。
4. **模型输出不确定：** 人格、情绪、是否接话、是否发照片/语音、记忆工具调用都是受提示词与模型影响的行为；只能通过测试提升可靠性，不能承诺每次一致。
5. **外部服务依赖：** 模型、QQ 适配器、Pixiv/Lolicon、TTS、音乐 API、图床、插件市场可能变化或失效；需使用者自行提供凭据并遵守平台/版权条款。
6. **插件版本变化：** 当前配置模板按 2026-10-06 版本快照整理。新版本字段可能变化，先备份，再让插件生成新配置并手动合并。
7. **运行时图库不等于公开素材许可：** 仓库包含当前 Airi「林小满」分类的 37 张照片；Smart ImageChat 等插件的自动采集图片、旧插件图库和缓存留在私有运行数据中。它们可能含用户提交内容或第三方作品，来源/授权未经逐项核验，因此不作为公共复刻素材包。

## 故障排查

| 现象 | 检查项 |
|---|---|
| AstrBot 面板打不开 | `docker compose ... ps/logs`；端口 6185 是否占用；Docker 镜像构建是否成功；查看 `deployment/README.md` |
| 插件列表缺插件 | 检查五个手动安装插件；核对目录名、版本、依赖与 AstrBot 启动日志 |
| 群里不回应 | 是否被提及/召唤；Angel Heart 群聊门控与 Provider；防抖是否还在等待；Fat Fish 是否处于峰值暂停；安全插件是否拦截 |
| 记忆答错或串人 | 检查 Angel Memory 会话范围、Self Learning 用户过滤、QuillPlus 集合/权限；检查并行记忆注入是否重复 |
| 今日状态与时间错 | 检查主机/容器时区、TimeAwareness、Life Scheduler 的日期与静态/AI 日程是否冲突 |
| 照片工具不可用 | 检查 Airi 是否启用并注册 `gallery_send`、接口插件是否加载、分类是否精确叫 `林小满`、LLM 工具是否开启 |
| 表情包混入角色照片 | 分开 Airi 和 Smart ImageChat 的目录/导入路径；检查自动采集来源和过滤规则 |
| TTS/音乐/外部图片失败 | 确认 Provider ID、Token、URL、Cookie/音色、网络和服务商限流；勿把密钥贴到 Issue |
| 定时任务没有执行 | 检查调度插件是否安装、时区/错过任务策略、目标会话是否有效；任务状态不会从 GitHub 恢复 |
| 配置字段不匹配 | 插件版本不同会生成不同 Schema；备份旧配置，先让当前插件生成模板，再参考 [`configuration-reference.md`](docs/configuration-reference.md) 合并 |

提交问题时请注明插件版本、复现步骤和删去账号/群号/密钥后的错误摘要；不要上传数据库或完整日志。

### 项目状态与反馈

本仓库是个人维护的、按上述日期封存的复刻快照，不是 AstrBot 或任一第三方插件的官方发行版，也不会自动跟随上游升级。发现配置/说明和实际快照不符时，可在 GitHub Issues 描述插件版本、配置项名称和可公开复现步骤；不要附真实密钥、QQ/群号、私聊、数据库或未脱敏日志。若自行更新了插件，请一并更新版本清单、配置索引和对应验收项。

## 文档索引与许可

- [完整机制说明](docs/mechanisms.md)：组件链路、21 个插件逐项职责和行为边界。
- [配置索引](docs/configuration-reference.md)：20 份 JSON 模板、字段责任、必须重填的本机值。
- [全功能验收清单](docs/acceptance.md)：按机制逐项测试并记录结果。
- [插件锁定清单](docs/plugin-lock.md)：版本、上游和分发限制。
- [运行架构](docs/runtime-architecture.md)：组件之间如何协作。
- [人格卡](docs/persona.md)：角色信息、语气和红线。
- [配置指南](docs/settings.md)：从 AstrBot 面板初始化的关键设置。
- [新机恢复与备份](docs/restore-and-backup.md)：个人数据迁移边界、更新和恢复。
- [Docker 部署说明](deployment/README.md)：Compose、SnowLuma 可选配置与运行目录。

本项目自有个人接口源代码和自有文档按根目录 [MIT LICENSE](LICENSE) 授权；图库图片按 [`gallery/LICENSE.md`](gallery/LICENSE.md) 的单独条款使用。第三方插件各自保留上游许可，根目录 MIT 不覆盖第三方源码。五个未随仓库分发的插件应按各自作者许可获取。
