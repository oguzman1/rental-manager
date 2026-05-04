import { useEffect, useState } from 'react'
import Topbar from './Topbar'
import { formatCLP, formatAmountInput, parseAmountInput } from './utils'

const API_BASE = 'http://127.0.0.1:8000'

function RentChangesView({ contract, onBack, onDataMutation, autoOpenForm }) {
  const [items, setItems] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const [showForm, setShowForm] = useState(autoOpenForm)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formError, setFormError] = useState(null)

  const [fDate, setFDate] = useState(
    autoOpenForm ? (contract.next_adjustment_date ?? contract.start_date ?? '') : ''
  )
  const [fAmount, setFAmount] = useState('')
  const [fPct, setFPct] = useState('')
  const [fComment, setFComment] = useState('')

  async function loadHistory() {
    try {
      const res = await fetch(`${API_BASE}/contracts/${contract.contract_id}/rent-changes`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setItems(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    async function init() {
      try {
        const res = await fetch(`${API_BASE}/contracts/${contract.contract_id}/rent-changes`)
        if (!res.ok) throw new Error(`Error ${res.status}`)
        setItems(await res.json())
      } catch (err) {
        setError(err.message)
      } finally {
        setIsLoading(false)
      }
    }
    init()
  }, [contract.contract_id])

  function openForm() {
    setFDate(contract.next_adjustment_date ?? contract.start_date ?? '')
    setFAmount('')
    setFPct('')
    setFComment('')
    setFormError(null)
    setShowForm(true)
  }

  function cancelForm() {
    setShowForm(false)
    setFormError(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setIsSubmitting(true)
    setFormError(null)
    try {
      const body = {
        effective_from: fDate,
        amount: parseAmountInput(fAmount),
        adjustment_pct: fPct.trim() ? parseFloat(fPct) : null,
        comment: fComment.trim() || null,
      }
      const res = await fetch(
        `${API_BASE}/contracts/${contract.contract_id}/rent-changes`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      )
      if (!res.ok) {
        const data = await res.json()
        setFormError(data.detail ?? `Error ${res.status}`)
        return
      }
      setShowForm(false)
      await loadHistory()
      await onDataMutation?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleDelete(rcId) {
    if (!window.confirm('¿Eliminar este reajuste?')) return
    try {
      const res = await fetch(`${API_BASE}/rent-changes/${rcId}`, { method: 'DELETE' })
      if (!res.ok) {
        const data = await res.json()
        alert(data.detail ?? `Error ${res.status}`)
        return
      }
      await loadHistory()
      await onDataMutation?.()
    } catch (err) {
      alert(`Error al eliminar: ${err.message}`)
    }
  }

  return (
    <>
      <Topbar
        title="Historial de reajustes"
        breadcrumb={['Reajustes', contract.property_label ?? contract.rol]}
        onBack={onBack}
        actions={
          !showForm ? (
            <button className="btn-primary" onClick={openForm}>
              + Aplicar reajuste
            </button>
          ) : (
            <button className="btn-secondary" onClick={cancelForm}>
              Cancelar
            </button>
          )
        }
      />
      <div className="page-body">
        {showForm && (
          <div className="form-scroll">
            <form onSubmit={handleSubmit}>
              <div className="form-section-label">Nuevo reajuste</div>
              {contract.current_rent != null && (
                <div className="rent-change-current">
                  Renta actual: {formatCLP(contract.current_rent)}
                </div>
              )}
              <div className="payment-form-row">
                <label className="payment-form-label">
                  Fecha efectiva *
                  <input
                    className="payment-form-input"
                    type="date"
                    value={fDate}
                    onChange={(e) => setFDate(e.target.value)}
                    required
                  />
                </label>
                <label className="payment-form-label">
                  Monto *
                  <input
                    className="payment-form-input"
                    type="text"
                    inputMode="numeric"
                    value={fAmount}
                    onChange={(e) => setFAmount(formatAmountInput(e.target.value))}
                    required
                    placeholder="ej. 750.000"
                  />
                </label>
                <label className="payment-form-label">
                  % reajuste
                  <input
                    className="payment-form-input"
                    type="number"
                    step="0.01"
                    value={fPct}
                    onChange={(e) => setFPct(e.target.value)}
                    placeholder="ej. 5.2"
                    style={{ maxWidth: 100 }}
                  />
                </label>
                <label className="payment-form-label">
                  Comentario
                  <input
                    className="payment-form-input"
                    type="text"
                    value={fComment}
                    onChange={(e) => setFComment(e.target.value)}
                    placeholder="opcional"
                    style={{ minWidth: 200 }}
                  />
                </label>
              </div>
              <div className="payment-form-actions" style={{ marginTop: 16 }}>
                <button className="btn-primary" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? 'Guardando…' : 'Guardar reajuste'}
                </button>
              </div>
              {formError && <div className="payment-form-error">{formError}</div>}
            </form>
          </div>
        )}

        {isLoading && <div className="app-loading">Cargando historial…</div>}
        {error && <div className="app-error">Error al cargar: {error}</div>}
        {!isLoading && !error && (
          <div className="table-scroll">
            <div className="table-wrapper">
              <table className="dashboard-table">
                <thead>
                  <tr>
                    <th className="th">Fecha efectiva</th>
                    <th className="th th-right">Monto</th>
                    <th className="th th-right">% reajuste</th>
                    <th className="th">Comentario</th>
                    <th className="th">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, index) => (
                    <tr key={item.id} className="table-row">
                      <td className="td td-mono">{item.effective_from}</td>
                      <td className="td td-right td-mono">{formatCLP(item.amount)}</td>
                      <td className="td td-right td-mono">
                        {item.adjustment_pct != null
                          ? `${item.adjustment_pct}%`
                          : <span className="text-muted">—</span>}
                      </td>
                      <td className="td td-muted">
                        {item.comment ?? <span className="text-muted">—</span>}
                      </td>
                      <td className="td">
                        {index === 0 && items.length > 1 && (
                          <button
                            className="btn-payments-danger"
                            onClick={() => handleDelete(item.id)}
                          >
                            Eliminar
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="table-footer">
                <span>{items.length} entradas</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  )
}

export default RentChangesView
