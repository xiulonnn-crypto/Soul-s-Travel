// Pure Node test — no framework. Run with `node applyAction.test.mjs` from this dir.
// Covers the "PDF 先传 → JPG 后覆盖" bug: JPG's empty expenses must not wipe
// PDF's populated expenses.
import assert from 'node:assert/strict'
import { applyAction } from './applyAction.js'

// --- Fixtures ----------------------------------------------------------------

// PDF parse result — shaped like services/ai_parser.parse_text() output,
// trimmed to the fields that matter for this bug.
const PDF_RESULT = {
  type: 'trip',
  trip: {
    title: 'SexySouL的英国行程',
    start_date: '2024-09-28',
    end_date: '2024-10-08',
    traveler_count: 1,
    description: 'SexySouL的英国行程',
    status: 'completed',
  },
  legs: [
    { order_index: 0, city: '伦敦', country: '英国', days: [{ day_number: 1 }] },
  ],
  expenses: [
    { date: '2024-09-28', amount: 100, category: '交通', description: '北京→伦敦 x1' },
    { date: '2024-09-29', amount: 500, category: '住宿', description: '伦敦摄政公园万豪酒店' },
    { date: '2024-09-29', amount: 80, category: '门票', description: '大英博物馆 x1' },
  ],
}

// JPG (PiTravel) parse result — planner_parser ALWAYS returns expenses=[].
const JPG_RESULT = {
  type: 'trip',
  trip: {
    title: '英国9日游',
    start_date: '2024-09-29',
    end_date: '2024-10-07',
    traveler_count: 1,
    description: '英国9日游',
    status: 'completed',
  },
  legs: [
    { order_index: 0, city: '伦敦', country: '英国', days: [{ day_number: 1 }] },
    { order_index: 1, city: '爱丁堡', country: '英国', days: [{ day_number: 5 }] },
  ],
  expenses: [],
}

// --- Tests -------------------------------------------------------------------

// THE BUG — the RED test.
// Before the fix, applying JPG over PDF wiped expenses. After the fix, JPG
// should still overwrite trip + legs (it IS the authoritative new itinerary),
// but expenses=[] must NOT clobber the PDF's populated expense list.
function test_jpg_over_pdf_preserves_expenses() {
  const merged = applyAction(PDF_RESULT, JPG_RESULT)
  // Leaf-value assertions (assert to the leaf):
  assert.equal(merged.type, 'trip')
  // JPG wins for trip + legs (the user's explicit "JPG 覆盖" intent):
  assert.equal(merged.trip.title, '英国9日游')
  assert.equal(merged.trip.start_date, '2024-09-29')
  assert.equal(merged.trip.end_date, '2024-10-07')
  assert.equal(merged.legs.length, 2)
  assert.equal(merged.legs[1].city, '爱丁堡')
  // THE CORE ASSERTION — expenses survive:
  assert.equal(merged.expenses.length, 3, 'expenses count preserved from PDF')
  assert.equal(merged.expenses[0].description, '北京→伦敦 x1')
  assert.equal(merged.expenses[1].description, '伦敦摄政公园万豪酒店')
  assert.equal(merged.expenses[2].category, '门票')
}

// First upload (base === null) on a fresh page should return the result as-is.
function test_no_base_returns_result() {
  const merged = applyAction(null, PDF_RESULT)
  assert.equal(merged.expenses.length, 3)
  assert.equal(merged.trip.title, 'SexySouL的英国行程')
}

// PDF over JPG: both have content, new wins for trip/legs AND for expenses
// (PDF has real expense data, so it legitimately replaces the empty list).
function test_pdf_over_jpg_replaces_expenses() {
  const merged = applyAction(JPG_RESULT, PDF_RESULT)
  assert.equal(merged.expenses.length, 3, 'PDF expenses win over JPG empty')
  assert.equal(merged.trip.title, 'SexySouL的英国行程')
}

// Regression: existing non-trip branches still behave correctly.
function test_expense_action_still_appends() {
  const merged = applyAction(PDF_RESULT, {
    type: 'expense',
    expenses: [{ date: '2024-09-30', amount: 200, category: '餐饮', description: '茶餐厅' }],
  })
  assert.equal(merged.expenses.length, 4)
  assert.equal(merged.expenses[3].description, '茶餐厅')
  assert.equal(merged.trip.title, 'SexySouL的英国行程', 'trip untouched')
}

// Null expenses (not []), new full-trip result: same preservation behavior.
function test_null_expenses_preserves_base() {
  const resultWithNullExpenses = { ...JPG_RESULT, expenses: null }
  const merged = applyAction(PDF_RESULT, resultWithNullExpenses)
  assert.equal(merged.expenses.length, 3)
}

// Missing expenses key entirely: new full-trip result → preserve base.
function test_missing_expenses_key_preserves_base() {
  const { expenses: _drop, ...resultNoExpenses } = JPG_RESULT
  const merged = applyAction(PDF_RESULT, resultNoExpenses)
  assert.equal(merged.expenses.length, 3)
}

// ---------------------------------------------------------------------------
// NEW TESTS — transport preservation across multi-source merge
// ---------------------------------------------------------------------------

