<template>
  <div class="dashboard">
    <!-- 区间筛选：整页共用一行，不在各图卡片里另设筛选 -->
    <div class="dash-toolbar">
      <h2 class="page-title">{{ t('dashboard.title') }}</h2>
      <div class="dash-actions">
        <el-radio-group :model-value="days" size="small" @change="selectRange">
          <el-radio-button v-for="d in RANGE_PRESETS" :key="d" :label="d">
            {{ d === 0 ? t('dashboard.allTime') : t('dashboard.lastNDays', { n: d }) }}
          </el-radio-button>
        </el-radio-group>
        <el-button size="small" :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <span class="dash-stamp">{{ t('dashboard.updatedAt') }} {{ generatedAt }}</span>
      </div>
    </div>

    <el-alert
      v-if="stock.incomplete_cards"
      :title="t('dashboard.incompleteWarn', { n: stock.incomplete_cards })"
      type="warning"
      show-icon
      :closable="false"
      class="warn"
    />

    <!-- 重新取数时保留上一版渲染并降透明度，避免骨架屏闪动与高度跳变 -->
    <div class="dash-body" :class="{ 'is-refreshing': loading && loaded }" v-loading="loading && !loaded">
      <!-- ── 经营概览 ─────────────────────────────────────────── -->
      <div class="kpi-row">
        <div v-for="card in kpiCards" :key="card.key" class="kpi-tile" :class="{ 'is-primary': card.primary }">
          <div class="kpi-label">{{ card.label }}</div>
          <div class="kpi-value">{{ card.value }}</div>
          <div class="kpi-meta">
            <span
              class="kpi-delta"
              :class="card.delta.good === null ? 'flat' : card.delta.good ? 'good' : 'bad'"
            >
              <template v-if="card.delta.dir === 'up'">▲</template>
              <template v-else-if="card.delta.dir === 'down'">▼</template>
              {{ card.delta.text }}
            </span>
            <span class="kpi-vs">{{ t('dashboard.vsPrev') }}</span>
          </div>
          <div class="kpi-foot">
            <span>{{ t('dashboard.today') }} {{ card.today }}</span>
            <span v-if="card.note" class="kpi-note">{{ card.note }}</span>
          </div>
          <svg v-if="card.spark" class="kpi-spark" viewBox="0 0 100 28" preserveAspectRatio="none">
            <polyline :points="card.spark" fill="none" :stroke="card.accent" stroke-width="1.5"
                      stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />
          </svg>
        </div>
      </div>

      <!-- ── 收支趋势 + 待处理 ─────────────────────────────────── -->
      <div class="dash-grid grid-8-4">
        <el-card class="dash-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon :color="SERIES0"><TrendCharts /></el-icon>
                {{ t('dashboard.revenueTrend') }}
              </span>
              <el-radio-group v-model="trendView" size="small">
                <el-radio-button label="chart">{{ t('dashboard.viewChart') }}</el-radio-button>
                <el-radio-button label="table">{{ t('dashboard.viewTable') }}</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <EChart v-if="trendView === 'chart'" :option="trendOption" height="300px" />
          <!-- 表格视图：图表的等价读法，保证任何数值都不只能靠悬浮提示才读得到 -->
          <el-table v-else :data="trend" size="small" height="300" stripe class="num-table">
            <el-table-column prop="date" :label="t('dashboard.date')" width="110" />
            <el-table-column :label="t('dashboard.bought')" width="70" align="right">
              <template #default="{ row }">{{ formatInt(row.bought) }}</template>
            </el-table-column>
            <el-table-column :label="t('dashboard.sold')" width="70" align="right">
              <template #default="{ row }">{{ formatInt(row.sold) }}</template>
            </el-table-column>
            <el-table-column :label="t('dashboard.cost')" align="right">
              <template #default="{ row }">{{ cny(row.cost) }}</template>
            </el-table-column>
            <el-table-column :label="t('dashboard.revenue')" align="right">
              <template #default="{ row }">{{ cny(row.revenue) }}</template>
            </el-table-column>
            <el-table-column :label="t('dashboard.profit')" align="right">
              <template #default="{ row }">
                <span :class="profitClass(row.profit)">{{ cny(row.profit) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="dash-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon :color="STATUS.warning"><Bell /></el-icon>
                {{ t('dashboard.workQueue') }}
              </span>
            </div>
          </template>
          <ul class="work-list">
            <li
              v-for="row in workRows"
              :key="row.key"
              class="work-row"
              :class="[row.tone, { 'is-zero': !row.value }]"
              @click="goCards(row.query)"
            >
              <span class="work-dot"></span>
              <span class="work-label">{{ row.label }}</span>
              <span class="work-value">{{ formatInt(row.value) }}</span>
            </li>
          </ul>
        </el-card>
      </div>

      <!-- ── 每日进出 + 状态构成 ───────────────────────────────── -->
      <div class="dash-grid grid-6-6">
        <el-card class="dash-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon :color="SERIES0"><Histogram /></el-icon>
                {{ t('dashboard.dailyFlow') }}
              </span>
            </div>
          </template>
          <EChart :option="countOption" height="210px" />
        </el-card>

        <el-card class="dash-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon :color="SERIES0"><PieChart /></el-icon>
                {{ t('dashboard.byStatus') }}
              </span>
              <span class="card-note">{{ t('dashboard.allCardsNote') }}</span>
            </div>
          </template>
          <div v-if="statusSegments.length" class="share-block">
            <EChart :option="statusOption" height="46px" />
            <ul class="share-legend">
              <li v-for="s in statusSegments" :key="s.key">
                <span class="legend-swatch" :style="{ background: s.color }"></span>
                <span class="legend-name">{{ s.name }}</span>
                <span class="legend-value">{{ formatInt(s.value) }}</span>
                <span class="legend-share">{{ share(statusSegments, s.value) }}</span>
              </li>
            </ul>
          </div>
          <el-empty v-else :image-size="52" :description="t('common.noData')" />
        </el-card>
      </div>

      <!-- ── 库存健康度 ─────────────────────────────────────────── -->
      <el-card class="dash-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span class="card-title">
              <el-icon :color="SERIES0"><Goods /></el-icon>
              {{ t('dashboard.stockHealth') }}
            </span>
            <span class="card-note">{{ t('dashboard.allCardsNote') }}</span>
          </div>
        </template>
        <div class="stock-body">
          <div class="stock-share">
            <div class="block-title">{{ t('dashboard.inStockMix') }}</div>
            <template v-if="inStockSegments.length">
              <EChart :option="inStockOption" height="46px" />
              <ul class="share-legend">
                <li v-for="s in inStockSegments" :key="s.key">
                  <span class="legend-swatch" :style="{ background: s.color }"></span>
                  <span class="legend-name">{{ s.name }}</span>
                  <span class="legend-value">{{ formatInt(s.value) }}</span>
                  <span class="legend-share">{{ share(inStockSegments, s.value) }}</span>
                </li>
              </ul>
            </template>
            <el-empty v-else :image-size="52" :description="t('common.noData')" />
          </div>
          <div class="stock-tiles">
            <div
              v-for="row in stockTiles"
              :key="row.key"
              class="mini-tile"
              :class="{ warn: row.warn }"
              @click="goCards(row.query)"
            >
              <div class="mini-value">{{ row.value }}</div>
              <div class="mini-label">{{ row.label }}</div>
            </div>
          </div>
        </div>
      </el-card>

      <!-- ── 平台对比 + 型号排行 ────────────────────────────────── -->
      <div class="dash-grid grid-5-7">
        <el-card class="dash-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon :color="SERIES0"><Connection /></el-icon>
                {{ t('dashboard.platformCompare') }}
              </span>
            </div>
          </template>
          <div v-if="platformRows.length" class="platform-list">
            <div v-for="p in platformRows" :key="p.platform" class="platform-row">
              <div class="platform-head">
                <span class="legend-swatch" :style="{ background: p.color }"></span>
                <span class="platform-name">{{ p.label }}</span>
                <span class="platform-amount">{{ cny(p.cost) }}</span>
                <span class="platform-share">{{ p.sharePct }}</span>
              </div>
              <div class="platform-meter">
                <div class="platform-fill" :style="{ width: p.widthPct, background: p.color }"></div>
              </div>
              <div class="platform-sub">
                <span>{{ t('dashboard.bought') }} {{ formatInt(p.count) }}</span>
                <span>{{ t('dashboard.sold') }} {{ formatInt(p.sold) }}</span>
                <span>{{ t('dashboard.revenue') }} {{ cny(p.revenue) }}</span>
                <span>{{ t('dashboard.profit') }} {{ cny(p.profit) }}</span>
              </div>
            </div>
          </div>
          <el-empty v-else :image-size="52" :description="t('common.noData')" />
        </el-card>

        <el-card class="dash-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon :color="SERIES0"><Trophy /></el-icon>
                {{ t('dashboard.topModels') }}
              </span>
            </div>
          </template>
          <el-table :data="topModels" size="small" stripe class="num-table">
            <el-table-column type="index" width="44" />
            <el-table-column :label="t('card.model')" min-width="150" prop="model" />
            <el-table-column :label="t('dashboard.count')" width="80" align="right">
              <template #default="{ row }">{{ formatInt(row.count) }}</template>
            </el-table-column>
            <el-table-column :label="t('dashboard.sold')" width="80" align="right">
              <template #default="{ row }">{{ formatInt(row.sold) }}</template>
            </el-table-column>
            <el-table-column :label="t('card.profit')" width="120" align="right">
              <template #default="{ row }">
                <span class="dc-mono" :class="profitClass(row.profit_cny)">{{ cny(row.profit_cny) }}</span>
              </template>
            </el-table-column>
            <template #empty><span class="dc-dim">{{ t('common.noData') }}</span></template>
          </el-table>
        </el-card>
      </div>

      <!-- ── 最近录入 ───────────────────────────────────────────── -->
      <el-card class="dash-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span class="card-title">
              <el-icon :color="SERIES0"><Tickets /></el-icon>
              {{ t('dashboard.recent') }}
            </span>
          </div>
        </template>
        <el-table :data="recent" size="small" stripe class="num-table clickable" @row-click="goDetail">
          <el-table-column :label="t('card.mgmtNo')" width="130">
            <template #default="{ row }"><span class="dc-mono mgmt">{{ row.mgmt_no }}</span></template>
          </el-table-column>
          <el-table-column :label="t('card.model')" min-width="160">
            <template #default="{ row }">{{ [row.brand, row.model].filter(Boolean).join(' ') || t('card.noModel') }}</template>
          </el-table-column>
          <el-table-column :label="t('card.status')" width="110">
            <template #default="{ row }"><StatusTag :status="row.status" /></template>
          </el-table-column>
          <el-table-column :label="t('card.purchaseDate')" width="120">
            <template #default="{ row }"><span class="dc-mono dc-dim">{{ row.purchase_date || '—' }}</span></template>
          </el-table-column>
          <el-table-column :label="t('card.cost')" width="120" align="right">
            <template #default="{ row }"><span class="dc-mono">{{ cny(row.money.cost_total_cny) }}</span></template>
          </el-table-column>
          <el-table-column :label="t('card.profit')" width="120" align="right">
            <template #default="{ row }">
              <span class="dc-mono" :class="profitClass(row.money.profit_cny)">{{ cny(row.money.profit_cny) }}</span>
            </template>
          </el-table-column>
          <template #empty><span class="dc-dim">{{ t('common.noData') }}</span></template>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onActivated, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  Bell, Connection, Goods, Histogram, PieChart, Refresh, Tickets, TrendCharts, Trophy
} from '@element-plus/icons-vue'
import { dashboardApi } from '@/api'
import { cny, profitClass, STATUS_ORDER } from '@/utils/format'
import EChart from '@/components/EChart.vue'
import StatusTag from '@/components/StatusTag.vue'
import { NEUTRAL, SERIES, STATUS, formatInt } from './chartTheme.js'
import { buildCountOption, buildShareBarOption, buildTrendOption } from './charts.js'

defineOptions({ name: 'Dashboard' })

const { t } = useI18n()
const router = useRouter()

/** 区间预设：0 = 「全部」，起点由后端取全库最早的交易日 */
const RANGE_PRESETS = [7, 14, 30, 90, 0]
const SERIES0 = SERIES[0]

/** 状态色：每个状态一个固定颜色，整页任何图里都不换。
 *  「测试不通过」用红、「已打款」用绿是语义色，其余取分类顺位里互相分得开的色。 */
const STATUS_COLOR = {
  purchased: '#5a6a88',
  pending_test: '#c98500',
  test_passed: '#3987e5',
  test_failed: '#d03b3b',
  returning: '#7c5cff',
  returned: '#d55181',
  forwarding: '#d95926',
  received: '#199e70',
  paid: '#008300'
}

/** 「待处理」面板的行：流程没走完、需要人推一把的状态 */
const WORK_ROWS = [
  { key: 'test_failed', status: 'test_failed', tone: 'critical' },
  { key: 'pending_test', status: 'pending_test', tone: 'warning' },
  { key: 'forwarding', status: 'forwarding', tone: 'warning' },
  { key: 'received', status: 'received', tone: 'warning' },
  { key: 'returning', status: 'returning', tone: 'plain' },
  { key: 'returned', status: 'returned', tone: 'plain' }
]

const days = ref(30)
const loading = ref(false)
const loaded = ref(false)
const trendView = ref('chart')
const data = ref(null)
const recent = ref([])
const topModels = ref([])

// ── 取数 ──────────────────────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const [summary, r, tm] = await Promise.all([
      dashboardApi.summary({ days: days.value }),
      dashboardApi.recent({ limit: 8 }),
      dashboardApi.topModels({ limit: 8 })
    ])
    data.value = summary
    recent.value = r.items
    topModels.value = tm.items
    loaded.value = true
  } finally {
    loading.value = false
  }
}

