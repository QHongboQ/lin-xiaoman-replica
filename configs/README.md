# 配置示例

插件配置结构随版本变化。请先安装 [`plugin-lock.md`](../docs/plugin-lock.md) 对应插件，再从 AstrBot 管理面板配置。Airi Gallery 有一份基于当前图库行为整理的公开示例：[airi-gallery.example.json](airi-gallery.example.json)。其余插件优先在管理面板配置，避免直接套用版本不匹配的 JSON。当前实例的完整配置留在用户自己的 WSL 数据目录，没有公开复制。

必需的私有设置包括模型提供方/模型 ID、Airi Gallery 上传和同步令牌、MusicDL Cookie（可选）、QQ 连接器凭据、管理员 UID、白名单及会话目标。将这些写入本机 `data/config/` 或环境变量，绝不要提交到 GitHub。

可以公开共享的设置是插件职责、图库分类名（`林小满`）、浏览命令模式、模型行为说明、时区规则等非凭据选项，见 [`settings.md`](../docs/settings.md)。
