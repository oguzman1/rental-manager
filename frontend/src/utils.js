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
