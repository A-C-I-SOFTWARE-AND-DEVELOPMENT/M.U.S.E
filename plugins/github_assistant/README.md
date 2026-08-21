# github_assistant

Native GitHub access for Hermes. Eight REST-backed tools, three
independent safety gates, no token leaks.

For installation, scopes, and the difference between this plugin and
the official MCP `server-github`, see
[`docs/github-integration.md`](../../docs/github-integration.md).

## At a glance

```yaml
# ~/.hermes/config.yaml
github:
  enabled: true
  allow_writes: false                       # write tools refuse to run
  allowed_repositories:
    - "NousResearch/hermes-agent"        # everything else is denied
```

```bash
# ~/.hermes/.env
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_yourFineGrainedTokenHere
```

## Tools

| Tool | Action | Read/write |
|---|---|---|
| `github_audit_repo` | repo metadata | read |
| `github_get_repo_file` | one file at path / ref | read |
| `github_list_branches` | branches | read |
| `github_list_issues` | issues | read |
| `github_list_pull_requests` | PRs | read |
| `github_get_pull_request` | one PR | read |
| `github_create_issue` | new issue | **write** |
| `github_comment_on_issue_or_pr` | new comment | **write** |