// Real-world trip days with date field
const PDF_WITH_FLIGHTS = {
  type: 'trip',
  trip: { title: '英国9日游', start_date: '2024-09-28', end_date: '2024-10-08', traveler_count: 1, status: 'completed' },
  legs: [
    {
      order_index: 0, city: '伦敦', country: '英国',
      days: [
        { date: '2024-09-29', day_number: 1, activities: [], transport: [], accommodation: null },
        { date: '2024-09-30', day_number: 2, activities: [], transport: [], accommodation: null },
      ],
    },
    {
      order_index: 1, city: '爱丁堡', country: '英国',
      days: [
        // 跨城日：PDF 捕获了航班
        { date: '2024-10-03', day_number: 5, activities: [], transport: ['U2308:伦敦→爱丁堡'], accommodation: null },
        { date: '2024-10-04', day_number: 6, activities: [], transport: [], accommodation: null },
      ],
    },
  ],
  expenses: [
    { date: '2024-09-29', amount: 500, category: '住宿', description: '伦敦摄政公园万豪酒店' },
  ],
}

const JPG_WITH_ACTIVITIES = {
  type: 'trip',
  trip: { title: '英国9日游', start_date: '2024-09-29', end_date: '2024-10-07', traveler_count: 1, status: 'completed' },
  legs: [
    {
      order_index: 0, city: '伦敦', country: '英国',
      days: [
        // JPG 有丰富活动，但 transport 为空
        { date: '2024-09-29', day_number: 1, activities: ['大英博物馆', 'OPSO', '摄政公园'], transport: [], accommodation: '伦敦摄政公园万豪酒店' },
        { date: '2024-09-30', day_number: 2, activities: ['Madame Tussauds London', 'Baker Street'], transport: [], accommodation: '伦敦摄政公园万豪酒店' },
      ],
    },
    {
      order_index: 1, city: '爱丁堡', country: '英国',
      days: [
        // JPG 对跨城日也有活动，但没有 transport
        { date: '2024-10-03', day_number: 5, activities: ['爱丁堡城堡', 'Makars Mash Bar'], transport: [], accommodation: '万豪爱丁堡官邸酒店' },
        { date: '2024-10-04', day_number: 6, activities: ['The Balmoral', '洛蒙德湖'], transport: [], accommodation: '万豪爱丁堡官邸酒店' },
      ],
    },
  ],
  expenses: [],
}

/**
 * 核心 bug 场景：PDF 先传（带航班 transport），JPG 后传（带活动但 transport=[]）
 * → 合并后 JPG 的活动应保留，PDF 的 transport 不能被 [] 覆盖
 */
function test_jpg_over_pdf_preserves_day_transport() {
  const merged = applyAction(PDF_WITH_FLIGHTS, JPG_WITH_ACTIVITIES)

  // JPG 的活动应保留
  const londonDay1 = merged.legs[0].days[0]
  assert.deepEqual(
    londonDay1.activities,
    ['大英博物馆', 'OPSO', '摄政公园'],
    'JPG activities should win on day 1',
  )

  // 跨城日：PDF 的 transport 不应被 JPG 的 [] 覆盖
  const edinburghDay5 = merged.legs[1].days[0]
  assert.deepEqual(
    edinburghDay5.transport,
    ['U2308:伦敦→爱丁堡'],
    'PDF transport (flight) must survive JPG empty transport=[] on same date',
  )

  // JPG 的 accommodation 应保留（非空覆盖空）
  assert.equal(londonDay1.accommodation, '伦敦摄政公园万豪酒店', 'JPG accommodation wins')

  // expenses 从 PDF 保留
  assert.equal(merged.expenses.length, 1, 'PDF expenses preserved')
}

/**
 * 反向：PDF 后传覆盖 JPG → PDF 有 transport 的天，transport 应写入；
 * JPG 的活动如果 PDF 对应天是空的，应被 PDF 覆盖（PDF 内容优先）。
 */
function test_pdf_over_jpg_activities_win() {
  const merged = applyAction(JPG_WITH_ACTIVITIES, PDF_WITH_FLIGHTS)

  // PDF 有 transport 的跨城日，transport 应保留
  const edinburghDay5 = merged.legs[1].days[0]
  assert.deepEqual(
    edinburghDay5.transport,
    ['U2308:伦敦→爱丁堡'],
    'PDF transport preserved when PDF applied over JPG',
  )

  // PDF 对该天 activities=[]，JPG 有活动 — JPG 的活动应被保留（mergePreservingEmpty：空不覆盖非空）
  assert.deepEqual(
    edinburghDay5.activities,
    ['爱丁堡城堡', 'Makars Mash Bar'],
    'JPG activities survive when PDF activities=[] for same date',
  )
}

/**
 * 兼容性：没有 date 字段的 day（如旧测试 fixture）应原样通过，不报错。
 */
function test_days_without_date_pass_through() {
  const merged = applyAction(PDF_RESULT, JPG_RESULT)
  assert.equal(merged.legs.length, 2, 'leg count from JPG')
  assert.equal(merged.expenses.length, 3, 'expenses from PDF preserved')
}

// --- Runner ------------------------------------------------------------------

const tests = [
  test_jpg_over_pdf_preserves_expenses,
  test_no_base_returns_result,
  test_pdf_over_jpg_replaces_expenses,
  test_expense_action_still_appends,
  test_null_expenses_preserves_base,
  test_missing_expenses_key_preserves_base,
  test_jpg_over_pdf_preserves_day_transport,
  test_pdf_over_jpg_activities_win,
  test_days_without_date_pass_through,
]

let failed = 0
for (const t of tests) {
  try {
    t()
    console.log(`PASS  ${t.name}`)
  } catch (e) {
    failed++
    console.error(`FAIL  ${t.name}`)
    console.error(`      ${e.message}`)
  }
}
if (failed) {
  console.error(`\n${failed} of ${tests.length} failed`)
  process.exit(1)
}
console.log(`\nAll ${tests.length} passed`)
