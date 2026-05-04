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

---

## Candidato futuro — feature/payments-cascading-overpayment-allocation

**Tipo:** Payments / asignación financiera / backend + frontend UX
**Estado:** Futuro, no incluido en `feature/payments-overpayment-confirmation-ux`

### Problema

Durante el PR `feature/payments-overpayment-confirmation-ux` se detectó que el flujo actual de sobrepagos solo puede abonar el excedente al período inmediatamente siguiente.

Si el excedente supera lo que ese período puede absorber, se genera otro sobrepago y pueden aparecer prompts row-level amarillos después de guardar. Esto no representa el comportamiento financiero ideal cuando un pago cubre varios meses hacia adelante.

### Comportamiento deseado futuro

Cuando un pago genere un sobrepago suficientemente grande, el sistema debería permitir prorratear/asignar el excedente hacia períodos futuros de forma secuencial:

- cubrir primero el período siguiente hasta su monto esperado pendiente
- continuar con los períodos posteriores mientras quede excedente
- crear períodos futuros faltantes si corresponde
- dejar el último período como parcial si el excedente no alcanza para cubrirlo completo
- mostrar una vista previa antes de confirmar, por ejemplo:
  - Abril 2027: $253.750 completo
  - Mayo 2027: $138.750 parcial
- evitar que después de aplicar el sobrepago aparezcan nuevos prompts row-level causados por esa misma operación

### Decisiones pendientes antes de implementar

- Definir qué hacer si un período futuro intermedio ya está totalmente pagado:
  - saltarlo
  - detener la asignación
  - pedir decisión manual
- Definir cómo calcular el monto esperado de períodos futuros cuando existan reajustes.
- Definir si el endpoint actual `POST /payments/{payment_id}/apply-overpayment` debe evolucionar o si conviene crear un endpoint nuevo.

### Notas técnicas

- Revisar `apply_overpayment_to_next_period` en `db.py`.
- Revisar endpoint `POST /payments/{payment_id}/apply-overpayment` en `main.py`.
- Los tests actuales no cubren el caso en que el excedente supera la capacidad del período siguiente.

### Tests esperados en un PR futuro

- excedente mayor a un período
- asignación a 3+ períodos
- creación de períodos futuros faltantes
- período intermedio ya pagado
- último período parcial
- no generar un nuevo prompt row-level inmediatamente después de aplicar la asignación

### Non-scope del PR actual

No resolver en `feature/payments-overpayment-confirmation-ux`.
