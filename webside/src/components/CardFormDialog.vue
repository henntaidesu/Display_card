<template>
  <el-dialog
    v-model="visible"
    :title="props.card ? t('card.editTitle') : t('card.addTitle')"
    width="820px"
    top="6vh"
    :close-on-click-modal="true"
    @closed="onClosed"
  >
    <template #header>
      <div class="dialog-header">
        <span class="dialog-title">{{ props.card ? t('card.editTitle') : t('card.addTitle') }}</span>
        <span class="autosave" :class="{ active: saving }">
          <template v-if="saving"><el-icon class="spin"><Loading /></el-icon>{{ t('card.saving') }}</template>
          <template v-else-if="savedOnce"><el-icon><Select /></el-icon>{{ t('card.autoSaved') }}</template>
        </span>
      </div>
    </template>
    <el-form ref="formRef" :model="form" label-position="top" class="card-form">
      <!-- 基本信息 -->
      <div class="section-title">{{ t('card.mgmtNo') }}</div>
      <el-row :gutter="16">
        <el-col :xs="24" :sm="8">
          <el-form-item :label="t('card.mgmtNo')">
            <el-input v-model="form.mgmt_no" disabled />
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="16">
          <el-form-item :label="t('card.status')">
            <el-select v-model="form.status" class="full">
              <el-option v-for="s in statuses" :key="s" :label="t('status.' + s)" :value="s" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <!-- 型号 / 序列号 -->
      <div class="section-title">{{ t('card.model') }} · {{ t('card.serialNo') }}</div>
      <el-row :gutter="16">
        <el-col :xs="24" :sm="8">
          <el-form-item :label="t('card.brand')">
            <el-select v-model="form.brand" filterable allow-create default-first-option clearable class="full">
              <el-option v-for="b in brands" :key="b.id" :label="b.name" :value="b.name" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-form-item :label="t('card.model')">
            <el-select v-model="form.model" filterable allow-create default-first-option clearable class="full">
              <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.name" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-form-item :label="t('card.serialNo')">
            <el-input v-model="form.serial_no" />
          </el-form-item>
        </el-col>
      </el-row>

      <!-- 购买来源 -->
      <div class="section-title">{{ t('card.source') }}</div>
      <el-row :gutter="16">
        <el-col :xs="24" :sm="8">
          <el-form-item :label="t('card.platform')">
            <el-select v-model="form.source_platform" clearable class="full">
              <el-option v-for="p in platforms" :key="p" :label="t('platform.' + p)" :value="p" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-form-item :label="t('card.seller')">
            <el-input v-model="form.seller" />
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-form-item :label="t('card.orderNo')">
            <el-input v-model="form.order_no" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item :label="t('card.itemUrl')">
        <el-input v-model="form.item_url" placeholder="https://" />
      </el-form-item>

      <!-- 采购信息 -->
      <div class="section-title">{{ t('card.purchaseInfo') }}</div>
      <el-row :gutter="16">
        <el-col :xs="24" :sm="8">
          <el-form-item :label="t('card.purchaseDate')">
            <el-date-picker v-model="form.purchase_date" type="date" value-format="YYYY-MM-DD"
              class="full" @change="() => previewFx('purchase')" />
          </el-form-item>
        </el-col>
        <el-col :xs="12" :sm="8">
          <MoneyInput v-model:amount="form.purchase_amount" v-model:currency="form.purchase_currency" :label="t('card.purchaseAmount')" />
        </el-col>
        <el-col :xs="12" :sm="8">
          <MoneyInput v-model:amount="form.intl_shipping_amount" v-model:currency="form.intl_shipping_currency" :label="t('card.intlShipping')" />
        </el-col>
      </el-row>
      <div v-if="fxPreview.purchase && !usePool" class="fx-hint">
        {{ t('card.fxPreview') }}: 1 {{ t('currency.CNY_short') }} = {{ formatRate(fxPreview.purchase.rate) }} {{ t('currency.JPY_short') }}
        <span class="dc-dim">（{{ fxPreview.purchase.rate_date }}{{ fxPreview.purchase.stale ? ' *' : '' }}）</span>
      </div>

      <!-- 资金来源。开着的时候这张卡的日元支出从资金池扣，成本改按被吃掉的那几批
           注资各自的换汇价折算，买卡当天的市场牌价不再参与计算。 -->
      <div class="pool-row">
        <el-switch v-model="usePool" />
        <span class="pool-label">{{ t('card.fundPool') }}</span>
        <span v-if="poolSummary" class="dc-dim pool-balance">
          {{ t('card.poolBalance') }} <b class="dc-mono">{{ jpyText(poolSummary.balance) }}</b>
        </span>
      </div>
      <div v-if="usePool" class="fx-hint pool-hint">
        <div>{{ t('card.fundPoolHint') }}</div>
        <div v-if="poolCurrencyMismatch" class="pool-warn">{{ t('card.poolCurrencyWarn') }}</div>
        <div v-if="poolCost !== null">
          {{ t('card.poolCost') }}: <b class="dc-mono">{{ cnyText(poolCost) }}</b>
          <span v-if="poolRate" class="dc-dim">（{{ t('card.poolRate') }} {{ formatRate(poolRate) }}）</span>
        </div>
      </div>

      <!-- 出售信息 -->
      <div class="section-title">{{ t('card.saleInfo') }}</div>
      <el-row :gutter="16">
        <el-col :xs="24" :sm="8">
          <el-form-item :label="t('card.saleDate')">
            <el-date-picker v-model="form.sale_date" type="date" value-format="YYYY-MM-DD"
              class="full" @change="() => previewFx('sale')" />
          </el-form-item>
        </el-col>
        <el-col :xs="12" :sm="8">
          <MoneyInput v-model:amount="form.sale_amount" v-model:currency="form.sale_currency" :label="t('card.saleAmount')" />
        </el-col>
        <el-col :xs="12" :sm="8">
          <MoneyInput v-model:amount="form.domestic_shipping_amount" v-model:currency="form.domestic_shipping_currency" :label="t('card.domesticShipping')" />
        </el-col>
      </el-row>
      <div v-if="fxPreview.sale" class="fx-hint">
        {{ t('card.fxPreview') }}: 1 {{ t('currency.CNY_short') }} = {{ formatRate(fxPreview.sale.rate) }} {{ t('currency.JPY_short') }}
        <span class="dc-dim">（{{ fxPreview.sale.rate_date }}{{ fxPreview.sale.stale ? ' *' : '' }}）</span>
      </div>

      <el-form-item :label="t('card.note')">
        <el-input v-model="form.note" type="textarea" :rows="2" />
      </el-form-item>

      <!-- 图片 / 视频：文件要挂到卡片上，必须先有 card_id；新增时先存基本信息再解锁上传 -->
      <div class="section-title media-title">
        <el-icon><Picture /></el-icon>{{ t('card.media') }}
      </div>
      <MediaManager
        v-if="form.id"
        ref="mediaRef"
        :card-id="form.id"
        :hosting-configured="hostingConfigured"
        @changed="$emit('media-changed')"
      />
      <!-- 兜底：草稿卡没建成（后端不可用）时才出现，提示先保存 -->
      <div v-else class="media-placeholder">
        <el-icon :size="34"><UploadFilled /></el-icon>
        <p class="media-placeholder-hint">{{ t('card.mediaHint') }}</p>
        <div class="media-cats">
          <span v-for="cat in mediaCategories" :key="cat" class="media-cat-chip">{{ t('category.' + cat) }}</span>
        </div>
      </div>
    </el-form>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { cardsApi, fundsApi, fxApi, optionsApi } from '@/api'
