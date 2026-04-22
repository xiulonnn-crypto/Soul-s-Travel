function fmtK(num) {
  if (num == null) return '—'
  if (num >= 10000) return `¥${(num / 1000).toFixed(0)}K`
  if (num >= 1000) return `¥${(num / 1000).toFixed(1)}K`
  return `¥${Math.round(num)}`
}

export default function OverviewCards({ overview }) {
  if (!overview) return null
  const cards = [
    { n: overview.total_trips, l: '旅行次数' },
    { n: overview.total_days, l: '总天数' },
    { n: overview.total_countries, l: '国家' },
    { n: overview.total_cities, l: '城市' },
    { n: `${overview.world_coverage}%`, l: '解锁地球' },
    { n: fmtK(overview.total_expense), l: '总花费' },
    { n: fmtK(overview.avg_expense_per_trip), l: '次均花费' },
  ]
  return (
    <div className="stats-overview">
      {cards.map((c, i) => (
        <div key={i} className="stats-num">
          <div className="n">{c.n}</div>
          <div className="l">{c.l}</div>
        </div>
      ))}
    </div>
  )
}
