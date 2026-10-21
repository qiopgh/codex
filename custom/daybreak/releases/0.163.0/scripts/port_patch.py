"""核对上游变更后迁移 provider 和 Daybreak 补丁，保留所有合并冲突供检查。"""
from pathlib import Path
import json
import re
import subprocess

source = Path("/home/debian/codex-source-0.163.0-linux")
build = Path("/home/debian/codex-build-0.163.0")
assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=source,text=True).strip() == "83086188ae0614bd882818ff1aa23f3194962012"
assert not subprocess.check_output(["git","status","--porcelain"],cwd=source)
patch = (build/"codex-0.162.1-openai-daybreak-r1.patch").read_text()
skip = {"codex-rs/Cargo.lock","codex-rs/core/config.schema.json","justfile"}
record = {
    "base":"rust-v0.163.0","previous":"rust-v0.162.1","applied":[],"regenerate":sorted(skip),
    "upstream_review":[
        "保留新版 provider capabilities 和 include_internal_metadata 的运行时限制",
        "保留原生 Daybreak 及 API-key 程序默认策略，不通过补丁改变授权",
        "保留 ModelClient 新增 output_token_replay_enabled 参数及 HTTP executor 分离",
        "保留响应内容保留注解、会话恢复权限和新增运行时状态结构",
        "兼容能力校验继续位于会话初始化、turn/start 和 HTTP/WebSocket 共用请求构造",
    ],
}
for chunk in re.split(r"(?=^diff --git )",patch,flags=re.M):
    if not chunk.startswith("diff --git "):
        continue
    name = chunk.splitlines()[0].split(" b/",1)[1]
    if name in skip:
        continue
    check = subprocess.run(["git","apply","--check","-"],input=chunk,text=True,cwd=source,capture_output=True)
    args = ["git","apply","-"] if check.returncode == 0 else ["git","apply","--3way","-"]
    result = subprocess.run(args,input=chunk,text=True,cwd=source,capture_output=True)
    entry = {"path":name,"three_way":check.returncode!=0,"exit_code":result.returncode}
    record["applied"].append(entry)
    print(json.dumps(entry),flush=True)
    if result.returncode:
        print(result.stdout+result.stderr,flush=True)
record["conflicts"] = subprocess.check_output(["git","diff","--name-only","--diff-filter=U"],cwd=source,text=True).splitlines()
(build/"port-audit-linux.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"conflicts":record["conflicts"]}),flush=True)

