import { PaymentStateBadge } from './Badge'
import { formatCLP, daysUntil, formatRentPeriod, formatPaymentDueTiming, formatPeriodLabel } from './utils'

function formatAdjustmentTiming(isoDate) {
  const days = daysUntil(isoDate)
  if (days === null) return null
  if (days === 0) return 'Vence hoy'
  if (days === 1) return 'Vence mañana'
  if (days > 1) return `Vence en ${days} días`
  if (days === -1) return 'Vencido hace 1 día'
  return `Vencido hace ${Math.abs(days)} días`
}

const PAYMENT_CARD_CLASS = {
  overdue: 'notice-card-overdue',
  partial: 'notice-card-next_7_days',
  pending: 'notice-card-next_30_days',
}

function NoticesPanel({ paymentNotices, adjustmentNotices, onPaymentSelect, onAdjustmentSelect, onMarkNoticeSent }) {
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
                  onApplyAdjustment={() => onAdjustmentSelect(item)}
                  onMarkNoticeSent={() => onMarkNoticeSent(item)}
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
      <button
        className="btn-payments notice-card-btn"
        onClick={(e) => { e.stopPropagation(); onClick() }}
      >
        Resolver
      </button>
    </div>
  )
}

function AdjustmentCard({ item, onApplyAdjustment, onMarkNoticeSent }) {
  const dateRef = item.due_adjustment_date ?? item.next_adjustment_date
  const title   = `Reajuste ${formatPeriodLabel((dateRef ?? '').slice(0, 7))}`
  const timing  = formatAdjustmentTiming(dateRef)
  const meta    = `${item.property_label ?? item.rol}: ${formatCLP(item.current_rent)}`

  function handleClick() {
    if (!item.notice_registered) {
      onMarkNoticeSent()
    } else if (item.adjustment_due) {
      onApplyAdjustment()
    }
  }

  return (
    <div
      className={`notice-card ${item.adjustment_due ? 'notice-card-overdue' : 'notice-card-next_30_days'}`}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && handleClick()}
    >
      <div className="notice-card-top">
        <span className="notice-card-name">{title}</span>
      </div>
      {timing && <div className="notice-card-date">{timing}</div>}
      <div className="notice-card-tenant">{meta}</div>
      <button
        className="btn-payments notice-card-btn"
        onClick={(e) => { e.stopPropagation(); handleClick() }}
      >
        Resolver
      </button>
    </div>
  )
}

export default NoticesPanel
