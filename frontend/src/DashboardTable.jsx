import DashboardRow from './DashboardRow'

function DashboardTable({ properties }) {
  return (
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
          <DashboardRow key={property.id} property={property} />
        ))}
      </tbody>
    </table>
  )
}

export default DashboardTable
