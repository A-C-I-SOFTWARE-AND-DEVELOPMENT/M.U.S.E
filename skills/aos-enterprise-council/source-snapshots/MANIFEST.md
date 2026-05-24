# Source Snapshots

This directory is intentionally empty inside the pack — the actual snapshot lives at the **repo root** under
`recovered-agent-sources/` (166 files preserved from the canonical hazmat-command repo plus 20 files from
the hermes-agent AOS skill set). See `../../../recovered-agent-sources/MANIFEST.md` for the full file index.

When this pack is installed into `~/.hermes/skills/aos-enterprise-council/`, copy the snapshot separately if
you want offline access:

```bash
cp -r ~/hermes-agent/recovered-agent-sources ~/.hermes/aos-recovered-sources
```

The skill pack only ships pointer files because the snapshot is large (~3 MB) and the canonical sources
live in their original repos. If a canonical source drifts, fall back to this snapshot.
