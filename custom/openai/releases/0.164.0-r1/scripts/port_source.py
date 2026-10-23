"""逐文件三方合并 provider 定制，保留新版原生协议与授权实现。"""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


ROOT = Path("/home/debian/codex-build-0.164.0")
OLD = Path("/home/debian/codex-source-0.163.0-linux-r2")
BASE = "83086188ae0614bd882818ff1aa23f3194962012"
CUSTOM = "867108b73f73931d426ab00bfccac76f2e253203"
NEW = "6aaac694803004a63c6f393d153c96d22521a6b9"
LINUX = Path("/home/debian/codex-source-0.164.0-linux")
WINDOWS = Path("/home/debian/codex-source-0.164.0-windows")
names = (
    "codex-rs/config/src/config_toml.rs",
    "codex-rs/config/src/model_provider_requirements_tests.rs",
    "codex-rs/app-server/src/config_manager_service_tests.rs",
    "codex-rs/model-provider-info/src/lib.rs",
    "codex-rs/model-provider-info/src/model_provider_info_tests.rs",
)
records = []
contents = {}
for source in (LINUX, WINDOWS):
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip() == NEW
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=source)
for name in names:
    ancestor = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=OLD)
    custom = subprocess.check_output(["git", "show", CUSTOM + ":" + name], cwd=OLD)
    upstream = (LINUX / name).read_bytes()
    with tempfile.TemporaryDirectory(prefix="codex-provider-port-") as temp:
        paths = [Path(temp) / kind for kind in ("custom", "base", "upstream")]
        for path, data in zip(paths, (custom, ancestor, upstream)):
            path.write_bytes(data)
        result = subprocess.run(["git", "merge-file", "-p", *map(str, paths)], capture_output=True)
    if result.returncode:
        (ROOT / (Path(name).name + ".conflict")).write_bytes(result.stdout)
        raise RuntimeError("三方合并有冲突，请检查后继续：" + name)
    assert b"experimental_daybreak_app_compat" not in result.stdout
    contents[name] = result.stdout
    records.append({"path": name, "upstream_changed": ancestor != upstream, "three_way_merge": "clean",
                    "sha256": hashlib.sha256(result.stdout).hexdigest()})
for source in (LINUX, WINDOWS):
    for name, content in contents.items():
        (source / name).write_bytes(content)
    subprocess.run(["git", "diff", "--check"], cwd=source, check=True)
record = {"version": "0.164.0", "revision": "openai-r1", "previous_custom_commit": CUSTOM,
          "previous_official_commit": BASE, "base_commit": NEW, "sources": [str(LINUX), str(WINDOWS)],
          "files": records, "daybreak_compat_removed_in_previous_revision": True,
          "only_provider_customization_ported": True}
(ROOT / "source-preparation.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(record, ensure_ascii=False))
