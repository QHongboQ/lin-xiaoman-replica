# Docker 部署

`compose.example.yaml` 以当前运行环境的 AstrBot 镜像基础和端口为参照。SnowLuma QQ 客户端放在 `qq-client` profile 中，可选启用。QQ 客户端、AstrBot 平台配置和模型服务凭据都要在新电脑上重新配对。

1. 复制 `compose.example.yaml` 为 `compose.yaml`，复制 `.env.example` 为 `.env`，将 `VNC_PASSWD` 改为自己的强密码。
2. 在仓库根目录运行 `docker compose --env-file deployment/.env -f deployment/compose.yaml up -d --build astrbot`。
3. 浏览器打开 `http://127.0.0.1:6185`，完成 AstrBot 初始设置，连接自己的 QQ 平台适配器，并配置模型提供方。
4. 完成 AstrBot 初始启动后，先停止容器，再从仓库根目录运行 `bash scripts/install-runtime.sh deployment/runtime-data`，安装插件源码和配置模板。
5. 重启 AstrBot，再通过管理面板安装插件版本清单中注明“未随仓库分发”的插件。
6. 若使用 SnowLuma，再从仓库根目录运行 `docker compose --env-file deployment/.env -f deployment/compose.yaml --profile qq-client up -d snowluma`，按自己的 QQ 账号完成登录，并让它连接到本 compose 项目的 AstrBot 服务。

`runtime-data/` 是运行目录，包含模型连接、平台账号和插件运行数据。它会被根 `.gitignore` 忽略，不能提交。要把配置迁移到新机器时，先使用本仓库的 `configs/runtime/*.example.json`，再在 AstrBot 中输入个人凭据。
