# Codex CLI 0.171.0：仅保留 openai 自定义 provider 的 openai-r1 修订

基于官方稳定标签 `rust-v0.171.0`，官方提交 `ccf9be8cc458bd6b8336fe84d68d8893f2691a5e`。本次于 2026-11-21 从 0.167.1-openai-r1 迁移到执行时确认的最新稳定版 0.171.0，继续只保留 provider 定制。`--version` 仍显示 `codex-cli 0.171.0`，通过包内 `custom-build.json` 的 `patch = "openai-r1"` 和 SHA-256 区分修订。

ChatGPT Learn 官方更新日志已列出 0.171.0。版本由官方更新日志、正式 Release、标签对象与源码提交交叉确认。原始记录见 `official-version-verification.json` 与 `official-latest-recheck.json`。

## 定制范围

只保留小写 `openai` 接受完整自定义 provider 定义。现有地址、密钥、请求头、能力覆盖和其他合法配置字段沿用用户定义。`include_internal_metadata` 继续是不可配置、不可序列化的运行时字段。

此前已删除 Daybreak 兼容标记生成、`experimental_daybreak_app_compat` 配置字段及专门为该机制增加的拦截代码和测试，本轮不恢复这些改动。Daybreak 的程序选择与授权处理沿用官方原生实现；模型名称保持原值。既有 GCP 与 Bedrock 的字段级覆盖约束及 Gateway OAuth 的认证和投递限制保留。

原生 `capabilities.cyber_access_programs` 以显式值优先，省略时按 provider ID 判断，小写 `openai` 默认支持 Cyber 程序。程序和模型的真实权限仍由上游决定。五个原有补丁文件三方合并无冲突，另适配两个相关测试夹具。

0.171.0 官方版本加入 GPT-6.2 Sol 和 Astra 目录支持，默认启用终端工作区。相对 0.167.1，App Server 增加了 provider 专项接口，数据库增加三条迁移。本轮保留原生专项接口的内置 ID 校验，完整小写 `openai` 定义可通过 TOML 或通用配置写入。官方目录原有模型按原值保留。参见 `SOURCE-PORT.zh-CN.md`。

从更早版本迁移时，旧配置若存在 `experimental_daybreak_app_compat = true` 或 `false`，应删除该行，其余 provider 配置保留。本轮保留现有配置，并核对旧兼容字段已经不存在。

## 原生 Daybreak 与验证边界

上一修订已删除兼容标记和专用配置项，本轮继续采用官方原生 Daybreak 程序选择及授权实现。历史 App SSH 对照来自 2026-10-22 的 0.163.0，单独保存在 `historical-app-ssh-daybreak-ab.json`，没有当作本轮新版的真实问答验证。本轮推理检查使用本机模拟服务，真实账号权限与 App 重连后的界面需要分别确认。

## 两套完整包

| 平台 | 完整包 | SHA-256 |
| --- | --- | --- |
| windows | `codex-0.171.0-openai-r1-windows-x86_64.zip` | `ee77bd58fe6e151fa5b7552c7079d9a755560653bae3e75b18271b286627cccd` |
| linux | `codex-0.171.0-openai-r1-linux-x86_64.tar.gz` | `e75649934bd49e25002076b96a29f3aa72a058be759d92977188c20965713c3a` |

两平台均为 x86_64／amd64 64 位。包内保留同版本代码宿主、codex-exec-server、rg、包布局元数据及全部官方资源。Windows 还包含命令执行器、沙箱设置及沙箱服务程序；Linux 包含 bwrap。逐文件来源见 `custom-build.json`。

两平台的 `codex-exec-server` 均已实际运行，完成版本、独立协议握手、命令启动、输出和正常退出验证，二进制 SHA-256 与完整包清单匹配。详情见各平台 `*-exec-server-validation.json`。

Linux 主程序使用 GNU 构建，最高 glibc 符号版本要求为 `GLIBC_2.39`；OpenSSL 及其他实际依赖清单见 `binary-inspection.txt`。

## 本机安装结果

Windows App 入口：`${CODEX_HOME}\bin\codex.exe`。用户级 `CODEX_CLI_PATH` 继续指向该入口。占用文件按约定暂存，未关闭当前 App：

- `codex-code-mode-host.new.exe` → `codex-code-mode-host.exe`
- `codex.new.exe` → `codex.exe`

完全退出 App 后完成上述替换，再启动 App。`complete-windows-replacement.ps1` 可核对部署收据并替换，不会关闭进程。

PowerShell 保持原 PATH 入口 `${WINDOWS_USER_HOME}\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe`。先由官方原生更新器创建 0.171.0 standalone 槽位，再替换为本轮完整定制包；用户 PATH、安装连接结构及更新器机制保留，当前连接与自动更新版本值由正常升级推进到新版。独立 managed daemon 已同步，默认 TUI 启动及 `/status` 已验证，未提交真实推理消息。

Linux 命令入口：`${LINUX_USER_HOME}/.local/bin/codex`，已原子切换到 `${LINUX_USER_HOME}/.codex/overrides/openai-custom-0.171.0-linux-x86_64-r1/bin/codex`。旧包保留；现有 App Server 继续运行，由用户原生重启 SSH 连接后加载新修订。

构建、迁移、验证及备份详情分别见 `BUILD.zh-CN.md`、`validation-summary.json`、`WINDOWS-DEPLOYMENT.zh-CN.md` 和 `LINUX-DEPLOYMENT.zh-CN.md`。

与本次完整包对应的 GitHub 修订标签为 `custom-v0.171.0-openai-r1`。
