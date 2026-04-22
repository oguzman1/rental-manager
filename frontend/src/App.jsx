import { useEffect, useState } from 'react'
import './App.css'

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

      <table className="dashboard-table">
        <thead>
          <tr>
            <th>Rol</th>
            <th>Comuna</th>
            <th>Estado</th>
            <th>Propiedad/arriendo</th>
            <th>Arrendatario</th>
            <th>Día de pago</th>
            <th>Arriendo actual</th>
            <th>Próximo reajuste</th>
            <th>Aviso reajuste</th>
            <th>Requiere aviso</th>
          </tr>
        </thead>

        <tbody>
          {properties.map((property) => (
            <tr key={property.id}>
              <td>{property.rol}</td>
              <td>{property.comuna}</td>
              <td>{property.status}</td>
              <td>{property.property_label ?? '-'}</td>
              <td>{property.tenant_name ?? '-'}</td>
              <td>{property.payment_day ?? '-'}</td>
              <td>
                {property.current_rent
                  ? `$${property.current_rent.toLocaleString('es-CL')}`
                  : '-'}
              </td>
              <td>{property.next_adjustment_date ?? '-'}</td>
              <td>{property.adjustment_notice_date ?? '-'}</td>
              <td>{property.requires_adjustment_notice ? 'Sí' : 'No'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  )
}

export default App