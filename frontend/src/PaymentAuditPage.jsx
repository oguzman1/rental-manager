import { useEffect, useRef, useState } from 'react'
import Topbar from './Topbar'
import { formatCLP } from './utils'

const API_BASE = 'http://127.0.0.1:8000'

const MONTH_BADGE_CLASS = {
  ok: 'badge-ok',
  missing: 'badge-danger',
  warning: 'badge-warn',
}

const CONTRACT_ROWS = [
  {
    id: 'depto-serena',
    property: 'Depto Serena',
    tenant: 'Nicolás Delgado',
    payers: 'Nicolás Delgado, N Delgado',
    months: [
      { label: 'Mar', state: 'ok' },
      { label: 'Abr', state: 'missing' },
      { label: 'May', state: 'ok' },
      { label: 'Jun', state: 'ok' },
    ],
    status: '1 mes sin respaldo',
    statusVariant: 'badge-warn',
    hasDifference: true,
  },
  {
    id: 'depto-las-condes',
    property: 'Depto Las Condes',
    tenant: 'Camila Muñoz',
    payers: 'Camila Muñoz, C Muñoz',
    months: [
      { label: 'Mar', state: 'ok' },
      { label: 'Abr', state: 'ok' },
      { label: 'May', state: 'ok' },
      { label: 'Jun', state: 'missing' },
    ],
    status: 'Falta junio',
    statusVariant: 'badge-danger',
    hasDifference: true,
  },
  {
    id: 'casa-chiloe',
    property: 'Casa Chiloé',
    tenant: 'Francisco Vera',
    payers: 'Francisco Vera',
    months: [
      { label: 'Mar', state: 'ok' },
      { label: 'Abr', state: 'ok' },
      { label: 'May', state: 'warning' },
      { label: 'Jun', state: 'ok' },
    ],
    status: 'Pago dudoso en mayo',
    statusVariant: 'badge-warn',
    hasDifference: true,
  },
]

const TABS = [
  { id: 'inconsistencias', label: 'Inconsistencias' },
  { id: 'completar', label: 'Completar pagos' },
  { id: 'no-encontrados', label: 'Pagos no encontrados' },
  { id: 'movimientos', label: 'Movimientos cartola' },
]

function findingTitle(f) {
  if (f.finding_type === 'missing_payment') return `Contrato #${f.contract_id} · ${f.period} sin abono`
  if (f.finding_type === 'match_found') return `${formatCLP(f.candidate_amount)} · ${f.period} · coincidencia ${f.confidence}`
  if (f.finding_type === 'amount_mismatch') return `Contrato #${f.contract_id} · ${f.period} · monto distinto`
  if (f.finding_type === 'unmatched_movement') return `${formatCLP(f.candidate_amount)} · movimiento sin contrato`
  return `Hallazgo #${f.id}`
}

function findingDescription(f) {
  if (f.finding_type === 'missing_payment')
    return `Pago esperado: ${formatCLP(f.expected_amount)}. Sin abono compatible encontrado en cartola.`
  if (f.finding_type === 'match_found')
    return `Movimiento #${f.bank_movement_id} coincide con contrato #${f.contract_id} período ${f.period}. Sin confirmar.`
  if (f.finding_type === 'amount_mismatch')
    return `Se esperaba ${formatCLP(f.expected_amount)}, se encontró ${formatCLP(f.candidate_amount)} (movimiento #${f.bank_movement_id}).`
  if (f.finding_type === 'unmatched_movement')
    return `Movimiento #${f.bank_movement_id} no coincide con ningún contrato conocido.`
  return ''
}

function MonthBadge({ label, state }) {
  return (
    <span className={`badge ${MONTH_BADGE_CLASS[state]}`}>
      <span className="badge-dot" />
      {label}
    </span>
  )
}

