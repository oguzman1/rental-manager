import { useEffect, useState } from 'react'
import './App.css'
import DashboardFilters from './DashboardFilters'
import DashboardSummary from './DashboardSummary'
import DashboardTable from './DashboardTable'

const API_URL = 'http://127.0.0.1:8000/dashboard'

function App() {
  const [properties, setProperties] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const [statusFilter, setStatusFilter] = useState('all')
  const [adjustmentFilter, setAdjustmentFilter] = useState('all')
  const [searchText, setSearchText] = useState('')

  useEffect(() => {
    async function loadDashboard() {
      try {
        const response = await fetch(API_URL)

        if (!response.ok) {
          throw new Error(`Error ${response.status}`)
        }

        const data = await response.json()
        setProperties(data)
      } catch (error) {
        setError(error.message)
      } finally {
        setIsLoading(false)
      }
    }

    loadDashboard()
  }, [])

  if (isLoading) {
    return (
      <main className="page">
        <h1>Rental Manager Dashboard</h1>
        <p>Cargando propiedades...</p>
      </main>
    )
  }

  if (error) {
    return (
      <main className="page">
        <h1>Rental Manager Dashboard</h1>
        <p>Error al cargar dashboard: {error}</p>
      </main>
    )
  }

  const filteredProperties = properties
    .filter((p) => statusFilter === 'all' || p.status === statusFilter)
    .filter(
      (p) =>
        adjustmentFilter === 'all' ||
        p.requires_adjustment_notice === true
    )
    .filter(
      (p) =>
        !searchText ||
        p.rol.toLowerCase().includes(searchText.toLowerCase()) ||
        p.comuna.toLowerCase().includes(searchText.toLowerCase())
    )

  const totalCount = properties.length
  const occupiedCount = properties.filter((p) => p.status === 'occupied').length
  const vacantCount = properties.filter((p) => p.status === 'vacant').length
  const noticeCount = properties.filter(
    (p) => p.requires_adjustment_notice
  ).length

  function handleClearFilters() {
    setStatusFilter('all')
    setAdjustmentFilter('all')
    setSearchText('')
  }

  return (
    <main className="page">
      <h1>Rental Manager Dashboard</h1>
      <p>Vista operativa de propiedades, arriendos y próximos reajustes.</p>

      <DashboardSummary
        total={totalCount}
        occupied={occupiedCount}
        vacant={vacantCount}
        noticeRequired={noticeCount}
      />

      <DashboardFilters
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        adjustmentFilter={adjustmentFilter}
        setAdjustmentFilter={setAdjustmentFilter}
        searchText={searchText}
        setSearchText={setSearchText}
        onClear={handleClearFilters}
      />

      <p className="results-count">
        {filteredProperties.length} de {properties.length} propiedades
      </p>

      <DashboardTable properties={filteredProperties} />
    </main>
  )
}

export default App