import { useNavigate } from 'react-router-dom'
import { EnvironmentOutlined } from '@ant-design/icons'
import { formatTripDateRange } from '../utils/formatTripDateRange'
import './TripCard.css'

const THEMES = [
  { bg: 'bg-blue',   accent: '#0099ff', spine: 'linear-gradient(to bottom, #60b4ff, #0099ff)', days: 'linear-gradient(to right, #60b4ff, #0099ff)' },
  { bg: 'bg-green',  accent: '#34c759', spine: 'linear-gradient(to bottom, #6ee89a, #34c759)', days: 'linear-gradient(to right, #6ee89a, #34c759)' },
  { bg: 'bg-yellow', accent: '#f59e0b', spine: 'linear-gradient(to bottom, #fbbf24, #f59e0b)', days: 'linear-gradient(to right, #fbbf24, #f59e0b)' },
  { bg: 'bg-pink',   accent: '#ec4899', spine: 'linear-gradient(to bottom, #f472b6, #ec4899)', days: 'linear-gradient(to right, #f472b6, #ec4899)' },
  { bg: 'bg-purple', accent: '#a855f7', spine: 'linear-gradient(to bottom, #c084fc, #a855f7)', days: 'linear-gradient(to right, #c084fc, #a855f7)' },
]

function stampClass(score) {
  if (score >= 80) return 'stamp-green'
  if (score >= 60) return 'stamp-yellow'
  return 'stamp-red'
}

export default function TripCard({ trip, index = 0 }) {
  const navigate = useNavigate()
  const theme = THEMES[index % THEMES.length]

  const days = Math.max(
    1,
    Math.ceil((new Date(trip.end_date) - new Date(trip.start_date)) / 86400000)
  )

  const destination = trip.destination_label || ''
  const legCount = trip.leg_count || 0
  const expense = trip.total_expense || 0
  const score = trip.evaluation_score ?? null

  const year = new Date(trip.start_date).getFullYear()
  const dateStr = formatTripDateRange(trip.start_date, trip.end_date)

  return (
    <div
      className="trip-card-wrapper"
      style={{ '--anim-delay': `${index * 0.2}s` }}
    >
      <div
        className={`trip-card ${theme.bg}`}
        onClick={() => navigate(`/trips/${trip.id}`)}
      >
        {/* 书脊 */}
        <div className="card-spine" style={{ background: theme.spine }} />

        {/* 上段：标题行 + 目的地 */}
        <div className="card-top">
          <div className="card-title-row">
            <h3 className="card-title">{trip.title}</h3>
            <span className="card-days" style={{ background: theme.days }}>
              {days}天
            </span>
          </div>
          {destination && (
            <div className="card-dest" style={{ color: theme.accent }}>
              <EnvironmentOutlined />
              <span>{destination}</span>
              {legCount > 0 && <span className="card-leg">{legCount}地</span>}
            </div>
          )}
        </div>

        {/* 中段：评价印章（居中） */}
        <div className="card-middle">
          {score !== null && (
            <div className={`card-stamp ${stampClass(score)}`}>
              <span className="stamp-score">{score}</span>
              <span className="stamp-label">SCORE</span>
            </div>
          )}
        </div>

        {/* 下段：日期 + 花费 */}
        <div className="card-bottom">
          <span className="card-date">
            {year}<br />{dateStr}
          </span>
          {expense > 0 && (
            <span className="card-expense">
              ¥{expense >= 10000 ? (expense / 10000).toFixed(1) + 'w' : expense.toLocaleString()}
            </span>
          )}
        </div>

        {/* 悬停效果层 */}
        <div className="card-hover-overlay" />
        <div className="card-edge-shimmer" />
      </div>
    </div>
  )
}
