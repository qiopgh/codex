# 0.163.0 openai-r2 构建说明

## 来源与最小差异

官方标签 `rust-v0.163.0`，提交 `83086188ae0614bd882818ff1aa23f3194962012`，Rust 1.95.0。本次仅在已有版本上移除兼容补丁。运行时修改集中于 provider 合并和保留 ID 校验，配套测试验证自定义定义和配置写入；锁文件按发布版本归一化，justfile 保留已验证的格式结果。

Daybreak 模型列表、turn/start、共享 HTTP／WebSocket 客户端、会话初始化和远端配置转换与官方提交字节一致，见 `source-validation.json`。配置 schema 已重新生成，内部字段限制保留。

独立源码：`/home/debian/codex-source-0.163.0-linux-r2` 和 `/home/debian/codex-source-0.163.0-windows-r2`。构建材料：`/home/debian/codex-build-0.163.0-r2`。旧源码和包均保留。

```bash
git checkout --detach rust-v0.163.0
git apply /path/to/codex-0.163.0-openai-r2.patch
```

补丁已通过干净官方索引的 `git apply --check --cached` 检查。

## 迁移 SQL

Linux 保持 LF；Windows 在独立源码中准备 CRLF。两平台均重新核对本机六个数据库共 77 条已应用迁移的 SHA-384，未修改真实迁移记录。

```bash
python3 prepare_windows_migrations.py /path/to/windows-source/codex-rs/state \
  windows-migrations-sha384.json \
  --database-migrations windows-db-migrations.json \
  --report windows-migration-match.json
```

根目录必须是 `codex-rs/state`。Windows 源码共 77 个 SQL 文件；Linux 独立清单见 `linux-migration-match.json`。数据库验证通过 SQLite 只读连接及 backup 制作一致性副本，并显式关闭连接。

## 必要准备与编译

使用仓库 `rust-toolchain.toml` 指定的工具链。已执行 `just write-config-schema`、`just bazel-lock-update`、`just fmt`、`just fix -p codex-model-provider-info` 和 `just fmt-check`，然后才编译交付程序。该标签没有根 AGENTS.md，本次未修改局部指令所辖的 TUI bottom_pane 或 exec-server sandbox_integrity。

Linux 原生编译：

```bash
export CARGO_BUILD_JOBS=10
export CARGO_PROFILE_RELEASE_LTO=false
export CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16
export CARGO_PROFILE_RELEASE_DEBUG=0
export CARGO_TARGET_DIR=/home/debian/codex-source-0.156.1/codex-rs/target
cargo build --release --locked -p codex-cli --bin codex
```

Windows MinGW 交叉编译：

```bash
export CARGO_BUILD_JOBS=10
export CARGO_PROFILE_RELEASE_LTO=false
export CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16
export CARGO_PROFILE_RELEASE_DEBUG=0
export CARGO_TARGET_DIR=/home/debian/codex-source-0.156.1/target-win
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

以缓存的同版官方完整包为底，重新核对未替换资源的字节和 SHA-256。主程序及 Windows 三个沙箱程序由本次源码编译，其他配套保留官方原始字节，包括同版代码宿主。

Rust 回归将 provider、配置和 App Server 的选定单元测试合并为一个 nextest 命令，共 41 项通过、844 项按筛选条件跳过。完整命令及结果见 `selected-checks-status.json` 与 `build-logs/selected-regression.log`；未运行整个仓库测试。

两平台最终完整包分别通过 HTTP 和 WebSocket 本机模拟服务验证：版本、initialize、config/read、配置写入、自定义地址／密钥／请求头、分页真实模型列表、七个模型 Blue／Standard 字段、实际代码宿主、exec_command、会话恢复和六个数据库副本启动及 quick_check。另验证官方 API-key 程序开关显式禁用时在发送前拒绝，以及默认开启时按选择转发。

真实 App SSH 对照与上述模拟验证分别记录。真实对照证明客户端发送的程序字段；模拟身份和模拟成功不作为真实上游权限证明。

Windows 部署使用根目录 `entrypoint=codex.exe`；PowerShell standalone 保持原 `bin/codex.exe` 入口。独立后台安装器使用 MSVC 平台槽位标识，`main_target` 如实记录 GNU 编译目标；此适配不改变二进制字节。后续定制更新继续同步 standalone 和 managed daemon，保留现有 PATH 与更新布局。