function selectRange(d) {
  if (days.value === d) return
  days.value = d
  load()
}

// ── 展示辅助 ──────────────────────────────────────────────────────────────
const trend = computed(() => data.value?.trend || [])
const stock = computed(() => data.value?.stock || {})
const granularity = computed(() => data.value?.trend_granularity || 'day')

const generatedAt = computed(() => {
  const ts = data.value?.generated_at
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString()
})

/** 环比：dir 为 up/down/flat，good 表示这个方向是不是好事（决定颜色） */
function delta(current, previous, upIsGood) {
  const cur = Number(current || 0)
  const prev = Number(previous || 0)
  if (!prev) return { text: prev === cur ? '—' : t('dashboard.noPrev'), dir: 'flat', good: null }
  const pct = ((cur - prev) / Math.abs(prev)) * 100
  const dir = pct > 0.05 ? 'up' : pct < -0.05 ? 'down' : 'flat'
  return {
    text: `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`,
    dir,
    good: dir === 'flat' ? null : (dir === 'up') === Boolean(upIsGood)
  }
}

/** 利润率的环比用百分点差，不用相对变化率——「利润率涨了 50%」读起来完全没有意义 */
function deltaPoints(current, previous) {
  if (current === null || current === undefined || previous === null || previous === undefined) {
    return { text: t('dashboard.noPrev'), dir: 'flat', good: null }
  }
  const diff = Number(current) - Number(previous)
  const dir = diff > 0.05 ? 'up' : diff < -0.05 ? 'down' : 'flat'
  return {
    text: `${diff > 0 ? '+' : ''}${diff.toFixed(1)}pt`,
    dir,
    good: dir === 'flat' ? null : dir === 'up'
  }
}

