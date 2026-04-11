import { useEffect, useState } from 'react'
import { Drawer, Form, Input, InputNumber, Button, Tag, Spin, Divider, message } from 'antd'
import { profileApi } from '../services/api'
import './ProfileDrawer.css'

function VisitedPlaces({ visited = {} }) {
  const countries = Object.keys(visited)
  if (!countries.length) return <div className="profile-empty">暂无旅行记录</div>

  return (
    <div className="profile-visited">
      {countries.map(country => (
        <div key={country} className="visited-country">
          <div className="visited-country-name">🌏 {country}</div>
          <div className="visited-cities">
            {Object.entries(visited[country]).map(([city, date]) => {
              const [y, m] = date.split('-')
              return (
                <Tag key={city} className="visited-tag">
                  {y}年{parseInt(m)}月 · {city}
                </Tag>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function ProfileDrawer({ open, onClose }) {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [visited, setVisited] = useState({})

  useEffect(() => {
    if (!open) return
    setLoading(true)
    profileApi.get()
      .then(data => {
        form.setFieldsValue({
          family_desc: data.family_desc,
          annual_income: data.annual_income ? data.annual_income / 10000 : undefined,
          annual_travel_budget: data.annual_travel_budget ? data.annual_travel_budget / 10000 : undefined,
        })
        setVisited(data.visited_places || {})
      })
      .catch(() => message.error('加载个人背景失败'))
      .finally(() => setLoading(false))
  }, [open, form])

  const handleSave = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      await profileApi.update({
        family_desc: values.family_desc,
        annual_income: values.annual_income ? values.annual_income * 10000 : 0,
        annual_travel_budget: values.annual_travel_budget ? values.annual_travel_budget * 10000 : 0,
      })
      message.success('已保存')
      onClose()
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Drawer
      title="👤 个人背景"
      open={open}
      onClose={onClose}
      width={380}
      className="profile-drawer"
      footer={
        <Button type="primary" block shape="round" loading={saving} onClick={handleSave}>
          保存
        </Button>
      }
    >
      <Spin spinning={loading}>
        <Form form={form} layout="vertical" className="profile-form">
          <Form.Item label="家庭描述" name="family_desc">
            <Input placeholder="例如：夫妻两人" />
          </Form.Item>
          <Form.Item label="年薪税后（万）" name="annual_income">
            <InputNumber min={0} placeholder="例如：30" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="年旅游预算（万）" name="annual_travel_budget">
            <InputNumber min={0} placeholder="例如：5" style={{ width: '100%' }} />
          </Form.Item>
        </Form>

        <Divider />

        <div className="profile-section-title">🗺 去过的地方</div>
        <VisitedPlaces visited={visited} />
      </Spin>
    </Drawer>
  )
}
