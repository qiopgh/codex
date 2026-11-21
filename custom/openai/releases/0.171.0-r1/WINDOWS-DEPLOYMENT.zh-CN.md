# Windows 部署记录

上游版本 `0.171.0`，定制修订 `openai-r1`。App 目录为 `${CODEX_HOME}\bin`，用户级 CODEX_CLI_PATH 指向 `${CODEX_HOME}\bin\codex.exe`。根目录包布局为 `entrypoint=codex.exe`、`execServer=bin/codex-exec-server.exe`。完整配套、资源及元数据一起部署。执行服务在内层 bin 握手时能读到正确的包版本。

App 备份：`${CODEX_HOME}\backups\cli-before-0.171.0-20261121-175709`。独立后台备份：`${CODEX_HOME}\backups\runtimes-before-0.171.0-20261121-155757`。数据库均通过 SQLite backup 制作一致性副本，本次 Windows 备份清单中 7 份 quick_check 通过。

待手动替换文件：

- `codex-code-mode-host.new.exe` → `codex-code-mode-host.exe`
- `codex.new.exe` → `codex.exe`

完全退出 App 后完成上述替换，再启动 App。`complete-windows-replacement.ps1` 可核对部署收据并替换，不会关闭进程。

没有为替换文件关闭 App。PowerShell 原 PATH 入口和安装连接结构保留，先通过官方更新器升级到新版槽位再部署同版定制包，自动更新版本值随正常升级更新；standalone 和独立 managed daemon 的主程序 SHA-256 已核对。默认 TUI 启动与 /status 验证通过，未提交真实推理消息。

最终包另在隔离的 App 根目录布局中验证 `initialize`、`config/read`、`account/read`、会话创建、执行服务及数据库副本，结果见 `windows-app-root-validation.json`。桌面 App 冷启动和真实问答待完成文件替换后验收。完整文件清单和实际目标见 `windows-deployment.json`、`standalone-deployment.json` 和 `windows-runtimes.json`。新旧引擎数据库副本共存检查见 `windows-db-coexistence.json`。
