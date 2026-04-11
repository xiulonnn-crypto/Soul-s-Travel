import { useEffect, useState } from 'react'
import { statsApi } from '../services/api'
import { CategoryPie, TripExpenseBar, PerDayTrend, DestinationRank } from '../components/StatsChart'
import './Stats.css'

export default function Stats() {
  const [overview, setOverview] = useState(null)
  const [destinations, setDestinations] = useState(null)
  const [expenses, setExpenses] = useState(null)

  useEffect(() => {
    statsApi.overview().then(setOverview).catch(() => {})
    statsApi.destinations().then(setDestinations).catch(() => {})
    statsApi.expenses().then(setExpenses).catch(() => {})
  }, [])

  return (
    <div className="stats-page">
      <h1 className="page-title">生涯<span className="hl">统计</span></h1>
      <p className="page-sub">你的旅行数据全览</p>

      {overview && (
        <div className="stats-overview">
          <div className="stats-num"><div className="n">{overview.total_trips}</div><div className="l">旅行次数</div></div>
          <div className="stats-num"><div className="n">{overview.total_days}</div><div className="l">总天数</div></div>
          <div className="stats-num"><div className="n">{overview.total_countries}</div><div className="l">国家</div></div>
          <div className="stats-num"><div className="n">{overview.total_cities}</div><div className="l">城市</div></div>
          <div className="stats-num"><div className="n">¥{(overview.total_expense/1000).toFixed(0)}K</div><div className="l">总花费</div></div>
          <div className="stats-num"><div className="n">¥{(overview.avg_expense_per_trip/1000).toFixed(1)}K</div><div className="l">次均花费</div></div>
        </div>
      )}

      <div className="chart-row">
        {destinations && (
          <div className="chart-card">
            <h3 className="chart-card-title">🌍 国家访问排名</h3>
            <DestinationRank data={destinations.countries} label="国家" />
          </div>
        )}
        {expenses && (
          <div className="chart-card">
            <h3 className="chart-card-title">💰 开销类别占比</h3>
            <CategoryPie data={expenses.by_category} />
          </div>
        )}
      </div>

      <div className="chart-row">
        {expenses && (
          <div className="chart-card">
            <h3 className="chart-card-title">📊 各旅行花费对比</h3>
            <TripExpenseBar data={expenses.by_trip} />
          </div>
        )}
        {expenses && (
          <div className="chart-card">
            <h3 className="chart-card-title">📈 人均日消费趋势</h3>
            <PerDayTrend data={expenses.per_day_trend} />
          </div>
        )}
      </div>
    </div>
  )
}
