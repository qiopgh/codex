# Codex CLI 的 openai 自定义 provider 修订

当前修订基于官方稳定版 0.163.0，仅保留小写 openai 的完整自定义 provider 定义。原有 Daybreak App 兼容标记、专用配置项和附加校验已删除，相关运行路径恢复为官方代码。

在当前 Codex App 26.1016.6573.0 的真实 SSH 连接中，用户手动开关并发送消息，验证无标记时 gpt-6-sol 分别发送 daybreak_blue 和 standard，两次均返回 HTTP 200。公开摘要不包含认证、会话编号和完整消息。

源码分支 custom/openai-0.163.0-r2，标签 custom-v0.163.0-openai-r2。完整包位于同名 GitHub Release，历史 r1 分支与标签保留。

详细材料见 [0.163.0-r2](releases/0.163.0-r2/README.zh-CN.md)。
