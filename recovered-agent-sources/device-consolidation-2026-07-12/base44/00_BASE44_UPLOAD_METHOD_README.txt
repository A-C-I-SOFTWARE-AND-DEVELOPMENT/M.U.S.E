BASE44 CONTEXT UPLOAD METHOD FOR HERMES / JARVIS

Problem:
Base44 is rejecting full source ZIPs because of file type and/or size limits. Do not try to upload the 33MB Hermes ZIP directly.

Best method:
1. Keep the full Hermes source in GitHub/local ZIP as the source of truth.
2. Give Base44 only a compact context pack in pasted text chunks.
3. Ask Base44 to build the Base44 cockpit, not to ingest or replace the whole Hermes backend.
4. Use GitHub links or local repo references for full source. Base44 receives summaries, schemas, entity definitions, pages, API contracts, and task packets.

Upload/paste order:
- Paste 01_MASTER_BUILD_PROMPT first.
- Paste 02_SYSTEM_ARCHITECTURE second.
- Paste 03_ENTITY_SCHEMA third.
- Paste 04_UI_AND_PAGES fourth.
- Paste 05_ANDROID_AVATAR_ACTIONS fifth.
- Paste 06_MEMORY_TREE_AND_SELF_EFFICIENT_CODER sixth.
- Paste 07_IMPLEMENTATION_TASKS seventh.

Rule:
Do not ask Base44 to import Hermes as a zip. Ask it to generate a small Vite/React/Base44 app that talks to Hermes through future local API endpoints or manually imported job/memory data during testing.
