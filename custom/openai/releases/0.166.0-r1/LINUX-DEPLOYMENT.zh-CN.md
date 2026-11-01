# Linux 部署记录

上游版本 `0.166.0`，定制修订 `openai-r1`。命令入口 `${LINUX_USER_HOME}/.local/bin/codex`，当前目标 `${LINUX_USER_HOME}/.codex/overrides/openai-custom-0.166.0-linux-x86_64-r1/bin/codex`。

完整包安装到新版本目录，旧包保留。原子替换命令符号链接，6 个数据库使用 SQLite 只读连接及 backup 制作一致性副本，quick_check 通过。

备份目录：`${LINUX_USER_HOME}/.codex/backups/cli-before-0.166.0-20261101-102105-702048`。部署记录：`linux-deployment.json`。新 SSH 登录 shell 的命令入口、版本和实际链接见 `linux-login-shell-verification.json`。

现有 config.toml 的地址、认证、请求头、模型目录路径和其他设置保留，配置中已经没有旧兼容字段。现有 App Server 未由部署步骤终止。用户通过 App 原生重启 SSH 连接后加载新版本；普通断开再连接可能复用已有后台。