/** 迷你走势：折线点坐标（0-100 × 0-28 视口），点数不够时返回 null 让模板跳过 */
function sparkline(field) {
  const values = trend.value.map((d) => Number(d[field] || 0))
  if (values.length < 2) return null
  const max = Math.max(...values)
  const min = Math.min(...values, 0)
  const span = max - min || 1
  return values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * 100
      const y = 28 - ((v - min) / span) * 26 - 1
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')
}

const pct = (v) => (v === null || v === undefined ? '—' : `${v}%`)

const kpiCards = computed(() => {
  const kpi = data.value?.kpi
  if (!kpi) return []
  const cur = kpi.current || {}
  const prev = kpi.previous || {}
  const today = kpi.today || {}
  return [
    {
      key: 'profit',
      label: t('dashboard.totalProfit'),
      value: cny(cur.profit),
      today: cny(today.profit),
      note: cur.margin === null ? '' : t('dashboard.marginNote', { rate: cur.margin }),
      delta: delta(cur.profit, prev.profit, true),
      spark: sparkline('profit'),
      accent: SERIES[1],
      primary: true
    },
    {
      key: 'revenue',
      label: t('dashboard.totalRevenue'),
      value: cny(cur.revenue),
      today: cny(today.revenue),
      note: '',
      delta: delta(cur.revenue, prev.revenue, true),
      spark: sparkline('revenue'),
      accent: SERIES[0]
    },
    {
      key: 'cost',
      label: t('dashboard.totalCost'),
      value: cny(cur.cost),
      today: cny(today.cost),
      note: '',
      delta: delta(cur.cost, prev.cost, false),
      spark: sparkline('cost'),
      accent: SERIES[3]
    },
    {
      key: 'sold',
      label: t('dashboard.soldCount'),
      value: formatInt(cur.sold_count),
      today: formatInt(today.sold_count),
      note: cur.avg_profit === null ? '' : t('dashboard.avgProfitNote', { value: cny(cur.avg_profit) }),
      delta: delta(cur.sold_count, prev.sold_count, true),
      spark: sparkline('sold'),
      accent: SERIES[2]
    },
    {
      key: 'bought',
      label: t('dashboard.boughtCount'),
      value: formatInt(cur.bought_count),
      today: formatInt(today.bought_count),
      note: '',
      delta: delta(cur.bought_count, prev.bought_count, true),
      spark: sparkline('bought'),
      accent: SERIES[0]
    },
    {
      key: 'margin',
      label: t('dashboard.margin'),
      value: pct(cur.margin),
      today: pct(today.margin),
      note: '',
      delta: deltaPoints(cur.margin, prev.margin),
      spark: null,
      accent: SERIES[4]
    }
  ]
})

