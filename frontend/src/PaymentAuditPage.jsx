import { useEffect, useRef, useState } from 'react'
import Topbar from './Topbar'
import { formatCLP, formatMonthShort } from './utils'

const API_BASE = 'http://127.0.0.1:8000'

const MONTH_STATUS_BADGE = {
  matched_registered: 'badge-ok',
  found_not_registered: 'badge-warn',
  missing: 'badge-danger',
}

const OVERALL_STATUS_BADGE = {
  matched_registered: 'badge-ok',
  found_not_registered: 'badge-warn',
  missing: 'badge-danger',
  no_data: 'badge-muted',
}

const OVERALL_STATUS_LABEL = {
  matched_registered: 'Al día',
  found_not_registered: 'Por confirmar',
  missing: 'Pagos faltantes',
  no_data: 'Sin datos',
}

function _contractLabel(f) {
  return f.property_label ?? `Contrato #${f.contract_id}`
}

function findingTitle(f) {
  if (f.finding_type === 'missing_payment') return `${_contractLabel(f)} · ${f.period} sin abono`
  if (f.finding_type === 'match_found') return `${formatCLP(f.candidate_amount)} · ${_contractLabel(f)} · ${f.period} · coincidencia ${f.confidence}`
  if (f.finding_type === 'amount_mismatch') return `${_contractLabel(f)} · ${f.period} · monto distinto`
  if (f.finding_type === 'unmatched_movement') return `${formatCLP(f.candidate_amount)} · movimiento sin contrato`
  return `Hallazgo #${f.id}`
}

function findingDescription(f) {
  if (f.finding_type === 'missing_payment')
    return `Pago esperado: ${formatCLP(f.expected_amount)}. Sin abono compatible encontrado en cartola.`
  if (f.finding_type === 'match_found') {
    const who = [f.property_label, f.tenant_name].filter(Boolean).join(' · ') || `contrato #${f.contract_id}`
    return `Movimiento #${f.bank_movement_id} coincide con ${who}, período ${f.period}. Sin confirmar.`
  }
  if (f.finding_type === 'amount_mismatch')
    return `Se esperaba ${formatCLP(f.expected_amount)}, se encontró ${formatCLP(f.candidate_amount)} (movimiento #${f.bank_movement_id}).`
  if (f.finding_type === 'unmatched_movement')
    return `Movimiento #${f.bank_movement_id} no coincide con ningún contrato conocido.`
  return ''
}

