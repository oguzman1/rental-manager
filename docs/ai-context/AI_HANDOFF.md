# Rental Manager — AI Handoff

## Current state

- Main is expected to include PR #26: `Fix PaymentsView lint and related updates`.
- PR #26 resolved frontend lint issues around `PaymentsView.jsx`, configured pytest module path, and kept tests passing.
- Latest known validation after PR #26:
  - `npm run lint` passed.
  - `npm run build` passed.
  - `pytest` passed with 89 tests.
- The previous 422 error when clicking a payment notice seems to have been resolved by recent work, but it should remain a regression check.

## Current workflow

Use the manual multi-agent framework:

1. Product Agent: clarify problem, affected user, desired outcome, priority.
2. Design Agent: define UX/UI behavior, copy, states, and flows.
3. Architect Agent: separate frontend/backend/data impacts, risks, and likely files.
4. Coder Agent: Claude Code implements only after receiving a closed spec.
5. Audit Agent: verify evidence, diff, tests, build, scope, and screenshots before commit.
6. Git/Release Manager: branch, PR, commit, merge, and next block.

Base rule:

> one block = one branch = one PR

Only break this rule explicitly.

## Current next focus

### RM-001 — Dashboard action cards

Rework the Dashboard right-side notices panel into an actionable operations panel.

The panel should represent pending actions of two types:

- payments
- rent adjustments

The previous 422 bug is no longer the main goal unless it reproduces again. Treat it as a regression check.

Expected payment card examples:

- Overdue payment
- Payment due soon
- Partial payment

Expected adjustment card examples:

- Adjustment pending
- Adjustment ready to apply

Each card should make clear:

1. what action is needed
2. which property it affects
3. relevant context, such as period or last adjustment
4. relevant amount
5. visible CTA to resolve the action

## Current non-goals

For RM-001, do not:

- touch Contracts unless strictly needed
- touch Tenants unless strictly needed
- do a broad refactor
- implement full rent-adjustment workflows if the underlying flow is not ready
- mix payment and adjustment logic into one ambiguous type

## Standard validation commands

For frontend/backend changes:

```bash
cd frontend && npm run lint && npm run build
cd ..
pytest
git status --short
```

For docs-only changes:

```bash
git diff --check
git status --short
```

## Evidence required before commit

Before approving a commit, collect:

- `git status --short`
- relevant `git diff`
- lint/build/test output when code changed
- screenshot or manual verification notes when UI changed
- confirmation that touched files match the planned scope

## Command style

Group low-risk commands when the state is known and clean.

Use one-by-one commands when there is risk of:

- data loss
- merge conflicts
- reset/rebase/force push
- dirty working tree
- ambiguous branch state
- broad file changes
