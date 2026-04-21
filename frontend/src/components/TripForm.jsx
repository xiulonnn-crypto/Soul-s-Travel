import { useState, useEffect, useCallback, useRef, Fragment } from 'react'
import { Input, DatePicker, InputNumber, Button, Collapse, Tag, Select } from 'antd'
import { EditOutlined, CheckOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import './TripForm.css'

const NAV_ITEMS = [
  { id: 'basic', label: '基本信息', icon: '📋' },
  { id: 'legs', label: '城市站点', icon: '🏙️' },
  { id: 'expenses', label: '费用明细', icon: '💰' },
]

const EXPENSE_CATEGORIES = ['交通', '住宿', '餐饮', '门票', '购物', '其他']

function EditableTagGroup({ items, editing, onRemove, onAdd, color, renderLabel, placeholder }) {
  const [adding, setAdding] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    if (adding && inputRef.current) inputRef.current.focus()
  }, [adding])

  const confirmAdd = () => {
    if (inputValue.trim()) onAdd?.(inputValue.trim())
    setInputValue('')
    setAdding(false)
  }

  const getColor = typeof color === 'function' ? color : () => color
  const getLabel = renderLabel || (item => item)

  if (!editing && (!items || items.length === 0)) return <span className="f-empty">—</span>

  return (
    <div className="transport-tags">
      {(items || []).map((item, i) => (
        <Tag
          key={i}
          color={getColor(item)}
          className="transport-tag"
          closable={editing}
          onClose={e => { e.preventDefault(); onRemove?.(i) }}
        >
          {getLabel(item)}
        </Tag>
      ))}
      {editing && (
        adding ? (
          <Input
            ref={inputRef}
            size="small"
            className="tag-add-input"
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onPressEnter={confirmAdd}
            onBlur={confirmAdd}
            placeholder={placeholder}
          />
        ) : (
          <Tag className="tag-add-btn" onClick={() => setAdding(true)}>
            <PlusOutlined /> 新增
          </Tag>
        )
      )}
    </div>
  )
}

function EditableHotelTag({ name, editing, onRemove, onAdd }) {
  const [adding, setAdding] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    if (adding && inputRef.current) inputRef.current.focus()
  }, [adding])

  const confirmAdd = () => {
    if (inputValue.trim()) onAdd?.(inputValue.trim())
    setInputValue('')
    setAdding(false)
  }

  if (!editing) {
    if (!name) return <span className="f-empty">—</span>
    return (
      <div className="transport-tags">
        <Tag color="purple" className="transport-tag">🏨 {name}</Tag>
      </div>
    )
  }

  return (
    <div className="transport-tags">
      {name && (
        <Tag color="purple" className="transport-tag" closable onClose={e => { e.preventDefault(); onRemove?.() }}>
          🏨 {name}
        </Tag>
      )}
      {!name && (
        adding ? (
          <Input
            ref={inputRef}
            size="small"
            className="tag-add-input"
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onPressEnter={confirmAdd}
            onBlur={confirmAdd}
            placeholder="住宿名称"
          />
        ) : (
          <Tag className="tag-add-btn" onClick={() => setAdding(true)}>
            <PlusOutlined /> 新增
          </Tag>
        )
      )}
    </div>
  )
}

const transportColor = (item) => {
  const colonIdx = item.indexOf(':')
  return (colonIdx > 0 && !/^\d/.test(item)) ? 'volcano' : 'orange'
}

const transportLabel = (item) => {
  const colonIdx = item.indexOf(':')
  if (colonIdx > 0 && !/^\d/.test(item)) {
    const code = item.slice(0, colonIdx)
    const route = item.slice(colonIdx + 1).replace('→', '-')
    return `✈ ${code}:${route}`
  }
  return item.replace('→', '-')
}

