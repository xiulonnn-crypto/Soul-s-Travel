import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Tag, message, Tabs, Modal } from 'antd'
import { EditOutlined, ShareAltOutlined, DeleteOutlined, ExclamationCircleOutlined } from '@ant-design/icons'
import { tripApi } from '../services/api'
import ExpenseTable from '../components/ExpenseTable'
import TripEvaluation from '../components/TripEvaluation'
import './TripDetail.css'

const CAT_COLORS = { '交通': '#0099ff', '住宿': '#af52de', '餐饮': '#ff9500', '门票': '#34c759', '购物': '#ff6b8a', '其他': '#8e99a4' }
const CAT_ICONS = { '交通': '✈️', '住宿': '🏨', '餐饮': '🍽', '门票': '🎟', '购物': '🛍', '其他': '💳' }

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

function ExpenseDetail({ expenses = [], travelerCount = 1 }) {
  const sorted = [...expenses].sort((a, b) => a.date.localeCompare(b.date))
  return (
    <div className="expense-detail-tab">
      <div className="expense-items-list">
        {sorted.map((e) => (
          <div key={e.id} className="expense-detail-item">
            <div className="edi-icon" style={{ background: (CAT_COLORS[e.category] || '#8e99a4') + '18' }}>
              <span>{CAT_ICONS[e.category] || '💳'}</span>
            </div>
            <div className="edi-info">
              <div className="edi-desc">{e.description || e.category}</div>
              <div className="edi-date">{e.date}</div>
            </div>
            <div className="edi-cat" style={{ color: CAT_COLORS[e.category] || '#8e99a4' }}>{e.category}</div>
            <div className="edi-amount">¥{e.amount.toLocaleString()}</div>
          </div>
        ))}
      </div>
      <div className="expense-summary-footer">
        <ExpenseTable expenses={expenses} travelerCount={travelerCount} />
      </div>
    </div>
  )
}

export default function TripDetail() {
  const { id } = useParams()
  const [trip, setTrip] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    tripApi.get(id).then(setTrip).catch(() => {})
  }, [id])

  if (!trip) return <div className="loading">加载中...</div>

  const handleShare = async () => {
    const { share_token } = await tripApi.createShare(trip.id)
    message.success(`分享链接: ${window.location.origin}/share/${share_token}`)
  }

  const handleDelete = () => {
    Modal.confirm({
      title: '确认删除',
      icon: <ExclamationCircleOutlined />,
      content: `确定要删除行程「${trip.title}」吗？删除后将不再显示。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        await tripApi.delete(trip.id)
        message.success('行程已删除')
        navigate('/')
      },
    })
  }

  const itineraryTab = (
    <div className="detail-itinerary">
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
  )

  const tabItems = [
    { key: 'itinerary', label: '行程', children: itineraryTab },
    {
      key: 'expenses',
      label: '开销明细',
      children: <ExpenseDetail expenses={trip.expenses} travelerCount={trip.traveler_count} />
    },
    {
      key: 'evaluation',
      label: '行程评价',
      children: <TripEvaluation tripId={trip.id} trip={trip} />
    },
  ]

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
          <Button shape="round" danger icon={<DeleteOutlined />} onClick={handleDelete}>删除</Button>
        </div>
      </div>

      <Tabs defaultActiveKey="itinerary" items={tabItems} className="detail-tabs" />
    </div>
  )
}
