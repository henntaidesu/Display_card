<template>
  <div ref="el" class="echart" :style="{ height }"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '320px' }
})

const el = ref()
let chart = null

function render() {
  if (!chart) return
  // notMerge:true —— 系列数量变化时（比如筛选后月份变少）不留下上一次的残影
  chart.setOption(props.option, true)
}

function resize() {
  chart?.resize()
}

onMounted(() => {
  chart = echarts.init(el.value, 'dark')
  render()
  window.addEventListener('resize', resize)
})

watch(() => props.option, render, { deep: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.echart { width: 100%; }
/* echarts 的 dark 主题底色是纯黑，盖成卡片色 */
.echart :deep(canvas) { background: transparent !important; }
</style>
