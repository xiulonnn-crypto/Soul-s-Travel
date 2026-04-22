import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { message } from 'antd'
import ChatPanel from '../components/ChatPanel'
import TripForm from '../components/TripForm'
import { tripApi } from '../services/api'
import { applyAction } from '../utils/applyAction'
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

  const handleParsed = (result) => {
    if (result.type === 'compound' && result.actions) {
      for (const action of result.actions) {
        tripDataRef.current = applyAction(tripDataRef.current, action)
      }
    } else {
      tripDataRef.current = applyAction(tripDataRef.current, result)
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

  const getContextYear = () => {
    const base = tripDataRef.current
    const startDate = base?.trip?.start_date
    if (!startDate) return null
    const year = parseInt(startDate.slice(0, 4), 10)
    return Number.isFinite(year) ? year : null
  }

  return (
    <div className="editor-layout">
      <div className="editor-chat">
        <ChatPanel onParsed={handleParsed} getContextYear={getContextYear} />
      </div>
      <div className="editor-form">
        <TripForm data={parsedData} onSave={handleSave} />
      </div>
    </div>
  )
}
