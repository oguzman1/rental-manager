function DashboardSummary({ total, occupied, vacant, noticeRequired }) {
  return (
    <section className="dashboard-summary">
      <article className="summary-card">
        <p className="summary-label">Total propiedades</p>
        <p className="summary-value">{total}</p>
      </article>

      <article className="summary-card">
        <p className="summary-label">Arrendadas</p>
        <p className="summary-value">{occupied}</p>
      </article>

      <article className="summary-card">
        <p className="summary-label">Vacías</p>
        <p className="summary-value">{vacant}</p>
      </article>

      <article className="summary-card">
        <p className="summary-label">Requieren aviso</p>
        <p className="summary-value">{noticeRequired}</p>
      </article>
    </section>
  )
}

export default DashboardSummary