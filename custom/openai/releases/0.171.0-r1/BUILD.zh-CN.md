# 0.171.0 openai-r1 构建说明

## 来源与最小差异

官方标签 `rust-v0.171.0`，提交 `ccf9be8cc458bd6b8336fe84d68d8893f2691a5e`，Rust 1.99.1。五个原有定制文件逐个进行了三方合并，共 0 处冲突。本轮另适配两个测试夹具。运行时修改集中于小写 openai 的完整 provider 合并与配置校验。GCP、Bedrock、Gateway OAuth 及原生 `cyber_access_programs` 行为沿用新版实现。

新版增加 provider 专项接口和 `model/list` 的可选 `modelProvider` 字段。源码审计核对专项接口、官方模型目录和原生能力检查。协议和配套包实查记录见 `protocol-package-review.json`。

Daybreak 模型列表、turn/start、共享 HTTP／WebSocket 客户端、会话初始化和远端配置转换与官方提交字节一致，见 `source-validation.json`。配置 schema 已重新生成，内部字段限制保留。

独立源码：`${LINUX_USER_HOME}/codex-source-0.171.0-linux` 和 `${LINUX_USER_HOME}/codex-source-0.171.0-windows`。构建材料：`${LINUX_USER_HOME}/codex-build-0.171.0`。旧源码和包均保留。

```bash
git checkout --detach rust-v0.171.0
git apply /path/to/codex-0.171.0-openai-r1.patch
```

补丁已通过干净官方索引的 `git apply --check --cached` 检查。

定制分支已经包含这些改动，直接构建本分支时无需重复应用补丁。上述命令适用于从干净官方标签重建定制源码。

## 迁移 SQL

Linux 保持 LF；Windows 在独立源码中准备 CRLF。两平台分别按本机实际数据库重新核对已应用迁移的 SHA-384，未修改真实迁移记录。下表由本轮迁移匹配报告生成：

| 平台 | 源码 SQL 数 | 已核对数据库数 | 已匹配迁移数 |
| --- | --- | --- | --- |
| windows | 81 | 7 | 80 |
| linux | 81 | 6 | 78 |

```bash
python3 prepare_windows_migrations.py /path/to/windows-source/codex-rs/state \
  windows-migrations-sha384.json \
  --database-migrations windows-db-migrations.json \
  --report windows-migration-match.json
```

根目录必须是 `codex-rs/state`。新版增加 state 0063、0064 和 thread history 0009，既有 SQL 字节不变。Windows 新旧引擎共存验证中的 state 数据库副本应用了 64 条迁移。Windows 清单见 `windows-migrations-sha384.json` 与 `windows-migration-match.json`，Linux 核对见 `linux-migration-match.json`。验证通过 SQLite 只读连接及 backup 制作一致性副本，连接在使用后显式关闭。

## 必要准备与编译

使用仓库 `rust-toolchain.toml` 指定的工具链。配置 schema、Bazel 锁文件、格式和 provider Clippy 的命令及执行结果见 `prepare-status.json`。

本轮工具链与 Windows 交叉目标的安装命令：

```bash
rustup toolchain install 1.99.1 --profile minimal \
  --component clippy,rustfmt,rust-src --target x86_64-pc-windows-gnu
```

Linux 原生编译：

```bash
export CARGO_BUILD_JOBS=10
export CARGO_PROFILE_RELEASE_LTO=false
export CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16
export CARGO_PROFILE_RELEASE_DEBUG=0
export CARGO_TARGET_DIR=${LINUX_USER_HOME}/codex-source-0.156.1/codex-rs/target
cargo build --release --locked -p codex-cli --bin codex
```

Windows MinGW 交叉编译：

