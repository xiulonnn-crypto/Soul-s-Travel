import { useEffect, useState } from 'react'
import { tripApi } from '../services/api'
import TimelineNode from '../components/TimelineNode'
import './Timeline.css'

export default function Timeline() {
  const [trips, setTrips] = useState([])

  useEffect(() => { tripApi.list().then(setTrips).catch(() => {}) }, [])

  const grouped = {}
  trips.forEach(t => {
    const year = t.start_date.slice(0, 4)
    if (!grouped[year]) grouped[year] = []
    grouped[year].push(t)
  })
  const years = Object.keys(grouped).sort((a, b) => b - a)

  return (
    <div className="timeline-page">
      <h1 className="page-title">旅行<span className="hl">时间线</span></h1>
      <p className="page-sub">{trips.length} 次旅行的足迹</p>

      {years.map(year => (
        <div key={year}>
          <div className="tl-year">{year} <span className="yr-badge">{grouped[year].length}次</span></div>
          <div className="tl-track">
            {grouped[year].map(trip => <TimelineNode key={trip.id} trip={trip} />)}
          </div>
        </div>
      ))}

      {trips.length === 0 && <div className="empty-state">还没有行程记录</div>}
    </div>
  )
}
