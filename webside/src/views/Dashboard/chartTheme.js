/**
 * 概览页图表的配色与通用轴 / 提示框配置。
 *
 * SERIES 是分类色的**固定顺位**：取色一律按 SERIES[i] 顺序取，不要循环、不要另生成颜色，
 * 也不要按数值大小重排——同一个实体（比如「收入」）在整页每张图里必须始终是同一个颜色。
 * 状态色（STATUS）只表达「好 / 警告 / 危险」语义，绝不当作第 N 个系列色使用。
 */
export const SURFACE = '#131c2f'

export const SERIES = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300']

/** 「其他」这类残差桶专用的中性灰：它不是一个实体，不该占用分类顺位 */
export const NEUTRAL = '#5a6a88'

export const STATUS = {
  good: '#4ade80',
  warning: '#f5a623',
  danger: '#f87171'
}

export const INK = {
  primary: '#e6edf7',
  secondary: '#9ba8bf',
  muted: '#7f8da6',
  grid: '#26314a',
  axis: '#33405c'
}

/** 千分位整数（数量类：卡数、件数） */
export function formatInt(v) {
  const n = Number(v || 0)
  if (!Number.isFinite(n)) return '0'
  return Math.round(n).toLocaleString('en-US')
}

/** 图表里的人民币：小数位在图上没有信息量，一律取整 */
export function money(v) {
  return `￥${formatInt(v)}`
}

/** 坐标轴刻度：万位以上压缩，避免刻度文字互相挤掉 */
export function formatAxisNumber(v) {
  const n = Number(v || 0)
  if (Math.abs(n) >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (Math.abs(n) >= 10000) return `${Math.round(n / 1000)}k`
  return formatInt(n)
}

/** MM-DD（30/90 天区间下完整日期会挤成一团） */
export function shortDate(ymd) {
  return String(ymd || '').slice(5)
}

/** 提示框统一样式：深色卡片底 + 细边。confine 把它约束在图内，
 *  否则窄屏点最右侧那根柱子时会溢出到屏幕外，只能看到半个数值。 */
export const tooltipStyle = {
  confine: true,
  backgroundColor: '#0f1830',
  borderColor: '#2f3d58',
  borderWidth: 1,
  padding: [8, 12],
  textStyle: { color: INK.primary, fontSize: 12 },
  extraCssText: 'box-shadow: 0 6px 20px rgba(0,0,0,.45); border-radius: 8px;'
}

/** 坐标轴：网格与轴线是贴近底色的实线细发丝线，永远不用虚线 */
export function categoryAxis(data, opts = {}) {
  return {
    type: 'category',
    data,
    boundaryGap: opts.boundaryGap !== false,
    axisLine: { lineStyle: { color: INK.axis } },
    axisTick: { show: false },
    axisLabel: { color: INK.muted, fontSize: 11, ...(opts.axisLabel || {}) },
    splitLine: { show: false }
  }
}

export function valueAxis(opts = {}) {
  return {
    type: 'value',
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: INK.muted,
      fontSize: 11,
      formatter: opts.formatter || formatAxisNumber
    },
    splitLine: { lineStyle: { color: INK.grid, width: 1, type: 'solid' } },
    ...(opts.extra || {})
  }
}
