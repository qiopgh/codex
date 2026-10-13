# Windows 0.162.1 部署记录

安装目录 `${CODEX_HOME}\bin`；用户级 CODEX_CLI_PATH 为 `${CODEX_HOME}\bin\codex.exe`。状态 `awaiting_manual_renames`，备份 `${CODEX_HOME}\backups\cli-before-0.162.1-20261013-114029`。

根目录布局的 entrypoint 为 `codex.exe`，codex-resources、codex-path、代码宿主和沙箱程序均已部署；48 项文件核对通过。

| 已暂存的新文件 | 正式名称 |
| --- | --- |
| `codex-code-mode-host.new.exe` | `codex-code-mode-host.exe` |
| `codex.new.exe` | `codex.exe` |

正式入口版本 `codex-cli 0.160.0`，交付新程序版本 `codex-cli 0.162.1`。完全退出 App 后完成待替换文件并重新启动，实际 App 使用需另行确认。数据库备份通过 SQLite backup 制作，真实迁移记录未修改。
