const NAV_ITEMS = [
  { id: 'dashboard',   label: 'Dashboard',      enabled: true },
  { id: 'properties',  label: 'Propiedades',    enabled: true },
  { id: 'contracts',   label: 'Contratos',      enabled: true },
  { id: 'tenants',     label: 'Arrendatarios',  enabled: true },
  { id: 'adjustments', label: 'Reajustes',      enabled: true },
]

function Sidebar({ active, onNav }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-mark">R</div>
        <span className="sidebar-brand-name">Rental Manager</span>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`sidebar-item${active === item.id ? ' active' : ''}`}
            onClick={() => item.enabled && onNav(item.id)}
            disabled={!item.enabled}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className="sidebar-spacer" />
      <div className="sidebar-footer">v1.0 — Stable Core</div>
    </aside>
  )
}

export default Sidebar
