import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Tag } from 'antd'
import { shareApi } from '../services/api'
import './TripDetail.css'

export default function ShareView() {
  const { token } = useParams()
  const [trip, setTrip] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    shareApi.get(token).then(setTrip).catch(() => setError(true))
  }, [token])

  if (error) return <div style={{ padding: 60, textAlign: 'center' }}>行程不存在或已取消分享</div>
  if (!trip) return <div className="loading">加载中...</div>

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: '40px 24px' }}>
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <div style={{ color: '#0099ff', fontWeight: 700, fontSize: 15, marginBottom: 8 }}>Soul's Travel</div>
        <h1 style={{ fontSize: 28, fontWeight: 800, marginBottom: 12 }}>{trip.title}</h1>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
          <Tag color="blue">📅 {trip.start_date} ~ {trip.end_date}</Tag>
          <Tag color="green">{trip.traveler_count}人</Tag>
        </div>
      </div>

      {trip.legs && trip.legs.map((leg, i) => (
        <div key={leg.id} className="leg-section card" style={{ marginBottom: 14 }}>
          <div className="leg-header">
            <div className="leg-badge">{i + 1}</div>
            <div>
              <div className="leg-title">{leg.city}</div>
              <div className="leg-dates">{leg.start_date} ~ {leg.end_date}</div>
            </div>
          </div>
          {leg.days && leg.days.map(day => (
            <div key={day.id} className="day-block">
              <div className="day-anchor" style={{ fontSize: 12, padding: '4px 12px' }}>Day {day.day_number} · {day.date}</div>
              <div className="day-items-list">
                {day.transport.map((t, j) => (
                  <div key={j} className="day-item"><div className="item-icon transport">✈️</div><div className="item-name">{t}</div></div>
                ))}
                {day.activities.map((a, j) => (
                  <div key={j} className="day-item"><div className="item-icon spot">🏛</div><div className="item-name">{a}</div></div>
                ))}
                {day.accommodation && (
                  <div className="day-item"><div className="item-icon hotel">🏨</div><div className="item-name">{day.accommodation}</div></div>
                )}
              </div>
            </div>
          ))}
        </div>
      ))}

      <div style={{ textAlign: 'center', padding: 32, borderTop: '1px solid #e5e8ed', marginTop: 16, color: '#8e99a4', fontSize: 12 }}>
        Soul's Travel &middot; 记录旅行，让回忆有迹可循
      </div>
    </div>
  )
}
