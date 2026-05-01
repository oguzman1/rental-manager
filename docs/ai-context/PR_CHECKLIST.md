# Rental Manager — PR Checklist

## Before implementation

- [ ] Request is captured in `BACKLOG.md`.
- [ ] Scope is clear.
- [ ] Non-scope is explicit.
- [ ] Candidate branch name is clear.
- [ ] Expected files are listed.
- [ ] Validation commands are defined.
- [ ] Claude receives a closed English prompt.

## During implementation

- [ ] Stop if unexpected files are touched.
- [ ] Stop if scope expands.
- [ ] Stop if backend/frontend contract changes unexpectedly.
- [ ] Keep commits small and explainable.

## Before commit

Collect evidence:

```bash
git status --short
git diff --stat
git diff
```

If frontend changed:

```bash
cd frontend && npm run lint && npm run build
cd ..
```

If backend changed:

```bash
pytest
```

For UI changes:

- [ ] Include screenshot or manual verification notes.
- [ ] Verify main user path.
- [ ] Verify at least one edge/error state if relevant.

Scope check:

- [ ] Files changed match the approved plan.
- [ ] No unrelated refactor.
- [ ] No sensitive local data committed.
- [ ] No `.env`, local DB, or private seed file committed.

## Before merge

- [ ] Branch pushed.
- [ ] PR description explains goal/scope/evidence.
- [ ] CI or local validation is green.
- [ ] Review comments resolved.
- [ ] Main branch is still compatible.
- [ ] Decide whether to squash merge.

## After merge

- [ ] Checkout main.
- [ ] Pull latest main.
- [ ] Delete local branch if safe.
- [ ] Update `AI_HANDOFF.md` if the state changed.
- [ ] Update `BACKLOG.md` if an item was completed or reprioritized.
- [ ] Decide the next PR candidate.
