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
  )
}

export default DashboardTable
