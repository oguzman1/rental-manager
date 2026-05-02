import { PaymentStateBadge } from './Badge'
import { formatCLP, daysUntil, formatRentPeriod, formatPaymentDueTiming } from './utils'

function formatNoticeTiming(isoDate) {
  if (!isoDate) return null
  const days = daysUntil(isoDate)
  if (days === null) return null
  if (days === 0) return 'Aviso desde hoy'
  if (days > 0) return days === 1 ? 'Avisar en 1 día' : `Avisar en ${days} días`
  const abs = Math.abs(days)
  return abs === 1 ? 'Aviso pendiente hace 1 día' : `Aviso pendiente hace ${abs} días`
}

const PAYMENT_CARD_TITLE = {
  overdue: 'Pago vencido',
  partial: 'Pago parcial',
  pending: 'Pago por vencer',
}

const PAYMENT_CARD_CLASS = {
  overdue: 'notice-card-overdue',
  partial: 'notice-card-next_7_days',
  pending: 'notice-card-next_30_days',
}

function NoticesPanel({ paymentNotices, adjustmentNotices, onPaymentSelect, onAdjustmentSelect }) {
  const hasPayments    = paymentNotices.length > 0
  const hasAdjustments = adjustmentNotices.length > 0
  const totalCount     = paymentNotices.length + adjustmentNotices.length

  return (
    <aside className="notices-panel">
      <div className="notices-header">
        <span className="notices-title">Alertas activas</span>
        {totalCount > 0 && <span className="notices-count">{totalCount}</span>}
      </div>

      {!hasPayments && !hasAdjustments ? (
        <div className="notices-empty">Sin alertas activas.</div>
      ) : (
        <>
          {hasPayments && (
            <div className="notices-group">
              <div className="notices-group-label">Pagos</div>
              {paymentNotices.map((item) => (
                <PaymentCard
                  key={item.id}
                  item={item}
                  onClick={() => onPaymentSelect(item)}
                />
              ))}
            </div>
          )}
          {hasAdjustments && (
            <div className="notices-group">
              <div className="notices-group-label">Reajustes</div>
              {adjustmentNotices.map((item) => (
                <AdjustmentCard
                  key={item.id}
                  item={item}
                  onClick={() => onAdjustmentSelect(item)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </aside>
  )
}

function PaymentCard({ item, onClick }) {
  const amount = item.actionable_payment_amount ?? item.current_rent
  const amountText = amount != null
    ? formatCLP(amount) + (item.paymentState === 'partial' ? ' esperado' : '')
    : null

  const title      = formatRentPeriod(item.actionable_payment_period)
  const meta       = [item.property_label ?? item.rol, amountText].filter(Boolean).join(' · ')
  const dueTiming  = formatPaymentDueTiming(item.actionable_payment_period, item.payment_day)

  return (
    <div
      className={`notice-card ${PAYMENT_CARD_CLASS[item.paymentState]}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      <div className="notice-card-top">
        <span className="notice-card-name">{title}</span>
        <PaymentStateBadge state={item.paymentState} />
      </div>
      {dueTiming && <div className="notice-card-date">{dueTiming}</div>}
      <div className="notice-card-tenant">{meta}</div>
      {item.tenant_name && (
        <div className="notice-card-tenant">{item.tenant_name}</div>
      )}
      <button
        className="btn-payments notice-card-btn"
        onClick={(e) => { e.stopPropagation(); onClick() }}
      >
        Resolver
      </button>
    </div>
  )
}

function AdjustmentCard({ item, onClick }) {
  const noticeTiming = formatNoticeTiming(item.adjustment_notice_date)

  return (
    <div
      className="notice-card notice-card-adjustment"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      <div className="notice-card-top">
        <span className="notice-card-name">Reajuste próximo</span>
      </div>
      <div className="notice-card-tenant">
        {item.property_label ?? item.rol}
      </div>
      {item.tenant_name && (
        <div className="notice-card-tenant">{item.tenant_name}</div>
      )}
      {noticeTiming && (
        <div className="notice-card-date">{noticeTiming}</div>
      )}
      {item.next_adjustment_date && (
        <div className="notice-card-date">Próx. reajuste: {item.next_adjustment_date}</div>
      )}
      <button
        className="btn-payments notice-card-btn"
        onClick={(e) => { e.stopPropagation(); onClick() }}
      >
        Resolver
      </button>
    </div>
  )
}

export default NoticesPanel
