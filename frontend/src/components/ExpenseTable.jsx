import './ExpenseTable.css'

const CAT_COLORS = { '交通': '#0099ff', '住宿': '#af52de', '餐饮': '#ff9500', '门票': '#34c759', '购物': '#ff6b8a', '其他': '#8e99a4' }

const CURR_SYMBOL = { CNY: '¥', USD: '$', EUR: '€', JPY: '¥', KRW: '₩', HKD: 'HK$', SGD: 'S$', THB: '฿' }

export default function ExpenseTable({ expenses = [], travelerCount = 1 }) {
  const cnyExpenses = expenses.filter(e => (e.currency || 'CNY') === 'CNY')
  const total = cnyExpenses.reduce((s, e) => s + e.amount, 0)
  const byCategory = {}
  cnyExpenses.forEach(e => { byCategory[e.category] = (byCategory[e.category] || 0) + e.amount })
  const days = expenses.length > 0
    ? new Set(expenses.map(e => e.date)).size
    : 1

  const foreignExpenses = expenses.filter(e => e.currency && e.currency !== 'CNY')

  return (
    <div className="expense-card">
      <h3 className="expense-title">💰 开销总览</h3>
      {Object.entries(byCategory).map(([cat, amt]) => (
        <div key={cat} className="expense-bar-row">
          <span className="expense-bar-label">{cat}</span>
          <div className="expense-bar">
            <div className="expense-bar-fill" style={{ width: `${total > 0 ? (amt/total)*100 : 0}%`, background: CAT_COLORS[cat] || '#8e99a4' }} />
          </div>
          <span className="expense-bar-val">¥{amt.toLocaleString()}</span>
        </div>
      ))}
      {foreignExpenses.length > 0 && (
        <div className="expense-bar-row" style={{ opacity: 0.7, fontSize: '0.85em' }}>
          <span className="expense-bar-label">外币</span>
          <div className="expense-bar" />
          <span className="expense-bar-val">
            {[...new Set(foreignExpenses.map(e => e.currency))].map(curr => {
              const sum = foreignExpenses.filter(e => e.currency === curr).reduce((s, e) => s + e.amount, 0)
              return `${CURR_SYMBOL[curr] || curr}${sum.toFixed(2)}`
            }).join(' + ')}
          </span>
        </div>
      )}
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
