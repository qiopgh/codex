use super::*;
use pretty_assertions::assert_eq;

fn model(programs: Vec<CyberAccessProgram>) -> ModelInfo {
    let mut model: ModelInfo = toml::from_str(
        r#"
slug = "ordinary-model"
display_name = "普通模型"
supported_reasoning_levels = []
shell_type = "disabled"
visibility = "list"
supported_in_api = true
priority = 0
support_verbosity = false
experimental_supported_tools = []
truncation_policy = { mode = "tokens", limit = 1000 }
"#,
    )
    .unwrap();
    model.available_access_programs = Some(ModelAccessPrograms { cyber: programs });
    model
}

#[test]
fn marker_requires_explicit_opt_in_chatgpt_openai_and_real_blue() {
    let mut provider = ModelProviderInfo {
        requires_openai_auth: true,
        experimental_daybreak_app_compat: true,
        ..Default::default()
    };
    let preset = ModelPreset::from(model(vec![CyberAccessProgram::DaybreakBlue]));
    let catalog = vec![preset.clone()];
    let marker = provider
        .daybreak_app_compat_marker("openai", &catalog, /*is_chatgpt_auth*/ true)
        .unwrap();
    assert_eq!(
        (
            marker.model.as_str(),
            marker.is_default,
            marker.show_in_picker
        ),
        (MARKER, false, true)
    );
    assert_eq!(
        marker.available_access_programs,
        preset.available_access_programs
    );
    assert_eq!(catalog, vec![preset]);
    assert!(
        provider
            .daybreak_app_compat_marker("OpenAI", &catalog, /*is_chatgpt_auth*/ true)
            .is_none()
    );
    assert!(
        provider
            .daybreak_app_compat_marker("openai", &catalog, /*is_chatgpt_auth*/ false)
            .is_none()
    );
    for programs in [
        vec![],
        vec![CyberAccessProgram::Standard],
        vec![
            CyberAccessProgram::DaybreakBlue,
            CyberAccessProgram::DaybreakRed,
        ],
    ] {
        assert!(
            provider
                .daybreak_app_compat_marker(
                    "openai",
                    &[model(programs).into()],
                    /*is_chatgpt_auth*/ true
                )
                .is_none()
        );
    }
    let mut red = model(vec![CyberAccessProgram::DaybreakBlue]);
    red.slug = MARKER.to_owned();
    assert!(
        provider
            .daybreak_app_compat_marker("openai", &[red.into()], /*is_chatgpt_auth*/ true)
            .is_none()
    );
    provider.experimental_daybreak_app_compat = false;
    assert!(
        provider
            .daybreak_app_compat_marker("openai", &catalog, /*is_chatgpt_auth*/ true)
            .is_none()
    );
}

#[test]
fn requests_reject_marker_and_unsupported_programs_without_rewriting_models() {
    let mut provider = ModelProviderInfo {
        experimental_daybreak_app_compat: true,
        ..Default::default()
    };
    let blue = model(vec![
        CyberAccessProgram::Standard,
        CyberAccessProgram::DaybreakBlue,
    ]);
    let original = blue.clone();
    for program in [
        None,
        Some(CyberAccessProgram::Standard),
        Some(CyberAccessProgram::DaybreakBlue),
    ] {
        provider
            .validate_daybreak_app_compat(&blue, program)
            .unwrap();
    }
    assert_eq!(blue, original);
    assert!(
        provider
            .validate_daybreak_app_compat(&blue, Some(CyberAccessProgram::DaybreakRed))
            .is_err()
    );
    assert!(
        provider
            .validate_daybreak_app_compat(&model(vec![]), Some(CyberAccessProgram::DaybreakBlue))
            .is_err()
    );
    let mut marker = blue;
    marker.slug = MARKER.to_owned();
    for program in [
        None,
        Some(CyberAccessProgram::Standard),
        Some(CyberAccessProgram::DaybreakBlue),
    ] {
        assert!(
            provider
                .validate_daybreak_app_compat(&marker, program)
                .is_err()
        );
    }
    marker.available_access_programs = Some(ModelAccessPrograms {
        cyber: vec![CyberAccessProgram::DaybreakRed],
    });
    provider
        .validate_daybreak_app_compat(&marker, Some(CyberAccessProgram::DaybreakRed))
        .unwrap();
    provider.experimental_daybreak_app_compat = false;
    provider
        .validate_daybreak_app_compat(&model(vec![]), Some(CyberAccessProgram::DaybreakBlue))
        .unwrap();
}