import { cny, formatMoney, formatRate } from '@/utils/format'
import { useMetaStore } from '@/stores/meta'
import MediaManager from './MediaManager.vue'
import MoneyInput from './MoneyInput.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  card: { type: Object, default: null },
  hostingConfigured: { type: Boolean, default: true }
})
const emit = defineEmits(['update:modelValue', 'saved', 'media-changed'])

const { t } = useI18n()
const meta = useMetaStore()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const brands = computed(() => meta.brands)
const statuses = computed(() => meta.enums.statuses || [])
const platforms = computed(() => meta.enums.source_platforms || [])
const mediaCategories = computed(() =>
  meta.enums.media_categories?.length
    ? meta.enums.media_categories
    : ['appearance', 'pcb', 'gpu_core', 'gpuz', 'mods']
)
const models = ref([])
const saving = ref(false)
// 资金池：池子总账（显示余额）+ 最近一次保存返回的金额，用来把「这张卡实际折了多少
// 人民币」直接回显在表单里——分摊要在后端按 FIFO 算完才知道，前端算不出来。
const poolSummary = ref(null)
const savedMoney = ref(null)
const savedOnce = ref(false)
const formRef = ref()
const mediaRef = ref()
// 草稿态：新增时先建的空卡。保存即定稿（转 false）；未保存就关闭则删掉这张草稿。
const isDraft = ref(false)
const fxPreview = reactive({ purchase: null, sale: null })

