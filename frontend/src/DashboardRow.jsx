import { StatusBadge, NoticeBadge, PaymentBadge } from './Badge'
import { formatCLP, daysUntil } from './utils'

function DashboardRow({ property, onClick }) {
  const days = daysUntil(property.adjustment_notice_date)

  return (
    <tr className="table-row" onClick={onClick}>
      <td className="td td-mono">{property.rol}</td>
      <td className="td td-muted">{property.comuna}</td>
      <td className="td">
        <StatusBadge status={property.status} />
      </td>
      <td className="td">
        <PaymentBadge status={property.current_payment_status} />
      </td>
      <td className="td">{property.property_label ?? <span className="text-muted">—</span>}</td>
      <td className="td">
        <div>{property.tenant_name ?? <span className="text-muted">—</span>}</div>
        <div className="td-sub">
          {property.tenant_name ? (property.start_date ?? '—') : 'Sin contrato'}
        </div>
      </td>
      <td className="td td-center td-mono">
        {property.payment_day ?? <span className="text-muted">—</span>}
      </td>
      <td className="td td-right td-mono">{formatCLP(property.current_rent)}</td>
      <td className="td td-mono td-muted">
        <div>{property.next_adjustment_date ?? <span className="text-muted">—</span>}</div>
        {property.start_date && (
          <div className="td-sub">
            {property.last_adjustment_date
              ? `Últ: ${property.last_adjustment_date}`
              : 'Sin reajuste'}
          </div>
        )}
      </td>
      <td className="td">
        {property.requires_adjustment_notice ? (
          <NoticeBadge daysUntilNotice={days} />
        ) : (
          <span className="text-muted">—</span>
        )}
      </td>
    </tr>
  )
}

export default DashboardRow
