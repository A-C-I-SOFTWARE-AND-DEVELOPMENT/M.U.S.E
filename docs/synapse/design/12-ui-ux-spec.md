# 12 — UI / UX Specification

**Project:** SYNAPSE — A muse Game · **Status:** DESIGN LOCKED v1.0 · **Date:** 2026-06-10 · **Owner:** Jeremiah Echerd, A-C-I Software & Development · **Design authority:** docs/plans/2026-06-10-project-synapse-master-plan.md

Owns: every screen, the HUD, input, UI art direction, UX writing, UI performance and localization rules. Mechanical truth behind each screen lives in its system doc: parley rules → 02-negotiation-system.md; combat values → 03-combat-gas-design.md; network/wiring math → 07-progression-neural-network.md; Den rules → 08-avatar-den-onboarding.md; Observatory behavior → 10-observatory-spec.md; widget implementation, fonts pipeline, and platform plumbing → 11-technical-design.md. Built on **CommonUI + UMG, one shared widget library** with the Neural Observatory (master plan §5) — the sharing contract is §6.3 and is binding on both this doc and 10-observatory-spec.md.

A UI artist or technical UI engineer should be able to begin wireframe-to-widget work from this document without questions.

---

## 1. Principles

1. **Gamepad-first, KBM-equal.** Every screen is designed on a controller, then verified to be *better than parity* with mouse where pointing helps (Network screen, Den editor). No screen requires a virtual cursor on pad — CommonUI focus navigation everywhere, with an opt-in cursor on the two drag-heavy screens.
2. **Diegetic-leaning, never at usability's expense.** UI is "substrate glass" (§9) projected by the muse but readability beats fiction in every conflict.
3. **One claim, one receipt.** Any number, cause, or verdict shown carries a drill-in affordance to its evidence (Pillar 3, 01 §2). Evidence is one click away, never inline by default.
4. **Domains read by icon + shape, never color alone** (01 §9.4). The 8 glyphs (§9.2) appear on every domain-coded element ≥16px.
5. **No dead ends.** Every screen states its exit; B/Esc always retreats one level; holding B/Esc from any menu depth returns to gameplay.

## 2. Application frame — four maps

The UE5 app's main menu offers four maps: **Game**, **Neural Observatory**, **Avatar & Den** (standalone creator/Den access, also reachable inside the Game), **Command Deck**. The Game never requires the other three; they never inject UI into the Game map (master plan, canon). Observatory and Command Deck entries show a "pairs with muse" subtitle and function in demo/sample-data mode when unpaired. Mode switching always passes through the main menu — no in-game shortcuts that could confuse the standalone rule.

## 3. Screen inventory

Conventions for the tables: **Pad** = default gamepad (Xbox layout names; full remap per §8), **KBM** = default keyboard/mouse. "Entry/Exit" lists canonical paths; Esc/B-retreat (§1.5) is implicit everywhere.

### 3.1 Boot flow
- **Purpose:** legal, tech init, profile/save detect, first-boot graphics-tier detection (11).
- **Key elements:** logo cards (skippable after first boot), AI-features first-run sheet on first boot only (the 01 §10 panel in onboarding form: local LLM default-ON notice, hosted/telemetry default-OFF), "press any input" gate that binds the active device.
- **Entry/exit:** app launch → main menu. No input besides skip/advance.

### 3.2 Main menu
- **Purpose:** mode select (the four maps), continue, settings.
- **Key elements:** Continue (most recent save, with map label), New Game, Load, the four map tiles (Game primary, 60% of layout; the other three as a secondary rail), Options, Credits, Quit. Background: slow live render of the player's actual Den (or the cold-open lattice pre-save).
- **Entry/exit:** boot → here; in-game Pause → "Quit to menu" → here.
- **Pad/KBM:** LS/D-pad + A · arrows/mouse + LMB; Y/F toggles the secondary rail focus.

