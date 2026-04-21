import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { message } from 'antd'
import ChatPanel from '../components/ChatPanel'
import TripForm from '../components/TripForm'
import { tripApi } from '../services/api'
import './TripEditor.css'

const PARSE_STORAGE_PREFIX = 'parse_ref_'

export default function TripEditor() {
  const { id } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const isEdit = Boolean(id)
  const [parsedData, setParsedData] = useState(null)
  const tripDataRef = useRef(null)
  const navigate = useNavigate()

  const loadTripId = isEdit ? id : searchParams.get('trip_id')
  const parseRef = searchParams.get('ref')

  useEffect(() => {
    if (loadTripId) {
      tripApi.get(loadTripId).then(trip => {
        const { legs, expenses, ...rest } = trip
        const formatted = { trip: rest, legs: legs || [], expenses: expenses || [] }
        setParsedData(formatted)
        tripDataRef.current = formatted
      }).catch(() => {
        message.error(isEdit ? '加载行程失败' : '加载调试数据失败')
      })
    } else if (parseRef) {
      try {
        const saved = sessionStorage.getItem(PARSE_STORAGE_PREFIX + parseRef)
        if (saved) {
          const data = JSON.parse(saved)
          setParsedData(data)
          tripDataRef.current = data
        }
      } catch { /* ignore corrupt data */ }
    }
  }, [loadTripId, parseRef])

  const saveParsedToUrl = (data) => {
    const refKey = Date.now().toString(36)
    sessionStorage.setItem(PARSE_STORAGE_PREFIX + refKey, JSON.stringify(data))
    setSearchParams({ ref: refKey }, { replace: true })
  }

  const applyAction = (result) => {
    const base = tripDataRef.current
    if (result.type === 'expense' && base) {
      return {
        ...base,
        expenses: [...(base.expenses || []), ...(result.expenses || [])],
      }
    }
    if (result.type === 'change_category' && base) {
      const name = result.item_name || ''
      const target = result.target_category || '住宿'
      return {
        ...base,
        expenses: (base.expenses || []).map(exp => {
          const desc = exp.description || ''
          if (name && desc.includes(name)) {
            return { ...exp, category: target }
          }
          return exp
        }),
      }
    }
    if (result.type === 'accommodation' && base) {
      const name = result.accommodation || ''
      const target = result.target_category || '住宿'
      return {
        ...base,
        expenses: (base.expenses || []).map(exp => {
          const desc = exp.description || ''
          if (name && desc.includes(name)) {
            return { ...exp, category: target }
          }
          return exp
        }),
      }
    }
    if (result.type === 'remove_expense' && base) {
      const desc = result.description || ''
      return {
        ...base,
        expenses: (base.expenses || []).filter(exp =>
          !desc || !(exp.description || '').includes(desc)
        ),
      }
    }
    if (result.type === 'rename' && base) {
      const { old_name, new_name } = result
      return {
        ...base,
        legs: (base.legs || []).map(leg => ({
          ...leg,
          days: (leg.days || []).map(day => ({
            ...day,
            activities: (day.activities || []).map(a => a === old_name ? new_name : a),
            accommodation: day.accommodation === old_name ? new_name : day.accommodation,
          })),
        })),
      }
    }
    if (result.trip || (result.legs && result.legs.length > 0)) {
      return result
    }
    return base || result
  }

  const handleParsed = (result) => {
    if (result.type === 'compound' && result.actions) {
      for (const action of result.actions) {
        tripDataRef.current = applyAction(action)
      }
    } else {
      tripDataRef.current = applyAction(result)
    }
    setParsedData({ ...tripDataRef.current })
    if (!isEdit) saveParsedToUrl(tripDataRef.current)
  }

  const handleSave = async (payload) => {
    try {
      if (isEdit) {
        await tripApi.update(id, payload)
        message.success('行程已更新')
        navigate(`/trips/${id}`)
      } else {
        const created = await tripApi.create(payload)
        message.success('行程已保存')
        navigate(`/trips/${created.id}`)
      }
    } catch (e) {
      message.error('保存失败: ' + (e.response?.data?.error || e.message))
    }
  }

  return (
    <div className="editor-layout">
      <div className="editor-chat">
        <ChatPanel onParsed={handleParsed} />
      </div>
      <div className="editor-form">
        <TripForm data={parsedData} onSave={handleSave} />
      </div>
    </div>
  )
}
