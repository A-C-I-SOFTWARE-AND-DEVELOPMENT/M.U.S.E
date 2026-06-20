# g-rename-prep: repo-slug `hermes-agent` → `muse` (outward surfaces)

> **REWORKED at merge time (2026-06-08).** The owner renamed the GitHub repo to
> **`muse`** (not lowercase `muse`), so the GitHub URLs were re-pointed
> `hermes-agent` → **`A-C-I-SOFTWARE-AND-DEVELOPMENT/muse`** (README,
> CONTRIBUTING, issue/PR templates). The publish/deploy guards, Docker/PyPI/Cachix
> registry names, and the homebrew formula were **reverted to status quo** — they
> are dormant on this repo (the `github.repository ==` guards never matched it) and
> the registry renames are owner-coordinated, so changing them here would only risk
> dead refs or activating dormant publishing. GitHub's rename redirect covers any
> remaining `hermes-agent` references. The notes below describe the original
> (pre-rework) `muse` plan and are kept for history.

- **Status:** in-review
- **Risk class:** behavior-change (owner-gated) — **STAGED**: must merge in
  lockstep with the GitHub repo rename `hermes-agent` → `muse`. Merging before
  the rename would itself create the dead links it is meant to prevent.
- **Branch:** `claude/g-rename-prep` · **Base:** `main` @ `origin/main`
- **PR:** draft (do not merge until the GitHub repo is renamed)
- **Owner-gate required to merge?** yes — the owner lifted the *rename* gate;
  this PR's merge happens together with the actual GitHub rename, so it waits.

## Intent (one paragraph)

Rewrite the repo **slug** `hermes-agent` (hyphen) → `muse` on **outward
surfaces only**, so the upcoming GitHub repo rename leaves no dead links.
Only repo-slug references change: `github.com/<org>/hermes-agent` URLs,
`raw.githubusercontent.com/.../hermes-agent/...` install one-liners,
`git clone` + `cd` commands, the License badge target, the `github.repository`
CI guards, workflow asset/image/cache names, and the Homebrew formula
name/file/url. The underscore code identifiers `hermes_cli` / `hermes_agent`
(the substrate) and the doc-host string `hermes-agent.nousresearch.com`
(runtime data) are deliberately **left untouched**, as are prose/agent-name
and runtime-mirror occurrences. Default code paths are unchanged (no Python
touched); `uv run ruff check .` stays green.

## Owned files (the ONLY files this task may write)

- `README.md`
- `CONTRIBUTING.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/dependabot.yml`
- `.github/codeql/codeql-config.yml`
- `.github/ISSUE_TEMPLATE/{bug_report,config,feature_request,setup_help}.yml`
- `.github/actions/hermes-smoke-test/action.yml`
- `.github/actions/nix-setup/action.yml`
- `.github/workflows/{docker-publish,android-build,skills-index,deploy-site,upload_to_pypi,sync-aci-to-base44}.yml`
- `packaging/homebrew/hermes-agent.rb` → **renamed** to `packaging/homebrew/muserb` (`git mv`)
- `docs/launch/followups/g-rename-prep.md` (this snapshot)

> Disjoint from every other in-flight task. No shared files discovered.

## Slug references CHANGED (`hermes-agent` → `muse`; org segment preserved)

The org segment is left as-is in every case (rule 1): `NousResearch` stays
`NousResearch`, `A-C-I-SOFTWARE-AND-DEVELOPMENT` stays itself — only the
trailing `hermes-agent` slug becomes `muse`.

**README.md** (7 edits)
- L8 — License badge link target `github.com/A-C-I-…/hermes-agent/blob/main/LICENSE`.
- L111 — Linux/macOS install one-liner `raw.githubusercontent.com/A-C-I-…/hermes-agent/main/scripts/install.sh`.
- L121 — `--jarvis-launch` install one-liner (same raw URL).
- L139 — "file issues" link `github.com/A-C-I-…/hermes-agent/issues`.
- L144 — Windows PowerShell `irm …/hermes-agent/main/scripts/install.ps1`.
- L151 — Windows `-JarvisLaunch` one-liner (same raw `install.ps1` URL).
- L379–380 — contributor `git clone …/hermes-agent.git` + `cd hermes-agent`.
- L401 — Community "Issues" link `github.com/A-C-I-…/hermes-agent/issues`.

