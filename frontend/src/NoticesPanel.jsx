import { PaymentStateBadge } from './Badge'

const STATE_CARD_CLASS = {
  overdue: 'notice-card-overdue',
  partial: 'notice-card-next_7_days',
  pending: 'notice-card-next_30_days',
}

function NoticesPanel({ notices, onSelect }) {
  const count = notices.length

  return (
    <aside className="notices-panel">
      <div className="notices-header">
        <span className="notices-title">Pendientes del período</span>
        {count > 0 && <span className="notices-count">{count}</span>}
      </div>

      {count === 0 ? (
        <div className="notices-empty">Todos al día en el período.</div>
      ) : (
        notices.map((item) => (
          <PendingCard
            key={item.id}
            item={item}
            onClick={() => onSelect(item)}
          />
        ))
      )}
    </aside>
  )
}

function PendingCard({ item, onClick }) {
  return (
    <div
      className={`notice-card ${STATE_CARD_CLASS[item.paymentState]}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      <div className="notice-card-top">
        <span className="notice-card-name">
          {item.property_label ?? item.rol}
        </span>
        <PaymentStateBadge state={item.paymentState} />
      </div>
      {item.tenant_name && (
        <div className="notice-card-tenant">{item.tenant_name}</div>
      )}
      {item.current_rent != null && (
        <div className="notice-card-date">
          {item.current_rent.toLocaleString('es-CL')} CLP
        </div>
      )}
    </div>
  )
}

export default NoticesPanel