const usePool = computed({
  get: () => form.fund_source === 'pool',
  set: (v) => { form.fund_source = v ? 'pool' : 'own' }
})
// 池子里是日元，人民币支付的部分与它无关：开着开关但币种选了人民币时要说清楚
const poolCurrencyMismatch = computed(() =>
  usePool.value && form.purchase_currency !== 'JPY' && form.purchase_amount
)
const poolCost = computed(() => {
  const m = savedMoney.value
  if (!m || !m.from_pool) return null
  const parts = [m.purchase_cny, m.intl_shipping_cny].filter((v) => v !== null && v !== undefined)
  return parts.length ? parts.reduce((a, b) => a + b, 0) : null
})
const poolRate = computed(() => savedMoney.value?.pool_fx_rate || null)
const jpyText = (v) => formatMoney(v, 'JPY')
const cnyText = (v) => cny(v)

async function loadPoolSummary() {
  try {
    poolSummary.value = await fundsApi.summary()
  } catch {
    poolSummary.value = null
  }
}

// ── 实时自动保存 ──────────────────────────────────────────────────────────
// 表单没有保存按钮：任何改动都防抖后自动 PUT。formReady 用来跳过「打开弹窗时
// 填充表单」引起的那次 watch，避免刚打开就误存一遍。dirty 标记有未落盘的改动。
let saveTimer = null
let savingInflight = false
const formReady = ref(false)
const dirty = ref(false)
const AUTOSAVE_DELAY = 600

function scheduleAutoSave() {
  if (!formReady.value || !visible.value) return
  dirty.value = true
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(doSave, AUTOSAVE_DELAY)
}

async function doSave() {
  if (saveTimer) { clearTimeout(saveTimer); saveTimer = null }
  // 同一时刻只跑一条保存链；已在跑时直接返回，正在跑的循环会自查 dirty 继续存。
  if (savingInflight || !dirty.value) return
  savingInflight = true
  saving.value = true
  // 循环直到没有新改动：存的过程中（await 期间）用户又改了，dirty 会再次置真，
  // 循环继续把最新值也存掉，避免「存旧值 + 丢最后一次改动」。
  while (dirty.value) {
    dirty.value = false
    try {
      const payload = { ...form }
      delete payload.mgmt_no
      let result
      if (form.id) {
        result = await cardsApi.update(form.id, payload)
      } else {
        result = await cardsApi.create(payload)  // 草稿没建成的兜底
        form.id = result.id
        form.mgmt_no = result.mgmt_no
      }
      savedMoney.value = result?.money || null
      // 池子余额被这张卡的扣款改动了，顺手刷一次；不走资金池就没必要多打这个请求
      if (form.fund_source === 'pool') loadPoolSummary()
      isDraft.value = false   // 有内容了，不再是待删的空草稿
      savedOnce.value = true
      await persistDict()
    } catch {
      dirty.value = true      // 存失败，标记未落盘并退出，避免失败死循环
      break
    }
  }
  saving.value = false
  savingInflight = false
}

