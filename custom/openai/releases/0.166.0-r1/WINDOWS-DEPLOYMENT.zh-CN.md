# Windows 部署记录

上游版本 `0.166.0`，定制修订 `openai-r1`。App 目录：`${CODEX_HOME}\bin`，用户级 CODEX_CLI_PATH：`${CODEX_HOME}\bin\codex.exe`。根目录包布局为 `entrypoint=codex.exe`、`execServer=codex-exec-server.exe`。完整配套、资源及元数据一起部署。

App 备份：`${CODEX_HOME}\backups\cli-before-0.166.0-20261101-101935`。独立后台备份：`${CODEX_HOME}\backups\runtimes-before-0.166.0-20261101-084630`。数据库均通过 SQLite backup 制作一致性副本，本次 Windows 备份清单中 7 份 quick_check 通过。

待手动替换文件：

- `codex-code-mode-host.new.exe` → `codex-code-mode-host.exe`
- `codex.new.exe` → `codex.exe`

用户完全退出 App 后替换并重新启动。没有为替换文件关闭 App。PowerShell 原 PATH 入口和安装连接结构保留，先通过官方更新器升级到新版槽位再部署同版定制包，自动更新版本值随正常升级更新；standalone 和独立 managed daemon 的主程序 SHA-256 已核对。默认 TUI 启动与 /status 验证通过，未提交真实推理消息。

完整文件清单、SHA-256 和实际目标分别见 `windows-deployment.json`、`standalone-deployment.json` 和 `windows-runtimes.json`。新旧引擎数据库副本共存检查见 `windows-db-coexistence.json`。
