# Skill — prompt-upgrade-synthesis

## Purpose

Synthesize lessons from recent retrospectives into improvements
to the AEO's prompts, subagent task contracts, workflow
playbooks, and skill SOPs.

## Triggers

- A retrospective recommends an improvement.
- 8+ retrospectives have accumulated since the last synthesis.
- A pattern of confusion / drift surfaces across multiple
  sessions.

## Required Inputs

- The set of recent retrospectives.
- Current subagent task contract
  (`docs/agents/subagent-task-contract.md`).
- Current workflow playbooks (`docs/workflows/`).
- Current skill SOPs (`docs/skills/`).

## Research Required

- Patterns in retrospective "What didn't" notes.
- Anthropic / OpenAI agent best-practice updates (if any).

## Step-by-Step Method

1. Read all unprocessed retrospectives.
2. Cluster patterns: where did agents drift, miss a Stop
   Condition, exceed scope, produce shallow output?
3. For each pattern, propose an SOP / contract / playbook
   change:
   - Add a Stop Condition example to the subagent task contract.
   - Tighten a skill's Quality Checklist.
   - Rewrite a workflow playbook's Sequence section.
   - Add an anti-pattern to a governance doc.
4. Land each change as an RC2 PR.
5. Link from the originating retrospectives.

## Deliverable Format

A Prompt Evolution Memo + the PR(s) implementing the changes.

## Quality Checklist

- [ ] Every change traces to ≥ 2 retrospectives
- [ ] No prompt change overfits to a one-off
- [ ] Documentation cross-references updated
- [ ] Index updated if a new SOP / workflow lands

## Escalation Triggers

- A pattern that suggests a governance constitutional change
  (e.g. need to expand AGENTS.md) → L3 owner review.

## Related Agents

- Prompt Evolution Agent (Knowledge Operations)
- Agent Performance Evaluator (Knowledge Operations)
- Skill Library Manager (Knowledge Operations)

## Related Artifacts

- `docs/governance/agent-performance-scoreboard-schema.md`
- Recent `docs/research/retros/` entries
