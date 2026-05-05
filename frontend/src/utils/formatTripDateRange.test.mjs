// Pure Node test — no framework. Run with `node formatTripDateRange.test.mjs` from this dir.
// 锁住「行程卡片日期范围始终输出完整 M.D–M.D」契约：同月、跨月、跨年、单日都不省略 endMonth。
import assert from 'node:assert/strict'
import { formatTripDateRange } from './formatTripDateRange.js'

assert.equal(
  formatTripDateRange('2025-05-01', '2025-05-11'),
  '5.1–5.11',
  '同月：肯尼亚 5.1–5.11，不可被渲染成 "5.1–11"'
)

assert.equal(
  formatTripDateRange('2024-04-04', '2024-04-14'),
  '4.4–4.14',
  '同月：新加坡 4.4–4.14'
)

assert.equal(
  formatTripDateRange('2019-10-01', '2019-10-07'),
  '10.1–10.7',
  '同月：缅甸 10.1–10.7（双位月份）'
)

assert.equal(
  formatTripDateRange('2025-01-30', '2025-02-06'),
  '1.30–2.6',
  '跨月：越南 1.30–2.6'
)

assert.equal(
  formatTripDateRange('2024-09-28', '2024-10-08'),
  '9.28–10.8',
  '跨月跨季度：英国 9.28–10.8'
)

assert.equal(
  formatTripDateRange('2023-12-30', '2024-01-03'),
  '12.30–1.3',
  '跨年：12.30–1.3（年份在外层渲染，此处只关心月日）'
)

assert.equal(
  formatTripDateRange('2024-03-05', '2024-03-05'),
  '3.5–3.5',
  '单日行程：起止同日仍输出完整 M.D–M.D'
)

console.log('All formatTripDateRange tests passed.')
