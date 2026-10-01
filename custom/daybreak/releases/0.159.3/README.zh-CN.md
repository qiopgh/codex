# Codex CLI 0.159.3：openai 自定义与 Daybreak 兼容版

基于执行时核实的官方稳定标签 `rust-v0.159.3`，源码提交 `01fc69f4026735edfdf6789820549727a4867b11`。Windows 和 Linux 两套包均为 x86_64／amd64 64 位，主程序版本输出为 `codex-cli 0.159.3`。

## 来源

- 官方稳定 Release：https://github.com/openai/codex/releases/tag/rust-v0.159.3
- 官方源码提交：https://github.com/openai/codex/commit/01fc69f4026735edfdf6789820549727a4867b11
- 官方更新日志：https://developers.openai.com/codex/changelog/
- Release 公布时间：2026-10-01 06:57:34（Asia/Shanghai）。该版新增符合条件的 ChatGPT 本地会话账号安全提醒。
- 官方更新日志页面已读取；当时页面快照未列出 0.159.3，版本以官方仓库非预发布 Release 和标签解析提交为准。原始 Release 与标签记录一并交付。

## 完整包

| 平台 | 文件 | 包内入口 |
| --- | --- | --- |
| Windows | `codex-0.159.3-openai-daybreak-r1-windows-x86_64.zip` | `bin/codex.exe` |
| Linux | `codex-0.159.3-openai-daybreak-r1-linux-x86_64.tar.gz` | `bin/codex` |

以同版官方完整包为底替换定制主程序，Windows 还替换三个自编译沙箱程序。其余文件包括同版代码宿主、rg、沙箱资源、语音资源及 Linux bwrap，保持官方原始字节。每个文件的来源、SHA-256 和目标架构记录于包内 `custom-build.json`；官方包下载来源及公布校验值见 `official-packages.json`。

## 补丁行为

小写 `openai` 可以接受完整用户 provider 定义，地址、密钥、请求头、查询参数及其他原有可配置字段继续由用户配置。`include_internal_metadata` 保留新版运行时内部字段限制，未开放配置序列化。

`experimental_daybreak_app_compat` 默认关闭。显式开启并满足小写 openai、requires_openai_auth、ChatGPT 身份和真实 Blue 目录能力时，model/list 才生成一个 App 识别标记 `gpt-daybreak-red-latest`。标记只声明 daybreakBlue，不写回模型目录、不能用于推理；真实目录已有 Red 时不额外生成。普通模型名称保持原值。

App 原生开关开启时使用 `access_programs.cyber = "daybreak_blue"`，关闭时使用 `"standard"`。保留会话初始化、turn/start、HTTP／WebSocket 共用请求构造处的能力校验，原有账号授权检查未改动。

## 验证结果

选定 Rust 回归 44 项通过，其中 provider／配置 41 项、HTTP／WebSocket 集成 3 项。完成仓库完整格式检查、schema 生成、Bazel 锁文件更新及 provider Clippy；未运行全仓库测试。

两平台最终二进制分别完成 HTTP 和 WebSocket 验证，每种传输 18 次本机模拟推理请求：initialize、config/read、自定义 openai 地址／密钥／请求头／查询参数、七个普通模型 Blue／Standard 切换、错误选择在发送前拒绝、兼容标记开关及所有门槛、真实 Red 抑制标记、会话保存与恢复、真实代码宿主执行和 exec_command。代码宿主回退已显式关闭，并观察到交付包对应子进程及哈希。

两平台各 6 个真实数据库的一致性副本均可启动，原有 73 条迁移保持匹配，quick_check 均为 ok。本版没有增加迁移 SQL。Windows 的 73 个 SQL 使用 CRLF，Linux 使用 LF；匹配结果和新清单已附。

模拟服务未实现 Apps MCP 等接口，相关 404 属于验证范围限制；日志保留原文。没有向真实上游发送试验推理请求，目录能力与协议成功不代表真实账号授权已验证。

## 已部署状态

Windows 安装目录为 `${CODEX_HOME}\bin`，用户级 CODEX_CLI_PATH 指向其中的正式 `codex.exe`。完整配套及根目录布局元数据已经部署，被占用文件按约定暂存：

| 已暂存的新文件 | 正式名称 |
| --- | --- |
| `codex-code-mode-host.new.exe` | `codex-code-mode-host.exe` |
| `codex.new.exe` | `codex.exe` |

部署后已复核：正式 codex.exe 仍输出 codex-cli 0.159.2，暂存 codex.new.exe 输出 codex-cli 0.159.3。完全退出 App 后覆盖原文件并改为正式名称，再启动 App。也可以在退出 App 后手动执行 complete-windows-replacement.ps1；该脚本先检查占用和哈希，不会关闭任何进程。部署记录准确列出所有暂存名称；本轮未关闭当前 App。

Linux 命令入口 `${LINUX_USER_HOME}/.local/bin/codex` 已原子切换到 `${LINUX_USER_HOME}/.codex/overrides/daybreak-compat-0.159.3-linux-x86_64-r1/bin/codex`。新 SSH 登录 shell 已核对路径、版本和实际链接。旧完整包保留；现有远端进程未终止，由用户重新连接 App 的 SSH 环境后验证界面和真实问答。

配置与模型目录在部署前后保持相同哈希。Windows 顶层 openai provider 未显式设置兼容选项，沿用默认关闭；Linux 原有显式设置为 `true`，原样保留。未增加或修改现有配置字段。

## 备份和平台要求

- Windows：`${CODEX_HOME}\backups\cli-before-0.159.3-20261001-105422`。
- Linux：`${LINUX_USER_HOME}/.codex/backups/cli-before-0.159.3-20261001-105520-778962`。

备份保存原安装或旧包入口记录、配置和一致性数据库快照。恢复数据库前须核对快照后的新聊天数据；本次没有执行回滚。

Linux 主程序为 GNU 动态链接版，实际系统库要求见 `binary-inspection.txt`；已在当前 Debian x86_64 主机运行验证。Windows 为 GNU 交叉编译版，已在当前 Windows 本机运行验证，配套代码宿主取自同版官方 MSVC 包。Windows 导入表和运行库检查记录见 `windows-package.json` 及 `custom-build.json`。

构建参数与复现步骤见 `BUILD.zh-CN.md`。详细验证、部署和备份证据见本目录 JSON 与原始日志。