// 关闭前把还没落盘的改动彻底存完（含在途的那次）
async function flushSave() {
  if (saveTimer) { clearTimeout(saveTimer); saveTimer = null }
  doSave()
  while (savingInflight) {
    await new Promise((r) => setTimeout(r, 40))
  }
}

function blankForm() {
  return {
    id: null,
    mgmt_no: '',
    brand: null, model: null, vram: null, serial_no: null,
    source_platform: null, seller: null, item_url: null, order_no: null,
    purchase_date: null, purchase_amount: null, purchase_currency: 'JPY',
    intl_shipping_amount: null, intl_shipping_currency: 'JPY',
    domestic_shipping_amount: null, domestic_shipping_currency: 'CNY',
    sale_date: null, sale_amount: null, sale_currency: 'CNY',
    fund_source: 'own',
    status: 'purchased', note: null
    // 汇率一律按日期自动获取，不再手工填写
  }
}

const form = reactive(blankForm())

// 必须放在 form 声明之后：const 有暂时性死区，写在前面会在 setup 里直接抛
// ReferenceError，整个弹窗连同它所在的页面一起挂掉
watch(form, scheduleAutoSave, { deep: true })

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    // 填充表单期间关掉自动保存，避免刚打开就把预填值当成用户改动存一遍
    formReady.value = false
    dirty.value = false
    savedOnce.value = false
    fxPreview.purchase = null
    fxPreview.sale = null
    savedMoney.value = props.card?.money || null
    loadPoolSummary()
    // 型号独立于品牌，进弹窗就拉全量
    await loadModels()
    if (props.card) {
      Object.assign(form, blankForm(), normalize(props.card))
      isDraft.value = false
    } else {
      Object.assign(form, blankForm())
      // 立刻建一张草稿卡拿到 id：这样媒体上传区在新增时就能用，和编辑态完全一致。
      // 建失败（后端不可用）时退回占位提示，保存时后端再补建。
      try {
        const draft = await cardsApi.createDraft()
        form.id = draft.id
        form.mgmt_no = draft.mgmt_no
        isDraft.value = true
      } catch {
        isDraft.value = false
        try {
          const res = await cardsApi.nextMgmtNo()
          form.mgmt_no = res.mgmt_no
        } catch { /* 忽略，保存时后端会生成编号 */ }
      }
    }
    // 等填充引起的那波 watch 冲刷完，再开启自动保存
    await nextTick()
    dirty.value = false
    formReady.value = true
  }
)

function normalize(card) {
  const out = {}
  for (const k of Object.keys(blankForm())) {
    out[k] = card[k] ?? null
  }
  out.id = card.id
  return out
}

async function loadModels() {
  // 型号独立于品牌，永远拉全量清单
  const res = await optionsApi.models()
  models.value = res.items || []
}

async function previewFx(which) {
  const date = which === 'purchase' ? form.purchase_date : form.sale_date
  if (!date) {
    fxPreview[which] = null
    return
  }
  try {
    fxPreview[which] = await fxApi.rate({ date })
  } catch {
    fxPreview[which] = null
  }
}

async function persistDict() {
  // 品牌只在「系统配置」里手动维护，这里**不**把卡片上现敲的品牌写进字典；
  // 卡片仍照常保存该品牌文本，只是不污染品牌清单。
  // 型号是独立模块，现敲一个新型号会顺手补进型号字典（不含任何品牌关联）。
  try {
    if (form.model && !models.value.some((m) => m.name === form.model)) {
      await optionsApi.createModel({ name: form.model })
    }
  } catch { /* 字典写入失败不影响卡片本身 */ }
}

