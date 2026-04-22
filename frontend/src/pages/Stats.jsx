import { useEffect, useState } from 'react'
import { statsApi } from '../services/api'
import { CategoryPie, TripExpenseBar, PerDayTrend, DestinationRank, YearExpenseBar } from '../components/StatsChart'
import StatsHero from '../components/stats/StatsHero'
import OverviewCards from '../components/stats/OverviewCards'
import WorldFootprintMap from '../components/stats/WorldFootprintMap'
import ContinentCards from '../components/stats/ContinentCards'
import HighlightTimeline from '../components/stats/HighlightTimeline'
import MonthDistribution from '../components/stats/MonthDistribution'
import CompanionPie from '../components/stats/CompanionPie'
import CountryExpenseBar from '../components/stats/CountryExpenseBar'
import './Stats.css'

function Section({ title, desc, children }) {
  return (
    <section className="stats-section">
      <div className="stats-section-head">
        <h2 className="stats-section-title">{title}</h2>
        {desc && <span className="stats-section-desc">{desc}</span>}
      </div>
      {children}
    </section>
  )
}

export default function Stats() {
  const [overview, setOverview] = useState(null)
  const [destinations, setDestinations] = useState(null)
  const [expenses, setExpenses] = useState(null)
  const [highlights, setHighlights] = useState(null)
  const [timeline, setTimeline] = useState(null)

  useEffect(() => {
    statsApi.overview().then(setOverview).catch(() => {})
    statsApi.destinations().then(setDestinations).catch(() => {})
    statsApi.expenses().then(setExpenses).catch(() => {})
    statsApi.highlights().then(setHighlights).catch(() => {})
    statsApi.timeline().then(setTimeline).catch(() => {})
  }, [])

  return (
    <div className="stats-page">
      <StatsHero overview={overview} />
      <OverviewCards overview={overview} />

      <Section title="世界足迹" desc="你已踏足的版图">
        {destinations && (
          <div className="world-grid">
            <div className="chart-card map-card">
              <WorldFootprintMap countries={destinations.countries} />
            </div>
            <div className="continent-column">
              <ContinentCards data={destinations.by_continent} />
            </div>
          </div>
        )}
      </Section>

      <Section title="旅行之最" desc="那些写进记忆的片段">
        {highlights && <HighlightTimeline data={highlights} />}
      </Section>

      <Section title="时间画像" desc="什么时候爱出发">
        <div className="chart-row">
          {expenses && expenses.by_year && (
            <div className="chart-card">
              <h3 className="chart-card-title">年度开销</h3>
              <YearExpenseBar data={expenses.by_year} />
            </div>
          )}
          {timeline && (
            <div className="chart-card">
              <h3 className="chart-card-title">月份出行分布</h3>
              <MonthDistribution data={timeline.by_month} />
            </div>
          )}
        </div>
      </Section>

      <Section title="同行画像" desc="和谁一起去的">
        <div className="chart-row">
          {timeline && (
            <div className="chart-card">
              <h3 className="chart-card-title">独行 / 结伴 / 家庭</h3>
              <CompanionPie data={timeline.by_companion} />
            </div>
          )}
          {destinations && (
            <div className="chart-card">
              <h3 className="chart-card-title">国家访问 top</h3>
              <DestinationRank data={destinations.countries} label="国家" />
            </div>
          )}
        </div>
      </Section>

      <Section title="开销洞察" desc="钱花在了哪里">
        <div className="chart-row">
          {expenses && (
            <div className="chart-card">
              <h3 className="chart-card-title">开销类别占比</h3>
              <CategoryPie data={expenses.by_category} />
            </div>
          )}
          {expenses && expenses.by_country && (
            <div className="chart-card">
              <h3 className="chart-card-title">各国花费 top</h3>
              <CountryExpenseBar data={expenses.by_country} />
            </div>
          )}
        </div>
        <div className="chart-row">
          {expenses && (
            <div className="chart-card">
              <h3 className="chart-card-title">各旅行花费对比</h3>
              <TripExpenseBar data={expenses.by_trip} />
            </div>
          )}
          {expenses && (
            <div className="chart-card">
              <h3 className="chart-card-title">人均日消费趋势</h3>
              <PerDayTrend data={expenses.per_day_trend} />
            </div>
          )}
        </div>
      </Section>
    </div>
  )
}
