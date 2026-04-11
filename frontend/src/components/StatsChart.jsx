import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, LineChart, Line, Area, AreaChart, ResponsiveContainer } from 'recharts'

const COLORS = ['#0099ff', '#af52de', '#ff9500', '#34c759', '#ff6b8a', '#8e99a4']

export function CategoryPie({ data }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie data={data} dataKey="total" nameKey="category" cx="50%" cy="50%"
             outerRadius={80} label={({ category, percent }) => `${category} ${(percent * 100).toFixed(0)}%`}>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function TripExpenseBar({ data }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data}>
        <XAxis dataKey="title" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip />
        <Bar dataKey="total" fill="#0099ff" radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function PerDayTrend({ data }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data}>
        <XAxis dataKey="title" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip />
        <defs>
          <linearGradient id="colorPpd" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0099ff" stopOpacity={0.15} />
            <stop offset="100%" stopColor="#0099ff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey="per_person_per_day" stroke="#0099ff" fill="url(#colorPpd)" strokeWidth={2.5} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function DestinationRank({ data, label }) {
  const max = data.length > 0 ? data[0][1] : 1
  return (
    <div>
      {data.slice(0, 8).map(([name, count], i) => (
        <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid #f0f2f5' }}>
          <span style={{ width: 22, height: 22, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
                         fontSize: 11, fontWeight: 700,
                         background: i < 3 ? ['#fff5e6','#e8f4ff','#f5eafa'][i] : '#f0f2f5',
                         color: i < 3 ? ['#ff9500','#0099ff','#af52de'][i] : '#8e99a4' }}>
            {i + 1}
          </span>
          <span style={{ width: 64, fontSize: 13, fontWeight: 500 }}>{name}</span>
          <div style={{ flex: 1, height: 8, background: '#f0f2f5', borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ width: `${(count / max) * 100}%`, height: '100%', borderRadius: 6, background: 'linear-gradient(90deg, #0099ff, #66ccff)' }} />
          </div>
          <span style={{ width: 32, textAlign: 'right', fontSize: 11, color: '#8e99a4' }}>{count}次</span>
        </div>
      ))}
    </div>
  )
}
