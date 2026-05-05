// 行程卡片日期范围渲染：始终输出 "M.D–M.D" 完整格式，
// 即使起止落在同一月份也保留终点月份，避免 "5.1–11" 这种容易被读成"11"的歧义。
export function formatTripDateRange(startISO, endISO) {
  const start = new Date(startISO)
  const end = new Date(endISO)
  const startMonth = start.getMonth() + 1
  const startDay = start.getDate()
  const endMonth = end.getMonth() + 1
  const endDay = end.getDate()
  return `${startMonth}.${startDay}–${endMonth}.${endDay}`
}
