//! 仅修复旧版 App 的能力识别，不提供或替代上游账号授权。

use crate::ModelProviderInfo;
use crate::OPENAI_PROVIDER_ID;
use codex_protocol::error::CodexErr;
use codex_protocol::error::Result;
use codex_protocol::openai_models::ModelAccessPrograms;
use codex_protocol::openai_models::ModelInfo;
use codex_protocol::openai_models::ModelPreset;
use codex_protocol::turn_input::CyberAccessProgram;

const MARKER: &str = "gpt-daybreak-red-latest";

impl ModelProviderInfo {
    /// 从真实目录生成一个仅用于 App 协议的标记，调用者不得将其写回模型目录。
    pub fn daybreak_app_compat_marker(
        &self,
        provider_id: &str,
        presets: &[ModelPreset],
        is_chatgpt_auth: bool,
    ) -> Option<ModelPreset> {
        if !self.experimental_daybreak_app_compat
            || provider_id != OPENAI_PROVIDER_ID
            || !self.requires_openai_auth
            || !is_chatgpt_auth
            || presets.iter().any(|model| {
                model.model == MARKER
                    || model
                        .available_access_programs
                        .as_ref()
                        .is_some_and(|programs| {
                            programs.cyber.contains(&CyberAccessProgram::DaybreakRed)
                        })
            })
        {
            return None;
        }
        let mut marker = presets
            .iter()
            .find(|model| {
                model
                    .available_access_programs
                    .as_ref()
                    .is_some_and(|programs| {
                        programs.cyber.contains(&CyberAccessProgram::DaybreakBlue)
                    })
            })?
            .clone();
        marker.id = MARKER.to_owned();
        marker.model = MARKER.to_owned();
        marker.display_name = "Daybreak UI 兼容标记（不可用于推理）".to_owned();
        marker.description = "仅供旧版 App 识别已有的 Blue 能力，请选择普通模型。".to_owned();
        marker.show_in_picker = true;
        marker.is_default = false;
        marker.upgrade = None;
        marker.availability_nux = None;
        marker.available_access_programs = Some(ModelAccessPrograms {
            cyber: vec![CyberAccessProgram::DaybreakBlue],
        });
        Some(marker)
    }

    /// 根据真实模型元数据校验选择；HTTP、WebSocket 和会话初始化共用此逻辑。
    pub fn validate_daybreak_app_compat(
        &self,
        model: &ModelInfo,
        program: Option<CyberAccessProgram>,
    ) -> Result<()> {
        if !self.experimental_daybreak_app_compat {
            return Ok(());
        }
        let supports = |program| {
            model
                .available_access_programs
                .as_ref()
                .is_some_and(|programs| programs.cyber.contains(&program))
        };
        if model.slug == MARKER && !supports(CyberAccessProgram::DaybreakRed) {
            return Err(CodexErr::InvalidRequest(
                "Daybreak UI 兼容标记不能用于推理；请选择真实模型并使用 Daybreak 开关。".to_owned(),
            ));
        }
        if let Some(program @ (CyberAccessProgram::DaybreakBlue | CyberAccessProgram::DaybreakRed)) =
            program
            && !supports(program)
        {
            return Err(CodexErr::InvalidRequest(format!(
                "真实模型目录未声明模型 `{}` 支持 {program:?}；请关闭 Daybreak 或选择支持的模型。",
                model.slug,
            )));
        }
        Ok(())
    }
}

#[cfg(test)]
#[path = "daybreak_app_compat_tests.rs"]
mod tests;
