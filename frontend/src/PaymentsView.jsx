import { useEffect, useState } from 'react'
import Topbar from './Topbar'
import { PaymentBadge } from './Badge'
import { formatCLP, nextMissingPeriod } from './utils'

const API_BASE = 'http://127.0.0.1:8000'

function currentPeriod() {
  const now = new Date()
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  return `${now.getFullYear()}-${mm}`
}

function todayLocal() {
  const now = new Date()
  const yyyy = now.getFullYear()
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  const dd = String(now.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

// Mirrors backend derivation: clamps day to last day of month.
function deriveDueDate(period, paymentDay) {
  const year = parseInt(period.slice(0, 4))
  const month = parseInt(period.slice(5, 7))
  const lastDay = new Date(year, month, 0).getDate()
  const day = Math.min(paymentDay, lastDay)
  return `${period}-${String(day).padStart(2, '0')}`
}

function PaymentsView({ contract, onBack, onPaymentMutation, targetPeriod }) {
  const [payments, setPayments] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  // null | { type: 'create' } | { type: 'update', payment }
  const [activeForm, setActiveForm] = useState(null)
  const [formError, setFormError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Main "Marcar pagado hoy" action state
  const [isRegistering, setIsRegistering] = useState(false)
  const [registerError, setRegisterError] = useState(null)

  // Manual creation form fields
  const [period, setPeriod] = useState(currentPeriod())
  const [createComment, setCreateComment] = useState('')

  // Edit form fields
  const [paidAmount, setPaidAmount] = useState('')
  const [paidAt, setPaidAt] = useState('')
  const [updateComment, setUpdateComment] = useState('')

  async function loadPayments() {
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/contracts/${contract.id}/payments`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setPayments(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadPayments()
  }, [contract.id])

  const thisPeriod = targetPeriod ?? currentPeriod()
  const currentPayment = payments.find((p) => p.period === thisPeriod)

  // Main action: POST period if missing, then PATCH with full amount + today.
  async function registerCurrentPeriod() {
    setIsRegistering(true)
    setRegisterError(null)
    const today = todayLocal()

    try {
      let paymentId
      let expectedAmount

      if (!currentPayment) {
        const postRes = await fetch(`${API_BASE}/contracts/${contract.id}/payments`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ period: thisPeriod }),
        })
        if (!postRes.ok) throw new Error(`Error ${postRes.status}`)
        const created = await postRes.json()
        paymentId = created.id
        expectedAmount = created.expected_amount
      } else {
        paymentId = currentPayment.id
        expectedAmount = currentPayment.expected_amount
      }

      const patchRes = await fetch(`${API_BASE}/payments/${paymentId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paid_amount: expectedAmount, paid_at: today }),
      })

      if (!patchRes.ok) {
        // Period was created but could not be marked as paid.
        setRegisterError(
          'Se creó el período, pero no se pudo marcar como pagado. Puedes editarlo abajo.'
        )
        await loadPayments()
        await onPaymentMutation?.()
        return
      }

      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setRegisterError(err.message)
    } finally {
      setIsRegistering(false)
    }
  }

  function openCreate() {
    setPeriod(nextMissingPeriod(payments))
    setCreateComment('')
    setFormError(null)
    setActiveForm({ type: 'create' })
  }

  function openUpdate(payment) {
    // Pre-fill with expected_amount (editable) and today if no paid_at recorded.
    setPaidAmount(String(payment.expected_amount))
    setPaidAt(payment.paid_at ?? todayLocal())
    setUpdateComment(payment.comment ?? '')
    setFormError(null)
    setActiveForm({ type: 'update', payment })
  }

  function cancelForm() {
    setActiveForm(null)
    setFormError(null)
  }

  async function handleCreate(e) {
    e.preventDefault()
    setIsSubmitting(true)
    setFormError(null)
    try {
      const res = await fetch(`${API_BASE}/contracts/${contract.id}/payments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ period, comment: createComment || null }),
      })
      if (res.status === 409) {
        setFormError(`Ya existe un pago para el período ${period}.`)
        return
      }
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setActiveForm(null)
      setFormError(null)
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
      if (res.status === 404) {
        setRegisterError('El pago ya no existe.')
        return
      }
      if (!res.ok) throw new Error(`Error ${res.status}`)
      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setRegisterError(err.message)
    }
  }

  async function handleUpdate(e) {
    e.preventDefault()
    setIsSubmitting(true)
    setFormError(null)
    try {
      const body = {}
      if (paidAmount !== '') body.paid_amount = Number(paidAmount)
      if (paidAt !== '') body.paid_at = paidAt
      if (updateComment !== '') body.comment = updateComment

      const res = await fetch(`${API_BASE}/payments/${activeForm.payment.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setActiveForm(null)
      setFormError(null)
      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  const showCard = !isLoading && !error

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

        {/* Período actual — acción principal */}
        {showCard && (
          <div className="current-period-card">
            <div className="current-period-meta">
              <span className="current-period-label">Período a registrar</span>
              <span className="current-period-value">{thisPeriod}</span>
              <span className="payment-info-sep">·</span>
              <span className="current-period-detail">
                Vence: {currentPayment?.due_date ?? deriveDueDate(thisPeriod, contract.payment_day)}
              </span>
              <span className="payment-info-sep">·</span>
              <span className="current-period-detail">
                Esperado: {formatCLP(currentPayment?.expected_amount ?? contract.current_rent)}
              </span>
              {currentPayment && (
                <>
                  <span className="payment-info-sep">·</span>
                  <PaymentBadge status={currentPayment.status} />
                </>
              )}
            </div>

            <div className="current-period-actions">
              {(!currentPayment || currentPayment.status === 'pending') && (
                <button
                  className="btn-primary"
                  onClick={registerCurrentPeriod}
                  disabled={isRegistering}
                >
                  {isRegistering ? 'Registrando…' : 'Registrar pago completo'}
                </button>
              )}
              {currentPayment && (
                <button
                  className="btn-payments"
                  onClick={() => openUpdate(currentPayment)}
                >
                  Editar
                </button>
              )}
            </div>

            {registerError && (
              <div className="payment-form-error">{registerError}</div>
            )}
          </div>
        )}

        {/* Formulario de edición */}
        {activeForm?.type === 'update' && (
          <form className="payment-form" onSubmit={handleUpdate}>
            <div className="payment-form-row">
              <label className="payment-form-label">
                Monto pagado
                <input
                  className="payment-form-input"
                  type="number"
                  min="0"
                  value={paidAmount}
                  onChange={(e) => setPaidAmount(e.target.value)}
                  placeholder="ej. 500000"
                />
              </label>
              <label className="payment-form-label">
                Fecha pago
                <input
                  className="payment-form-input"
                  type="date"
                  value={paidAt}
                  onChange={(e) => setPaidAt(e.target.value)}
                />
              </label>
              <label className="payment-form-label">
                Nota
                <input
                  className="payment-form-input"
                  type="text"
                  value={updateComment}
                  onChange={(e) => setUpdateComment(e.target.value)}
                  placeholder="opcional"
                />
              </label>
              <div className="payment-form-actions">
                <button className="btn-primary" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? 'Guardando…' : 'Guardar'}
                </button>
                <button className="btn-secondary" type="button" onClick={cancelForm}>
                  Cancelar
                </button>
              </div>
            </div>
            {formError && <div className="payment-form-error">{formError}</div>}
          </form>
        )}

        {/* Formulario manual de creación (flujo secundario) */}
        {activeForm?.type === 'create' && (
          <form className="payment-form" onSubmit={handleCreate}>
            <div className="payment-form-row">
              <label className="payment-form-label">
                Período
                <input
                  className="payment-form-input"
                  type="text"
                  value={period}
                  onChange={(e) => setPeriod(e.target.value)}
                  placeholder="ej. 2025-04"
                  required
                />
              </label>
              <label className="payment-form-label">
                Nota
                <input
                  className="payment-form-input"
                  type="text"
                  value={createComment}
                  onChange={(e) => setCreateComment(e.target.value)}
                  placeholder="opcional"
                />
              </label>
              <div className="payment-form-actions">
                <button className="btn-primary" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? 'Creando…' : 'Crear'}
                </button>
                <button className="btn-secondary" type="button" onClick={cancelForm}>
                  Cancelar
                </button>
              </div>
            </div>
            {formError && <div className="payment-form-error">{formError}</div>}
          </form>
        )}

        {/* Loading / error */}
        {isLoading && <div className="app-loading">Cargando pagos…</div>}
        {!isLoading && error && <div className="app-error">Error al cargar: {error}</div>}

        {/* Empty state */}
        {!isLoading && !error && payments.length === 0 && (
          <div className="payment-empty">
            <p className="payment-empty-text">Sin pagos registrados para este contrato.</p>
            {!activeForm && (
              <button className="btn-link-secondary" onClick={openCreate}>
                + Agregar período manual
              </button>
            )}
          </div>
        )}

        {/* Tabla de historial */}
        {!isLoading && !error && payments.length > 0 && (
          <div className="table-scroll">
            <div className="table-wrapper">
              {!activeForm && (
                <div className="payment-table-header">
                  <button className="btn-link-secondary" onClick={openCreate}>
                    + Agregar período manual
                  </button>
                </div>
              )}
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
                    <th className="th">Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {payments.map((p) => (
                    <tr key={p.id} className="table-row-static">
                      <td className="td td-mono">{p.period}</td>
                      <td className="td td-mono td-muted">{p.due_date}</td>
                      <td className="td td-right td-mono">
                        {formatCLP(p.expected_amount)}
                      </td>
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
                        <button
                          className="btn-payments"
                          onClick={() => openUpdate(p)}
                        >
                          Editar
                        </button>
                        {' '}
                        <button
                          className="btn-payments-danger"
                          onClick={() => handleDelete(p)}
                        >
                          Eliminar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="table-footer">
                <span>
                  {payments.length} período{payments.length !== 1 ? 's' : ''}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  )
}

export default PaymentsView
