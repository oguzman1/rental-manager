import { useEffect, useState } from 'react'
import Topbar from './Topbar'
import { formatCLP, formatMonthsAgo, formatTenancyYears } from './utils'

const API_URL = 'http://127.0.0.1:8000/tenants'

function TenantsPage({ onPropertySelect }) {
  const [items, setItems] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

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

  return (
    <>
      <Topbar title="Arrendatarios" breadcrumb={['Arrendatarios']} />
      <div className="page-body">
        {isLoading && <div className="app-loading">Cargando arrendatarios…</div>}
        {error && <div className="app-error">Error al cargar: {error}</div>}
        {!isLoading && !error && (
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
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr
                      key={item.id}
                      className="table-row"
                      onClick={() =>
                        onPropertySelect && onPropertySelect(item.property_id)
                      }
                    >
                      <td className="td">{item.display_name}</td>
                      <td className="td">
                        <div>{item.property_label ?? item.rol}</div>
                        <div className="td-sub">{item.rol}</div>
                      </td>
                      <td className="td td-mono td-muted">
                        <div>{item.start_date ?? '—'}</div>
                        <div className="td-sub">
                          {formatTenancyYears(item.tenancy_years)}
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
                      <td className="td td-right td-mono">{formatCLP(item.current_rent)}</td>
                      <td className="td td-center td-mono">
                        {item.payment_day ?? <span className="text-muted">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="table-footer">
                <span>{items.length} arrendatarios activos</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  )
}

export default TenantsPage
