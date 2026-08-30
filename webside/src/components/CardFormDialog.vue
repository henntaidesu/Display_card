<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? t('card.editTitle') : t('card.addTitle')"
    width="820px"
    top="6vh"
    :close-on-click-modal="false"
    @closed="onClosed"
  >
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
      <div v-if="fxPreview.purchase" class="fx-hint">
        {{ t('card.fxPreview') }}: 1 {{ t('currency.CNY_short') }} = {{ formatRate(fxPreview.purchase.rate) }} {{ t('currency.JPY_short') }}
        <span class="dc-dim">（{{ fxPreview.purchase.rate_date }}{{ fxPreview.purchase.stale ? ' *' : '' }}）</span>
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

      <el-collapse class="manual-fx">
        <el-collapse-item :title="t('card.fxManual')">
          <el-row :gutter="16">
            <el-col :xs="24" :sm="12">
              <el-form-item :label="t('card.purchaseFx')">
                <el-input-number v-model="form.purchase_fx_rate" :precision="6" :step="0.001" :controls="false" class="full" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :sm="12">
              <el-form-item :label="t('card.saleFx')">
                <el-input-number v-model="form.sale_fx_rate" :precision="6" :step="0.001" :controls="false" class="full" />
              </el-form-item>
            </el-col>
          </el-row>
          <p class="dc-dim manual-hint">{{ t('card.fxManualHint') }}</p>
        </el-collapse-item>
      </el-collapse>

      <el-form-item :label="t('card.note')">
        <el-input v-model="form.note" type="textarea" :rows="2" />
      </el-form-item>

      <!-- 图片 / 视频：文件要挂到卡片上，必须先有 card_id；新增时先存基本信息再解锁上传 -->
      <div class="section-title media-title">
        <el-icon><Picture /></el-icon>{{ t('card.media') }}
      </div>
      <MediaManager
        v-if="isEdit"
        ref="mediaRef"
        :card-id="form.id"
        :hosting-configured="hostingConfigured"
        @changed="$emit('media-changed')"
      />
      <div v-else class="media-placeholder">
        <el-icon :size="34"><UploadFilled /></el-icon>
        <p class="media-placeholder-hint">{{ t('card.mediaHint') }}</p>
        <div class="media-cats">
          <span v-for="cat in mediaCategories" :key="cat" class="media-cat-chip">{{ t('category.' + cat) }}</span>
        </div>
      </div>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">
        {{ isEdit ? t('common.save') : t('card.saveToUpload') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { cardsApi, fxApi, optionsApi } from '@/api'
import { ElMessage } from '@/utils/notify'
import { formatRate } from '@/utils/format'
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

const isEdit = computed(() => Boolean(form.id))
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
const formRef = ref()
const mediaRef = ref()
const fxPreview = reactive({ purchase: null, sale: null })

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
    status: 'purchased', note: null,
    purchase_fx_rate: null, sale_fx_rate: null
  }
}

const form = reactive(blankForm())

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    fxPreview.purchase = null
    fxPreview.sale = null
    // 型号独立于品牌，进弹窗就拉全量
    await loadModels()
    if (props.card) {
      Object.assign(form, blankForm(), normalize(props.card))
    } else {
      Object.assign(form, blankForm())
      try {
        const res = await cardsApi.nextMgmtNo()
        form.mgmt_no = res.mgmt_no
      } catch { /* 忽略，保存时后端会生成 */ }
    }
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

async function onSave() {
  saving.value = true
  try {
    const payload = { ...form }
    delete payload.mgmt_no
    let result
    if (isEdit.value) {
      result = await cardsApi.update(form.id, payload)
    } else {
      result = await cardsApi.create(payload)
      // 新建成功后把 id / 编号回填，切到编辑态，用户可以接着上传图片
      form.id = result.id
      form.mgmt_no = result.mgmt_no
    }
    // 现敲的品牌/型号落库，下次进下拉能选到
    await persistDict()
    if (result.warnings?.length) {
      result.warnings.forEach((w) => ElMessage.warning(w))
    } else {
      ElMessage.success(t('common.saved'))
    }
    emit('saved', result)
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
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

function onClosed() {
  models.value = []
}
</script>

<style scoped>
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
