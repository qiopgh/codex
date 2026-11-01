"""逐文件三方合并 provider 定制，保留新版原生协议与授权实现。"""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path("/home/debian/codex-build-0.166.0")
OLD = Path("/home/debian/codex-source-0.165.0-linux")
BASE = "360319d8dee62d87e2d59fc0c21805d79519cfed"
CUSTOM = "9cbc20ac226fbc7c0289cd9d5ae6c19465aa420c"
NEW = "6ff1e1ca3b30fc8b914720681fcf5fe62e95f856"
LINUX = Path("/home/debian/codex-source-0.166.0-linux")
WINDOWS = Path("/home/debian/codex-source-0.166.0-windows")
names = (
    "codex-rs/config/src/config_toml.rs",
    "codex-rs/config/src/model_provider_requirements_tests.rs",
    "codex-rs/app-server/src/config_manager_service_tests.rs",
    "codex-rs/model-provider-info/src/lib.rs",
    "codex-rs/model-provider-info/src/model_provider_info_tests.rs",
)


def replace_once(text, original, replacement):
    """只替换已审阅的新版本代码块，输入漂移时停止迁移。"""
    assert text.count(original) == 1, original[:160]
    return text.replace(original, replacement, 1)


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
    assert result.returncode in (0, 1), result.stderr.decode()
    text = result.stdout.decode()
    resolutions = []
    if result.returncode:
        assert name == "codex-rs/model-provider-info/src/lib.rs", name
        conflicts = re.findall(r"^<<<<<<< .*?\n(.*?)^=======\n(.*?)^>>>>>>> .*?\n", text, flags=re.M | re.S)
        assert len(conflicts) == 1 and conflicts[0][0].startswith("/// 小写 `openai`"), conflicts
        text = re.sub(r"^<<<<<<< .*?\n(.*?)^=======\n(.*?)^>>>>>>> .*?\n", lambda match: match[1], text, flags=re.M | re.S)
        merge_kind = "manual_conflict_resolved"
        resolutions.append("保留中文 full custom openai 合并说明，GCP 与 Bedrock 沿用新版受限分支")
    if name == "codex-rs/config/src/config_toml.rs":
        text = replace_once(text, '''            if key.as_str() == "openai" {
                let provider = &model_providers[*key];
                return provider
                    != &ModelProviderInfo {
                        model_catalog_url: provider.model_catalog_url.clone(),
                        ..Default::default()
                    };
            }
''', "")
        text = replace_once(text, ''') && key != "openai"
            && provider.name.trim().is_empty()''', ''') && provider.name.trim().is_empty()''')
        resolutions.append("移除新版 catalog-only openai 特例，完整自定义定义继续接受通用 provider 校验")
    if name == "codex-rs/model-provider-info/src/lib.rs":
        start = text.index("    /// Optional full URL for a Codex-native model catalog.")
        end = text.index("    pub model_catalog_url:", start)
        text = text[:start] + '''    /// 可选的 Codex 原生模型目录完整地址；端点必须返回 Codex 目录格式。
    /// 小写 `openai` 与其他自定义 provider 一样保留用户指定的目录地址、推理地址和认证。
    /// 目录请求使用该 provider 的凭据，只应配置用户信任的端点。
    /// 请求构造、URL 处理和认证仍由原生运行路径校验；配置地址不代表获得目录或模型权限。
''' + text[end:]
        start = text.index('        if key == "openai" {', text.index("pub fn merge_configured_model_providers("))
        end = text.index("        } else if matches!(", start)
        text = text[:start] + '''        if key == OPENAI_PROVIDER_ID {
            model_providers.insert(key, provider);
''' + text[end:]
        text = replace_once(text, '''        } else if key == OPENAI_PROVIDER_ID {
            model_providers.insert(key, provider);
        } else if key == GCP_PROVIDER_ID {''', '''        } else if key == GCP_PROVIDER_ID {''')
        resolutions.append("用完整 openai 定义替换新版 catalog-only 合并分支，并去除旧迁移的重复分支")
    if name == "codex-rs/model-provider-info/src/model_provider_info_tests.rs":
        start = text.index("#[test]\nfn builtin_openai_catalog_override_preserves_inference_and_identity()")
        text = text[:start] + '''#[test]
fn custom_openai_catalog_override_preserves_full_definition() {
    for inference_url in [None, Some("https://us.api.openai.com/v1")] {
        for catalog_url in [None, Some("https://chatgpt.com/backend-api/codex/models")] {
            let configured: ModelProviderInfo = toml::from_str(&format!(
                "name = \\"自定义 OpenAI\\"\\nbase_url = \\"https://proxy.example/v1\\"\\nrequires_openai_auth = false\\n{}",
                catalog_url.map(|url| format!("model_catalog_url = {url:?}")).unwrap_or_default()
            )).unwrap();
            let builtins = built_in_model_providers(inference_url.map(str::to_owned));
            let mut expected = builtins.clone();
            expected.insert(OPENAI_PROVIDER_ID.to_string(), configured.clone());
            assert_eq!(
                merge_configured_model_providers(
                    builtins,
                    HashMap::from([(OPENAI_PROVIDER_ID.to_string(), configured)]),
                ).unwrap(),
                expected,
            );
        }
    }
}

#[test]
fn custom_openai_catalog_uses_custom_provider_merge_semantics() {
    // 合并层保留原始配置；端点的实际连接与认证继续由原生请求路径处理。
    for url in [
        "http://chatgpt.com/backend-api/codex/models",
        "https://chatgpt.com.evil.example/models",
        "https://evilchatgpt.com/models",
        "https://api.openai.com/v1/models",
        "https://example.com/models?secret=do-not-log",
        "https://user:secret@chatgpt.com/models",
        "/models",
        "not a URL",
    ] {
        let provider = ModelProviderInfo {
            name: "自定义目录".into(),
            model_catalog_url: Some(url.into()),
            ..Default::default()
        };
        for key in [OPENAI_PROVIDER_ID, "custom"] {
            let mut expected = built_in_model_providers(/*openai_base_url*/ None);
            expected.insert(key.into(), provider.clone());
            assert_eq!(
                merge_configured_model_providers(
                    built_in_model_providers(/*openai_base_url*/ None),
                    HashMap::from([(key.into(), provider.clone())]),
                ).unwrap(),
                expected,
            );
        }
    }
}

#[test]
fn custom_openai_catalog_keeps_definition_on_chatgpt_hosts() {
    for host in [
        "chatgpt.com",
        "gov.chatgpt.com",
        "chat.openai.com",
        "chatgpt-staging.com",
        "api.chatgpt-staging.com",
        "CHATGPT.COM",
    ] {
        let provider = ModelProviderInfo {
            name: "自定义目录".into(),
            base_url: Some("https://proxy.example/v1".into()),
            model_catalog_url: Some(format!("https://{host}/backend-api/codex/models").into()),
            ..Default::default()
        };
        let mut expected = built_in_model_providers(/*openai_base_url*/ None);
        expected.insert(OPENAI_PROVIDER_ID.to_string(), provider.clone());
        assert_eq!(
            merge_configured_model_providers(
                built_in_model_providers(/*openai_base_url*/ None),
                HashMap::from([(OPENAI_PROVIDER_ID.to_string(), provider)]),
            ).unwrap(),
            expected,
        );
    }
}
'''
        resolutions.append("三条新版 catalog-only 回归改为完整自定义定义的预期，保留通用 URL 与认证层测试")
    assert not any(marker in text for marker in ("<<<<<<<", "=======", ">>>>>>>", "experimental_daybreak_app_compat"))
    contents[name] = text.encode()
    records.append({"path": name, "upstream_changed": ancestor != upstream, "three_way_merge": merge_kind,
                    "semantic_adaptations": resolutions, "sha256": hashlib.sha256(contents[name]).hexdigest()})
for source in (LINUX, WINDOWS):
    for name, content in contents.items():
        (source / name).write_bytes(content)
    subprocess.run(["git", "diff", "--check"], cwd=source, check=True)
record = {"version": "0.166.0", "revision": "openai-r1", "previous_custom_commit": CUSTOM,
          "previous_official_commit": BASE, "base_commit": NEW, "sources": [str(LINUX), str(WINDOWS)],
          "files": records, "manual_conflicts_resolved": sum(item["three_way_merge"] != "clean" for item in records), "daybreak_compat_removed_in_previous_revision": True,
          "only_provider_customization_ported": True}
(ROOT / "source-preparation.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(record, ensure_ascii=False))