// ── 图表 option ───────────────────────────────────────────────────────────
const chartLabels = computed(() => ({
  cost: t('dashboard.cost'),
  revenue: t('dashboard.revenue'),
  profit: t('dashboard.profit'),
  bought: t('dashboard.bought'),
  sold: t('dashboard.sold')
}))

const trendOption = computed(() => buildTrendOption(trend.value, chartLabels.value, granularity.value))
const countOption = computed(() => buildCountOption(trend.value, chartLabels.value, granularity.value))

function segmentsFrom(counts) {
  return STATUS_ORDER
    .map((key) => ({
      key,
      name: t('status.' + key),
      value: Number((counts || {})[key] || 0),
      color: STATUS_COLOR[key] || NEUTRAL
    }))
    .filter((s) => s.value > 0)
}

const statusSegments = computed(() => segmentsFrom(stock.value.by_status))
const inStockSegments = computed(() => segmentsFrom(stock.value.in_stock_by_status))
const statusOption = computed(() => buildShareBarOption(statusSegments.value))
const inStockOption = computed(() => buildShareBarOption(inStockSegments.value))

function share(segments, value) {
  const total = segments.reduce((sum, s) => sum + s.value, 0)
  return total ? `${((value / total) * 100).toFixed(1)}%` : '—'
}

