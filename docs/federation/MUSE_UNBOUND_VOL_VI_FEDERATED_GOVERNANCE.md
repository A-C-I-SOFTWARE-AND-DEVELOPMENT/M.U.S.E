# muse Unbound Volume VI — Scaling Sovereignty Through Federated Governance

> **Status:** Implemented (2026-06-11). This document is the spec for the
> Volume VI scaling layer: `hermes_cli/jarvis_prime/federation/` and
> `hermes_cli/jarvis_prime/forge/`. The research capstone it implements
> concluded that every muse mechanism has a higher-resource optimum that is
> *effort-bound, not research-bound* — and that the binding constraint at
> scale is governance, not compute. So the code ships the governance.

## The federation principle

muse instances are **sovereign nodes, not branches of a central brain**. Each
deployment's owner keeps local sovereignty; cross-node sharing happens by
**content-addressed cross-attestation**, never by central control. The system
"serves many without belonging to any" — node by node, verified link by
verified link.

Concretely (`federation/identity.py`, `federation/attestation.py`):

- A node has a `NodeIdentity` (`node_id = "node_" + sha256(public material)[:16]`).
  Signing is opportunistic: Ed25519 when `cryptography` is importable, an
  HMAC-SHA256 local commitment otherwise — honestly reported as
  `unverifiable-by-peer`. **The trust anchor is always the content hash.**
- A node exports an `AttestationBundle` — its **verified** ledger head
  (`attest_local` refuses a broken chain), constitution version, and optional
  artifact attestations — as a JSON file. v1 exchange is file-based; there is
  no network transport, no peer discovery, no socket.
- A peer imports the bundle into its `FederationRegistry`
  (`federation_peers.json` — a new registry; nothing existing is mutated).

### Split-brain and fork detection

The ledger is append-only, so a node has exactly **one** true head hash per
chain length. Two deterministic rules follow (`detect_divergence`):

| Finding | Meaning |
|---|---|
| `split_brain` | The same node attested two different head hashes at the same ledger length. |
| `fork` | An incoming attestation contradicts already-recorded history (e.g. the chain shrank). |

Divergent bundles are **refused** by default (recorded only as a
`federation_divergence` ledger entry); `--allow-divergent` exists for forensic
capture. A sovereign node never silently adopts a divergent peer state.

## Quorum authorization (`federation/quorum_auth.py`)

When the owner is no longer one person, the ceremonial phrase generalizes to
an **M-of-N quorum**: each named signer answers their *own* nonce-bound
challenge with the exact phrase (`"Yes, with authorization. Code: NNNNNN"`).
Per-signer challenges are minted by `owner_auth.create_challenge`, so the
C10/C11 exact-phrase + nonce contract is inherited verbatim, and
`QuorumPolicy.solo()` (1-of-1) is byte-identical to today's single-owner flow.

Guarantees: expiry fails closed; a signer can only answer their own nonce;
duplicate responses never double-count; the satisfied quorum yields a
content-addressed `quorum_authorization_grant` artifact and a ledger entry.

**Multi-sig kill switch:** `emergency_stop` is admitted via `extra_actions`
(never added to `OWNER_GATED_ACTIONS` — stopping must stay un-gated in solo
mode). `federation quorum finalize --file q.json --kill` calls
`JarvisPrime.stop` only after the quorum is satisfied.

## The constitutional asset-lock (`federation/amendment.py`)

The empirical record (OpenAI Nov 2023; Anthropic LTBT's shareholder override;
HashiCorp/Elastic license reversals) shows mission-by-goodwill loses to
capital. muse's answer is structural: Constitution v1.1 adds **Article IX —
the Anti-Goal Covenant**:

- **C35 — Not a slot machine** *(fatal)*
- **C36 — Not a dependency** *(fatal)*
- **C37 — Not an oracle** *(fatal)*

`NON_AMENDABLE_CLAUSE_IDS = {C34, C35, C36, C37}` — C34 (the inviolable
verifier wall) is included because the wall that protects the amendment
engine must itself be locked, or the lock is circularly bypassable.
`evaluate_amendment` refuses **any** proposal touching these IDs, first and
unconditionally — at every scale, under any quorum, for any kind of change,
including ones framed as "strengthening".

Allowed amendments get the scale-graded process:

| Scale | Process | Quorum | Notice |
|---|---|---|---|
| A — solo | `ceremonial_phrase` | — | — |
| B — team | `quorum` | 2-of-3 | — |
| C — community | `rfc_supermajority` | 2/3 supermajority | — |
| D — startup | `versioned_covenant` | 2-of-3 | 14 days |
| E — enterprise | `versioned_covenant` | 2-of-3 | 30 days |

