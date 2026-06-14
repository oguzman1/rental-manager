import { useState } from 'react'
import Topbar from './Topbar'

const MONTH_BADGE_CLASS = {
  ok: 'badge-ok',
  missing: 'badge-danger',
  warning: 'badge-warn',
}

const CONTRACT_ROWS = [
  {
    id: 'depto-serena',
    property: 'Depto Serena',
    tenant: 'Nicolás Delgado',
    payers: 'Nicolás Delgado, N Delgado',
    months: [
      { label: 'Mar', state: 'ok' },
      { label: 'Abr', state: 'missing' },
      { label: 'May', state: 'ok' },
      { label: 'Jun', state: 'ok' },
    ],
    status: '1 mes sin respaldo',
    statusVariant: 'badge-warn',
    hasDifference: true,
  },
  {
    id: 'depto-las-condes',
    property: 'Depto Las Condes',
    tenant: 'Camila Muñoz',
    payers: 'Camila Muñoz, C Muñoz',
    months: [
      { label: 'Mar', state: 'ok' },
      { label: 'Abr', state: 'ok' },
      { label: 'May', state: 'ok' },
      { label: 'Jun', state: 'missing' },
    ],
    status: 'Falta junio',
    statusVariant: 'badge-danger',
    hasDifference: true,
  },
  {
    id: 'casa-chiloe',
    property: 'Casa Chiloé',
    tenant: 'Francisco Vera',
    payers: 'Francisco Vera',
    months: [
      { label: 'Mar', state: 'ok' },
      { label: 'Abr', state: 'ok' },
      { label: 'May', state: 'warning' },
      { label: 'Jun', state: 'ok' },
    ],
    status: 'Pago dudoso en mayo',
    statusVariant: 'badge-warn',
    hasDifference: true,
  },
]

const TABS = [
  { id: 'inconsistencias', label: 'Inconsistencias' },
  { id: 'completar', label: 'Completar pagos' },
  { id: 'no-encontrados', label: 'Pagos no encontrados' },
  { id: 'movimientos', label: 'Movimientos cartola' },
]

const TAB_ITEMS = {
  inconsistencias: [
    {
      title: 'Depto Las Condes · Junio sin respaldo',
      description: 'Se esperaba $759.808 cerca del 05/06 y no aparece abono compatible.',
      action: 'Resolver',
    },
    {
      title: 'Casa Chiloé · Mayo dudoso',
      description: 'Monto exacto por $520.000, pero el nombre "FRANCISCO" no está guardado como alias.',
      action: 'Resolver',
    },
    {
      title: 'Depto Serena · Abril sin respaldo',
      description: 'No aparece por nombre, cuenta ni monto en las cartolas cargadas.',
      action: 'Resolver',
    },
  ],
  completar: [
    {
      title: '$801.875 · 05/06 · NICOLAS DELGADO',
      description: 'Sugerido: Depto Serena · Junio 2026 · confianza alta. Crearía un abono al confirmar.',
      action: 'Completar pago',
    },
    {
      title: '$200.000 · 16/05 · N DELGADO',
      description: 'Completa saldo parcial de mayo. No reemplaza el abono ya registrado.',
      action: 'Completar pago',
    },
  ],
  'no-encontrados': [
    {
      title: 'Depto Las Condes · Junio · $759.808',
      description: 'No hay abono compatible en Banco de Chile para el período auditado.',
      action: 'Marcar revisado',
    },
    {
      title: 'Depto Serena · Abril · $801.875',
      description: 'No aparece por nombre ni monto. Puede ser deuda real o falta cargar otra cartola.',
      action: 'Marcar revisado',
    },
  ],
  movimientos: [
    {
      title: 'Cartola Banco de Chile · Junio 2026',
      description: '78 movimientos leídos · 0 duplicados nuevos · parser reconocido.',
    },
    {
      title: 'Cartola Banco de Chile · Mayo 2026',
      description: '65 movimientos leídos · 3 duplicados ignorados · parser reconocido.',
    },
  ],
}

function MonthBadge({ label, state }) {
  return (
    <span className={`badge ${MONTH_BADGE_CLASS[state]}`}>
      <span className="badge-dot" />
      {label}
    </span>
  )
}

