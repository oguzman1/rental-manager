import { Fragment, useEffect, useState } from 'react'
import Topbar from './Topbar'
import { NoticeBadge } from './Badge'
import { formatCLP, daysUntil, formatMonthsAgo, formatNextAdjustment } from './utils'

const BASE_URL = 'http://127.0.0.1:8000'
const API_URL = `${BASE_URL}/rent-adjustments`

const EVENT_LABEL = {
  sent: 'Aviso enviado',
  reverted: 'Aviso anulado',
  dismissed: 'Alerta anulada / no corresponde',
}

function formatNextAdjustmentSubtext(isoDate) {
  if (!isoDate) return null
  const label = formatNextAdjustment(isoDate)
  return label ? label.charAt(0).toLowerCase() + label.slice(1) : null
}

function formatLastAdjustmentSubtext(monthsSinceLast) {
  if (monthsSinceLast === null || monthsSinceLast === undefined) return null
  if (monthsSinceLast < 0) return 'programado'
  return formatMonthsAgo(monthsSinceLast)
}

function AdjustmentsPage({ onPropertySelect, onRentChangeSelect, onNoticeStateChanged }) {
  const [items, setItems] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sendingId, setSendingId] = useState(null)
  const [revertingId, setRevertingId] = useState(null)
  const [dismissingId, setDismissingId] = useState(null)
  const [formItemId, setFormItemId] = useState(null)
  const [formComment, setFormComment] = useState('')
  const [historyContractId, setHistoryContractId] = useState(null)
  const [historyMap, setHistoryMap] = useState({})
  const [historyLoadingId, setHistoryLoadingId] = useState(null)

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(API_URL)
        if (!res.ok) throw new Error(`Error ${res.status}`)
        setItems(await res.json())
      } catch (err) {
        setError(err.message)
      } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [])

  async function reloadItems() {
    try {
      const res = await fetch(API_URL)
      if (!res.ok) return
      setItems(await res.json())
    } catch {
      // silent — consistent with app error handling style
    }
  }

  function clearHistoryCache(contractId) {
    setHistoryMap((prev) => {
      const next = { ...prev }
      delete next[contractId]
      return next
    })
  }

  async function handleConfirmNotice(item) {
    if (!item.contract_id) return
    setSendingId(item.id)
    try {
      const body = formComment.trim() ? { comment: formComment.trim() } : {}
      const res = await fetch(`${BASE_URL}/contracts/${item.contract_id}/notice-sent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.ok) {
        setFormItemId(null)
        setFormComment('')
        clearHistoryCache(item.contract_id)
        await reloadItems()
        onNoticeStateChanged?.()
      }
    } catch {
      // silent
    } finally {
      setSendingId(null)
    }
  }

  async function handleRevert(item) {
    if (!item.contract_id) return
    if (!window.confirm('¿Anular el registro de aviso?')) return
    setRevertingId(item.id)
    try {
      const res = await fetch(`${BASE_URL}/contracts/${item.contract_id}/notice-revert`, {
        method: 'POST',
      })
      if (res.ok) {
        clearHistoryCache(item.contract_id)
        await reloadItems()
        onNoticeStateChanged?.()
      }
    } catch {
      // silent
    } finally {
      setRevertingId(null)
    }
  }

  async function handleDismissAlert(item) {
    if (!item.contract_id) return
    if (!window.confirm('¿Anular esta alerta de reajuste? No se modificará el calendario ni el historial de reajustes.')) return
    const comment = window.prompt('Motivo opcional')
    setDismissingId(item.id)
    try {
      const body = comment?.trim() ? { comment: comment.trim() } : {}
      const res = await fetch(`${BASE_URL}/contracts/${item.contract_id}/adjustment-alert-dismiss`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.ok) {
        clearHistoryCache(item.contract_id)
        await reloadItems()
        onNoticeStateChanged?.()
      }
    } catch {
      // silent
    } finally {
      setDismissingId(null)
    }
  }

  async function handleToggleHistory(item) {
    const cid = item.contract_id
    if (historyContractId === cid) {
      setHistoryContractId(null)
      return
    }
    setHistoryContractId(cid)
    if (historyMap[cid] !== undefined) return
    setHistoryLoadingId(cid)
    try {
      const res = await fetch(`${BASE_URL}/contracts/${cid}/notice-events`)
      if (res.ok) {
        const events = await res.json()
        setHistoryMap((prev) => ({ ...prev, [cid]: events }))
      } else {
        setHistoryMap((prev) => ({ ...prev, [cid]: [] }))
      }
    } catch {
      setHistoryMap((prev) => ({ ...prev, [cid]: [] }))
    } finally {
      setHistoryLoadingId(null)
    }
  }

  return (
    <>
      <Topbar title="Reajustes" breadcrumb={['Reajustes']} />
      <div className="page-body">
        {isLoading && <div className="app-loading">Cargando reajustes…</div>}
        {error && <div className="app-error">Error al cargar: {error}</div>}
        {!isLoading && !error && (
          <div className="table-scroll">
            <div className="table-wrapper adjustments-table-wrapper">
              <table className="dashboard-table adjustments-table">
                <thead>
                  <tr>
                    <th className="th">Rol</th>
                    <th className="th">Propiedad</th>
                    <th className="th">Arrendatario</th>
                    <th className="th th-right">Renta</th>
                    <th className="th">Próx. reajuste</th>
                    <th className="th">Últ. reajuste</th>
                    <th className="th">Estado</th>
                    <th className="th th-actions">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <Fragment key={item.id}>
                      <tr
                        className="table-row"
                        onClick={() => onPropertySelect && onPropertySelect(item.id)}
                      >
                        <td className="td td-mono">{item.rol}</td>
                        <td className="td">
                          {item.property_label ?? <span className="text-muted">—</span>}
                        </td>
                        <td className="td">
                          {item.tenant_name ?? <span className="text-muted">—</span>}
                        </td>
                        <td className="td td-right td-mono">{formatCLP(item.current_rent)}</td>
                        <td className="td td-mono td-muted">
                          <div>{item.next_adjustment_date}</div>
                          {formatNextAdjustmentSubtext(item.next_adjustment_date) && (
                            <div className="td-sub">
                              {formatNextAdjustmentSubtext(item.next_adjustment_date)}
                            </div>
                          )}
                        </td>
                        <td className="td td-mono td-muted">
                          <div>{item.last_adjustment_date ?? '—'}</div>
                          {item.last_adjustment_date && (
                            <div className="td-sub">
                              {formatLastAdjustmentSubtext(item.months_since_last_adjustment)}
                            </div>
                          )}
                        </td>
                        <td className="td">
                          <NoticeBadge
                            daysUntilNotice={daysUntil(item.adjustment_notice_date)}
                            noticeRegistered={item.notice_registered}
                            adjustmentDue={item.adjustment_due}
                            noticeSentAt={item.notice_sent_at}
                            adjustmentResolved={item.adjustment_resolved}
                            adjustmentDismissed={item.adjustment_dismissed}
                            adjustmentAlertState={item.adjustment_alert_state}
                          />
                        </td>
                        <td className="td td-actions" onClick={(e) => e.stopPropagation()}>
                          <div className="row-actions--wrap">
                            {!item.requires_adjustment_notice && !item.notice_registered ? (
                              <button
                                className="btn-payments"
                                onClick={() => handleToggleHistory(item)}
                              >
                                Ver historial
                              </button>
                            ) : !item.notice_registered ? (
                              <>
                                {item.adjustment_due && (
                                  <button
                                    className="btn-payments"
                                    onClick={() => onRentChangeSelect?.({
                                      ...item,
                                      next_adjustment_date: item.due_adjustment_date ?? item.next_adjustment_date,
                                    })}
                                  >
                                    Aplicar reajuste
                                  </button>
                                )}
                                <button
                                  className="btn-payments"
                                  onClick={() => {
                                    setFormItemId(item.id)
                                    setFormComment('')
                                  }}
                                >
                                  Registrar aviso
                                </button>
                              </>
                            ) : (
                              <>
                                <button
                                  className="btn-payments"
                                  onClick={() => onRentChangeSelect?.({
                                    ...item,
                                    next_adjustment_date: item.due_adjustment_date ?? item.next_adjustment_date,
                                  })}
                                >
                                  Aplicar reajuste
                                </button>
                                <button
                                  className="btn-payments"
                                  disabled={revertingId === item.id}
                                  onClick={() => handleRevert(item)}
                                >
                                  Anular aviso
                                </button>
                              </>
                            )}
                            {item.requires_adjustment_notice && !item.adjustment_resolved && !item.adjustment_dismissed && (
                              <button
                                className="btn-payments"
                                disabled={dismissingId === item.id}
                                onClick={() => handleDismissAlert(item)}
                              >
                                Anular alerta
                              </button>
                            )}
                            {(item.requires_adjustment_notice || item.notice_registered) && item.contract_id && (
                              <button
                                className="btn-payments"
                                onClick={() => handleToggleHistory(item)}
                              >
                                {historyContractId === item.contract_id
                                  ? 'Ocultar historial'
                                  : 'Ver historial'}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>

                      {formItemId === item.id && (
                        <tr>
                          <td
                            colSpan={8}
                            className="td"
                            style={{ background: 'rgba(0,0,0,0.025)', padding: '10px 16px' }}
                          >
                            <div
                              style={{
                                display: 'flex',
                                gap: '8px',
                                alignItems: 'flex-end',
                                flexWrap: 'wrap',
                              }}
                            >
                              <div style={{ flex: 1, minWidth: '200px' }}>
                                <label
                                  style={{
                                    display: 'block',
                                    fontSize: '0.8rem',
                                    marginBottom: '4px',
                                    opacity: 0.7,
                                  }}
                                >
                                  Comentario (opcional)
                                </label>
                                <input
                                  type="text"
                                  value={formComment}
                                  onChange={(e) => setFormComment(e.target.value)}
                                  placeholder="Ej. Carta enviada por email"
                                  style={{ width: '100%', boxSizing: 'border-box' }}
                                  autoFocus
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') handleConfirmNotice(item)
                                    if (e.key === 'Escape') {
                                      setFormItemId(null)
                                      setFormComment('')
                                    }
                                  }}
                                />
                              </div>
                              <button
                                className="btn-payments"
                                disabled={sendingId === item.id}
                                onClick={() => handleConfirmNotice(item)}
                              >
                                Confirmar
                              </button>
                              <button
                                className="btn-payments"
                                onClick={() => {
                                  setFormItemId(null)
                                  setFormComment('')
                                }}
                              >
                                Cancelar
                              </button>
                            </div>
                          </td>
                        </tr>
                      )}

                      {historyContractId === item.contract_id && (
                        <tr>
                          <td
                            colSpan={8}
                            className="td"
                            style={{ background: 'rgba(0,0,0,0.025)', padding: '10px 16px' }}
                          >
                            {historyLoadingId === item.contract_id ? (
                              <span style={{ opacity: 0.6 }}>Cargando historial…</span>
                            ) : (historyMap[item.contract_id] ?? []).length === 0 ? (
                              <span style={{ opacity: 0.6 }}>Sin historial de avisos.</span>
                            ) : (
                              <table
                                style={{
                                  width: '100%',
                                  fontSize: '0.85rem',
                                  borderCollapse: 'collapse',
                                }}
                              >
                                <thead>
                                  <tr>
                                    <th style={{ textAlign: 'left', padding: '3px 8px', fontWeight: 600 }}>Fecha</th>
                                    <th style={{ textAlign: 'left', padding: '3px 8px', fontWeight: 600 }}>Tipo</th>
                                    <th style={{ textAlign: 'left', padding: '3px 8px', fontWeight: 600 }}>Ciclo</th>
                                    <th style={{ textAlign: 'left', padding: '3px 8px', fontWeight: 600 }}>Comentario</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {(historyMap[item.contract_id] ?? []).map((ev) => (
                                    <tr key={ev.id}>
                                      <td style={{ padding: '3px 8px', fontFamily: 'monospace' }}>
                                        {ev.event_at}
                                      </td>
                                      <td style={{ padding: '3px 8px' }}>
                                        {EVENT_LABEL[ev.event_type] ?? ev.event_type}
                                      </td>
                                      <td style={{ padding: '3px 8px', fontFamily: 'monospace' }}>
                                        {ev.due_adjustment_date}
                                      </td>
                                      <td style={{ padding: '3px 8px', opacity: 0.65 }}>
                                        {ev.comment ?? '—'}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
              <div className="table-footer">
                <span>{items.length} contratos con ciclo de reajuste</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  )
}

export default AdjustmentsPage
