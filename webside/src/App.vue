<template>
  <el-config-provider :locale="elementLocale">
    <router-view />
  </el-config-provider>
</template>

<script setup>
import { ElConfigProvider } from 'element-plus'
import { elementLocale } from '@/i18n'
</script>

<style>
/* 深色主题地基，配色与 FreeMarket_Manager 对齐：底 #0b1220 / 卡片 #131c2f */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root.dark {
  color-scheme: dark;
}

:root {
  --app-vh: 1vh;
  --dc-bg: #0b1220;
  --dc-card: #131c2f;
  --dc-card-header: #161f33;
  --dc-border: #28354a;
  --dc-text: #e6edf7;
  --dc-text-dim: #a6adb4;
  --dc-accent: #5b8cff;
  --dc-profit: #4ade80;
  --dc-loss: #f87171;
}

@supports (height: 1dvh) {
  :root { --app-vh: 1dvh; }
}

html.dark {
  --el-bg-color: #0b1220;
  --el-bg-color-page: #0b1220;
  --el-fill-color-blank: #131c2f;
  --el-fill-color-light: #18233a;
  --el-mask-color: rgba(11, 18, 32, 0.78);
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  background: var(--dc-bg);
  color: #e5e7eb;
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-thumb { background: #3a4456; border-radius: 3px; }
::-webkit-scrollbar-track { background: transparent; }

.page-title { color: #e6edf7 !important; }

.el-card, .el-dialog, .el-table,
.el-input__wrapper, .el-select__wrapper, .el-textarea__inner {
  border-color: #2a3446 !important;
}

.el-card {
  background: #131c2f !important;
  color: #e6edf7;
}
.el-card__header {
  background: #161f33 !important;
  border-bottom: 1px solid #28354a !important;
  color: #e6edf7 !important;
}
.el-card__body { background: transparent !important; color: #e6edf7; }

.el-loading-mask { background-color: var(--el-mask-color) !important; }
.el-loading-mask .el-loading-spinner .path { stroke: #8fb8ff; }

.el-table {
  --el-table-header-bg-color: #18233a;
  --el-table-tr-bg-color: #131c2f;
  --el-table-row-hover-bg-color: #1b2942;
  --el-table-border-color: #28354a;
  color: #d6deea;
}
.el-dialog { --el-dialog-bg-color: #131c2f; }

/* iOS 文本自动放大 / 链式滚动 / 点击高亮，三个移动端通病一并按 FreeMarket 的做法压掉 */
html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
html, body { overscroll-behavior: none; }
body { -webkit-tap-highlight-color: transparent; }

@media (max-width: 768px) {
  /* iOS 聚焦 <16px 的输入框会强行放大整页且不复位——所有输入类控件手机上一律 16px */
  .el-input__inner, .el-input__wrapper, .el-textarea__inner,
  .el-select__wrapper, .el-select__placeholder {
    font-size: 16px;
  }
  .el-dialog {
    --el-dialog-margin-top: 5vh;
    width: 94vw !important;
    max-width: 94vw;
  }
  /* 弹窗表单一律标签在上，窄屏下不挤成一条 */
  .el-dialog .el-form-item { display: block; }
  .el-dialog .el-form-item__label {
    width: auto !important;
    justify-content: flex-start;
    text-align: left;
    padding: 0 0 4px;
  }
  .el-dialog .el-form-item__content { margin-left: 0 !important; }
  .el-card__body { padding: 12px; }
  .el-card__header { padding: 12px; }
  .el-table { font-size: 12px; }
  @media (hover: none) {
    .el-table { --el-table-row-hover-bg-color: transparent; }
  }
}

/* 通用工具类 */
.dc-profit { color: var(--dc-profit); }
.dc-loss { color: var(--dc-loss); }
.dc-dim { color: var(--dc-text-dim); }
.dc-mono { font-variant-numeric: tabular-nums; }
</style>
