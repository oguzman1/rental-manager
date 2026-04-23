import { useState } from 'react'
import DashboardRow from './DashboardRow'

function compareValues(a, b, direction) {
  if (a === null || a === undefined) return 1
  if (b === null || b === undefined) return -1
  if (a < b) return direction === 'asc' ? -1 : 1
  if (a > b) return direction === 'asc' ? 1 : -1
  return 0
}

function DashboardTable({ properties }) {
  const [sortColumn, setSortColumn] = useState(null)
  const [sortDirection, setSortDirection] = useState('asc')

  function handleSort(column) {
    if (sortColumn === column) {
      setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortColumn(column)
      setSortDirection('asc')
    }
  }

  const sortedProperties = sortColumn
    ? [...properties].sort((a, b) =>
        compareValues(a[sortColumn], b[sortColumn], sortDirection)
      )
    : properties

  function indicator(column) {
    if (sortColumn !== column) return null
    return <span className="sort-indicator">{sortDirection === 'asc' ? '↑' : '↓'}</span>
  }

  return (
    <table className="dashboard-table">
      <thead>
        <tr>
          <th className="col-sortable" onClick={() => handleSort('rol')}>Rol {indicator('rol')}</th>
          <th className="col-sortable" onClick={() => handleSort('comuna')}>Comuna {indicator('comuna')}</th>
          <th className="col-sortable" onClick={() => handleSort('status')}>Estado {indicator('status')}</th>
          <th>Propiedad/arriendo</th>
          <th>Arrendatario</th>
          <th>Día de pago</th>
          <th className="col-sortable" onClick={() => handleSort('current_rent')}>Arriendo actual {indicator('current_rent')}</th>
          <th className="col-sortable" onClick={() => handleSort('next_adjustment_date')}>Próximo reajuste {indicator('next_adjustment_date')}</th>
          <th>Aviso reajuste</th>
          <th>Requiere aviso</th>
        </tr>
      </thead>

      <tbody>
        {sortedProperties.map((property) => (
          <DashboardRow key={property.id} property={property} />
        ))}
      </tbody>
    </table>
  )
}

export default DashboardTable
