<template>
  <div class="detail" v-loading="loading">
    <div class="detail-head">
      <el-button :icon="ArrowLeft" text @click="$router.back()">{{ t('common.close') }}</el-button>
      <div class="head-right" v-if="card">
        <el-button :icon="EditPen" @click="editVisible = true">{{ t('common.edit') }}</el-button>
        <el-button :icon="Refresh" :disabled="card.fx_manual" @click="refreshFx">{{ t('card.fxRefreshed') }}</el-button>
      </div>
    </div>

    <template v-if="card">
      <div class="title-row">
        <span class="dc-mono mgmt">{{ card.mgmt_no }}</span>
        <h2 class="model">{{ [card.brand, card.model].filter(Boolean).join(' ') || t('card.noModel') }}</h2>
        <span v-if="card.vram" class="vram-badge">{{ card.vram }}</span>
        <StatusTag :status="card.status" />
      </div>

      <el-row :gutter="16">
        <el-col :xs="24" :lg="10">
          <!-- 关键信息 -->
          <el-card shadow="never" class="info-card">
            <template #header>{{ t('card.purchaseInfo') }} / {{ t('card.saleInfo') }}</template>
            <div class="kv"><span>{{ t('card.serialNo') }}</span><b>{{ card.serial_no || '—' }}</b></div>
            <div class="kv"><span>{{ t('card.platform') }}</span><b>{{ card.source_platform ? t('platform.' + card.source_platform) : '—' }}</b></div>
            <div class="kv"><span>{{ t('card.seller') }}</span><b>{{ card.seller || '—' }}</b></div>
            <div class="kv"><span>{{ t('card.orderNo') }}</span><b>{{ card.order_no || '—' }}</b></div>
            <div class="kv"><span>{{ t('card.itemUrl') }}</span>
              <a v-if="card.item_url" :href="card.item_url" target="_blank" class="link">{{ t('common.detail') }} ↗</a>
              <b v-else>—</b>
            </div>
            <el-divider />
            <div class="kv"><span>{{ t('card.purchaseDate') }}</span><b>{{ card.purchase_date || '—' }}</b></div>
            <div class="kv"><span>{{ t('card.purchaseAmount') }}</span><b>{{ money(card.purchase_amount, card.purchase_currency) }}</b></div>
            <div class="kv"><span>{{ t('card.intlShipping') }}</span><b>{{ money(card.intl_shipping_amount, card.intl_shipping_currency) }}</b></div>
            <div class="kv"><span>{{ t('card.purchaseFx') }}</span><b class="dc-mono">{{ card.purchase_fx_rate ? formatRate(card.purchase_fx_rate) : '—' }}<span class="dc-dim" v-if="card.purchase_fx_date"> · {{ card.purchase_fx_date }}</span></b></div>
            <div class="kv"><span>{{ t('card.fundSource') }}</span>
              <b>
                {{ card.fund_source === 'pool' ? t('card.fundPool') : t('card.fundOwn') }}
                <span v-if="card.fund_source === 'pool' && card.money.pool_fx_rate" class="dc-dim dc-mono"> · {{ formatRate(card.money.pool_fx_rate) }}</span>
              </b>
            </div>
            <el-divider />
            <div class="kv"><span>{{ t('card.saleDate') }}</span><b>{{ card.sale_date || '—' }}</b></div>
            <div class="kv"><span>{{ t('card.saleAmount') }}</span><b>{{ money(card.sale_amount, card.sale_currency) }}</b></div>
            <div class="kv"><span>{{ t('card.domesticShipping') }}</span><b>{{ money(card.domestic_shipping_amount, card.domestic_shipping_currency) }}</b></div>
            <div class="kv"><span>{{ t('card.saleFx') }}</span><b class="dc-mono">{{ card.sale_fx_rate ? formatRate(card.sale_fx_rate) : '—' }}<span class="dc-dim" v-if="card.sale_fx_date"> · {{ card.sale_fx_date }}</span></b></div>
            <div v-if="card.note" class="note">{{ card.note }}</div>
          </el-card>

          <!-- 利润卡 -->
          <el-card shadow="never" class="profit-card">
            <div class="profit-row"><span>{{ t('card.cost') }}</span><b class="dc-mono">{{ cny(card.money.cost_total_cny) }}</b></div>
            <div class="profit-row"><span>{{ t('card.revenue') }}</span><b class="dc-mono">{{ cny(card.money.sale_cny) }}</b></div>
            <div class="profit-row big">
              <span>{{ t('card.profit') }}</span>
              <b class="dc-mono" :class="profitClass(card.money.profit_cny)">{{ cny(card.money.profit_cny) }}</b>
            </div>
            <div class="profit-row"><span>{{ t('card.margin') }}</span><b class="dc-mono">{{ card.money.profit_margin === null ? '—' : card.money.profit_margin + '%' }}</b></div>
            <el-alert v-if="card.money.incomplete" :title="t('card.incomplete')" type="warning" :closable="false" show-icon class="mt" />
          </el-card>

          <!-- 资金池分摊：这张卡的日元是从哪几批注资里出的，各按什么汇率折成人民币 -->
          <el-card v-if="card.fund_draws?.length" shadow="never" class="pool-card">
            <template #header>
              <div class="pool-head">
                <span>{{ t('funds.poolBreakdown') }}</span>
                <router-link to="/funds" class="link">{{ t('route.funds') }} ↗</router-link>
              </div>
            </template>
            <div v-for="d in card.fund_draws" :key="d.id" class="pool-draw">
              <div class="pool-draw-head">
                <span>{{ t('funds.cat.' + d.category) }}</span>
                <b class="dc-mono">{{ money(d.amount, 'JPY') }} → {{ cny(d.cny_amount) }}</b>
              </div>
              <div v-for="(a, i) in d.allocations" :key="i" class="pool-alloc">
                <span class="dc-dim dc-mono">{{ a.inject_date }}</span>
                <span class="dc-mono">{{ money(a.amount, 'JPY') }}</span>
                <span class="dc-dim">÷ {{ formatRate(a.fx_rate) }} =</span>
                <span class="dc-mono">{{ cny(a.cny_amount) }}</span>
              </div>
              <div v-if="d.shortfall" class="pool-alloc short">
                <span>{{ t('funds.shortfall') }}</span>
                <span class="dc-mono">{{ money(d.shortfall, 'JPY') }}</span>
                <span class="dc-dim">{{ t('funds.shortfallHint') }}</span>
              </div>
            </div>
          </el-card>

          <!-- 状态流转 -->
          <el-card shadow="never" class="log-card" v-if="card.status_logs?.length">
            <template #header>{{ t('card.status') }}</template>
            <el-timeline>
              <el-timeline-item
                v-for="(log, i) in card.status_logs"
                :key="i"
                :timestamp="fmtTime(log.occurred_at)"
                placement="top"
              >
                {{ t('status.' + log.to_status) }}
                <span v-if="log.note" class="dc-dim">· {{ log.note }}</span>
              </el-timeline-item>
            </el-timeline>
          </el-card>
        </el-col>

        <el-col :xs="24" :lg="14">
          <el-card shadow="never">
            <template #header>{{ t('card.media') }}</template>
            <MediaManager ref="mediaRef" :card-id="card.id" :hosting-configured="hostingConfigured" />
          </el-card>
        </el-col>
      </el-row>

      <CardFormDialog v-model="editVisible" :card="card" :hosting-configured="hostingConfigured" @saved="reload" @media-changed="reloadMedia" />
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, EditPen, Refresh } from '@element-plus/icons-vue'
import { cardsApi, systemApi } from '@/api'
import { ElMessage } from '@/utils/notify'
import { cny, formatMoney, formatRate, profitClass } from '@/utils/format'
import { useMetaStore } from '@/stores/meta'
import MediaManager from '@/components/MediaManager.vue'
import CardFormDialog from '@/components/CardFormDialog.vue'
import StatusTag from '@/components/StatusTag.vue'

