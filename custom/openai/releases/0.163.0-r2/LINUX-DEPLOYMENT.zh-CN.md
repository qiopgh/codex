# Linux 部署记录

上游版本 `0.163.0`，定制修订 `openai-r2`。命令入口 `/home/debian/.local/bin/codex`，当前目标 `/home/debian/.codex/overrides/openai-custom-0.163.0-linux-x86_64-r2/bin/codex`。

完整包安装到新版本目录，旧包保留。原子替换命令符号链接，六个数据库使用 SQLite 只读连接及 backup 制作一致性副本，quick_check 通过。

备份目录：`/home/debian/.codex/backups/cli-before-0.163.0-r2-20261022-095359-892303`。部署记录：`linux-deployment.json`。新 SSH 登录 shell 的命令入口、版本和实际链接见 `linux-login-shell-verification.json`。

现有 config.toml 的地址、认证、请求头、模型目录路径和其他设置保留；按本次简化请求清理旧兼容字段。测试的临时转发地址已恢复。原生控制入口保持原路径，现有 App Server 未由部署步骤终止。用户原生重启 SSH 连接后加载新修订；临时转发进程随原测试后台退出自动清理。
