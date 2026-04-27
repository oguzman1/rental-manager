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

function computePendingItems(properties) {
  const todayDay = new Date().getDate()

  return properties
    .filter((p) => p.status === 'occupied' && p.current_payment_status !== 'paid')
    .map((p) => {
      let paymentState
      if (p.current_payment_status === 'partial') {
        paymentState = 'partial'
      } else {
        // pending or null: check if past the payment day
        paymentState = p.payment_day != null && todayDay > p.payment_day
          ? 'overdue'
          : 'pending'
      }
      return { ...p, paymentState }
    })
    .sort((a, b) => {
      const order = { overdue: 0, partial: 1, pending: 2 }
      return order[a.paymentState] - order[b.paymentState]
    })
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
          onPropertySelect={handlePropertySelect}
          onDataMutation={refreshDashboard}
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
          onDataMutation={refreshDashboard}
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

    const totalCount        = properties.length
    const occupiedCount     = properties.filter((p) => p.status === 'occupied').length
    const paidCount         = properties.filter((p) => p.status === 'occupied' && p.current_payment_status === 'paid').length
    const adjustedThisMonth = properties.filter((p) => p.months_since_last_adjustment === 0).length
    const pendingItems      = computePendingItems(properties)

    return (
      <>
        <Topbar title="Portafolio" breadcrumb={['Dashboard']} />
        <DashboardSummary
          total={totalCount}
          occupied={occupiedCount}
          paid={paidCount}
          adjustedThisMonth={adjustedThisMonth}
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
            notices={pendingItems}
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
