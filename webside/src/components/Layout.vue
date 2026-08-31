<template>
  <el-container class="layout" :class="{ 'layout--mobile': isMobile }">
    <!-- 手机：抽屉遮罩 + 唤出按钮挂到 body，避开父级 transform 让 fixed 失效 -->
    <Teleport to="body">
      <div v-if="isMobile && drawerOpen" class="layout-mask" @click="drawerOpen = false" />
    </Teleport>
    <Teleport to="body">
      <button v-if="isMobile && !drawerOpen" class="layout-fab" type="button" @click="drawerOpen = true">
        <el-icon :size="22"><Menu /></el-icon>
      </button>
    </Teleport>

    <Teleport to="body" :disabled="!isMobile">
      <el-aside
        width="216px"
        class="sidebar"
        :class="{ 'sidebar--mobile': isMobile, 'sidebar--open': isMobile && drawerOpen }"
      >
        <div class="sidebar-inner">
          <div class="logo">
            <img class="logo-img" src="/static/logo.svg" alt="logo" />
            <span class="logo-text">{{ t('app.short') }}</span>
          </div>

          <el-menu
            :default-active="activePath"
            class="menu"
            background-color="transparent"
            text-color="#a6adb4"
            active-text-color="#ffffff"
            @select="onSelect"
          >
            <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
              <el-icon><component :is="item.icon" /></el-icon>
              <template #title>{{ t(item.titleKey) }}</template>
            </el-menu-item>
          </el-menu>

          <div class="sidebar-footer">
            <el-select :model-value="locale" size="small" class="lang-select" @change="onLocaleChange">
              <el-option v-for="opt in localeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
            <div class="footer-row">
              <span class="user-name" :title="userName">{{ userName }}</span>
              <el-button size="small" type="danger" plain @click="handleLogout">
                {{ t('common.logout') }}
              </el-button>
            </div>
          </div>
        </div>
      </el-aside>
    </Teleport>

    <el-main class="main">
      <router-view v-slot="{ Component }">
        <keep-alive include="Cards,Dashboard">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </el-main>
  </el-container>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { currentLocale, localeOptions, setLocale } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useIsMobile } from '@/composables/useIsMobile'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { isMobile } = useIsMobile()

const drawerOpen = ref(false)
const locale = currentLocale

const menuItems = [
  { path: '/dashboard', titleKey: 'route.dashboard', icon: 'Odometer' },
  { path: '/cards', titleKey: 'route.cards', icon: 'Cpu' },
  { path: '/funds', titleKey: 'route.funds', icon: 'Wallet' },
  { path: '/fx', titleKey: 'route.fx', icon: 'TrendCharts' },
  { path: '/settings', titleKey: 'route.settings', icon: 'Setting' }
]

// 详情页 /cards/:id 高亮到「显卡库存」
const activePath = computed(() => {
  if (route.path.startsWith('/cards')) return '/cards'
  return route.path
})

const userName = computed(() => auth.user?.username || 'admin')

// 切页面自动收起手机抽屉，否则点完还挡着内容
watch(() => route.path, () => { drawerOpen.value = false })

function onSelect(path) {
  if (path !== route.path) router.push(path)
}
function onLocaleChange(value) {
  setLocale(value)
}
function handleLogout() {
  auth.logout()
}
</script>

<style scoped>
.layout { height: 100%; }

.sidebar {
  background: #0f1728;
  border-right: 1px solid #1c2740;
  height: 100%;
  overflow: hidden;
}
.sidebar-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0;
}
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 18px 14px;
}
.logo-img { width: 30px; height: 30px; }
.logo-text { font-size: 16px; font-weight: 600; color: #e6edf7; letter-spacing: 0.3px; }

.menu {
  flex: 1;
  border-right: none;
  padding: 6px 8px;
  overflow-y: auto;
}
.menu :deep(.el-menu-item) {
  border-radius: 8px;
  margin-bottom: 4px;
  height: 46px;
}
.menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(91,140,255,0.22), rgba(124,92,255,0.14));
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid #1c2740;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.lang-select { width: 100% !important; }
.footer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.user-name {
  color: #a6adb4;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.main {
  padding: 20px 24px;
  height: 100%;
  overflow-y: auto;
  background: #0b1220;
}

/* ---- 手机抽屉 ---- */
.sidebar--mobile {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 2000;
  transform: translateX(-100%);
  transition: transform 0.25s ease;
}
.sidebar--open { transform: translateX(0); }
.layout-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1999;
}
.layout-fab {
  position: fixed;
  left: 14px;
  bottom: 18px;
  z-index: 1500;
  width: 46px;
  height: 46px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #5b8cff, #7c5cff);
  color: #fff;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
}
@media (max-width: 768px) {
  .main { padding: 14px 12px calc(72px + env(safe-area-inset-bottom)); }
}
</style>
