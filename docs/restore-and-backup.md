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

### 通过加密归档迁移完整私有状态

以下示例以 Compose 挂载目录 `deployment/runtime-data/` 为例。确保备份介质是私有且有足够空间；归档中可能包含 API 密钥、平台登录态和聊天/记忆数据。

在旧电脑的仓库目录执行：

```bash
docker compose --env-file deployment/.env -f deployment/compose.yaml stop astrbot
umask 077
tar -czf /secure/private-backups/lin-xiaoman-runtime-data.tar.gz -C deployment runtime-data
gpg --symmetric --cipher-algo AES256 \
  --output /secure/private-backups/lin-xiaoman-runtime-data.tar.gz.gpg \
  /secure/private-backups/lin-xiaoman-runtime-data.tar.gz
```

将 `.gpg` 文件通过可信的私有渠道转移；确认目标机解密、归档完整且机器人可启动后，再按自己的设备安全策略删除未加密的 `.tar.gz`。不要把明文归档、密钥或解密后的目录放到 Git 工作区、云盘公开链接或 Issues。

在新电脑克隆仓库并准备 Compose 文件后，先停止服务。最好在**新克隆且尚无重要运行数据**的实例恢复；若 `deployment/runtime-data/` 已存在，先把它改名保留作回滚点，不要把归档直接覆盖/混合到正在使用的数据目录：

```bash
docker compose --env-file deployment/.env -f deployment/compose.yaml stop astrbot
if [ -d deployment/runtime-data ]; then
  mv deployment/runtime-data "deployment/runtime-data.before-restore-$(date +%Y%m%d-%H%M%S)"
fi
gpg --output /secure/private-backups/lin-xiaoman-runtime-data.tar.gz \
  --decrypt /secure/private-backups/lin-xiaoman-runtime-data.tar.gz.gpg
tar -xzf /secure/private-backups/lin-xiaoman-runtime-data.tar.gz -C deployment
docker compose --env-file deployment/.env -f deployment/compose.yaml up -d astrbot
```

恢复后核对 AstrBot/插件版本、容器日志、Provider/平台连接、图库、记忆和定时任务；迁移到不同操作系统或插件版本时，旧数据库/配置可能需要迁移，保留原始加密备份直至新实例完成验收。上述 `gpg` 示例会在目标机创建明文压缩包，验收后按安全策略移除。

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