function PaymentAuditPage() {
  const [period, setPeriod] = useState('12m')
  const [onlyDifferences, setOnlyDifferences] = useState(false)
  const [activeTab, setActiveTab] = useState('inconsistencias')

  const [statements, setStatements] = useState([])
  const [statementsError, setStatementsError] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [showStatementsList, setShowStatementsList] = useState(false)
  const [parsingId, setParsingId] = useState(null)
  const fileInputRef = useRef(null)

  const [movements, setMovements] = useState([])
  const [movementsError, setMovementsError] = useState(null)
  const [isLoadingMovements, setIsLoadingMovements] = useState(false)

  const [findings, setFindings] = useState([])
  const [findingsError, setFindingsError] = useState(null)
  const [isRunningAudit, setIsRunningAudit] = useState(false)
  const [auditResult, setAuditResult] = useState(null)
  const [completingId, setCompletingId] = useState(null)
  const [resolvingFindingId, setResolvingFindingId] = useState(null)

  const visibleRows = onlyDifferences
    ? CONTRACT_ROWS.filter((row) => row.hasDifference)
    : CONTRACT_ROWS

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
      setFindings(await res.json())
      setFindingsError(null)
    } catch (err) {
      setFindingsError(`Error al cargar hallazgos: ${err.message}`)
    }
  }

  async function handleRunAudit() {
    setIsRunningAudit(true)
    setFindingsError(null)
    setAuditResult(null)
    try {
      const res = await fetch(`${API_BASE}/payment-audit/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (!res.ok) {
        const body = await res.json()
        throw new Error(body.detail ?? `Error ${res.status}`)
      }
      const result = await res.json()
      setAuditResult(result)
      await loadFindings()
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

  useEffect(() => {
    loadStatements()
    loadMovements()
    loadFindings()
  }, [])

  useEffect(() => {
    if (activeTab === 'movimientos') {
      loadMovements()
    }
  }, [activeTab])

  async function handleUploadCartola(file) {
    if (!file) return
    setIsUploading(true)
    setStatementsError(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch(`${API_BASE}/payment-audit/statements`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const body = await res.json()
        throw new Error(body.detail ?? `Error ${res.status}`)
      }
      await loadStatements()
    } catch (err) {
      setStatementsError(`Error al subir la cartola: ${err.message}`)
    } finally {
      setIsUploading(false)
    }
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
  const latestStatements = statements.slice(0, 2)

  return (
    <>
      <Topbar title="Auditoría de pagos" breadcrumb={['Auditoría de pagos']} />
      <div className="page-body">
        <div className="property-detail-scroll">
          <p className="page-subtitle">
            Una sola sección: eliges cartolas, auditas pagos y resuelves diferencias sin salir de esta pantalla.
          </p>

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
                    <>
                      {latestStatements.map((s) => (
                        <span className="badge badge-ok" key={s.id}>
                          <span className="badge-dot" />
                          {`✓ ${s.period_label ?? s.original_filename}`}
                        </span>
                      ))}
                      <span className="badge badge-muted">
                        <span className="badge-dot" />
                        {`${statements.length} cartola${statements.length === 1 ? '' : 's'}`}
                      </span>
                    </>
                  )}
                  <span className="badge badge-muted">
                    <span className="badge-dot" />
                    {`${totalMovements} movimiento${totalMovements === 1 ? '' : 's'}`}
                  </span>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xls,.pdf"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    e.target.value = ''
                    handleUploadCartola(file)
                  }}
                />
                <button
                  className="btn-secondary audit-step-btn"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                >
                  <span className="step-badge">1</span>
                  {isUploading ? 'Subiendo…' : 'Agregar cartola'}
                </button>
              </div>

              <div className="detail-card detail-card--outlined audit-step-card">
                <div className="audit-step-header">
                  <span className="step-badge">2</span>
                  <div className="audit-step-title">Revisar cartolas</div>
                </div>
                <p className="audit-col-text">
                  Valida qué cartolas están cargadas antes de auditar pagos.
                </p>
                <div className="audit-chip-row">
                  <span className="badge badge-muted">
                    <span className="badge-dot" />
                    {`${statements.length} cartola${statements.length === 1 ? '' : 's'} cargada${statements.length === 1 ? '' : 's'}`}
                  </span>
                  <span className="badge badge-muted">
                    <span className="badge-dot" />
                    XLS/PDF
                  </span>
                </div>
                <button
                  className="btn-ghost audit-step-btn"
                  onClick={() => setShowStatementsList((v) => !v)}
                >
                  <span className="step-badge">2</span>
                  Ver cartolas
                </button>
              </div>

              <div className="detail-card detail-card--outlined audit-step-card">
                <div className="audit-step-header">
                  <span className="step-badge">3</span>
                  <div className="audit-step-title">Auditar pagos</div>
                </div>
                <p className="audit-col-text">
                  Compara contratos, pagadores esperados y movimientos importados.
                </p>
                <select
                  className="payment-form-input audit-period-select"
                  value={period}
                  onChange={(e) => setPeriod(e.target.value)}
                >
                  <option value="6m">Últimos 6 meses</option>
                  <option value="12m">Últimos 12 meses</option>
                  <option value="2026">2026 completo</option>
                </select>
                <button
                  className="btn-primary audit-step-btn"
                  onClick={handleRunAudit}
                  disabled={isRunningAudit}
                >
                  <span className="step-badge">3</span>
                  {isRunningAudit ? 'Auditando…' : 'Auditar pagos'}
                </button>
                {auditResult && (
                  <p className="audit-col-text">
                    {`${auditResult.created} hallazgo${auditResult.created !== 1 ? 's' : ''} nuevo${auditResult.created !== 1 ? 's' : ''} · ${auditResult.skipped_duplicates} duplicado${auditResult.skipped_duplicates !== 1 ? 's' : ''} omitido${auditResult.skipped_duplicates !== 1 ? 's' : ''}`}
                  </p>
                )}
              </div>
            </div>

            {statementsError && <div className="payment-form-error">{statementsError}</div>}

            {showStatementsList && (
              <div className="table-wrapper">
                {statements.length === 0 ? (
                  <p className="audit-col-text">Sin cartolas cargadas todavía.</p>
                ) : (
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
                )}
              </div>
            )}
          </div>

          <div className="audit-section-header">
            <div>
              <h2 className="audit-section-title">Resumen por contrato</h2>
              <p className="audit-section-subtitle">Vista principal: contrato por contrato, mes por mes.</p>
            </div>
            <button
              className={onlyDifferences ? 'btn-primary' : 'btn-secondary'}
              onClick={() => setOnlyDifferences((v) => !v)}
            >
              Ver solo diferencias
            </button>
          </div>

          <div className="table-wrapper">
            <table className="dashboard-table">
              <thead>
                <tr>
                  <th className="th">Contrato</th>
                  <th className="th">Pagadores esperados</th>
                  <th className="th">Meses auditados</th>
                  <th className="th">Estado</th>
                  <th className="th">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row) => (
                  <tr key={row.id}>
                    <td className="td">
                      {row.property}
                      <div className="td-sub">{row.tenant}</div>
                    </td>
                    <td className="td td-muted">{row.payers}</td>
                    <td className="td">
                      <div className="audit-months">
                        {row.months.map((month) => (
                          <MonthBadge key={month.label} label={month.label} state={month.state} />
                        ))}
                      </div>
                    </td>
                    <td className="td">
                      <span className={`badge ${row.statusVariant}`}>
                        <span className="badge-dot" />
                        {row.status}
                      </span>
                    </td>
                    <td className="td">
                      <button className="btn-payments">Resolver</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
            {TABS.map((tab) => (
              <button
                key={tab.id}
                className={`audit-tab${activeTab === tab.id ? ' active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
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
                    return <p className="audit-col-text">No hay hallazgos en esta categoría.</p>
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
