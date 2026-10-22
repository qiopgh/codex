# Codex CLI 0.163.0：仅保留 openai 自定义 provider 的 openai-r2 修订

基于官方稳定标签 `rust-v0.163.0`，官方提交 `83086188ae0614bd882818ff1aa23f3194962012`。本次按请求简化已有 0.163.0 定制版，不扩大为其他版本升级。`--version` 仍显示 `codex-cli 0.163.0`，通过包内 `custom-build.json` 的 `patch = "openai-r2"` 和 SHA-256 区分修订。

## 定制范围

只保留小写 `openai` 接受完整自定义 provider 定义。现有地址、密钥、请求头、能力覆盖和其他合法配置字段沿用用户定义。`include_internal_metadata` 继续是不可配置、不可序列化的运行时字段。

已删除 Daybreak 兼容标记生成、`experimental_daybreak_app_compat` 配置字段及专门为该机制增加的拦截代码和测试。Daybreak 的程序选择与授权处理沿用官方原生实现；模型名称保持原值。

旧配置若存在 `experimental_daybreak_app_compat = true` 或 `false`，删除该行，其余 provider 配置保留。本机 Linux 已完成此清理。

## 为什么可以删除

2026 年 10 月 22 日，在 Windows Codex App `26.1016.6573.0` 的实际 SSH 连接中，通过 App 原生重启加载关闭标记的配置，核对真实 `model/list` 不含合成标记。用户固定选择 `gpt-6-sol`，手动切换开关并发送消息，捕获到：

| App 状态 | 实际请求字段 | HTTP 状态 |
| --- | --- | --- |
| 开启 | `access_programs.cyber = "daybreak_blue"` | 200 |
| 关闭 | `access_programs.cyber = "standard"` | 200 |

两条请求与同一个原生后台进程的会话记录对应。此结论适用于本次 App、账号连接和模型目录；HTTP 200 不单独证明上游最终执行档位或其他账号权限。公开证据见 `app-ssh-daybreak-ab-public.json`，不含真实认证、会话编号或完整消息。

## 两套完整包

| 平台 | 完整包 | SHA-256 |
| --- | --- | --- |
| windows | `codex-0.163.0-openai-r2-windows-x86_64.zip` | `95fd9ac3ba8db9a1863ec29338d63d3be3fdbb23b2063f251693a9f09259072b` |
| linux | `codex-0.163.0-openai-r2-linux-x86_64.tar.gz` | `30dbf032aa10209affa09395321fb0dfb7929bda23392b9682212ba4ffcccf36` |

两平台均为 x86_64／amd64 64 位。包内保留同版本代码宿主、rg、包布局元数据及全部官方资源。Windows 还包含命令执行器、沙箱设置及沙箱服务程序；Linux 包含 bwrap。逐文件来源见 `custom-build.json`。

Linux 主程序使用 GNU 构建，最高 glibc 符号版本要求为 `GLIBC_2.39`，并依赖 `libssl.so.3`、`libcrypto.so.3`；实际依赖清单见 `binary-inspection.txt`。

## 本机安装结果

Windows App 入口：`C:\Users\qiopgh\.codex\bin\codex.exe`。用户级 `CODEX_CLI_PATH` 继续指向该入口。占用文件按约定暂存，未关闭当前 App：

- `codex.new.exe` → `codex.exe`

退出 App 后完成上述替换，再启动 App。`complete-windows-replacement.ps1` 可核对部署收据并替换，不会关闭进程。

PowerShell 保持原 PATH 入口 `C:\Users\qiopgh\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe`。原 standalone 安装连接、用户 PATH 和自动更新标记保持原状，独立 managed daemon 已同步并验证默认 TUI。

Linux 命令入口：`/home/debian/.local/bin/codex`，已原子切换到 `/home/debian/.codex/overrides/openai-custom-0.163.0-linux-x86_64-r2/bin/codex`。旧包保留；现有 App Server 继续运行，由用户原生重启 SSH 连接后加载新修订。

构建、迁移、验证及备份详情分别见 `BUILD.zh-CN.md`、`validation-summary.json`、`WINDOWS-DEPLOYMENT.zh-CN.md` 和 `LINUX-DEPLOYMENT.zh-CN.md`。

GitHub 修订标签：`custom-v0.163.0-openai-r2`。完整包发布地址：https://github.com/qiopgh/codex/releases/tag/custom-v0.163.0-openai-r2
