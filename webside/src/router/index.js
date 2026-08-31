import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login/index.vue'),
    meta: { public: true, titleKey: 'route.login' }
  },
  {
    path: '/',
    component: () => import('@/components/Layout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/Dashboard/index.vue'), meta: { titleKey: 'route.dashboard', icon: 'Odometer' } },
      { path: 'cards', name: 'Cards', component: () => import('@/views/Cards/index.vue'), meta: { titleKey: 'route.cards', icon: 'Cpu' } },
      { path: 'cards/:id', name: 'CardDetail', component: () => import('@/views/CardDetail/index.vue'), meta: { titleKey: 'route.cardDetail', icon: 'Cpu', hidden: true } },
      { path: 'funds', name: 'Funds', component: () => import('@/views/Funds/index.vue'), meta: { titleKey: 'route.funds', icon: 'Wallet' } },
      { path: 'fx', name: 'Fx', component: () => import('@/views/Fx/index.vue'), meta: { titleKey: 'route.fx', icon: 'TrendCharts' } },
      { path: 'settings', name: 'Settings', component: () => import('@/views/Settings/index.vue'), meta: { titleKey: 'route.settings', icon: 'Setting' } }
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  const isPublic = Boolean(to.meta?.public)
  const token = localStorage.getItem('auth_token')
  if (!isPublic && !token) return next('/login')
  if (to.path === '/login' && token) return next('/dashboard')
  next()
})

export default router
