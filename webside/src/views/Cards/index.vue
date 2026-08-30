<template>
  <div class="cards-page">
    <div class="page-head">
      <h2 class="page-title">{{ t('route.cards') }}</h2>
      <el-button type="primary" :icon="Plus" @click="openAdd">{{ t('common.add') }}</el-button>
    </div>

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
        <el-table-column :label="t('card.mgmtNo')" width="130">
          <template #default="{ row }"><span class="dc-mono mgmt">{{ row.mgmt_no }}</span></template>
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
        <el-table-column :label="t('card.cost')" width="120" align="right">
          <template #default="{ row }">
            <span class="dc-mono">{{ cny(row.money.cost_total_cny) }}</span>
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
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  EditPen, Picture, Plus, Refresh, Search, WarningFilled
} from '@element-plus/icons-vue'
import { cardsApi, optionsApi, systemApi } from '@/api'
import { cny, firstImage, profitClass } from '@/utils/format'
import { useMetaStore } from '@/stores/meta'
import CardFormDialog from '@/components/CardFormDialog.vue'
import StatusTag from '@/components/StatusTag.vue'

defineOptions({ name: 'Cards' })

const { t } = useI18n()
const router = useRouter()
const meta = useMetaStore()

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

const statuses = computed(() => meta.enums.statuses || [])
const platforms = computed(() => meta.enums.source_platforms || [])

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

async function fetch() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      keyword: filters.keyword || undefined,
      status: filters.status.length ? filters.status.join(',') : undefined,
      brand: filters.brand || undefined,
      source_platform: filters.source_platform || undefined
    }
    const res = await cardsApi.list(params)
    rows.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
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

onActivated(() => {
  loadAux()
  fetch()
})
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-title { font-size: 20px; }
.filter-card { margin-bottom: 16px; }
.filter-card :deep(.el-card__body) { padding: 14px 16px; }
.filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.f-keyword { width: 220px !important; }
.f-status { width: 200px !important; }
.f-brand { width: 160px !important; }
.f-platform { width: 150px !important; }

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
  .f-keyword, .f-status, .f-brand, .f-platform { width: 100% !important; }
  .filters { flex-direction: column; align-items: stretch; }
}
</style>
