import { Fragment, useEffect, useState } from 'react'
import Topbar from './Topbar'
import { PaymentBadge } from './Badge'
import { formatCLP, formatPeriodLabel, formatAmountInput, parseAmountInput } from './utils'

const API_BASE = 'http://127.0.0.1:8000'

const STATUS_ES = { pending: 'Pendiente', partial: 'Parcial', paid: 'Pagado' }

function todayLocal() {
  const now = new Date()
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
  ].join('-')
}

function addOneMonth(period) {
  const [y, m] = period.split('-').map(Number)
  const nm = m === 12 ? 1 : m + 1
  const ny = m === 12 ? y + 1 : y
  return `${ny}-${String(nm).padStart(2, '0')}`
}

function isFullyPaid(payment) {
  if (!payment) return false
  if (payment.paid_amount == null || payment.expected_amount == null) return false
  return payment.paid_amount >= payment.expected_amount
}

// Returns the amount to prefill in "Agregar pago":
// - pending/null → expected_amount
// - partial → remaining balance (expected - paid)
// - paid → '' (no prefill; user can still type)
function getPrefillAmount(payment) {
  if (!payment) return ''
  if (payment.status === 'paid') return ''
  if (payment.status === 'partial' && payment.paid_amount != null) {
    return String(Math.max(0, payment.expected_amount - payment.paid_amount))
  }
  return String(payment.expected_amount)
}

// Returns the next payable period using priority:
//   1. earliest partial  2. earliest pending  3. virtual next month (all paid)
function getNextPayablePeriod(payments, sortedPayments) {
  const asc = [...payments].sort((a, b) => a.period.localeCompare(b.period))
  const partial = asc.find(p => p.status === 'partial')
  if (partial) return { period: partial.period, payment: partial, isVirtual: false }
  const pending = asc.find(p => p.status === 'pending')
  if (pending) return { period: pending.period, payment: pending, isVirtual: false }
  if (sortedPayments.length > 0) {
    const [y, m] = sortedPayments[0].period.split('-').map(Number)
    const nextM = m === 12 ? 1 : m + 1
    const nextY = m === 12 ? y + 1 : y
    const period = `${nextY}-${String(nextM).padStart(2, '0')}`
    return { period, payment: null, isVirtual: true }
  }
  return { period: '', payment: null, isVirtual: false }
}

