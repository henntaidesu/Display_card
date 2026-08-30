<template>
  <div class="stat-card" :class="'tone-' + tone">
    <div class="stat-icon"><el-icon :size="20"><component :is="iconComp" /></el-icon></div>
    <div class="stat-body">
      <div class="stat-value" :class="{ 'dc-mono': mono }">{{ value ?? '—' }}</div>
      <div class="stat-label">{{ label }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import * as Icons from '@element-plus/icons-vue'

const props = defineProps({
  label: { type: String, default: '' },
  value: { type: [String, Number, null], default: null },
  icon: { type: String, default: 'DataLine' },
  tone: { type: String, default: 'blue' },
  mono: { type: Boolean, default: false }
})

// Element 图标里没有 Sell，做个兜底映射，避免整卡渲染不出来
const FALLBACK = { Sell: 'ShoppingCart', Box: 'Box' }
const iconComp = computed(() => Icons[props.icon] || Icons[FALLBACK[props.icon]] || Icons.DataLine)
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  background: #131c2f;
  border: 1px solid #222f47;
}
.stat-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 42px;
}
.stat-body { min-width: 0; }
.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: #e6edf7;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.stat-label { font-size: 12px; color: #8a94a6; margin-top: 4px; }

.tone-blue .stat-icon { background: rgba(91,140,255,0.16); color: #7ba2ff; }
.tone-cyan .stat-icon { background: rgba(56,189,248,0.16); color: #38bdf8; }
.tone-violet .stat-icon { background: rgba(124,92,255,0.16); color: #a78bfa; }
.tone-amber .stat-icon { background: rgba(245,166,35,0.16); color: #f5a623; }
.tone-teal .stat-icon { background: rgba(45,212,191,0.16); color: #2dd4bf; }
.tone-green .stat-icon { background: rgba(74,222,128,0.16); color: #4ade80; }
.tone-green .stat-value { color: #4ade80; }
.tone-red .stat-icon { background: rgba(248,113,113,0.16); color: #f87171; }
.tone-red .stat-value { color: #f87171; }
</style>
