# 林小满：自托管复刻指南

这个仓库打包了林小满当前运行版本的角色设定、部署配置模板、插件源码快照、37 张 Airi 图库图片和完整安装步骤。它按 2026-10-06 WSL 实例整理，目标是在另一台电脑从空白 AstrBot 环境重新部署。

## 当前版本基线

此仓库按 2026-10-06 的 WSL 运行实例整理。除五个需单独安装的第三方插件外，锁定清单中的许可允许分发的源码已放在 `plugins/bundled/`；当前插件配置已脱敏后放在 `configs/runtime/`。图库包含 `gallery/xiaoman/` 下的 37 张图片。版本和上游来源见 [`docs/plugin-lock.md`](docs/plugin-lock.md)。

## 安装

1. 在新电脑安装 Docker Engine 和 Docker Compose，然后克隆仓库：

   ```bash
   git clone https://github.com/QHongboQ/lin-xiaoman-replica.git
   cd lin-xiaoman-replica
   cp deployment/compose.example.yaml deployment/compose.yaml
   cp deployment/.env.example deployment/.env
   ```

   修改 `deployment/.env` 中的 VNC 密码。若只用外部 QQ 连接器，可不启用 SnowLuma。
2. 在仓库根目录启动 AstrBot：

   ```bash
   docker compose --env-file deployment/.env -f deployment/compose.yaml up -d --build astrbot
   ```

   打开 `http://127.0.0.1:6185`，完成 AstrBot 初始设置，连接自己的 QQ 平台适配器并配置模型提供方。部署细节见 [`deployment/README.md`](deployment/README.md)。
3. 停止 AstrBot 后，把源码和脱敏配置复制到运行目录：

   ```bash
   docker compose --env-file deployment/.env -f deployment/compose.yaml stop astrbot
   bash scripts/install-runtime.sh deployment/runtime-data
   docker compose --env-file deployment/.env -f deployment/compose.yaml up -d astrbot
   ```

   安装脚本只补缺失插件/配置，不覆盖已有文件。
4. 通过 AstrBot 插件市场安装清单中标记“需单独安装”的五个插件，并选择表中版本：Airi Gallery、Splitter、Scheduled Sender、Cost Control、Essential。它们的本地源码没有可确认的再分发许可，所以仓库不镜像其源码。若插件市场不再提供锁定版本，从 [`docs/plugin-lock.md`](docs/plugin-lock.md) 的上游链接安装兼容版本。
5. 在 AstrBot 管理面板填入自己的模型服务、QQ 连接器、管理员 UID、白名单、会话目标和插件令牌。当前运行配置模板见 [`configs/runtime/`](configs/runtime/)；这些文件已脱敏，空字段需按你的环境填写。配置说明见 [`docs/settings.md`](docs/settings.md)。
6. 安装 Airi Gallery v2.11.15，在图库中新建 `林小满` 分类，将 [`gallery/xiaoman/`](gallery/xiaoman/) 中 37 张图片导入。设置浏览命令为 `prefix`，启用 LLM 工具以注册 `gallery_send`；上传令牌和 Git 同步令牌留在你的本机。
7. 按 [`docs/persona.md`](docs/persona.md) 配置角色人格；按 [`docs/runtime-architecture.md`](docs/runtime-architecture.md) 开启协作插件。记忆、好感度和会话数据从空库开始积累。

逐项恢复、数据备份边界和更新操作见 [`docs/restore-and-backup.md`](docs/restore-and-backup.md)。

## 林小满的机制一览

林小满不是只有一张人格卡或一个发图工具，而是由 AstrBot、角色设定、多个插件和本机运行数据一起构成。详细机制、各能力边界和复刻验收项目见 [`docs/mechanisms.md`](docs/mechanisms.md)。

