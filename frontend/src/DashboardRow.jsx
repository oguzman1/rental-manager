import { StatusBadge, PaymentBadge } from './Badge'
import { formatCLP, contractDuration } from './utils'

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
      </td>
      <td className="td td-mono td-muted">
        <div>{property.next_adjustment_date ?? <span className="text-muted">—</span>}</div>
        {property.start_date && (
          <div className="td-sub">
            {property.last_adjustment_date ? `Últ: ${property.last_adjustment_date}` : 'Sin reajuste'}
          </div>
        )}
      </td>
      <td className="td">
        <PaymentBadge status={property.current_payment_status} />
      </td>
      <td className="td td-right td-mono">
        <div>{formatCLP(property.current_rent)}</div>
        <div className="td-sub">
          {property.payment_day != null ? `día ${property.payment_day}` : '—'}
        </div>
      </td>
    </tr>
  )
}

export default DashboardRow
