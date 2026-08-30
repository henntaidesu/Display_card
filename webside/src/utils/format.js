// 金额、状态、颜色的展示辅助。所有文案走 i18n，这里只管数值格式和颜色。

// 状态对应的 Element tag 主题色。测试不通过用 danger，成交类用 success，
// 中间流转用 info/warning，让列表扫一眼就能分出「出问题的」和「快到手的」。
export const STATUS_TAG_TYPE = {
  purchased: 'info',
  pending_test: 'warning',
  test_passed: 'success',
  test_failed: 'danger',
  returning: 'primary',
  forwarding: 'primary',
  received: 'success',
  paid: 'success'
}

// 状态在流程里的先后，用于按流程排序而不是字母序
export const STATUS_ORDER = [
  'purchased', 'pending_test', 'test_passed', 'test_failed',
  'returning', 'forwarding', 'received', 'paid'
]

export function currencySymbol(code) {
  return code === 'JPY' ? '¥' : '￥'
}

// 金额格式化：日元不留小数（日元没有分），人民币两位小数。
export function formatMoney(amount, currency = 'CNY') {
  if (amount === null || amount === undefined || amount === '') return '—'
  const num = Number(amount)
  if (Number.isNaN(num)) return '—'
  const digits = currency === 'JPY' ? 0 : 2
  const symbol = currencySymbol(currency)
  return symbol + num.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

// 人民币专用，概览页大量用
export function cny(amount) {
  return formatMoney(amount, 'CNY')
}

export function formatRate(rate) {
  if (rate === null || rate === undefined) return '—'
  // 1 日元换几分钱人民币，量级 0.04 左右，留 4~5 位才看得出变化
  return Number(rate).toFixed(5)
}

// 利润着色：正绿负红，0 和缺失用默认色
export function profitClass(value) {
  if (value === null || value === undefined) return ''
  if (value > 0) return 'dc-profit'
  if (value < 0) return 'dc-loss'
  return ''
}

export function firstImage(media) {
  if (!Array.isArray(media)) return null
  return media.find((m) => m.kind === 'image') || media[0] || null
}
