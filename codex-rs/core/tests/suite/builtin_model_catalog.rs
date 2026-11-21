//! 小写 `openai` 的自定义目录和推理分别使用各自配置的地址。
#![cfg(test)]

use anyhow::Result;
use codex_login::CodexAuth;
use codex_models_manager::bundled_models_response;
use core_test_support::load_default_config_for_test;
use core_test_support::responses;
use core_test_support::test_codex::test_codex;
use pretty_assertions::assert_eq;
use std::sync::Arc;
use tempfile::TempDir;
use test_case::test_case;
use wiremock::Mock;
use wiremock::MockServer;
use wiremock::ResponseTemplate;
use wiremock::matchers::header;
use wiremock::matchers::method;
use wiremock::matchers::path;

#[test_case(CodexAuth::from_api_key("catalog-routing-test-key"), "Bearer catalog-routing-test-key"; "api_key")]
#[test_case(CodexAuth::create_dummy_chatgpt_auth_for_testing(), "Bearer Access Token"; "chatgpt")]
#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn custom_openai_catalog_preserves_inference_routing(
    auth: CodexAuth,
    authorization: &str,
) -> Result<()> {
    let inference = responses::start_mock_server().await;
    let catalog_server = MockServer::start().await;
    let mut catalog = bundled_models_response()?;
    catalog.models[0].display_name = "显式自定义目录".into();
    Mock::given(method("GET"))
        .and(path("/catalog"))
        .and(header("authorization", authorization))
        .respond_with(ResponseTemplate::new(200).set_body_json(&catalog))
        .mount(&catalog_server)
        .await;
    let home = Arc::new(TempDir::new()?);
    std::fs::write(
        home.path().join("config.toml"),
        format!(
            r#"model_provider = "openai"
[features]
api_key_model_discovery = true
[model_providers.openai]
name = "OpenAI"
base_url = "{}/v1"
model_catalog_url = "{}/catalog"
requires_openai_auth = true
supports_websockets = false
"#,
            inference.uri(),
            catalog_server.uri(),
        ),
    )?;
    let loaded = load_default_config_for_test(&home).await;
    assert_eq!(
        loaded
            .model_provider
            .model_catalog_url
            .as_deref()
            .map(String::as_str),
        Some(format!("{}/catalog", catalog_server.uri()).as_str()),
    );
    assert_eq!(loaded.model_provider_id, "openai");
    assert_eq!(loaded.model_provider.name, "OpenAI");
    let test = test_codex()
        .with_home(home)
        .with_auth(auth)
        .with_config(move |config| {
            config.model_provider = loaded.model_provider.clone();
            config.features = loaded.features;
        })
        .build_with_auto_env(&inference)
        .await?;
    let response = responses::mount_sse_once(&inference, responses::sse_completed("done")).await;
    test.submit_turn("hello").await?;
    assert_eq!(
        response.single_request().header("authorization").as_deref(),
        Some(authorization),
    );
    assert_eq!(
        test.thread_manager
            .get_models_manager()
            .get_remote_models()
            .await,
        catalog.models,
    );
    assert!(
        inference
            .received_requests()
            .await
            .unwrap()
            .iter()
            .all(|request| request.url.path() != "/v1/models")
    );
    assert_eq!(catalog_server.received_requests().await.unwrap().len(), 1);
    Ok(())
}
