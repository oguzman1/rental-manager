function DashboardFilters({
  statusFilter,
  setStatusFilter,
  adjustmentFilter,
  setAdjustmentFilter,
  searchText,
  setSearchText,
  onClear,
  resultCount,
  totalCount,
}) {
  const hasActiveFilters =
    statusFilter !== 'all' || adjustmentFilter !== 'all' || searchText !== ''

  return (
    <div className="table-filters">
      <div className="filter-chips">
        <FilterChip
          label="Estado"
          value={statusFilter}
          onChange={setStatusFilter}
          options={[
            { value: 'all',      label: 'Todos' },
            { value: 'occupied', label: 'Arrendadas' },
            { value: 'vacant',   label: 'Vacantes' },
          ]}
        />
        <FilterChip
          label="Aviso"
          value={adjustmentFilter}
          onChange={setAdjustmentFilter}
          options={[
            { value: 'all',    label: 'Todos' },
            { value: 'notice', label: 'Solo con aviso' },
          ]}
        />
        <div className="search-input-wrap">
          <input
            type="text"
            placeholder="Buscar rol, comuna, propiedad…"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
        </div>
        {hasActiveFilters && (
          <button className="btn-ghost" onClick={onClear}>
            Limpiar
          </button>
        )}
      </div>
      <span className="filters-count">
        {resultCount} / {totalCount}
      </span>
    </div>
  )
}

function FilterChip({ label, value, onChange, options }) {
  return (
    <div className="filter-chip">
      <span className="filter-chip-label">{label}:</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}

export default DashboardFilters
