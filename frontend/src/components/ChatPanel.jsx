import { useState, useRef } from 'react'
import { Button, Input, Upload } from 'antd'
import { PaperClipOutlined, SendOutlined } from '@ant-design/icons'
import { parseApi } from '../services/api'
import './ChatPanel.css'

export default function ChatPanel({ onParsed }) {
  const [messages, setMessages] = useState([
    { role: 'ai', text: '你好！我可以帮你快速创建行程 ✨\n\n📄 上传行程 PDF\n🖼️ 上传行程表图片\n📝 粘贴文字描述\n🔗 粘贴穷游行程助手链接\n💬 直接告诉我去了哪里' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const fileInputRef = useRef()

  const addMsg = (role, text) => setMessages(prev => [...prev, { role, text }])

  const isQyerUrl = (text) => /plan\.qyer\.com\/trip\//.test(text)

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const text = input.trim()
    setInput('')
    addMsg('user', text)
    setLoading(true)
    try {
      let result
      if (isQyerUrl(text)) {
        addMsg('ai', '正在从穷游网抓取行程数据，请稍候...')
        result = await parseApi.url(text)
      } else {
        result = await parseApi.text(text)
      }
      if (result.type === 'compound') {
        const parts = (result.actions || []).map(a => {
          if (a.type === 'expense') return `添加 ${a.expenses?.length || 0} 笔费用`
          if (a.type === 'change_category') return `将「${a.item_name}」改为${a.target_category}`
          if (a.type === 'remove_expense') return `移除「${a.description}」`
          if (a.type === 'rename') return `改名「${a.old_name}」→「${a.new_name}」`
          return '已处理'
        })
        addMsg('ai', `已处理 ${parts.length} 条指令：${parts.join('；')}`)
      } else if (result.type === 'expense' && result.expenses?.length > 0) {
        if (result.expenses.length > 1) {
          addMsg('ai', `已添加 ${result.expenses.length} 笔费用，已更新到费用明细。`)
        } else {
          const exp = result.expenses[0]
          addMsg('ai', `已添加费用：${exp.description}，¥${exp.amount.toFixed(2)}，已更新到费用明细。`)
        }
      } else if (result.type === 'change_category') {
        addMsg('ai', `已将「${result.item_name || ''}」的类别改为${result.target_category || '住宿'}。`)
      } else if (result.type === 'remove_expense') {
        addMsg('ai', `已移除费用「${result.description || ''}」。`)
      } else if (result.type === 'accommodation') {
        addMsg('ai', `已识别「${result.accommodation || ''}」为住宿，已将对应费用类别更新为住宿。`)
      } else if (result.type === 'rename') {
        if (result.old_name && result.new_name) {
          addMsg('ai', `已将「${result.old_name}」改名为「${result.new_name}」。`)
        } else {
          addMsg('ai', '未能识别改名内容，请用格式：[旧名]改名为[新名]')
        }
      } else {
        addMsg('ai', `解析完成！识别到 ${result.trip?.title || '行程'}，已填入右侧表单。`)
      }
      onParsed(result)
    } catch (e) {
      addMsg('ai', `解析失败: ${e.message}`)
    }
    setLoading(false)
  }

  const isImageFile = (name) => /\.(jpg|jpeg|png|webp|gif|bmp)$/i.test(name)

  const handleFile = async (file) => {
    const icon = isImageFile(file.name) ? '🖼️' : '📎'
    addMsg('user', `${icon} 已上传: ${file.name}`)
    setLoading(true)
    if (isImageFile(file.name)) {
      addMsg('ai', '正在识别图片中的行程信息，请稍候...')
    }
    try {
      const result = await parseApi.file(file)
      if (result.type === 'compound') {
        const count = result.actions?.length || 0
        addMsg('ai', `已处理 ${count} 条指令，已更新到行程中。`)
      } else {
        addMsg('ai', `解析完成！识别到 ${result.trip?.title || '行程'}，已填入右侧表单。`)
      }
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
        <Upload beforeUpload={handleFile} showUploadList={false} accept=".pdf,.txt,.docx,.xlsx,.pptx,.html,.csv,.jpg,.jpeg,.png,.webp">
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
