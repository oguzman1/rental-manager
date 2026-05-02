import { StatusBadge, PaymentBadge } from './Badge'
import { formatCLP, formatPeriod, contractDuration, formatNextAdjustment, formatRentSince } from './utils'

function DashboardRow({ property, onClick }) {
  const since = formatRentSince(property.start_date, property.last_adjustment_date)
  const estadoSubtitle =
    property.status === 'vacant'
      ? 'Sin arriendo activo'
      : property.current_rent != null
        ? (since ? `${formatCLP(property.current_rent)} desde ${since}` : `${formatCLP(property.current_rent)}`)
        : null

  return (
    <tr className="table-row" onClick={onClick}>
      <td className="td">
        <div>{property.property_label ?? <span className="text-muted">—</span>}</div>
        <div className="td-sub">{property.rol}</div>
      </td>
      <td className="td">
        <div>{property.tenant_name ?? <span className="text-muted">—</span>}</div>
        <div className="td-sub">
          {property.tenant_name ? (contractDuration(property.start_date) ?? '—') : 'Sin contrato'}
        </div>
      </td>
      <td className="td">
        <StatusBadge status={property.status} />
        {estadoSubtitle && <div className="td-sub">{estadoSubtitle}</div>}
      </td>
      <td className="td">
        <PaymentBadge status={property.payment_status} />
        <div className="td-sub">{formatPeriod(property.latest_period)}</div>
      </td>
      <td className="td td-mono td-muted">
        <div>{formatNextAdjustment(property.next_adjustment_date) ?? <span className="text-muted">—</span>}</div>
        {property.start_date && (
          <div className="td-sub">
            {property.last_adjustment_date ? `Últ: ${property.last_adjustment_date}` : 'Últ: Sin reajuste'}
          </div>
        )}
      </td>
    </tr>
  )
}

export default DashboardRow
