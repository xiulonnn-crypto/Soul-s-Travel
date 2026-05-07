/**
 * 把一个 parse 结果（上传 PDF / JPG / 自然语言 / chat 指令）叠加到当前行程上。
 *
 * - 指令类 result（type==='expense' / 'change_category' / 'accommodation' /
 *   'remove_expense' / 'rename'）→ 基于 base 做定向修改。
 * - 完整行程类 result（含 trip 或非空 legs）→ 覆盖 base，但以「保留 base 中
 *   已有非空值、仅用 result 里有内容的字段替换」为准。这样「PDF 先传，JPG 后
 *   覆盖」时，JPG 里 expenses=[] 不会把 PDF 已解析的费用清单冲掉；同时
 *   JPG 里 day.transport=[] 也不会把 PDF 在同一日期写入的航班记录冲掉。
 *
 * 返回新对象，不修改 base。
 */

const hasContent = (v) => {
  if (v === null || v === undefined) return false
  if (Array.isArray(v)) return v.length > 0
  if (typeof v === 'string') return v.trim().length > 0
  if (typeof v === 'object') return Object.keys(v).length > 0
  return true
}

/** 浅层保留合并：base 为底，result 中有内容的键覆盖到 base 上。 */
const mergePreservingEmpty = (base, result) => {
  const out = { ...(base || {}) }
  for (const key of Object.keys(result || {})) {
    if (hasContent(result[key])) out[key] = result[key]
  }
  return out
}

/**
 * 深度 legs 合并：以 base（已有数据）的城市/leg 结构为主，
 * 对每个有 date 字段的 day 做逐字段合并——base 已有的非空字段不被 result 覆盖，
 * result 中有内容而 base 为空的字段才补充进来。
 * result 中出现而 base 没有的额外 leg/day 追加到末尾。
 * 没有 date 字段的 day 直接使用 base 的版本（兼容老格式）。
 *
 * 设计原则：「PDF 先传，图片后传」时，PDF 已解析的航班/住宿/城市不被 OCR 乱码覆盖；
 * 图片仅用于填充 PDF 中尚未提取的空字段（如部分活动名称）。
 */
