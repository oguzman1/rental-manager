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

export function nextMissingPeriod(payments) {
  const existing = new Set((payments || []).map((p) => p.period))
  const now = new Date()
  let year = now.getFullYear()
  let month = now.getMonth() + 1

  for (let i = 0; i < 24; i++) {
    const period = `${year}-${String(month).padStart(2, '0')}`
    if (!existing.has(period)) return period
    month += 1
    if (month > 12) {
      month = 1
      year += 1
    }
  }

  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

const MONTHS_ES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

export function formatPeriod(period) {
  if (!period) return 'Sin período'
  const [year, month] = period.split('-').map(Number)
  if (!year || !month || month < 1 || month > 12) return period
  return `A ${MONTHS_ES[month - 1]} del ${year}`
}

export function contractDuration(startDateStr) {
  if (!startDateStr) return null

  const [y, m, d] = startDateStr.split('-').map(Number)
  if (!y || !m || !d) return null

  const start = new Date(y, m - 1, d)
  if (Number.isNaN(start.getTime())) return null

  const now = new Date()
  let years = now.getFullYear() - start.getFullYear()
  let months = now.getMonth() - start.getMonth()

  if (months < 0) {
    years -= 1
    months += 12
  }

  if (years < 0) return null
  if (years === 0 && months === 0) return '< 1 mes'

  const parts = []
  if (years > 0) parts.push(`${years} año${years > 1 ? 's' : ''}`)
  if (months > 0) parts.push(`${months} mes${months > 1 ? 'es' : ''}`)

  return parts.join(' ')
}