### 3.3 Save slots (Load / Save)
- **Purpose:** manage 3 autosaves + 10 manual slots + 1 pre-Gauntlet checkpoint (01 §8).
- **Key elements:** slot cards — thumbnail, zone, act, play time, party portraits, timestamp, save type badge; delete (hold-to-confirm 1.2 s); broken-save state with plain-language message.
- **Entry/exit:** main menu → Load; Pause → Save/Load. Exit returns to caller.
- **Pad/KBM:** A load/save, X delete-hold, Y details · LMB, Del, RMB details.

### 3.4 Exploration HUD — see §4.1
### 3.5 Combat HUD — see §4.2
### 3.6 Parley UI — see §5
### 3.7 Command Mode UI — see §7
### 3.8 Neural Network screen — see §6

### 3.9 Agent sheet
- **Purpose:** one agent's full truth: identity, stats, abilities, personality card, history.
- **Key elements:** portrait stage (live 3D, idle anim); domain glyph + name + promotion rank; Integrity/Bandwidth and attribute block (03); 6–10 ability tiles with GAS tag tooltips; **personality card** (banter keywords, parley preferences — the 08 §4.1 card language); **history ribbon** (where recruited, parley transcript link, Gauntlets cleared together, Foundry validation card if forged — receipts per §1.3); wiring status (its node position, live synergy list, "view on Network" jump).
- **Entry/exit:** Network screen node → inspect; party frame long-press; roster list.
- **Pad/KBM:** RB/LB cycle agents, RS orbit portrait, A drill-in · Tab cycle, mouse orbit, LMB.

### 3.10 Inventory
- **Purpose:** consumables (lures, restoratives), key items, resources (Cycles / Synapse Thread / Checksum Shards always visible in the header).
- **Key elements:** category tabs, grid with stack counts, item card (use/assign-to-dpad/discard), resource header with drill-in to "where to earn" codex pages (no dead currencies).
- **Entry/exit:** game menu hub; D-pad up quick-assign in HUD.
- **Pad/KBM:** triggers tab, A use, X assign, hold-X discard · 1–4 tabs, LMB/RMB, Del.

