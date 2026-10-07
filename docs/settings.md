# 配置指南

建议从 AstrBot 管理面板安装和配置插件。配置面板会按插件版本生成正确字段；本文件说明复刻时需要设置的项目。当前运行实例的 JSON 含有个人账号信息和令牌，因此没有原样导出。

## AstrBot 基础设置

- 设置主模型提供方和模型；在角色配置中加入 `docs/persona.md` 的人格设定。
- 添加管理员账号，并配置 QQ 连接器。连接器、机器人账号、群号和管理员 UID 都使用复刻者自己的值。
- 设置统一时区，并确保系统时钟正确。
- 若使用本地 Ollama、模型代理或自建 API，仅在本机配置真实地址和凭据。

## 核心插件

- Angel Heart：启用唤醒/称呼规则、会话上下文压缩、输出长度控制；按 `runtime-architecture.md` 保持对话与媒体插件职责分离。
- Angel Memory：启用按用户检索的长期记忆；限制召回片段；避免写入机器人自己的消息或无关群聊内容。
- Self Learning：启用好感度和阶段机制；管理员白名单使用自己的 UID；设置真人消息过滤和每日结算。
- Life Scheduler：选择日程模型，设置地点锚点、工作周、时区、衣橱与人格外观锚点。
- Airi Gallery：新建 `林小满` 分类并导入本仓库图片；设 `view_command_mode=prefix`，启用 LLM 工具（注册 `gallery_send`），并按需设置分类别名。公开参考配置见 [`configs/airi-gallery.example.json`](../configs/airi-gallery.example.json)。上传令牌及 Git 同步令牌只在管理面板填写。
- Xiaoman Personal Interface：确认已启用。管理员测试命令受 AstrBot `ADMIN` 权限保护，测试放行只对开启它的当前会话生效。
- TTS Router：按部署选择 TTS 引擎和音色；在明确的语音请求路径启用，不要求普通文字回复自动转语音。
- Fat Fish Wallet：填入时区、峰谷时段和日程播报目标。目标群/用户使用你自己的会话 ID。
- Splitter：选择自然语义分段，设置每次回复气泡上限。
- MusicDL：选择发送方式和下载目录；Cookie（如确实需要）留在本机。
- Smart ImageChat：将表情图库与林小满照片图库分开；关闭机器人自己发出的图片自动采集。

## 私有配置备份

升级前可在自己的机器备份 `AstrBot/data/config/` 和必要的 `plugin_data/`。公开仓库仅保留没有令牌、账号 ID、Cookie、真实服务地址和个人数据的示例。恢复私有配置时先审查并替换凭据、管理员/白名单与会话列表。
