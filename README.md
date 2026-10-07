# 林小满：自托管复刻指南

这个仓库记录林小满当前运行方案，并提供个人接口插件、图库导入包和复刻说明。运行时是 AstrBot；人格、长期记忆、日程、好感度、照片图库和语音由各自插件负责。

## 当前版本基线

此仓库按 2026-10-06 的 WSL 运行实例整理。图库包含 `gallery/xiaoman/` 下的 37 张图片。核心插件版本见 [`docs/plugin-lock.md`](docs/plugin-lock.md)。复刻后可自行替换模型、账号和插件版本。

## 安装

1. 准备一套 AstrBot `>=4.28.2`。如需复用当前实例为中国节假日识别加入的 Python 依赖，可参考 [`deployment/Dockerfile`](deployment/Dockerfile) 构建镜像。QQ 机器人连接器（如 NapCat）单独部署并连接到 AstrBot。
2. 在 AstrBot 插件市场安装 [`docs/plugin-lock.md`](docs/plugin-lock.md) 列出的依赖插件。优先选清单中的版本；若市场不提供该版本，从对应上游仓库安装并确认兼容性。
3. 将 `plugins/astrbot_plugin_xiaoman_personal_interface` 放进 AstrBot 的 `data/plugins/`，或从本仓库的 GitHub Release 安装。重启/重载后确认插件启用。
4. 在 AstrBot 配置中设置人格模型、时区、管理员、模型服务和各插件选项。配置方向见 [`docs/settings.md`](docs/settings.md)。凭据只填入你自己的 AstrBot 实例，不能把真实值提交到 Git。
5. 安装 Airi Gallery v2.11.15，在图库中新建 `林小满` 分类。将 [`gallery/xiaoman/`](gallery/xiaoman/) 中图片导入该分类。图片文件名为图库编号，不要求沿用原编号。
6. 在 Airi Gallery 启用 `gallery_send` 工具，并将显式图库浏览命令设为前缀模式。插件配置、上传令牌和 Git 同步令牌由 AstrBot 管理面板保存。
7. 配置林小满人格卡和插件职责，参考 [`docs/persona.md`](docs/persona.md) 与 [`docs/runtime-architecture.md`](docs/runtime-architecture.md)。不要把个人聊天、记忆库或好感度数据库迁入公开仓库。

## 照片行为

- 自然对话由主模型根据人格和上下文判断是否调用 `send_xiaoman_photo()`；用户提到“照片”不等于必须发图。
- 个人接口只委托 Airi Gallery 的 `gallery_send`，目标固定为 `林小满` 分类、1 张；未确认发送时按失败处理。
- 显式图库浏览由 Airi 命令处理，例如 `/看看小满`。普通聊天文字仍走正常对话。
- 手动制图素材见 [`creative-kit/`](creative-kit/)。新增图片需人工审核后再导入图库。

## 配置文件与安全

`configs/` 只放可公开的结构示例。请在 AstrBot 管理面板根据各插件配置项填写自己的值；不要将运行中的 `data/config/*.json` 原样复制进仓库。真实模型密钥、Airi 上传/Git 令牌、MusicDL Cookie、QQ/群号、管理员 UID、白名单、个人记忆、聊天历史和日志都属于私有数据。

## 验收

- 普通聊天和显式 `/看看小满` 命令都能正常工作。
- 模型决定发照片时，只发送林小满分类中的一张。
- 关闭或移除图库工具后，照片调用明确失败，不会误报成功。
- 重启 AstrBot 后，插件和图库仍可用。

## 许可

个人接口源代码按根目录 `LICENSE`（MIT）授权。`gallery/xiaoman/` 图片和角色设定按 `gallery/LICENSE.md` 的条款使用。第三方插件保留其各自上游许可证；本仓库不包含它们的完整源码。
