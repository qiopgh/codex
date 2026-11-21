# Codex CLI 0.171.0 定制迁移

以官方标签 `rust-v0.171.0` 的提交 `ccf9be8cc458bd6b8336fe84d68d8893f2691a5e` 为基线。上一轮官方提交是 `0a94398fa60c4fac0e7659e4213a0a36e613dd46`，上一轮定制源码提交是 `a308c2ff9342b456e86d10cf4bb56a55bf64ef48`。

0.171.0 的普通配置加载仍只接受对内置 `openai` 的目录地址覆盖，合并时仍使用内置推理地址和认证。定制继续允许大小写完全匹配的 `openai` 使用完整的自定义 `ModelProviderInfo`。当该表存在时，用户提供的名称、推理和目录地址、认证、请求头以及能力字段进入运行时。合并仍经过配置校验，名称必须非空，`include_internal_metadata` 只用于运行时。

原补丁的五个文件三方合并无冲突。两个运行时文件分别调整 `openai` 配置验证和完整定义合并。配置要求、通用 `config/value/write` 和合并行为的三个测试文件随补丁迁移。云配置缓存测试使用仍受保留 ID 规则约束的 Ollama。核心目录集成测试使用两个本地端点和完整 `openai` 配置，分别检查目录与推理的路由和现有认证。两棵源码共七个定制文件，迁移后内容相同，`git diff --check` 通过。

新版的 Gateway OAuth 及凭据导出、GCP 和 Bedrock 覆盖、线程独立 provider 与原生 Daybreak 均沿用官方实现。原生 `modelProvider/config/write` 的 CustomGateway 写入规则、`modelProvider/list` 中 OpenAI 的内置分类和摘要仍按 0.171.0 工作。完整小写 `openai` 定义继续通过 TOML 或通用配置写入。官方 bundled 模型目录已有真实 `gpt-daybreak-red-latest` 条目，目录字节保持原样。旧版兼容开关和合成标记逻辑没有恢复。

相较 0.167.1，官方 state 主迁移追加 `0063_session_model_ids.sql` 和 `0064_thread_listing_indexes.sql`，thread-history 追加 `0009_realtime_observation_indexes.sql`。Linux 构建使用官方 LF 版本，Windows 构建在独立工作树准备 CRLF，按现有数据库中的已应用记录核对。

`source-preparation.json` 记录七个迁移文件和初始哈希。构建阶段会生成配置 schema 和必要锁文件。`source-validation.json` 记录最终补丁、两平台定制源码与官方原生实现的校验结果。
