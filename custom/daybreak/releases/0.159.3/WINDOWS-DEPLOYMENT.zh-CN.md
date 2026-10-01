# Windows 0.159.3 部署记录

完整包部署到 `${CODEX_HOME}\bin`，用户级 CODEX_CLI_PATH 为 `${CODEX_HOME}\bin\codex.exe`。部署前正式程序输出 `codex-cli 0.159.2`，实际新文件输出 `codex-cli 0.159.3`。

状态：`awaiting_manual_renames`。逐文件部署校验 48 项通过。完整安装目录、配置、模型目录和 6 个数据库一致性快照备份于 `${CODEX_HOME}\backups\cli-before-0.159.3-20261001-105422`。

## 待替换文件

| 已暂存的新文件 | 正式名称 |
| --- | --- |
| `codex-code-mode-host.new.exe` | `codex-code-mode-host.exe` |
| `codex.new.exe` | `codex.exe` |

完全退出 App 后，用新文件覆盖旧正式文件并重命名。未占用程序已经使用正式名称部署。当前 App 未终止，正式名称被占用时仍保留旧程序。

## 布局与验证

bin 目录保留代码宿主、三个根目录沙箱程序、codex-resources、codex-path 和包元数据。codex-package.json 的 layoutVersion 为 1、entrypoint 为 codex.exe；新版 install-context 仍按该字段识别 Windows 根目录布局。

最终包已经在本机通过 HTTP／WebSocket、真实代码宿主及 exec_command、会话恢复和数据库副本验证。部署时校验实际暂存／正式文件的哈希及新主程序版本。重命名后的 App 启动、实际界面和真实上游问答尚待用户重新启动验证。

配置和模型目录的部署前后哈希相同。详细文件及待重命名映射见 windows-deployment.json，数据库快照清单也保存在备份目录。
