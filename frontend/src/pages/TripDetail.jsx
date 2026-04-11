import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Tag, message } from 'antd'
import { EditOutlined, ShareAltOutlined } from '@ant-design/icons'
import { tripApi } from '../services/api'
import ExpenseTable from '../components/ExpenseTable'
import './TripDetail.css'

const ITEM_ICONS = { transport: '✈️', spot: '🏛', hotel: '🏨', food: '🍽' }

function DayBlock({ day }) {
  return (
    <div className="day-block">
      <div className="day-anchor">📅 Day {day.day_number} · {day.date}</div>
      <div className="day-items-list">
        {day.transport.map((t, i) => (
          <div key={`t${i}`} className="day-item">
            <div className="item-icon transport">✈️</div>
            <div className="item-text"><div className="item-name">{t}</div></div>
          </div>
        ))}
        {day.activities.map((a, i) => (
          <div key={`a${i}`} className="day-item">
            <div className="item-icon spot">🏛</div>
            <div className="item-text"><div className="item-name">{a}</div></div>
          </div>
        ))}
        {day.accommodation && (
          <div className="day-item">
            <div className="item-icon hotel">🏨</div>
            <div className="item-text"><div className="item-name">{day.accommodation}</div></div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function TripDetail() {
  const { id } = useParams()
  const [trip, setTrip] = useState(null)
  const navigate = useNavigate()

  useEffect(() => { tripApi.get(id).then(setTrip).catch(() => {}) }, [id])

  if (!trip) return <div className="loading">加载中...</div>

  const handleShare = async () => {
    const { share_token } = await tripApi.createShare(trip.id)
    message.success(`分享链接: ${window.location.origin}/share/${share_token}`)
  }

  return (
    <div className="detail-page">
      <div className="detail-hero">
        <h1 className="detail-title">{trip.title}</h1>
        <div className="detail-chips">
          <Tag color="blue">📅 {trip.start_date} ~ {trip.end_date}</Tag>
          <Tag color="green">👥 {trip.traveler_count}人</Tag>
          <Tag color="cyan">{trip.status}</Tag>
        </div>
        <div className="detail-actions">
          <Button type="primary" shape="round" icon={<EditOutlined />}
                  onClick={() => navigate(`/trips/${trip.id}/edit`)}>编辑</Button>
          <Button shape="round" icon={<ShareAltOutlined />} onClick={handleShare}>分享</Button>
        </div>
      </div>

      <div className="detail-body">
        <div className="detail-main">
          {trip.legs && trip.legs.map((leg, i) => (
            <div key={leg.id} className="leg-section card">
              <div className="leg-header">
                <div className="leg-badge">{i + 1}</div>
                <div>
                  <div className="leg-title">{leg.city}</div>
                  <div className="leg-dates">{leg.start_date} ~ {leg.end_date}</div>
                </div>
              </div>
              {leg.days && leg.days.map(day => <DayBlock key={day.id} day={day} />)}
            </div>
          ))}
        </div>

        <div className="detail-sidebar">
          <ExpenseTable expenses={trip.expenses} travelerCount={trip.traveler_count} />
        </div>
      </div>
    </div>
  )
}
