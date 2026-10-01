# Codex CLI 定制源码与构建记录

本分支基于官方稳定版 `rust-v0.159.3`，源码提交 `01fc69f4026735edfdf6789820549727a4867b11`。源码已包含小写 `openai` 自定义 provider 与 Daybreak App 兼容补丁。

小写 `openai` 接受完整用户 provider 定义；`include_internal_metadata` 继续受内部字段限制。`experimental_daybreak_app_compat` 默认关闭。启用后只有满足身份、provider 和真实目录能力门槛，才在 `model/list` 生成只声明 Blue 的兼容标记。标记不能用于推理，也不会写回真实目录；普通模型名称保持原值。

App 原生开关为每轮选择 `access_programs.cyber = "daybreak_blue"` 或 `"standard"`，保留会话初始化、turn/start 和 HTTP／WebSocket 共享请求构造处的能力校验及账号授权检查。

- [0.159.3 归档说明](releases/0.159.3/ARCHIVE.zh-CN.md)
- [构建说明](releases/0.159.3/BUILD.zh-CN.md)
- [源码验证](releases/0.159.3/source-validation.json)
- [交付验证汇总](releases/0.159.3/validation-summary.json)
- [完整安装包校验值](releases/0.159.3/PACKAGE-SHA256SUMS.txt)

后续升级时先确认官方稳定版本，再从对应标签建立新的定制分支并迁移补丁。Windows 与 Linux 使用独立构建目录；Windows 的 CRLF 迁移输入由准备脚本生成。
