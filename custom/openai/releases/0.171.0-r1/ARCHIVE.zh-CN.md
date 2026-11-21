# 0.171.0 openai-r1 公开归档

材料记录 2026-11-21 从 0.167.1-openai-r1 迁移到官方稳定版 0.171.0 的 provider 定制完整包。文档和日志中的本机路径已脱敏，原始记录仍保留在交付目录，原件与公开副本哈希见 archive-provenance.json。

五个继承文件合并无冲突，另适配两个测试夹具。Cyber provider 能力、GCP、Bedrock 和 OAuth 沿用新版原生实现。新版新增三条 SQL，Windows 和 Linux 分别按实际数据库重新核对既有迁移校验值。

scripts 中保留本次实际参数，复用前请调整本机路径、版本和缓存。Windows 迁移输入必须独立准备 CRLF，Linux 源码保持 LF，不修改真实数据库的已应用迁移。

historical-app-ssh-daybreak-ab.json 来自 0.163.0 的历史真实 App 对照；本轮仅做本机模拟推理，没有把历史结果当作 0.171.0 的真实问答或账号权限证明。
