use anyhow::Result;
use app_test_support::ChatGptAuthFixture;
use app_test_support::TestAppServer;
use app_test_support::write_chatgpt_auth;
use codex_app_server_protocol::ClientRequest;
use codex_app_server_protocol::CyberAccessProgram;
use codex_app_server_protocol::ModelListParams;
use codex_app_server_protocol::ModelListResponse;
use codex_app_server_protocol::RequestId;
use codex_app_server_protocol::ThreadResumeParams;
use codex_app_server_protocol::ThreadResumeResponse;
use codex_app_server_protocol::ThreadStartParams;
use codex_app_server_protocol::TurnStartParams;
use codex_app_server_protocol::TurnStatus;
use codex_app_server_protocol::UserInput;
use codex_login::AuthCredentialsStoreMode;
use codex_protocol::openai_models::ModelAccessPrograms;
use codex_protocol::openai_models::ModelVisibility;
use codex_protocol::openai_models::ModelsResponse;
use codex_protocol::turn_input::CyberAccessProgram as CoreProgram;
use core_test_support::responses;
use pretty_assertions::assert_eq;
use serde_json::json;
use std::path::Path;
use tempfile::TempDir;
use wiremock::MockServer;

const MARKER: &str = "gpt-daybreak-red-latest";
const MODELS: [&str; 7] = [
    "gpt-6.1-sol",
    "gpt-6-sol",
    "gpt-6-luna",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-5.5",
];

async fn start_app(home: &Path, server: &MockServer) -> Result<TestAppServer> {
    let template = codex_models_manager::bundled_models_response()?
        .models
        .into_iter()
        .find(|model| model.slug == "gpt-5.5")
        .expect("测试模型模板");
    let models = MODELS
        .into_iter()
        .chain(["gpt-6-astra"])
        .map(|name| {
            let mut model = template.clone();
            model.slug = name.to_owned();
            model.visibility = ModelVisibility::List;
            model.available_access_programs = Some(ModelAccessPrograms {
                cyber: if name == "gpt-6-astra" {
                    vec![CoreProgram::Standard]
                } else {
                    vec![CoreProgram::Standard, CoreProgram::DaybreakBlue]
                },
            });
            model
        })
        .collect();
    let catalog = home.join("models.json");
    std::fs::write(&catalog, serde_json::to_vec(&ModelsResponse { models })?)?;
    let endpoint = server.uri();
    std::fs::write(
        home.join("config.toml"),
        format!(
            r#"
model = "gpt-6-sol"
model_provider = "openai"
model_catalog_json = {catalog:?}
approval_policy = "never"
cli_auth_credentials_store = "file"
[model_providers.openai]
name = "OpenAI"
base_url = "{endpoint}/v1"
requires_openai_auth = true
supports_websockets = false
experimental_daybreak_app_compat = true
"#
        ),
    )?;
    write_chatgpt_auth(
        home,
        ChatGptAuthFixture::new("daybreak-compat-test").plan_type("pro"),
        AuthCredentialsStoreMode::File,
    )?;
    TestAppServer::builder()
        .with_plugin_startup_tasks()
        .with_codex_home(home)
        .without_managed_config()
        .with_env_overrides(&[("OPENAI_API_KEY", None), ("CODEX_API_KEY", None)])
        .build_initialized()
        .await
}

