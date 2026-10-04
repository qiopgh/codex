# Codex CLI 0.160.0 定制构建说明

## 固定来源和架构

- 官方标签：`rust-v0.160.0`，稳定 Release，非 alpha、非预发布。
- 源码提交：`a956835d020762cb2b570053af06f643a11c0ecc`。
- `codex-rs/rust-toolchain.toml`：Rust 1.95.0，包含 clippy、rustfmt、rust-src。
- 两个平台均为 x86_64／amd64 64 位。
- 构建主机：SSH 别名 `本地ssh虚拟机`，用户 `debian`。
- 独立源码：`${LINUX_USER_HOME}/codex-source-0.160.0-linux`、`${LINUX_USER_HOME}/codex-source-0.160.0-windows`。
- 构建材料：`${LINUX_USER_HOME}/codex-build-0.160.0`。
- 本机适配脚本：`${WORKSPACE}\work\update-0.160.0`。

两个源码目录均从官方标签建立，旧 0.159.3 源码及安装包保留。逐项检查 provider、配置和会话初始化相关上游变化，保留模型目录缓存重构、模型消息字段和空模型目录检查，再迁移已验证补丁。Cargo.lock 和配置 schema 由新版重新生成。交付补丁可直接应用于干净的 0.160.0 源码，不需要依赖旧源码目录。

## 准备源码及 Windows 迁移

先检出固定提交，应用 `codex-0.160.0-openai-daybreak-r1.patch`。Linux 保留迁移 SQL 的 LF；Windows 源码单独准备为 CRLF。

```bash
git checkout --detach rust-v0.160.0
git apply /path/to/codex-0.160.0-openai-daybreak-r1.patch
python3 prepare_windows_migrations.py \
  /path/to/windows-source/codex-rs/state \
  /path/to/windows-migrations-sha384.json \
  --database-migrations /path/to/windows-db-migrations.json \
  --report /path/to/windows-migration-match.json
```

根目录参数必须是 `codex-rs/state`。本次重新生成 73 个 SQL 的清单，并与本机 6 个数据库共 73 条已应用迁移逐条匹配。脚本只改变 Windows 专用源码中的行尾，不修改真实数据库。

若仅验证现有清单和已经准备好的 CRLF 文件，追加 `--check-only`。Linux 使用附带的 LF 检查脚本或等价 SHA-384 检查，禁止复用 Windows 的 SQL 输入。

数据库读取使用 SQLite URI `mode=ro`；一致性快照使用 SQLite backup，所有 Python 连接显式关闭。交付材料不包含真实数据库或配置密钥。

## Linux 原生编译

在 Linux 专用源码的 `codex-rs` 中运行：

```bash
export CARGO_BUILD_JOBS=10
export CARGO_PROFILE_RELEASE_LTO=false
export CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16
export CARGO_PROFILE_RELEASE_DEBUG=0
export CARGO_TARGET_DIR=${LINUX_USER_HOME}/codex-source-0.156.1/codex-rs/target
cargo build --release --locked -p codex-cli --bin codex
```

缓存目录沿用已有 release 构建缓存；源码目录和安装目录仍是新版独立目录。主程序为 x86_64-unknown-linux-gnu 动态链接程序，实际 glibc 及系统库要求以 `binary-inspection.txt` 为准。

## Windows MinGW 交叉编译

在 Windows 专用源码的 `codex-rs` 中运行：

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
  -p codex-windows-sandbox --bin codex-command-runner \
  --bin codex-windows-sandbox-setup \
  -p codex-windows-sandbox-service --bin codex-windows-sandbox-service
