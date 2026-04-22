import { useEffect, useState } from 'react'
import './App.css'
import DashboardTable from './DashboardTable'

const API_URL = 'http://127.0.0.1:8000/dashboard'

function App() {
  const [properties, setProperties] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

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

  return (
    <main className="page">
      <h1>Rental Manager Dashboard</h1>
      <p>Vista operativa de propiedades, arriendos y próximos reajustes.</p>

      <DashboardTable properties={properties} />
    </main>
  )
}

export default App