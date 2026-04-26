export function formatCLP(n) {
  if (!n) return '—'
  return '$' + n.toLocaleString('es-CL')
}

export function daysUntil(isoDate) {
  if (!isoDate) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(isoDate)
  target.setHours(0, 0, 0, 0)
  return Math.round((target - today) / 86400000)
}

export function formatFrequency(freq) {
  if (!freq) return '—'
  if (freq === 'annual') return 'IPC anual'
  if (freq === 'semiannual') return 'IPC semestral'
  return freq
}

export function formatMonthsAgo(n) {
  if (n === null || n === undefined) return '—'
  if (n === 0) return 'este mes'
  if (n === 1) return 'hace 1 mes'
  return `hace ${n} meses`
}

export function formatMonthsUntil(n) {
  if (n === null || n === undefined) return '—'
  if (n === 0) return 'este mes'
  if (n > 0) return n === 1 ? 'en 1 mes' : `en ${n} meses`
  const abs = Math.abs(n)
  return abs === 1 ? 'vencido hace 1 mes' : `vencido hace ${abs} meses`
}

export function formatTenancyYears(years) {
  if (years === null || years === undefined) return '—'
  if (years === 0) return '< 1 año'
  if (years === 1) return '1 año'
  return `${years} años`
}
