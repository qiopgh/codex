"""逐文件三方合并 provider 定制，保留新版原生协议与授权实现。"""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


ROOT = Path("/home/debian/codex-build-0.165.0")
OLD = Path("/home/debian/codex-source-0.164.0-linux")
BASE = "6aaac694803004a63c6f393d153c96d22521a6b9"
CUSTOM = "3a036e3aaae36f067ae449e306f24b342276b73e"
NEW = "360319d8dee62d87e2d59fc0c21805d79519cfed"
LINUX = Path("/home/debian/codex-source-0.165.0-linux")
WINDOWS = Path("/home/debian/codex-source-0.165.0-windows")
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
    merge_kind = "clean"
    ancestor = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=OLD)
    custom = subprocess.check_output(["git", "show", CUSTOM + ":" + name], cwd=OLD)
    upstream = (LINUX / name).read_bytes()
    with tempfile.TemporaryDirectory(prefix="codex-provider-port-") as temp:
        paths = [Path(temp) / kind for kind in ("custom", "base", "upstream")]
        for path, data in zip(paths, (custom, ancestor, upstream)):
            path.write_bytes(data)
        result = subprocess.run(["git", "merge-file", "-p", *map(str, paths)], capture_output=True)
    if result.returncode and name == "codex-rs/config/src/config_toml.rs":
        merge_kind = "manual_resolution_preserves_gcp_and_bedrock"
        # 新增 GCP 保留原有限制，只允许小写 openai 的完整定义。
        assert upstream.count(b"use codex_model_provider_info::OPENAI_PROVIDER_ID;\n") == 1
        merged = upstream.replace(b"use codex_model_provider_info::OPENAI_PROVIDER_ID;\n", b"")
        merged = merged.replace(b"RESERVED_MODEL_PROVIDER_IDS: [&str; 6]", b"RESERVED_MODEL_PROVIDER_IDS: [&str; 5]")
        merged = merged.replace(b"    OPENAI_PROVIDER_ID,\n", b"")
        assert b"GCP_PROVIDER_ID," in merged and b"OPENAI_PROVIDER_ID" not in merged
        result = subprocess.CompletedProcess(result.args, 0, merged)
    if result.returncode and name == "codex-rs/model-provider-info/src/lib.rs":
        merge_kind = "manual_resolution_preserves_gcp_and_bedrock"
        # 两种云 provider 保持官方覆盖规则；openai 仍使用完整自定义定义。
        merged = upstream.replace(
            b"        } else if key == GCP_PROVIDER_ID {\n",
            b"        } else if key == OPENAI_PROVIDER_ID {\n            model_providers.insert(key, provider);\n        } else if key == GCP_PROVIDER_ID {\n",
        )
        start = merged.index(b"/// Merge configured providers into the built-in provider catalog.")
        end = merged.index(b"pub fn merge_configured_model_providers", start)
        merged = merged[:start] + "/// 将用户配置的 provider 合并到内置目录。\n///\n/// 小写 `openai` 使用完整的自定义定义；Amazon Bedrock 与 GCP 保留官方字段级覆盖规则。\n/// 其他内置 provider 不接受覆盖。\n".encode() + merged[end:]
        assert merged != upstream and merged.count(b"model_providers.insert(key, provider);") == 1
        result = subprocess.CompletedProcess(result.args, 0, merged)
    if result.returncode:
        (ROOT / (Path(name).name + ".conflict")).write_bytes(result.stdout)
        raise RuntimeError("三方合并有冲突，请检查后继续：" + name)
    assert b"experimental_daybreak_app_compat" not in result.stdout
    contents[name] = result.stdout
    records.append({"path": name, "upstream_changed": ancestor != upstream, "three_way_merge": merge_kind,
                    "sha256": hashlib.sha256(result.stdout).hexdigest()})
for source in (LINUX, WINDOWS):
    for name, content in contents.items():
        (source / name).write_bytes(content)
    subprocess.run(["git", "diff", "--check"], cwd=source, check=True)
record = {"version": "0.165.0", "revision": "openai-r1", "previous_custom_commit": CUSTOM,
          "previous_official_commit": BASE, "base_commit": NEW, "sources": [str(LINUX), str(WINDOWS)],
          "files": records, "manual_conflicts_resolved": sum(item["three_way_merge"] != "clean" for item in records), "daybreak_compat_removed_in_previous_revision": True,
          "only_provider_customization_ported": True}
(ROOT / "source-preparation.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(record, ensure_ascii=False))
