# Full-suite baseline on pristine upstream

Repo: NousResearch/hermes-agent @ `2d92793045` (v0.20.4), 2026-08-20
Command: `HERMES_HOME=~/.hermes-port bash scripts/run_tests.sh`
Result: **exit 1 — 40 test files fail on untouched upstream.**

**This list is a LOWER BOUND, not the complete set.** It was captured through
`tail -40`, which truncated the run's output.
`tests/plugins/video_gen/test_fal_plugin.py` is known to fail on pristine
upstream (8 failed, 36 passed) and is absent from this list, which proves the
truncation. Do not treat absence from this list as evidence a test passes
upstream.

**Use the control worktree instead.** `C:\Users\Echer\refs\baseline` is pinned to
pristine upstream `2d92793045`. When a test fails during a tranche, run that same
test there:

    cd C:\Users\Echer\refs\baseline
    HERMES_HOME=~/.hermes-port uv run python -m pytest <failing test> -o addopts="" -q

The same failure there means it is upstream's, not ours. This is decisive per
case and costs seconds, where a full re-run costs hours.

Never compare to zero: upstream is not green here, and a gate demanding zero
would be permanently red and therefore ignored.

Recorded before any fork material was ported, so every one of these is
upstream's, not ours.

```
tests/acp/test_entry.py
tests/acp/test_mcp_e2e.py
tests/acp/test_named_provider_catalogs.py
tests/acp/test_ping_suppression.py
tests/acp/test_tools.py
tests/acp_adapter/test_acp_commands.py
tests/acp_adapter/test_acp_images.py
tests/acp_adapter/test_acp_mcp_discovery.py
tests/gateway/test_api_server.py
tests/gateway/test_api_server_active_work_drain.py
tests/gateway/test_api_server_jobs.py
tests/gateway/test_api_server_multimodal.py
tests/gateway/test_api_server_runs.py
tests/gateway/test_cron_fire_webhook.py
tests/gateway/test_kanban_wake_scope.py
tests/gateway/test_media_download_retry.py
tests/gateway/test_raft_adapter.py
tests/gateway/test_send_image_file.py
tests/gateway/test_send_multiple_images.py
tests/gateway/test_session_api.py
tests/gateway/test_slack_approval_buttons.py
tests/gateway/test_slack_block_kit.py
tests/gateway/test_slack_block_kit_adapter.py
tests/gateway/test_slack_channel_session_scope.py
tests/gateway/test_slack_clarify_buttons.py
tests/gateway/test_slack_cron_continuable_surface.py
tests/gateway/test_slack_dedup_ttl.py
tests/gateway/test_slack_group_dm_scope_warning.py
tests/gateway/test_slack_ignore_other_user_mentions.py
tests/gateway/test_slack_log_noise.py
tests/gateway/test_slack_mention.py
tests/gateway/test_slack_native_streaming.py
tests/gateway/test_slack_plugin_setup.py
tests/gateway/test_slack_require_mention_channels.py
tests/gateway/test_slack_sdk_response.py
tests/gateway/test_slack_send_retry.py
tests/gateway/test_slack_user_token_warning.py
tests/hermes_cli/test_doctor_journal_modes.py
tests/tools/test_browser_npx_warmup.py
tests/verify/test_environment_and_runner.py
```
