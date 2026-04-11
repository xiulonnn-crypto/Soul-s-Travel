import { useEffect, useState } from 'react'
import { Button, Spin, message } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { evaluationApi } from '../services/api'
import './TripEvaluation.css'

const DIM_META = {
  cost:          { icon: '💰', color: '#34c759' },
  pace:          { icon: '🏃', color: '#ff9500' },
  accommodation: { icon: '🏨', color: '#0099ff' },
  transport:     { icon: '✈️', color: '#af52de' },
  attractions:   { icon: '🎯', color: '#ff6b8a' },
}

function ScoreRing({ score }) {
  const pct = Math.min(score, 100)
  return (
    <div className="eval-ring" style={{ background: `conic-gradient(#0099ff ${pct}%, #eef2f7 0)` }}>
      <div className="eval-ring-inner">
        <span className="eval-ring-num">{score}</span>
        <span className="eval-ring-label">/100</span>
      </div>
    </div>
  )
}

function Stars({ score }) {
  const full = Math.round(score / 20)
  return (
    <div className="eval-stars">
      {[1, 2, 3, 4, 5].map(i => (
        <span key={i} className={i <= full ? 'star-on' : 'star-off'}>⭐</span>
      ))}
    </div>
  )
}

function DimensionCard({ dimKey, dim }) {
  const meta = DIM_META[dimKey] || { icon: '📊', color: '#8e99a4' }
  return (
    <div className="eval-dim-card">
      <div className="dim-header">
        <span className="dim-icon-label">{meta.icon} {dim.label}</span>
        <span className="dim-score" style={{ color: meta.color }}>{dim.score}</span>
      </div>
      <div className="dim-bar-track">
        <div className="dim-bar-fill" style={{ width: `${dim.score}%`, background: meta.color }} />
      </div>
      <div className="dim-text">{dim.text}</div>
      {dim.tags && dim.tags.length > 0 && (
        <div className="dim-tags">
          {dim.tags.map((t, i) => (
            <span key={i} className={`eval-tag tag-${t.type}`}>{t.type === 'positive' ? '✓' : '⚠'} {t.text}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function CityCard({ city, index }) {
  const scoreBg = city.score >= 85 ? '#0099ff' : city.score >= 70 ? '#ff9500' : '#ff3b30'
  return (
    <div className="eval-city-card">
      <div className="city-card-header">
        <div className="city-card-left">
          <div className="city-badge">{index + 1}</div>
          <span className="city-name">{city.city}</span>
          <span className="city-meta">{city.days}天 · {city.country}</span>
        </div>
        <div className="city-score-pill" style={{ background: scoreBg }}>{city.score}</div>
      </div>
      <div className="city-card-text">{city.text}</div>
      {city.tags && city.tags.length > 0 && (
        <div className="dim-tags">
          {city.tags.map((t, i) => (
            <span key={i} className={`eval-tag tag-${t.type}`}>{t.type === 'positive' ? '✓' : '⚠'} {t.text}</span>
          ))}
        </div>
      )}
      {city.missed_spots && city.missed_spots.length > 0 && (
        <div className="city-missed">📍 遗漏景点: {city.missed_spots.join('、')}</div>
      )}
    </div>
  )
}

export default function TripEvaluation({ tripId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [regenerating, setRegenerating] = useState(false)

  const fetchEvaluation = () => {
    setLoading(true)
    evaluationApi.get(tripId)
      .then(setData)
      .catch(() => message.error('加载评价失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchEvaluation() }, [tripId])

  const handleRegenerate = () => {
    setRegenerating(true)
    evaluationApi.regenerate(tripId)
      .then(d => { setData(d); message.success('评价已重新生成') })
      .catch(() => message.error('重新生成失败'))
      .finally(() => setRegenerating(false))
  }

  if (loading) {
    return <div className="eval-loading"><Spin size="large" /><p>正在生成行程评价...</p></div>
  }

  if (!data || !data.evaluation_data) {
    return <div className="eval-loading"><p>暂无评价数据</p></div>
  }

  const ev = data.evaluation_data
  const dims = ev.dimensions || {}

  return (
    <div className="eval-container">
      {/* 顶部: 综合评分 */}
      <div className="eval-hero card">
        <ScoreRing score={data.overall_score} />
        <div className="eval-hero-body">
          <div className="eval-hero-title">{ev.summary}</div>
          <Stars score={data.overall_score} />
          <div className="eval-hero-sub">
            综合评分 {data.overall_score} 分 · 生成于 {data.created_at?.slice(0, 10)}
          </div>
        </div>
        <Button
          className="eval-regen-btn"
          icon={<ReloadOutlined />}
          loading={regenerating}
          onClick={handleRegenerate}
        >重新生成</Button>
      </div>

      {/* 中部: 维度评分 */}
      <div className="eval-dims-grid">
        {Object.entries(dims).map(([key, dim]) => (
          <DimensionCard key={key} dimKey={key} dim={dim} />
        ))}
      </div>

      {/* 城市评价 */}
      {ev.cities && ev.cities.length > 0 && (
        <div className="eval-cities card">
          <h3 className="eval-section-title">🏙️ 城市评价</h3>
          {ev.cities.map((city, i) => (
            <CityCard key={i} city={city} index={i} />
          ))}
        </div>
      )}

      {/* 建议 */}
      {ev.suggestions && ev.suggestions.length > 0 && (
        <div className="eval-suggestions card">
          <h3 className="eval-section-title">💡 后续行程建议</h3>
          {ev.suggestions.map((s, i) => (
            <div key={i} className="eval-suggestion-item">{s}</div>
          ))}
        </div>
      )}
    </div>
  )
}