// ── 待处理 / 库存 ─────────────────────────────────────────────────────────
const workRows = computed(() => {
  const work = data.value?.work || {}
  const rows = WORK_ROWS.map((row) => ({
    key: row.key,
    label: t('status.' + row.status),
    value: work[row.status] || 0,
    tone: row.tone,
    query: { status: row.status }
  }))
  rows.push({
    key: 'incomplete',
    label: t('dashboard.missingFx'),
    value: work.incomplete || 0,
    tone: 'critical',
    query: { status: '' }
  })
  return rows
})

const stockTiles = computed(() => {
  const s = stock.value
  return [
    { key: 'total', label: t('dashboard.totalCards'), value: formatInt(s.total_cards), query: { status: '' } },
    { key: 'inStock', label: t('dashboard.inStock'), value: formatInt(s.in_stock_cards), query: { status: '' } },
    { key: 'sold', label: t('dashboard.sold'), value: formatInt(s.sold_cards), query: { status: '' } },
    { key: 'inStockCost', label: t('dashboard.inStockCost'), value: cny(s.in_stock_cost_cny), query: { status: '' } },
    { key: 'allCost', label: t('dashboard.totalCost'), value: cny(s.total_cost_cny), query: { status: '' } },
    { key: 'allRevenue', label: t('dashboard.totalRevenue'), value: cny(s.total_revenue_cny), query: { status: '' } },
    { key: 'allProfit', label: t('dashboard.totalProfit'), value: cny(s.total_profit_cny), query: { status: '' } },
    { key: 'avgProfit', label: t('dashboard.avgProfit'), value: cny(s.avg_profit_cny), query: { status: '' } },
    { key: 'margin', label: t('dashboard.margin'), value: pct(s.profit_margin), query: { status: '' } },
    {
      key: 'incomplete',
      label: t('dashboard.missingFx'),
      value: formatInt(s.incomplete_cards),
      warn: s.incomplete_cards > 0,
      query: { status: '' }
    }
  ]
})

