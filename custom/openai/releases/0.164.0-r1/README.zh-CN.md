# Codex CLI 0.164.0：仅保留 openai 自定义 provider 的 openai-r1 修订

基于官方稳定标签 `rust-v0.164.0`，官方提交 `6aaac694803004a63c6f393d153c96d22521a6b9`。本次从 0.163.0-openai-r2 迁移到执行时确认的最新稳定版 0.164.0，继续只保留 provider 定制。`--version` 仍显示 `codex-cli 0.164.0`，通过包内 `custom-build.json` 的 `patch = "openai-r1"` 和 SHA-256 区分修订。

官方文档更新日志已转到 ChatGPT Learn，本次打开的文档页尚未列出 0.164.0。官方源码 CHANGELOG 指向 GitHub Releases，因此以最新正式 Release、标签对象及其提交交叉确认版本，并在部署前再次复核。原始记录见 `official-version-verification.json` 与 `official-latest-recheck.json`。

## 定制范围

只保留小写 `openai` 接受完整自定义 provider 定义。现有地址、密钥、请求头、能力覆盖和其他合法配置字段沿用用户定义。`include_internal_metadata` 继续是不可配置、不可序列化的运行时字段。

已删除 Daybreak 兼容标记生成、`experimental_daybreak_app_compat` 配置字段及专门为该机制增加的拦截代码和测试。Daybreak 的程序选择与授权处理沿用官方原生实现；模型名称保持原值。

旧配置若存在 `experimental_daybreak_app_compat = true` 或 `false`，删除该行，其余 provider 配置保留。本机 Linux 已完成此清理。

## 原生 Daybreak 与验证边界

上一修订已删除兼容标记和专用配置项，本轮继续采用官方原生 Daybreak 程序选择及授权实现。历史 App SSH 对照来自 2026-10-22 的 0.163.0，单独保存在 `historical-app-ssh-daybreak-ab.json`，没有当作本轮新版的真实问答验证。本轮推理检查使用本机模拟服务，真实账号权限与 App 重连后的界面需要分别确认。

## 两套完整包

| 平台 | 完整包 | SHA-256 |
| --- | --- | --- |
| windows | `codex-0.164.0-openai-r1-windows-x86_64.zip` | `3585b721eb37b42faa025d51d2845fe1af05e87ed8bcbb3776878508c349292b` |
| linux | `codex-0.164.0-openai-r1-linux-x86_64.tar.gz` | `38e2d760119507548426a86580b72be656455e1549c891b54d33be0b5774a4b2` |

两平台均为 x86_64／amd64 64 位。包内保留同版本代码宿主、rg、包布局元数据及全部官方资源。Windows 还包含命令执行器、沙箱设置及沙箱服务程序；Linux 包含 bwrap。逐文件来源见 `custom-build.json`。

Linux 主程序使用 GNU 构建，最高 glibc 符号版本要求为 `GLIBC_2.39`；OpenSSL 及其他实际依赖清单见 `binary-inspection.txt`。

## 本机安装结果

Windows App 入口：`${CODEX_HOME}\bin\codex.exe`。用户级 `CODEX_CLI_PATH` 继续指向该入口。占用文件按约定暂存，未关闭当前 App：

- `codex-code-mode-host.new.exe` → `codex-code-mode-host.exe`
- `codex.new.exe` → `codex.exe`

退出 App 后完成上述替换，再启动 App。`complete-windows-replacement.ps1` 可核对部署收据并替换，不会关闭进程。

PowerShell 保持原 PATH 入口 `${WINDOWS_USER_HOME}\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe`。原 standalone 安装连接、用户 PATH 和自动更新标记保持原状，独立 managed daemon 已同步并验证默认 TUI。

Linux 命令入口：`${LINUX_USER_HOME}/.local/bin/codex`，已原子切换到 `${LINUX_USER_HOME}/.codex/overrides/openai-custom-0.164.0-linux-x86_64-r1/bin/codex`。旧包保留；现有 App Server 继续运行，由用户原生重启 SSH 连接后加载新修订。

构建、迁移、验证及备份详情分别见 `BUILD.zh-CN.md`、`validation-summary.json`、`WINDOWS-DEPLOYMENT.zh-CN.md` 和 `LINUX-DEPLOYMENT.zh-CN.md`。

GitHub 修订标签：`custom-v0.164.0-openai-r1`。完整包发布地址：https://github.com/qiopgh/codex/releases/tag/custom-v0.164.0-openai-r1
