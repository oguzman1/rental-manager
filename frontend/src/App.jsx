import { useEffect, useState } from 'react'
import './App.css'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import DashboardSummary from './DashboardSummary'
import DashboardFilters from './DashboardFilters'
import DashboardTable from './DashboardTable'
import NoticesPanel from './NoticesPanel'
import PropertyDetail from './PropertyDetail'
import PropertiesPage from './PropertiesPage'
import ContractsPage from './ContractsPage'
import TenantsPage from './TenantsPage'
import AdjustmentsPage from './AdjustmentsPage'
import PaymentsView from './PaymentsView'

const API_URL = 'http://127.0.0.1:8000/dashboard'

function computeNoticeItems(properties) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  return properties
    .filter((p) => p.requires_adjustment_notice && p.adjustment_notice_date)
    .map((p) => {
      const noticeDate = new Date(p.adjustment_notice_date)
      noticeDate.setHours(0, 0, 0, 0)
      const daysUntilNotice = Math.round((noticeDate - today) / 86400000)

      let bucket
      if (daysUntilNotice < 0)       bucket = 'overdue'
      else if (daysUntilNotice === 0) bucket = 'today'
      else if (daysUntilNotice <= 7)  bucket = 'next_7_days'
      else if (daysUntilNotice <= 30) bucket = 'next_30_days'
      else                            bucket = 'later'

      return { ...p, daysUntilNotice, bucket }
    })
    .filter((p) => p.bucket !== 'later')
    .sort(
      (a, b) =>
        new Date(a.adjustment_notice_date) - new Date(b.adjustment_notice_date)
    )
    .slice(0, 5)
}

function App() {
  const [properties, setProperties] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const [route, setRoute] = useState({ name: 'dashboard' })

  const [statusFilter, setStatusFilter] = useState('occupied')
  const [adjustmentFilter, setAdjustmentFilter] = useState('all')
  const [searchText, setSearchText] = useState('')

  useEffect(() => {
    async function loadDashboard() {
      try {
        const response = await fetch(API_URL)
        if (!response.ok) throw new Error(`Error ${response.status}`)
        const data = await response.json()
        setProperties(data)
      } catch (err) {
        setError(err.message)
      } finally {
        setIsLoading(false)
      }
    }
    loadDashboard()
  }, [])

  async function refreshDashboard() {
    try {
      const response = await fetch(API_URL)
      if (!response.ok) return
      setProperties(await response.json())
    } catch {
      // silent — stale data is better than a crash
    }
  }

  function handleNav(target) {
    setRoute({ name: target })
  }

  function handleRowClick(property) {
    setRoute({ name: 'property', property, from: route.name })
  }

  function handlePropertySelect(propertyId) {
    const property = properties.find((p) => p.id === propertyId)
    if (property) {
      setRoute({ name: 'property', property, from: route.name })
    }
  }

  function handlePaymentSelect(contract) {
    setRoute({ name: 'payments', contract, from: route.name })
  }

  function handleClearFilters() {
    setStatusFilter('occupied')
    setAdjustmentFilter('all')
    setSearchText('')
  }

  function renderContent() {
    if (isLoading) {
      return (
        <>
          <Topbar title="Portafolio" breadcrumb={['Dashboard']} />
          <div className="app-loading">Cargando propiedades…</div>
        </>
      )
    }

    if (error) {
      return (
        <>
          <Topbar title="Portafolio" breadcrumb={['Dashboard']} />
          <div className="app-error">Error al cargar: {error}</div>
        </>
      )
    }

    if (route.name === 'property') {
      return (
        <PropertyDetail
          property={route.property}
          onBack={() => handleNav(route.from || 'dashboard')}
        />
      )
    }

    if (route.name === 'properties') {
      return (
        <PropertiesPage
          properties={properties}
          onRowClick={handleRowClick}
        />
      )
    }

    if (route.name === 'payments') {
      return (
        <PaymentsView
          contract={route.contract}
          onBack={() => handleNav(route.from || 'contracts')}
          onPaymentMutation={refreshDashboard}
        />
      )
    }

    if (route.name === 'contracts') {
      return (
        <ContractsPage
          onPropertySelect={handlePropertySelect}
          onPaymentSelect={handlePaymentSelect}
        />
      )
    }

    if (route.name === 'tenants') {
      return <TenantsPage onPropertySelect={handlePropertySelect} />
    }

    if (route.name === 'adjustments') {
      return <AdjustmentsPage onPropertySelect={handlePropertySelect} />
    }

    // Dashboard (default)
    const filteredProperties = properties
      .filter((p) => statusFilter === 'all' || p.status === statusFilter)
      .filter((p) => adjustmentFilter === 'all' || p.requires_adjustment_notice === true)
      .filter((p) => {
        if (!searchText) return true
        const q = searchText.toLowerCase()
        return (
          p.rol.toLowerCase().includes(q) ||
          p.comuna.toLowerCase().includes(q) ||
          (p.property_label ?? '').toLowerCase().includes(q) ||
          (p.tenant_name ?? '').toLowerCase().includes(q)
        )
      })

    const totalCount    = properties.length
    const occupiedCount = properties.filter((p) => p.status === 'occupied').length
    const vacantCount   = properties.filter((p) => p.status === 'vacant').length
    const noticeCount   = properties.filter((p) => p.requires_adjustment_notice).length
    const noticeItems   = computeNoticeItems(properties)

    return (
      <>
        <Topbar title="Portafolio" breadcrumb={['Dashboard']} />
        <DashboardSummary
          total={totalCount}
          occupied={occupiedCount}
          vacant={vacantCount}
          noticeRequired={noticeCount}
        />
        <div className="dashboard-body">
          <div className="table-section">
            <DashboardFilters
              statusFilter={statusFilter}
              setStatusFilter={setStatusFilter}
              adjustmentFilter={adjustmentFilter}
              setAdjustmentFilter={setAdjustmentFilter}
              searchText={searchText}
              setSearchText={setSearchText}
              onClear={handleClearFilters}
              resultCount={filteredProperties.length}
              totalCount={totalCount}
            />
            <div className="table-scroll">
              <DashboardTable
                properties={filteredProperties}
                onRowClick={handleRowClick}
              />
            </div>
          </div>
          <NoticesPanel
            notices={noticeItems}
            onSelect={handleRowClick}
          />
        </div>
      </>
    )
  }

  return (
    <div className="app-shell">
      <Sidebar active={route.name} onNav={handleNav} />
      <div className="app-main">
        {renderContent()}
      </div>
    </div>
  )
}

export default App
