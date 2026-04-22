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

// --- Runner ------------------------------------------------------------------

const tests = [
  test_jpg_over_pdf_preserves_expenses,
  test_no_base_returns_result,
  test_pdf_over_jpg_replaces_expenses,
  test_expense_action_still_appends,
  test_null_expenses_preserves_base,
  test_missing_expenses_key_preserves_base,
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