function PaymentsView({ contract, onBack, onPaymentMutation, targetPeriod }) {
  const [payments, setPayments] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showAll, setShowAll] = useState(false)

  // 'add' | 'edit' | null
  const [activeForm, setActiveForm] = useState(null)
  const [formError, setFormError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // "Agregar pago" form
  const [formPeriod, setFormPeriod] = useState('')
  const [formUseCustom, setFormUseCustom] = useState(false)
  const [formCustomPeriod, setFormCustomPeriod] = useState('')
  const [formAmount, setFormAmount] = useState('')
  const [formDate, setFormDate] = useState(todayLocal())
  const [formNote, setFormNote] = useState('')

  // Edit form
  const [editPayment, setEditPayment] = useState(null)
  const [editAmount, setEditAmount] = useState('')
  const [editDate, setEditDate] = useState('')
  const [editNote, setEditNote] = useState('')

  // Overpayment
  const [applyingOverpayment, setApplyingOverpayment] = useState(new Set())
  const [overpaymentError, setOverpaymentError] = useState(null)
  const [pendingOverpaymentId, setPendingOverpaymentId] = useState(null)
  // Keyed by payment.id → dismissed overpayment amount. Hides the prompt after "No abonar ahora"
  // until the payment is edited and the overpayment amount changes.
  const [dismissedOverpayments, setDismissedOverpayments] = useState({})
  // Pre-save overpayment draft: set when handleAdd/handleEdit detects excess before submitting.
  // Shape: { source, period, enteredAmount, expectedAmount, originPaidBefore, originPaidAfter,
  //          overpaymentAmount, formDate, formNote, paymentId, nextPeriod, nextPayment }
  const [pendingOverpaymentDraft, setPendingOverpaymentDraft] = useState(null)

  async function loadPayments() {
    try {
      const res = await fetch(`${API_BASE}/contracts/${contract.id}/payments`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setPayments(await res.json())
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    async function fetchData() {
      try {
        const res = await fetch(`${API_BASE}/contracts/${contract.id}/payments`)
        if (!res.ok) throw new Error(`Error ${res.status}`)
        const data = await res.json()
        if (!cancelled) {
          setPayments(data)
          setIsLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message)
          setIsLoading(false)
        }
      }
    }
    fetchData()
    return () => { cancelled = true }
  }, [contract.id])

  const sortedPayments = [...payments].sort((a, b) => b.period.localeCompare(a.period))
  const now = new Date()
  const currentYear = now.getFullYear()
  const currentMonth = now.getMonth() + 1
  const maxYear  = currentMonth === 12 ? currentYear + 1 : currentYear
  const maxMonth = currentMonth === 12 ? 1 : currentMonth + 1
  const maxPeriod = `${maxYear}-${String(maxMonth).padStart(2, '0')}`
  const minPeriod = `${currentYear}-01`
  const defaultVisiblePayments = sortedPayments.filter(
    p => p.period >= minPeriod && p.period <= maxPeriod
  )
  const hiddenCount = payments.length - defaultVisiblePayments.length
  const visiblePayments = showAll ? sortedPayments : defaultVisiblePayments

  // Next calendar month after the last known period — used as virtual "Próximo período" option
  const nextVirtualPeriod = (() => {
    if (sortedPayments.length === 0) return null
    const [y, m] = sortedPayments[0].period.split('-').map(Number)
    const nextM = m === 12 ? 1 : m + 1
    const nextY = m === 12 ? y + 1 : y
    return `${nextY}-${String(nextM).padStart(2, '0')}`
  })()

  function openAdd() {
    if (payments.length === 0) {
      setFormPeriod('')
      setFormUseCustom(true)
      setFormCustomPeriod(targetPeriod ?? todayLocal().slice(0, 7))
      setFormAmount(contract.current_rent != null ? formatAmountInput(contract.current_rent) : '')
      setFormDate(todayLocal())
      setFormNote('')
      setFormError(null)
      setActiveForm('add')
      return
    }

    if (targetPeriod) {
      const p = payments.find(py => py.period === targetPeriod) ?? null
      setFormPeriod(targetPeriod)
      setFormUseCustom(p === null && targetPeriod !== nextVirtualPeriod)
      setFormCustomPeriod(p === null && targetPeriod !== nextVirtualPeriod ? targetPeriod : '')
      setFormAmount(formatAmountInput(p ? getPrefillAmount(p) : contract.current_rent))
      setFormDate(todayLocal())
      setFormNote('')
      setFormError(null)
      setActiveForm('add')
      return
    }

    const { period, payment, isVirtual } = getNextPayablePeriod(payments, sortedPayments)
    setFormPeriod(period)
    setFormUseCustom(false)
    setFormCustomPeriod('')
    setFormAmount(formatAmountInput(isVirtual ? contract.current_rent : getPrefillAmount(payment)))
    setFormDate(todayLocal())
    setFormNote('')
    setFormError(null)
    setActiveForm('add')
  }

  function handlePeriodSelect(value) {
    if (value === '__custom__') {
      setFormUseCustom(true)
      return
    }
    setFormPeriod(value)
    const p = payments.find(py => py.period === value)
    if (p) {
      setFormAmount(formatAmountInput(getPrefillAmount(p)))
      setFormDate(p.paid_at ?? todayLocal())
    } else {
      // Virtual period not yet created — default to expected monthly rent
      setFormAmount(formatAmountInput(contract.current_rent))
      setFormDate(todayLocal())
    }
  }

  function openEdit(payment) {
    setEditPayment(payment)
    setEditAmount(formatAmountInput(payment.paid_amount ?? payment.expected_amount))
    setEditDate(payment.paid_at ?? todayLocal())
    setEditNote(payment.comment ?? '')
    setFormError(null)
    setActiveForm('edit')
  }

  function cancelForm() {
    setPendingOverpaymentDraft(null)
    setActiveForm(null)
    setFormError(null)
  }

  async function handleAdd(e) {
    e.preventDefault()
    setIsSubmitting(true)
    setFormError(null)
    setOverpaymentError(null)
    const period = formUseCustom ? formCustomPeriod : formPeriod
    const amount = parseAmountInput(formAmount)
    const existing = payments.find(p => p.period === period)
    const expectedAmount = existing ? existing.expected_amount : (contract.current_rent ?? 0)
    const alreadyPaid = existing ? (existing.paid_amount ?? 0) : 0
    const originPaidAfter = alreadyPaid + amount
    const overpaymentAmount = Math.max(0, originPaidAfter - expectedAmount)
    if (overpaymentAmount > 0) {
      const nextPeriod = addOneMonth(period)
      const nextPayment = payments.find(p => p.period === nextPeriod) ?? null
      setPendingOverpaymentDraft({
        source: 'add',
        period,
        enteredAmount: amount,
        expectedAmount,
        originPaidBefore: alreadyPaid,
        originPaidAfter,
        overpaymentAmount,
        formDate,
        formNote,
        paymentId: existing?.id ?? null,
        nextPeriod,
        nextPayment,
      })
      setIsSubmitting(false)
      return
    }
    try {
      if (existing) {
        const res = await fetch(`${API_BASE}/payments/${existing.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            paid_amount: (existing.paid_amount ?? 0) + amount,
            paid_at: formDate,
            ...(formNote ? { comment: formNote } : {}),
          }),
        })
        if (!res.ok) throw new Error(`Error ${res.status}`)
      } else {
        const res = await fetch(`${API_BASE}/contracts/${contract.id}/payments`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            period,
            paid_amount: amount || null,
            paid_at: formDate || null,
            comment: formNote || null,
          }),
        })
        if (res.status === 409) {
          setFormError(`Ya existe un pago para el período ${period}.`)
          return
        }
        if (!res.ok) throw new Error(`Error ${res.status}`)
      }
      setActiveForm(null)
      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleEdit(e) {
    e.preventDefault()
    setIsSubmitting(true)
    setFormError(null)
    const newTotal = parseAmountInput(editAmount)
    const originPaidBefore = editPayment.paid_amount ?? 0
    const expectedAmount = editPayment.expected_amount
    const overpaymentAmount = Math.max(0, newTotal - expectedAmount)
    if (overpaymentAmount > 0) {
      const period = editPayment.period
      const nextPeriod = addOneMonth(period)
      const nextPayment = payments.find(p => p.period === nextPeriod) ?? null
      setPendingOverpaymentDraft({
        source: 'edit',
        period,
        enteredAmount: newTotal,
        expectedAmount,
        originPaidBefore,
        originPaidAfter: newTotal,
        overpaymentAmount,
        formDate: editDate,
        formNote: editNote,
        paymentId: editPayment.id,
        nextPeriod,
        nextPayment,
      })
      setIsSubmitting(false)
      return
    }
    try {
      const body = {}
      if (editAmount !== '') body.paid_amount = newTotal
      if (editDate !== '') body.paid_at = editDate
      if (editNote !== '') body.comment = editNote
      const res = await fetch(`${API_BASE}/payments/${editPayment.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setActiveForm(null)
      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleDelete(payment) {
    if (!window.confirm(`¿Eliminar el pago de ${payment.period}?`)) return
    try {
      const res = await fetch(`${API_BASE}/payments/${payment.id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`Error ${res.status}`)
      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleApplyOverpayment(payment) {
    setPendingOverpaymentId(null)
    setApplyingOverpayment(prev => new Set([...prev, payment.id]))
    setOverpaymentError(null)
    try {
      const res = await fetch(`${API_BASE}/payments/${payment.id}/apply-overpayment`, {
        method: 'POST',
      })
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setDismissedOverpayments(prev => {
        const next = { ...prev }
        delete next[payment.id]
        return next
      })
      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setOverpaymentError(err.message)
    } finally {
      setApplyingOverpayment(prev => {
        const next = new Set(prev)
        next.delete(payment.id)
        return next
      })
    }
  }

  // Saves the payment from pendingOverpaymentDraft.
  // applyAfter=true: also calls apply-overpayment (Case A/B).
  // applyAfter=false: saves only, no transfer (Case C — next period fully paid).
  async function saveFromDraft(applyAfter) {
    if (!pendingOverpaymentDraft) return
    const { period, paymentId, originPaidAfter, formDate, formNote } = pendingOverpaymentDraft
    setIsSubmitting(true)
    setFormError(null)
    setOverpaymentError(null)
    try {
      let resolvedId = paymentId
      if (paymentId != null) {
        // PATCH: add-to-existing (originPaidAfter = alreadyPaid + entered)
        //        or edit (originPaidAfter = entered, replaces rather than adds)
        const res = await fetch(`${API_BASE}/payments/${paymentId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            paid_amount: originPaidAfter,
            ...(formDate ? { paid_at: formDate } : {}),
            ...(formNote ? { comment: formNote } : {}),
          }),
        })
        if (!res.ok) throw new Error(`Error ${res.status}`)
      } else {
        // POST: new period (add flow only, paymentId is null)
        const res = await fetch(`${API_BASE}/contracts/${contract.id}/payments`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            period,
            paid_amount: originPaidAfter || null,
            paid_at: formDate || null,
            comment: formNote || null,
          }),
        })
        if (!res.ok) throw new Error(`Error ${res.status}`)
        const data = await res.json()
        resolvedId = data.id
      }
      if (applyAfter) {
        const applyRes = await fetch(
          `${API_BASE}/payments/${resolvedId}/apply-overpayment`,
          { method: 'POST' }
        )
        if (!applyRes.ok) {
          // Payment already persisted — do not retry. Reload and show row-level error.
          setPendingOverpaymentDraft(null)
          setActiveForm(null)
          await loadPayments()
          await onPaymentMutation?.()
          setOverpaymentError('El pago se guardó, pero no se pudo abonar el excedente. Intenta nuevamente desde la fila.')
          return
        }
      }
      setPendingOverpaymentDraft(null)
      setActiveForm(null)
      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  const periodOptions = [...payments].sort((a, b) => a.period.localeCompare(b.period))

  // Build the inline confirmation panel JSX once, shared by add and edit forms.
  let overpaymentPanel = null
  if (pendingOverpaymentDraft) {
    const {
      source,
      period,
      enteredAmount,
      expectedAmount,
      originPaidBefore,
      originPaidAfter,
      overpaymentAmount,
      nextPeriod,
      nextPayment,
    } = pendingOverpaymentDraft

    const fullyPaidBlocked = isFullyPaid(nextPayment)
    const nextRemainingCapacity = nextPayment == null
      ? (contract.current_rent ?? 0)
      : Math.max(0, (nextPayment.expected_amount ?? 0) - (nextPayment.paid_amount ?? 0))
    const overflowBlocked = overpaymentAmount > nextRemainingCapacity
    const nextBlocked = fullyPaidBlocked || overflowBlocked

    let originLine
    if (source === 'edit') {
      originLine = (
        <>
          Monto actualizado: <strong>{formatCLP(originPaidAfter)}</strong>
          {' '}(antes: {formatCLP(originPaidBefore)})
          {' · '}Esperado: {formatCLP(expectedAmount)}
          {' · '}Excedente: <strong>{formatCLP(overpaymentAmount)}</strong>
        </>
      )
    } else if (originPaidBefore > 0) {
      originLine = (
        <>
          Ya pagado: {formatCLP(originPaidBefore)}
          {' + '}Nuevo abono: {formatCLP(enteredAmount)}
          {' = '}Total: <strong>{formatCLP(originPaidAfter)}</strong>
          {' · '}Esperado: {formatCLP(expectedAmount)}
          {' · '}Excedente: <strong>{formatCLP(overpaymentAmount)}</strong>
        </>
      )
    } else {
      originLine = (
        <>
          Registrado: <strong>{formatCLP(originPaidAfter)}</strong>
          {' · '}Esperado: {formatCLP(expectedAmount)}
          {' · '}Excedente: <strong>{formatCLP(overpaymentAmount)}</strong>
        </>
      )
    }

    let destLine
    if (fullyPaidBlocked) {
      destLine = (
        <>
          ⚠ <strong>Período de destino: {formatPeriodLabel(nextPeriod)}</strong>
          {' '}— ya está totalmente pagado.
        </>
      )
    } else if (nextPayment == null) {
      destLine = (
        <>
          <strong>Período de destino: {formatPeriodLabel(nextPeriod)}</strong>
          {' '}— aún no existe. Se creará al aplicar el excedente.
        </>
      )
    } else {
      const currentPaid = nextPayment.paid_amount ?? 0
      const afterApply = currentPaid + overpaymentAmount
      const nextExpected = nextPayment.expected_amount
      destLine = currentPaid === 0 ? (
        <>
          <strong>Período de destino: {formatPeriodLabel(nextPeriod)}</strong>
          {' '}— pendiente, sin pago registrado.
          {' '}Después de aplicar: <strong>{formatCLP(overpaymentAmount)}</strong> de {formatCLP(nextExpected)}.
        </>
      ) : (
        <>
          <strong>Período de destino: {formatPeriodLabel(nextPeriod)}</strong>
          {' '}— parcial: {formatCLP(currentPaid)} de {formatCLP(nextExpected)}.
          {' '}Después de aplicar: <strong>{formatCLP(afterApply)}</strong> de {formatCLP(nextExpected)}.
        </>
      )
    }

    overpaymentPanel = (
      <div className="payment-overpayment-inline">
        <p className="payment-overpayment-heading">
          Se detectó un sobrepago
        </p>
        <p className="payment-overpayment-confirm-text">
          El monto ingresado supera lo esperado para este período.
        </p>
        <p className="payment-overpayment-confirm-text">
          <strong>Período de origen: {formatPeriodLabel(period)}</strong>
          <br />
          {originLine}
        </p>
        <p className="payment-overpayment-confirm-text">
          {destLine}
        </p>
        <p className="payment-overpayment-confirm-text">
          {fullyPaidBlocked
            ? 'El período de destino ya está totalmente pagado. Si guardas sin abonar excedente, el sobrepago quedará registrado en el período de origen.'
            : overflowBlocked
              ? 'El excedente supera lo que necesita el período de destino. La asignación automática en múltiples períodos aún no está disponible. Si guardas sin abonar excedente, el sobrepago quedará registrado en el período de origen.'
              : `Si guardas y abonas el excedente, se abonarán ${formatCLP(overpaymentAmount)} a ${formatPeriodLabel(nextPeriod)}.`
          }
        </p>
        <div className="payment-form-actions">
          {!nextBlocked && (
            <button
              type="button"
              className="btn-primary"
              onClick={() => saveFromDraft(true)}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Guardando…' : 'Guardar y abonar excedente'}
            </button>
          )}
          {nextBlocked && (
            <button
              type="button"
              className="btn-warn-sm"
              onClick={() => saveFromDraft(false)}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Guardando…' : 'Guardar sin abonar excedente'}
            </button>
          )}
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setPendingOverpaymentDraft(null)}
            disabled={isSubmitting}
          >
            Volver a editar
          </button>
        </div>
      </div>
    )
  }

  return (
    <>
      <Topbar
        title={`Pagos — ${contract.property_label}`}
        breadcrumb={['Contratos', contract.property_label]}
        actions={
          <button className="btn-secondary" onClick={onBack}>
            ← Volver
          </button>
        }
      />
      <div className="page-body">
        <div className="payment-info-line">
          <span>{contract.tenant_name}</span>
          <span className="payment-info-sep">·</span>
          <span>Esperado: {formatCLP(contract.current_rent)}</span>
          <span className="payment-info-sep">·</span>
          <span>Día de pago: {contract.payment_day}</span>
        </div>

        {/* Agregar pago form */}
        {activeForm === 'add' && (
          <form className="payment-form" onSubmit={handleAdd}>
            <div className="payment-form-row">
              {!formUseCustom ? (
                <label className="payment-form-label">
                  Período
                  <select
                    className="payment-form-input"
                    value={formPeriod}
                    onChange={e => handlePeriodSelect(e.target.value)}
                    disabled={!!pendingOverpaymentDraft}
                  >
                    {periodOptions.map(p => (
                      <option key={p.period} value={p.period}>
                        {formatPeriodLabel(p.period)} — {STATUS_ES[p.status] ?? p.status}
                      </option>
                    ))}
                    {nextVirtualPeriod && !payments.some(p => p.period === nextVirtualPeriod) && (
                      <option value={nextVirtualPeriod}>
                        Próximo período — {formatPeriodLabel(nextVirtualPeriod)}
                      </option>
                    )}
                    <option value="__custom__">Otro período…</option>
                  </select>
                </label>
              ) : (
                <label className="payment-form-label">
                  Período
                  <input
                    className="payment-form-input"
                    type="text"
                    value={formCustomPeriod}
                    onChange={e => setFormCustomPeriod(e.target.value)}
                    placeholder="ej. 2025-04"
                    required
                    disabled={!!pendingOverpaymentDraft}
                  />
                  {payments.length > 0 && !pendingOverpaymentDraft && (
                    <button
                      type="button"
                      className="btn-link-secondary"
                      onClick={() => setFormUseCustom(false)}
                    >
                      ← Seleccionar de lista
                    </button>
                  )}
                </label>
              )}
              <label className="payment-form-label">
                Monto a registrar
                <input
                  className="payment-form-input"
                  type="text"
                  inputMode="numeric"
                  value={formAmount}
                  onChange={e => setFormAmount(formatAmountInput(e.target.value))}
                  placeholder={`ej. ${formatAmountInput(contract.current_rent)}`}
                  required
                  disabled={!!pendingOverpaymentDraft}
                />
              </label>
              <label className="payment-form-label">
                Fecha pago
                <input
                  className="payment-form-input"
                  type="date"
                  value={formDate}
                  onChange={e => setFormDate(e.target.value)}
                  required
                  disabled={!!pendingOverpaymentDraft}
                />
              </label>
              <label className="payment-form-label">
                Nota
                <input
                  className="payment-form-input"
                  type="text"
                  value={formNote}
                  onChange={e => setFormNote(e.target.value)}
                  placeholder="opcional"
                  disabled={!!pendingOverpaymentDraft}
                />
              </label>
              {!pendingOverpaymentDraft && (
                <div className="payment-form-actions">
                  <button className="btn-primary" type="submit" disabled={isSubmitting}>
                    {isSubmitting ? 'Guardando…' : 'Guardar'}
                  </button>
                  <button className="btn-secondary" type="button" onClick={cancelForm}>
                    Cancelar
                  </button>
                </div>
              )}
            </div>
            {pendingOverpaymentDraft?.source === 'add' && overpaymentPanel}
            {formError && <div className="payment-form-error">{formError}</div>}
          </form>
        )}

        {/* Edit form */}
        {activeForm === 'edit' && (
          <form className="payment-form" onSubmit={handleEdit}>
            <div className="payment-form-row">
              <label className="payment-form-label">
                Período
                <input
                  className="payment-form-input"
                  type="text"
                  value={editPayment?.period ?? ''}
                  disabled
                />
              </label>
              <label className="payment-form-label">
                Monto pagado total
                <input
                  className="payment-form-input"
                  type="text"
                  inputMode="numeric"
                  value={editAmount}
                  onChange={e => setEditAmount(formatAmountInput(e.target.value))}
                  disabled={!!pendingOverpaymentDraft}
                />
              </label>
              <label className="payment-form-label">
                Fecha pago
                <input
                  className="payment-form-input"
                  type="date"
                  value={editDate}
                  onChange={e => setEditDate(e.target.value)}
                  disabled={!!pendingOverpaymentDraft}
                />
              </label>
              <label className="payment-form-label">
                Nota
                <input
                  className="payment-form-input"
                  type="text"
                  value={editNote}
                  onChange={e => setEditNote(e.target.value)}
                  placeholder="opcional"
                  disabled={!!pendingOverpaymentDraft}
                />
              </label>
              {!pendingOverpaymentDraft && (
                <div className="payment-form-actions">
                  <button className="btn-primary" type="submit" disabled={isSubmitting}>
                    {isSubmitting ? 'Guardando…' : 'Guardar'}
                  </button>
                  <button className="btn-secondary" type="button" onClick={cancelForm}>
                    Cancelar
                  </button>
                </div>
              )}
            </div>
            {pendingOverpaymentDraft?.source === 'edit' && overpaymentPanel}
            {formError && <div className="payment-form-error">{formError}</div>}
          </form>
        )}

        {isLoading && <div className="app-loading">Cargando pagos…</div>}
        {!isLoading && error && <div className="app-error">Error al cargar: {error}</div>}

        {/* Toolbar: main action + period toggle — toggle is always independent of activeForm */}
        {!isLoading && !error && (
          <div className="payment-table-toolbar">
            {!activeForm && (
              <button className="btn-primary" onClick={openAdd}>
                + Agregar pago
              </button>
            )}
            {hiddenCount > 0 && (
              !showAll ? (
                <button className="btn-link-secondary" onClick={() => setShowAll(true)}>
                  Mostrar más períodos ({hiddenCount})
                </button>
              ) : (
                <button className="btn-link-secondary" onClick={() => setShowAll(false)}>
                  Mostrar menos
                </button>
              )
            )}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && payments.length === 0 && (
          <div className="payment-empty">
            <p className="payment-empty-text">Sin períodos generados para este contrato.</p>
          </div>
        )}

        {/* Period table */}
        {!isLoading && !error && visiblePayments.length > 0 && (
          <div className="table-scroll">
            <div className="table-wrapper">
              <table className="dashboard-table">
                <thead>
                  <tr>
                    <th className="th">Período</th>
                    <th className="th">Vencimiento</th>
                    <th className="th th-right">Esperado</th>
                    <th className="th th-right">Pagado</th>
                    <th className="th">Fecha pago</th>
                    <th className="th">Estado</th>
                    <th className="th">Nota</th>
                    <th className="th">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {visiblePayments.map(p => {
                    const rowNextPeriod = addOneMonth(p.period)
                    const rowNextPayment = payments.find(q => q.period === rowNextPeriod) ?? null
                    const rowIsBlocked = isFullyPaid(rowNextPayment)
                    const rowNextRemainingCapacity = rowNextPayment == null
                      ? (contract.current_rent ?? 0)
                      : Math.max(0, (rowNextPayment.expected_amount ?? 0) - (rowNextPayment.paid_amount ?? 0))
                    const rowOverflowBlocked = p.overpayment > rowNextRemainingCapacity
                    return (
                      <Fragment key={p.id}>
                        <tr className="table-row-static">
                          <td className="td td-mono">{formatPeriodLabel(p.period)}</td>
                          <td className="td td-mono td-muted">{p.due_date}</td>
                          <td className="td td-right td-mono">{formatCLP(p.expected_amount)}</td>
                          <td className="td td-right td-mono">
                            {p.paid_amount != null
                              ? formatCLP(p.paid_amount)
                              : <span className="text-muted">—</span>}
                          </td>
                          <td className="td td-mono td-muted">
                            {p.paid_at ?? <span className="text-muted">—</span>}
                          </td>
                          <td className="td">
                            <PaymentBadge status={p.status} />
                          </td>
                          <td className="td td-muted">
                            {p.comment ?? <span className="text-muted">—</span>}
                          </td>
                          <td className="td">
                            <button className="btn-payments" onClick={() => openEdit(p)}>
                              Editar
                            </button>
                            {' '}
                            <button className="btn-payments-danger" onClick={() => handleDelete(p)}>
                              Eliminar
                            </button>
                          </td>
                        </tr>
                        {p.overpayment > 0 && dismissedOverpayments[p.id] !== p.overpayment && (
                          <tr className="overpayment-row">
                            <td colSpan={8} className="overpayment-cell">
                              <span className="overpayment-label">
                                Sobrepago: {formatCLP(p.overpayment)}
                              </span>
                              {rowIsBlocked ? (
                                <>
                                  <span className="overpayment-confirm-text">
                                    El período siguiente ({formatPeriodLabel(rowNextPeriod)}) ya está totalmente pagado. Aplicar este excedente generaría otro sobrepago. Revisa manualmente.
                                  </span>
                                  <button
                                    className="btn-warn-sm"
                                    onClick={() => setDismissedOverpayments(prev => ({ ...prev, [p.id]: p.overpayment }))}
                                  >
                                    No abonar ahora
                                  </button>
                                </>
                              ) : rowOverflowBlocked ? (
                                <>
                                  <span className="overpayment-confirm-text">
                                    El excedente supera lo que necesita el período siguiente. Abonarlo ahora generaría otro sobrepago.
                                  </span>
                                  <button
                                    className="btn-warn-sm"
                                    onClick={() => setDismissedOverpayments(prev => ({ ...prev, [p.id]: p.overpayment }))}
                                  >
                                    No abonar ahora
                                  </button>
                                </>
                              ) : pendingOverpaymentId === p.id ? (
                                <>
                                  <span className="overpayment-confirm-text">
                                    ¿Abonar este sobrepago al próximo período?
                                  </span>
                                  <button
                                    className="btn-warn-sm"
                                    onClick={() => handleApplyOverpayment(p)}
                                    disabled={applyingOverpayment.has(p.id)}
                                  >
                                    {applyingOverpayment.has(p.id) ? 'Aplicando…' : 'Confirmar'}
                                  </button>
                                  <button
                                    className="btn-warn-sm"
                                    onClick={() => {
                                      setPendingOverpaymentId(null)
                                      setDismissedOverpayments(prev => ({ ...prev, [p.id]: p.overpayment }))
                                    }}
                                  >
                                    No abonar ahora
                                  </button>
                                </>
                              ) : (
                                <button
                                  className="btn-warn-sm"
                                  onClick={() => setPendingOverpaymentId(p.id)}
                                  disabled={applyingOverpayment.has(p.id)}
                                >
                                  {applyingOverpayment.has(p.id) ? 'Aplicando…' : 'Abonar al próximo periodo'}
                                </button>
                              )}
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
              <div className="table-footer">
                <span>
                  {visiblePayments.length} período{visiblePayments.length !== 1 ? 's' : ''}
                  {!showAll && hiddenCount > 0 && ` · ${hiddenCount} ocultos`}
                </span>
              </div>
            </div>
          </div>
        )}

        {overpaymentError && (
          <div className="payment-form-error" style={{ padding: '8px 20px' }}>
            {overpaymentError}
          </div>
        )}
      </div>
    </>
  )
}

export default PaymentsView
