import { useEffect, useState } from 'react'
import Topbar from './Topbar'
import { formatCLP, formatMonthsAgo, formatTenancyYears } from './utils'

const API_BASE = 'http://127.0.0.1:8000'

function TenantsPage({ onPropertySelect, onDataMutation }) {
  const [items, setItems] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  // null | { type: 'create' } | { type: 'edit', id }
  const [activeForm, setActiveForm] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formError, setFormError] = useState(null)

  // form fields
  const [fName, setFName] = useState('')
  const [fType, setFType] = useState('')
  const [fTaxId, setFTaxId] = useState('')
  const [fEmail, setFEmail] = useState('')
  const [fPhone, setFPhone] = useState('')
  const [fNotes, setFNotes] = useState('')

  async function loadTenants() {
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/tenants`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setItems(await res.json())
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
        const res = await fetch(`${API_BASE}/tenants`)
        if (!res.ok) throw new Error(`Error ${res.status}`)
        setItems(await res.json())
      } catch (err) {
        setError(err.message)
      } finally {
        setIsLoading(false)
      }
    }
    onMount()
  }, [])

  function resetFormFields() {
    setFName(''); setFType(''); setFTaxId('')
    setFEmail(''); setFPhone(''); setFNotes('')
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
      const res = await fetch(`${API_BASE}/tenants/${id}`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      const data = await res.json()
      setFName(data.display_name ?? '')
      setFType(data.tenant_type ?? '')
      setFTaxId(data.tax_id ?? '')
      setFEmail(data.email ?? '')
      setFPhone(data.phone ?? '')
      setFNotes(data.notes ?? '')
    } catch (err) {
      setFormError(`Error al cargar arrendatario: ${err.message}`)
    }
  }

  function cancelForm() {
    setActiveForm(null)
    setFormError(null)
  }

  function buildPayload() {
    return {
      display_name: fName.trim(),
      tenant_type: fType.trim() || null,
      tax_id: fTaxId.trim() || null,
      email: fEmail.trim() || null,
      phone: fPhone.trim() || null,
      notes: fNotes.trim() || null,
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setIsSubmitting(true)
    setFormError(null)
    const isEdit = activeForm.type === 'edit'
    const url = isEdit
      ? `${API_BASE}/tenants/${activeForm.id}`
      : `${API_BASE}/tenants`
    try {
      const res = await fetch(url, {
        method: isEdit ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload()),
      })
      if (!res.ok) {
        const body = await res.json()
        setFormError(body.detail ?? `Error ${res.status}`)
        return
      }
      setActiveForm(null)
      await loadTenants()
      await onDataMutation?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleDelete(id, name) {
    if (!window.confirm(`¿Eliminar el arrendatario "${name}"?\nEsta acción no se puede deshacer.`))
      return
    try {
      const res = await fetch(`${API_BASE}/tenants/${id}`, { method: 'DELETE' })
      if (res.status === 409) {
        const body = await res.json()
        alert(body.detail)
        return
      }
      if (!res.ok) throw new Error(`Error ${res.status}`)
      await loadTenants()
      await onDataMutation?.()
    } catch (err) {
      alert(`Error al eliminar: ${err.message}`)
    }
  }

  return (
    <>
      <Topbar
        title="Arrendatarios"
        breadcrumb={['Arrendatarios']}
        actions={
          !activeForm
            ? <button className="btn-primary" onClick={openCreate}>+ Nuevo arrendatario</button>
            : <button className="btn-secondary" onClick={cancelForm}>Cancelar</button>
        }
      />
      <div className="page-body">
        {activeForm ? (
          <div className="form-scroll">
            <form onSubmit={handleSubmit}>
              <div className="form-section-label">
                {activeForm.type === 'create' ? 'Nuevo arrendatario' : 'Editar arrendatario'}
              </div>
              <div className="payment-form-row">
                <label className="payment-form-label">
                  Nombre *
                  <input
                    className="payment-form-input"
                    type="text"
                    value={fName}
                    onChange={(e) => setFName(e.target.value)}
                    required
                    autoFocus
                    placeholder="Nombre completo"
                    style={{ minWidth: 200 }}
                  />
                </label>
                <label className="payment-form-label">
                  Tipo
                  <input
                    className="payment-form-input"
                    type="text"
                    value={fType}
                    onChange={(e) => setFType(e.target.value)}
                    placeholder="ej. Persona natural"
                  />
                </label>
                <label className="payment-form-label">
                  RUT / ID tributario
                  <input
                    className="payment-form-input"
                    type="text"
                    value={fTaxId}
                    onChange={(e) => setFTaxId(e.target.value)}
                    placeholder="ej. 12.345.678-9"
                  />
                </label>
              </div>
              <div className="payment-form-row" style={{ marginTop: 10 }}>
                <label className="payment-form-label">
                  Email
                  <input
                    className="payment-form-input"
                    type="email"
                    value={fEmail}
                    onChange={(e) => setFEmail(e.target.value)}
                    placeholder="correo@ejemplo.com"
                  />
                </label>
                <label className="payment-form-label">
                  Teléfono
                  <input
                    className="payment-form-input"
                    type="text"
                    value={fPhone}
                    onChange={(e) => setFPhone(e.target.value)}
                    placeholder="ej. +56 9 1234 5678"
                  />
                </label>
                <label className="payment-form-label">
                  Notas
                  <input
                    className="payment-form-input"
                    type="text"
                    value={fNotes}
                    onChange={(e) => setFNotes(e.target.value)}
                    placeholder="opcional"
                    style={{ minWidth: 200 }}
                  />
                </label>
              </div>
              <div className="payment-form-actions" style={{ marginTop: 20 }}>
                <button className="btn-primary" type="submit" disabled={isSubmitting}>
                  {isSubmitting
                    ? 'Guardando…'
                    : activeForm.type === 'create' ? 'Crear arrendatario' : 'Guardar cambios'}
                </button>
              </div>
              {formError && <div className="payment-form-error">{formError}</div>}
            </form>
          </div>
        ) : (
          <>
            {isLoading && <div className="app-loading">Cargando arrendatarios…</div>}
            {!isLoading && error && <div className="app-error">Error al cargar: {error}</div>}
            {!isLoading && !error && items.length === 0 && (
              <div className="payment-empty">
                <p className="payment-empty-text">Sin arrendatarios registrados.</p>
              </div>
            )}
            {!isLoading && !error && items.length > 0 && (
              <div className="table-scroll">
                <div className="table-wrapper">
                  <table className="dashboard-table">
                    <thead>
                      <tr>
                        <th className="th">Arrendatario</th>
                        <th className="th">Propiedad</th>
                        <th className="th">Desde</th>
                        <th className="th">Últ. reajuste</th>
                        <th className="th th-right">Renta</th>
                        <th className="th th-center">Día pago</th>
                        <th className="th">Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) => (
                        <tr
                          key={item.id}
                          className="table-row"
                          onClick={() =>
                            item.property_id && onPropertySelect && onPropertySelect(item.property_id)
                          }
                        >
                          <td className="td">{item.display_name}</td>
                          <td className="td">
                            {item.property_label ? (
                              <>
                                <div>{item.property_label}</div>
                                <div className="td-sub">{item.rol}</div>
                              </>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </td>
                          <td className="td td-mono td-muted">
                            <div>{item.start_date ?? '—'}</div>
                            {item.tenancy_years != null && (
                              <div className="td-sub">
                                {formatTenancyYears(item.tenancy_years)}
                              </div>
                            )}
                          </td>
                          <td className="td td-mono td-muted">
                            <div>{item.last_adjustment_date ?? '—'}</div>
                            {item.last_adjustment_date && (
                              <div className="td-sub">
                                {formatMonthsAgo(item.months_since_last_adjustment)}
                              </div>
                            )}
                          </td>
                          <td className="td td-right td-mono">
                            {item.current_rent != null
                              ? formatCLP(item.current_rent)
                              : <span className="text-muted">—</span>}
                          </td>
                          <td className="td td-center td-mono">
                            {item.payment_day ?? <span className="text-muted">—</span>}
                          </td>
                          <td className="td" onClick={(e) => e.stopPropagation()}>
                            <button
                              className="btn-payments"
                              onClick={() => openEdit(item.id)}
                            >
                              Editar
                            </button>
                            {' '}
                            <button
                              className="btn-payments-danger"
                              onClick={() => handleDelete(item.id, item.display_name)}
                            >
                              Eliminar
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="table-footer">
                    <span>{items.length} arrendatarios</span>
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

export default TenantsPage
