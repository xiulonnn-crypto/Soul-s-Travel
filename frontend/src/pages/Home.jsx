import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { tripApi, statsApi } from '../services/api'
import TripCard from '../components/TripCard'
import './Home.css'

export default function Home() {
  const [trips, setTrips] = useState([])
  const [overview, setOverview] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    tripApi.list().then(setTrips).catch(() => {})
    statsApi.overview().then(setOverview).catch(() => {})
  }, [])

  return (
    <div className="home-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">我的<span className="hl">旅行世界</span></h1>
          <p className="page-sub">记录每一段旅程，让回忆有迹可循</p>
        </div>
        <Button type="primary" shape="round" icon={<PlusOutlined />}
                onClick={() => navigate('/trips/new')}>
          新建行程
        </Button>
      </div>

      {overview && (
        <div className="stat-row">
          <div className="stat-pill"><div className="stat-icon blue">✈️</div><div><div className="stat-val">{overview.total_trips}</div><div className="stat-label">旅行次数</div></div></div>
          <div className="stat-pill"><div className="stat-icon green">🌍</div><div><div className="stat-val">{overview.total_countries}</div><div className="stat-label">去过的国家</div></div></div>
          <div className="stat-pill"><div className="stat-icon orange">📅</div><div><div className="stat-val">{overview.total_days}</div><div className="stat-label">旅行天数</div></div></div>
          <div className="stat-pill"><div className="stat-icon purple">💰</div><div><div className="stat-val">¥{(overview.total_expense/1000).toFixed(0)}K</div><div className="stat-label">总花费</div></div></div>
        </div>
      )}

      <div className="sec-head">
        <h2 className="sec-title">最近行程</h2>
      </div>
      <div className="trip-list">
        {trips.slice(0, 5).map((trip, i) => (
          <TripCard key={trip.id} trip={trip} index={i} />
        ))}
        {trips.length === 0 && (
          <div className="empty-state">还没有行程记录，点击右上角开始创建</div>
        )}
      </div>
    </div>
  )
}
