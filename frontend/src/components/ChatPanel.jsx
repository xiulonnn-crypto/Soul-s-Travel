import { useState, useRef } from 'react'
import { Button, Input, Upload } from 'antd'
import { PaperClipOutlined, SendOutlined } from '@ant-design/icons'
import { parseApi } from '../services/api'
import './ChatPanel.css'

export default function ChatPanel({ onParsed }) {
  const [messages, setMessages] = useState([
    { role: 'ai', text: '你好！我可以帮你快速创建行程 ✨\n\n📄 上传行程 PDF\n📝 粘贴文字描述\n💬 直接告诉我去了哪里' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const fileInputRef = useRef()

  const addMsg = (role, text) => setMessages(prev => [...prev, { role, text }])

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const text = input.trim()
    setInput('')
    addMsg('user', text)
    setLoading(true)
    try {
      const result = await parseApi.text(text)
      addMsg('ai', `解析完成！识别到 ${result.trip?.title || '行程'}，已填入右侧表单。`)
      onParsed(result)
    } catch (e) {
      addMsg('ai', `解析失败: ${e.message}`)
    }
    setLoading(false)
  }

  const handleFile = async (file) => {
    addMsg('user', `📎 已上传: ${file.name}`)
    setLoading(true)
    try {
      const result = await parseApi.file(file)
      addMsg('ai', `解析完成！识别到 ${result.trip?.title || '行程'}，已填入右侧表单。`)
      onParsed(result)
    } catch (e) {
      addMsg('ai', `解析失败: ${e.message}`)
    }
    setLoading(false)
    return false
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <span className="ai-avatar">🤖</span>
        <div>
          <div className="ai-name">AI 行程助手</div>
          <div className="ai-tag">Claude</div>
        </div>
      </div>
      <div className="chat-body">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">{m.text}</div>
          </div>
        ))}
        {loading && <div className="msg ai"><div className="bubble typing">解析中...</div></div>}
      </div>
      <div className="chat-input-area">
        <Upload beforeUpload={handleFile} showUploadList={false} accept=".pdf,.txt">
          <Button icon={<PaperClipOutlined />} shape="circle" />
        </Upload>
        <Input
          value={input}
          onChange={e => setInput(e.target.value)}
          onPressEnter={handleSend}
          placeholder="输入修改指令或补充信息..."
          disabled={loading}
        />
        <Button type="primary" icon={<SendOutlined />} onClick={handleSend}
                loading={loading} shape="circle" />
      </div>
    </div>
  )
}
