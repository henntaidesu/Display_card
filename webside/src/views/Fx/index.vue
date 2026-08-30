<template>
  <div class="fx-page" v-loading="loading">
    <h2 class="page-title">{{ t('fx.title') }}</h2>

    <el-row :gutter="16">
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="today-card">
          <div class="today-label">{{ t('fx.today') }}</div>
          <div class="today-rate dc-mono" v-if="today">
            1 <span class="unit">{{ t('currency.JPY_short') }}</span> =
            {{ formatRate(today.rate) }} <span class="unit">{{ t('currency.CNY_short') }}</span>
          </div>
          <div class="today-rate" v-else>—</div>
          <div class="today-date dc-dim" v-if="today">
            {{ today.rate_date }}
            <span v-if="today.stale">{{ t('fx.stale', { date: today.rate_date }) }}</span>
          </div>
          <p class="ecb-note dc-dim">{{ t('fx.ecbNote') }}</p>
        </el-card>

        <el-card shadow="never" class="query-card">
          <template #header>{{ t('fx.query') }}</template>
          <div class="query-row">
            <el-date-picker v-model="queryDate" type="date" value-format="YYYY-MM-DD" :placeholder="t('fx.queryDate')" class="full" @change="doQuery" />
          </div>
          <div v-if="queryResult" class="query-result dc-mono">
            {{ formatRate(queryResult.rate) }}
            <span class="dc-dim">（{{ queryResult.rate_date }}<template v-if="queryResult.stale"> {{ t('fx.stale', { date: queryResult.rate_date }) }}</template>）</span>
          </div>
          <div v-else-if="queried" class="dc-dim">{{ t('fx.noRate') }}</div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="16">
        <el-card shadow="never">
          <template #header>
            <div class="chart-head">
              <span>{{ t('fx.trend') }}</span>
              <el-button size="small" :icon="Refresh" :loading="refreshing" @click="backfill">{{ t('fx.refresh') }}</el-button>
            </div>
          </template>
          <EChart v-if="history.length" :option="trendOption" height="300px" />
          <el-empty v-else :description="t('common.noData')" :image-size="80" />
        </el-card>

        <el-card shadow="never" class="config-card">
          <template #header>{{ t('settings.tabFx') }}</template>
          <div class="cfg-row">
            <span>{{ t('fx.source') }}</span>
            <el-select v-model="config.source" class="cfg-select" @change="saveConfig">
              <el-option v-for="a in config.available" :key="a.key" :label="a.label" :value="a.key" />
            </el-select>
          </div>
          <div class="cfg-row">
            <span>{{ t('fx.autoFetch') }}<br /><small class="dc-dim">{{ t('fx.autoFetchHint') }}</small></span>
            <el-switch v-model="config.auto_fetch" @change="saveConfig" />
          </div>
          <div class="cfg-row">
            <span>{{ t('fx.cachedRange') }}</span>
            <span class="dc-dim dc-mono">
              {{ t('fx.cachedCount', { n: config.cached_count }) }}
              <template v-if="config.cached_range?.min_date"> · {{ config.cached_range.min_date }} ~ {{ config.cached_range.max_date }}</template>
            </span>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Refresh } from '@element-plus/icons-vue'
import { fxApi } from '@/api'
import { ElMessage } from '@/utils/notify'
import { formatRate } from '@/utils/format'
import EChart from '@/components/EChart.vue'

const { t } = useI18n()

const loading = ref(false)
const refreshing = ref(false)
const today = ref(null)
const history = ref([])
const config = ref({ source: 'ecb', auto_fetch: true, available: [], cached_count: 0, cached_range: null })

const queryDate = ref(null)
const queryResult = ref(null)
const queried = ref(false)

const trendOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis', valueFormatter: (v) => formatRate(v) },
  grid: { left: 8, right: 12, bottom: 8, top: 20, containLabel: true },
  xAxis: { type: 'category', data: history.value.map((h) => h.date), axisLine: { lineStyle: { color: '#3a4456' } } },
  yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { color: '#1c2740' } }, axisLabel: { formatter: (v) => v.toFixed(4) } },
  series: [{
    type: 'line', smooth: true, showSymbol: false,
    data: history.value.map((h) => h.rate),
    itemStyle: { color: '#5b8cff' },
    lineStyle: { width: 2 },
    areaStyle: { color: 'rgba(91,140,255,0.12)' }
  }]
}))

async function loadAll() {
  loading.value = true
  try {
    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - 90)
    const fmt = (d) => d.toISOString().slice(0, 10)
    const [tRate, hist, cfg] = await Promise.all([
      fxApi.rate({}).catch(() => null),
      fxApi.history({ start: fmt(start), end: fmt(end) }),
      fxApi.getConfig()
    ])
    today.value = tRate
    history.value = hist.items
    config.value = cfg
  } finally {
    loading.value = false
  }
}

async function backfill() {
  refreshing.value = true
  try {
    const res = await fxApi.refresh({ days: 90 })
    ElMessage.success(t('fx.refreshDone', { n: res.cached }))
    await loadAll()
  } catch { /* 拦截器已提示 */ } finally {
    refreshing.value = false
  }
}

async function doQuery() {
  queried.value = true
  if (!queryDate.value) { queryResult.value = null; return }
  try {
    queryResult.value = await fxApi.rate({ date: queryDate.value })
  } catch {
    queryResult.value = null
  }
}

async function saveConfig() {
  try {
    config.value = await fxApi.setConfig({ source: config.value.source, auto_fetch: config.value.auto_fetch })
    ElMessage.success(t('common.saved'))
  } catch { /* 拦截器已提示 */ }
}

onMounted(loadAll)
</script>

<style scoped>
.page-title { font-size: 20px; margin-bottom: 16px; }
.today-card { margin-bottom: 16px; text-align: center; padding: 8px 0; }
.today-label { color: #8a94a6; font-size: 13px; margin-bottom: 10px; }
.today-rate { font-size: 26px; color: #e6edf7; font-weight: 600; }
.today-rate .unit { font-size: 14px; color: #8a94a6; font-weight: 400; }
.today-date { font-size: 12px; margin-top: 8px; }
.ecb-note { font-size: 12px; margin-top: 14px; line-height: 1.6; padding: 0 12px; }
.query-card :deep(.el-card__body) { padding-top: 12px; }
.query-row { margin-bottom: 10px; }
.full { width: 100% !important; }
.query-result { font-size: 18px; color: #e6edf7; }
.chart-head { display: flex; justify-content: space-between; align-items: center; }
.config-card { margin-top: 16px; }
.cfg-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #1c2740; }
.cfg-row:last-child { border-bottom: none; }
.cfg-row > span { color: #c7d0de; font-size: 14px; }
.cfg-select { width: 220px !important; }
</style>
