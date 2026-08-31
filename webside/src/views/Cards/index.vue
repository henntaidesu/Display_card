<template>
  <div class="cards-page">
    <div class="page-head">
      <h2 class="page-title">{{ t('route.cards') }}</h2>
      <el-button type="primary" :icon="Plus" @click="openAdd">{{ t('common.add') }}</el-button>
    </div>

    <!-- 统计模块：随下方筛选联动，覆盖整个筛选结果（不只当前页）。
         手机端不展示——8 张卡两列排下来要划掉大半屏才看得到表格。 -->
    <el-card v-if="!isMobile" class="stats-card" shadow="never">
      <div v-loading="statsLoading">
        <el-row :gutter="16" class="stat-row">
          <el-col v-for="card in statCards" :key="card.key" :xs="12" :sm="12" :md="8" :lg="6" :xl="3">
            <StatCard
              :label="card.label"
              :value="card.value"
              :icon="card.icon"
              :color="card.color"
              :value-class="card.valueClass"
            />
          </el-col>
        </el-row>
        <div v-if="stats.incomplete" class="stats-warn">
          <el-icon><WarningFilled /></el-icon>
          <span>{{ t('dashboard.incompleteWarn', { n: stats.incomplete }) }}</span>
        </div>
      </div>
    </el-card>

    <!-- 筛选行 -->
    <el-card class="filter-card" shadow="never">
      <div class="filters">
        <el-input
          v-model="filters.keyword"
          :placeholder="t('common.search')"
          clearable
          class="f-keyword"
          @keyup.enter="reload"
          @clear="reload"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="filters.status" multiple collapse-tags :placeholder="t('card.status')" clearable class="f-status" @change="reload">
          <el-option v-for="s in statuses" :key="s" :label="t('status.' + s)" :value="s" />
        </el-select>
        <el-select v-model="filters.brand" :placeholder="t('card.brand')" clearable filterable class="f-brand" @change="reload">
          <el-option v-for="b in usedBrands" :key="b.brand" :label="`${b.brand} (${b.count})`" :value="b.brand" />
        </el-select>
        <el-select v-model="filters.source_platform" :placeholder="t('card.platform')" clearable class="f-platform" @change="reload">
          <el-option v-for="p in platforms" :key="p" :label="t('platform.' + p)" :value="p" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          :start-placeholder="t('card.purchaseDate')"
          :end-placeholder="t('card.purchaseDate')"
          class="f-date"
          @change="reload"
        />
        <el-button :icon="Refresh" @click="resetFilters">{{ t('common.reset') }}</el-button>
      </div>
    </el-card>

    <!-- 表格 -->
    <el-card class="table-card" shadow="never">
      <el-table
        v-loading="loading"
        :data="rows"
        class="cards-table"
        row-key="id"
        @row-click="goDetail"
      >
        <el-table-column :label="t('card.cover')" width="82">
          <template #default="{ row }">
            <div class="cover" @click.stop="goDetail(row)">
              <img v-if="cover(row)" :src="cover(row)" alt="" loading="lazy" />
              <el-icon v-else class="cover-empty"><Picture /></el-icon>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('card.model')" min-width="180">
          <template #default="{ row }">
            <div class="model-cell">
              <span class="model-name">{{ modelLabel(row) }}</span>
              <span v-if="row.vram" class="dc-dim vram">{{ row.vram }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('card.status')" width="110">
          <template #default="{ row }"><StatusTag :status="row.status" /></template>
        </el-table-column>
        <el-table-column :label="t('card.purchaseDate')" width="120">
          <template #default="{ row }"><span class="dc-mono dc-dim">{{ row.purchase_date || '—' }}</span></template>
        </el-table-column>
        <el-table-column :label="t('card.saleDate')" width="120">
          <template #default="{ row }"><span class="dc-mono dc-dim">{{ row.sale_date || '—' }}</span></template>
        </el-table-column>
        <el-table-column :label="t('card.cost')" width="140" align="right">
          <template #default="{ row }">
            <span class="dc-mono">{{ cny(row.money.cost_total_cny) }}</span>
            <!-- 成本是按资金池的注资汇率折的，不是买卡当天的牌价——标出来，免得对不上账 -->
            <el-tooltip v-if="row.money.from_pool" :content="t('card.fundPoolHint')">
              <el-tag size="small" type="primary" effect="plain" class="pool-tag">{{ t('card.poolTag') }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column :label="t('card.saleAmount')" width="120" align="right">
          <template #default="{ row }">
            <span class="dc-mono">{{ cny(row.money.sale_cny) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('card.profit')" width="130" align="right">
          <template #default="{ row }">
            <span class="dc-mono" :class="profitClass(row.money.profit_cny)">
              {{ cny(row.money.profit_cny) }}
            </span>
            <el-tooltip v-if="row.money.incomplete" :content="t('card.incomplete')">
              <el-icon class="warn-icon"><WarningFilled /></el-icon>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column :label="t('common.actions')" width="90" fixed="right" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" text bg :icon="EditPen" @click.stop="openEdit(row)">
              {{ t('common.edit') }}
            </el-button>
          </template>
        </el-table-column>
        <template #empty><span class="dc-dim">{{ t('common.noData') }}</span></template>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="fetch"
          @size-change="fetch"
        />
      </div>
    </el-card>

    <CardFormDialog
      v-model="dialogVisible"
      :card="editing"
      :hosting-configured="hostingConfigured"
      @saved="onSaved"
    />
  </div>
</template>

<script setup>
import { computed, onActivated, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  EditPen, Picture, Plus, Refresh, Search, WarningFilled
} from '@element-plus/icons-vue'
import { cardsApi, optionsApi, systemApi } from '@/api'
import { cny, firstImage, profitClass } from '@/utils/format'
import { useIsMobile } from '@/composables/useIsMobile'
import { useMetaStore } from '@/stores/meta'
import CardFormDialog from '@/components/CardFormDialog.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'

defineOptions({ name: 'Cards' })

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const meta = useMetaStore()
const { isMobile } = useIsMobile()

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const usedBrands = ref([])
const hostingConfigured = ref(true)

const dialogVisible = ref(false)
const editing = ref(null)

const filters = reactive({ keyword: '', status: [], brand: null, source_platform: null })
// 购入日期区间：绑定 daterange 选择器，拆成 purchase_from/purchase_to 传后端
const dateRange = ref(null)

const emptyStats = () => ({
  total: 0, in_stock: 0, sold: 0,
  total_cost_cny: 0, total_revenue_cny: 0, total_profit_cny: 0,
  avg_profit_cny: null, profit_margin: null, incomplete: 0
})
const stats = ref(emptyStats())
const statsLoading = ref(false)

const statuses = computed(() => meta.enums.statuses || [])
const platforms = computed(() => meta.enums.source_platforms || [])

// 顶部统计卡。顺序固定：先数量、后金额，颜色跟着指标走，不随数值变化重排
const statCards = computed(() => {
  const s = stats.value
  const profit = s.total_profit_cny
  return [
    { key: 'total', label: t('dashboard.totalCards'), value: s.total, icon: 'Cpu', color: '#409EFF' },
    { key: 'inStock', label: t('dashboard.inStock'), value: s.in_stock, icon: 'Box', color: '#E6A23C' },
    { key: 'sold', label: t('dashboard.sold'), value: s.sold, icon: 'Sell', color: '#67C23A' },
    { key: 'cost', label: t('dashboard.totalCost'), value: cny(s.total_cost_cny), icon: 'Coin', color: '#F56C6C' },
    { key: 'revenue', label: t('dashboard.totalRevenue'), value: cny(s.total_revenue_cny), icon: 'Money', color: '#38bdf8' },
    {
      key: 'profit',
      label: t('dashboard.totalProfit'),
      value: cny(profit),
      icon: 'TrendCharts',
      color: profit > 0 ? '#67C23A' : profit < 0 ? '#F56C6C' : '#409EFF',
      valueClass: profitClass(profit)
    },
    { key: 'avgProfit', label: t('dashboard.avgProfit'), value: cny(s.avg_profit_cny), icon: 'Histogram', color: '#a78bfa' },
    {
      key: 'margin',
      label: t('dashboard.margin'),
      value: s.profit_margin === null ? '—' : s.profit_margin + '%',
      icon: 'PieChart',
      color: '#2dd4bf'
    }
  ]
})

function cover(row) {
  const img = firstImage(row.media)
  if (!img) return null
  return img.kind === 'image'
    ? img.public_url + (img.public_url.includes('?') ? '&' : '?') + 'w=200'
    : null
}
function modelLabel(row) {
  const label = [row.brand, row.model].filter(Boolean).join(' ')
  return label || t('card.noModel')
}

// 列表和统计共用的筛选参数
function filterParams() {
  return {
    keyword: filters.keyword || undefined,
    status: filters.status.length ? filters.status.join(',') : undefined,
    brand: filters.brand || undefined,
    source_platform: filters.source_platform || undefined,
    purchase_from: dateRange.value?.[0] || undefined,
    purchase_to: dateRange.value?.[1] || undefined
  }
}

async function fetch() {
  loading.value = true
  try {
    const res = await cardsApi.list({ ...filterParams(), page: page.value, page_size: pageSize.value })
    rows.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
  fetchStats()
}

async function fetchStats() {
  statsLoading.value = true
  try {
    stats.value = await cardsApi.stats(filterParams())
  } catch {
    stats.value = emptyStats()
  } finally {
    statsLoading.value = false
  }
}

function reload() {
  page.value = 1
  fetch()
}
function resetFilters() {
  filters.keyword = ''
  filters.status = []
  filters.brand = null
  filters.source_platform = null
  dateRange.value = null
  reload()
}

async function loadAux() {
  await meta.ensure()
  const [ub, ih] = await Promise.all([
    optionsApi.usedBrands(),
    systemApi.getImageHosting().catch(() => ({ configured: false }))
  ])
  usedBrands.value = ub.items || []
  hostingConfigured.value = Boolean(ih.configured)
}

function openAdd() {
  editing.value = null
  dialogVisible.value = true
}
function openEdit(row) {
  editing.value = row
  dialogVisible.value = true
}
function goDetail(row) {
  router.push(`/cards/${row.id}`)
}

async function onSaved() {
  await fetch()
  loadAux()
}

// 概览页点进来时带 ?status=xxx，直接把筛选摆好；带空的 status= 表示「看全部」。
// 判断的是「有没有这个参数」而不是它真不真：从详情页返回时 query 是空的，
// 那种情况下必须原样保留用户自己设的筛选，不能顺手清掉。
function applyRouteQuery() {
  if (!('status' in route.query)) return
  const status = route.query.status
  filters.status = String(status || '').split(',').filter(Boolean)
  page.value = 1
}

onActivated(() => {
  applyRouteQuery()
  loadAux()
  fetch()
})
</script>

<style scoped>
.pool-tag { margin-left: 5px; transform: scale(0.85); }
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-title { font-size: 20px; }

/* 顶部统计卡（与 FreeMarket_Manager 库存页同一套版式） */
.stats-card { margin-bottom: 16px; border-radius: 8px; }
/* 换行后两排卡片之间的空隙由 el-col 的下边距给出；最后一排多出来的那 16px
   用行的负下边距抵掉，否则卡片和卡片底之间会比左右留白宽一截 */
.stat-row { margin-bottom: -16px; }
.stat-row :deep(.el-col) { margin-bottom: 16px; }
.stats-warn {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 16px;
  font-size: 12px;
  color: #f5a623;
}

.filter-card { margin-bottom: 16px; }
.filter-card :deep(.el-card__body) { padding: 14px 16px; }
.filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.f-keyword { width: 220px !important; }
.f-status { width: 200px !important; }
.f-brand { width: 160px !important; }
.f-platform { width: 150px !important; }
.f-date { width: 260px !important; }

.cards-table :deep(.el-table__row) { cursor: pointer; }
.cover {
  width: 54px;
  height: 40px;
  border-radius: 6px;
  overflow: hidden;
  background: #0e1830;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cover img { width: 100%; height: 100%; object-fit: cover; }
.cover-empty { color: #3a4a66; font-size: 18px; }
.mgmt { font-size: 12px; color: #8fb8ff; }
.model-cell { display: flex; flex-direction: column; }
.model-name { color: #e6edf7; }
.vram { font-size: 12px; }
.warn-icon { color: #f5a623; margin-left: 4px; vertical-align: middle; }
.pager { display: flex; justify-content: flex-end; margin-top: 16px; }

@media (max-width: 768px) {
  .f-keyword, .f-status, .f-brand, .f-platform, .f-date { width: 100% !important; }
  .filters { flex-direction: column; align-items: stretch; }
}
</style>
