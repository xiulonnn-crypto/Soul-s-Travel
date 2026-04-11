import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Input, Segmented } from 'antd'
import { PlusOutlined, SearchOutlined, UserOutlined } from '@ant-design/icons'
import { tripApi } from '../services/api'
import TripCard from '../components/TripCard'
import ProfileDrawer from '../components/ProfileDrawer'
import './TripList.css'

export default function TripList() {
  const [trips, setTrips] = useState([])
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [profileOpen, setProfileOpen] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const params = {}
    if (status) params.status = status
    if (search) params.search = search
    tripApi.list(params).then(setTrips).catch(() => {})
  }, [status, search])

  return (
    <div className="triplist-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">我的<span className="hl">行程</span></h1>
          <p className="page-sub">共 {trips.length} 次旅行</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button shape="round" icon={<UserOutlined />} onClick={() => setProfileOpen(true)}>个人背景</Button>
          <Button type="primary" shape="round" icon={<PlusOutlined />}
                  onClick={() => navigate('/trips/new')}>
            新建行程
          </Button>
        </div>
      </div>
      <ProfileDrawer open={profileOpen} onClose={() => setProfileOpen(false)} />

      <div className="filter-bar">
        <Segmented
          value={status || '全部'}
          onChange={v => setStatus(v === '全部' ? '' : v)}
          options={['全部', 'completed', 'planned']}
        />
        <Input
          prefix={<SearchOutlined />}
          placeholder="搜索目的地..."
          style={{ width: 200, borderRadius: 50 }}
          value={search}
          onChange={e => setSearch(e.target.value)}
          allowClear
        />
      </div>

      <div className="trip-list">
        {trips.map((trip, i) => (
          <TripCard key={trip.id} trip={trip} index={i} />
        ))}
        {trips.length === 0 && (
          <div className="empty-state">没有找到行程</div>
        )}
      </div>
    </div>
  )
}
