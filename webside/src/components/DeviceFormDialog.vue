<template>
  <el-dialog
    v-model="visible"
    width="980px"
    top="5vh"
    :close-on-click-modal="true"
    @closed="onClosed"
  >
    <template #header>
      <div class="dialog-header">
        <span class="dialog-title">{{ props.device ? t('device.editTitle') : t('device.addTitle') }}</span>
        <span class="autosave" :class="{ active: saving }">
          <template v-if="saving"><el-icon class="spin"><Loading /></el-icon>{{ t('card.saving') }}</template>
          <template v-else-if="savedOnce"><el-icon><Select /></el-icon>{{ t('card.autoSaved') }}</template>
        </span>
      </div>
    </template>

    <el-form :model="form" label-position="top" class="device-form">
      <!-- 基本信息 -->
      <el-row :gutter="16">
        <el-col :xs="24" :sm="7">
          <el-form-item :label="t('card.mgmtNo')">
            <el-input v-model="form.mgmt_no" disabled />
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="10">
          <el-form-item :label="t('device.name')">
            <el-input v-model="form.title" :placeholder="t('device.namePlaceholder')" />
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="7">
          <el-form-item :label="t('card.status')">
            <el-select v-model="form.status" class="full">
              <el-option v-for="s in statuses" :key="s" :label="t('status.' + s)" :value="s" />
            </el-select>
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

      <!-- 采购信息：整机只有一笔总价，出售价在下面的部件里各自填 -->
      <div class="section-title">{{ t('device.purchaseInfo') }}</div>
      <el-row :gutter="16">
        <el-col :xs="24" :sm="8">
          <el-form-item :label="t('card.purchaseDate')">
            <el-date-picker v-model="form.purchase_date" type="date" value-format="YYYY-MM-DD"
              class="full" @change="previewFx" />
          </el-form-item>
        </el-col>
        <el-col :xs="12" :sm="8">
          <MoneyInput v-model:amount="form.purchase_amount" v-model:currency="form.purchase_currency"
            :label="t('device.purchaseAmount')" />
        </el-col>
        <el-col :xs="12" :sm="8">
          <MoneyInput v-model:amount="form.intl_shipping_amount" v-model:currency="form.intl_shipping_currency"
            :label="t('card.intlShipping')" />
        </el-col>
      </el-row>
      <div v-if="fxPreview" class="fx-hint">
        {{ t('card.fxPreview') }}: 1 {{ t('currency.CNY_short') }} = {{ formatRate(fxPreview.rate) }} {{ t('currency.JPY_short') }}
        <span class="dc-dim">（{{ fxPreview.rate_date }}{{ fxPreview.stale ? ' *' : '' }}）</span>
      </div>

      <!-- 资金来源。开着的时候这台设备的日元支出从资金池扣，成本改按被吃掉的那几批
           注资各自的换汇价折算，购入当天的市场牌价不再参与计算。 -->
      <div class="pool-row">
        <el-switch v-model="usePool" />
        <span class="pool-label">{{ t('card.fundPool') }}</span>
        <span v-if="poolSummary" class="dc-dim pool-balance">
          {{ t('card.poolBalance') }} <b class="dc-mono">{{ jpyText(poolSummary.balance) }}</b>
        </span>
      </div>
      <div v-if="usePool" class="fx-hint pool-hint">
        <div>{{ t('device.fundPoolHint') }}</div>
        <div v-if="poolCurrencyMismatch" class="pool-warn">{{ t('card.poolCurrencyWarn') }}</div>
        <div v-if="poolCost !== null">
          {{ t('card.poolCost') }}: <b class="dc-mono">{{ cny(poolCost) }}</b>
          <span v-if="poolRate" class="dc-dim">（{{ t('card.poolRate') }} {{ formatRate(poolRate) }}）</span>
        </div>
        <!-- 分段折算明细。整机没有独立详情页，这里是唯一能看到「钱从哪几批出的」的地方 -->
        <div v-for="draw in fundDraws" :key="draw.id" class="pool-draw">
          <span class="dc-dim">{{ t('funds.cat.' + draw.category) }}</span>
          <b class="dc-mono">{{ jpyText(draw.amount) }}</b>
          <span v-for="(seg, i) in draw.allocations" :key="i" class="pool-seg dc-mono">
            {{ seg.inject_date }} {{ jpyText(seg.amount) }} @{{ formatRate(seg.fx_rate) }} = {{ cny(seg.cny_amount) }}
          </span>
          <span v-if="draw.shortfall" class="pool-warn">
            {{ t('funds.shortfall') }} {{ jpyText(draw.shortfall) }}（{{ t('funds.shortfallHint') }}）
          </span>
        </div>
      </div>

      <!-- 部件与出售：一台设备多行，内存/硬盘可以重复添加 -->
      <div class="section-title">{{ t('device.parts') }}</div>
      <div class="parts-hint">{{ t('device.partsHint') }}</div>
      <div class="quick-add">
        <span class="quick-add-label">{{ t('device.quickAdd') }}</span>
        <el-button v-for="type in partTypes" :key="type" size="small" plain @click="addPart(type)">
          + {{ t('partType.' + type) }}
        </el-button>
      </div>

      <div v-if="!form.parts.length" class="parts-empty">{{ t('device.noParts') }}</div>

      <div v-for="(part, index) in form.parts" :key="part._uid" class="part-card"
        :class="{ 'part-card--blank': isBlank(part) }">
        <div class="part-head">
          <el-tag size="small" effect="plain" type="info">{{ t('partType.' + part.part_type) }}</el-tag>
          <span class="part-title">{{ partTitle(part) }}</span>
          <!-- 空槽位：六个标准部件是默认摆出来的，没填的不会存进库 -->
          <el-tag v-if="isBlank(part)" size="small" type="info" effect="plain">{{ t('device.blankSlot') }}</el-tag>
          <el-tag v-else-if="part.sale_amount !== null && part.sale_amount !== ''" size="small" type="success" effect="plain">
            {{ formatMoney(part.sale_amount, part.sale_currency) }}
          </el-tag>
          <el-tag v-else size="small" type="info" effect="plain">{{ t('device.unsold') }}</el-tag>
          <span v-if="partNet(index) !== null" class="dc-dim part-net">
            {{ t('device.netIncome') }} <b class="dc-mono">{{ cny(partNet(index)) }}</b>
          </span>
          <div class="part-actions">
            <el-button size="small" text @click="toggleMore(part._uid)">
              {{ expanded.has(part._uid) ? '−' : '+' }} {{ t('card.serialNo') }} / {{ t('device.buyer') }}
            </el-button>
            <el-button size="small" text type="danger" :icon="Delete" :title="t('device.removePart')"
              @click="removePart(index)" />
          </div>
        </div>

        <el-row :gutter="10">
          <el-col :xs="12" :sm="4">
            <el-form-item :label="t('device.partType')">
              <el-select v-model="part.part_type" class="full">
                <el-option v-for="type in partTypes" :key="type" :label="t('partType.' + type)" :value="type" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="4">
            <!-- 品牌候选按部件类型给：CPU 只有 Intel / AMD（不允许现场新建），
                 显卡直接用系统里的品牌字典，其余给一份常见清单但可以现场输入 -->
            <el-form-item :label="t('card.brand')">
              <el-select v-model="part.brand" filterable :allow-create="allowCreateBrand(part)"
                default-first-option clearable class="full">
                <el-option v-for="b in brandOptions(part)" :key="b" :label="b" :value="b" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="6">
            <el-form-item :label="t('card.model')">
              <el-select v-if="modelOptions(part).length" v-model="part.model" filterable allow-create
                default-first-option clearable class="full" :placeholder="schemaOf(part).modelPlaceholder">
                <el-option v-for="m in modelOptions(part)" :key="m" :label="m" :value="m" />
              </el-select>
              <el-input v-else v-model="part.model" :placeholder="schemaOf(part).modelPlaceholder" />
            </el-form-item>
          </el-col>
          <el-col :xs="18" :sm="7">
            <!-- 「规格」这一栏各类型填的不是一回事：显存 / 容量 / 功率 / 芯片组，
                 所以标题和候选值都跟着类型走，写法才不会一台一个样 -->
            <el-form-item :label="t(specLabelKey(part.part_type))">
              <el-select v-if="specOptions(part).length" v-model="part.spec" filterable allow-create
                default-first-option clearable class="full">
                <el-option v-for="sp in specOptions(part)" :key="sp" :label="sp" :value="sp" />
              </el-select>
              <el-input v-else v-model="part.spec" :placeholder="t('device.specPlaceholder')" />
            </el-form-item>
          </el-col>
          <el-col :xs="6" :sm="3">
            <el-form-item :label="t('device.quantity')">
              <el-input-number v-model="part.quantity" :min="1" :max="999" :controls="false" class="full" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="10">
          <el-col :xs="24" :sm="5">
            <el-form-item :label="t('card.saleDate')">
              <el-date-picker v-model="part.sale_date" type="date" value-format="YYYY-MM-DD" class="full" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="7">
            <MoneyInput v-model:amount="part.sale_amount" v-model:currency="part.sale_currency"
              :label="t('card.saleAmount')" />
          </el-col>
          <el-col :xs="12" :sm="7">
            <MoneyInput v-model:amount="part.domestic_shipping_amount"
              v-model:currency="part.domestic_shipping_currency" :label="t('card.domesticShipping')" />
          </el-col>
          <el-col :xs="24" :sm="5">
            <el-form-item :label="t('card.status')">
              <el-select v-model="part.status" class="full">
                <el-option v-for="s in statuses" :key="s" :label="t('status.' + s)" :value="s" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row v-if="expanded.has(part._uid)" :gutter="10">
          <el-col :xs="24" :sm="8">
            <el-form-item :label="t('card.serialNo')">
              <el-input v-model="part.serial_no" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-form-item :label="t('device.buyer')">
              <el-input v-model="part.buyer" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-form-item :label="t('card.note')">
              <el-input v-model="part.note" />
            </el-form-item>
          </el-col>
        </el-row>
      </div>

      <!-- 合计：金额要按各自日期的汇率折算，只有后端算得准，这里显示最近一次保存的结果 -->
      <div v-if="money" class="summary">
        <div class="summary-item">
          <span class="summary-label">{{ t('device.cost') }}</span>
          <span class="dc-mono summary-value">{{ cny(money.cost_total_cny) }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">{{ t('device.revenue') }}</span>
          <span class="dc-mono summary-value">{{ cny(money.sale_cny) }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">{{ t('device.profit') }}</span>
          <span class="dc-mono summary-value" :class="profitClass(money.profit_cny)">{{ cny(money.profit_cny) }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">{{ t('device.recovery') }}</span>
          <span class="dc-mono summary-value">{{ money.recovery === null ? '—' : money.recovery + '%' }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">{{ t('device.soldParts') }}</span>
          <span class="dc-mono summary-value">{{ money.sold_count }} / {{ money.part_count }}</span>
        </div>
      </div>
      <div v-if="money" class="fx-hint" :class="{ 'settled-hint': money.settled }">
        {{ money.settled ? t('device.settledHint') : t('device.unsettledHint') }}
      </div>

      <el-form-item :label="t('card.note')">
        <el-input v-model="form.note" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Delete, Loading, Select } from '@element-plus/icons-vue'
import { devicesApi, fundsApi, fxApi } from '@/api'
import { cny, formatMoney, formatRate, profitClass } from '@/utils/format'
import { useMetaStore } from '@/stores/meta'
import { DEFAULT_PART_TYPES, partSchema, specLabelKey } from '@/constants/parts'
import { optionsApi } from '@/api'
import MoneyInput from './MoneyInput.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  device: { type: Object, default: null }
})
const emit = defineEmits(['update:modelValue', 'saved'])

const { t } = useI18n()
const meta = useMetaStore()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const statuses = computed(() => meta.enums.statuses || [])
const platforms = computed(() => meta.enums.source_platforms || [])
const partTypes = computed(() =>
  meta.enums.device_part_types?.length
    ? meta.enums.device_part_types
    : ['cpu', 'gpu', 'ram', 'disk', 'motherboard', 'psu', 'cooler', 'case', 'other']
)

const saving = ref(false)
const savedOnce = ref(false)
// 最近一次保存的返回值：金额要按购入日 / 各部件出售日的汇率折算，那只有后端算得准，
// 前端不自己算一遍（自己算必然和列表页对不上）。
const saved = ref(null)
const money = computed(() => saved.value?.money || null)
const fxPreview = ref(null)
// 池子总账，只为在开关旁边显示余额；分摊结果由后端算完随保存返回
const poolSummary = ref(null)
// 显卡型号字典，给部件里的「显卡」一行做下拉候选
const models = ref([])

const usePool = computed({
  get: () => form.fund_source === 'pool',
  set: (v) => { form.fund_source = v ? 'pool' : 'own' }
})
// 池子里是日元，人民币支付的部分与它无关：开着开关但币种选了人民币时要说清楚
const poolCurrencyMismatch = computed(() =>
  usePool.value && form.purchase_currency !== 'JPY' && form.purchase_amount
)
// 这台设备实际折了多少人民币：要按 FIFO 吃到的批次算，前端算不出来，取后端的返回值
const poolCost = computed(() => {
  const m = money.value
  if (!m || !m.from_pool) return null
  const parts = [m.purchase_cny, m.intl_shipping_cny].filter((v) => v !== null && v !== undefined)
  return parts.length ? parts.reduce((a, b) => a + b, 0) : null
})
const poolRate = computed(() => money.value?.pool_fx_rate || null)
// 池内扣款与它的 FIFO 分段。每次保存的返回值都带着它，改完金额立刻能看到新的分段
const fundDraws = computed(() => saved.value?.fund_draws || [])
const jpyText = (v) => formatMoney(v, 'JPY')

async function loadPoolSummary() {
  try {
    poolSummary.value = await fundsApi.summary()
  } catch {
    poolSummary.value = null
  }
}
// 草稿态：新增时先建的空设备。保存即定稿；未保存就关闭则删掉它。
const isDraft = ref(false)
// 展开了「序列号 / 买家 / 备注」那一行的部件（按 _uid）
const expanded = ref(new Set())

// 部件行的本地唯一键。v-for 不能拿数组下标当 key——删掉中间一条时，后面每条的
// key 都会平移到上一条的输入框上，正在编辑的内容会跳到别的行去。
let uid = 0

function blankPart(partType = 'other') {
  return {
    _uid: ++uid,
    part_type: partType,
    brand: null, model: null, spec: null, serial_no: null, quantity: 1,
    sale_date: null, sale_amount: null, sale_currency: 'CNY',
    domestic_shipping_amount: null, domestic_shipping_currency: 'CNY',
    buyer: null, status: 'purchased', note: null
  }
}

function blankForm() {
  return {
    id: null,
    mgmt_no: '',
    title: null,
    source_platform: null, seller: null, item_url: null, order_no: null,
    purchase_date: null, purchase_amount: null, purchase_currency: 'JPY',
    intl_shipping_amount: null, intl_shipping_currency: 'JPY',
    fund_source: 'own',
    status: 'purchased', note: null,
    // 默认把 CPU / 显卡 / 内存 / 硬盘 / 主板 / 电源 六个槽位摆出来：一台机器几乎必然
    // 有这些东西，让人每次点六下「快捷添加」纯属白费事。没填的槽位保存时会被丢掉
    // （见 buildPayload），所以它只是模板，不会变成一堆空部件。
    parts: DEFAULT_PART_TYPES.map((type) => blankPart(type))
  }
}

const form = reactive(blankForm())

const schemaOf = (part) => partSchema(part.part_type)
const allowCreateBrand = (part) => !schemaOf(part).brandStrict

function brandOptions(part) {
  if (part.part_type === 'gpu') {
    // 显卡用系统里维护的品牌字典（「系统配置 → 品牌/型号」那份），空了才退回内置清单
    const dict = meta.brands.map((b) => b.name).filter(Boolean)
    if (dict.length) return dict
  }
  return schemaOf(part).brands
}
// 显卡的型号同样取字典；其余类型型号太发散，给个占位提示就够了
const modelOptions = (part) => (part.part_type === 'gpu' ? models.value.map((m) => m.name) : [])
const specOptions = (part) => schemaOf(part).specs

// 完全没填过的槽位。数量、状态、币种这些一建行就有默认值的字段不算「填过」，
// 否则六个默认槽位一打开就全成了「有内容」，会被原样存进库。
const CONTENT_KEYS = [
  'brand', 'model', 'spec', 'serial_no', 'buyer', 'note',
  'sale_date', 'sale_amount', 'domestic_shipping_amount'
]
const filled = (v) => v !== null && v !== undefined && v !== ''
function isBlank(part) {
  return !CONTENT_KEYS.some((key) => filled(part[key]))
}

function partTitle(part) {
  return [part.brand, part.model, part.spec].filter(Boolean).join(' ') || '—'
}

// 单个部件折人民币后的净收入，从上次保存的返回值里按下标取——后端返回的部件顺序与
// 提交顺序一致。但**提交时跳过了空槽位**，所以这里要按「非空行」重新数一遍下标，
// 否则中间有一个空槽位，后面每一行显示的都会是上一行的钱。
function partNet(index) {
  const part = form.parts[index]
  if (!part || isBlank(part)) return null
  let pos = 0
  for (let i = 0; i < index; i += 1) {
    if (!isBlank(form.parts[i])) pos += 1
  }
  return saved.value?.parts?.[pos]?.money?.net_cny ?? null
}

function addPart(partType) {
  form.parts.push(blankPart(partType))
}
function removePart(index) {
  const [removed] = form.parts.splice(index, 1)
  if (removed) expanded.value.delete(removed._uid)
}
function toggleMore(partUid) {
  const next = new Set(expanded.value)
  if (next.has(partUid)) next.delete(partUid)
  else next.add(partUid)
  expanded.value = next
}

// ── 实时自动保存 ──────────────────────────────────────────────────────────
// 与显卡表单同一套机制：没有保存按钮，任何改动防抖后自动 PUT。formReady 用来跳过
// 「打开弹窗时填充表单」引起的那次 watch，dirty 标记有未落盘的改动。
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

function buildPayload() {
  return {
    title: form.title,
    source_platform: form.source_platform,
    seller: form.seller,
    item_url: form.item_url,
    order_no: form.order_no,
    purchase_date: form.purchase_date,
    purchase_amount: form.purchase_amount,
    purchase_currency: form.purchase_currency,
    intl_shipping_amount: form.intl_shipping_amount,
    intl_shipping_currency: form.intl_shipping_currency,
    fund_source: form.fund_source,
    status: form.status,
    note: form.note,
    // 提交的数组就是这台设备**当前的全部部件**，后端整体覆盖。_uid 是前端的行标识，
    // 不发给后端；sort_order 用下标，拖动/插入后不必自己维护。
    // 一个字都没填的槽位不提交：默认摆出来的六个是录入模板，不是「这台机器有六个空部件」
    // ——真存进去的话部件数会永远显示成 0/6，「已清算」也永远为假。
    parts: form.parts.filter((part) => !isBlank(part)).map((part, index) => {
      const { _uid, ...rest } = part
      return { ...rest, sort_order: index }
    })
  }
}

async function doSave() {
  if (saveTimer) { clearTimeout(saveTimer); saveTimer = null }
  // 同一时刻只跑一条保存链；已在跑时直接返回，正在跑的循环会自查 dirty 继续存。
  if (savingInflight || !dirty.value) return
  savingInflight = true
  saving.value = true
  // 循环直到没有新改动：存的过程中用户又改了，dirty 会再次置真，循环把最新值也存掉。
  while (dirty.value) {
    dirty.value = false
    try {
      const payload = buildPayload()
      let result
      if (form.id) {
        result = await devicesApi.update(form.id, payload)
      } else {
        result = await devicesApi.create(payload)  // 草稿没建成时的兜底
        form.id = result.id
        form.mgmt_no = result.mgmt_no
      }
      saved.value = result
      // 这台设备的扣款改动了池子余额，顺手刷一次；不走资金池就没必要多打这个请求
      if (form.fund_source === 'pool') loadPoolSummary()
      isDraft.value = false   // 有内容了，不再是待删的空草稿
      savedOnce.value = true
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

// 必须放在 form 声明之后：const 有暂时性死区，写在前面会直接抛 ReferenceError。
watch(form, scheduleAutoSave, { deep: true })

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    // 填充表单期间关掉自动保存，避免刚打开就把预填值当成用户改动存一遍
    formReady.value = false
    dirty.value = false
    savedOnce.value = false
    fxPreview.value = null
    expanded.value = new Set()
    saved.value = null
    loadPoolSummary()
    loadModels()
    if (props.device) {
      // 列表行里已经带着完整的部件与金额，但仍重新拉一次：列表是分页缓存的快照，
      // 别人（或另一个标签页）改过之后，拿旧快照编辑会把新数据覆盖回去。
      let full = props.device
      try {
        full = await devicesApi.get(props.device.id)
      } catch { /* 拉不到就用列表里的那份 */ }
      Object.assign(form, normalize(full))
      saved.value = full
      isDraft.value = false
      previewFx()
    } else {
      Object.assign(form, blankForm())
      // 立刻建一台草稿设备拿到 id 与编号，和编辑态完全一致；建失败则保存时后端再补建。
      try {
        const draft = await devicesApi.createDraft()
        form.id = draft.id
        form.mgmt_no = draft.mgmt_no
        isDraft.value = true
      } catch {
        isDraft.value = false
        try {
          const res = await devicesApi.nextMgmtNo()
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

function normalize(device) {
  const out = blankForm()
  for (const key of Object.keys(out)) {
    if (key === 'parts') continue
    out[key] = device[key] ?? out[key]
  }
  out.id = device.id
  out.mgmt_no = device.mgmt_no || ''
  // 只挑表单认识的字段：服务端行上还有 id / money / 汇率快照等，整份铺回表单会被
  // 原样发回后端（虽被忽略，但载荷里多一堆没人读的字段，调起来也难看）。
  const saved = (device.parts || []).map((part) => {
    const row = blankPart(part.part_type)
    for (const key of Object.keys(row)) {
      if (key !== '_uid' && key in part) row[key] = part[key] ?? row[key]
    }
    return row
  })
  // 编辑已有设备时也要摆齐六个标准槽位：这台机器当初没录显卡，不代表之后不想补录，
  // 而空槽位不会被保存，摆着不会污染数据。已有的部件按标准顺序归组，非标准类型
  // （散热 / 机箱 / 其他）排在最后。
  out.parts = []
  for (const type of DEFAULT_PART_TYPES) {
    const rows = saved.filter((p) => p.part_type === type)
    out.parts.push(...(rows.length ? rows : [blankPart(type)]))
  }
  out.parts.push(...saved.filter((p) => !DEFAULT_PART_TYPES.includes(p.part_type)))
  return out
}

async function loadModels() {
  try {
    const res = await optionsApi.models()
    models.value = res.items || []
  } catch {
    models.value = []   // 拉不到就退回内置候选，不影响录入
  }
}

async function previewFx() {
  if (!form.purchase_date) {
    fxPreview.value = null
    return
  }
  try {
    fxPreview.value = await fxApi.rate({ date: form.purchase_date })
  } catch {
    fxPreview.value = null
  }
}

async function onClosed() {
  formReady.value = false
  // 关闭前把最后一次未落盘的改动存掉（防抖还没触发、或在途保存还没结束就关了弹窗）
  if (form.id && (dirty.value || savingInflight)) {
    await flushSave()
  }
  // 仍是草稿（全程没输入任何东西）→ 删掉这台空设备，免得留下没内容的废记录
  if (isDraft.value && form.id) {
    const draftId = form.id
    isDraft.value = false
    try {
      await devicesApi.remove(draftId)
    } catch { /* 删草稿失败就算了，不打扰用户 */ }
  } else if (form.id) {
    emit('saved', { id: form.id })
  }
  Object.assign(form, blankForm())
  saved.value = null
  dirty.value = false
  savedOnce.value = false
}
</script>

<style scoped>
.dialog-header { display: flex; align-items: center; justify-content: space-between; padding-right: 20px; }
.dialog-title { font-size: 16px; font-weight: 600; color: #e6edf7; }
.autosave { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: #6f7b8e; }
.autosave.active { color: #8fb8ff; }
.autosave .spin { animation: dc-spin 0.9s linear infinite; }
@keyframes dc-spin { to { transform: rotate(360deg); } }

.device-form { max-height: 70vh; overflow-y: auto; overflow-x: hidden; padding-right: 8px; }
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #8fb8ff;
  margin: 14px 0 10px;
  padding-left: 8px;
  border-left: 3px solid #5b8cff;
}
.full { width: 100% !important; }
.device-form :deep(.el-input),
.device-form :deep(.el-select),
.device-form :deep(.el-date-editor) { width: 100% !important; }
.device-form :deep(.el-form-item) { margin-bottom: 10px; }
.device-form :deep(.el-form-item__label) {
  padding-bottom: 2px;
  line-height: 1.3;
  color: #9aa6b8;
  font-size: 12px;
}

.fx-hint {
  margin: -2px 0 12px;
  padding: 6px 10px;
  font-size: 12px;
  color: #b9c4d6;
  background: rgba(91, 140, 255, 0.08);
  border-radius: 6px;
}
.settled-hint { background: rgba(103, 194, 58, 0.1); }

.pool-row { display: flex; align-items: center; gap: 10px; margin: -2px 0 10px; flex-wrap: wrap; }
.pool-label { font-size: 13px; color: #c7d0de; }
.pool-balance { font-size: 12px; }
.pool-hint { line-height: 1.7; }
.pool-warn { color: #e6a23c; }
.pool-draw { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }
.pool-seg { font-size: 12px; color: #9aa6b8; }

.parts-hint { font-size: 12px; color: #8a94a6; margin-bottom: 8px; line-height: 1.6; }
.quick-add { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 12px; }
.quick-add-label { font-size: 12px; color: #8a94a6; margin-right: 2px; }
.parts-empty {
  border: 1px dashed #3a4a66;
  border-radius: 10px;
  padding: 18px;
  text-align: center;
  color: #8a94a6;
  font-size: 13px;
  margin-bottom: 12px;
}

.part-card {
  border: 1px solid #22304a;
  border-radius: 10px;
  padding: 10px 12px 0;
  margin-bottom: 10px;
  background: rgba(91, 140, 255, 0.04);
}
/* 还没填的槽位淡一点：一眼能看出哪些是待填的模板、哪些是真有的部件 */
.part-card--blank {
  border-style: dashed;
  background: transparent;
}
.part-card--blank .part-head { opacity: 0.75; }
.part-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
.part-title { font-size: 13px; color: #c7d0de; }
.part-net { font-size: 12px; }
.part-actions { margin-left: auto; display: flex; align-items: center; gap: 2px; }

.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 24px;
  padding: 12px 14px;
  margin: 6px 0 10px;
  border-radius: 8px;
  background: #101b30;
  border: 1px solid #22304a;
}
.summary-item { display: flex; flex-direction: column; gap: 2px; }
.summary-label { font-size: 12px; color: #8a94a6; }
.summary-value { font-size: 15px; color: #e6edf7; }

@media (max-width: 768px) {
  .part-actions { margin-left: 0; }
}
</style>