#[tokio::test]
async fn daybreak_app_compat_lists_one_marker_and_preserves_models_across_turns_and_resume()
-> Result<()> {
    let server = responses::start_mock_server().await;
    let requests = responses::mount_sse_sequence(
        &server,
        (0..15)
            .map(|n| responses::sse(vec![responses::ev_completed(&format!("compat-{n}"))]))
            .collect(),
    )
    .await;
    let home = TempDir::new()?;
    let mut app = start_app(home.path(), &server).await?;
    let mut items = Vec::new();
    let mut cursor = None;
    loop {
        let page: ModelListResponse = app
            .request(|request_id| ClientRequest::ModelList {
                request_id,
                params: ModelListParams {
                    limit: Some(2),
                    cursor,
                    include_hidden: Some(true),
                },
            })
            .await?;
        items.extend(page.data);
        cursor = page.next_cursor;
        if cursor.is_none() {
            break;
        }
    }
    assert_eq!(items.len(), 9);
    let marker = items
        .iter()
        .find(|model| model.model == MARKER)
        .expect("协议标记");
    assert_eq!((marker.hidden, marker.is_default), (false, false));
    assert_eq!(
        serde_json::to_value(&marker.available_access_programs)?,
        json!({"cyber":["daybreakBlue"]})
    );
    let catalog = std::fs::read_to_string(home.path().join("models.json"))?;
    assert!(!catalog.contains(MARKER));
    let thread = app
        .start_thread(ThreadStartParams {
            daybreak_enabled: Some(true),
            ..Default::default()
        })
        .await?
        .thread;
    let mut expected = Vec::new();
    for (index, model) in MODELS.into_iter().enumerate() {
        for program in [
            CyberAccessProgram::DaybreakBlue,
            CyberAccessProgram::Standard,
        ] {
            let mut params = TurnStartParams {
                thread_id: thread.id.clone(),
                model: Some(model.to_owned()),
                cyber_access_program: Some(program),
                input: vec![UserInput::Text {
                    text: "兼容性测试".to_owned(),
                    text_elements: vec![],
                }],
                ..Default::default()
            };
            if index % 2 == 0 {
                params.model = Some("gpt-6-astra".to_owned());
                params.collaboration_mode = Some(serde_json::from_value(json!({
                    "mode":"default", "settings":{"model":model,"reasoning_effort":"medium","developer_instructions":null}
                }))?);
            }
            let completed = app.start_turn_and_wait_for_completion(params).await?;
            assert_eq!(completed.turn.status, TurnStatus::Completed);
            expected.push((
                model.to_owned(),
                if program == CyberAccessProgram::DaybreakBlue {
                    "daybreak_blue"
                } else {
                    "standard"
                },
            ));
        }
    }
    app.shutdown_gracefully().await?;
    let mut app = start_app(home.path(), &server).await?;
    let resumed: ThreadResumeResponse = app
        .request(|request_id| ClientRequest::ThreadResume {
            request_id,
            params: ThreadResumeParams {
                thread_id: thread.id.clone(),
                ..Default::default()
            },
        })
        .await?;
    assert_eq!(resumed.thread.daybreak_enabled, Some(true));
    let completed = app
        .start_turn_and_wait_for_completion(TurnStartParams {
            thread_id: thread.id,
            cyber_access_program: Some(CyberAccessProgram::DaybreakBlue),
            input: vec![UserInput::Text {
                text: "恢复后的测试".to_owned(),
                text_elements: vec![],
            }],
            ..Default::default()
        })
        .await?;
    assert_eq!(completed.turn.status, TurnStatus::Completed);
    expected.push(("gpt-5.5".to_owned(), "daybreak_blue"));
    let actual = requests
        .requests()
        .into_iter()
        .map(|request| {
            let body = request.body_json();
            (
                body["model"].as_str().unwrap().to_owned(),
                body["access_programs"]["cyber"]
                    .as_str()
                    .unwrap()
                    .to_owned(),
            )
        })
        .collect::<Vec<_>>();
    assert_eq!(
        actual,
        expected
            .into_iter()
            .map(|(m, p)| (m, p.to_owned()))
            .collect::<Vec<_>>()
    );
    app.shutdown_gracefully().await?;
    Ok(())
}

#[tokio::test]
async fn daybreak_app_compat_rejects_marker_and_unsupported_program_before_inference() -> Result<()>
{
    let server = responses::start_mock_server().await;
    let home = TempDir::new()?;
    let mut app = start_app(home.path(), &server).await?;
    let id = app
        .send_thread_start_request_with_auto_env(ThreadStartParams {
            model: Some(MARKER.to_owned()),
            ..Default::default()
        })
        .await?;
    let error = app
        .read_stream_until_error_message(RequestId::Integer(id))
        .await?;
    assert!(error.error.message.contains("兼容标记"));
    let thread = app.start_thread(ThreadStartParams::default()).await?.thread;
    for (model, program, collaboration) in [
        ("gpt-6-astra", CyberAccessProgram::DaybreakBlue, false),
        ("gpt-6-sol", CyberAccessProgram::DaybreakRed, false),
        (MARKER, CyberAccessProgram::Standard, false),
        (MARKER, CyberAccessProgram::DaybreakBlue, true),
    ] {
        let mut params = TurnStartParams {
            thread_id: thread.id.clone(),
            model: Some(model.to_owned()),
            cyber_access_program: Some(program),
            input: vec![UserInput::Text {
                text: "应被拒绝".to_owned(),
                text_elements: vec![],
            }],
            ..Default::default()
        };
        if collaboration {
            params.model = Some("gpt-6-sol".to_owned());
            params.collaboration_mode = Some(serde_json::from_value(json!({
                "mode":"default", "settings":{"model":model,"reasoning_effort":"medium","developer_instructions":null}
            }))?);
        }
        let id = app.send_turn_start_request(params).await?;
        let error = app
            .read_stream_until_error_message(RequestId::Integer(id))
            .await?;
        assert_eq!(error.error.code, -32600);
        assert!(error.error.message.contains("兼容标记") || error.error.message.contains("未声明"));
    }
    assert!(
        server
            .received_requests()
            .await
            .unwrap()
            .iter()
            .all(|request| request.url.path() != "/v1/responses")
    );
    app.shutdown_gracefully().await?;
    Ok(())
}
