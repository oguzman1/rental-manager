function DashboardFilters({
  statusFilter,
  setStatusFilter,
  adjustmentFilter,
  setAdjustmentFilter,
  searchText,
  setSearchText,
  onClear,
}) {
  return (
    <div className="dashboard-filters">
      <label>
        Estado:{' '}
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="all">Todos</option>
          <option value="occupied">Arrendadas</option>
          <option value="vacant">Vacías</option>
        </select>
      </label>

      <label>
        Aviso de reajuste:{' '}
        <select value={adjustmentFilter} onChange={(e) => setAdjustmentFilter(e.target.value)}>
          <option value="all">Todos</option>
          <option value="notice_required">Solo requieren aviso</option>
        </select>
      </label>

      <label>
        Buscar:{' '}
        <input
          type="text"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          placeholder="Rol o comuna..."
        />
      </label>

      <button onClick={onClear}>Limpiar filtros</button>
    </div>
  )
}

export default DashboardFilters
