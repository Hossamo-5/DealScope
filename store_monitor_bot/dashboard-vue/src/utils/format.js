export const formatNumberAr = (value) => {
  const n = Number(value || 0)
  return new Intl.NumberFormat('ar-SA').format(n)
}

export const parseUtcDate = (value) => {
  if (!value) return null
  if (value instanceof Date) return value
  if (typeof value !== 'string') return new Date(value)

  const normalized = value.endsWith('Z') || value.includes('+')
    ? value
    : `${value}Z`

  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export const formatDateAr = (value) => {
  if (!value) return '—'
  const d = parseUtcDate(value)
  if (!d) return '—'
  return new Intl.DateTimeFormat('ar-SA').format(d)
}

export const formatDateTimeAr = (value) => {
  if (!value) return '—'
  const d = parseUtcDate(value)
  if (!d) return '—'
  return new Intl.DateTimeFormat('ar-SA', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(d)
}

export const timeAgoAr = (value) => {
  const dateUtc = parseUtcDate(value)
  if (!dateUtc) return '—'

  const diff = Date.now() - dateUtc.getTime()
  if (diff < 0) return 'الآن'

  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (seconds < 30) return 'الآن'
  if (seconds < 60) return `منذ ${seconds} ثانية`
  if (minutes < 60) return `منذ ${minutes} دقيقة`
  if (hours < 24) return `منذ ${hours} ساعة`
  if (days < 7) return `منذ ${days} يوم`

  return new Intl.DateTimeFormat('ar-SA', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  }).format(dateUtc)
}
