import './ExpenseTable.css'

const CAT_COLORS = { '交通': '#0099ff', '住宿': '#af52de', '餐饮': '#ff9500', '门票': '#34c759', '购物': '#ff6b8a', '其他': '#8e99a4' }

export default function ExpenseTable({ expenses = [], travelerCount = 1 }) {
  const total = expenses.reduce((s, e) => s + e.amount, 0)
  const byCategory = {}
  expenses.forEach(e => { byCategory[e.category] = (byCategory[e.category] || 0) + e.amount })
  const days = expenses.length > 0
    ? new Set(expenses.map(e => e.date)).size
    : 1

  return (
    <div className="expense-card">
      <h3 className="expense-title">💰 开销总览</h3>
      {Object.entries(byCategory).map(([cat, amt]) => (
        <div key={cat} className="expense-bar-row">
          <span className="expense-bar-label">{cat}</span>
          <div className="expense-bar">
            <div className="expense-bar-fill" style={{ width: `${(amt/total)*100}%`, background: CAT_COLORS[cat] || '#8e99a4' }} />
          </div>
          <span className="expense-bar-val">¥{amt.toLocaleString()}</span>
        </div>
      ))}
      <div className="expense-total">
        <span>合计</span><span>¥{total.toLocaleString()}</span>
      </div>
      <div className="expense-per">
        <span>人均 ¥{Math.round(total / travelerCount).toLocaleString()}</span>
        <span>日均 ¥{Math.round(total / days).toLocaleString()}</span>
      </div>
    </div>
  )
}
