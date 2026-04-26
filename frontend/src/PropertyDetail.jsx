import Topbar from './Topbar'
import { StatusBadge, PaymentBadge } from './Badge'
import { formatCLP, formatFrequency, formatMonthsAgo } from './utils'

function PropertyDetail({ property: p, onBack }) {
  const isOccupied = p.status === 'occupied'

  return (
    <>
      <Topbar
        title={p.property_label ?? p.rol}
        breadcrumb={['Portafolio', p.rol]}
        actions={
          <button className="btn-secondary" onClick={onBack}>
            ← Volver
          </button>
        }
      />
      <div className="property-detail-scroll">
        <div className="property-detail-grid">
          <div>
            <div className="detail-card">
              <div className="detail-status-row">
                <StatusBadge status={p.status} />
              </div>
              <div className="detail-stats">
                <StatItem label="Rol SII" value={p.rol} mono />
                <StatItem label="Comuna" value={p.comuna} />
                <StatItem label="Renta actual" value={formatCLP(p.current_rent)} mono />
              </div>
            </div>

            {isOccupied ? (
              <div className="detail-card">
                <div className="detail-card-title">Contrato activo</div>
                <div className="kv-list">
                  <KVRow label="Arrendatario" value={p.tenant_name ?? '—'} />
                  <KVRow label="Inicio contrato" value={p.start_date ?? '—'} mono />
                  <KVRow
                    label="Día de pago"
                    value={p.payment_day ? `${p.payment_day} de cada mes` : '—'}
                  />
                  <KVRow
                    label="Estado pago actual"
                    value={<PaymentBadge status={p.current_payment_status} />}
                  />
                  <KVRow
                    label="Frecuencia reajuste"
                    value={formatFrequency(p.adjustment_frequency)}
                  />
                  <KVRow
                    label="Último reajuste"
                    value={p.last_adjustment_date ?? '—'}
                    mono
                  />
                  <KVRow
                    label="Meses desde reajuste"
                    value={
                      p.months_since_last_adjustment !== null &&
                      p.months_since_last_adjustment !== undefined
                        ? formatMonthsAgo(p.months_since_last_adjustment)
                        : 'Sin reajustes aún'
                    }
                  />
                  <KVRow
                    label="Próximo reajuste"
                    value={p.next_adjustment_date ?? '—'}
                    mono
                  />
                  <KVRow
                    label="Aviso de reajuste"
                    value={p.adjustment_notice_date ?? '—'}
                    mono
                  />
                </div>
              </div>
            ) : (
              <div className="detail-card">
                <div className="detail-card-title">Sin contrato activo</div>
                <p className="detail-vacant-text">
                  Esta propiedad está vacante. No tiene contrato ni arrendatario
                  asociado.
                </p>
              </div>
            )}
          </div>

          <div>
            <div className="detail-card">
              <div className="detail-card-label">Renta mensual</div>
              <div className="detail-rent-value">{formatCLP(p.current_rent)}</div>
              <div className="detail-rent-sub">
                {p.current_rent ? 'activa' : 'sin renta activa'}
              </div>
            </div>

            {p.tenant_name && (
              <div className="detail-card">
                <div className="detail-card-label">Arrendatario</div>
                <div className="detail-card-title" style={{ marginBottom: 0 }}>
                  {p.tenant_name}
                </div>
                {p.payment_day && (
                  <div className="detail-card-sub">
                    Día de pago: {p.payment_day}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}

function StatItem({ label, value, mono }) {
  return (
    <div>
      <div className="stat-label">{label}</div>
      <div className={`stat-value${mono ? ' stat-value-mono' : ''}`}>{value}</div>
    </div>
  )
}

function KVRow({ label, value, mono }) {
  return (
    <div className="kv-row">
      <span className="kv-label">{label}</span>
      <span className={`kv-value${mono ? ' kv-value-mono' : ''}`}>{value}</span>
    </div>
  )
}

export default PropertyDetail