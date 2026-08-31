<template>
  <div class="stat-card" :style="{ borderTopColor: color }">
    <div class="stat-icon" :style="{ background: color + '20', color }">
      <el-icon :size="22"><component :is="iconComp" /></el-icon>
    </div>
    <div class="stat-info">
      <div class="stat-value" :class="valueClass">{{ display }}</div>
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
  // 顶边与图标底色都取这一个色，卡片之间靠它区分
  color: { type: String, default: '#409EFF' },
  valueClass: { type: String, default: '' }
})

// Element 图标里没有 Sell，做个兜底映射，避免整卡渲染不出来
const FALLBACK = { Sell: 'ShoppingCart' }
const iconComp = computed(() => Icons[props.icon] || Icons[FALLBACK[props.icon]] || Icons.DataLine)

const display = computed(() => (props.value === null || props.value === undefined ? '—' : props.value))
</script>

<style scoped>
.stat-card {
  background: #131c2f;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 14px;
  border: 1px solid #2a3446;
  border-top: 3px solid;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}
.stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-info { min-width: 0; }
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #ecf2ff;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
  /* 金额位数多时折行，不用省略号——省略号会把 ￥12,345,678 读成 ￥12,345… */
  overflow-wrap: anywhere;
}
/* 盈亏色要盖过上面那条 .stat-value 的默认色：全局的 .dc-profit / .dc-loss
   没带 scoped 属性选择器，特异性比它低，不在这里重申一遍就会被吃掉 */
.stat-value.dc-profit { color: var(--dc-profit); }
.stat-value.dc-loss { color: var(--dc-loss); }
.stat-label { font-size: 12px; color: #9ba8bf; margin-top: 2px; }
</style>