| 机制 | 负责组件 | 当前配置下的作用 |
|---|---|---|
| 人格与说话边界 | [`docs/persona.md`](docs/persona.md) + 主模型 | 嘴硬、熟人调侃、严肃问题收敛；限制隐私泄露、人身攻击和越界亲密内容。模型生成不是硬编码保证。 |
| 群聊在场与唤醒 | 天使之心 | 被提及/明确召唤后进入群聊，评估是否接话并整理输出；不承诺每条消息必答。 |
| 连续消息理解 | 消息防抖 + Splitter | 合并短时间连续输入，处理引用、媒体、链接；长回复按语义分段发送。 |
| 关系、记忆、学习 | 天使之魂 + Self Learning + 羽笔 | 用户记忆、笔记/检索、好感度与情绪变化、风格/群黑话学习、世界书/RAG。数据写入本地，复刻后重新积累。 |
| 时间与生活状态 | Life Scheduler + TimeAwareness | 生成每日活动/穿搭，注入当前时段、节假日、日历和上次聊天间隔；需要检查时区和重叠日程。 |
| 角色照片 | Airi Gallery + 林小满个人接口 | 模型决定调用时，从“林小满”分类委托发送 1 张；不与表情包或外部插画混用。 |
| 表情包与斗图 | Smart ImageChat Hub | 语义搜索、主动表情、自动采集和图库备份；需单独审核采集内容。 |
| 外部插画/签到 | 画境拾珍（Get PX） | 外部插画检索和签到排行，不是角色照片库。 |
| 语音和音乐 | TTS Router、MusicDL、Music Pro | TTS 情绪路由/按策略发语音；点歌下载与语音合成是两条独立链路。 |
| 安全与成本 | 阿瓦隆、大肥鱼钱包、Cost Control | 输入/输出审核、关键词与重复消息拦截；峰谷时段调用闸门及成本管理。 |
| 定时及管理 | Scheduled Sender、AstrBot 命令扩展 | 定时任务向指定会话发送、会话/插件/模型管理；目标和权限必须在新实例重新设置。 |

照片机制补充：

- 自然对话由主模型根据人格和上下文判断是否调用 `send_xiaoman_photo()`；用户提到“照片”不等于必须发图。
- 个人接口只委托 Airi Gallery 的 `gallery_send`，目标固定为 `林小满` 分类、1 张；未确认发送时按失败处理。
- 显式图库浏览由 Airi 命令处理，例如 `/看看小满`。普通聊天文字仍走正常对话。
- 手动制图素材见 [`creative-kit/`](creative-kit/)。新增图片需人工审核后再导入图库。

## 各项机制的细节

- [`docs/mechanisms.md`](docs/mechanisms.md)：消息链路、群聊门控、关系/记忆/学习、日程、图片、语音、审核、成本与验收。
- [`docs/runtime-architecture.md`](docs/runtime-architecture.md)：插件职责与组件连接关系。
- [`docs/persona.md`](docs/persona.md)：角色身份、互动风格、隐私和行为红线。
- [`docs/plugin-lock.md`](docs/plugin-lock.md)：当前插件版本、源码是否随仓库分发及上游来源。
- [`docs/settings.md`](docs/settings.md)：新实例需要配置的模型、平台、插件和私有凭据。

## 配置文件与安全

`configs/runtime/` 放置的是从当前有效插件配置派生的脱敏副本。不要把它们误当作已填好凭据的可直接运行备份。真实模型密钥、Airi 上传/Git 令牌、MusicDL Cookie、QQ/群号、管理员 UID、白名单、个人记忆、聊天历史和日志都不在仓库里。

## 验收

- 普通聊天和显式 `/看看小满` 命令都能正常工作。
- 模型决定发照片时，只发送林小满分类中的一张。
- 关闭或移除图库工具后，照片调用明确失败，不会误报成功。
- 重启 AstrBot 后，插件和图库仍可用。
- 新实例能启动，插件管理页可看到分发的插件，且所有需要填写的占位/空凭据均已由部署者配置。

## 许可

个人接口源代码和本项目自有文档按根目录 `LICENSE`（MIT）授权。`gallery/xiaoman/` 图片按 `gallery/LICENSE.md` 的条款使用。第三方插件快照按各自目录中的上游许可证使用；未随仓库分发的插件请直接从作者渠道获取。