// ── 平台对比 ──────────────────────────────────────────────────────────────
const PLATFORM_COLOR = { yahoo: SERIES[0], mercari: SERIES[1], other: NEUTRAL }

const platformRows = computed(() => {
  const rows = data.value?.platforms || []
  const max = Math.max(1, ...rows.map((r) => Number(r.cost || 0)))
  const total = rows.reduce((sum, r) => sum + Number(r.cost || 0), 0)
  return rows.map((r) => ({
    ...r,
    color: PLATFORM_COLOR[r.platform] || NEUTRAL,
    label: t('platform.' + r.platform),
    widthPct: `${Math.max(2, (Number(r.cost || 0) / max) * 100).toFixed(1)}%`,
    sharePct: total ? `${((Number(r.cost || 0) / total) * 100).toFixed(1)}%` : '—'
  }))
})

// ── 跳转 ──────────────────────────────────────────────────────────────────
function goCards(query) {
  router.push({ path: '/cards', query: query || {} })
}
function goDetail(row) {
  router.push(`/cards/${row.id}`)
}

onActivated(load)
</script>

<style scoped>
/* 配色沿用全站暗色（卡片 #131c2f / 描边 #2a3446），数据色一律来自 chartTheme.js
   的固定顺位，这里只写版式与中性色。 */

/* ── 顶部工具条：区间筛选一行管全页 ─────────────────────────── */
.dash-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.page-title { font-size: 20px; }
.dash-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.dash-stamp {
  font-size: 12px;
  color: #7f8da6;
  font-variant-numeric: tabular-nums;
}
.warn { margin-bottom: 16px; }

/* 刷新时按住上一版画面，不闪骨架、不跳高度 */
.dash-body { transition: opacity 0.18s ease; }
.dash-body.is-refreshing { opacity: 0.55; pointer-events: none; }

