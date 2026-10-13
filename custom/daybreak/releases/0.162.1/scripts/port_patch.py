"""在已核对新版核心结构后迁移旧补丁，保留冲突供逐项合并。"""

import json
from pathlib import Path
import re
import subprocess


source = Path("/home/debian/codex-source-0.162.1-linux")
build = Path("/home/debian/codex-build-0.162.1")
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip() == "092d3acd6bec3e3a14bdc7e7a2810ab628ab759d"
assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=source)
patch = (build / "codex-0.160.0-openai-daybreak-r1.patch").read_text(encoding="utf-8")
skip = {"codex-rs/Cargo.lock", "codex-rs/core/config.schema.json"}
record = {
    "base": "rust-v0.162.1", "previous": "rust-v0.160.0", "applied": [], "regenerate": sorted(skip),
    "upstream_review": [
        "保留 ModelProviderInfo.capabilities 及原有内部字段序列化限制",
        "保留上游原生 daybreak 配置与 API-key 程序授权策略",
        "保留新版请求 input 构造、工具缓存、turn root/parent 标识及环境请求结构",
        "会话初始化、turn/start 及 HTTP/WebSocket 共用请求构造继续执行兼容能力检查",
        "旧测试结构字面量与新增字段合并后按新版调用签名编译验证",
    ],
}
for chunk in re.split(r"(?=^diff --git )", patch, flags=re.M):
    if not chunk.startswith("diff --git "):
        continue
    name = chunk.splitlines()[0].split(" b/", 1)[1]
    if name in skip:
        continue
    check = subprocess.run(["git", "apply", "--check", "-"], input=chunk, text=True, cwd=source, capture_output=True)
    command = ["git", "apply", "-"] if check.returncode == 0 else ["git", "apply", "--3way", "-"]
    result = subprocess.run(command, input=chunk, text=True, cwd=source, capture_output=True)
    entry = {"path": name, "three_way": check.returncode != 0, "exit_code": result.returncode}
    record["applied"].append(entry)
    print(json.dumps(entry), flush=True)
    if result.returncode:
        print(result.stdout + result.stderr, flush=True)
record["conflicts"] = subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=U"], cwd=source, text=True).splitlines()
(build / "port-audit-linux.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"conflicts": record["conflicts"]}, ensure_ascii=False), flush=True)