const mergeLegsDeep = (baseLegs, resultLegs) => {
  // 双重索引：
  //   resultDayByDateCity["date::city"] → 精确匹配（多城市同日场景必须）
  //   resultDayByDate["date"]           → 日期兜底（城市名称不匹配时使用）
  const resultDayByDateCity = {}
  const resultDayByDate = {}
  for (const leg of resultLegs || []) {
    for (const day of leg.days || []) {
      if (!day.date) continue
      resultDayByDateCity[`${day.date}::${leg.city}`] = day
      resultDayByDate[day.date] = day  // 同日期最后一个 leg 覆盖（兜底）
    }
  }

  // 预计算 base 中每个 date 的出现次数（同 date 多 sub-leg 场景）
  const dateOccurrenceCounts = {}
  for (const leg of baseLegs || []) {
    for (const day of leg.days || []) {
      if (day.date) dateOccurrenceCounts[day.date] = (dateOccurrenceCounts[day.date] || 0) + 1
    }
  }

  // 记录 base 已覆盖的 date，用于追加 result 独有的 day
  const baseDates = new Set()
  const dateSeenCounts = {}

  const merged = (baseLegs || []).map((leg) => ({
    ...leg,
    days: (leg.days || []).map((day) => {
      if (day.date) baseDates.add(day.date)
      dateSeenCounts[day.date] = (dateSeenCounts[day.date] || 0) + 1

      let resultDay = null
      if (day.date) {
        // 1. 优先按 date+city 精确匹配（处理维也纳+斯德哥尔摩同日期的情况）
        const cityKey = `${day.date}::${leg.city}`
        if (resultDayByDateCity[cityKey]) {
          resultDay = resultDayByDateCity[cityKey]
        } else {
          // 2. 城市名不匹配时，用日期兜底——但仅对该日期的最后一个 sub-leg 应用，
          //    避免 OCR 乱码数据被重复注入多个 sub-leg。
          const isLastOccurrence =
            dateSeenCounts[day.date] === dateOccurrenceCounts[day.date]
          if (isLastOccurrence) resultDay = resultDayByDate[day.date]
        }
      }

      if (!resultDay) return day

      // base 优先合并（现有数据不被新来源的空字段清空）
      const mergedDay = { ...mergePreservingEmpty(resultDay, day) }

      // 活动例外：新来源（如 PiTravel）的景点列表通常比 PDF 概览表更完整，
      // 当新来源有更多活动时，优先使用新来源的列表。
      const resultActs = resultDay.activities || []
      const baseActs = day.activities || []
      if (resultActs.length > baseActs.length) {
        mergedDay.activities = resultActs
      }

      return mergedDay
    }),
  }))

  // 追加 result 中有而 base 没有的 leg/day（如 PNG 包含更多天数）
  // 仅追加日期在行程范围内的日期，过滤 OCR 错误推断的跨年/跨月日期
  const baseDateList = Array.from(baseDates).filter((d) => /^\d{4}-\d{2}-\d{2}$/.test(d)).sort()
  const minDate = baseDateList[0] || null
  const maxDate = baseDateList[baseDateList.length - 1] || null

  for (const leg of resultLegs || []) {
    const extraDays = (leg.days || []).filter((day) => {
      if (!day.date || baseDates.has(day.date)) return false
      if (!minDate || !maxDate) return true
      // 只接受落在行程日期范围内的额外日期，拒绝 OCR 乱码产生的错误年月
      return day.date >= minDate && day.date <= maxDate
    })
    if (extraDays.length > 0) {
      merged.push({ ...leg, days: extraDays })
    }
  }
  return merged
}

export function applyAction(base, result) {
  if (result.type === 'expense' && base) {
    return {
      ...base,
      expenses: [...(base.expenses || []), ...(result.expenses || [])],
    }
  }
  if (result.type === 'change_category' && base) {
    const name = result.item_name || ''
    const target = result.target_category || '住宿'
    return {
      ...base,
      expenses: (base.expenses || []).map((exp) => {
        const desc = exp.description || ''
        if (name && desc.includes(name)) {
          return { ...exp, category: target }
        }
        return exp
      }),
    }
  }
  if (result.type === 'accommodation' && base) {
    const name = result.accommodation || ''
    const target = result.target_category || '住宿'
    return {
      ...base,
      expenses: (base.expenses || []).map((exp) => {
        const desc = exp.description || ''
        if (name && desc.includes(name)) {
          return { ...exp, category: target }
        }
        return exp
      }),
    }
  }
  if (result.type === 'remove_expense' && base) {
    const desc = result.description || ''
    return {
      ...base,
      expenses: (base.expenses || []).filter(
        (exp) => !desc || !(exp.description || '').includes(desc),
      ),
    }
  }
  if (result.type === 'rename' && base) {
    const { old_name, new_name } = result
    return {
      ...base,
      legs: (base.legs || []).map((leg) => ({
        ...leg,
        days: (leg.days || []).map((day) => ({
          ...day,
          activities: (day.activities || []).map((a) =>
            a === old_name ? new_name : a,
          ),
          accommodation:
            day.accommodation === old_name ? new_name : day.accommodation,
        })),
      })),
    }
  }
  if (result.trip || (result.legs && result.legs.length > 0)) {
    if (!base) return result
    const merged = mergePreservingEmpty(base, result)
    // 对 legs 做逐日深度合并：result 的城市结构优先，但每天的空字段不覆盖 base 的非空字段
    if (base.legs && base.legs.length > 0 && merged.legs && merged.legs.length > 0) {
      merged.legs = mergeLegsDeep(base.legs, merged.legs)
    }
    return merged
  }
  return base || result
}