```bash
export CARGO_BUILD_JOBS=10
export CARGO_PROFILE_RELEASE_LTO=false
export CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16
export CARGO_PROFILE_RELEASE_DEBUG=0
export CARGO_TARGET_DIR=${LINUX_USER_HOME}/codex-source-0.156.1/target-win
export CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER=x86_64-w64-mingw32-gcc
export CC_x86_64_pc_windows_gnu=x86_64-w64-mingw32-gcc
export CXX_x86_64_pc_windows_gnu=x86_64-w64-mingw32-g++-posix
export AR_x86_64_pc_windows_gnu=x86_64-w64-mingw32-ar
cargo build --release --locked --target x86_64-pc-windows-gnu \
  -p codex-cli --bin codex \
  -p codex-windows-sandbox --bin codex-command-runner --bin codex-windows-sandbox-setup \
  -p codex-windows-sandbox-service --bin codex-windows-sandbox-service
```

缓存可以复用，源码必须分开。实际系统库及 DLL 要求见 `binary-inspection.txt`。Windows 运行库由打包脚本按导入表收集。

## 完整包与验证

以重新下载并核对 SHA-256 的同版官方完整包为底，重新核对未替换资源的字节和 SHA-256。主程序及 Windows 三个沙箱程序由本次源码编译，其他配套保留官方原始字节，包括同版代码宿主。

Rust 回归用一个 nextest 命令执行选定的测试。完整命令、运行与跳过数量见 `selected-checks-status.json` 和 `build-logs/selected-regression.log`。

首次运行在集成测试枚举阶段触发发布模式的临时目录校验，原始日志保存在 `build-logs/selected-regression-first-discovery.log`。复验使用 `release-test-home.patch`，让测试夹具在 `TEST_TMPDIR` 指定的构建专用目录创建测试用 `CODEX_HOME`。用 `run_selected_checks.py` 执行时会应用并回退这份测试专用补丁，同时核对恢复后的源码哈希。产品源码补丁和成品程序均沿用原生目录校验。

两平台最终完整包分别通过 HTTP 和 WebSocket 本机模拟服务验证：版本、initialize、config/read、配置写入、自定义地址／密钥／请求头、分页模拟目录和普通模型名称、Blue／Standard 字段、实际代码宿主、exec_command、会话恢复和数据库副本启动及 quick_check。另验证官方 API-key 程序开关显式禁用时在发送前拒绝，以及默认开启时按选择转发。共 4 份最终二进制报告，各项数量由实际结果生成：

新版对 ChatGPT 身份显式选择的程序先检查 provider 的 `cyber_access_programs` 能力，再沿用原生转发逻辑；模型支持和账号授权由上游裁决。本机目录与协议验证不证明真实上游权限，也不声称按目录在客户端拒绝 Blue。release 构建仍加载适用的系统 managed policy，测试环境中的 `CODEX_APP_SERVER_DISABLE_MANAGED_CONFIG` 仅对 debug 构建有效。

| 验证报告 | 检查项数 | 本机模拟请求数 | 数据库副本数 |
| --- | --- | --- | --- |
| windows-validation | 16 | 27 | 7 |
| windows-websocket-validation | 16 | 27 | 7 |
| linux-validation | 16 | 27 | 6 |
| linux-websocket-validation | 16 | 27 | 6 |

同版独立命令服务另有 2 份执行报告，均完成 `initialize`、`process/start`、标记输出及服务退出检查，SHA-256 与最终完整包清单一致：

| 平台 | 命令服务版本 | 命令退出码 | 服务退出码 |
| --- | --- | --- | --- |
| windows | `codex-exec-server 0.171.0` | 0 | 0 |
| linux | `codex-exec-server 0.171.0` | 0 | 0 |

验证脚本需要 Python 3.12 或更新版本。需要解压 zstd 请求时，按 `validation-requirements.txt` 将依赖安装到脚本同目录的 `validation-deps`，例如 `python3 -m pip install --target validation-deps -r validation-requirements.txt`；依赖只用于验证，不属于 CLI 运行安装要求。

历史 App SSH 对照单独标明原日期和 0.163.0 版本，本轮没有发送真实推理消息。模拟身份和模拟成功不作为真实上游权限证明。

Windows App 布局为 `entrypoint=codex.exe`、`execServer=bin/codex-exec-server.exe`。执行服务由内层 bin 读取父目录的包版本。PowerShell 独立安装继续使用原 `bin/codex.exe` 入口和原生更新布局。独立后台安装器使用 MSVC 平台槽位标识，实际 GNU 编译目标记录在 `main_target`。
