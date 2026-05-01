import { StatusBadge, PaymentBadge } from './Badge'
import { formatCLP, formatPeriod, contractDuration } from './utils'

function DashboardRow({ property, onClick }) {
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
        {property.period_amount != null && (
          <div className="td-sub">{`Canon: ${formatCLP(property.period_amount)}`}</div>
        )}
      </td>
      <td className="td">
        <PaymentBadge status={property.payment_status} />
        <div className="td-sub">{formatPeriod(property.latest_period)}</div>
      </td>
      <td className="td td-mono td-muted">
        <div>{property.next_adjustment_date ?? <span className="text-muted">—</span>}</div>
        {property.start_date && (
          <div className="td-sub">
            {property.last_adjustment_date ? `Últ: ${property.last_adjustment_date}` : 'Sin reajuste'}
          </div>
        )}
      </td>
    </tr>
  )
}

export default DashboardRow
