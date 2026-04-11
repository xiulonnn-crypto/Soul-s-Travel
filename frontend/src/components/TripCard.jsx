import { useNavigate } from 'react-router-dom'
import './TripCard.css'

const BG_COLORS = ['bg-green', 'bg-yellow', 'bg-blue', 'bg-pink', 'bg-purple']

export default function TripCard({ trip, index = 0 }) {
  const navigate = useNavigate()
  const bgClass = BG_COLORS[index % BG_COLORS.length]
  const days = Math.max(
    1,
    Math.ceil((new Date(trip.end_date) - new Date(trip.start_date)) / 86400000)
  )
  const legCount = trip.legs ? trip.legs.length : 0
  const cities = trip.legs
    ? trip.legs.map(l => l.city).join(' → ')
    : ''

  return (
    <div className={`trip-card ${bgClass}`} onClick={() => navigate(`/trips/${trip.id}`)}>
      <div className="tc-info">
        <div className="tc-title">{trip.title}</div>
        <div className="tc-meta">
          {trip.start_date} 至 {trip.end_date}  
          <b>{days}天</b>
          {legCount > 0 && <><br />{legCount}个城市 &middot; {cities}</>}
        </div>
        {trip.total_expense > 0 && (
          <div className="tc-cost">¥{trip.total_expense.toLocaleString()}</div>
        )}
      </div>
    </div>
  )
}
