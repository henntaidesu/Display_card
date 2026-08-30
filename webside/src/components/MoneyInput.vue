<template>
  <el-form-item :label="label">
    <div class="money-input">
      <el-input-number
        :model-value="amount"
        :precision="currency === 'JPY' ? 0 : 2"
        :step="currency === 'JPY' ? 100 : 1"
        :min="0"
        :controls="false"
        class="amount"
        @update:model-value="(v) => emit('update:amount', v)"
      />
      <el-select
        :model-value="currency"
        class="currency"
        @update:model-value="(v) => emit('update:currency', v)"
      >
        <el-option v-for="c in currencies" :key="c" :label="t('currency.' + c + '_short')" :value="c" />
      </el-select>
    </div>
  </el-form-item>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMetaStore } from '@/stores/meta'

defineProps({
  label: { type: String, default: '' },
  amount: { type: [Number, null], default: null },
  currency: { type: String, default: 'JPY' }
})
const emit = defineEmits(['update:amount', 'update:currency'])

const { t } = useI18n()
const meta = useMetaStore()
const currencies = computed(() => meta.enums.currencies?.length ? meta.enums.currencies : ['JPY', 'CNY'])
</script>

<style scoped>
.money-input { display: flex; gap: 6px; width: 100%; }
.amount { flex: 1; }
.amount :deep(.el-input__inner) { text-align: right; }
.currency { width: 92px !important; flex: 0 0 92px; }
.money-input :deep(.el-input-number) { width: 100% !important; }
</style>