/* ── KPI ────────────────────────────────────────────────────── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.kpi-tile {
  position: relative;
  overflow: hidden;
  background: #131c2f;
  border: 1px solid #2a3446;
  border-radius: 10px;
  /* 底部留出 30px 给迷你走势，让它落在文字下方而不是压着文字 */
  padding: 14px 16px 30px;
}
.kpi-tile.is-primary { border-color: #38496a; }
.kpi-label { font-size: 12px; color: #9ba8bf; }
.kpi-value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 650;
  line-height: 1.15;
  color: #ecf2ff;
  overflow-wrap: anywhere;
}
.kpi-meta {
  margin-top: 6px;
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
}
.kpi-delta { font-weight: 600; font-variant-numeric: tabular-nums; }
.kpi-delta.good { color: #4ade80; }
.kpi-delta.bad { color: #f87171; }
.kpi-delta.flat { color: #7f8da6; }
.kpi-vs { color: #7f8da6; }
.kpi-foot {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  font-size: 12px;
  color: #7f8da6;
  font-variant-numeric: tabular-nums;
}
.kpi-note { color: #9ba8bf; }
.kpi-spark {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100%;
  height: 26px;
  opacity: 0.5;
  pointer-events: none;
}

/* ── 栅格 ───────────────────────────────────────────────────── */
.dash-grid {
  display: grid;
  gap: 16px;
  margin-bottom: 16px;
}
.grid-8-4 { grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); }
.grid-6-6 { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
.grid-5-7 { grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); }
@media (max-width: 1200px) {
  .grid-8-4, .grid-6-6, .grid-5-7 { grid-template-columns: 1fr; }
}

.dash-card { border-radius: 10px; margin-bottom: 16px; }
.dash-grid .dash-card { margin-bottom: 0; }
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.card-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #e6edf7;
}
.card-note { font-size: 12px; color: #7f8da6; }

/* 表格里的数字列纵向对齐，用等宽数字 */
.num-table :deep(td) { font-variant-numeric: tabular-nums; }
.clickable :deep(.el-table__row) { cursor: pointer; }
.mgmt { font-size: 12px; color: #8fb8ff; }

/* ── 待处理列表 ─────────────────────────────────────────────── */
.work-list { list-style: none; margin: 0; padding: 0; }
.work-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 4px;
  border-bottom: 1px solid #1f2a3f;
  cursor: pointer;
  transition: background 0.15s ease;
}
.work-row:last-child { border-bottom: none; }
/* 触摸屏没有 hover：点过的行会一直停在 hover 底色，看着像被选中了 */
@media (hover: hover) {
  .work-row:hover { background: #18233a; }
}
.work-row:active { background: #18233a; }
.work-label { flex: 1; min-width: 0; font-size: 13px; color: #d6deea; }
.work-value {
  font-size: 16px;
  font-weight: 650;
  color: #ecf2ff;
  font-variant-numeric: tabular-nums;
}
.work-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: #4c5b78;
}
/* 状态色只表达「警告 / 危险」，不当系列色用；计数为 0 时整行转灰，
   免得一堆红点常驻，真正要处理的那条反而不显眼 */
.work-row.critical .work-dot { background: #d03b3b; }
.work-row.warning .work-dot { background: #fab219; }
.work-row.is-zero .work-dot { background: #3a4762; }
.work-row.is-zero .work-value { color: #6d7b95; }

/* ── 占比条 + 图例（图例同时充当表格，数值不只藏在悬浮提示里） ── */
.share-block { display: flex; flex-direction: column; gap: 10px; }
.share-legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 4px 16px;
}
.share-legend li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #9ba8bf;
  padding: 3px 0;
}
.legend-swatch {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  flex-shrink: 0;
  display: inline-block;
  vertical-align: middle;
}
.legend-name {
  flex: 1;
  min-width: 0;
  color: #d6deea;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.legend-value { color: #ecf2ff; font-weight: 600; font-variant-numeric: tabular-nums; }
.legend-share { width: 48px; text-align: right; font-variant-numeric: tabular-nums; }

/* ── 库存健康度 ─────────────────────────────────────────────── */
.stock-body {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
  gap: 20px;
}
@media (max-width: 1200px) {
  .stock-body { grid-template-columns: 1fr; }
}
.block-title { font-size: 12px; color: #9ba8bf; margin-bottom: 10px; }
.stock-tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
  align-content: start;
}
.mini-tile {
  background: #18233a;
  border: 1px solid #26314a;
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color 0.15s ease;
}
@media (hover: hover) {
  .mini-tile:hover { border-color: #3a4c6e; }
}
.mini-tile:active { border-color: #3a4c6e; }
.mini-tile.warn { border-color: #6a4a1c; }
.mini-value {
  font-size: 18px;
  font-weight: 650;
  color: #ecf2ff;
  font-variant-numeric: tabular-nums;
}
.mini-label { margin-top: 2px; font-size: 12px; color: #8b98b0; }

/* ── 平台对比（平台就两三个，不做饼图，用带刻度的量条 + 数字） ── */
.platform-list { display: flex; flex-direction: column; gap: 18px; }
.platform-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}
.platform-name { flex: 1; min-width: 0; font-size: 13px; color: #d6deea; }
.platform-amount { font-size: 15px; font-weight: 650; color: #ecf2ff; }
.platform-share {
  width: 52px;
  text-align: right;
  font-size: 12px;
  color: #7f8da6;
  font-variant-numeric: tabular-nums;
}
.platform-meter {
  height: 10px;
  border-radius: 5px;
  background: #1c2740;
  overflow: hidden;
}
.platform-fill { height: 100%; border-radius: 5px; }
.platform-sub {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  font-size: 12px;
  color: #8b98b0;
  font-variant-numeric: tabular-nums;
}

/* ── 手机端：断点 768px，与全站一致 ───────────────────────────── */
@media (max-width: 768px) {
  .dash-toolbar { margin-bottom: 12px; gap: 8px; }
  /* 区间预设有 5 个，日文 / 英文文案下一行放不下。不换行、改成横向可滑，
     比折成两行更省纵向空间，也不会随语言变高度。 */
  .dash-actions { width: 100%; gap: 8px; }
  .dash-actions :deep(.el-radio-group) {
    flex: 1 1 auto;
    min-width: 0;
    flex-wrap: nowrap;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .dash-actions :deep(.el-radio-group)::-webkit-scrollbar { display: none; }
  .dash-actions :deep(.el-radio-button__inner) { white-space: nowrap; }
  .dash-stamp { flex: 1 1 100%; }

  /* KPI 一行两块：6 块单列排下来要划满两屏 */
  .kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
  .kpi-tile { padding: 11px 12px 26px; }
  /* 金额位数多时宁可折行也不截断——省略号会把 ￥12,345,678 读成 ￥12,345… */
  .kpi-value { font-size: 18px; }
  .kpi-label, .kpi-meta, .kpi-foot { font-size: 11px; }
  .kpi-foot { margin-top: 6px; gap: 2px 8px; }
  .kpi-spark { height: 22px; }

  .dash-grid { gap: 12px; margin-bottom: 12px; }
  .dash-card { margin-bottom: 12px; }
  .card-header { flex-wrap: wrap; row-gap: 8px; gap: 8px; }
  .card-title { font-size: 14px; }

  /* 整行可点：38px 高在手机上偏小，抬到 44px */
  .work-row { padding: 12px 4px; }
  .work-label { font-size: 14px; }

  .stock-body { gap: 14px; }
  .share-legend { grid-template-columns: 1fr; }
  .share-legend li { padding: 5px 0; }
  .mini-tile { padding: 10px; }

  .platform-list { gap: 14px; }
  .platform-head { flex-wrap: wrap; }
  .platform-name { flex: 1 1 100%; }
  .platform-amount { flex: 1 1 auto; }
}
</style>