**CONTRIBUTING.md** (2 edits)
- L84–85 — `git clone --recurse-submodules …/hermes-agent.git` + `cd hermes-agent`.
- L904 — "GitHub Issues" link `github.com/A-C-I-…/hermes-agent/issues`.

**.github/PULL_REQUEST_TEMPLATE.md** (5 link targets)
- L45, L60, L67, L68 — Contributing-Guide deep links `github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md#…`.
- L47 — existing-PRs link `github.com/NousResearch/hermes-agent/pulls`.

**.github/ISSUE_TEMPLATE/config.yml** (2) — Documentation (`/blob/main/README.md`) and Contributing-Guide (`/blob/main/CONTRIBUTING.md`) contact-link URLs.

**.github/ISSUE_TEMPLATE/feature_request.yml** (2) — "skills, not tools" CONTRIBUTING deep link + "existing issues" link.

**.github/ISSUE_TEMPLATE/setup_help.yml** (1) — README troubleshooting anchor `github.com/NousResearch/hermes-agent#troubleshooting`.

**.github/ISSUE_TEMPLATE/bug_report.yml** (1) — "existing issues" link.

**.github/actions/nix-setup/action.yml** (1) — Cachix binary-cache `name: hermes-agent` → `name: muse` (workflow asset/cache name).

**.github/actions/hermes-smoke-test/action.yml** (1) — example image tag in the `image` input description `nousresearch/hermes-agent:test` (kept consistent with the docker image rename below).

**.github/workflows/docker-publish.yml** (10) — `IMAGE_NAME: nousresearch/hermes-agent` (1), the five `github.repository == 'NousResearch/hermes-agent'` job guards, and the four inline `image=nousresearch/hermes-agent` shell vars in move-main / move-latest.

**.github/workflows/android-build.yml** (1) — debug-APK upload artifact `name: hermes-agent-debug-apk` → `muse-debug-apk` (workflow asset name).

**.github/workflows/skills-index.yml** (1) — `github.repository == 'NousResearch/hermes-agent'` build-index guard.

**.github/workflows/deploy-site.yml** (1) — `github.repository == 'NousResearch/hermes-agent'` deploy-docs guard.

**.github/workflows/upload_to_pypi.yml** (1) — publish `environment.url: https://pypi.org/p/hermes-agent` (publish-asset/display URL tied to the package name).

**packaging/homebrew/hermes-agent.rb → muserb** (file rename + 4 content edits)
- File renamed via `git mv` (formula name derives from the filename).
- L1 — Ruby class `HermesAgent` → `muse` (Homebrew requires the class name to match the formula name, or `brew audit` fails).
- L8 — source `url "…github.com/NousResearch/hermes-agent/releases/download/…"` slug → `muse`. The sdist **asset filename `hermes_agent-0.6.0.tar.gz` is preserved byte-for-byte** (it is the published package artifact name, an underscore identifier — not the slug).
- L20 — comment `brew update-python-resources --print-only hermes-agent` (formula name).
- L46 — test assertion `assert_match "brew upgrade hermes-agent"` (formula name).

## `hermes-agent` occurrences in owned files INTENTIONALLY LEFT

Per rules 2 (never touch the doc-host or the underscore substrate) and 3
(leave prose / agent-name / non-slug occurrences and note them):

