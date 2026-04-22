const HIGHLIGHT_META = {
  earliest:         { icon: '🎬', title: '最早的一次',   accent: '#0099ff' },
  longest:          { icon: '⏱️', title: '最长的一次',   accent: '#34c759' },
  most_expensive:   { icon: '💎', title: '最贵的一次',   accent: '#ff9500' },
  cheapest_per_day: { icon: '🪶', title: '最省的人均日', accent: '#00c7be' },
  highest_rated:    { icon: '⭐', title: '评分最高',     accent: '#af52de' },
  lowest_rated:     { icon: '🌀', title: '评分最低',     accent: '#8e99a4' },
}

const ORDER = ['earliest', 'longest', 'most_expensive', 'cheapest_per_day', 'highest_rated', 'lowest_rated']

export default function HighlightTimeline({ data }) {
  if (!data) return null
  const items = ORDER.filter(k => data[k]).map(k => ({ key: k, ...data[k] }))
  if (items.length === 0) {
    return <div className="stats-empty">暂无之最数据，去录入一些旅行吧</div>
  }
  return (
    <div className="highlight-grid">
      {items.map((it) => {
        const meta = HIGHLIGHT_META[it.key]
        return (
          <div key={it.key} className="highlight-card">
            <div className="highlight-head">
              <span className="highlight-icon" style={{ background: `${meta.accent}1a`, color: meta.accent }}>{meta.icon}</span>
              <span className="highlight-title">{meta.title}</span>
            </div>
            <div className="highlight-value" style={{ color: meta.accent }}>{it.value}</div>
            <div className="highlight-trip">{it.title}</div>
            {it.destination_label && (
              <div className="highlight-dest">{it.destination_label}</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
