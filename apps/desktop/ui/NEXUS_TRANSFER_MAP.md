# NEXUS -> Desktop UI Transfer Map

Source: C:\Users\Echer\OneDrive\Desktop\projects\M.U.S.E\apps\nexus  (the "NEXUS Console" PWA)
Target: C:\Users\Echer\M.U.S.E\apps\desktop\ui                (the Tauri v2 desktop client)

Purpose. A concise feature / page / component / API map for integrating the
NEXUS frontend into the current desktop UI. No edits were made to either tree.

Policies respected (per task constraints):
  - No iframe, no mock data, no Google/OpenRouter/Anthropic/local paths inside Fusion.
  - Preserve the Singularity / sacred-geometry identity (void + white core + single
    spectral ring — already established in the desktop scaffold).
  - Honest empty states: never fabricate telemetry when the gateway is unset.

---------------------------------------------------------------------------
1. ARCHITECTURAL CONTRAST (what differs, must be reconciled)
---------------------------------------------------------------------------

                        NEXUS (nexus)                 Desktop (ui)
  React                  18.3                         19.1
  Router                 react-router-dom v6          custom "append-only registry"
                         (Routes/Route/Navigate)       (routes.ts + registerRoute)
  State                  zustand (useNexusStore)      local useState per view
  Animations             framer-motion                CSS + ReducedMotion-aware CSS
  Styles                 Tailwind v3 + CSS modules     CSS design tokens (no TW)
  Gateway transport      cockpit.ts adapter           lib/gateway.ts (same protocol)
  Direct provider        OpenRouter/Anthropic (SKIP)  gateway-only (no direct)
  Native bridge          none (PWA)                   Tauri v2 commands (brain.rs

  KEY RECONCILIATION:
  - NEXUS uses react-router; the desktop uses a registry. Every NEXUS page becomes
    a `registerRoute(...)` call (see views/register.ts model) — NOT a <Route>.
  - NEXUS's direct-provider paths (OpenRouter/Anthropic/Google) must NOT be ported.
    The desktop UI talks ONLY to the local gateway (http://127.0.0.1:8765).
  - The NEXUS zustand store is ported by extracting shared slices into lib/ modules
    and keeping view-local state where the desktop already does (see §5).
  - Tailwind classes in NEXUS components must be re-authored as plain CSS against
    the existing design tokens (--void, --core, --ring-1/2, --signal, etc.).

---------------------------------------------------------------------------
2. PAGE-BY-PAGE TRANSFER MAP
---------------------------------------------------------------------------

  NEXUS page                 Desktop view        Overlap / action
  --------------------------------------------------------------------------------
  ConsolePage (/)            Chat (/) &          MERGE: ConsolePage's capability
                             Home                 grid + status tiles port to Home
                                                  (it already has pairing/chat/
                                                  phase-rail). ConsolePage's
                                                  "agents + runtime status" is a
                                                  new Home sub-section.

  ChatPage                   Chat.tsx             SAME SLOT. Desktop Chat is
                                                  already NDJSON over the gateway;
                                                  NEXUS ChatPage is duplicate
                                                  — drop NEXUS copy, keep desktop.

  SteerPage (/steer)         (none)               NEW ROUTE. The sacred Octagon +
                                                  vertex sliders + telemetry is a
                                                  distinct feature. Register as
                                                  "Steer" (order ~35, between
                                                  Approvals and Autonomy).

  AxiomGatePage (/axiom)     (none)               NEW ROUTH (low priority — pure
                                                  client-side fusion/verification
                                              logic in lib/fusion.ts, no gateway
                                                  dep). Register as "Axiom".

  ObservatoryPage            Observatory.tsx      SAME SLOT. Desktop version is an
                                                  iframe to /cockpit/observatory.html
                                                  (per task: NO iframe -> must be
                                                  replaced by the native Octagon/
                                                  Galaxy rendering from
                                                  components/observatory + the
                                                  telemetry adapter data).

  FusionPage (/fusion)       (none)               NEW ROUTE BUT policy: NO
                                                  OpenRouter/Anthropic/Google
                                                  paths. Port ONLY the gateway-
                                                  transport leg + preset/strategy
                                                  UI; strip directProvider. See §4.

  ForgePage (/forge)         AgentWorkshop        LITE OVERLAP. Forge = persona/
                                                  knowledge-pack authoring
                                                  (IndexedDB). Desktop AgentWorkshop
                                                  = orchestrate+jobs. These are
                                                  complementary: register Forge as
                                                  its own route (order ~15) and keep
                                                  AgentWorkshop for jobs.

  FleetPage (/fleet)         Jobs.tsx             OVERLAP. Fleet also lists jobs
                                                  (cockpit adapter) with budget/
                                                  fanout logic. Merge Fleet's
                                                  budget+fanout into Jobs.tsx.

  ModelsPage (/models)       (none)               NEW ROUTE. Model catalog +
                                                  transport routing UI. Policy:
                                                  strip OpenRouter/Anthropic/
                                                  Gemini direct rows; keep only
                                                  the "via gateway" transport.

  SecondBrainPage            (none)               NEW ROUTE. BrainLadder + Galaxy
                                                  + StationPipeline visuals
                                                  (sacred-geometry identity).

  CouncilPage (/council)     (none)               NEW ROUTE. Council dispatch +
                                                  member roster.

  RepoPage (/repo)           (none)               NEW ROUTE. Repo mirror
                                                  inventory + FileBrowser + PullList.

  ChampionshipPage            (none)               NEW ROUTE (read-only leaderboard
                                                  from forgeArena over gateway).

  SharePage (/share)         (none)               NEW ROUTE (OS share-target
                                                  -> orchestrate). Desktop gets this
                                                  from native share via Tauri.

  ActivityPage                (none)               NEW ROUTE. activityStream feed.

  StudioPage                  (none)               STUB (returns null). Skip.

  AgentsPage                  AgentWorkshop        PARTIAL OVERLAP. Agents list by
                                                  surface -> merge into a new
                                                  "Agents" route or fold into
                                                  AgentWorkshop dashboard.

  SettingsPage                Settings.tsx         SAME SLOT. Desktop already has
                                                  gateway/brain/pairing/e-stop.
                                                  NEXUS Settings adds provider
                                                  credentials UI (SKIP — policy:
                                                  no third-party key storage).

  SignInPage                  (none via gateway)   SKIP. Desktop uses device
                                                  pairing (pair/start|confirm),
                                                  not Supabase auth. Do not port
                                                  OAuth/login forms.

---------------------------------------------------------------------------
3. REUSABLE COMPONENTS (NEXUS -> desktop registry)
---------------------------------------------------------------------------

  NEXUS component                         Desktop home / reuse
  ------------------------------------------------------------------------------------
  shell/SideNav, TopBar, TabBar,         -> consumed by App.tsx shell (header+nav).
    CommandPalette, CinematicBackdrop,      CommandPalette + SideNav are reusable
    StatusDot                               as-is (StatusDot already dot-styled).

  muse/CapabilityDrawer                   -> new: slide-out capability inventory
                                             (binds to lib/capabilities PLANES).

  octagon/Octagon, VertexSliders,        -> new "Steer" surface. Keep sacred-
    TelemetryPanel                          geometry styling.

  observatory/{BrainLadder,Galaxy,       -> new "SecondBrain" + replace the
    StationPipeline}                        Observatory iframe (no-iframe rule).

  fusion/{FusionGraph,RecommendPicker}   -> new "Fusion" route (gateway-transport
                                             leg only).

  axiom/FusionCore                       -> new "Axiom" route.

  repo/{FileBrowser,PullList,            -> new "Repo" route.
    RepoSyncCard}

  setup/{ConnectWizard,                  -> SKIP on desktop: desktop already has
    CredentialsManager,                     its own pairing flow (Settings.tsx).
    ProvidersManager,                       CredentialsManager/ProvidersManager/
    AddOnsManager,                          SecretField, ImportKeysCard all manage
    ImportKeysCard, SecretField}            third-party keys -> policy says no.

---------------------------------------------------------------------------
4. DATA / API DEPENDENCIES
---------------------------------------------------------------------------

  NEXUS lib module              Supplies                          Transfer?
  ------------------------------------------------------------------------------------
  adapters/cockpit.ts           /v1/cockpit/* (full surface)      KEEP — identical
                                                                   protocol to desktop
                                                                   lib/gateway.ts. Merge
                                                                   the two clients.

  adapters/observatory.ts       /v1/observatory/* snapshot+stream  KEEP — data source
                                                                   for native Observatory
                                                                   (replaces iframe).

  adapters/index.ts (surfaces)  muse/antigravity/aiStudio          KEEP museSurface
                                                                   only; antigravity &
                                                                   aiStudio are link-out
                                                                   only (no embedding).

  lib/fusion.ts, fusionTypes.ts Axiom Gate pure logic               KEEP (client-only).

  lib/fusionClient.ts           streamFusion via gateway           KEEP gateway leg.

  lib/directProvider.ts         OpenRouter/Anthropic/Google        DO NOT PORT.

  lib/providers.ts              configuredProviders (3rd-party)    DO NOT PORT.

  lib/chat.ts                   NDJSON chat client                  MERGE into
                                                                   lib/gateway.ts
                                                                   (desktop already has
                                                                   `chat()` there).

  lib/forge.ts                  forge/forgeArena types+logic       KEEP (gateway).

  lib/fleet.ts                  budget/fanout helpers               KEEP -> Jobs.

  lib/council.ts                council dispatch                    KEEP (gateway).

  lib/repoSync.ts               repo mirror fetcher                 KEEP.

  lib/activityStream.ts         activity feed                       KEEP (gateway).

  lib/steering.ts, weights,     Octagon math (weights, glow,        KEEP (pure).
    presets.ts, vertices.ts      inference)                         Port zustand slices.

  lib/capabilities.ts           capability registry/planes          KEEP (doc/catalog).

  lib/capabilityMatrix.json     task -> model ranking               DO NOT PORT
                                                                   (references third-
                                                                   party model ids).

  lib/modelCatalog.ts           model catalog                       STRIP third-party
                                                                   rows; keep gateway.

  lib/config.ts, securestore.ts encrypted config + AES-GCM           SKIP — desktop uses
                                                                   localStorage +
                                                                   Tauri native; no
                                                                   IndexedDB key vault.

  lib/supabase.ts               GoTrue auth                          DO NOT PORT.

  lib/health.ts, appUpdate.ts   health monitor + SW updater          PARTIAL — desktop has
                                                                   its own (pingHealth);
                                                                   SW/PWA updater skipped
                                                                   (native app).

---------------------------------------------------------------------------
5. STATE / STORE MIGRATION
---------------------------------------------------------------------------

  NEXUS zustand (useNexusStore.ts) slices:
    - vertices / preset / profiles / activeProfileId / emitVector
        -> port to a lib/steering-store module (or view-local state in Steer).
    - savedFusions / fusionHistory / fusionFavorites / saveFusion / addFusionRun
        -> lib/fusion-store module (gateway-transport only).
    - gateway config -> use desktop lib/gateway.ts (BASE_KEY/TOKEN_KEY) directly.

  Desktop currently holds everything in local useState per view. The suggested
  approach: extract the two Fusion/Steering slices into small, dependency-free
  lib/*-store.ts modules (localStorage-backed, identical shape), leaving views
  thin. No new global store needed.

---------------------------------------------------------------------------
6. RECOMMENDED ROUTE REGISTRY (after integration)
---------------------------------------------------------------------------

  order  id          label        source
  0       home        Home         scaffold (keep)
  10      chat        Chat         scaffold (keep)
  15      forge       Forge        NEW (nexus ForgePage)
  20      jobs        Jobs         scaffold (enrich w/ fleet budget/fanout)
  30      approvals   Approvals    scaffold (keep)
  35      steer       Steer        NEW (nexus SteerPage)
  40      autonomy    Autonomy     scaffold (keep)
  50      observatory Observatory  REWRITE (native Galaxy, no iframe)
  55      second-brain SecondBrain NEW (nexus SecondBrainPage)
  60      fusion      Fusion       NEW (gateway leg only)
  70      council     Council      NEW (nexus CouncilPage)
  75      activity    Activity     NEW (nexus ActivityPage)
  80      repo        Repo         NEW (nexus RepoPage)
  85      models      Models       NEW (gateway-transport only)
  90      settings    Settings     scaffold (keep)

  Routes intentionally NOT ported: SignInPage (pairing replaces auth),
  StudioPage (stub), ChampionshipPage (low priority, add later), SharePage
  (use Tauri native share instead), and all third-party-credential surfaces.

---------------------------------------------------------------------------
7. QUICK RISKS / OPEN DECISIONS
---------------------------------------------------------------------------

  - Observatory iframe: hard "no iframe" rule means the desktop Observatory.tsx
    rewrite must consume adapters/observatory.ts (snapshot+stream) and render the
    Galaxy/BrainLadder/StationPipeline components directly. This is the single
    largest port.

  - NEXUS uses framer-motion everywhere; the desktop scaffold is pure CSS. All
    ported page transitions must be re-authored as CSS (the tokens already define
    motion curves).

  - cockpit.ts (nexus) vs lib/gateway.ts (desktop) are near-identical protocols.
    Merge into ONE gateway client under lib/gateway.ts and have the Observatory
    data layer consume it.

  - Third-party model names in capabilityMatrix.json and ModelsPage violate the
    "no Google/Anthropic/OpenRouter in fusion" policy — strip to gateway routing.

  - No port of securestore/supabase: desktop persists the gateway token in
    localStorage (muse.cockpit.token) and pairs via /v1/cockpit/pair/*.