- **Doc-host `hermes-agent.nousresearch.com`** — runtime data, rule 2. Left in:
  `README.md` (L158, 185, 247, 253, 257–271, 374 — the doc table + "Full
  documentation" links), `CONTRIBUTING.md` L197 (project-structure comment),
  `packaging/homebrew/muserb` L5 (`homepage`),
  `.github/workflows/skills-index.yml` L92 (the `_site/CNAME` value),
  `.github/workflows/deploy-site.yml` L80 (llms.txt comment).
- **`CONTRIBUTING.md` L137** — `hermes-agent/` is the root label of the
  project-structure ASCII tree (a local directory-name illustration), not a
  repo-slug URL/asset. Left as prose.
- **`packaging/homebrew/muserb` L29** — `%w[hermes hermes-agent hermes-acp]`
  are the **console-script executable names** the package installs (binary
  identity from `pyproject.toml`), independent of the repo slug. Renaming would
  break the install. Also left: `desc` and the `"Hermes Agent v#{version}"`
  test assertion (product name printed by `hermes version`, not the slug).
- **`.github/codeql/codeql-config.yml` L1** and **`.github/dependabot.yml` L1**
  — descriptive header comments ("… configuration for hermes-agent"), prose,
  not links/assets. Left.
- **`.github/workflows/sync-aci-to-base44.yml` L31, L72, L80** — the
  `SOURCE_FOLDER: aci-hermes-agent-source` env var, the mirror-layout folder
  `aci-hermes-agent-source/`, and the `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`
  "Canonical ACI repo" line inside the source-of-truth heredoc are **runtime
  mirror data**, not outward install/badge/clone surfaces. Renaming the folder
  would change the Base44 mirror's on-disk layout (a behavior change, not a
  dead-link fix); the heredoc text describes the mirror relationship. Left
  intentionally — out of scope for "outward surfaces only."

## Residual / follow-on (NOT in this PR — flag for the orchestrator)

- **External registry/namespace renames must be coordinated with the merge.**
  A GitHub repo rename does NOT auto-rename the Docker Hub repo
  (`nousresearch/hermes-agent` → `nousresearch/muse`), the PyPI project
  (`hermes-agent` → `muse`), or the Cachix cache (`hermes-agent` → `muse`).
  The workflow edits above point CI at the renamed targets; those targets must
  exist (or be renamed) before the workflows run green. This is why the PR is
  STAGED.
- **`packaging/homebrew/muserb` L46 couples to runtime CLI output.** The
  `brew test` asserts `hermes update` prints `brew upgrade muse`. That string
  is emitted by the Hermes update code path (NOT an owned file). Update it in
  lockstep, or this brew test will fail post-rename. Tracked here, not fixed
  (outside owned files).
- **`packaging/homebrew/README.md`** (NOT owned) still references
  `packaging/homebrew/hermes-agent.rb` and the `hermes-agent` formula name in
  `brew` commands (L3, L12, L14). It is now stale (file renamed). The
  orchestrator should sequence a follow-up edit to that file (disjoint owner).
- **Many non-owned files** still carry `hermes-agent` slug/prose
  (`docs/README.md` install one-liner; `apps/android/README.md` release links +
  `hermes-agent-debug-apk` artifact reference; `skills/aos-enterprise-council/…`;
  `plugins/**/README.md`; `README.zh-CN.md` likely). They are out of this
  grain's owned set and must be handled by separate, disjoint grains.

## Validation

- `rg -n 'hermes-agent' README.md CONTRIBUTING.md .github/ packaging/` →
  only the intentionally-left prose / doc-host / runtime-mirror / binary-name
  hits enumerated above remain; **0 outward slug hits**.
- `rg -n 'hermes_cli|hermes_agent' <changed files>` → the only match is the
  preserved `hermes_agent-0.6.0.tar.gz` sdist asset filename on the homebrew
  `url` line (present identically on both `-` and `+` sides of the diff); no
  underscore identifier was altered.
- `git diff --stat` → 15 files, +43/-43; plus the staged `git mv`
  `packaging/homebrew/{hermes-agent.rb => muserb}`.
- `uv run ruff check .` → **All checks passed!** (no Python touched).
