# Rental Manager — Prompt Templates

Use these templates when handing work to Claude.

## 1. Claude Design — planning only

```text
You are working on the Rental Manager app.

Do not implement anything yet.

Goal:
[Describe the product/UX goal.]

Current behavior:
[Describe what happens today.]

Desired behavior:
[Describe what should happen.]

Constraints:
- Do not write code yet.
- Do not do a broad refactor.
- Keep the scope limited to [module].
- Preserve existing behavior unless explicitly changed.
- Identify risks and missing information.

Please respond with:

1. Product diagnosis.
2. UX proposal.
3. Suggested states and copy.
4. Data/model needs.
5. Files likely involved.
6. Risks.
7. A maximum 5-step implementation plan.
8. What should be verified manually.
```

## 2. Claude Code — implementation after approval

```text
You are working on the Rental Manager app.

Implement only the approved scope below.

Goal:
[Approved goal.]

Scope:
[Exact scope.]

Non-scope:
[List explicit non-goals.]

Expected files:
[List expected files. Do not touch other files unless strictly necessary and explain why.]

Constraints:
- Keep the change minimal.
- Do not disable lint rules.
- Do not do broad refactors.
- Preserve existing behavior outside this scope.
- If you discover unexpected complexity, stop and report before expanding scope.

Validation commands:
```bash
cd frontend && npm run lint && npm run build
cd ..
pytest
git status --short
```

After implementation, report:

1. Files changed.
2. Summary of changes.
3. Validation commands run and exact results.
4. Any manual verification needed.
5. Any risks or follow-up work.
```

## 3. Claude Audit — review existing changes

```text
You are auditing recent changes in the Rental Manager app.

Do not modify files.

Audit goal:
[What needs to be verified.]

Please inspect:

- git status
- git diff
- touched files
- tests/lint/build results if available
- whether scope matches the approved plan
- whether any unrelated files were modified
- whether frontend behavior matches the intended UX

Report:

1. What changed.
2. Whether the change matches the approved scope.
3. Evidence from diff/tests/build/lint.
4. Risks or issues.
5. Whether this is safe to commit.
6. If not safe, the smallest corrective action.
```

## 4. Bug triage — no implementation

```text
We need to diagnose a bug in Rental Manager.

Do not implement anything yet.

Bug:
[Describe bug.]

Expected behavior:
[Describe expected behavior.]

Evidence:
[Paste logs, screenshot, or reproduction steps.]

Please respond with:

1. Most likely cause.
2. Exact failing call, component, or function.
3. Minimal fix strategy.
4. Files likely involved.
5. Risks.
6. Validation plan.
7. Whether this should be fixed in the current PR or split into another PR.
```

## 5. PR closeout summary

```text
Create a PR closeout summary.

Include:

- PR number/title:
- Branch:
- What changed:
- Evidence:
- Tests/lint/build:
- Manual verification:
- Decisions added:
- Risks remaining:
- Next candidate PR:
```
