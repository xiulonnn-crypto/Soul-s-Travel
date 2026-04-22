import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from 'recharts'

const SEASON_COLOR = {
  spring: '#34c759',
  summer: '#ff9500',
  autumn: '#af52de',
  winter: '#0099ff',
}

function seasonOf(month) {
  if (month >= 3 && month <= 5) return 'spring'
  if (month >= 6 && month <= 8) return 'summer'
  if (month >= 9 && month <= 11) return 'autumn'
  return 'winter'
}

export default function MonthDistribution({ data }) {
  if (!data) return null
  const safe = data.map(d => ({ ...d, label: `${d.month}月` }))
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={safe} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <XAxis dataKey="label" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis allowDecimals={false} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
        <Tooltip formatter={v => [`${v} 次`, '出行']} labelFormatter={l => l} />
        <Bar dataKey="trip_count" radius={[6, 6, 0, 0]}>
          {safe.map((d, i) => (
            <Cell key={i} fill={SEASON_COLOR[seasonOf(d.month)]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
