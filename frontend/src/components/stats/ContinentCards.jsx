const CONTINENT_META = {
  '亚洲': { icon: '🌏', accent: '#0099ff' },
  '欧洲': { icon: '🏰', accent: '#af52de' },
  '北美洲': { icon: '🗽', accent: '#ff9500' },
  '南美洲': { icon: '🌴', accent: '#34c759' },
  '非洲': { icon: '🦁', accent: '#ff6b8a' },
  '大洋洲': { icon: '🏝️', accent: '#00c7be' },
  '其他': { icon: '🧭', accent: '#8e99a4' },
}

export default function ContinentCards({ data }) {
  if (!data || data.length === 0) {
    return <div className="stats-empty">暂无大洲数据</div>
  }
  return (
    <div className="continent-cards">
      {data.map((item) => {
        const meta = CONTINENT_META[item.continent] || CONTINENT_META['其他']
        return (
          <div key={item.continent} className="continent-card">
            <div className="continent-icon" style={{ background: `${meta.accent}1a` }}>
              <span>{meta.icon}</span>
            </div>
            <div className="continent-body">
              <div className="continent-name">{item.continent}</div>
              <div className="continent-stats">
                <b>{item.country_count}</b> 国 · <b>{item.trip_count}</b> 次
              </div>
              <div className="continent-countries" title={item.countries.join(' · ')}>
                {item.countries.slice(0, 4).join(' · ')}
                {item.countries.length > 4 ? ` +${item.countries.length - 4}` : ''}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
