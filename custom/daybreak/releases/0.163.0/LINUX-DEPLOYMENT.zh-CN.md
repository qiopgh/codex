# Linux 0.163.0 部署记录

SSH 主机 `本地ssh虚拟机`，用户 `debian`，x86_64／amd64。命令 `${LINUX_USER_HOME}/.local/bin/codex` 指向 `${LINUX_USER_HOME}/.codex/overrides/daybreak-compat-0.163.0-linux-x86_64-r1/bin/codex`，新登录 shell 已核对 `codex-cli 0.163.0`。

完整包 43 个文件通过校验，代码宿主、rg、bwrap 实际启动通过。已安装二进制完成隔离验证和数据库副本检查。配置、目录及 Daybreak 设置保持原样。

备份 `${LINUX_USER_HOME}/.codex/backups/cli-before-0.163.0-20261021-125639-424347`；旧 0.162.1 包保留。没有终止已有远端 App Server，用户重新连接后再确认 App 界面和真实上游问答。
