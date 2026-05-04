import { useEffect, useState } from 'react'
import Topbar from './Topbar'
import { StatusBadge } from './Badge'
import { formatAmountInput, parseAmountInput } from './utils'

const API_BASE = 'http://127.0.0.1:8000'

const MONTHS = [
  'january', 'february', 'march', 'april', 'may', 'june',
  'july', 'august', 'september', 'october', 'november', 'december',
]

const MONTHS_ES = {
  january: 'Enero', february: 'Febrero', march: 'Marzo', april: 'Abril',
  may: 'Mayo', june: 'Junio', july: 'Julio', august: 'Agosto',
  september: 'Septiembre', october: 'Octubre', november: 'Noviembre', december: 'Diciembre',
}

function PropertiesPage({ onPropertySelect, onDataMutation }) {
  const [properties, setProperties] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchText, setSearchText] = useState('')

  // null | { type: 'create' } | { type: 'edit', id }
  const [activeForm, setActiveForm] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formError, setFormError] = useState(null)

  // --- property fields ---
  const [fRol, setFRol] = useState('')
  const [fComuna, setFComuna] = useState('')
  const [fAddress, setFAddress] = useState('')
  const [fDestination, setFDestination] = useState('')
  const [fStatus, setFStatus] = useState('vacant')
  const [fFojas, setFFojas] = useState('')
  const [fPropertyNumber, setFPropertyNumber] = useState('')
  const [fYear, setFYear] = useState('')
  const [fFiscalAppraisal, setFFiscalAppraisal] = useState('')

  // --- rental fields (only when status = 'occupied') ---
  const [fPropertyLabel, setFPropertyLabel] = useState('')
  const [fTenantName, setFTenantName] = useState('')
  const [fPaymentDay, setFPaymentDay] = useState('')
  const [fCurrentRent, setFCurrentRent] = useState('')
  const [fAdjFreq, setFAdjFreq] = useState('annual')
  const [fStartDate, setFStartDate] = useState('')
  const [fNoticeDays, setFNoticeDays] = useState('30')
  const [fAdjMonth, setFAdjMonth] = useState('january')

  async function loadProperties() {
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/managed-properties`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setProperties(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    async function onMount() {
      setIsLoading(true)
      setError(null)
      try {
        const res = await fetch(`${API_BASE}/managed-properties`)
        if (!res.ok) throw new Error(`Error ${res.status}`)
        setProperties(await res.json())
      } catch (err) {
        setError(err.message)
      } finally {
        setIsLoading(false)
      }
    }
    onMount()
  }, [])

  function resetFormFields() {
    setFRol(''); setFComuna(''); setFAddress(''); setFDestination('')
    setFStatus('vacant'); setFFojas(''); setFPropertyNumber('')
    setFYear(''); setFFiscalAppraisal('')
    setFPropertyLabel(''); setFTenantName('')
    setFPaymentDay(''); setFCurrentRent('')
    setFAdjFreq('annual'); setFStartDate('')
    setFNoticeDays('30'); setFAdjMonth('january')
    setFormError(null)
  }

  function openCreate() {
    resetFormFields()
    setActiveForm({ type: 'create' })
  }

  async function openEdit(id) {
    resetFormFields()
    setActiveForm({ type: 'edit', id })
    try {
      const res = await fetch(`${API_BASE}/managed-property/${id}`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      const data = await res.json()
      const p = data.property
      const r = data.rental
      setFRol(p.rol ?? '')
      setFComuna(p.comuna ?? '')
      setFAddress(p.address ?? '')
      setFDestination(p.destination ?? '')
      setFStatus(p.status ?? 'vacant')
      setFFojas(p.fojas ?? '')
      setFPropertyNumber(p.property_number ?? '')
      setFYear(p.year != null ? String(p.year) : '')
      setFFiscalAppraisal(p.fiscal_appraisal != null ? String(p.fiscal_appraisal) : '')
      if (r) {
        setFPropertyLabel(r.property_label ?? '')
        setFTenantName(r.tenant_name ?? '')
        setFPaymentDay(r.payment_day != null ? String(r.payment_day) : '')
        setFCurrentRent(r.current_rent != null ? formatAmountInput(r.current_rent) : '')
        setFAdjFreq(r.adjustment_frequency ?? 'annual')
        setFStartDate(r.start_date ?? '')
        setFNoticeDays(r.notice_days != null ? String(r.notice_days) : '30')
        setFAdjMonth(r.adjustment_month ?? 'january')
      }
    } catch (err) {
      setFormError(`Error al cargar propiedad: ${err.message}`)
    }
  }

  function cancelForm() {
    setActiveForm(null)
    setFormError(null)
  }

  function buildPayload() {
    return {
      property: {
        rol: fRol.trim(),
        comuna: fComuna.trim(),
        address: fAddress.trim(),
        destination: fDestination.trim(),
        status: fStatus,
        fojas: fFojas.trim() || null,
        property_number: fPropertyNumber.trim() || null,
        year: fYear ? parseInt(fYear) : null,
        fiscal_appraisal: fFiscalAppraisal ? parseInt(fFiscalAppraisal) : null,
      },
      rental: fStatus === 'occupied' ? {
        property_label: fPropertyLabel.trim(),
        tenant_name: fTenantName.trim(),
        payment_day: parseInt(fPaymentDay),
        current_rent: parseAmountInput(fCurrentRent),
        adjustment_frequency: fAdjFreq,
        start_date: fStartDate,
        notice_days: parseInt(fNoticeDays),
        adjustment_month: fAdjMonth,
      } : null,
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setIsSubmitting(true)
    setFormError(null)
    const isEdit = activeForm.type === 'edit'
    const url = isEdit
      ? `${API_BASE}/managed-property/${activeForm.id}`
      : `${API_BASE}/managed-property`
    try {
      const res = await fetch(url, {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload()),
      })
      if (res.status === 409) {
        setFormError('Ya existe una propiedad con ese ROL.')
        return
      }
      if (res.status === 400) {
        const body = await res.json()
        setFormError(body.detail ?? 'Error de validación.')
        return
      }
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setActiveForm(null)
      await loadProperties()
      await onDataMutation?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleDelete(id, label) {
    if (!window.confirm(`¿Eliminar "${label}"?\nSe eliminarán también sus contratos, reajustes y pagos.`)) return
    try {
      const res = await fetch(`${API_BASE}/managed-property/${id}`, { method: 'DELETE' })
      if (res.status === 404) { await loadProperties(); return }
      if (!res.ok) throw new Error(`Error ${res.status}`)
      await loadProperties()
      await onDataMutation?.()
    } catch (err) {
      alert(`Error al eliminar: ${err.message}`)
    }
  }

  const filtered = properties.filter((p) => {
    if (!searchText) return true
    const q = searchText.toLowerCase()
    return (
      p.rol.toLowerCase().includes(q) ||
      p.comuna.toLowerCase().includes(q) ||
      (p.property_label ?? '').toLowerCase().includes(q) ||
      (p.tenant_name ?? '').toLowerCase().includes(q)
    )
  })

  return (
    <>
      <Topbar
        title="Propiedades"
        breadcrumb={['Propiedades']}
        actions={
          !activeForm
            ? <button className="btn-primary" onClick={openCreate}>+ Nueva propiedad</button>
            : <button className="btn-secondary" onClick={cancelForm}>Cancelar</button>
        }
      />
      <div className="page-body">
        {activeForm ? (
          <div className="form-scroll">
            <form onSubmit={handleSubmit}>
              <div className="form-section-label">Datos de inventario</div>
              <div className="payment-form-row">
                <label className="payment-form-label">
                  ROL *
                  <input
                    className="payment-form-input" type="text" value={fRol}
                    onChange={(e) => setFRol(e.target.value)} required
                    placeholder="ej. 02162-00036"
                  />
                </label>
                <label className="payment-form-label">
                  Comuna *
                  <input
                    className="payment-form-input" type="text" value={fComuna}
                    onChange={(e) => setFComuna(e.target.value)} required
                    placeholder="ej. LA SERENA"
                  />
                </label>
                <label className="payment-form-label">
                  Dirección *
                  <input
                    className="payment-form-input" type="text" value={fAddress}
                    onChange={(e) => setFAddress(e.target.value)} required
                    placeholder="ej. Av. Balmaceda 1234"
                    style={{ minWidth: 200 }}
                  />
                </label>
                <label className="payment-form-label">
                  Destino *
                  <input
                    className="payment-form-input" type="text" value={fDestination}
                    onChange={(e) => setFDestination(e.target.value)} required
                    placeholder="ej. HABITACIONAL"
                  />
                </label>
                <label className="payment-form-label">
                  Estado *
                  <select
                    className="payment-form-input" value={fStatus}
                    onChange={(e) => setFStatus(e.target.value)}
                  >
                    <option value="vacant">Vacante</option>
                    <option value="occupied">Arrendado</option>
                  </select>
                </label>
              </div>
              <div className="payment-form-row" style={{ marginTop: 10 }}>
                <label className="payment-form-label">
                  Fojas
                  <input
                    className="payment-form-input" type="text" value={fFojas}
                    onChange={(e) => setFFojas(e.target.value)} placeholder="opcional"
                  />
                </label>
                <label className="payment-form-label">
                  N° propiedad
                  <input
                    className="payment-form-input" type="text" value={fPropertyNumber}
                    onChange={(e) => setFPropertyNumber(e.target.value)} placeholder="opcional"
                  />
                </label>
                <label className="payment-form-label">
                  Año
                  <input
                    className="payment-form-input" type="number" value={fYear}
                    onChange={(e) => setFYear(e.target.value)} placeholder="opcional"
                  />
                </label>
                <label className="payment-form-label">
                  Avalúo fiscal
                  <input
                    className="payment-form-input" type="number" value={fFiscalAppraisal}
                    onChange={(e) => setFFiscalAppraisal(e.target.value)} placeholder="opcional"
                  />
                </label>
              </div>

              {fStatus === 'occupied' && (
                <>
                  <div className="form-section-label" style={{ marginTop: 20 }}>Datos de arriendo</div>
                  <div className="payment-form-row">
                    <label className="payment-form-label">
                      Nombre propiedad *
                      <input
                        className="payment-form-input" type="text" value={fPropertyLabel}
                        onChange={(e) => setFPropertyLabel(e.target.value)} required
                        placeholder="ej. depto serena"
                      />
                    </label>
                    <label className="payment-form-label">
                      Arrendatario *
                      <input
                        className="payment-form-input" type="text" value={fTenantName}
                        onChange={(e) => setFTenantName(e.target.value)} required
                        placeholder="Nombre completo" style={{ minWidth: 160 }}
                      />
                    </label>
                    <label className="payment-form-label">
                      Día pago *
                      <input
                        className="payment-form-input" type="number" min="1" max="31"
                        value={fPaymentDay} onChange={(e) => setFPaymentDay(e.target.value)}
                        required placeholder="ej. 5"
                      />
                    </label>
                    <label className="payment-form-label">
                      Renta mensual *
                      <input
                        className="payment-form-input" type="text" inputMode="numeric"
                        value={fCurrentRent} onChange={(e) => setFCurrentRent(formatAmountInput(e.target.value))}
                        required placeholder="ej. 500.000"
                      />
                    </label>
                  </div>
                  <div className="payment-form-row" style={{ marginTop: 10 }}>
                    <label className="payment-form-label">
                      Reajuste *
                      <select
                        className="payment-form-input" value={fAdjFreq}
                        onChange={(e) => setFAdjFreq(e.target.value)}
                      >
                        <option value="annual">Anual</option>
                        <option value="semiannual">Semestral</option>
                      </select>
                    </label>
                    <label className="payment-form-label">
                      Mes reajuste *
                      <select
                        className="payment-form-input" value={fAdjMonth}
                        onChange={(e) => setFAdjMonth(e.target.value)}
                      >
                        {MONTHS.map((m) => (
                          <option key={m} value={m}>{MONTHS_ES[m]}</option>
                        ))}
                      </select>
                    </label>
                    <label className="payment-form-label">
                      Inicio contrato *
                      <input
                        className="payment-form-input" type="date" value={fStartDate}
                        onChange={(e) => setFStartDate(e.target.value)} required
                      />
                    </label>
                    <label className="payment-form-label">
                      Días aviso *
                      <input
                        className="payment-form-input" type="number" min="0"
                        value={fNoticeDays} onChange={(e) => setFNoticeDays(e.target.value)}
                        required placeholder="ej. 30"
                      />
                    </label>
                  </div>
                </>
              )}

              <div className="payment-form-actions" style={{ marginTop: 20 }}>
                <button className="btn-primary" type="submit" disabled={isSubmitting}>
                  {isSubmitting
                    ? 'Guardando…'
                    : activeForm.type === 'create' ? 'Crear propiedad' : 'Guardar cambios'}
                </button>
              </div>
              {formError && <div className="payment-form-error">{formError}</div>}
            </form>
          </div>
        ) : (
          <>
            <div className="table-filters">
              <div className="filter-chips">
                <div className="search-input-wrap">
                  <input
                    type="text"
                    placeholder="Buscar rol, comuna, propiedad…"
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                  />
                </div>
              </div>
              <span className="filters-count">
                {filtered.length} / {properties.length}
              </span>
            </div>

            {isLoading && <div className="app-loading">Cargando propiedades…</div>}
            {!isLoading && error && <div className="app-error">Error al cargar: {error}</div>}
            {!isLoading && !error && properties.length === 0 && (
              <div className="payment-empty">
                <p className="payment-empty-text">Sin propiedades registradas.</p>
              </div>
            )}
            {!isLoading && !error && properties.length > 0 && (
              <div className="table-scroll">
                <div className="table-wrapper">
                  <table className="dashboard-table">
                    <thead>
                      <tr>
                        <th className="th">Propiedad</th>
                        <th className="th">ROL</th>
                        <th className="th">Estado</th>
                        <th className="th">Arrendatario</th>
                        <th className="th th-center">Día pago</th>
                        <th className="th">Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((p) => (
                        <tr
                          key={p.id}
                          className="table-row"
                          onClick={() => onPropertySelect && onPropertySelect(p.id)}
                        >
                          <td className="td">
                            <div>{p.property_label ?? p.rol}</div>
                            <div className="td-sub">{p.comuna}</div>
                          </td>
                          <td className="td td-mono">{p.rol}</td>
                          <td className="td">
                            <StatusBadge status={p.status} />
                          </td>
                          <td className="td">
                            {p.tenant_name ?? <span className="text-muted">—</span>}
                          </td>
                          <td className="td td-center td-mono">
                            {p.payment_day ?? <span className="text-muted">—</span>}
                          </td>
                          <td className="td">
                            <button
                              className="btn-payments"
                              onClick={(e) => { e.stopPropagation(); openEdit(p.id) }}
                            >
                              Editar
                            </button>
                            {' '}
                            <button
                              className="btn-payments-danger"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleDelete(p.id, p.property_label ?? p.rol)
                              }}
                            >
                              Eliminar
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="table-footer">
                    <span>{properties.length} propiedades</span>
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

export default PropertiesPage
