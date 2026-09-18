---
name: beads
description: Track durable Hajimi work, blockers, dependencies, and handoffs with bd.
triggers: issue, task, blocker, claim, close, handoff
---

# Objective

Keep production state durable across sessions without using markdown TODO files.

# Inputs

User-authorized work, current repository state, and verification results.

# Outputs

Beads issues, status changes, blockers, and completion reasons.

# Required Workflow

1. Run `bd prime` when context is missing or stale.
2. Create a bead before writing implementation code.
3. Claim work with `bd update <id> --claim`.
4. File follow-up blockers as child or related issues.
5. Close only after quality gates and handoff evidence exist.

# Quality Gate

The active issue names scope, acceptance, current status, and any blocked
external operation.

# Failure Conditions

Untracked work, premature close, or a markdown task list treated as canonical.

# Tools

`bd ready`, `bd show`, `bd create`, `bd update`, `bd close`, `bd remember`.

# Forbidden Patterns

Do not run `bd edit`, commit/push/sync without authority, or expose secrets.

# Handoff

Report issue IDs, changed files, checks, and exact next command.
