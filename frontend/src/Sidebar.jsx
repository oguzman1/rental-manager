const NAV_SECTIONS = [
  {
    label: 'Operación',
    items: [
      { id: 'dashboard',     label: 'Dashboard',          enabled: true },
      { id: 'adjustments',   label: 'Reajustes',          enabled: true },
      { id: 'payment-audit', label: 'Auditoría de pagos', enabled: true },
    ],
  },
  {
    label: 'Mantenedores',
    items: [
      { id: 'properties', label: 'Propiedades',   enabled: true },
      { id: 'contracts',  label: 'Contratos',     enabled: true },
      { id: 'tenants',    label: 'Arrendatarios', enabled: true },
    ],
  },
]

function Sidebar({ active, onNav }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-mark">R</div>
        <span className="sidebar-brand-name">Rental Manager</span>
      </div>

      <nav className="sidebar-nav">
        {NAV_SECTIONS.map((section) => (
          <div className="sidebar-section" key={section.label}>
            <div className="sidebar-section-label">{section.label}</div>
            {section.items.map((item) => (
              <button
                key={item.id}
                className={`sidebar-item${active === item.id ? ' active' : ''}`}
                onClick={() => item.enabled && onNav(item.id)}
                disabled={!item.enabled}
              >
                {item.label}
              </button>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-spacer" />
      <div className="sidebar-footer">v1.0 — Stable Core</div>
    </aside>
  )
}

export default Sidebar
