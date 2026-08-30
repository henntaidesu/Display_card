<template>
  <el-tag :type="tagType" size="small" effect="dark" round>{{ t('status.' + status) }}</el-tag>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { STATUS_TAG_TYPE } from '@/utils/format'

const props = defineProps({ status: { type: String, required: true } })
const { t } = useI18n()
const tagType = computed(() => STATUS_TAG_TYPE[props.status] || 'info')
</script>
