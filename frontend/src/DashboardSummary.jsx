function DashboardSummary({ total, occupied, vacant, noticeRequired }) {
  const occupancyPct = total > 0 ? Math.round((occupied / total) * 100) : 0

  return (
    <div className="kpi-strip">
      <KpiTile
        label="Arrendadas"
        value={occupied}
        sub={`de ${total} propiedades`}
        tone="ok"
      />
      <KpiTile
        label="Vacantes"
        value={vacant}
        sub="sin contrato activo"
        tone="muted"
      />
      <KpiTile
        label="Ocupación"
        value={`${occupancyPct}%`}
        sub={`${occupied} arrendadas · ${vacant} vacantes`}
      />
      <KpiTile
        label="Avisos reajuste"
        value={noticeRequired}
        sub={noticeRequired > 0 ? 'requieren aviso' : 'sin avisos pendientes'}
        tone={noticeRequired > 0 ? 'warn' : 'muted'}
      />
    </div>
  )
}

function KpiTile({ label, value, sub, tone }) {
  return (
    <div className={`kpi-tile${tone ? ` kpi-tile-${tone}` : ''}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  )
}

export default DashboardSummary
