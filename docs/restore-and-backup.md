# 新电脑恢复与日常备份

## 这份公开仓库恢复什么

- 林小满角色卡、机制说明、当前插件配置模板和插件源码快照。
- 当前 Airi Gallery `林小满` 分类的 37 张图片。
- Docker AstrBot 部署文件和安装脚本。

新实例不会带入原来的 QQ 登录、模型服务密钥、对话记录、用户记忆、好感度/学习数据库、日程运行状态、表情包采集库或日志。它们留在原设备的 AstrBot `data/` 中；本仓库用于创建干净实例，再按自己的账号重新配置。

## 恢复步骤

1. 克隆仓库，复制 `deployment/compose.example.yaml` 与 `deployment/.env.example`，设置本机环境变量。
2. 启动 AstrBot 一次，完成管理面板初始化，然后停止容器。
3. 运行 `bash scripts/install-runtime.sh deployment/runtime-data`。安装脚本会复制本仓库内的插件源码快照与脱敏配置，并保留目标目录已有文件。
4. 启动 AstrBot，安装插件锁定表中需单独安装的插件，重新配置 QQ 平台、模型提供方和管理员/白名单。
5. 在 Airi Gallery 创建 `林小满` 分类并导入 `gallery/xiaoman/` 中的 37 张图片。
6. 按 `docs/settings.md` 检查插件配置，并运行 `README.md` 中的验收清单。

## 原设备的数据备份

若还要迁移个人对话记忆和学习状态，在原设备单独备份整个 `astrbot/data/`，其中包括 `data_v4.db`、`plugin_data/`、`config/`、图库及运行缓存。不要将这种备份提交到公开 GitHub；它包含账号凭据和可识别个人的对话/记忆。只需要迁移图库时，仅导出 Airi 的 `gallery/林小满` 分类即可。

## 更新仓库后的部署同步

```bash
git pull
bash scripts/install-runtime.sh deployment/runtime-data
```

安装脚本不会覆盖已有插件目录或配置，因此更新插件源码/设置时先备份，然后按需手动比较仓库版本和本地 `runtime-data/`。图库更新则在 Airi Gallery 中导入新增图片；不要用整个 `gallery/` 目录覆盖正在运行的图库。

## 常见问题

- **照片工具不存在：** 检查 Airi Gallery 已启用且 `llm_tool_enabled=true`，并确认个人接口插件已重载。
- **照片发送失败：** 检查分类名严格为 `林小满`，Airi Gallery 已有图片，并确认 `gallery_send` 工具可用。
- **配置字段不匹配：** 确认插件版本与 `docs/plugin-lock.md` 一致。若市场版本不同，让插件重新生成配置，再对照 `configs/runtime/` 合并设置。
- **模型或 QQ 不连接：** 这些凭据没有公开导出；在 AstrBot 管理面板重新添加自己的提供方与平台适配器。
