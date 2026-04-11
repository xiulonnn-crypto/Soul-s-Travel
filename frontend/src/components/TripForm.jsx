import { useState, useEffect, useCallback, useRef, Fragment } from 'react'
import { Input, DatePicker, InputNumber, Button, Collapse, Tag } from 'antd'
import dayjs from 'dayjs'
import './TripForm.css'

const NAV_ITEMS = [
  { id: 'basic', label: '基本信息', icon: '📋' },
  { id: 'legs', label: '城市站点', icon: '🏙️' },
  { id: 'expenses', label: '费用明细', icon: '💰' },
]

function ActivityTags({ items }) {
  if (!items || items.length === 0) return <span className="f-empty">—</span>
  return (
    <div className="transport-tags">
      {items.map((item, i) => (
        <Tag key={i} color="cyan" className="transport-tag">{item}</Tag>
      ))}
    </div>
  )
}

function TransportTags({ items }) {
  if (!items || items.length === 0) return <span className="f-empty">—</span>
  return (
    <div className="transport-tags">
      {items.map((item, i) => {
        const colonIdx = item.indexOf(':')
        if (colonIdx > 0 && !/^\d/.test(item)) {
          // Pre-paired "FD531:广州→曼谷"
          const code = item.slice(0, colonIdx)
          const route = item.slice(colonIdx + 1).replace('→', '-')
          return <Tag key={i} color="volcano" className="transport-tag">✈ {code}:{route}</Tag>
        }
        // Route only "曼德勒→蒲甘"
        return <Tag key={i} color="orange" className="transport-tag">{item.replace('→', '-')}</Tag>
      })}
    </div>
  )
}

function HotelTag({ name }) {
  if (!name) return <span className="f-empty">—</span>
  return (
    <div className="transport-tags">
      <Tag color="purple" className="transport-tag">🏨 {name}</Tag>
    </div>
  )
}

