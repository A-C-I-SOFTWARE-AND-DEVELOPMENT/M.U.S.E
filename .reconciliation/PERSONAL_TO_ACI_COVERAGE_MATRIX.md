# Personal-to-ACI Coverage Matrix

**Source:** echerd27-design/hermes-agent @ personal/main

**Target:** A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent @ origin/main

Personal-only files (A status in `git diff origin/main..personal/main`): **513**.
Ported on this branch: **61**.  Deferred: **452**.

Personal/ACI also share **726 files with divergent contents (M)** and ACI has **994 files personal lacks (D)** — those are documented in the deep-dive report, not in this per-file matrix.

| Personal file | ACI equivalent | Status | Decision | Reason |
|---|---|---|---|---|
| `.github/workflows/docker-lint.yml` | none | MISSING_DEFER | defer | CI workflow changes affect every PR; review with launch policy first. |
| `.github/workflows/skills-index-freshness.yml` | none | MISSING_DEFER | defer | CI workflow changes affect every PR; review with launch policy first. |
| `.hadolint.yaml` | none | MISSING_PORT | port exact | Lint config; inert without hadolint runner. |
| `agent/credential_persistence.py` | none | MISSING_PORT | port exact | Leaf agent module. |
| `agent/secret_sources/__init__.py` | none | MISSING_PORT | port exact | Leaf agent module. |
| `agent/secret_sources/bitwarden.py` | none | MISSING_PORT | port exact | Leaf agent module. |
| `agent/transcription_provider.py` | none | MISSING_PORT | port exact | Leaf agent module. |
| `agent/transcription_registry.py` | none | MISSING_PORT | port exact | Leaf agent module. |
| `agent/tts_provider.py` | none | MISSING_PORT | port exact | Leaf agent module. |
| `agent/tts_registry.py` | none | MISSING_PORT | port exact | Leaf agent module. |
| `docker/cont-init.d/015-supervise-perms` | none | MISSING_DEFER | defer | s6-overlay supervision touches Dockerfile + boot; needs paired docker/ + Dockerfile + workflows pass. |
| `docker/cont-init.d/02-reconcile-profiles` | none | MISSING_DEFER | defer | s6-overlay supervision touches Dockerfile + boot; needs paired docker/ + Dockerfile + workflows pass. |
| `docker/main-wrapper.sh` | none | MISSING_DEFER | defer | s6-overlay supervision touches Dockerfile + boot; needs paired docker/ + Dockerfile + workflows pass. |
| `docker/s6-rc.d/dashboard/finish` | none | MISSING_DEFER | defer | s6-overlay supervision touches Dockerfile + boot; needs paired docker/ + Dockerfile + workflows pass. |
| `docker/s6-rc.d/dashboard/run` | none | MISSING_DEFER | defer | s6-overlay supervision touches Dockerfile + boot; needs paired docker/ + Dockerfile + workflows pass. |
| `docker/s6-rc.d/dashboard/type` | none | MISSING_DEFER | defer | s6-overlay supervision touches Dockerfile + boot; needs paired docker/ + Dockerfile + workflows pass. |
| `docker/s6-rc.d/main-hermes/run` | none | MISSING_DEFER | defer | s6-overlay supervision touches Dockerfile + boot; needs paired docker/ + Dockerfile + workflows pass. |
| `docker/s6-rc.d/main-hermes/type` | none | MISSING_DEFER | defer | s6-overlay supervision touches Dockerfile + boot; needs paired docker/ + Dockerfile + workflows pass. |
| `docker/s6-rc.d/user/contents.d/dashboard` | none | MISSING_DEFER | defer | s6-overlay supervision touches Dockerfile + boot; needs paired docker/ + Dockerfile + workflows pass. |
| `docker/s6-rc.d/user/contents.d/main-hermes` | none | MISSING_DEFER | defer | s6-overlay supervision touches Dockerfile + boot; needs paired docker/ + Dockerfile + workflows pass. |
| `docker/stage2-hook.sh` | none | MISSING_DEFER | defer | s6-overlay supervision touches Dockerfile + boot; needs paired docker/ + Dockerfile + workflows pass. |
| `docs/plans/2026-05-07-s6-overlay-dynamic-subagent-gateways.md` | none | MISSING_PORT | port exact | Doc-only file. |
| `hermes_cli/container_boot.py` | none | MISSING_PORT | port exact | CLI module backing an existing subcommand surface. |
| `hermes_cli/fallback_config.py` | none | MISSING_PORT | port exact | CLI module backing an existing subcommand surface. |
| `hermes_cli/mcp_catalog.py` | none | MISSING_PORT | port exact | CLI module backing an existing subcommand surface. |
| `hermes_cli/mcp_picker.py` | none | MISSING_PORT | port exact | CLI module backing an existing subcommand surface. |
| `hermes_cli/migrate.py` | none | MISSING_PORT | port exact | CLI module backing an existing subcommand surface. |
| `hermes_cli/portal_cli.py` | none | MISSING_PORT | port exact | CLI module backing an existing subcommand surface. |
| `hermes_cli/secret_prompt.py` | none | MISSING_PORT | port exact | CLI module backing an existing subcommand surface. |
| `hermes_cli/secrets_cli.py` | none | MISSING_PORT | port exact | CLI module backing an existing subcommand surface. |
| `hermes_cli/security_audit.py` | none | MISSING_PORT | port exact | CLI module backing an existing subcommand surface. |
| `hermes_cli/service_manager.py` | none | MISSING_PORT | port exact | CLI module backing an existing subcommand surface. |
| `hermes_cli/xai_retirement.py` | none | MISSING_PORT | port exact | CLI module backing an existing subcommand surface. |
| `infographic/kanban-db-corruption-defense/infographic.png` | none | MISSING_DEFER | defer | Large binary; low priority. |
| `optional-mcps/linear/manifest.yaml` | none | MISSING_PORT | port exact | Manifest only; no runtime side effects. |
| `optional-mcps/n8n/manifest.yaml` | none | MISSING_PORT | port exact | Manifest only; no runtime side effects. |
| `optional-skills/autonomous-ai-agents/openhands/SKILL.md` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/security/web-pentest/SKILL.md` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/security/web-pentest/references/bypass-techniques.md` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/security/web-pentest/references/exploitation-techniques.md` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/security/web-pentest/references/scope-enforcement.md` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/security/web-pentest/references/vuln-taxonomy.md` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/security/web-pentest/scripts/recon-scan.sh` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/security/web-pentest/templates/authorization.md` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/security/web-pentest/templates/exploitation-queue.json` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/security/web-pentest/templates/pentest-report.md` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/software-development/code-wiki/SKILL.md` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/software-development/code-wiki/templates/README.md` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/software-development/code-wiki/templates/architecture.md` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/software-development/code-wiki/templates/getting-started.md` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `optional-skills/software-development/code-wiki/templates/module.md` | none | MISSING_PORT | port exact | Opt-in skill bundle; no runtime side effects. |
| `plugins/image_gen/fal/__init__.py` | none | MISSING_PORT | port exact | Plugin scaffold; opt-in loader. |
| `plugins/image_gen/fal/plugin.yaml` | none | MISSING_PORT | port exact | Plugin scaffold; opt-in loader. |
| `plugins/platforms/discord/__init__.py` | none | MISSING_PORT | port exact | Plugin scaffold; opt-in loader. |
| `plugins/platforms/discord/plugin.yaml` | none | MISSING_PORT | port exact | Plugin scaffold; opt-in loader. |
| `plugins/platforms/mattermost/__init__.py` | none | MISSING_PORT | port exact | Plugin scaffold; opt-in loader. |
| `plugins/platforms/mattermost/plugin.yaml` | none | MISSING_PORT | port exact | Plugin scaffold; opt-in loader. |
| `plugins/platforms/ntfy/__init__.py` | none | MISSING_PORT | port exact | Plugin scaffold; opt-in loader. |
| `plugins/platforms/ntfy/adapter.py` | none | MISSING_PORT | port exact | Plugin scaffold; opt-in loader. |
| `plugins/platforms/ntfy/plugin.yaml` | none | MISSING_PORT | port exact | Plugin scaffold; opt-in loader. |
| `plugins/web/xai/__init__.py` | none | MISSING_PORT | port exact | Plugin scaffold; opt-in loader. |
| `plugins/web/xai/plugin.yaml` | none | MISSING_PORT | port exact | Plugin scaffold; opt-in loader. |
| `plugins/web/xai/provider.py` | none | MISSING_PORT | port exact | Plugin scaffold; opt-in loader. |
| `scripts/run_tests_parallel.py` | none | MISSING_PORT | port exact | Devops helper. |
| `skills/software-development/hermes-s6-container-supervision/SKILL.md` | none | MISSING_PORT | port exact | Markdown playbook only. |
| `tests/agent/lsp/test_shell_linter_lsp_skip.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_anthropic_mcp_prefix_strip.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_codex_ttfb_watchdog.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_custom_provider_extra_body.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_display_todo_progress.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_display_tool_failure.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_file_safety.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_file_safety_credentials.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_file_safety_cross_profile.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_last_total_tokens.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_non_stream_stale_timeout.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_nous_oauth_401_guidance.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_save_url_image.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_tool_dispatch_helpers.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/agent/test_transcription_registry.py` | none | MISSING_PORT | port exact | Test for module already ported. |
| `tests/agent/test_tts_registry.py` | none | MISSING_PORT | port exact | Test for module already ported. |
| `tests/agent/test_vision_routing_31179.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/cli/test_bracketed_paste_timeout.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/cli/test_cli_resume_command.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/cli/test_destructive_slash_inline_skip_e2e.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/cli/test_exit_summary_resume_hint.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/cli/test_resume_quiet_stderr.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/cli/test_slash_command_interrupt.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/cli/test_slash_confirm_windows.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/cron/test_cronjob_schema.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/docker/__init__.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/docker/conftest.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/docker/test_container_restart.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/docker/test_dashboard.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/docker/test_main_invocation.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/docker/test_profile_gateway.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/docker/test_s6_profile_gateway_integration.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/docker/test_tui_passthrough.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/docker/test_zombie_reaping.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/gateway/platforms/__init__.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/gateway/platforms/test_yuanbao_recall_db_only.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/gateway/test_compression_session_id_persistence.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/gateway/test_load_transcript_db_only.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/gateway/test_loop_exception_handler.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/gateway/test_mcp_reload_refreshes_cached_agents.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/gateway/test_model_command_flat_string_config.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/gateway/test_ntfy_plugin.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/gateway/test_runtime_config_env_expansion.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/gateway/test_subagent_protection_30170.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/gateway/test_telegram_send_path_health.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/gateway/test_telegram_status_update.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_auth_usable_secret.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_cli_output.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_container_boot.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_curses_color_compat.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_gateway_s6_dispatch.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_kanban_promote.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_mcp_catalog.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_migrate_xai.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_nous_inference_url_validation.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_plugin_auxiliary_tasks.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_plugins_transcription_registration.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_plugins_tts_registration.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_profiles_s6_hooks.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_project_plugin_rce_bypass.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_secret_prompt.py` | none | MISSING_PORT | port exact | Test for module already ported. |
| `tests/hermes_cli/test_security_audit.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_service_manager.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_tts_picker.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_update_zip_symlink_reject.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_web_server_oauth_write.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_xai_provider_labels.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/hermes_cli/test_xai_retirement.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/plugins/image_gen/check_parity_vs_main.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/plugins/image_gen/test_fal_provider.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/plugins/model_providers/test_opencode_go_profile.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/plugins/transcription/__init__.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/plugins/transcription/check_parity_vs_main.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/plugins/tts/__init__.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/plugins/tts/check_parity_vs_main.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/run_agent/test_31273_402_not_retried.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/run_agent/test_codex_silent_hang_hint.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/run_agent/test_credential_pool_interrupt.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/run_agent/test_multimodal_tool_content_recovery.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/run_agent/test_partial_stream_finish_reason.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/run_agent/test_tls_fd_recycle_corruption.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/test_bitwarden_secrets.py` | none | MISSING_PORT | port exact | Test for module already ported. |
| `tests/test_env_loader_secret_sources.py` | none | MISSING_PORT | port exact | Test for module already ported. |
| `tests/test_run_tests_parallel.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/conftest.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/test_computer_use_capture_routing.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/test_computer_use_vision_routing.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/test_cross_profile_guard.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/test_line_ending_preservation.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/test_patch_failure_tracking.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/test_pr_6656_regressions.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/test_skills_ast_audit.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/test_threat_patterns.py` | none | MISSING_PORT | port exact | Test for module already ported. |
| `tests/tools/test_transcription_command_providers.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/test_transcription_plugin_dispatch.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/test_tts_path_traversal.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/test_tts_plugin_dispatch.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/test_tts_xai_speech_tags.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tests/tools/test_web_providers_xai.py` | none | MISSING_DEFER | defer | Target code not yet ported; bundle in follow-up PR. |
| `tools/computer_use/vision_routing.py` | none | MISSING_PORT | port exact | Tool helper module. |
| `tools/fal_common.py` | none | MISSING_PORT | port exact | Tool helper module. |
| `tools/skills_ast_audit.py` | none | MISSING_PORT | port exact | Tool helper module. |
| `tools/threat_patterns.py` | none | MISSING_PORT | port exact | Tool helper module. |
| `ui-tui/packages/hermes-ink/src/ink/app-mouse.test.ts` | none | MISSING_DEFER | defer | TypeScript test files; need parent ui-tui source ported. |
| `ui-tui/packages/hermes-ink/src/utils/execFileNoThrow.test.ts` | none | MISSING_DEFER | defer | TypeScript test files; need parent ui-tui source ported. |
| `ui-tui/src/__tests__/messageLine.test.ts` | none | MISSING_DEFER | defer | TypeScript test files; need parent ui-tui source ported. |
| `ui-tui/src/__tests__/statusRule.test.ts` | none | MISSING_DEFER | defer | TypeScript test files; need parent ui-tui source ported. |
| `ui-tui/src/__tests__/termuxComposerLayout.test.ts` | none | MISSING_DEFER | defer | TypeScript test files; need parent ui-tui source ported. |
| `ui-tui/src/__tests__/textInputBurstInput.test.ts` | none | MISSING_DEFER | defer | TypeScript test files; need parent ui-tui source ported. |
| `website/docs/guides/run-hermes-with-nous-portal.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/docs/integrations/nous-portal.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/docs/user-guide/messaging/ntfy.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/docs/user-guide/secrets/bitwarden.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/docs/user-guide/secrets/index.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/docs/user-guide/skills/optional/autonomous-ai-agents/autonomous-ai-agents-openhands.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/docs/user-guide/skills/optional/software-development/software-development-code-wiki.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/acp-internals.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/adding-platform-adapters.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/adding-providers.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/adding-tools.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/agent-loop.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/architecture.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/browser-supervisor.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/context-compression-and-caching.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/context-engine-plugin.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/contributing.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/creating-skills.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/cron-internals.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/extending-the-cli.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/gateway-internals.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/image-gen-provider-plugin.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/memory-provider-plugin.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/model-provider-plugin.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/plugin-llm-access.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/programmatic-integration.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/prompt-assembly.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/provider-runtime.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/session-storage.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/tools-runtime.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/trajectory-format.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/video-gen-provider-plugin.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/developer-guide/web-search-provider-plugin.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/getting-started/installation.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/getting-started/learning-path.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/getting-started/nix-setup.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/getting-started/quickstart.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/getting-started/termux.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/getting-started/updating.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/automate-with-cron.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/automation-templates.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/aws-bedrock.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/azure-foundry.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/build-a-hermes-plugin.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/cron-script-only.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/cron-troubleshooting.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/daily-briefing-bot.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/delegation-patterns.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/github-pr-review-agent.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/google-gemini.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/local-llm-on-mac.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/local-ollama-setup.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/microsoft-graph-app-registration.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/migrate-from-openclaw.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/minimax-oauth.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/oauth-over-ssh.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/operate-teams-meeting-pipeline.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/pipe-script-output.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/python-library.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/run-hermes-with-nous-portal.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/team-telegram-assistant.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/tips.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/use-mcp-with-hermes.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/use-soul-with-hermes.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/use-voice-mode-with-hermes.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/webhook-github-pr-review.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/work-with-skills.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/xai-grok-oauth.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/index.mdx` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/integrations/index.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/integrations/nous-portal.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/integrations/providers.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/reference/cli-commands.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/reference/environment-variables.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/reference/faq.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/reference/mcp-config-reference.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/reference/model-catalog.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/reference/optional-skills-catalog.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/reference/profile-commands.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/reference/skills-catalog.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/reference/slash-commands.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/reference/tools-reference.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/reference/toolsets-reference.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/checkpoints-and-rollback.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/cli.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/configuration.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/configuring-models.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/docker.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/acp.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/api-server.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/batch-processing.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/browser.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/built-in-plugins.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/code-execution.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/codex-app-server-runtime.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/computer-use.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/context-files.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/context-references.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/credential-pools.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/cron.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/curator.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/delegation.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/deliverable-mode.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/extending-the-dashboard.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/fallback-providers.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/goals.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/honcho.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/hooks.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/kanban-tutorial.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/kanban-worker-lanes.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/kanban.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/lsp.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/mcp.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/memory-providers.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/memory.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/overview.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/personality.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/plugins.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/provider-routing.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/skills.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/skins.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/spotify.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/subscription-proxy.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/tools.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/tts.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/vision.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/voice-mode.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/web-dashboard.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/web-search.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/features/x-search.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/git-worktrees.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/bluebubbles.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/dingtalk.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/discord.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/email.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/feishu.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/google_chat.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/homeassistant.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/index.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/line.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/matrix.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/mattermost.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/msgraph-webhook.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/ntfy.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/open-webui.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/qqbot.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/signal.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/simplex.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/slack.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/sms.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/teams-meetings.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/teams.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/telegram.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/webhooks.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/wecom-callback.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/wecom.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/weixin.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/whatsapp.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/messaging/yuanbao.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/profile-distributions.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/profiles.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/secrets/bitwarden.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/secrets/index.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/security.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/sessions.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/apple/apple-apple-notes.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/apple/apple-apple-reminders.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/apple/apple-findmy.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/apple/apple-imessage.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/apple/apple-macos-computer-use.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-claude-code.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-codex.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-hermes-agent.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-opencode.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-architecture-diagram.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-ascii-art.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-ascii-video.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-baoyu-article-illustrator.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-baoyu-comic.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-baoyu-infographic.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-claude-design.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-comfyui.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-creative-ideation.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-design-md.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-excalidraw.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-humanizer.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-manim-video.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-p5js.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-pixel-art.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-popular-web-designs.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-pretext.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-sketch.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-songwriting-and-ai-music.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/creative/creative-touchdesigner-mcp.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/data-science/data-science-jupyter-live-kernel.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/devops/devops-kanban-orchestrator.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/devops/devops-kanban-worker.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/devops/devops-webhook-subscriptions.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/dogfood/dogfood-dogfood.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/email/email-himalaya.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/gaming/gaming-minecraft-modpack-server.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/gaming/gaming-pokemon-player.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/github/github-codebase-inspection.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/github/github-github-auth.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/github/github-github-code-review.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/github/github-github-issues.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/github/github-github-pr-workflow.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/github/github-github-repo-management.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/mcp/mcp-native-mcp.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/media/media-gif-search.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/media/media-heartmula.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/media/media-songsee.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/media/media-spotify.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/media/media-youtube-content.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/mlops/mlops-evaluation-lm-evaluation-harness.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/mlops/mlops-evaluation-weights-and-biases.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/mlops/mlops-huggingface-hub.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/mlops/mlops-inference-llama-cpp.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/mlops/mlops-inference-obliteratus.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/mlops/mlops-inference-vllm.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/mlops/mlops-models-audiocraft.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/mlops/mlops-models-segment-anything.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/mlops/mlops-research-dspy.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/note-taking/note-taking-obsidian.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/productivity/productivity-airtable.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/productivity/productivity-google-workspace.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/productivity/productivity-linear.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/productivity/productivity-maps.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/productivity/productivity-nano-pdf.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/productivity/productivity-notion.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/productivity/productivity-ocr-and-documents.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/productivity/productivity-powerpoint.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/productivity/productivity-teams-meeting-pipeline.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/red-teaming/red-teaming-godmode.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/research/research-arxiv.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/research/research-blogwatcher.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/research/research-llm-wiki.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/research/research-polymarket.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/research/research-research-paper-writing.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/smart-home/smart-home-openhue.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/social-media/social-media-xurl.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/software-development/software-development-debugging-hermes-tui-commands.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/software-development/software-development-hermes-agent-skill-authoring.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/software-development/software-development-node-inspect-debugger.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/software-development/software-development-plan.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/software-development/software-development-python-debugpy.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/software-development/software-development-requesting-code-review.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/software-development/software-development-spike.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/software-development/software-development-subagent-driven-development.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/software-development/software-development-systematic-debugging.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/software-development/software-development-test-driven-development.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/software-development/software-development-writing-plans.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/bundled/yuanbao/yuanbao-yuanbao.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/godmode.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/google-workspace.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/autonomous-ai-agents/autonomous-ai-agents-blackbox.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/autonomous-ai-agents/autonomous-ai-agents-honcho.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/blockchain/blockchain-evm.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/blockchain/blockchain-hyperliquid.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/blockchain/blockchain-solana.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/communication/communication-one-three-one-rule.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/creative/creative-blender-mcp.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/creative/creative-concept-diagrams.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/creative/creative-hyperframes.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/creative/creative-kanban-video-orchestrator.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/creative/creative-meme-generation.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/devops/devops-cli.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/devops/devops-docker-management.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/devops/devops-pinggy-tunnel.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/devops/devops-watchers.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/dogfood/dogfood-adversarial-ux-test.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/email/email-agentmail.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/finance/finance-3-statement-model.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/finance/finance-comps-analysis.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/finance/finance-dcf-model.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/finance/finance-excel-author.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/finance/finance-lbo-model.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/finance/finance-merger-model.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/finance/finance-pptx-author.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/finance/finance-stocks.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/health/health-fitness-nutrition.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/health/health-neuroskill-bci.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mcp/mcp-fastmcp.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mcp/mcp-mcporter.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/migration/migration-openclaw-migration.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-accelerate.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-chroma.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-clip.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-faiss.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-flash-attention.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-guidance.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-huggingface-tokenizers.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-inference-outlines.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-instructor.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-lambda-labs.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-llava.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-modal.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-nemo-curator.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-peft.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-pinecone.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-pytorch-fsdp.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-pytorch-lightning.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-qdrant.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-saelens.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-simpo.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-slime.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-stable-diffusion.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-tensorrt-llm.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-torchtitan.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-training-axolotl.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-training-trl-fine-tuning.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-training-unsloth.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/mlops/mlops-whisper.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/productivity/productivity-canvas.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/productivity/productivity-here-now.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/productivity/productivity-memento-flashcards.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/productivity/productivity-shop-app.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/productivity/productivity-shopify.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/productivity/productivity-siyuan.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/productivity/productivity-telephony.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/research/research-bioinformatics.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/research/research-darwinian-evolver.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/research/research-domain-intel.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/research/research-drug-discovery.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/research/research-duckduckgo-search.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/research/research-gitnexus-explorer.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/research/research-osint-investigation.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/research/research-parallel-cli.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/research/research-qmd.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/research/research-scrapling.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/research/research-searxng-search.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/security/security-1password.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/security/security-oss-forensics.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/security/security-sherlock.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/software-development/software-development-rest-graphql-debug.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/skills/optional/web-development/web-development-page-agent.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/tui.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-guide/windows-native.md` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
| `website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/user-stories.mdx` | none | MISSING_DEFER | defer | ACI website has its own architecture; targeted website pass needed. |
