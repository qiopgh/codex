"""逐文件迁移上一版 provider 定制，并核对新版原生能力与认证边界。"""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


ROOT = Path("/home/debian/codex-build-0.171.0")
OLD = Path("/home/debian/codex-source-0.167.1-linux")
BASE = "0a94398fa60c4fac0e7659e4213a0a36e613dd46"
CUSTOM = "a308c2ff9342b456e86d10cf4bb56a55bf64ef48"
NEW = "ccf9be8cc458bd6b8336fe84d68d8893f2691a5e"
LINUX = Path("/home/debian/codex-source-0.171.0-linux")
WINDOWS = Path("/home/debian/codex-source-0.171.0-windows")
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
    with tempfile.TemporaryDirectory(prefix="codex-provider-port-") as temporary:
        paths = [Path(temporary) / kind for kind in ("custom", "base", "upstream")]
        for path, data in zip(paths, (custom, ancestor, upstream)):
            path.write_bytes(data)
        result = subprocess.run(["git", "merge-file", "-p", *map(str, paths)], capture_output=True)
    assert result.returncode == 0, "三方合并发生未审阅冲突：" + name
    text = result.stdout.decode()
    assert not any(marker in text for marker in ("<<<<<<<", "=======", ">>>>>>>", "experimental_daybreak_app_compat"))
    contents[name] = text.encode()
    records.append({"path": name, "upstream_changed": ancestor != upstream, "three_way_merge": "clean",
                    "semantic_adaptations": [], "sha256": hashlib.sha256(contents[name]).hexdigest()})

# 云端要求验证继续测试被保留的内置 ID。核心集成验证使用完整小写 openai 定义。
for name, replacements, summary in (
    (
        "codex-rs/cloud-config/src/service_tests.rs",
        (("[model_providers.openai]\\nname = 'Reserved'", "[model_providers.ollama]\\nname = 'Reserved'"),),
        "保留非法内置 provider 不得写入云配置缓存的覆盖，非法 ID 改用 Ollama。",
    ),
    (
        "codex-rs/core/tests/suite/builtin_model_catalog.rs",
        (
            ("//! Built-in OpenAI catalog routing uses configured metadata without redirecting inference.",
             "//! 小写 `openai` 的自定义目录和推理分别使用各自配置的地址。"),
            ("builtin_openai_catalog_override_preserves_inference", "custom_openai_catalog_preserves_inference_routing"),
            ('"Explicit built-in catalog"', '"显式自定义目录"'),
            ('openai_base_url = "{}/v1"\n[features]\napi_key_model_discovery = true\n'
             '[model_providers.openai]\nmodel_catalog_url = "https://chatgpt.com/backend-api/codex/models"\n',
             '[features]\napi_key_model_discovery = true\n[model_providers.openai]\n'
             'name = "OpenAI"\nbase_url = "{}/v1"\nmodel_catalog_url = "{}/catalog"\n'
             'requires_openai_auth = true\nsupports_websockets = false\n'),
            ('            inference.uri(),\n', '            inference.uri(),\n            catalog_server.uri(),\n'),
            ('    let mut loaded = load_default_config_for_test(&home).await;',
             '    let loaded = load_default_config_for_test(&home).await;'),
            ('        Some("https://chatgpt.com/backend-api/codex/models"),',
             '        Some(format!("{}/catalog", catalog_server.uri()).as_str()),'),
            ('    // Config validation uses the production allowlist. Redirect only this test\'s\n'
             '    // runtime catalog client to a local server to capture credential routing.\n'
             '    loaded.model_provider.model_catalog_url =\n'
             '        Some(format!("{}/catalog", catalog_server.uri()).into());\n', ''),
            ('            config.model_provider.supports_websockets = false;\n', ''),
        ),
        "从实际 TOML 加载完整小写 openai 定义，在本地分别验证目录和推理的地址及认证。",
    ),
):
    upstream = (LINUX / name).read_bytes()
    text = upstream.decode()
    for before, after in replacements:
        assert text.count(before) == 1, (name, before)
        text = text.replace(before, after, 1)
    contents[name] = text.encode()
    upstream_changes = subprocess.check_output(["git", "diff", "--name-only", BASE, NEW, "--", name], cwd=LINUX)
    records.append({"path": name, "upstream_changed": bool(upstream_changes), "three_way_merge": "test_fixture_adaptation",
                    "semantic_adaptations": [summary], "sha256": hashlib.sha256(contents[name]).hexdigest()})

