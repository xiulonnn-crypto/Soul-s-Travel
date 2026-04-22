import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'

const COMPANION_COLOR = {
  '独行': '#af52de',
  '结伴': '#0099ff',
  '家庭/多人': '#ff9500',
}

export default function CompanionPie({ data }) {
  if (!data || data.length === 0) return null
  const active = data.filter(d => d.count > 0)
  if (active.length === 0) return <div className="stats-empty">暂无旅伴数据</div>
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={active}
          dataKey="count"
          nameKey="type"
          cx="50%"
          cy="50%"
          innerRadius={42}
          outerRadius={80}
          label={({ type, percent }) => `${type} ${(percent * 100).toFixed(0)}%`}
          labelLine={{ strokeWidth: 1 }}
        >
          {active.map((d) => (
            <Cell key={d.type} fill={COMPANION_COLOR[d.type] || '#8e99a4'} />
          ))}
        </Pie>
        <Tooltip formatter={v => [`${v} 次`, '']} />
      </PieChart>
    </ResponsiveContainer>
  )
}
