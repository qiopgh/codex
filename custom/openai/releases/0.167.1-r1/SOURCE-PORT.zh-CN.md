# Codex CLI 0.167.1 源码迁移审阅

本轮以官方 `rust-v0.167.1` 对应提交 `0a94398fa60c4fac0e7659e4213a0a36e613dd46` 为源码基线，从上一轮定制提交 `d0387289927d6fe6fdfa72bdc74759a1457b3c39` 迁移小写 `openai` provider 补丁。上一轮官方基线为 `086ccc833bc9cf01024ad2dd6af7dbd421b6bf9a`。

## 上游变更

官方两个稳定版本之间共变更 11 个文件，新增 381 行、删除 47 行。五个定制补丁文件均未发生上游变更，因此本轮三方合并全部干净，未解决任何文本冲突，也不需要增加新的 provider 字段或改变调用签名。

上游变更集中在以下方面，全部保持官方实现：

- `codex-rs/Cargo.toml` 将工作区版本更新为 `0.167.1`。
- `codex-rs/features/src/lib.rs` 新增 `incremental_tools_legacy`，属于开发中能力，默认关闭；Amazon Bedrock 的普通 Responses 路由可使用它选择增量工具布局。
- `codex-rs/core/config.schema.json` 同步新增该特性。后续 schema 生成必须从新版本输入生成，保留这一上游字段。
- `codex-rs/core/src/session/step_context.rs` 新增 `incremental_tools_feature()`，按 Responses Lite 与 Amazon Bedrock 路由选取特性；`incremental_tools_enabled()` 继续依据所选特性的真实开关。
- `codex-rs/core/src/session/turn.rs` 与 `world_state.rs` 调整增量工具声明：WebSearch 继续使用顶层 Responses 配置，其他工具声明进入历史。
- `codex-rs/core/src/compact_remote_v2_attempt.rs` 同步压缩流程的工具历史判定和 WebSearch 配置。
- 上游的 `base_instructions.rs`、`scenarios_incremental_tools.rs` 及两份快照补充相应回归。

## 保留的定制范围

1. `config_toml.rs` 将小写 `openai` 移出保留 provider ID 限制，并要求完整定义提供非空 `name`；其他内置 provider 的限制保留。
2. `model-provider-info/src/lib.rs` 合并小写 `openai` 时保留整个用户定义，包括推理地址、目录地址、密钥来源、请求头、认证和能力配置。
3. provider 定义测试、配置要求测试、App Server 配置写入测试随同迁移。
4. `include_internal_metadata` 继续使用 `#[serde(skip)]` 与 `#[schemars(skip)]`，没有增加外部配置入口。
5. GCP 凭据验证与字段合并、Bedrock 合并、OAuth、Gateway OAuth、原生 cyber 能力和账号校验保持新版官方实现。
6. 不恢复旧 `experimental_daybreak_app_compat`、合成模型标记、别名或专用拦截逻辑。

上一轮迁移脚本曾为新增的 `ModelProviderCapabilities.cyber_access_programs` 补入 `None`。该字段已存在于上一轮定制源码，本轮删除脚本中的一次性插入操作，避免重复字段；迁移后的测试结构仍保留原有 `None`。

## 源码检查结果

- 两棵独立 worktree 均在新官方提交上开始，迁移前工作区干净。
- 五文件三方合并全部成功，两平台对应文件逐字节相同。
- 两平台 `git diff --check` 通过；迁移阶段仅改变所列五个文件。
- 原生 `supports_cyber_access_programs`、GCP 验证及合并函数与新官方相同。
- `capabilities.rs`、`oauth_session.rs`、`gateway_oauth.rs` 及本轮新增量工具实现路径与新官方逐字节相同。
- 官方树没有根 `AGENTS.md`。已跟踪的三份 `AGENTS.md` 分别位于 `code-mode-host`、`exec-server/src/sandbox_integrity`、`tui/src/bottom_pane`，五个补丁文件不在其作用目录内。

机器可读的逐文件 SHA-256 与合并记录见 `source-preparation.json`。本说明只记录源码迁移阶段；格式、schema、锁文件、编译、最终二进制及数据库验证由后续流水线记录，不能据此声称已经通过。
