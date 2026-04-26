export function PaymentBadge({ status }) {
  if (!status) return <span className="text-muted">—</span>
  if (status === 'paid') {
    return (
      <span className="badge badge-ok">
        <span className="badge-dot" />
        Pagado
      </span>
    )
  }
  if (status === 'partial') {
    return (
      <span className="badge badge-warn">
        <span className="badge-dot" />
        Parcial
      </span>
    )
  }
  return (
    <span className="badge badge-danger">
      <span className="badge-dot" />
      Pendiente
    </span>
  )
}

export function StatusBadge({ status }) {
  const isOccupied = status === 'occupied'
  return (
    <span className={`badge ${isOccupied ? 'badge-ok' : 'badge-muted'}`}>
      <span className="badge-dot" />
      {isOccupied ? 'Arrendada' : 'Vacante'}
    </span>
  )
}

export function NoticeBadge({ daysUntilNotice }) {
  if (daysUntilNotice === null || daysUntilNotice === undefined) return null

  if (daysUntilNotice < 0) {
    return (
      <span className="badge badge-danger">
        <span className="badge-dot" />
        {`Atrasado ${-daysUntilNotice}d`}
      </span>
    )
  }
  if (daysUntilNotice === 0) {
    return (
      <span className="badge badge-warn">
        <span className="badge-dot" />
        Avisar hoy
      </span>
    )
  }
  if (daysUntilNotice <= 7) {
    return (
      <span className="badge badge-warn">
        <span className="badge-dot" />
        {`Avisar en ${daysUntilNotice}d`}
      </span>
    )
  }
  return (
    <span className="badge badge-muted">
      <span className="badge-dot" />
      {`En ${daysUntilNotice}d`}
    </span>
  )
}
