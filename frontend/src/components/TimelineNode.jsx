import { useNavigate } from 'react-router-dom'

export default function TimelineNode({ trip }) {
  const navigate = useNavigate()
  const cities = trip.legs ? trip.legs.map(l => l.city).join(' → ') : ''

  return (
    <div className="tl-node" onClick={() => navigate(`/trips/${trip.id}`)}>
      <div className="tl-card">
        <div className="tl-card-title">{trip.title}</div>
        {cities && <div className="tl-card-route">{cities}</div>}
        <div className="tl-card-meta">
          <span>{trip.start_date} ~ {trip.end_date}</span>
          <span>{trip.traveler_count}人</span>
        </div>
      </div>
    </div>
  )
}
