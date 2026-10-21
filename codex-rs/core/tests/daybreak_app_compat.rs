use anyhow::Result;
use codex_core::TurnInputRequest;
use codex_core::TurnStartOptions;
use codex_login::CodexAuth;
use codex_protocol::openai_models::ModelAccessPrograms;
use codex_protocol::protocol::EventMsg;
use codex_protocol::protocol::ThreadSettingsOverrides;
use codex_protocol::turn_input::CyberAccessProgram;
use codex_protocol::user_input::UserInput;
use core_test_support::responses;
use core_test_support::test_codex::test_codex;
use core_test_support::wait_for_event;
use pretty_assertions::assert_eq;
use serde_json::json;

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn daybreak_app_compat_websocket_preserves_model_and_blocks_invalid_final_requests()
-> Result<()> {
    let server = responses::start_websocket_server(vec![
        (0..4)
            .map(|n| vec![responses::ev_completed(&format!("compat-ws-{n}"))])
            .collect(),
    ])
    .await;
    let test = test_codex()
        .with_auth(CodexAuth::create_dummy_chatgpt_auth_for_testing())
        .with_model("gpt-5.5")
        .with_model_info_override("gpt-5.5", |model| {
            model.available_access_programs = Some(ModelAccessPrograms {
                cyber: vec![
                    CyberAccessProgram::Standard,
                    CyberAccessProgram::DaybreakBlue,
                ],
            });
        })
        .with_config(|config| {
            config.model_provider.experimental_daybreak_app_compat = true;
            config
                .model_catalog
                .as_mut()
                .expect("测试模型目录")
                .models
                .retain(|model| model.slug == "gpt-5.5");
        })
        .build_with_websocket_server(&server)
        .await?;
    for (program, model, success) in [
        (Some(CyberAccessProgram::DaybreakBlue), None, true),
        (Some(CyberAccessProgram::Standard), None, true),
        (None, None, true),
        (Some(CyberAccessProgram::DaybreakRed), None, false),
        (None, Some("gpt-daybreak-red-latest"), false),
    ] {
        test.codex
            .start_or_steer_turn(
                TurnInputRequest::user_input(vec![UserInput::Text {
                    text: "传输与最终请求校验".to_owned(),
                    text_elements: vec![],
                }])
                .with_thread_settings(ThreadSettingsOverrides {
                    model: model.map(str::to_owned),
                    ..Default::default()
                })
                .on_start(TurnStartOptions {
                    cyber_access_program: program,
                    ..Default::default()
                }),
            )
            .await?;
        let event = wait_for_event(&test.codex, |event| {
            matches!(event, EventMsg::TurnComplete(_) | EventMsg::Error(_))
        })
        .await;
        assert_eq!(
            matches!(event, EventMsg::TurnComplete(_)),
            success,
            "{event:?}"
        );
        if !success {
            wait_for_event(&test.codex, |event| {
                matches!(event, EventMsg::TurnComplete(_))
            })
            .await;
        }
    }
    let requests = server.single_connection();
    assert_eq!(
        requests
            .iter()
            .map(|request| {
                let body = request.body_json();
                (body["model"].clone(), body.get("access_programs").cloned())
            })
            .collect::<Vec<_>>(),
        vec![
            (json!("gpt-5.5"), None),
            (json!("gpt-5.5"), Some(json!({"cyber":"daybreak_blue"}))),
            (json!("gpt-5.5"), Some(json!({"cyber":"standard"}))),
            (json!("gpt-5.5"), None),
        ]
    );
    test.codex.shutdown_and_wait().await?;
    server.shutdown().await;
    Ok(())
}
