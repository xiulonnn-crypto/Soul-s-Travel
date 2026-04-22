function formatYearMonth(iso) {
  if (!iso) return '—'
  const [y, m] = iso.split('-')
  return `${y} 年 ${parseInt(m, 10)} 月`
}

function yearsSince(iso) {
  if (!iso) return 0
  const start = new Date(iso)
  const now = new Date()
  const diff = (now - start) / (365.25 * 24 * 3600 * 1000)
  return Math.max(Math.floor(diff), 0)
}

export default function StatsHero({ overview }) {
  if (!overview) {
    return <div className="stats-hero stats-hero-skeleton" />
  }
  const firstMonth = formatYearMonth(overview.first_trip_date)
  const years = yearsSince(overview.first_trip_date)
  return (
    <div className="stats-hero">
      <div className="stats-hero-inner">
        <div className="stats-hero-eyebrow">我的旅行人生</div>
        <h1 className="stats-hero-title">
          从 <span className="hero-num">{firstMonth}</span> 出发，<br />
          已走过 <span className="hero-num">{overview.total_trips}</span> 次远方
        </h1>
        <div className="stats-hero-sub">
          {years > 0 && <span>{years} 年旅途 · </span>}
          解锁地球 <b>{overview.world_coverage}%</b> ·
          走过 <b>{overview.total_continents}</b> 个大洲
        </div>
      </div>
    </div>
  )
}