function PaymentAuditPage() {
  const [period, setPeriod] = useState('12m')
  const [onlyDifferences, setOnlyDifferences] = useState(false)
  const [activeTab, setActiveTab] = useState('inconsistencias')

  const visibleRows = onlyDifferences
    ? CONTRACT_ROWS.filter((row) => row.hasDifference)
    : CONTRACT_ROWS

  return (
    <>
      <Topbar title="Auditoría de pagos" breadcrumb={['Auditoría de pagos']} />
      <div className="page-body">
        <div className="property-detail-scroll">
          <p className="page-subtitle">
            Una sola sección: eliges cartolas, auditas pagos y resuelves diferencias sin salir de esta pantalla.
          </p>

          <div className="detail-card">
            <div className="detail-card-title">Auditoría con cartola Banco de Chile</div>

            <div className="audit-steps-grid">
              <div className="detail-card detail-card--outlined audit-step-card">
                <div className="audit-step-header">
                  <span className="step-badge">1</span>
                  <div className="audit-step-title">Agregar cartola</div>
                </div>
                <p className="audit-col-text">
                  Carga los PDF del Banco de Chile que servirán como respaldo.
                </p>
                <div className="audit-chip-row">
                  <span className="badge badge-ok">
                    <span className="badge-dot" />
                    ✓ Mayo 2026
                  </span>
                  <span className="badge badge-ok">
                    <span className="badge-dot" />
                    ✓ Junio 2026
                  </span>
                  <span className="badge badge-muted">
                    <span className="badge-dot" />
                    143 movimientos
                  </span>
                </div>
                <button className="btn-secondary audit-step-btn">
                  <span className="step-badge">1</span>
                  Agregar cartola
                </button>
              </div>

              <div className="detail-card detail-card--outlined audit-step-card">
                <div className="audit-step-header">
                  <span className="step-badge">2</span>
                  <div className="audit-step-title">Revisar cartolas</div>
                </div>
                <p className="audit-col-text">
                  Valida qué cartolas están cargadas antes de auditar pagos.
                </p>
                <div className="audit-chip-row">
                  <span className="badge badge-muted">
                    <span className="badge-dot" />
                    Banco de Chile
                  </span>
                  <span className="badge badge-muted">
                    <span className="badge-dot" />
                    PDF reconocidos
                  </span>
                </div>
                <button className="btn-ghost audit-step-btn">
                  <span className="step-badge">2</span>
                  Ver cartolas
                </button>
              </div>

              <div className="detail-card detail-card--outlined audit-step-card">
                <div className="audit-step-header">
                  <span className="step-badge">3</span>
                  <div className="audit-step-title">Auditar pagos</div>
                </div>
                <p className="audit-col-text">
                  Compara contratos, pagadores esperados y movimientos importados.
                </p>
                <select
                  className="payment-form-input audit-period-select"
                  value={period}
                  onChange={(e) => setPeriod(e.target.value)}
                >
                  <option value="6m">Últimos 6 meses</option>
                  <option value="12m">Últimos 12 meses</option>
                  <option value="2026">2026 completo</option>
                </select>
                <button className="btn-primary audit-step-btn">
                  <span className="step-badge">3</span>
                  Auditar pagos
                </button>
              </div>
            </div>
          </div>

          <div className="audit-section-header">
            <div>
              <h2 className="audit-section-title">Resumen por contrato</h2>
              <p className="audit-section-subtitle">Vista principal: contrato por contrato, mes por mes.</p>
            </div>
            <button
              className={onlyDifferences ? 'btn-primary' : 'btn-secondary'}
              onClick={() => setOnlyDifferences((v) => !v)}
            >
              Ver solo diferencias
            </button>
          </div>

          <div className="table-wrapper">
            <table className="dashboard-table">
              <thead>
                <tr>
                  <th className="th">Contrato</th>
                  <th className="th">Pagadores esperados</th>
                  <th className="th">Meses auditados</th>
                  <th className="th">Estado</th>
                  <th className="th">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row) => (
                  <tr key={row.id}>
                    <td className="td">
                      {row.property}
                      <div className="td-sub">{row.tenant}</div>
                    </td>
                    <td className="td td-muted">{row.payers}</td>
                    <td className="td">
                      <div className="audit-months">
                        {row.months.map((month) => (
                          <MonthBadge key={month.label} label={month.label} state={month.state} />
                        ))}
                      </div>
                    </td>
                    <td className="td">
                      <span className={`badge ${row.statusVariant}`}>
                        <span className="badge-dot" />
                        {row.status}
                      </span>
                    </td>
                    <td className="td">
                      <button className="btn-payments">Resolver</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="audit-section-header">
            <div>
              <h2 className="audit-section-title">Resumen inconsistencias</h2>
              <p className="audit-section-subtitle">
                Diferencias accionables detectadas entre pagos esperados, cartolas importadas y pagos registrados.
              </p>
            </div>
          </div>

          <div className="audit-tabs">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                className={`audit-tab${activeTab === tab.id ? ' active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="audit-tab-content">
            {TAB_ITEMS[activeTab].map((item) => (
              <div className="detail-card audit-issue-card" key={item.title}>
                <div>
                  <div className="audit-issue-title">{item.title}</div>
                  <p className="audit-issue-desc">{item.description}</p>
                </div>
                {item.action && <button className="btn-secondary">{item.action}</button>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}

export default PaymentAuditPage
