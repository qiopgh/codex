# Codex CLI 0.163.0：openai 自定义与 Daybreak 兼容版

基于执行时核实的官方稳定标签 `rust-v0.163.0`，源码提交 `83086188ae0614bd882818ff1aa23f3194962012`。两平台均为 x86_64／amd64 64 位。

## 官方来源及本次迁移

- 官方源码更新日志：https://github.com/openai/codex/blob/rust-v0.163.0/CHANGELOG.md
- 官方稳定 Release：https://github.com/openai/codex/releases/tag/rust-v0.163.0
- 官方提交：https://github.com/openai/codex/commit/83086188ae0614bd882818ff1aa23f3194962012
- 官方发布时间：2026-10-16 05:30:38（Asia/Shanghai）。官方源码 CHANGELOG 指向 Releases，本版为稳定发布，非预发布、非草稿。

官方文档站的更新日志已迁移到 ChatGPT Learn；其 CLI 分类当前未列出本版。版本以官方仓库最新稳定 Release、对应标签及提交交叉核对，详情见 `official-version-verification.json`。

本次从 0.162.1 迁移；25 个定制源码文件未产生合并冲突。保留新版 provider capabilities、原生 Daybreak 默认设置、API-key 程序门槛、HTTP executor 分离、output_token_replay_enabled 参数及响应内容保留注解。Cargo.lock、配置 schema 和 Bazel 锁文件按新版核对或生成。

上游 0.163.0 将 cli_daybreak 和 api_key_cyber_access_programs 设为稳定、默认开启。本补丁保留这些默认策略；配置中的显式设置继续生效，实际权限仍由真实目录、账号和上游服务判断。兼容标记开关 experimental_daybreak_app_compat 仍单独默认关闭。

## 完整安装包

| 平台 | 文件 | 包内入口 |
| --- | --- | --- |
| Windows | `codex-0.163.0-openai-daybreak-r1-windows-x86_64.zip` | `bin/codex.exe` |
| Linux | `codex-0.163.0-openai-daybreak-r1-linux-x86_64.tar.gz` | `bin/codex` |

以同版官方完整包为底，替换定制主程序，Windows 另替换三个自编译沙箱程序。代码宿主、rg、沙箱资源、语音及 Linux bwrap 保留同版官方原始字节。包内 `custom-build.json` 记录每个文件的来源和 SHA-256。

## 定制行为

小写 `openai` 接受完整自定义 provider，包括地址、密钥、请求头及新版 capabilities。`include_internal_metadata` 仍是内部字段，不开放配置序列化。

`experimental_daybreak_app_compat` 默认关闭。显式开启且满足小写 openai、requires_openai_auth、ChatGPT 身份和真实 Blue 目录能力时，`model/list` 生成 `gpt-daybreak-red-latest` 标记，元数据只声明 Blue。标记不能推理、不写回目录；真实目录存在 Red 能力时不另生成。普通模型名称保持原值。

App 原生开关为每轮选择 `access_programs.cyber = "daybreak_blue"` 或 `"standard"`。保留会话初始化、turn/start 和共享 HTTP／WebSocket 请求构造处的能力校验与账号授权检查。

## 验证范围

选定 Rust 回归 61 项通过：provider／配置与能力 45 项，目录缓存 2 项，HTTP／WebSocket 集成 3 项，SQLite 连接锁与完整性验证 11 项。完成 schema、锁文件、格式和 provider Clippy 检查；未运行全仓库测试。

两平台最终二进制分别完成 HTTP 和 WebSocket 模拟验证，覆盖版本、initialize、config/read、自定义传输字段、七个普通模型 Blue／Standard、标记门槛和错误选择拦截、会话保存恢复、实际代码宿主与 exec_command。代码宿主回退被禁用，并核对了实际子进程路径和哈希。

两平台各六个真实数据库的一致性副本启动、迁移及 quick_check 通过，75 条既有迁移匹配。Windows 的 77 个 SQL 为 CRLF，Linux 为 LF。本版新增 Guardian 审核反馈与线程已读状态两条迁移。API-key 显式禁用时仍在请求发出前拒绝程序选择，默认开启时的 Blue／Standard 转发也完成模拟验证。

模拟服务没有实现的接口错误保留在原始日志中。目录声明、模拟协议、真实账号权限和重启后的 App 界面是不同证据；本次没有向真实上游发起推理试验。

## 部署与备份

Windows 正式入口为 `${CODEX_HOME}\bin\codex.exe`，状态 `awaiting_manual_renames`。实际正式入口版本 `codex-cli 0.162.1`，交付新程序版本 `codex-cli 0.163.0`。

| 已暂存的新文件 | 正式名称 |
| --- | --- |
| `codex-code-mode-host.new.exe` | `codex-code-mode-host.exe` |
| `codex.new.exe` | `codex.exe` |

如有暂存文件，由用户完全退出 App 后替换为正式名称，再重新启动 App。`complete-windows-replacement.ps1` 可在退出后核对并替换，不会关闭进程。

PowerShell 继续使用原 PATH 入口 `${WINDOWS_USER_HOME}\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe`，其完整包已同步为本轮定制版。默认 TUI 的独立 managed daemon 也已通过原生 --from-cli 机制同步，并检查实际 TUI 启动和 /status。用户 PATH、现有 current 连接及自动更新标记保留。后续升级需一并同步后台包；普通 daemon update 会恢复官方生产更新来源。

Linux 命令入口 `${LINUX_USER_HOME}/.local/bin/codex` 已原子切换到 `${LINUX_USER_HOME}/.codex/overrides/daybreak-compat-0.163.0-linux-x86_64-r1/bin/codex`。新 SSH 登录 shell 核对了路径和版本；旧包保留，已有远端进程继续运行，由用户重新连接 App 的 SSH 环境后检查界面和真实问答。

- Windows 备份：`${CODEX_HOME}\backups\cli-before-0.163.0-20261021-125746`。
- Linux 备份：`${LINUX_USER_HOME}/.codex/backups/cli-before-0.163.0-20261021-125639-424347`。

部署阶段核对现有配置和模型目录，保留当前设置；交互验证带来的界面偏好变化单独记录，不回退用户设置。Linux 主程序为 GNU 动态链接版，Windows 为 GNU 交叉编译版，同版代码宿主使用官方程序。系统库及 DLL 要求见 `binary-inspection.txt`，构建步骤见 `BUILD.zh-CN.md`。
