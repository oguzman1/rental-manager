import { NoticeBadge } from './Badge'

const BUCKET_LABELS = {
  overdue:      'Atrasados',
  today:        'Hoy',
  next_7_days:  'Esta semana',
  next_30_days: 'Este mes',
}

const BUCKET_ORDER = ['overdue', 'today', 'next_7_days', 'next_30_days']

function NoticesPanel({ notices, onSelect }) {
  if (notices.length === 0) {
    return (
      <aside className="notices-panel">
        <div className="notices-header">
          <span className="notices-title">Avisos de reajuste</span>
        </div>
        <div className="notices-empty">
          Sin avisos pendientes en los próximos 30 días.
        </div>
      </aside>
    )
  }

  const grouped = BUCKET_ORDER.reduce((acc, bucket) => {
    const items = notices.filter((n) => n.bucket === bucket)
    if (items.length > 0) acc[bucket] = items
    return acc
  }, {})

  return (
    <aside className="notices-panel">
      <div className="notices-header">
        <span className="notices-title">Avisos de reajuste</span>
        <span className="notices-count">{notices.length}</span>
      </div>

      {Object.entries(grouped).map(([bucket, items]) => (
        <div key={bucket} className="notices-group">
          <div className="notices-group-label">{BUCKET_LABELS[bucket]}</div>
          {items.map((notice) => (
            <NoticeCard
              key={notice.id}
              notice={notice}
              onClick={() => onSelect(notice)}
            />
          ))}
        </div>
      ))}
    </aside>
  )
}

function NoticeCard({ notice, onClick }) {
  return (
    <div
      className={`notice-card notice-card-${notice.bucket}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      <div className="notice-card-top">
        <span className="notice-card-name">
          {notice.property_label ?? notice.rol}
        </span>
        <NoticeBadge daysUntilNotice={notice.daysUntilNotice} />
      </div>
      {notice.tenant_name && (
        <div className="notice-card-tenant">{notice.tenant_name}</div>
      )}
      <div className="notice-card-date">{notice.adjustment_notice_date}</div>
    </div>
  )
}

export default NoticesPanel
