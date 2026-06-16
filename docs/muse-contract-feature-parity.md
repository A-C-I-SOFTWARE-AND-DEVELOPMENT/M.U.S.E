# MUSE Contract — feature parity ledger

Tracks **every capability** named in the uploaded contract against its concrete
implementation in this repo. "Done" for the *wire-and-build* goal = every row is
`EXISTS` (already real), `BUILT` (added here), or `OWNER-GATED` (a deliberate,
documented deferral the owner must green-light). No row may sit at `STUB`.

The behavioral layer (SC1…SC12) lives in
[`docs/muse-system-contract.md`](muse-system-contract.md); this ledger covers the
**capability/tool** surface. The tool seam is `tools/registry.py`
(`registry.register` / plugin `register(ctx)`); free-API plugins follow the
[`plugins/weather/`](../plugins/weather) template (host-pinned
`tools.http_client.PublicApiClient`, config-gated, mocked tests).

| # | Contract capability | Status | Implementation |
|---|---|---|---|
| 1 | web search | EXISTS | `tools/web_tools.py` `web_search` (Exa/Tavily/Brave/DDG/SearXNG…) |
| 2 | web/URL fetch | EXISTS | `tools/web_tools.py` `web_extract` |
| 3 | image search | BUILT | `plugins/image_search/` (Openverse, free, CC-licensed) |
| 4 | weather | EXISTS | `plugins/weather/` (Open-Meteo, free) |
| 5 | sports scores/standings | PLANNED | `plugins/sports/` (ESPN public JSON, free) |
| 6 | places / maps | BUILT | `plugins/places/` (OSM Nominatim search + map/itinerary URL builder) |
| 7 | recipe (structured) | PLANNED | `plugins/recipe/` (auxiliary LLM → validated schema) |
| 8 | message composition | EXISTS | `tools/send_message_tool.py` `send_message` |
| 9 | file create/edit/view/run/share | EXISTS | `tools/file_tools.py` (`read_file`/`write_file`/`patch`/`search_files`) + `execute_code` |
| 10 | interactive prompts / options | EXISTS | `tools/clarify_tool.py` `clarify` |
| 11 | recommend apps/surfaces | PLANNED | tool wrapper over `gateway/cockpit/observatory_recommend.py` |
| 12 | MCP connector discovery / suggest | EXISTS | `hermes_cli/mcp_catalog.py`, `hermes_cli/mcp_picker.py`, `tools/mcp_tool.py` |
| 13 | skills system (SKILL.md) | EXISTS | `tools/skills_tool.py` + `skills/` |
| 14 | memory (durable/session) | EXISTS | `tools/memory_tool.py` (MEMORY.md + USER.md) |
| 15 | citations / source attribution | EXISTS | source URLs preserved in `web_search`/`web_extract` JSON (model cites from them) |
| 16 | artifact persistent KV storage | OWNER-GATED | web/cockpit artifact-runtime feature (`window.storage` bridge); architecturally significant — deferred, see note |
| 17 | model-API-from-artifacts | OWNER-GATED | artifact→backend token vending + origin validation; security-sensitive — deferred, see note |

## Owner-gated deferrals (16, 17)

Rows 16–17 are **web artifact-runtime** features, not agent tools: they require a
persistent key-value bridge and a backend token-vending endpoint injected into
sandboxed artifact iframes in the cockpit/web surface, with origin validation and
token-scope controls. Building them changes the cockpit's security surface, so
they are deferred as **owner-gated** until explicitly scoped — half-building a
token bridge would be the kind of insecure shortcut the contract (SC8) forbids.

## Build order

Free-API / no-key first (real, graceful when offline): **places → image_search →
sports → recipe → recommend-surfaces**. Each ships config + host-pinned client +
schema/handlers + mocked tests, opt-in via `<name>.enabled` in
`~/.hermes/config.yaml`, registered under its own toolset.
