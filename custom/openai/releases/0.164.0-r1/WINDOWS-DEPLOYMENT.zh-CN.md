# Windows 部署记录

上游版本 `0.164.0`，定制修订 `openai-r1`。App 目录：`${CODEX_HOME}\bin`，用户级 CODEX_CLI_PATH：`${CODEX_HOME}\bin\codex.exe`。包布局 `entrypoint=codex.exe`。完整配套、资源及元数据一起部署。

App 备份：`${CODEX_HOME}\backups\cli-before-0.164.0-20261023-180812`。独立后台备份：`${CODEX_HOME}\backups\runtimes-before-0.164.0-20261023-165759`。数据库均通过 SQLite backup 制作一致性副本，六份 quick_check 通过。

待手动替换文件：

- `codex-code-mode-host.new.exe` → `codex-code-mode-host.exe`
- `codex.new.exe` → `codex.exe`

用户完全退出 App 后替换并重新启动。没有为替换文件关闭 App。PowerShell 原 PATH 入口和当前安装连接保持原状；standalone 和独立 managed daemon 的主程序 SHA-256 已核对。默认 TUI 启动与 /status 验证通过，未提交真实推理消息。

完整文件清单、SHA-256 和实际目标分别见 `windows-deployment.json`、`standalone-deployment.json` 和 `windows-runtimes.json`。新旧引擎数据库副本共存检查见 `windows-db-coexistence.json`。