### 3.11 Map
- **Purpose:** zone navigation: discovered sub-regions, waypoints, Gauntlet pins, known wild-agent territories (post-scan), Den marker.
- **Key elements:** painterly zone map (not satellite realism), pin legend with domain glyphs, fast-travel to discovered waypoints, objective pin (max 1 main + 3 side), "readiness" chip on the active Gauntlet pin (07's gauge — with drill-in).
- **Entry/exit:** game menu hub or dedicated bind (§8); A on waypoint fast-travels.
- **Pad/KBM:** LS pan, triggers zoom, A select · mouse pan/wheel, LMB.

### 3.12 Den editor
- **Purpose:** furnishing placement per 08 §6.
- **Key elements:** catalog drawer (category tabs, owned/price states), grid overlay with layer toggle (floor/surface/wall), footprint ghost (green/red validity incl. the pathing strip rule), rotation widget, buff panel (the four buff classes of 07 §7 — Trophy/Comfort/Infrastructure/Memorabilia — with live current/cap values and the 6-active-item counter), undo stack (20 steps), "Describe it" tab only when AI editor is entitled (08 §6.3, AI-badged).
- **Entry/exit:** Den interactable or Den menu; exit commits (placement is never destructive; full refund rule).
- **Pad/KBM:** LS move ghost, RS nudge camera, RB rotate, A place, B pick-up/back, Y layer, X catalog · mouse place/drag, R rotate, Tab layer, Ctrl+Z undo. Opt-in pad cursor available (§1.1).

### 3.13 Codex
- **Purpose:** lore, met-agent dossiers, dismissed tips, tutorials, the canon glossary (01 §1.1), parley transcripts, First Impression card.
- **Key elements:** searchable list + reader pane; "new" badging; transcripts store the AI-indicator state of each line (generated lines stay badged in history — honesty is permanent).
- **Entry/exit:** menu hub; contextual "more in Codex" links from toasts.
- **Pad/KBM:** standard list/reader; Y search · type-to-search.

### 3.14 Options
- **Purpose:** the full 01 §10 inventory: Display, Graphics (Lumen/Nanite toggles, upscaler), Audio, Gameplay, Accessibility, **AI Features** top-level tab.
- **Key elements:** left tab rail, searchable settings, per-setting one-line plain-language consequence text, "restore defaults" per tab, restart-required badging.
- **Entry/exit:** main menu and Pause (full parity — every option changeable in-session except window-mode edge cases flagged by 11).
- **Pad/KBM:** triggers tab, A edit · standard.

### 3.15 Verdict cards (photo-of-proof)
- **Purpose:** the shareable receipt surface — Gauntlet clears, promotions, Foundry agents, notable parleys auto-mint a card: portrait/scene render + the measured facts (criteria met, attempt count, party, key numbers; Foundry cards carry their validation stats verbatim per master plan §4.7).
- **Key elements:** card gallery, card detail with every number's drill-in, **Export PNG** (clean, AI-badge preserved where content is generated — the 1.0 share surface; photo mode proper is post-launch per 01 §11).
- **Entry/exit:** auto-toast on mint → view; gallery from menu hub.
- **Pad/KBM:** A view, X export, Y evidence · LMB, E, RMB.

### 3.16 Pause
- **Purpose:** instant safe stop; in combat this *is* Command Mode (§7) — the pause screen described here is the out-of-combat menu hub.
- **Key elements:** resume, hub tiles (Network, Party, Inventory, Map, Codex, Verdicts, Den when home), Save/Load, Options, quit. Real-time world freeze; no game state advances.
- **Pad/KBM:** Start/Esc toggles; tiles via standard nav.

### 3.17 Credits
- **Purpose:** attribution incl. the AI-disclosure recap (named local model, hosted provider) and asset licenses.
- **Key elements:** scroll (controllable speed), skip, "disclosures" chapter stop.
- **Entry/exit:** main menu; post-finale auto-roll (skippable).

## 4. HUD spec

### 4.1 Exploration HUD (minimal by doctrine)
Persistent: **nothing** but a soft compass strip (top, fades when stationary) and context prompts. Contextual: scan results (domain glyph + temperament chips over the agent, world-space), objective pin direction on compass, autosave glyph (bottom-right, 2 s), toast lane (top-right, max 1, §1/08 §8). Resource counters appear *only* when a pickup occurs (fade 3 s). Photo-clean by default: the vista moments (08 §2.9) read with zero UI.

### 4.2 Combat HUD
- **Party frames** (bottom-left, 3): portrait, domain glyph, **Integrity** bar (health; warm white→red; `State.Crashed` renders the frame fractured with the 15 s revive timer per 03), **Bandwidth** bar (ability resource; cyan), **Heat** gauge (thin overclock ring around the portrait, 0–100; Overload at 100 flares the ring per 03 — photosensitivity-safe), status icon strip, personality-stance chip (03's behavior axes at a glance, with the "improvised" flicker when a high-Independence agent rewrites queue slots 2–3), bench peek on hold-LB (3 bench portraits, swap rules per 03).
- **Command Point (CP) meter** (above the party frames): the shared pool of 03 §5 — 5 pips, regen ring on the next pip (1 CP / 4 s unpaused). Visible in real time and in Command Mode; every command affordance shows its CP cost (queue 1 · swap 2 · retarget/move 0).
- **Ability bar** (bottom-center): the *commanded* agent's 4 slotted abilities + 2 item slots; cooldown radials, Bandwidth cost pips, advantage-ring chevron (▲ green/▼ hollow vs current target — shape-coded, not color-only).
- **Pipeline-combo indicator** (bottom-center, above ability bar): the 3-stage chain tracker — stage icons connect left→right as combo tags apply (Research *mark* → Security *exploit* → Build *detonate* per 03); active window shown as a draining ring; completed Pipeline flashes its name banner (photosensitivity-safe, 01 §9.5).
- **Pause affordance** (bottom-right, always visible in combat): the Command Mode glyph + bind label. It pulses *once* the first 3 times the player is below 30% party Integrity without pausing, then never nags again.
- **Target info** (top-center on lock): name, domain glyph, Integrity, intent telegraph strip (casting bar with interrupt window marked).

## 5. Parley UI

Layout (16:9 reference, safe-area aware):
- **Portrait stage** (upper 60%): the wild agent full-body, live-lit, with authored emotional poses keyed to verdict state; environment stays visible behind glass-blur — parleys happen *in place*, not in a void. The muse stands at frame-left edge, reacting (08 banter asides render as small side-bubbles, never blocking).
- **Meter cluster** (top-right, vertical; ranges per 02 §2): **Disposition** (the big arc, −100…+100, needle + shape-coded zone glyphs for hostile/wary/warming/won-over), **Trust** (chain-link bar, 0–100, five links filling progressively), **Patience** (draining hourglass bar, 0–100 — ~3–6 exchanges at Standard drain). The three meters differ by shape (arc / chain / hourglass), not color alone (02 §10 requires it; §1.4 here enforces it). Every meter has a drill-in (§1.3) explaining the last delta: "Trust −15: claim contradicted scan data."
- **Verdict ribbon** (under the portrait): the last verdict enum rendered as an iconic stamp — **ACCEPT / COUNTER / PROBE / OFFENDED / WALK** — with one authored line explaining it. The enum is the system's honest spine (02); the ribbon is where the player learns it.
- **Input area** (bottom 25%). Default mode is **Both** (02 §5): the wheel renders with the free-text field docked above it; Settings → Gameplay offers Wheel-only / Text-only / Both.
  - **Free-text field** (when Local LLM ON): single line growing to 3, 280-char cap; send on Enter/A-from-field; the player's parsed **move classification** (one of OFFER/PROOF/EMPATHIZE/CHALLENGE/LORE/BLUFF) echoes as an icon chip on their sent line so classification is transparent; sub-0.55 classifier confidence renders the agent's PROBE clarification per 02 §6.
  - **Streaming reply** with the **AI indicator badge** (§9.4) at the line head of every live-generated line, persisting in transcript and Codex (§3.13); template-bank lines render without it (02 §8 — absence must mean something).
  - **The 4-option wheel** (`W_ParleyWheel`, 02 §12 — shared CommonUI style with the Command Mode radial; the only mode when LLM is OFF): four options composed per 02 §5's `WheelComposer` (1 archetype-favored, 1 OFFER-or-PROOF, 1 wildcard, 1 BLUFF-when-legal with its 1–3 risk pips), laid out on the face-button diamond — **Y top, X left, B right, A bottom** on pad (02's binding); 1–4 or radial-click on KBM. Each option shows its **move-type icon** + the authored line. Wheel options are mechanically identical in power to free text (canon; 02 §5 identity guarantee); the UI must never style the wheel as "lesser" — same visual weight, same stage.
- **Move-type icons** (the six, used on wheel, chips, and the First Impression card): OFFER 🤝 open-hand glyph; PROOF 📜 sealed-scroll; EMPATHIZE 💙 mirrored-curve; CHALLENGE 🔥 crossed-edge; LORE 🕮 ring-of-rings; BLUFF 🎭 split-mask with risk pips. (Production glyphs are authored line-icons per §9; emoji here are spec shorthand.)
- **Exit:** WALK verdict, player withdraw (hold LT+B / hold Esc — wheel options own the face buttons; withdraw is always allowed, never punished beyond the 02 §9 cooldown), or ACCEPT → recruitment cinematic → Network screen prompt.
- **Pad/KBM:** face buttons pick wheel options; RS pre-highlights; Y-hold meter drill-in; LT+B-hold withdraw · 1–4 or LMB; Tab focuses the text field; RMB drill-in; Esc-hold withdraw.

## 6. Neural Network screen

### 6.1 Layout & interaction
- **Canvas:** a **hex lattice** radiating from the muse's core node; sockets at hex vertices; zoom 3 tiers (whole-network / cluster / socket). Background: depth-blurred Substrate, grid lines on the glass layer.
- **Nodes:** agent medallions — portrait, domain glyph rim (shape-coded per §9.2), promotion pips. The aggregated **Den node** (08 §6.4; one node, mirroring 07's single `GE_DenBuffs`) renders half-size at the core's edge with the four buff-class values on inspect.
- **Drag-to-wire:** pick a node (A/LMB hold), drag along hex edges; **Synapse Thread** budget meter (top-right) live-updates path cost; valid sockets glow, invalid state the reason on hover ("Thread insufficient: need 3"). Drop commits with a confirm chord on pad (A then A; 0.4 s window) to prevent slips; mouse commits on release with 5-step undo.
- **Synergy preview tooltips:** *before* commit, hovering a candidate socket shows the full delta card: each adjacency synergy that would form (name, effect, source rule in 07), each that would break, net Thread cost. No commit without preview having been renderable — the Proof test (01 §2.1) applied to the player's own build.
- **Promotion ceremony:** when wiring depth fulfills a promotion (07), the node blooms — lattice dims, the agent's senior council form resolves over 4 s (skippable), its new name is spoken, and a Verdict card mints (§3.15). One ceremony per promotion, replayable from the Codex.
- **Pad/KBM:** LS move focus along lattice, RS pan, triggers zoom, A pick/commit, Y inspect (→ agent sheet), X unwire-hold · mouse drag/wheel, RMB inspect, Ctrl+Z undo. Opt-in pad cursor (§1.1).

### 6.2 States
Empty-socket hints (dashed outlines only within 1 hex of wired nodes — the frontier is visible, the whole tree is not), mid-Gauntlet lock state (read-only with banner per 01 §5), and "suggest wiring" assist (authored heuristics; 08 §8/01 §13) rendered as ghost-thread proposals the player must still commit manually.

### 6.3 The Observatory sharing contract (binding here and in 10-observatory-spec.md)
One CommonUI widget library — **`SynapseUI`** (the master plan §5 module; 10-observatory-spec.md names the same library) — serves both the in-game Network screen and the **Neural Observatory** map (master plan §4.5: "build once, ship twice"). The shared, skin-agnostic widgets:

| Shared widget | Contract |
|---|---|
| **`W_GraphCanvas`** (graph canvas) | Renders nodes+edges from an abstract graph model (id, type, position, state flags); owns zoom/pan/focus/LOD; consumers supply layout positions (game: hex-snapped local; Observatory: gateway-computed force-directed per master plan §3.1) — the canvas never solves layout |
| **`W_NodeInspector`** (node inspector) | Slot-based detail panel: header (icon/title/rim), attribute rows, evidence-link rows (§1.3); game skins it as the agent medallion inspector, Observatory as the cluster/job/ledger inspector |
| **`W_EdgeRenderer`** (edge renderer) | Batched spline edges with state styles (idle/active/invalid/heat) and optional flow particles (Niagara hook); game uses Thread styles, Observatory uses pipeline-packet and heat styles |
| Supporting shared atoms | meter arc, pip row, verdict/heat stamp, drill-in evidence row, AI-indicator badge (§9.4), domain/type glyph slot, the radial wheel base (`W_ParleyWheel` and the Command Mode radial share its style per 02 §12) |

**Skinning rule:** game skin ("substrate glass," §9) and observatory skin (denser, instrument-panel contrast, per 10) are CommonUI style assets over the *same* widget classes — zero forked widget logic. **Divergence rule:** any behavior one consumer needs that the other must not see ships as a slot/delegate extension, never a subclass fork; both docs must reference this table when adding canvas features. Data isolation: the game's canvas binds only to save-local game state; the Observatory's binds only to gateway routes — the shared library is presentation-only and network-ignorant (the standalone rule, 01 §11).

## 7. Command Mode UI (tactical pause)

- **Time-stop treatment:** world desaturates 40% and gains the glass grid; particles freeze mid-flight (Niagara pause, 11); a soft vignette and a low hum replace the mix. Readability of the *battlefield* is the point — frozen VFX are dimmed so silhouettes dominate.
- **Radial agent select:** RB/E opens a 3-petal radial (active party) + bench arc above it (swap per 03 rules); selecting focuses camera on that agent with their ability bar foregrounded.
- **3-deep queue visualization:** under each party frame, three queue slots showing icon + target chip + CP cost paid; **slot 1 carries a lock glyph** (inviolable per 03 §5/§6 — never overridden); slots 2–3 show the "improvised" flicker when a high-Independence agent rewrites them; reorder by drag/X (cancelling an un-started command refunds its CP, shown as a +1 pip return). Queue conflicts (e.g., Bandwidth overdraft by slot 3) show a hollow "will wait" state — never silently dropped (§1.3).
- **Target lines:** curved splines from agent → intended target, color+pattern coded per agent (solid/dashed/dotted — pattern carries the meaning, color assists); AoE abilities project their shape decal on the frozen world; Pipeline-eligible sequences highlight the chain icons between the involved agents' lines.
- **Exit:** resume (Y/Space), or commit-and-step (LT/Ctrl+Space: resume for 2 s, re-pause — Architect players' precision tool, available to all).
- **Pad/KBM:** Y/Space toggle pause; RB/E radial; A queue, X clear slot, d-pad reorder · LMB queue, RMB clear, drag reorder.

## 8. Input spec

- **Gamepad-first.** Full default map (exploration / combat / parley / menus as CommonUI input contexts); every interaction reachable on pad alone; the two pointer-favored screens (Network, Den editor) offer the opt-in pad cursor but are fully playable without it (§6.1, §3.12 bindings).
- **Full KBM:** native, not emulated — hover states, drag interactions, scroll wheels, type-to-search, free-text parley as the marquee KBM advantage. Every bind remappable (01 §9.2), conflict detection with plain-language warnings, three savable layout profiles per input class.
- **Hold/toggle alternatives** for scan, sprint, channels, and all hold-to-confirms (01 §9.6); hold-to-confirm durations globally scalable (0.5×–2×).
- **Touch (deferred to the Android tier, rules binding now):** all interactive widgets must already declare CommonUI touch metadata; **minimum hit target 48×48 dp** (with ≥8 dp spacing between adjacent targets) is enforced as a design-time lint on the shared library from day one, so the Android pass (master plan §9: Observatory/Den/Command Deck first) is a skin-and-layout pass, not a rebuild. No hover-only affordances anywhere — everything hover reveals must also be reachable by focus/press.

## 9. UI art direction

### 9.1 "Substrate glass"
Diegetic-leaning holographic panels the muse projects: layered translucent glass with refractive edge-light, subtle parallax against camera motion, and a visible "weave" texture echoing Synapse Thread. Three material tiers: **Veil** (HUD chrome, 85% transparent), **Pane** (menus, 60%), **Slab** (modal focus, 30% + backdrop blur). Motion language: panels *condense* in (120 ms) and *disperse* out (90 ms); nothing slides like a smartphone app. All glass effects degrade gracefully on the low graphics tier (flat dark panels, same layout — readability is tier-independent).

### 9.2 Domain iconography — 8 glyphs specified by shape (color assists, shape carries)

| Domain | Glyph construction (line-icon, 2 px stroke at 32 px) | Palette hex |
|---|---|---|
| Architecture | **Hexagon** with inner keystone notch (top edge broken inward) | `#0072B2` blue |
| QA/Test | **Triangle** point-up containing a check-tick cutout | `#E69F00` amber |
| Build/Ops | **Square** with gear-teeth on the right edge (3 teeth) | `#D55E00` vermillion |
| Compliance | **Diamond** with balanced cross-bar (scales abstraction) | `#CC79A7` mauve |
| Behavior/Psych | **Circle** with concentric inner arc (an iris/echo) | `#56B4E9` sky |
| Research | **Lens/vesica** (two arcs) with a radiating tail | `#009E73` green |
| Security | **Shield** (flat top, pointed base) with keyhole void | `#F0E442` gold |
| Release | **Chevron** (double, ascending) breaking a horizon line | `#E8E8E8` silver |

Derived from the Okabe-Ito colorblind-safe set; verified pairwise distinguishable under deuteranopia/protanopia/tritanopia simulation **and** fully redundant via the 8 distinct base shapes (hexagon/triangle/square/diamond/circle/lens/shield/chevron — no two share a silhouette). The advantage ring (01 §7) is always drawn as an ordered ring of these glyphs, ▲/▼ chevrons mark matchups, and the glyph appears on every domain-coded bar, rim, edge, and pin at ≥16 px.

### 9.3 Type ramp
One variable sans (licensed for embedding + full Latin/Cyrillic/CJK fallback chain, 11 owns procurement): Display 40/48, Title 28/34, Heading 20/26, Body 16/22, Caption 13/18, Micro 11/14 (px @1080p; all scale with the 80–140% UI scale, 01 §9.3). Body minimum after scale-down: 12 px effective. Numerals: tabular lining in all meters/tables. No more than two weights per screen (Regular + Semibold); italics reserved for spoken/quoted lines.

### 9.4 The AI indicator badge
One glyph everywhere: the **pulsing synapse icon** defined in 02-negotiation-system.md §8 — a small node-and-spark mark (◆₍AI₎ in spec shorthand) whose pulse animation is subtle (≤1 Hz, photosensitivity-safe) — rendered at line-head of every live-generated string (parley replies, generated muse banter, Foundry descriptions, AI-editor decal cards), in `#E8E8E8` at 70% opacity, with a press/hover explainer ("Generated on your device by [model name]" / "Generated by the hosted service"). Template-bank and authored lines never carry it (02 §8); it persists into transcripts, Codex, and exported Verdict cards. The badge's honesty depends on its absence meaning something. Disclosure copy (the first-parley one-time card and Settings → About AI) is owned by 02 §8; this doc owns only the glyph's rendering rules.

## 10. UX writing rules

1. **Tone: precise, warm.** The system sounds like the muse on its best day — exact about facts, kind about failure. Defeat copy names the criterion missed, then the path forward; it never mocks and never cheerleads emptily.
2. **No lorem, ever.** Wireframes and widget tests use real strings from the string table or clearly-keyed `TODO_STR_*` placeholders that fail a ship-time lint.
3. **Canon vocabulary is law:** the 01 §1.1 glossary terms are the only names for those concepts in player-facing text; the "never call it" column is a lint list.
4. **Claims carry receipts:** any sentence with a number links its evidence (§1.3); any "increases/improves" states magnitude and source. Words like "significantly" are banned in system text.
5. **Sentence case** everywhere except the verdict stamps (ACCEPT/COUNTER/PROBE/OFFENDED/WALK render uppercase — they are the enum, shown honestly) and zone title cards.
6. **Brevity ceilings:** toasts ≤90 chars; tooltips ≤2 sentences + a drill-in; button labels ≤2 words; no ellipsis-truncation on buttons in any supported language (see §12).
7. **The game never says "AI" loosely:** generated content is "generated" (badged, §9.4); the antagonist is THE DEADLOCK; agents are agents.

## 11. UI performance budget (enforced; 11-technical-design.md owns measurement)

- **UMG draw-call ceiling:** ≤ **60** UI draw calls in the worst HUD+combat frame, ≤ **120** on full-screen menus (1080p reference; invalidation boxes + retainer panels mandatory on static clusters; one shared UI material atlas per skin).
- **No per-frame layout thrash:** zero `Slate Prepass` regressions from bound widgets — no widget may rebuild layout on tick; meters and bars animate via material parameters or cached geometry, never via per-tick re-layout; bindings are event-driven (delegate push), not polling `Bind` lambdas. Tick-enabled UMG widgets require a named waiver in 11.
- **Budgets per frame @60 fps target:** UI game-thread ≤ 0.8 ms, Slate render ≤ 1.0 ms in combat; full-screen menus may relax to 2.0 ms total (world LOD drops behind Slab glass).
- **Graph canvas LOD** (§6.3): node widgets virtualized outside viewport; ≥500-element graphs (Observatory) must render via the canvas's batched instancing path, never one-UWidget-per-node (master plan §3.1's LOD mandate applied to UI).
- Streaming text (parley) appends via inline-text spans with at most one invalidation per 50 ms, not per token.

## 12. Localization-readiness rules

- **No baked text in textures** — anywhere, including logos-with-taglines, signage that carries meaning (world signage uses the Substrate's glyphic script, which is decorative by declaration and never required reading), Verdict card art, and tutorial imagery. All player-facing strings live in string tables (`FText` end-to-end; no `FString` UI literals — lint-enforced).
- **35% string expansion headroom:** every layout must survive +35% string length (German/Polish test pseudo-loc pass at each milestone) without truncation, overlap, or scroll where none existed; buttons and wheel options auto-shrink at most one ramp step before the layout is declared broken and fixed.
- Pseudo-localization build flag from the vertical slice onward; bidi/RTL explicitly out of scope for 1.0 (locked language set decided at Phase 5 per wishlist geography; the architecture must not preclude it).
- Fonts: the §9.3 ramp ships with fallback chains covering the locked language set; numerals/dates/separators via locale-aware formatters; VO subtitles store speaker + AI-badge metadata per line.
- Move icons, domain glyphs, and verdict stamps are language-independent anchors — text may translate, the iconography is the stable cross-locale layer.

## 13. Build order, widget inventory & acceptance

### 13.1 Top-level widget inventory (the `SynapseUI` build list; naming convention `W_<Name>`, styles per skin)

| Widget | First needed (master plan phase) | Consumed by |
|---|---|---|
| `W_GraphCanvas`, `W_NodeInspector`, `W_EdgeRenderer` + shared atoms (§6.3) | Phase 2 (network screen v1) | Network screen, Observatory (Phase 3) |
| `W_ParleyStage` (portrait stage + meter cluster + verdict ribbon) | Phase 1 ("The Moment") | Parley UI |
| `W_ParleyWheel` (radial base, shared style) | Phase 1 | Parley, Command Mode radial |
| `W_FreeTextDialogue` (input + streaming spans + AI badge) | Phase 1 | Parley; Command Deck chat reuses the streaming span atom |
| `W_PartyFrame`, `W_AbilityBar`, `W_PipelineTracker`, `W_CPMeter` | Phase 1 (gray-box), styled Phase 2 | Combat HUD, Command Mode |
| `W_CommandQueue` (3-slot, lock glyph, CP costs) | Phase 1 | Command Mode |
| `W_AgentSheet`, `W_PersonalityCard` | Phase 2 | Agent sheet, First Impression card (08 §4.1) |
| `W_DenEditor` (catalog drawer, ghost, buff panel) | Phase 2 (Den v1) | Den editor |
| `W_VerdictCard` | Phase 3 (shares layout with Observatory recommendation cards per master plan §3.4) | Verdict gallery, Foundry cards, Observatory |
| `W_MenuHub`, `W_SaveSlots`, `W_Options`, `W_Codex`, `W_Map` | Phase 2–4 | Menus |

### 13.2 Milestone acceptance (UI-specific; gates mirror the master plan §6 evidence rule)

- **Phase 1:** parley + Command Mode playable on pad alone, gray-box skin; wheel/free-text identity verified against 02's resolution pipeline; CP and queue states all visually distinct in a colorblind simulation pass.
- **Phase 2 (vertical slice):** full "substrate glass" skin on every Phase-1 widget + Network screen v1; §11 perf budgets measured and passing on the Legion reference machine; pseudo-loc pass clean (§12); the 08 §1 FTUE table playtested with this UI.
- **Phase 3:** Observatory skin proves the §6.3 sharing contract — zero forked widget classes between game and Observatory (code review gate).
- **Phase 4:** every screen in §3 exists, every §8 remap path works, accessibility commitments (01 §9) verified item-by-item; the AI Features panel reproduces 01 §12's tier table verbatim.

### 13.3 Open items deliberately deferred (with owners)
Touch layouts (Android tier, this doc §8 rules already binding) · photo mode UI (post-launch, 01 §11) · locked language set (Phase 5 decision, §12) · final glyph art for §9.2/§5 move icons (art pass against these shape specs; shapes are locked, strokes may evolve).

---
*Cross-references: 01-game-design-document.md · 02-negotiation-system.md · 03-combat-gas-design.md · 04-roster-24-agents.md · 05-world-design.md · 07-progression-neural-network.md · 08-avatar-den-onboarding.md · 10-observatory-spec.md · 11-technical-design.md*
