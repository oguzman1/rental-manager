import { useState } from 'react'
import DashboardRow from './DashboardRow'

const COLUMNS = [
  { key: 'rol',                  label: 'Rol' },
  { key: 'comuna',               label: 'Comuna' },
  { key: null,                   label: 'Estado' },
  { key: 'property_label',       label: 'Propiedad' },
  { key: 'tenant_name',          label: 'Arrendatario' },
  { key: 'payment_day',          label: 'Día pago',       align: 'center' },
  { key: 'current_rent',         label: 'Renta',          align: 'right' },
  { key: 'next_adjustment_date', label: 'Próx. reajuste' },
  { key: null,                   label: 'Aviso' },
]

function compareValues(a, b, direction) {
  if (a === null || a === undefined) return 1
  if (b === null || b === undefined) return -1
  if (a < b) return direction === 'asc' ? -1 : 1
  if (a > b) return direction === 'asc' ? 1 : -1
  return 0
}

function DashboardTable({ properties, onRowClick }) {
  const [sortColumn, setSortColumn] = useState(null)
  const [sortDirection, setSortDirection] = useState('asc')

  function handleSort(key) {
    if (!key) return
    if (sortColumn === key) {
      setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortColumn(key)
      setSortDirection('asc')
    }
  }

  const sorted = sortColumn
    ? [...properties].sort((a, b) =>
        compareValues(a[sortColumn], b[sortColumn], sortDirection)
      )
    : properties

  return (
    <div className="table-wrapper">
      <table className="dashboard-table">
        <thead>
          <tr>
            {COLUMNS.map((col, i) => {
              const isActive = col.key && sortColumn === col.key
              const alignClass = col.align ? ` th-${col.align}` : ''
              const activeClass = isActive ? ' th-active' : ''
              return (
                <th
                  key={i}
                  className={`th${alignClass}${activeClass}`}
                  onClick={() => handleSort(col.key)}
                  style={{ cursor: col.key ? 'pointer' : 'default' }}
                >
                  {col.label}
                  {isActive && (sortDirection === 'asc' ? ' ↑' : ' ↓')}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((property) => (
            <DashboardRow
              key={property.id}
              property={property}
              onClick={() => onRowClick && onRowClick(property)}
            />
          ))}
        </tbody>
      </table>
      <div className="table-footer">
        <span>
          {sorted.length} de {properties.length} propiedades
        </span>
      </div>
    </div>
  )
}

export default DashboardTable