export default function TripForm({ data, onSave }) {
  const [form, setForm] = useState({ title: '', start_date: '', end_date: '', traveler_count: 1, description: '', legs: [], expenses: [] })
  const [dirty, setDirty] = useState(new Set())
  const [activeSection, setActiveSection] = useState('basic')

  const basicRef = useRef(null)
  const legsRef = useRef(null)
  const expensesRef = useRef(null)
  const sectionRefs = { basic: basicRef, legs: legsRef, expenses: expensesRef }

  useEffect(() => {
    if (data) {
      setForm(prev => {
        const next = { ...prev }
        Object.keys(data.trip || {}).forEach(k => {
          if (!dirty.has(k)) next[k] = data.trip[k]
        })
        if (!dirty.has('legs') && data.legs) next.legs = data.legs
        if (!dirty.has('expenses') && data.expenses) next.expenses = data.expenses
        return next
      })
    }
  }, [data])

  useEffect(() => {
    const container = basicRef.current?.closest('.editor-form')
    if (!container) return
    const handleScroll = () => {
      const containerTop = container.getBoundingClientRect().top
      let active = 'basic'
      for (const { id } of NAV_ITEMS) {
        const ref = sectionRefs[id]
        if (ref.current) {
          const rect = ref.current.getBoundingClientRect()
          if (rect.top - containerTop <= 72) active = id
        }
      }
      setActiveSection(active)
    }
    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [])

  const scrollToSection = (id) => {
    const container = basicRef.current?.closest('.editor-form')
    const ref = sectionRefs[id]
    if (!container || !ref.current) return
    const containerTop = container.getBoundingClientRect().top
    const sectionTop = ref.current.getBoundingClientRect().top
    container.scrollTo({ top: sectionTop - containerTop + container.scrollTop - 60, behavior: 'smooth' })
  }

  const setField = useCallback((key, value) => {
    setForm(prev => ({ ...prev, [key]: value }))
    setDirty(prev => new Set(prev).add(key))
  }, [])

  const handleSave = () => {
    onSave({
      title: form.title,
      start_date: form.start_date,
      end_date: form.end_date,
      traveler_count: form.traveler_count,
      description: form.description,
      status: 'completed',
      legs: form.legs,
      expenses: form.expenses,
    })
  }

  const legItems = (form.legs || []).map((leg, li) => ({
    key: li,
    label: `🏙️ ${leg.city || `站点 ${li+1}`} (${leg.start_date} ~ ${leg.end_date})`,
    children: (
      <div>
        {(leg.days || []).map((day, di) => (
          <div key={di} className="day-form-block">
            <div className="day-form-label">Day {day.day_number} · {day.date}</div>
            <div className="f-row">
              <div className="f-group">
                <label className="f-label">活动</label>
                <ActivityTags items={day.activities} />
              </div>
            </div>
            <div className="f-row">
              <div className="f-group">
                <label className="f-label">交通</label>
                <TransportTags items={day.transport} />
              </div>
            </div>
            <div className="f-row">
              <div className="f-group">
                <label className="f-label">住宿</label>
                <HotelTag name={day.accommodation} />
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }))

  return (
    <div className="trip-form">
      <div className="form-topbar">
        <nav className="form-nav">
          {NAV_ITEMS.map(({ id, label, icon }, idx) => (
            <Fragment key={id}>
              <button
                className={`form-nav-item${activeSection === id ? ' active' : ''}`}
                onClick={() => scrollToSection(id)}
              >
                <span className="form-nav-dot" />
                <span className="form-nav-label">{icon} {label}</span>
              </button>
              {idx < NAV_ITEMS.length - 1 && <div className="form-nav-connector" />}
            </Fragment>
          ))}
        </nav>
        <Button type="primary" shape="round" onClick={handleSave}>💾 保存行程</Button>
      </div>

      <div ref={basicRef} className="form-block">
        <h4>📋 基本信息</h4>
        <div className="f-row">
          <div className="f-group">
            <label className="f-label">标题</label>
            <Input value={form.title} onChange={e => setField('title', e.target.value)} />
          </div>
          <div className="f-group" style={{ flex: '0 0 100px' }}>
            <label className="f-label">人数</label>
            <InputNumber value={form.traveler_count} min={1} onChange={v => setField('traveler_count', v)} style={{ width: '100%' }} />
          </div>
        </div>
        <div className="f-row">
          <div className="f-group">
            <label className="f-label">开始</label>
            <DatePicker value={form.start_date ? dayjs(form.start_date) : null}
                        onChange={(d, s) => setField('start_date', s)} style={{ width: '100%' }} />
          </div>
          <div className="f-group">
            <label className="f-label">结束</label>
            <DatePicker value={form.end_date ? dayjs(form.end_date) : null}
                        onChange={(d, s) => setField('end_date', s)} style={{ width: '100%' }} />
          </div>
        </div>
      </div>

      {legItems.length > 0 && (
        <div ref={legsRef} className="form-block">
          <h4>🏙️ 城市站点</h4>
          <Collapse items={legItems} defaultActiveKey={[0]} />
        </div>
      )}

      {(form.expenses || []).length > 0 && (
        <div ref={expensesRef} className="form-block">
          <h4>💰 费用明细</h4>
          <div className="expense-table">
            <div className="expense-header">
              <span>类别</span>
              <span>描述</span>
              <span>金额</span>
            </div>
            {(form.expenses || []).map((exp, i) => (
              <div key={i} className="expense-row">
                <span className={`expense-tag tag-${exp.category === '交通' ? 'blue' : exp.category === '住宿' ? 'green' : exp.category === '餐饮' ? 'orange' : 'gray'}`}>
                  {exp.category}
                </span>
                <span className="expense-desc">{exp.description}</span>
                <span className="expense-amount">¥{exp.amount.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}</span>
              </div>
            ))}
            <div className="expense-total">
              <span>合计</span>
              <span></span>
              <span>¥{(form.expenses || []).reduce((s, e) => s + e.amount, 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
