# Linux 0.159.3 部署记录

SSH 主机：本地ssh虚拟机；用户：debian；架构：x86_64／amd64 64 位。

命令入口 `${LINUX_USER_HOME}/.local/bin/codex` 已通过原子替换符号链接切换到 `${LINUX_USER_HOME}/.codex/overrides/daybreak-compat-0.159.3-linux-x86_64-r1/bin/codex`，新登录 shell 输出 codex-cli 0.159.3。完整包 44 个文件哈希通过，代码宿主、rg、bwrap 的实际启动检查通过。

安装后的实际二进制通过 HTTP 隔离验证，并在数据库一致性副本上验证原有迁移及 quick_check。最终包还完成 WebSocket 验证。目录能力和身份均为模拟数据，没有重新证明真实上游权限。

配置及 model_catalog_json 内容保持相同哈希，兼容选项沿用 `true`。旧 0.159.2 完整包保留在原目录，备份路径为 `${LINUX_USER_HOME}/.codex/backups/cli-before-0.159.3-20261001-105520-778962`，包括配置、6 个数据库一致性快照、安装验证和部署记录。

现有远端 App Server 未重启或终止，已加载旧程序的进程继续运行。用户自行重新连接 App 的 SSH 环境并测试实际界面和问答。重新登录 shell 的证据见 linux-login-shell.txt。
