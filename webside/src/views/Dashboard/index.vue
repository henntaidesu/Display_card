<template>
  <div class="dashboard" v-loading="loading">
    <h2 class="page-title">{{ t('dashboard.title') }}</h2>

    <el-alert
      v-if="summary.incomplete_cards"
      :title="t('dashboard.incompleteWarn', { n: summary.incomplete_cards })"
      type="warning"
      show-icon
      :closable="false"
      class="warn"
    />

    <!-- 统计卡 -->
    <div class="stat-grid">
      <StatCard :label="t('dashboard.totalCards')" :value="summary.total_cards" icon="Cpu" tone="blue" />
      <StatCard :label="t('dashboard.inStock')" :value="summary.in_stock_cards" icon="Box" tone="cyan" />
      <StatCard :label="t('dashboard.sold')" :value="summary.sold_cards" icon="Sell" tone="violet" />
      <StatCard :label="t('dashboard.totalCost')" :value="cny(summary.total_cost_cny)" icon="Coin" tone="amber" mono />
      <StatCard :label="t('dashboard.totalRevenue')" :value="cny(summary.total_revenue_cny)" icon="Money" tone="teal" mono />
      <StatCard
        :label="t('dashboard.totalProfit')"
        :value="cny(summary.total_profit_cny)"
        icon="TrendCharts"
        :tone="profitTone"
        mono
      />
      <StatCard :label="t('dashboard.avgProfit')" :value="cny(summary.avg_profit_cny)" icon="Histogram" tone="blue" mono />
      <StatCard :label="t('dashboard.margin')" :value="marginText" icon="PieChart" tone="violet" mono />
    </div>

    <el-row :gutter="16" class="charts">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never">
          <template #header>{{ t('dashboard.monthlyProfit') }}</template>
          <EChart v-if="monthly.length" :option="monthlyOption" height="320px" />
          <el-empty v-else :description="t('dashboard.noSold')" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card shadow="never">
          <template #header>{{ t('dashboard.byStatus') }}</template>
          <EChart v-if="hasStatus" :option="statusOption" height="320px" />
          <el-empty v-else :description="t('common.noData')" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="charts">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never">
          <template #header>{{ t('dashboard.recent') }}</template>
          <el-table :data="recent" size="small" @row-click="goDetail">
            <el-table-column :label="t('card.mgmtNo')" width="120">
              <template #default="{ row }"><span class="dc-mono mgmt">{{ row.mgmt_no }}</span></template>
            </el-table-column>
            <el-table-column :label="t('card.model')" min-width="150">
              <template #default="{ row }">{{ [row.brand, row.model].filter(Boolean).join(' ') || t('card.noModel') }}</template>
            </el-table-column>
            <el-table-column :label="t('card.status')" width="100">
              <template #default="{ row }"><StatusTag :status="row.status" /></template>
            </el-table-column>
            <el-table-column :label="t('card.profit')" width="110" align="right">
              <template #default="{ row }">
                <span class="dc-mono" :class="profitClass(row.money.profit_cny)">{{ cny(row.money.profit_cny) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card shadow="never">
          <template #header>{{ t('dashboard.topModels') }}</template>
          <el-table :data="topModels" size="small">
            <el-table-column type="index" width="44" />
            <el-table-column :label="t('card.model')" min-width="140" prop="model" />
            <el-table-column :label="t('dashboard.count')" width="70" align="center" prop="count" />
            <el-table-column :label="t('card.profit')" width="110" align="right">
              <template #default="{ row }">
                <span class="dc-mono" :class="profitClass(row.profit_cny)">{{ cny(row.profit_cny) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onActivated, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { dashboardApi } from '@/api'
import { cny, profitClass, STATUS_ORDER, STATUS_TAG_TYPE } from '@/utils/format'
import EChart from '@/components/EChart.vue'
import StatusTag from '@/components/StatusTag.vue'
import StatCard from './StatCard.vue'

defineOptions({ name: 'Dashboard' })

const { t } = useI18n()
const router = useRouter()

const loading = ref(false)
const summary = ref({
  total_cards: 0, in_stock_cards: 0, sold_cards: 0, by_status: {},
  total_cost_cny: 0, total_revenue_cny: 0, total_profit_cny: 0,
  avg_profit_cny: null, profit_margin: null, incomplete_cards: 0, monthly: []
})
const recent = ref([])
const topModels = ref([])

const monthly = computed(() => summary.value.monthly || [])
const hasStatus = computed(() => Object.values(summary.value.by_status || {}).some((v) => v > 0))

const profitTone = computed(() => {
  const p = summary.value.total_profit_cny
  return p > 0 ? 'green' : p < 0 ? 'red' : 'blue'
})
const marginText = computed(() =>
  summary.value.profit_margin === null ? '—' : summary.value.profit_margin + '%'
)

// 状态色映射到 echarts 颜色，与列表页 tag 一致的语义
const STATUS_COLORS = {
  info: '#8a94a6', warning: '#f5a623', success: '#4ade80',
  danger: '#f87171', primary: '#5b8cff'
}

const monthlyOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis' },
  legend: { data: [t('dashboard.cost'), t('dashboard.revenue'), t('dashboard.profit')], textStyle: { color: '#a6adb4' } },
  grid: { left: 8, right: 12, bottom: 8, top: 40, containLabel: true },
  xAxis: { type: 'category', data: monthly.value.map((m) => m.month), axisLine: { lineStyle: { color: '#3a4456' } } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1c2740' } } },
  series: [
    { name: t('dashboard.cost'), type: 'bar', data: monthly.value.map((m) => m.cost), itemStyle: { color: '#f5a623' } },
    { name: t('dashboard.revenue'), type: 'bar', data: monthly.value.map((m) => m.revenue), itemStyle: { color: '#38bdf8' } },
    { name: t('dashboard.profit'), type: 'line', smooth: true, data: monthly.value.map((m) => m.profit), itemStyle: { color: '#4ade80' }, lineStyle: { width: 3 } }
  ]
}))

const statusOption = computed(() => {
  const data = STATUS_ORDER
    .filter((s) => (summary.value.by_status?.[s] || 0) > 0)
    .map((s) => ({
      name: t('status.' + s),
      value: summary.value.by_status[s],
      itemStyle: { color: STATUS_COLORS[STATUS_TAG_TYPE[s]] || '#8a94a6' }
    }))
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { color: '#a6adb4' } },
    series: [{
      type: 'pie', radius: ['42%', '68%'], center: ['50%', '44%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#131c2f', borderWidth: 2 },
      label: { color: '#c7d0de' },
      data
    }]
  }
})

async function load() {
  loading.value = true
  try {
    const [s, r, tm] = await Promise.all([
      dashboardApi.summary(),
      dashboardApi.recent({ limit: 8 }),
      dashboardApi.topModels({ limit: 8 })
    ])
    summary.value = s
    recent.value = r.items
    topModels.value = tm.items
  } finally {
    loading.value = false
  }
}

function goDetail(row) {
  router.push(`/cards/${row.id}`)
}

onActivated(load)
</script>

<style scoped>
.page-title { font-size: 20px; margin-bottom: 16px; }
.warn { margin-bottom: 16px; }
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 16px;
}
.charts { margin-bottom: 16px; }
.charts :deep(.el-table__row) { cursor: pointer; }
.mgmt { font-size: 12px; color: #8fb8ff; }
@media (max-width: 1100px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 768px) { .stat-grid { grid-template-columns: repeat(2, 1fr); gap: 10px; } }
</style>
