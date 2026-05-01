# Rental Manager — Decisions

## Process decisions

### D-001 — Manual multi-agent workflow

Use a manual multi-agent workflow before adopting an agent framework:

1. Product Agent
2. Design Agent
3. Architect Agent
4. Coder Agent
5. Audit Agent
6. Git/Release Manager

Reason: the user is still learning and wants practical control before moving into frameworks such as CrewAI.

### D-002 — One block, one branch, one PR

Default rule:

> one block = one branch = one PR

Reason: keeps scope small, reviewable, and easier to recover from.

### D-003 — Claude Code only implements closed specs

Claude Code should not receive vague implementation requests.

Before coding, ChatGPT should produce a closed spec with:

- goal
- scope
- non-scope
- expected files
- constraints
- validation commands
- required evidence

### D-004 — Evidence beats agent summaries

Do not approve work only because Claude says it worked.

Require concrete evidence:

- `git status --short`
- `git diff`
- lint/build/test output
- screenshots or manual verification for UI changes
- scope check against the original plan

### D-005 — Use English for Claude prompts

The user can think and plan in Spanish.

Prompts sent to Claude Design, Claude Code, and Claude Audit should be written in concise English.

Reason: technical tooling, code conventions, and AI coding instructions are usually clearer in English. The goal is precision more than token saving.

### D-006 — Group commands when risk is low

Low-risk, already audited commands can be grouped.

Use one-by-one commands when there is risk of:

- dirty working tree
- merge conflicts
- destructive Git operations
- force push
- reset/rebase
- ambiguous branch state

## Product decisions

### D-101 — Dashboard notices are actions, not passive alerts

Dashboard right-side cards should represent pending actions.

A useful card should communicate:

1. action needed
2. affected property
3. context
4. relevant amount
5. clear CTA

### D-102 — Payment and adjustment notices must remain distinct

Payments and rent adjustments should not be collapsed into ambiguous generic alerts.

They are different action types and may need different CTA behavior.
