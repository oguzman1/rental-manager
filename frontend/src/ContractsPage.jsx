import { useEffect, useState } from 'react'
import Topbar from './Topbar'
import { contractDuration, formatCLP, formatFrequency } from './utils'

const API_BASE = 'http://127.0.0.1:8000'

function ContractsPage({ onPropertySelect, onPaymentSelect, onDataMutation }) {
  const [items, setItems] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  // null | { type: 'create' } | { type: 'edit', id }
  const [activeForm, setActiveForm] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formError, setFormError] = useState(null)

  // select data for create form
  const [properties, setProperties] = useState([])
  const [tenants, setTenants] = useState([])

  // form fields
  const [fPropertyId, setFPropertyId] = useState('')
  const [fTenantId, setFTenantId] = useState('')
  const [fStartDate, setFStartDate] = useState('')
  const [fPaymentDay, setFPaymentDay] = useState('')
  const [fRent, setFRent] = useState('')
  const [fFrequency, setFFrequency] = useState('annual')
  const [fAdjMonth, setFAdjMonth] = useState('')
  const [fNoticeDays, setFNoticeDays] = useState('0')
  const [fComment, setFComment] = useState('')

  async function loadContracts() {
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/contracts`)
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
      setIsLoading(true)
      setError(null)
      try {
        const res = await fetch(`${API_BASE}/contracts`)
        if (!res.ok) throw new Error(`Error ${res.status}`)
        setItems(await res.json())
      } catch (err) {
        setError(err.message)
      } finally {
        setIsLoading(false)
      }
    }
    init()
  }, [])

  function resetFormFields() {
    setFPropertyId('')
    setFTenantId('')
    setFStartDate('')
    setFPaymentDay('')
    setFRent('')
    setFFrequency('annual')
    setFAdjMonth('')
    setFNoticeDays('0')
    setFComment('')
    setFormError(null)
  }

  async function openCreate() {
    resetFormFields()
    try {
      const [propRes, tenantRes] = await Promise.all([
        fetch(`${API_BASE}/managed-properties`),
        fetch(`${API_BASE}/tenants`),
      ])
      const allProps = propRes.ok ? await propRes.json() : []
      const allTenants = tenantRes.ok ? await tenantRes.json() : []
      setProperties(allProps.filter((p) => !p.has_rental))
      setTenants(allTenants)
    } catch {
      setProperties([])
      setTenants([])
    }
    setActiveForm({ type: 'create' })
  }

  async function openEdit(id) {
    resetFormFields()
    setActiveForm({ type: 'edit', id })
    try {
      const res = await fetch(`${API_BASE}/contracts/${id}`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      const data = await res.json()
      setFPaymentDay(String(data.payment_day))
      setFNoticeDays(String(data.notice_days))
      setFFrequency(data.adjustment_frequency)
      setFAdjMonth(data.adjustment_month ?? '')
      setFComment(data.comment ?? '')
    } catch (err) {
      setFormError(`Error al cargar contrato: ${err.message}`)
    }
  }

  function cancelForm() {
    setActiveForm(null)
    setFormError(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setIsSubmitting(true)
    setFormError(null)
    const isEdit = activeForm.type === 'edit'
    try {
      const res = isEdit
        ? await fetch(`${API_BASE}/contracts/${activeForm.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              payment_day: parseInt(fPaymentDay, 10),
              notice_days: parseInt(fNoticeDays, 10),
              adjustment_frequency: fFrequency,
              adjustment_month: fAdjMonth.trim() || null,
              comment: fComment.trim() || null,
            }),
          })
        : await fetch(`${API_BASE}/contracts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              property_id: parseInt(fPropertyId, 10),
              tenant_id: parseInt(fTenantId, 10),
              start_date: fStartDate,
              payment_day: parseInt(fPaymentDay, 10),
              notice_days: parseInt(fNoticeDays, 10),
              adjustment_frequency: fFrequency,
              adjustment_month: fAdjMonth.trim() || null,
              current_rent: parseInt(fRent, 10),
              comment: fComment.trim() || null,
            }),
          })

      if (!res.ok) {
        const body = await res.json()
        setFormError(body.detail ?? `Error ${res.status}`)
        return
      }
      setActiveForm(null)
      await loadContracts()
      await onDataMutation?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleClose(item) {
    const todayStr = new Date().toISOString().slice(0, 10)
    if (
      !window.confirm(
        `¿Cerrar contrato con ${item.tenant_name} (${item.property_label ?? item.rol})?\n` +
          `El historial de pagos se conservará. La propiedad quedará como vacante.`
      )
    )
      return

    try {
      const res = await fetch(`${API_BASE}/contracts/${item.id}/close`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ end_date: todayStr }),
      })
      if (!res.ok) {
        const body = await res.json()
        alert(body.detail ?? `Error ${res.status}`)
        return
      }
      await loadContracts()
      await onDataMutation?.()
    } catch (err) {
      alert(`Error al cerrar contrato: ${err.message}`)
    }
  }

  return (
    <>
      <Topbar
        title="Contratos"
        breadcrumb={['Contratos']}
        actions={
          !activeForm ? (
            <button className="btn-primary" onClick={openCreate}>
              + Nuevo contrato
            </button>
          ) : (
            <button className="btn-secondary" onClick={cancelForm}>
              Cancelar
            </button>
          )
        }
      />
      <div className="page-body">
        {activeForm ? (
          <div className="form-scroll">
            <form onSubmit={handleSubmit}>
              <div className="form-section-label">
                {activeForm.type === 'create' ? 'Nuevo contrato' : 'Editar contrato'}
              </div>

              {activeForm.type === 'create' && (
                <>
                  <div className="payment-form-row">
                    <label className="payment-form-label">
                      Propiedad *
                      <select
                        className="payment-form-input"
                        value={fPropertyId}
                        onChange={(e) => setFPropertyId(e.target.value)}
                        required
                      >
                        <option value="">Seleccionar propiedad</option>
                        {properties.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.property_label ?? p.rol} — {p.rol}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="payment-form-label">
                      Arrendatario *
                      <select
                        className="payment-form-input"
                        value={fTenantId}
                        onChange={(e) => setFTenantId(e.target.value)}
                        required
                      >
                        <option value="">Seleccionar arrendatario</option>
                        {tenants.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.display_name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="payment-form-row" style={{ marginTop: 10 }}>
                    <label className="payment-form-label">
                      Fecha inicio *
                      <input
                        className="payment-form-input"
                        type="date"
                        value={fStartDate}
                        onChange={(e) => setFStartDate(e.target.value)}
                        required
                      />
                    </label>
                    <label className="payment-form-label">
                      Renta inicial *
                      <input
                        className="payment-form-input"
                        type="number"
                        min="1"
                        value={fRent}
                        onChange={(e) => setFRent(e.target.value)}
                        required
                        placeholder="ej. 700000"
                      />
                    </label>
                  </div>
                </>
              )}

              <div className="payment-form-row" style={{ marginTop: 10 }}>
                <label className="payment-form-label">
                  Día de pago *
                  <input
                    className="payment-form-input"
                    type="number"
                    min="1"
                    max="31"
                    value={fPaymentDay}
                    onChange={(e) => setFPaymentDay(e.target.value)}
                    required
                    placeholder="ej. 5"
                    style={{ maxWidth: 80 }}
                  />
                </label>
                <label className="payment-form-label">
                  Días aviso *
                  <input
                    className="payment-form-input"
                    type="number"
                    min="0"
                    value={fNoticeDays}
                    onChange={(e) => setFNoticeDays(e.target.value)}
                    required
                    placeholder="ej. 60"
                    style={{ maxWidth: 80 }}
                  />
                </label>
                <label className="payment-form-label">
                  Reajuste *
                  <select
                    className="payment-form-input"
                    value={fFrequency}
                    onChange={(e) => setFFrequency(e.target.value)}
                    required
                  >
                    <option value="annual">Anual</option>
                    <option value="semiannual">Semestral</option>
                  </select>
                </label>
                <label className="payment-form-label">
                  Mes reajuste
                  <input
                    className="payment-form-input"
                    type="text"
                    value={fAdjMonth}
                    onChange={(e) => setFAdjMonth(e.target.value)}
                    placeholder="ej. march"
                  />
                </label>
              </div>

              <div className="payment-form-row" style={{ marginTop: 10 }}>
                <label className="payment-form-label">
                  Comentario
                  <input
                    className="payment-form-input"
                    type="text"
                    value={fComment}
                    onChange={(e) => setFComment(e.target.value)}
                    placeholder="opcional"
                    style={{ minWidth: 300 }}
                  />
                </label>
              </div>

              <div className="payment-form-actions" style={{ marginTop: 20 }}>
                <button className="btn-primary" type="submit" disabled={isSubmitting}>
                  {isSubmitting
                    ? 'Guardando…'
                    : activeForm.type === 'create'
                    ? 'Crear contrato'
                    : 'Guardar cambios'}
                </button>
              </div>
              {formError && <div className="payment-form-error">{formError}</div>}
            </form>
          </div>
        ) : (
          <>
            {isLoading && <div className="app-loading">Cargando contratos…</div>}
            {error && <div className="app-error">Error al cargar: {error}</div>}
            {!isLoading && !error && items.length === 0 && (
              <div className="payment-empty">
                <p className="payment-empty-text">Sin contratos activos.</p>
              </div>
            )}
            {!isLoading && !error && items.length > 0 && (
              <div className="table-scroll">
                <div className="table-wrapper">
                  <table className="dashboard-table">
                    <thead>
                      <tr>
                        <th className="th">Propiedad</th>
                        <th className="th">Arrendatario</th>
                        <th className="th">Inicio</th>
                        <th className="th th-right">Renta</th>
                        <th className="th th-center">Día pago</th>
                        <th className="th">Reajuste</th>
                        <th className="th">Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) => {
                        const dur = item.start_date ? contractDuration(item.start_date) : null
                        return (
                          <tr
                            key={item.id}
                            className="table-row"
                            onClick={() =>
                              onPropertySelect && onPropertySelect(item.property_id)
                            }
                          >
                            <td className="td">
                              <div>{item.property_label ?? item.rol}</div>
                              <div className="td-sub">{item.rol}</div>
                            </td>
                            <td className="td">
                              {item.tenant_name ?? <span className="text-muted">—</span>}
                            </td>
                            <td className="td td-mono td-muted">
                              {item.start_date ?? '—'}
                              {dur && <div className="td-sub">{dur}</div>}
                            </td>
                            <td className="td td-right td-mono">
                              {formatCLP(item.current_rent)}
                            </td>
                            <td className="td td-center td-mono">
                              {item.payment_day ?? <span className="text-muted">—</span>}
                            </td>
                            <td className="td td-muted">
                              {formatFrequency(item.adjustment_frequency)}
                            </td>
                            <td className="td" onClick={(e) => e.stopPropagation()}>
                              <button
                                className="btn-payments"
                                onClick={() => onPaymentSelect && onPaymentSelect(item)}
                              >
                                Ver pagos
                              </button>
                              {' '}
                              <button
                                className="btn-payments"
                                onClick={() => openEdit(item.id)}
                              >
                                Editar
                              </button>
                              {' '}
                              <button
                                className="btn-payments-danger"
                                onClick={() => handleClose(item)}
                              >
                                Cerrar contrato
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                  <div className="table-footer">
                    <span>{items.length} contratos activos</span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}

export default ContractsPage