lib = contents["codex-rs/model-provider-info/src/lib.rs"].decode()
official_lib = (LINUX / "codex-rs/model-provider-info/src/lib.rs").read_text()
assert lib.count("if key == OPENAI_PROVIDER_ID {") == 1
assert "model_providers.insert(key, provider);" in lib
assert '#[serde(skip)]\n    #[schemars(skip)]\n    pub include_internal_metadata: bool' in lib
for start, end in (
    ("    pub fn supports_cyber_access_programs(", "    pub fn is_openai("),
    ("    pub fn validate_gcp_credential_file(", "    pub fn validate("),
    ("    pub fn validate(&self) -> std::result::Result", "    /// Resolve configured request headers"),
    ("        } else if matches!(\n            key.as_str(),\n            AMAZON_BEDROCK_PROVIDER_ID", "pub fn create_oss_provider("),
    ("pub fn merge_gcp_provider_overrides(", "pub fn create_oss_provider("),
):
    actual = lib[lib.index(start):lib.index(end, lib.index(start))]
    expected = official_lib[official_lib.index(start):official_lib.index(end, official_lib.index(start))]
    assert actual == expected, start
config = contents["codex-rs/config/src/config_toml.rs"].decode()
assert 'if key.as_str() == "openai"' not in config
assert '&& provider.name.trim().is_empty()' in config
assert "provider\n                .validate_gcp_credential_file()" in config
assert "/// 目录请求使用该 provider 的凭据，只应配置用户信任的端点。" in lib
native = (
    "codex-rs/model-provider-info/src/capabilities.rs",
    "codex-rs/model-provider-info/src/oauth_session.rs",
    "codex-rs/model-provider-info/src/gateway_oauth.rs",
    "codex-rs/model-provider/src/catalog_factory.rs",
    "codex-rs/model-provider/src/models_endpoint.rs",
    "codex-rs/model-provider/src/request_setup.rs",
    "codex-rs/model-provider/src/gateway_auth.rs",
    "codex-rs/model-provider/src/gateway_export.rs",
    "codex-rs/app-server/src/request_processors/account_processor/gateway_oauth.rs",
    "codex-rs/core/src/compact_remote_v2_attempt.rs",
    "codex-rs/core/src/session/step_context.rs",
    "codex-rs/core/src/session/turn.rs",
    "codex-rs/core/src/session/world_state.rs",
    "codex-rs/features/src/lib.rs",
)
for source in (LINUX, WINDOWS):
    for name, content in contents.items():
        (source / name).write_bytes(content)
    subprocess.run(["git", "diff", "--check"], cwd=source, check=True)
    assert set(subprocess.check_output(["git", "diff", "--name-only"], cwd=source, text=True).splitlines()) == set(contents)
    assert all((source / name).read_bytes() == content for name, content in contents.items())
    for name in native:
        official = subprocess.check_output(["git", "show", NEW + ":" + name], cwd=source)
        assert (source / name).read_bytes() == official, name
record = {"version": "0.171.0", "revision": "openai-r1", "previous_custom_commit": CUSTOM,
          "previous_official_commit": BASE, "base_commit": NEW, "sources": [str(LINUX), str(WINDOWS)],
          "files": records, "manual_conflicts_resolved": 0,
          "native_cyber_capability_and_oauth_boundaries_preserved": True,
          "gcp_validation_and_merge_preserved": True, "internal_metadata_not_configurable": True,
          "daybreak_compat_removed_in_previous_revision": True, "only_provider_customization_ported": True}
(ROOT / "source-preparation.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(record, ensure_ascii=False))