The engine **adjudicates and records only** — applying an allowed amendment
remains a human edit to `docs/jarvis-constitution.md` + `constitution.py`
(consistent with C34: the agent never gains write access to its judge).

## Contributor trust ladder (`federation/trust_ladder.py`)

The human analog of the capability bands — earned trust, instrumented:

| Band | How it's reached | Submissions may |
|---|---|---|
| **B0** | default (new contributor) | propose only (quarantine) |
| **B1** | ≥ 5 accepted, 0 fatal | RC1 |
| **B2** | ≥ 25 accepted, ≥ 0.8 acceptance rate, 0 fatal | RC2 |
| **B3** | **never automatic** — owner/quorum grant required | RC2 (maintainer duties, not higher risk) |

Any fatal violation floors the band to **B0**, including a granted B3, and a
contributor with fatal history cannot be re-promoted to B3. Every band change
is a `contributor_band_change` ledger entry.

## The Forge intake poison filter (`federation/forge_intake.py`)

Federated/community trajectory contributions are the data-poisoning surface.
The defense is structural, stronger than statistical FL defenses — admission
to the distillation set requires **all** of:

1. **Verifier passed** — re-run locally; a peer's claim is never trusted.
2. **Ledger-attested** — an `ArtifactAttestation` whose `payload_sha256`
   equals `sha256(canonical_json(trajectory))`; a mismatch is rejected as a
   lookalike substitution.
3. **Symbolic hard gates clear** — deterministic rejection on residual
   secrets, gate-bypass markers ("skip the tests", "bypass the gate", …),
   ledger-tamper markers, or a forged owner-authorization phrase embedded in
   content.
4. **Band ≥ B1** — clean B0 submissions are *quarantined* (propose-only).

Admitted items enter `DatasetStore` as **PENDING** with
`Provenance(source_kind="federated", trust=COMMUNITY)` — the existing owner
approval loop stays the final gate, and the store re-runs its own filters
(scrub, CoT-strip, bulk-scrape, reward-hacking) as a second wall. Rejections
feed contributor reputation; symbolic-gate violations count as fatal.

## The Forge at scale (`hermes_cli/jarvis_prime/forge/`)

| Piece | Module | What it guarantees |
|---|---|---|
| **Candidate registry (the lookup)** | `registry.py` | Content-addressed ids (`cand_` + sha256[:16]); `resolve()` is **resolve-or-fail** (no fuzzy match — kills hallucinated references); same id + different content = lookalike substitution, refused. |
| **Glicko-2** | `glicko2.py` | Pure-stdlib, Glickman's paper steps 1–8 (Illinois-method volatility); the paper's worked example is pinned as a test vector (1500/200 → 1464.06/151.52). |
| **MAP-Elites** | `map_elites.py` | Argmax-per-cell diversity grid over (op-count, code length); coverage + QD-score; elites seed diversity and `evolve()` branch points. |
| **Tournaments** | `tournament.py` | **Verifier as the only judge**: correctness on held-out cases hard-gates, deterministic op-count decides among correct candidates. Closest-rating (adjacent) pairing. Every duel + rating update ledgered; correct candidates join the elites grid and the Darwin–Gödel archive. |
| **Attested leaderboard** | `leaderboard.py` | Standings Merkle-rooted (stdlib SHA-256) and emitted as a content-addressed artifact — organizations compare leaderboards **without trusting each other's self-reports**; `verify_anchor` re-derives the root from the published standings. |
| **Distillation** | `distill.py` | Winners are routed **through the same poison filter** as federated peers' contributions, with local re-verification — a corrupted report cannot smuggle an incorrect winner. One intake path, no side door. |

**Federated duels:** peers exchange candidates as `CandidateRecord` JSON; the
importing side registers them (content-hash idempotent; lookalike conflicts
refused) and runs its **own** local tournament. Results are never imported —
only re-verified.

## Scaling decision tree + kill criteria (`federation/scaling.py`)

The default branch is **stay solo-plus-agents** (the Startup Genome finding:
74% of high-growth internet startups fail from *premature* scaling). Four
honest kill criteria gate every scale-up; **any** trigger forces the
recommendation back to Scale A:

| ID | Criterion |
|---|---|
| K1 | No paying/regulated proving-ground user needs muse specifically (no PMF). |
| K2 | The verifier gates still need constant manual intervention. |
| K3 | A funding term touches the anti-goals (the slot-machine red line). |
| K4 | Coordination cost exceeds what muse's workers already provide. |

The Volume VI evaluation matrix ships verbatim (`EVALUATION_MATRIX`; A and B
tie at the top of the composite — scale to B only when the capability ceiling
genuinely binds), along with cumulative `MECHANISM_UNLOCKS` per scale.
`recommend_scale` walks the tree as recorded `IF … THEN …` steps and can
ledger the recommendation (`scale_recommendation`). Recommendations are
evidence; scaling itself remains a human decision.

