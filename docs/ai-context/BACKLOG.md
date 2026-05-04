# Rental Manager — Backlog

## Intake format

Use this format for each new request:

```text
Screen or module:
What happens today:
What should happen:
User impact:
Screenshot or evidence:
```

## Recently resolved

| Branch | Module | Type | Summary |
|---|---|---|---|
| fix/payments-overpayment-cancel-loop | PaymentsView | Bug / UX flow | Fixed overpayment cancel behavior: pre-save Cancelar now aborts the pending save flow without creating/updating a payment, and row-level Cancelar dismisses the apply-overpayment prompt for the same payment and overpayment amount without calling backend. |

## Inbox

### RM-001 — Rework Dashboard right-side action cards

- Module: Dashboard / right-side notices panel / `NoticesPanel`
- What happens today: The panel shows pending items, but cards do not clearly communicate the required action. The earlier 422 issue when clicking a payment notice seems resolved after PR #26, but it should be verified manually as a regression.
- What should happen: Cards should represent pending actions of two types: payments and rent adjustments. Each card should explain the action, property, context, amount, and include a visible CTA.
- Expected types:
  - Overdue payment
  - Payment due soon
  - Partial payment
  - Adjustment pending
  - Adjustment ready to apply
- User impact: High. The Dashboard should act as an operations center, not just an informational list.
- Status: Pending product/design/architecture pass before implementation.
- Priority: P1

## Classified backlog

| ID | Title | Type | Module | Priority | Status |
|---|---|---|---|---|---|
| RM-001 | Rework Dashboard right-side action cards | Functional UX | Dashboard / NoticesPanel / Payments navigation | P1 | Pending planning |

## PR candidates

### PR Candidate 1 — Dashboard action cards

Goal: Convert the Dashboard right-side panel into an actionable pending-actions panel.

Tentative scope:

- Verify manually that the previous 422 payment-navigation bug no longer reproduces.
- Redesign payment cards textually and visually.
- Define a common notice/action-card model if needed.
- Identify what is missing before rent-adjustment cards can become fully actionable.

Tentative non-scope:

- No broad refactor.
- No Contracts work unless strictly needed.
- No Tenants work unless strictly needed.
- No full rent-adjustment implementation if backend/flow is not ready.
