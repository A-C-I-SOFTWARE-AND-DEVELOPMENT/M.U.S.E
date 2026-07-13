# Recovered Static Product Surfaces

These static assets were recovered from the most complete pre-consolidation M.U.S.E workspace. They provide functional Atlas, Observatory, Studio, legacy cockpit, PWA, and vendor-backed fallback surfaces while the unified Desktop/Omni implementation evolves.

`scripts/deploy/prepare_unified_dashboard.mjs` rebuilds source-owned MuseHQ and NEXUS bundles, then stages these static surfaces. Generated `musehq/` and `nexus/` bundle directories are intentionally not stored here; build them from their source packages.

The single-file `atlas/muse-atlas.html` and modular `atlas/index.html` implementations are retained as visual/interaction references. New Atlas Crown work should migrate useful behavior into `apps/desktop/ui/src/omni/` and the shared universe contracts rather than growing another disconnected production UI.