const { t } = useI18n()
const route = useRoute()
const meta = useMetaStore()

const card = ref(null)
const loading = ref(false)
const hostingConfigured = ref(true)
const editVisible = ref(false)
const mediaRef = ref()

function money(amount, currency) {
  return formatMoney(amount, currency)
}
function fmtTime(iso) {
  return iso ? iso.replace('T', ' ').slice(0, 16) : ''
}

async function reload() {
  loading.value = true
  try {
    card.value = await cardsApi.get(route.params.id)
  } finally {
    loading.value = false
  }
}
function reloadMedia() {
  mediaRef.value?.reload()
}

async function refreshFx() {
  try {
    const res = await cardsApi.refreshFx(card.value.id)
    if (res.warnings?.length) res.warnings.forEach((w) => ElMessage.warning(w))
    else ElMessage.success(t('card.fxRefreshed'))
    reload()
  } catch { /* 拦截器已提示 */ }
}

onMounted(async () => {
  await meta.ensure()
  const ih = await systemApi.getImageHosting().catch(() => ({ configured: false }))
  hostingConfigured.value = Boolean(ih.configured)
  reload()
})
</script>

<style scoped>
.pool-card { margin-top: 16px; }
.pool-head { display: flex; align-items: center; justify-content: space-between; }
.pool-draw { padding: 6px 0; border-bottom: 1px solid #1c2740; }
.pool-draw:last-child { border-bottom: none; }
.pool-draw-head { display: flex; align-items: center; justify-content: space-between; font-size: 13px; color: #c7d0de; margin-bottom: 4px; }
.pool-alloc { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #9aa6b8; padding: 2px 0 2px 10px; }
.pool-alloc.short { color: #e6a23c; }
.link { color: #8fb8ff; text-decoration: none; font-size: 12px; }
.link:hover { text-decoration: underline; }
.detail-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.title-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.mgmt { font-size: 13px; color: #8fb8ff; }
.model { font-size: 20px; color: #e6edf7; margin: 0; }
.vram-badge { font-size: 12px; padding: 2px 8px; border-radius: 6px; background: #1b2942; color: #a6adb4; }
.info-card, .profit-card, .log-card { margin-bottom: 16px; }
.kv { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; font-size: 14px; }
.kv span { color: #8a94a6; }
.kv b { color: #e6edf7; font-weight: 500; text-align: right; }
.link { color: #7ba2ff; text-decoration: none; }
.note { margin-top: 10px; padding: 10px; border-radius: 8px; background: #0e1830; color: #c7d0de; font-size: 13px; line-height: 1.6; white-space: pre-wrap; }
.profit-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; }
.profit-row span { color: #8a94a6; }
.profit-row b { color: #e6edf7; font-size: 15px; }
.profit-row.big b { font-size: 22px; }
.mt { margin-top: 10px; }
</style>
