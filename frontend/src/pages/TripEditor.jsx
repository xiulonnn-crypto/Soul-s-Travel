import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { message } from 'antd'
import ChatPanel from '../components/ChatPanel'
import TripForm from '../components/TripForm'
import { tripApi } from '../services/api'
import './TripEditor.css'

export default function TripEditor() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  const [parsedData, setParsedData] = useState(null)
  const tripDataRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!isEdit) return
    tripApi.get(id).then(trip => {
      const { legs, expenses, ...rest } = trip
      const formatted = { trip: rest, legs: legs || [], expenses: expenses || [] }
      setParsedData(formatted)
      tripDataRef.current = formatted
    }).catch(() => {
      message.error('加载行程失败')
    })
  }, [id])

  const handleParsed = (result) => {
    if (result.type === 'expense' && tripDataRef.current) {
      const base = tripDataRef.current
      const merged = {
        ...base,
        expenses: [...(base.expenses || []), ...(result.expenses || [])],
      }
      tripDataRef.current = merged
      setParsedData(merged)
    } else {
      tripDataRef.current = result
      setParsedData(result)
    }
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
