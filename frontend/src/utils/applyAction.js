/**
 * 把一个 parse 结果（上传 PDF / JPG / 自然语言 / chat 指令）叠加到当前行程上。
 *
 * - 指令类 result（type==='expense' / 'change_category' / 'accommodation' /
 *   'remove_expense' / 'rename'）→ 基于 base 做定向修改。
 * - 完整行程类 result（含 trip 或非空 legs）→ 覆盖 base，但以「保留 base 中
 *   已有非空值、仅用 result 里有内容的字段替换」为准。这样「PDF 先传，JPG 后
 *   覆盖」时，JPG 里 expenses=[] 不会把 PDF 已解析的费用清单冲掉。
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
    return mergePreservingEmpty(base, result)
  }
  return base || result
}
