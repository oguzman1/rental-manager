function DashboardSummary({ total, occupied, paid, adjustedThisMonth }) {
  const occupancyPct = total > 0 ? Math.round((occupied / total) * 100) : 0

  return (
    <div className="kpi-strip">
      <KpiTile
        label="Arrendadas"
        value={`${occupied} de ${total}`}
        sub="propiedades ocupadas"
        tone="ok"
      />
      <KpiTile
        label="Pagadas en el período"
        value={`${paid} de ${occupied}`}
        sub="pagos confirmados este mes"
        tone={paid === occupied && occupied > 0 ? 'ok' : 'muted'}
      />
      <KpiTile
        label="Reajustadas este mes"
        value={`${adjustedThisMonth} de ${occupied}`}
        sub="reajustes en el mes calendario"
        tone="muted"
      />
      <KpiTile
        label="Ocupación"
        value={`${occupancyPct}%`}
        sub={`${occupied} arrendadas · ${total - occupied} vacantes`}
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
