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

export function nextMissingPeriod(payments) {
  const existing = new Set(payments.map((p) => p.period))
  const now = new Date()
  let year = now.getFullYear()
  let month = now.getMonth() + 1

  for (let i = 0; i < 24; i++) {
    const period = `${year}-${String(month).padStart(2, '0')}`
    if (!existing.has(period)) return period
    month++
    if (month > 12) { month = 1; year++ }
  }

  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

export function contractDuration(startDateStr) {
  if (!startDateStr) return null
  const [y, m, d] = startDateStr.split('-').map(Number)
  if (!y || !m || !d) return null
  const start = new Date(y, m - 1, d)
  if (isNaN(start.getTime())) return null

  const now = new Date()
  let years = now.getFullYear() - start.getFullYear()
  let months = now.getMonth() - start.getMonth()

  if (months < 0) {
    years -= 1
    months += 12
  }

  if (years < 0) return null
  if (years === 0 && months === 0) return '< 1 mes'

  const chunks = []
  if (years > 0) chunks.push(`${years} año${years > 1 ? 's' : ''}`)
  if (months > 0) chunks.push(`${months} mes${months > 1 ? 'es' : ''}`)
  return chunks.join(' ')
}
