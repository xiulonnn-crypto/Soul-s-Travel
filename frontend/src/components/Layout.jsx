import { useLocation, useNavigate } from 'react-router-dom'
import {
  HomeOutlined,
  SendOutlined,
  FieldTimeOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import './Layout.css'

const NAV_ITEMS = [
  { key: '/', icon: <HomeOutlined />, label: '首页' },
  { key: '/trips', icon: <SendOutlined />, label: '行程' },
  { key: '/timeline', icon: <FieldTimeOutlined />, label: '时间线' },
  { key: '/stats', icon: <BarChartOutlined />, label: '统计' },
]

export default function Layout({ children }) {
  const location = useLocation()
  const navigate = useNavigate()
  const current = '/' + (location.pathname.split('/')[1] || '')

  return (
    <div className="app-shell">
      <nav className="sidebar">
        <div className="sidebar-logo" onClick={() => navigate('/')}>S</div>
        {NAV_ITEMS.map(item => (
          <div
            key={item.key}
            className={`nav-btn ${current === item.key ? 'active' : ''}`}
            onClick={() => navigate(item.key)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </div>
        ))}
      </nav>
      <main className="main-content">{children}</main>
    </div>
  )
}
