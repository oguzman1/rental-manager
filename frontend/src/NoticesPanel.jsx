import { useState } from 'react'
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

const ADJUSTMENT_STATE_LABEL = {
  pending_adjustment: 'Pendiente de reajuste',
  pending_notice: 'Pendiente de aviso',
  notice_sent: 'Aviso enviado / pendiente de aplicar',
  resolved: 'Resuelto',
  dismissed: 'Anulado / no corresponde',
  upcoming: 'Próximo ciclo',
}

function NoticesPanel({
  paymentNotices,
  adjustmentNotices,
  onPaymentSelect,
  onAdjustmentSelect,
  onMarkNoticeSent,
  onDismissAdjustmentAlert,
}) {
  const [resolveModal, setResolveModal] = useState(null)

  const hasPayments    = paymentNotices.length > 0
  const hasAdjustments = adjustmentNotices.length > 0
  const totalCount     = paymentNotices.length + adjustmentNotices.length

  return (
    <>
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
                    key={item._alertKey ?? item.id}
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
                    onResolve={() => setResolveModal(item)}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </aside>

      {resolveModal && (
        <div className="payment-modal-overlay" onClick={() => setResolveModal(null)}>
          <div className="payment-modal-panel" onClick={(e) => e.stopPropagation()}>
            <div className="payment-modal-header">
              <span className="payment-modal-title">
                Resolver reajuste — {resolveModal.property_label ?? resolveModal.rol}
              </span>
              <button className="payment-modal-close" onClick={() => setResolveModal(null)}>×</button>
            </div>
            <div className="payment-modal-body" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.875rem' }}>
                {resolveModal.tenant_name && (
                  <div><span style={{ opacity: 0.6 }}>Arrendatario:</span> {resolveModal.tenant_name}</div>
                )}
                <div><span style={{ opacity: 0.6 }}>Renta actual:</span> {formatCLP(resolveModal.current_rent)}</div>
                {resolveModal.next_adjustment_date && (
                  <div><span style={{ opacity: 0.6 }}>Próximo reajuste:</span> {resolveModal.next_adjustment_date}</div>
                )}
                {resolveModal.last_adjustment_date && (
                  <div><span style={{ opacity: 0.6 }}>Último reajuste:</span> {resolveModal.last_adjustment_date}</div>
                )}
                {resolveModal.due_adjustment_date && (
                  <div>
                    <span style={{ opacity: 0.6 }}>Ciclo pendiente:</span>{' '}
                    {resolveModal.due_adjustment_date}
                    {formatAdjustmentTiming(resolveModal.due_adjustment_date) && (
                      <span style={{ opacity: 0.6 }}> · {formatAdjustmentTiming(resolveModal.due_adjustment_date)}</span>
                    )}
                  </div>
                )}
                <div>
                  <span style={{ opacity: 0.6 }}>Estado:</span>{' '}
                  {ADJUSTMENT_STATE_LABEL[resolveModal.adjustment_alert_state] ?? 'Pendiente de reajuste'}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', paddingTop: '4px' }}>
                <button
                  className="btn-payments"
                  onClick={() => { setResolveModal(null); onAdjustmentSelect(resolveModal) }}
                >
                  Aplicar reajuste
                </button>
                {!resolveModal.notice_registered && (
                  <button
                    className="btn-payments"
                    onClick={() => { setResolveModal(null); onMarkNoticeSent(resolveModal) }}
                  >
                    Registrar aviso enviado
                  </button>
                )}
                <button
                  className="btn-payments"
                  onClick={() => {
                    if (!window.confirm('¿Anular esta alerta de reajuste? No se modificará el calendario ni el historial de reajustes.')) return
                    const comment = window.prompt('Motivo opcional')
                    setResolveModal(null)
                    onDismissAdjustmentAlert?.(resolveModal, comment ?? '')
                  }}
                >
                  Anular alerta
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function PaymentCard({ item, onClick }) {
  const expected = item.actionable_payment_amount ?? item.current_rent
  let amountText = null
  if (expected != null) {
    if (item.paymentState === 'partial') {
      const paid    = item.actionable_payment_paid_amount ?? 0
      const missing = expected - paid
      amountText = `Faltan ${formatCLP(missing)} de ${formatCLP(expected)}`
    } else {
      amountText = `${formatCLP(expected)} pendiente`
    }
  }

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

function AdjustmentCard({ item, onResolve }) {
  const dateRef = item.due_adjustment_date ?? item.next_adjustment_date
  const title   = `Reajuste ${formatPeriodLabel((dateRef ?? '').slice(0, 7))}`
  const timing  = formatAdjustmentTiming(dateRef)
  const meta    = `${item.property_label ?? item.rol}: ${formatCLP(item.current_rent)}`
  const state   = ADJUSTMENT_STATE_LABEL[item.adjustment_alert_state] ?? 'Pendiente de reajuste'

  return (
    <div
      className={`notice-card ${item.adjustment_due ? 'notice-card-overdue' : 'notice-card-next_30_days'}`}
      onClick={onResolve}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onResolve()}
    >
      <div className="notice-card-top">
        <span className="notice-card-name">{title}</span>
      </div>
      {timing && <div className="notice-card-date">{timing}</div>}
      <div className="notice-card-tenant">{state} · {meta}</div>
      <button
        className="btn-payments notice-card-btn"
        onClick={(e) => { e.stopPropagation(); onResolve() }}
      >
        Resolver
      </button>
    </div>
  )
}

export default NoticesPanel
