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
import RentChangesView from './RentChangesView'

const API_URL = 'http://127.0.0.1:8000/dashboard'

function computePendingItems(properties) {
  const todayDay = new Date().getDate()
  const now = new Date()
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`

  const result = []

  for (const p of properties) {
    if (p.status !== 'occupied' || p.actionable_payment_period == null) continue

    let paymentState
    if (p.actionable_payment_status === 'partial') {
      paymentState = 'partial'
    } else if (p.actionable_payment_period < currentMonth) {
      paymentState = 'overdue'
    } else {
      paymentState = p.payment_day != null && todayDay > p.payment_day ? 'overdue' : 'pending'
    }
    result.push({ ...p, paymentState, _alertKey: `${p.id}_${p.actionable_payment_period}` })

    // Also alert for current month if unpaid and different from the oldest actionable period
    const currentPeriod = p.current_payment_period
    const currentStatus = p.current_payment_status
    if (
      currentPeriod &&
      currentStatus != null &&
      currentStatus !== 'paid' &&
      p.actionable_payment_period !== currentPeriod
    ) {
      const currentPaymentState = p.payment_day != null && todayDay > p.payment_day ? 'overdue' : 'pending'
      result.push({
        ...p,
        paymentState: currentPaymentState,
        actionable_payment_period: currentPeriod,
        actionable_payment_status: currentStatus,
        actionable_payment_amount: p.current_payment_amount,
        actionable_payment_paid_amount: p.current_payment_paid_amount,
        actionable_payment_recognized_amount: null,
        _alertKey: `${p.id}_${currentPeriod}`,
      })
    }
  }

  return result.sort((a, b) => {
    const order = { overdue: 0, partial: 1, pending: 2 }
    return order[a.paymentState] - order[b.paymentState]
  })
}

function computeAdjustmentAlerts(properties) {
  return properties
    .filter((p) => p.requires_adjustment_notice && !p.adjustment_dismissed && !p.adjustment_resolved)
    .sort((a, b) => {
      if (!a.due_adjustment_date) return 1
      if (!b.due_adjustment_date) return -1
      return a.due_adjustment_date.localeCompare(b.due_adjustment_date)
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

  async function handleRowClick(property) {
    if (!property.contract_id) {
      setRoute({ name: 'property', property, from: route.name })
      return
    }
    try {
      const res = await fetch(`http://127.0.0.1:8000/contracts/${property.contract_id}`)
      if (!res.ok) throw new Error()
      const contract = await res.json()
      setRoute({ name: 'payments', contract, from: 'dashboard' })
    } catch {
      setRoute({ name: 'property', property, from: route.name })
    }
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

  async function handleNoticePaymentClick(property) {
    const targetPeriod = property.actionable_payment_period ?? null
    try {
      const res = await fetch(`http://127.0.0.1:8000/contracts/${property.contract_id}`)
      if (!res.ok) throw new Error()
      const contract = await res.json()
      setRoute({
        name: 'payments',
        contract,
        targetPeriod,
        from: 'dashboard',
        returnOnCancel: true,
      })
    } catch {
      setRoute({
        name: 'payments',
        contract: {
          id:             property.contract_id,
          property_label: property.property_label,
          tenant_name:    property.tenant_name,
          current_rent:   property.current_rent,
          payment_day:    property.payment_day,
        },
        targetPeriod,
        from: 'dashboard',
        returnOnCancel: true,
      })
    }
  }

  function handleNoticeAdjustmentClick(property) {
    setRoute({
      name: 'rent-changes',
      contract: {
        contract_id:          property.contract_id,
        property_label:       property.property_label,
        rol:                  property.rol,
        tenant_name:          property.tenant_name,
        current_rent:         property.current_rent,
        start_date:           property.start_date,
        next_adjustment_date: property.due_adjustment_date ?? property.next_adjustment_date,
        due_adjustment_date:  property.due_adjustment_date,
        adjustment_frequency: property.adjustment_frequency,
      },
      from: 'dashboard',
      autoOpenForm: true,
    })
  }

  async function handleMarkNoticeSent(property) {
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/contracts/${property.contract_id}/notice-sent`,
        { method: 'POST' }
      )
      if (res.ok) await refreshDashboard()
    } catch {
      // silent — stale data is better than a crash
    }
  }

  async function handleDismissAdjustmentAlert(property, comment) {
    try {
      const body = comment?.trim() ? { comment: comment.trim() } : {}
      const res = await fetch(
        `http://127.0.0.1:8000/contracts/${property.contract_id}/adjustment-alert-dismiss`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      )
      if (res.ok) await refreshDashboard()
    } catch {
      // silent — stale data is better than a crash
    }
  }

  function handleRentChangeSelect(contract) {
    setRoute({ name: 'rent-changes', contract, from: route.name })
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
          targetPeriod={route.targetPeriod}
          returnOnCancel={route.returnOnCancel ?? false}
        />
      )
    }

    if (route.name === 'rent-changes') {
      return (
        <RentChangesView
          contract={route.contract}
          onBack={() => handleNav(route.from || 'adjustments')}
          onDataMutation={refreshDashboard}
          autoOpenForm={route.autoOpenForm ?? false}
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
      return (
        <AdjustmentsPage
          onPropertySelect={handlePropertySelect}
          onRentChangeSelect={handleRentChangeSelect}
          onNoticeStateChanged={refreshDashboard}
        />
      )
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
    const adjustmentItems   = computeAdjustmentAlerts(properties)

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
            paymentNotices={pendingItems}
            adjustmentNotices={adjustmentItems}
            onPaymentSelect={handleNoticePaymentClick}
            onAdjustmentSelect={handleNoticeAdjustmentClick}
            onMarkNoticeSent={handleMarkNoticeSent}
            onDismissAdjustmentAlert={handleDismissAdjustmentAlert}
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
