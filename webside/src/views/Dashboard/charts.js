/**
 * 概览页各图表的 ECharts option 构造。
 *
 * 约定（与 chartTheme.js 的配色规则配套）：
 * - 金额类共用一个 y 轴（成本 / 收入 / 利润同为人民币）；数量是另一个量纲，单独成图，
 *   绝不和金额共图做双 y 轴——两套刻度怎么对齐都是任意的，会凭空造出并不存在的相关性。
 * - 收入用柱、利润用线：形状本身是第二重区分通道，色觉障碍用户不必只靠颜色分辨。
 * - 不给数据点逐个标数值，靠图例 + 悬浮提示 + 「表格」视图读数。
 */
import {
  INK,
  SERIES,
  SURFACE,
  categoryAxis,
  formatInt,
  money,
  shortDate,
  tooltipStyle,
  valueAxis
} from './chartTheme.js'

/** x 轴刻度：按日时省掉年份，按月时保留 YYYY-MM */
function axisTicks(trend, granularity) {
  return trend.map((d) => (granularity === 'month' ? d.date : shortDate(d.date)))
}

function row(label, value, dim = false) {
  const color = dim ? INK.secondary : INK.primary
  return `<div style="display:flex;justify-content:space-between;gap:16px;color:${color}">
            <span>${label}</span>
            <b style="font-variant-numeric:tabular-nums">${value}</b>
          </div>`
}

/** 收入（柱）+ 成本（柱）+ 利润（线），同一人民币轴 */
export function buildTrendOption(trend, labels, granularity = 'day') {
  return {
    backgroundColor: 'transparent',
    grid: { top: 34, left: 8, right: 12, bottom: 4, containLabel: true },
    legend: {
      top: 0,
      right: 0,
      itemWidth: 12,
      itemHeight: 8,
      itemGap: 16,
      icon: 'roundRect',
      textStyle: { color: INK.secondary, fontSize: 12 },
      data: [labels.revenue, labels.cost, labels.profit]
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: '#41507080', width: 1 } },
      ...tooltipStyle,
      formatter: (params) => {
        if (!params || !params.length) return ''
        const full = trend[params[0].dataIndex] || {}
        const series = params.map((p) => row(`${p.marker}${p.seriesName}`, money(p.value))).join('')
        return (
          `<div style="margin-bottom:6px;color:${INK.secondary}">${full.date || ''}</div>` +
          series +
          row(labels.bought, formatInt(full.bought), true) +
          row(labels.sold, formatInt(full.sold), true)
        )
      }
    },
    xAxis: categoryAxis(axisTicks(trend, granularity)),
    yAxis: valueAxis(),
    series: [
      {
        name: labels.revenue,
        type: 'bar',
        barMaxWidth: 18,
        itemStyle: { color: SERIES[0], borderRadius: [4, 4, 0, 0] },
        data: trend.map((d) => d.revenue)
      },
      {
        name: labels.cost,
        type: 'bar',
        barMaxWidth: 18,
        itemStyle: { color: SERIES[3], borderRadius: [4, 4, 0, 0] },
        data: trend.map((d) => d.cost)
      },
      {
        name: labels.profit,
        type: 'line',
        smooth: false,
        showSymbol: false,
        symbolSize: 8,
        lineStyle: { color: SERIES[1], width: 2, cap: 'round', join: 'round' },
        itemStyle: { color: SERIES[1], borderColor: SURFACE, borderWidth: 2 },
        data: trend.map((d) => d.profit)
      }
    ]
  }
}

/** 每日（或每月）购入 / 售出张数 */
export function buildCountOption(trend, labels, granularity = 'day') {
  return {
    backgroundColor: 'transparent',
    grid: { top: 30, left: 8, right: 12, bottom: 4, containLabel: true },
    legend: {
      top: 0,
      right: 0,
      itemWidth: 12,
      itemHeight: 8,
      itemGap: 16,
      icon: 'roundRect',
      textStyle: { color: INK.secondary, fontSize: 12 },
      data: [labels.bought, labels.sold]
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: '#41507080', width: 1 } },
      ...tooltipStyle,
      formatter: (params) => {
        if (!params || !params.length) return ''
        const full = trend[params[0].dataIndex] || {}
        return (
          `<div style="margin-bottom:4px;color:${INK.secondary}">${full.date || ''}</div>` +
          params.map((p) => row(`${p.marker}${p.seriesName}`, formatInt(p.value))).join('')
        )
      }
    },
    xAxis: categoryAxis(axisTicks(trend, granularity)),
    yAxis: valueAxis({ formatter: (v) => formatInt(v) }),
    series: [
      {
        name: labels.bought,
        type: 'bar',
        barMaxWidth: 16,
        itemStyle: { color: SERIES[0], borderRadius: [4, 4, 0, 0] },
        data: trend.map((d) => d.bought)
      },
      {
        name: labels.sold,
        type: 'bar',
        barMaxWidth: 16,
        itemStyle: { color: SERIES[2], borderRadius: [4, 4, 0, 0] },
        data: trend.map((d) => d.sold)
      }
    ]
  }
}

/**
 * 占比条：一根横向堆叠柱，段与段之间用 1px 底色描边形成缝隙。
 * segments: [{ key, name, value, color }]
 */
export function buildShareBarOption(segments) {
  const visible = segments.filter((s) => Number(s.value || 0) > 0)
  const last = visible.length - 1
  return {
    backgroundColor: 'transparent',
    grid: { top: 0, left: 0, right: 0, bottom: 0 },
    tooltip: {
      trigger: 'item',
      ...tooltipStyle,
      formatter: (p) => row(`${p.marker}${p.seriesName}`, formatInt(p.value))
    },
    // 占比条只表达比例，刻度轴没有信息量：整条柱就是 100%，各段数值由下方图例给出
    xAxis: { type: 'value', show: false },
    yAxis: { type: 'category', data: [''], show: false },
    series: visible.map((s, i) => ({
      name: s.name,
      type: 'bar',
      stack: 'share',
      barWidth: 22,
      itemStyle: {
        color: s.color,
        borderColor: SURFACE,
        borderWidth: 1,
        borderRadius:
          visible.length === 1 ? 4 : i === 0 ? [4, 0, 0, 4] : i === last ? [0, 4, 4, 0] : 0
      },
      data: [s.value]
    }))
  }
}