export default function TripForm({ data, onSave }) {
  const [form, setForm] = useState({ title: '', start_date: '', end_date: '', traveler_count: 1, description: '', legs: [], expenses: [] })
  const [dirty, setDirty] = useState(new Set())
  const [activeSection, setActiveSection] = useState('basic')
  const [legsEditing, setLegsEditing] = useState(false)
  const [expensesEditing, setExpensesEditing] = useState(false)
  const [newExpense, setNewExpense] = useState(null)

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

  const updateLegDay = useCallback((legIdx, dayIdx, field, value) => {
    setForm(prev => ({
      ...prev,
      legs: prev.legs.map((leg, li) => {
        if (li !== legIdx) return leg
        return {
          ...leg,
          days: (leg.days || []).map((day, di) => {
            if (di !== dayIdx) return day
            return { ...day, [field]: value }
          })
        }
      })
    }))
    setDirty(prev => new Set(prev).add('legs'))
  }, [])

  const removeExpense = useCallback((index) => {
    setForm(prev => ({
      ...prev,
      expenses: prev.expenses.filter((_, i) => i !== index)
    }))
    setDirty(prev => new Set(prev).add('expenses'))
  }, [])

  const addExpense = useCallback((expense) => {
    setForm(prev => ({
      ...prev,
      expenses: [...(prev.expenses || []), expense]
    }))
    setDirty(prev => new Set(prev).add('expenses'))
  }, [])

  const updateExpense = useCallback((index, field, value) => {
    setForm(prev => ({
      ...prev,
      expenses: prev.expenses.map((e, i) => i === index ? { ...e, [field]: value } : e)
    }))
    setDirty(prev => new Set(prev).add('expenses'))
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
                <EditableTagGroup
                  items={day.activities}
                  editing={legsEditing}
                  color="cyan"
                  placeholder="活动名称"
                  onRemove={idx => {
                    const next = [...(day.activities || [])]
                    next.splice(idx, 1)
                    updateLegDay(li, di, 'activities', next)
                  }}
                  onAdd={val => updateLegDay(li, di, 'activities', [...(day.activities || []), val])}
                />
              </div>
            </div>
            <div className="f-row">
              <div className="f-group">
                <label className="f-label">交通</label>
                <EditableTagGroup
                  items={day.transport}
                  editing={legsEditing}
                  color={transportColor}
                  renderLabel={transportLabel}
                  placeholder="交通信息"
                  onRemove={idx => {
                    const next = [...(day.transport || [])]
                    next.splice(idx, 1)
                    updateLegDay(li, di, 'transport', next)
                  }}
                  onAdd={val => updateLegDay(li, di, 'transport', [...(day.transport || []), val])}
                />
              </div>
            </div>
            <div className="f-row">
              <div className="f-group">
                <label className="f-label">住宿</label>
                <EditableHotelTag
                  name={day.accommodation}
                  editing={legsEditing}
                  onRemove={() => updateLegDay(li, di, 'accommodation', '')}
                  onAdd={val => updateLegDay(li, di, 'accommodation', val)}
                />
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
          <div className="form-block-header">
            <h4>🏙️ 城市站点</h4>
            <Button
              type="text"
              size="small"
              className="section-edit-btn"
              icon={legsEditing ? <CheckOutlined /> : <EditOutlined />}
              onClick={() => setLegsEditing(!legsEditing)}
            >
              {legsEditing ? '完成' : '编辑'}
            </Button>
          </div>
          <Collapse items={legItems} defaultActiveKey={[0]} />
        </div>
      )}

      <div ref={expensesRef} className="form-block">
        <div className="form-block-header">
          <h4>💰 费用明细</h4>
          <Button
            type="text"
            size="small"
            className="section-edit-btn"
            icon={expensesEditing ? <CheckOutlined /> : <EditOutlined />}
            onClick={() => { setExpensesEditing(!expensesEditing); setNewExpense(null) }}
          >
            {expensesEditing ? '完成' : '编辑'}
          </Button>
        </div>
        {(form.expenses || []).length > 0 ? (
          <div className={`expense-table${expensesEditing ? ' editing' : ''}`}>
            <div className="expense-header">
              <span>类别</span>
              <span>描述</span>
              <span>金额</span>
              {expensesEditing && <span></span>}
            </div>
            {(form.expenses || []).map((exp, i) => (
              expensesEditing ? (
                <div key={i} className="expense-row expense-row-new">
                  <span>
                    <Select
                      size="small"
                      value={exp.category}
                      onChange={v => updateExpense(i, 'category', v)}
                      options={EXPENSE_CATEGORIES.map(c => ({ label: c, value: c }))}
                      className="expense-new-select"
                      popupMatchSelectWidth={false}
                      popupStyle={{ minWidth: 112 }}
                    />
                  </span>
                  <span>
                    <Input
                      size="small"
                      value={exp.description}
                      onChange={e => updateExpense(i, 'description', e.target.value)}
                      placeholder="描述"
                    />
                  </span>
                  <span>
                    <InputNumber
                      size="small"
                      value={exp.amount}
                      onChange={v => updateExpense(i, 'amount', v || 0)}
                      min={0}
                      prefix="¥"
                      className="expense-new-amount"
                    />
                  </span>
                  <span className="expense-action">
                    <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => removeExpense(i)} />
                  </span>
                </div>
              ) : (
                <div key={i} className="expense-row">
                  <span className={`expense-tag tag-${exp.category === '交通' ? 'blue' : exp.category === '住宿' ? 'green' : exp.category === '餐饮' ? 'orange' : 'gray'}`}>
                    {exp.category}
                  </span>
                  <span className="expense-desc">{exp.description}</span>
                  <span className="expense-amount">
                    {exp.currency && exp.currency !== 'CNY' ? `${exp.currency} ` : '¥'}
                    {exp.amount.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
                  </span>
                </div>
              )
            ))}
            {expensesEditing && newExpense && (
              <div className="expense-row expense-row-new">
                <span>
                  <Select
                    size="small"
                    value={newExpense.category}
                    onChange={v => setNewExpense(prev => ({ ...prev, category: v }))}
                    options={EXPENSE_CATEGORIES.map(c => ({ label: c, value: c }))}
                    className="expense-new-select"
                    popupMatchSelectWidth={false}
                    popupStyle={{ minWidth: 112 }}
                  />
                </span>
                <span>
                  <Input
                    size="small"
                    value={newExpense.description}
                    onChange={e => setNewExpense(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="描述"
                    onPressEnter={() => {
                      if (newExpense.description.trim()) {
                        addExpense({ ...newExpense })
                        setNewExpense(null)
                      }
                    }}
                  />
                </span>
                <span>
                  <InputNumber
                    size="small"
                    value={newExpense.amount}
                    onChange={v => setNewExpense(prev => ({ ...prev, amount: v || 0 }))}
                    min={0}
                    prefix="¥"
                    className="expense-new-amount"
                  />
                </span>
                <span className="expense-action">
                  <Button
                    type="text"
                    size="small"
                    icon={<CheckOutlined />}
                    className="expense-confirm-btn"
                    onClick={() => {
                      if (newExpense.description.trim()) {
                        addExpense({ ...newExpense })
                        setNewExpense(null)
                      }
                    }}
                  />
                </span>
              </div>
            )}
            <div className="expense-total">
              <span>合计</span>
              <span></span>
              <span>¥{(form.expenses || []).filter(e => !e.currency || e.currency === 'CNY').reduce((s, e) => s + e.amount, 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              {expensesEditing && <span></span>}
            </div>
          </div>
        ) : (
          !expensesEditing && <div className="f-empty" style={{ textAlign: 'center', padding: '16px 0' }}>暂无费用记录</div>
        )}
        {expensesEditing && !newExpense && (
          <div
            className="expense-add-row"
            onClick={() => setNewExpense({ category: '其他', description: '', amount: 0, currency: 'CNY', date: form.start_date || '' })}
          >
            <PlusOutlined /> 添加费用
          </div>
        )}
      </div>
    </div>
  )
}
