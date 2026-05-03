import { useEffect, useState } from 'react'
import Topbar from './Topbar'
import { NoticeBadge } from './Badge'
import { formatCLP, daysUntil, formatMonthsAgo, formatMonthsUntil } from './utils'

const BASE_URL = 'http://127.0.0.1:8000'
const API_URL = `${BASE_URL}/rent-adjustments`

function AdjustmentsPage({ onPropertySelect, onRentChangeSelect, onNoticeStateChanged }) {
  const [items, setItems] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sendingId, setSendingId] = useState(null)

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

  async function handleManage(item) {
    if (!item.notice_registered) {
      if (!item.contract_id) {
        console.error('handleManage: contract_id missing', item.id)
        return
      }
      setSendingId(item.id)
      try {
        const res = await fetch(
          `${BASE_URL}/contracts/${item.contract_id}/notice-sent`,
          { method: 'POST' }
        )
        if (res.ok) {
          await reloadItems()
          onNoticeStateChanged?.()
        }
      } catch {
        // silent — consistent with app error handling style
      } finally {
        setSendingId(null)
      }
    } else {
      onRentChangeSelect?.(item)
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
            <div className="table-wrapper">
              <table className="dashboard-table">
                <thead>
                  <tr>
                    <th className="th">Rol</th>
                    <th className="th">Propiedad</th>
                    <th className="th">Arrendatario</th>
                    <th className="th th-right">Renta</th>
                    <th className="th">Próx. reajuste</th>
                    <th className="th">Últ. reajuste</th>
                    <th className="th">Estado</th>
                    <th className="th">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr
                      key={item.id}
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
                        <div className="td-sub">
                          {formatMonthsUntil(item.months_until_next_adjustment)}
                        </div>
                      </td>
                      <td className="td td-mono td-muted">
                        <div>{item.last_adjustment_date ?? '—'}</div>
                        {item.last_adjustment_date && (
                          <div className="td-sub">
                            {formatMonthsAgo(item.months_since_last_adjustment)}
                          </div>
                        )}
                      </td>
                      <td className="td">
                        <NoticeBadge
                          daysUntilNotice={daysUntil(item.adjustment_notice_date)}
                          noticeRegistered={item.notice_registered}
                          adjustmentDue={item.adjustment_due}
                          noticeSentAt={item.notice_sent_at}
                        />
                      </td>
                      <td className="td" onClick={(e) => e.stopPropagation()}>
                        <button
                          className="btn-payments"
                          disabled={sendingId === item.id}
                          onClick={() => handleManage(item)}
                        >
                          Gestionar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="table-footer">
                <span>{items.length} contratos con reajuste activo</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  )
}

export default AdjustmentsPage
