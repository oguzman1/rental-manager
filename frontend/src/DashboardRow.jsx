import { StatusBadge, NoticeBadge } from './Badge'
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
      <td className="td">{property.property_label ?? <span className="text-muted">—</span>}</td>
      <td className="td">{property.tenant_name ?? <span className="text-muted">—</span>}</td>
      <td className="td td-center td-mono">
        {property.payment_day ?? <span className="text-muted">—</span>}
      </td>
      <td className="td td-right td-mono">{formatCLP(property.current_rent)}</td>
      <td className="td td-mono td-muted">
        {property.next_adjustment_date ?? <span className="text-muted">—</span>}
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
