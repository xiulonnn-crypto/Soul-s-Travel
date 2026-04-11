import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import ChatPanel from '../components/ChatPanel'
import TripForm from '../components/TripForm'
import { tripApi } from '../services/api'
import './TripEditor.css'

export default function TripEditor() {
  const [parsedData, setParsedData] = useState(null)
  const navigate = useNavigate()

  const handleSave = async (payload) => {
    try {
      const created = await tripApi.create(payload)
      message.success('行程已保存')
      navigate(`/trips/${created.id}`)
    } catch (e) {
      message.error('保存失败: ' + (e.response?.data?.error || e.message))
    }
  }

  return (
    <div className="editor-layout">
      <div className="editor-chat">
        <ChatPanel onParsed={setParsedData} />
      </div>
      <div className="editor-form">
        <TripForm data={parsedData} onSave={handleSave} />
      </div>
    </div>
  )
}
