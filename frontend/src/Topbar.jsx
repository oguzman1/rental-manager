function Topbar({ title, breadcrumb, onBack, actions }) {
  return (
    <div className="topbar">
      <div className="topbar-left">
        {onBack && (
          <button className="btn-ghost topbar-back" onClick={onBack}>← Volver</button>
        )}
        {breadcrumb && breadcrumb.length > 0 && (
          <div className="topbar-breadcrumb">
            {breadcrumb.map((crumb, i) => (
              <span key={i}>
                {i > 0 && <span className="topbar-breadcrumb-sep"> / </span>}
                {crumb}
              </span>
            ))}
          </div>
        )}
        <h1 className="topbar-title">{title}</h1>
      </div>
      {actions && <div className="topbar-actions">{actions}</div>}
    </div>
  )
}

export default Topbar
