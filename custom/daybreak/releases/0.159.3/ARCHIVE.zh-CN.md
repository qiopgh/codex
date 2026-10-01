# 0.159.3 构建归档说明

这些材料记录 2026-10-01 已完成的定制构建、验证和部署。源码以当前分支中的文件为准，附带 patch 用于还原同一组定制改动。部署状态是当时的历史记录。

文档、记录和构建日志中的本机路径已替换为 `${WORKSPACE}`、`${PREVIOUS_WORKSPACE}`、`${CODEX_HOME}`、`${WINDOWS_USER_HOME}` 和 `${LINUX_USER_HOME}`。原始记录仍保留在本机交付目录；`archive-provenance.json` 同时记录原文件与公开副本的哈希。

`scripts/` 保留此次实际使用的脚本，包括当时的固定版本和构建缓存路径。复用前需适配自己的路径；`port_patch.py` 是从 0.159.2 迁移到 0.159.3 的历史脚本。直接使用本分支源码时无需重复应用 patch。

源码迁移 SQL 保持 LF；Windows 构建必须在独立目录中运行 `prepare_windows_migrations.py`，根目录参数是 `codex-rs/state`。校验依据为真实数据库的只读迁移记录，数据库文件没有上传。

`SHA256SUMS.txt` 校验当前归档中的公开副本，`PACKAGE-SHA256SUMS.txt` 校验两套完整安装包。安装包约为 344 MB 和 187 MB，保留在本机交付目录，未放入 Git 历史。

选定的 44 项 Rust 回归和两平台 HTTP／WebSocket 模拟验证已经通过。这些结果覆盖本地协议和交付二进制；真实上游账号权限以及重新连接后的 App 界面仍需分别验证。