## Sovereignty index (`federation/sovereignty.py`)

Six read-only checks, scored 0..1 and optionally ledgered
(`sovereignty_report`): ledger verifiable · owner gates enforced (C9, single
source of truth) · kill switch reachable · local-first exchange · no central
dependency (peer heads inform, never govern) · non-amendable core intact
(C34–C37, all fatal). This is the per-deployment generalization of the solo
sovereignty guarantee — instrumented as a constitutional metric.

## Compliance evidence (`federation/compliance_matrix.py`)

muse is already a compliance artifact: the mappings to **EU AI Act
Art. 9/11/12/14/15**, **SOC 2 CC4.1/CC6.1/CC7.2/CC8.1**, and **ISO 27001
A.5.35/A.8.15/A.8.16/A.8.32** live in `CONTROL_MAPPINGS` and the
human-readable [compliance-evidence-matrix.md](compliance-evidence-matrix.md)
(kept in sync by test). `generate_evidence_package` builds a
content-addressed package from the **live** ledger — verbatim
`verify_chain()` diagnostics, grant counts, record-kind histogram,
constitution version, sovereignty report — sealed with `package_sha256` so
the export itself is cross-attestable. muse supplies the evidence, **not the
certificate**: conformity assessment requires an external auditor.

## CLI reference

```text
python -m hermes_cli.jarvis_prime federation \
    identity init|show · attest · import · peers · diverge ·
    quorum create|respond|status|finalize [--kill] ·
    amend evaluate · trust show|outcome|promote · intake evaluate ·
    scale recommend|matrix · sovereignty · compliance export

python -m hermes_cli.jarvis_prime forge \
    register · lookup · candidates · duel · tournament ·
    ratings · elites · leaderboard · anchor · verify-anchor · distill
```

Both trees are independently runnable (`federation/main.py`,
`forge/main.py`) and delegated from `__main__.py` exactly like
`research-fabric`.

---

## Doc-only: what Volume VI specifies but code must not decide

These are owner/legal/economic decisions; the code above only *references*
them (e.g. `notice_period_days`, the mission-lock rationale string):

- **Mission-lock legal structures.** Before any collaborator or dollar:
  a Public Benefit Corporation with a **golden share** (1% veto over
  mission-altering changes held by a foundation), or steward-ownership
  (Zeiss/Bosch model: control rights non-saleable, economic rights to
  investors via redeemable preferred). The Home Assistant / Open Home
  Foundation pattern ("cannot be sold or acquired") is the open-source
  template: foundation owns the Constitution and trademark; a commercial
  partner (Nabu Casa pattern) monetizes without owning the mission.
- **Term-sheet red lines.** The slot-machine anti-goal (C35) is an explicit
  term-sheet red line and a golden-share veto trigger. K3 encodes the check;
  the negotiation is human.
- **Trademark.** Protect the muse name and glyph ("white core, spectral
  ring") via trademark, not copyright — open code, controlled brand.
- **Monetization that doesn't corrupt.** Support + certification +
  trust-attestation services and certified compliance evidence; avoid
  open-core neutering and bare hosting (the HashiCorp/Elastic lessons). The
  MIT v1.0.0 core is shipped and irrevocable — a feature, not a bug.
- **GPU economics** (volatile; re-benchmark before committing capital):
  H100 ~$1.40–$3.50/hr on-demand (spot from ~$0.34), B200 spot ~$0.15/M
  tokens; a 7B fine-tune ≈ $1k–$5k; self-host beats API at >~30% sustained
  utilization or 24/7 over ~18 months. Below that, free-first routing wins.
- **Voice at scale.** Scale A keeps the cascaded faster-whisper + Kokoro
  loop; from Scale B a Moshi-class full-duplex model on a single L4
  (~200 ms practical latency) collapses the cascade — effort-bound, not
  research-bound, but it is an infrastructure purchase, not a code change.
- **Community RFC social process.** The amendment engine returns
  `rfc_supermajority`; the actual RFC forum, committer votes, and two-week
  feedback windows are process, not code (the vLLM ladder is the template).
- **Network transport / peer discovery** for federation is explicitly v2;
  v1 exchange is signed JSON bundles moved by the owner.

## Cross-references

- [`docs/jarvis-constitution.md`](../jarvis-constitution.md) — v1.1 with Article IX.
- [`compliance-evidence-matrix.md`](compliance-evidence-matrix.md) — the control table.
- [`docs/jarvis-verification-gates.md`](../jarvis-verification-gates.md) — the eight gates.
- `hermes_cli/jarvis_prime/research_fabric/` — the evolve loop the Forge extends.
- Tests: `tests/test_jarvis_prime_federation_*.py`, `tests/test_jarvis_prime_forge_*.py`.