function PaymentAuditPage() {
  const [activeTab, setActiveTab] = useState('inconsistencias')
  const [isProcessing, setIsProcessing] = useState(false)

  const [statements, setStatements] = useState([])
  const [statementsError, setStatementsError] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [parsingId, setParsingId] = useState(null)
  const fileInputRef = useRef(null)

  const [movements, setMovements] = useState([])
  const [movementsError, setMovementsError] = useState(null)
  const [isLoadingMovements, setIsLoadingMovements] = useState(false)

  const [findings, setFindings] = useState([])
  const [findingsError, setFindingsError] = useState(null)
  const [isRunningAudit, setIsRunningAudit] = useState(false)
  const [auditResult, setAuditResult] = useState(null)

  const [contractSummary, setContractSummary] = useState(null)
  const [contractSummaryError, setContractSummaryError] = useState(null)
  const [isLoadingContractSummary, setIsLoadingContractSummary] = useState(false)
  const [completingId, setCompletingId] = useState(null)
  const [resolvingFindingId, setResolvingFindingId] = useState(null)
  const [resolvingUnmatchedId, setResolvingUnmatchedId] = useState(null)
  const [resolvingAmountMismatchId, setResolvingAmountMismatchId] = useState(null)

  async function loadStatements() {
    try {
      const res = await fetch(`${API_BASE}/payment-audit/statements`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setStatements(await res.json())
      setStatementsError(null)
    } catch (err) {
      setStatementsError(`Error al cargar cartolas: ${err.message}`)
    }
  }

  async function loadMovements() {
    setIsLoadingMovements(true)
    try {
      const res = await fetch(`${API_BASE}/payment-audit/movements`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setMovements(await res.json())
      setMovementsError(null)
    } catch (err) {
      setMovementsError(`Error al cargar movimientos: ${err.message}`)
    } finally {
      setIsLoadingMovements(false)
    }
  }

  async function loadFindings() {
    try {
      const res = await fetch(`${API_BASE}/payment-audit/findings`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      const data = await res.json()
      setFindings(data)
      setFindingsError(null)
      return data
    } catch (err) {
      setFindingsError(`Error al cargar hallazgos: ${err.message}`)
      return []
    }
  }

  async function loadContractSummary(period_from, period_to) {
    setIsLoadingContractSummary(true)
    try {
      const params = new URLSearchParams()
      if (period_from) params.set('period_from', period_from)
      if (period_to) params.set('period_to', period_to)
      const qs = params.toString()
      const res = await fetch(`${API_BASE}/payment-audit/contract-summary${qs ? `?${qs}` : ''}`)
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setContractSummary(await res.json())
      setContractSummaryError(null)
    } catch (err) {
      setContractSummaryError(`Error al cargar resumen por contrato: ${err.message}`)
    } finally {
      setIsLoadingContractSummary(false)
    }
  }

  async function handleProcessCartolas() {
    const pending = statements.filter(
      (s) => s.status === 'uploaded' && s.original_filename.toLowerCase().endsWith('.xls')
    )
    if (pending.length === 0) return

    setIsProcessing(true)
    setStatementsError(null)

    for (const s of pending) {
      try {
        await fetch(`${API_BASE}/payment-audit/statements/${s.id}/parse`, { method: 'POST' })
      } catch {
        // continue on individual failure
      }
    }

    await Promise.all([loadStatements(), loadMovements()])
    setIsProcessing(false)
  }

  async function handleRunAudit() {
    if (movements.length === 0) {
      setFindingsError('Primero procesa al menos una cartola con movimientos.')
      return
    }

    const months = movements.map((m) => m.movement_date.slice(0, 7)).sort()
    const period_from = months[0]
    const period_to = months[months.length - 1]

    setIsRunningAudit(true)
    setFindingsError(null)
    setAuditResult(null)
    try {
      const res = await fetch(`${API_BASE}/payment-audit/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ period_from, period_to }),
      })
      if (!res.ok) {
        const body = await res.json()
        throw new Error(body.detail ?? `Error ${res.status}`)
      }
      const result = await res.json()
      setAuditResult(result)
      await loadContractSummary(period_from, period_to)
      const freshFindings = await loadFindings()
      const hasInconsistencias = freshFindings.some(
        (f) => f.finding_type === 'missing_payment' || f.finding_type === 'amount_mismatch'
      )
      const hasCompletar = freshFindings.some((f) => f.finding_type === 'match_found')
      const hasNoEncontrados = freshFindings.some((f) => f.finding_type === 'unmatched_movement')
      if (hasInconsistencias) setActiveTab('inconsistencias')
      else if (hasCompletar) setActiveTab('completar')
      else if (hasNoEncontrados) setActiveTab('no-encontrados')
    } catch (err) {
      setFindingsError(`Error al auditar: ${err.message}`)
    } finally {
      setIsRunningAudit(false)
    }
  }

  async function handleCompletePayment(finding) {
    const confirmed = window.confirm(
      `¿Confirmar pago de ${formatCLP(finding.candidate_amount)} para período ${finding.period}?`
    )
    if (!confirmed) return
    setCompletingId(finding.id)
    setFindingsError(null)
    try {
      const res = await fetch(`${API_BASE}/payment-audit/findings/${finding.id}/complete-payment`, {
        method: 'POST',
      })
      if (!res.ok) {
        const body = await res.json()
        throw new Error(body.detail ?? `Error ${res.status}`)
      }
      await Promise.all([loadFindings(), loadMovements(), loadStatements()])
    } catch (err) {
      setFindingsError(`Error al completar pago: ${err.message}`)
    } finally {
      setCompletingId(null)
    }
  }

  async function handleResolveMissingPayment(finding) {
    const note = window.prompt('Nota para resolver este pago no encontrado:')
    if (!note || !note.trim()) return
    setResolvingFindingId(finding.id)
    setFindingsError(null)
    try {
      const res = await fetch(
        `${API_BASE}/payment-audit/findings/${finding.id}/resolve-missing-payment`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ resolution_note: note.trim() }),
        }
      )
      if (!res.ok) {
        const body = await res.json()
        throw new Error(body.detail ?? `Error ${res.status}`)
      }
      await loadFindings()
    } catch (err) {
      setFindingsError(`Error al marcar revisado: ${err.message}`)
    } finally {
      setResolvingFindingId(null)
    }
  }

  async function handleResolveUnmatchedMovement(finding) {
    const note = window.prompt('Nota para resolver este movimiento no encontrado:')
    if (!note || !note.trim()) return
    setResolvingUnmatchedId(finding.id)
    setFindingsError(null)
    try {
      const res = await fetch(
        `${API_BASE}/payment-audit/findings/${finding.id}/resolve-unmatched-movement`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ resolution_note: note.trim() }),
        }
      )
      if (!res.ok) {
        const body = await res.json()
        throw new Error(body.detail ?? `Error ${res.status}`)
      }
      await loadFindings()
    } catch (err) {
      setFindingsError(`Error al marcar revisado: ${err.message}`)
    } finally {
      setResolvingUnmatchedId(null)
    }
  }

  async function handleResolveAmountMismatch(finding) {
    const note = window.prompt('Nota para resolver esta diferencia de monto:')
    if (!note || !note.trim()) return
    setResolvingAmountMismatchId(finding.id)
    setFindingsError(null)
    try {
      const res = await fetch(
        `${API_BASE}/payment-audit/findings/${finding.id}/resolve-amount-mismatch`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ resolution_note: note.trim() }),
        }
      )
      if (!res.ok) {
        const body = await res.json()
        throw new Error(body.detail ?? `Error ${res.status}`)
      }
      await loadFindings()
    } catch (err) {
      setFindingsError(`Error al resolver diferencia: ${err.message}`)
    } finally {
      setResolvingAmountMismatchId(null)
    }
  }

  useEffect(() => {
    loadStatements()
    loadMovements()
    loadFindings()
    loadContractSummary()
  }, [])

  useEffect(() => {
    if (activeTab === 'movimientos') {
      loadMovements()
    }
  }, [activeTab])

  async function handleUploadCartolas(files) {
    if (!files || files.length === 0) return
    setIsUploading(true)
    setStatementsError(null)
    for (const file of Array.from(files)) {
      try {
        const formData = new FormData()
        formData.append('file', file)
        const res = await fetch(`${API_BASE}/payment-audit/statements`, {
          method: 'POST',
          body: formData,
        })
        if (!res.ok) {
          const body = await res.json()
          setStatementsError(`Error al subir ${file.name}: ${body.detail ?? `Error ${res.status}`}`)
        }
      } catch (err) {
        setStatementsError(`Error al subir ${file.name}: ${err.message}`)
      }
    }
    await loadStatements()
    setIsUploading(false)
  }

  async function handleDeleteStatement(id) {
    if (!window.confirm('¿Eliminar esta cartola? Esta acción no se puede deshacer.')) return
    try {
      const res = await fetch(`${API_BASE}/payment-audit/statements/${id}`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const body = await res.json()
        throw new Error(body.detail ?? `Error ${res.status}`)
      }
      await loadStatements()
    } catch (err) {
      setStatementsError(`Error al eliminar la cartola: ${err.message}`)
    }
  }

  async function handleParseStatement(id) {
    setParsingId(id)
    setStatementsError(null)
    try {
      const res = await fetch(`${API_BASE}/payment-audit/statements/${id}/parse`, {
        method: 'POST',
      })
      if (!res.ok) {
        const body = await res.json()
        throw new Error(body.detail ?? `Error ${res.status}`)
      }
      await loadStatements()
      await loadMovements()
    } catch (err) {
      setStatementsError(`Error al parsear la cartola: ${err.message}`)
    } finally {
      setParsingId(null)
    }
  }

  const totalMovements = statements.reduce((sum, s) => sum + (s.movements_count || 0), 0)
  const pendingCount = statements.filter(
    (s) => s.status === 'uploaded' && s.original_filename.toLowerCase().endsWith('.xls')
  ).length
  const parsedCount = statements.filter((s) => s.status !== 'uploaded').length
  const inconsistenciasCount = findings.filter(
    (f) => f.finding_type === 'missing_payment' || f.finding_type === 'amount_mismatch'
  ).length
  const completarCount = findings.filter((f) => f.finding_type === 'match_found').length
  const noEncontradosCount = findings.filter((f) => f.finding_type === 'unmatched_movement').length

  return (
    <>
      <Topbar title="Auditoría de pagos" breadcrumb={['Auditoría de pagos']} />
      <div className="page-body">
        <div className="property-detail-scroll">
          <div className="detail-card">
            <div className="detail-card-title">Auditoría con cartola Banco de Chile</div>

            <div className="audit-steps-grid">
              <div className="detail-card detail-card--outlined audit-step-card">
                <div className="audit-step-header">
                  <span className="step-badge">1</span>
                  <div className="audit-step-title">Agregar cartola</div>
                </div>
                <p className="audit-col-text">
                  Carga la cartola del Banco de Chile que servirá como respaldo.
                </p>
                <div className="audit-chip-row">
                  {statements.length === 0 ? (
                    <span className="badge badge-muted">
                      <span className="badge-dot" />
                      Sin cartolas cargadas
                    </span>
                  ) : (
                    <span className="badge badge-ok">
                      <span className="badge-dot" />
                      {`${statements.length} cartola${statements.length === 1 ? '' : 's'} cargada${statements.length === 1 ? '' : 's'}`}
                    </span>
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xls,.pdf"
                  multiple
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    const files = Array.from(e.target.files || [])
                    e.target.value = ''
                    handleUploadCartolas(files)
                  }}
                />
                <button
                  className="btn-secondary audit-step-btn"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                >
                  {isUploading ? 'Subiendo…' : 'Agregar cartola'}
                </button>
              </div>

              <div className="detail-card detail-card--outlined audit-step-card">
                <div className="audit-step-header">
                  <span className="step-badge">2</span>
                  <div className="audit-step-title">Procesar cartolas</div>
                </div>
                <p className="audit-col-text">
                  Procesa las cartolas cargadas para extraer sus movimientos.
                </p>
                <div className="audit-chip-row">
                  {pendingCount > 0 && (
                    <span className="badge badge-warn">
                      <span className="badge-dot" />
                      {`${pendingCount} pendiente${pendingCount === 1 ? '' : 's'}`}
                    </span>
                  )}
                  {parsedCount > 0 && (
                    <span className="badge badge-ok">
                      <span className="badge-dot" />
                      {`${parsedCount} procesada${parsedCount === 1 ? '' : 's'}`}
                    </span>
                  )}
                  {statements.length === 0 && (
                    <span className="badge badge-muted">
                      <span className="badge-dot" />
                      Sin cartolas
                    </span>
                  )}
                  {totalMovements > 0 && (
                    <span className="badge badge-muted">
                      <span className="badge-dot" />
                      {`${totalMovements} movimiento${totalMovements === 1 ? '' : 's'}`}
                    </span>
                  )}
                </div>
                <button
                  className="btn-secondary audit-step-btn"
                  onClick={handleProcessCartolas}
                  disabled={isProcessing || pendingCount === 0}
                >
                  {isProcessing
                    ? 'Procesando…'
                    : pendingCount === 0 && statements.length > 0
                    ? 'Sin cartolas pendientes'
                    : 'Procesar cartolas'}
                </button>
              </div>

              <div className="detail-card detail-card--outlined audit-step-card">
                <div className="audit-step-header">
                  <span className="step-badge">3</span>
                  <div className="audit-step-title">Auditar cartolas</div>
                </div>
                <p className="audit-col-text">
                  Compara contratos, pagadores esperados y movimientos importados.
                </p>
                <div className="audit-chip-row">
                  <span className="badge badge-muted">
                    <span className="badge-dot" />
                    {`${movements.length} movimiento${movements.length === 1 ? '' : 's'} cargado${movements.length === 1 ? '' : 's'}`}
                  </span>
                </div>
                <button
                  className="btn-primary audit-step-btn"
                  onClick={handleRunAudit}
                  disabled={isRunningAudit || movements.length === 0}
                >
                  {isRunningAudit ? 'Auditando…' : 'Auditar cartolas'}
                </button>
              </div>
            </div>

            {statementsError && <div className="payment-form-error">{statementsError}</div>}

            <div className="table-wrapper">
                <table className="dashboard-table">
                    <thead>
                      <tr>
                        <th className="th">Archivo</th>
                        <th className="th">Tipo</th>
                        <th className="th">Estado</th>
                        <th className="th">Movimientos</th>
                        <th className="th">Cargado</th>
                        <th className="th">Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {statements.map((s) => (
                        <tr key={s.id}>
                          <td className="td">{s.original_filename}</td>
                          <td className="td td-muted">{s.mime_type}</td>
                          <td className="td">
                            <span className="badge badge-muted">
                              <span className="badge-dot" />
                              {s.status}
                            </span>
                          </td>
                          <td className="td">{s.movements_count}</td>
                          <td className="td td-muted">{s.uploaded_at}</td>
                          <td className="td">
                            <div className="row-actions--wrap">
                              {s.status === 'uploaded' && s.original_filename.toLowerCase().endsWith('.xls') && (
                                <button
                                  className="btn-payments"
                                  onClick={() => handleParseStatement(s.id)}
                                  disabled={parsingId === s.id}
                                >
                                  {parsingId === s.id ? 'Parseando…' : 'Parsear'}
                                </button>
                              )}
                              {s.status === 'uploaded' && s.movements_count === 0 && (
                                <button className="btn-payments" onClick={() => handleDeleteStatement(s.id)}>
                                  Eliminar
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                </table>
            </div>
          </div>

          <div className="detail-card">
            <h2 className="audit-section-title">Resumen por contrato</h2>
            {contractSummaryError && <div className="payment-form-error">{contractSummaryError}</div>}
            {isLoadingContractSummary ? (
              <p className="audit-col-text">Cargando resumen…</p>
            ) : !contractSummary || contractSummary.contracts.length === 0 ? (
              <p className="audit-col-text">No hay contratos activos para auditar.</p>
            ) : (
              <div className="table-wrapper">
                <table className="dashboard-table">
                  <thead>
                    <tr>
                      <th className="th">Contrato / propiedad</th>
                      <th className="th">Pagadores esperados</th>
                      <th className="th">Meses auditados</th>
                      <th className="th">Estado general</th>
                    </tr>
                  </thead>
                  <tbody>
                    {contractSummary.contracts.map((c) => (
                      <tr key={c.contract_id}>
                        <td className="td">{c.property_label ?? `Contrato #${c.contract_id}`}</td>
                        <td className="td td-muted">{c.tenant_name ?? '—'}</td>
                        <td className="td">
                          <div className="audit-chip-row">
                            {c.months.length === 0 ? (
                              <span className="badge badge-muted">
                                <span className="badge-dot" />
                                Sin datos
                              </span>
                            ) : (
                              c.months.map((m) => (
                                <span className={`badge ${MONTH_STATUS_BADGE[m.status]}`} key={m.period}>
                                  <span className="badge-dot" />
                                  {formatMonthShort(m.period)}
                                </span>
                              ))
                            )}
                          </div>
                        </td>
                        <td className="td">
                          <span className={`badge ${OVERALL_STATUS_BADGE[c.overall_status]}`}>
                            <span className="badge-dot" />
                            {OVERALL_STATUS_LABEL[c.overall_status]}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="audit-section-header">
            <div>
              <h2 className="audit-section-title">Resumen inconsistencias</h2>
              <p className="audit-section-subtitle">
                Diferencias accionables detectadas entre pagos esperados, cartolas importadas y pagos registrados.
              </p>
            </div>
          </div>

          <div className="audit-tabs">
            {[
              { id: 'inconsistencias', label: 'Inconsistencias', count: inconsistenciasCount },
              { id: 'completar', label: 'Completar pagos', count: completarCount },
              { id: 'no-encontrados', label: 'Pagos no encontrados', count: noEncontradosCount },
              { id: 'movimientos', label: 'Movimientos cartola', count: movements.length },
            ].map((tab) => (
              <button
                key={tab.id}
                className={`audit-tab${activeTab === tab.id ? ' active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.count > 0 ? `${tab.label} (${tab.count})` : tab.label}
              </button>
            ))}
          </div>

          <div className="audit-tab-content">
            {activeTab === 'movimientos' ? (
              <>
                {movementsError && <div className="payment-form-error">{movementsError}</div>}
                {isLoadingMovements ? (
                  <p className="audit-col-text">Cargando movimientos…</p>
                ) : movements.length === 0 ? (
                  <p className="audit-col-text">No hay movimientos parseados todavía.</p>
                ) : (
                  <div className="table-wrapper">
                    <table className="dashboard-table">
                      <thead>
                        <tr>
                          <th className="th">Fecha</th>
                          <th className="th">Descripción</th>
                          <th className="th">Abono</th>
                          <th className="th">Saldo</th>
                          <th className="th">Cartola</th>
                        </tr>
                      </thead>
                      <tbody>
                        {movements.map((m) => (
                          <tr key={m.id}>
                            <td className="td td-muted">{m.movement_date}</td>
                            <td className="td">{m.description}</td>
                            <td className="td">{formatCLP(m.amount)}</td>
                            <td className="td td-muted">{formatCLP(m.balance_after)}</td>
                            <td className="td td-muted">#{m.statement_id}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            ) : (
              <>
                {findingsError && <div className="payment-form-error">{findingsError}</div>}
                {(() => {
                  const tabFindings =
                    activeTab === 'inconsistencias'
                      ? findings.filter((f) => f.finding_type === 'missing_payment' || f.finding_type === 'amount_mismatch')
                      : activeTab === 'completar'
                      ? findings.filter((f) => f.finding_type === 'match_found')
                      : findings.filter((f) => f.finding_type === 'unmatched_movement')
                  if (tabFindings.length === 0) {
                    const totalFindings = inconsistenciasCount + completarCount + noEncontradosCount
                    return (
                      <p className="audit-col-text">
                        {totalFindings > 0
                          ? 'No hay hallazgos en esta categoría. Revisa los otros tabs.'
                          : 'No hay hallazgos registrados.'}
                      </p>
                    )
                  }
                  return tabFindings.map((f) => (
                    <div className="detail-card audit-issue-card" key={f.id}>
                      <div>
                        <div className="audit-issue-title">{findingTitle(f)}</div>
                        <p className="audit-issue-desc">{findingDescription(f)}</p>
                      </div>
                      {activeTab === 'completar' && f.finding_type === 'match_found' && (
                        f.status === 'open' ? (
                          <button
                            className="btn-primary"
                            onClick={() => handleCompletePayment(f)}
                            disabled={completingId === f.id}
                          >
                            {completingId === f.id ? 'Completando…' : 'Completar pago'}
                          </button>
                        ) : (
                          <span className="badge badge-ok">
                            <span className="badge-dot" />
                            Completado
                          </span>
                        )
                      )}
                      {activeTab === 'inconsistencias' && f.finding_type === 'missing_payment' && (
                        f.status === 'open' ? (
                          <button
                            className="btn-secondary"
                            onClick={() => handleResolveMissingPayment(f)}
                            disabled={resolvingFindingId === f.id}
                          >
                            {resolvingFindingId === f.id ? 'Guardando…' : 'Marcar revisado'}
                          </button>
                        ) : (
                          <span className="badge badge-ok">
                            <span className="badge-dot" />
                            Revisado
                          </span>
                        )
                      )}
                      {activeTab === 'inconsistencias' && f.finding_type === 'amount_mismatch' && (
                        f.status === 'open' ? (
                          <button
                            className="btn-secondary"
                            onClick={() => handleResolveAmountMismatch(f)}
                            disabled={resolvingAmountMismatchId === f.id}
                          >
                            {resolvingAmountMismatchId === f.id ? 'Guardando…' : 'Resolver diferencia'}
                          </button>
                        ) : (
                          <span className="badge badge-ok">
                            <span className="badge-dot" />
                            Revisado
                          </span>
                        )
                      )}
                      {activeTab === 'no-encontrados' && f.finding_type === 'unmatched_movement' && (
                        f.status === 'open' ? (
                          <button
                            className="btn-secondary"
                            onClick={() => handleResolveUnmatchedMovement(f)}
                            disabled={resolvingUnmatchedId === f.id}
                          >
                            {resolvingUnmatchedId === f.id ? 'Guardando…' : 'Marcar revisado'}
                          </button>
                        ) : (
                          <span className="badge badge-ok">
                            <span className="badge-dot" />
                            Revisado
                          </span>
                        )
                      )}
                    </div>
                  ))
                })()}
              </>
            )}
          </div>
        </div>
      </div>
    </>
  )
}

export default PaymentAuditPage