```

两平台使用不同 target 缓存，构建可独立进行。Windows 包内主程序及三个沙箱程序为自编译 GNU 程序，其他未受补丁影响的配套来自同版官方 MSVC 完整包。打包脚本检查导入表，发现所需 MinGW 运行库时会递归收集并部署，不假设系统中已安装这些 DLL。

## 官方完整包与组装

官方基础包：

- `codex-package-x86_64-pc-windows-msvc.tar.gz`：SHA-256 `7f7fbbc8d6fd4ea2f3b13855ef47ea59663ba7e61fb2e9821df37163b8030891`。
- `codex-package-x86_64-unknown-linux-musl.tar.gz`：SHA-256 `4fcc47ab57f52ff75363951a8761146cd10c8288bd86fed45487dbb204a16b71`。

以官方完整目录结构为底，替换上述自编译文件。保留 `bin/`、`codex-resources/`、`codex-path/` 和 `codex-package.json`，包括代码宿主、rg、Windows 沙箱资源、Linux bwrap 及官方其他资源。

`package_release.py` 将主程序 target 更新为实际 GNU 目标，逐文件核验未替换资源仍与官方包字节相同，写入来源及 SHA-256 清单，再生成 zip／tar.gz。源码版本、官方资源版本和程序版本一致。

Windows 本机部署将包内 `bin/` 文件放到 `.codex\bin` 根目录，并将 `codex-package.json` 的 `entrypoint` 更新为 `codex.exe`。新版 install-context 在 Windows 上仍支持这个根目录布局。完整包保留通用 `bin/codex.exe` 布局，部署记录另记根目录元数据的哈希。

## 必要检查

按仓库 AGENTS.md 执行 `just write-config-schema`、`just bazel-lock-update`、两棵源码的 `just fmt`、provider 的 `just fix` 和最终 `just fmt-check`。Git 空白检查将 Windows CRLF 作为预期行尾；Linux 源码和交付补丁按常规空白规则检查。

选定测试使用 just／nextest，复用 release 缓存：

```bash
just test --release --locked \
  -p codex-model-provider-info -p codex-config --lib \
  -E 'package(codex-model-provider-info) | test(model_provider)'
just test --release --locked \
  -p codex-core -p codex-app-server --test daybreak_app_compat
just test --release --locked -p codex-models-manager --lib \
  -E 'test(authoritative_catalog_preserves_hidden_models_and_matches_exact_ids) | test(authoritative_catalog_failure_invalidates_cache_until_refresh_succeeds)'
just test --release --locked -p codex-state --lib \
  -E 'test(writable_pool_reads_do_not_wait_for_an_existing_writer) | test(open_read_write_pool_preserves_existing_settings_under_write_lock) | test(open_read_write_pool_preserves_wal_conversion_lock_error)'
just fix -p codex-model-provider-info
just fmt-check
```

core 和 app-server 集成目标在同一条命令中执行，避免同一大型 crate 因拆分测试反复编译。未运行整个仓库测试。检查前后核对源码哈希，若 Clippy 修改源码，必须重新构建交付程序。本次真实结果以 `validation-summary.json` 和原始日志为准。

## 最终二进制验证

`validate_release.py` 使用隔离 CODEX_HOME、本机模拟身份和 127.0.0.1 服务，不访问真实推理上游。两平台分别执行 HTTP 与 WebSocket：

```bash
python3 validate_release.py \
  --binary /path/to/package/bin/codex \
  --catalog /path/to/source/codex-rs/models-manager/models.json \
  --database-source ${LINUX_USER_HOME}/.codex \
  --transport http --output linux-validation.json
python3 validate_release.py \
  --binary /path/to/package/bin/codex \
  --catalog /path/to/source/codex-rs/models-manager/models.json \
  --database-source ${LINUX_USER_HOME}/.codex \
  --transport websocket --output linux-websocket-validation.json
```

Windows 使用本机 Python、codex.exe 及对应 Windows 路径。代码宿主通过新版支持的配置显式禁用回退：

```toml
[features]
code_mode = true
code_mode_host = { enabled = true, disable_in_process_fallback = true }
```

验证不仅检查工具输出，还观察代码宿主子进程的实际路径和 SHA-256。旧脚本的 `[code_mode]` 用户配置已不受新版支持，本次测试夹具已迁移；不修改用户实际配置。

验证覆盖版本、initialize、config/read、自定义 provider 传输、分页 model/list、开关及身份／目录门槛、七个普通模型的程序选择、错误请求拦截、真实 Red 目录、代码宿主和 exec_command、会话恢复、模型目录不变，以及真实数据库一致性副本的启动、迁移与 quick_check。

模拟协议通过、目录声明和真实账号授权分别记录。真实 App 界面、SSH 重连和真实上游推理需要用户重新启动连接后检查；本次不停止现有 App 或远端服务。