async function onClosed() {
  formReady.value = false
  // 关闭前把最后一次未落盘的改动彻底存掉（防抖还没触发、或在途保存还没结束就点了外面关掉）
  if (form.id && (dirty.value || savingInflight)) {
    await flushSave()
  }
  // 仍是草稿（整个过程没输入任何东西、从没存过）→ 删掉这张空草稿卡连同已传的图，
  // 免得留下没内容的废卡。已存过则 isDraft 为 false，转而通知列表刷新一次。
  if (isDraft.value && form.id) {
    const draftId = form.id
    isDraft.value = false
    try {
      await cardsApi.remove(draftId, true)
    } catch { /* 删草稿失败就算了，不打扰用户 */ }
  } else if (form.id) {
    emit('saved', { id: form.id })
  }
  models.value = []
  form.id = null
  dirty.value = false
  savedOnce.value = false
}
</script>

<style scoped>
/* 标题栏：左标题 + 右侧自动保存状态 */
.dialog-header { display: flex; align-items: center; justify-content: space-between; padding-right: 20px; }
.dialog-title { font-size: 16px; font-weight: 600; color: #e6edf7; }
.autosave { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: #6f7b8e; }
.autosave.active { color: #8fb8ff; }
.autosave .spin { animation: dc-spin 0.9s linear infinite; }
@keyframes dc-spin { to { transform: rotate(360deg); } }

/* overflow-x:hidden 干掉横向滚动条：顶部标签布局下每个控件都满宽，之前那条横条
   来自左标签 + 定宽控件挤不下时的溢出，改顶标签后不再需要横向滚动 */
.card-form { max-height: 66vh; overflow-y: auto; overflow-x: hidden; padding-right: 8px; }
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #8fb8ff;
  margin: 14px 0 10px;
  padding-left: 8px;
  border-left: 3px solid #5b8cff;
}
.section-title:first-child { margin-top: 0; }
.media-title { display: flex; align-items: center; gap: 6px; }
.full { width: 100% !important; }
.card-form :deep(.el-input),
.card-form :deep(.el-select),
.card-form :deep(.el-date-editor) { width: 100% !important; }
/* 顶部标签布局：压紧每个表单项的上下间距与标签行高，别让表单拉得太长 */
.card-form :deep(.el-form-item) { margin-bottom: 12px; }
.card-form :deep(.el-form-item__label) {
  padding-bottom: 4px;
  line-height: 1.3;
  color: #9aa6b8;
  font-size: 13px;
}
.fx-hint {
  margin: -4px 0 12px;
  padding: 6px 10px;
  font-size: 12px;
  color: #b9c4d6;
  background: rgba(91, 140, 255, 0.08);
  border-radius: 6px;
}
.pool-row { display: flex; align-items: center; gap: 10px; margin: -2px 0 10px; flex-wrap: wrap; }
.pool-label { font-size: 13px; color: #c7d0de; }
.pool-balance { font-size: 12px; }
.pool-hint { line-height: 1.7; }
.pool-warn { color: #e6a23c; }
.manual-fx { margin-bottom: 12px; border: none; }
.manual-fx :deep(.el-collapse-item__header),
.manual-fx :deep(.el-collapse-item__wrap) { background: transparent; border: none; }
.manual-hint { font-size: 12px; margin-top: 2px; }

/* 新增态的上传占位：一块虚线区域，说明保存后可上传，并预告 5 个分类 */
.media-placeholder {
  border: 1px dashed #3a4a66;
  border-radius: 10px;
  padding: 22px 16px;
  text-align: center;
  color: #8a94a6;
  background: rgba(91, 140, 255, 0.04);
}
.media-placeholder .el-icon { color: #5b7096; }
.media-placeholder-hint { font-size: 13px; margin: 8px 0 12px; line-height: 1.5; }
.media-cats { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.media-cat-chip {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 12px;
  background: #1b2942;
  color: #b9c4d6;
  border: 1px solid #28354a;
}
</style>
