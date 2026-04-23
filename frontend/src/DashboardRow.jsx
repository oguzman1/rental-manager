function DashboardRow({ property }) {
  return (
    <tr>
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
  )
}

export default DashboardRow
