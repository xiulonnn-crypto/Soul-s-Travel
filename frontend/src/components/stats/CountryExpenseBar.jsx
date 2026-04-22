import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from 'recharts'

const COLORS = ['#0099ff', '#af52de', '#ff9500', '#34c759', '#ff6b8a', '#00c7be', '#8e99a4']

export default function CountryExpenseBar({ data }) {
  if (!data || data.length === 0) return <div className="stats-empty">暂无分国花费</div>
  const top = data.slice(0, 10)
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={top} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <XAxis dataKey="country" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `¥${(v / 1000).toFixed(0)}K`}
               axisLine={false} tickLine={false} />
        <Tooltip formatter={v => [`¥${v.toLocaleString()}`, '花费']} />
        <Bar dataKey="total" radius={[6, 6, 0, 0]}>
          {top.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
