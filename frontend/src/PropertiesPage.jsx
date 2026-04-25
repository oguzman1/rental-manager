import { useState } from 'react'
import Topbar from './Topbar'
import DashboardTable from './DashboardTable'

function PropertiesPage({ properties, onRowClick }) {
  const [searchText, setSearchText] = useState('')

  const filtered = properties.filter((p) => {
    if (!searchText) return true
    const q = searchText.toLowerCase()
    return (
      p.rol.toLowerCase().includes(q) ||
      p.comuna.toLowerCase().includes(q) ||
      (p.property_label ?? '').toLowerCase().includes(q) ||
      (p.tenant_name ?? '').toLowerCase().includes(q)
    )
  })

  return (
    <>
      <Topbar title="Propiedades" breadcrumb={['Propiedades']} />
      <div className="page-body">
        <div className="table-filters">
          <div className="filter-chips">
            <div className="search-input-wrap">
              <input
                type="text"
                placeholder="Buscar rol, comuna, propiedad…"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
              />
            </div>
          </div>
          <span className="filters-count">
            {filtered.length} / {properties.length}
          </span>
        </div>
        <div className="table-scroll">
          <DashboardTable properties={filtered} onRowClick={onRowClick} />
        </div>
      </div>
    </>
  )
}

export default PropertiesPage
