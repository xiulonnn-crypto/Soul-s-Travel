import { useState, useEffect, useCallback } from 'react'
import { Input, DatePicker, InputNumber, Button, Collapse } from 'antd'
import dayjs from 'dayjs'
import './TripForm.css'

export default function TripForm({ data, onSave }) {
  const [form, setForm] = useState({ title: '', start_date: '', end_date: '', traveler_count: 1, description: '', legs: [], expenses: [] })
  const [dirty, setDirty] = useState(new Set())

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

  const setField = useCallback((key, value) => {
    setForm(prev => ({ ...prev, [key]: value }))
    setDirty(prev => new Set(prev).add(key))
  }, [])

  const handleSave = () => {
    const payload = {
      title: form.title,
      start_date: form.start_date,
      end_date: form.end_date,
      traveler_count: form.traveler_count,
      description: form.description,
      status: 'completed',
      legs: form.legs,
      expenses: form.expenses,
    }
    onSave(payload)
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
                <Input value={(day.activities || []).join(', ')} readOnly className="f-input ai-fill" />
              </div>
            </div>
            <div className="f-row">
              <div className="f-group">
                <label className="f-label">交通</label>
                <Input value={(day.transport || []).join(', ')} readOnly className="f-input ai-fill" />
              </div>
            </div>
            <div className="f-row">
              <div className="f-group">
                <label className="f-label">住宿</label>
                <Input value={day.accommodation || ''} readOnly className="f-input ai-fill" />
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }))

  return (
    <div className="trip-form">
      <div className="form-header">
        <h3>行程表单</h3>
        <Button type="primary" shape="round" onClick={handleSave}>💾 保存行程</Button>
      </div>

      <div className="form-block">
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
        <div className="form-block">
          <h4>🏙️ 城市站点</h4>
          <Collapse items={legItems} defaultActiveKey={[0]} />
        </div>
      )}
    </div>
  )
}
