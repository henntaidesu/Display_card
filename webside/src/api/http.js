import axios from 'axios'
import { ElLoading } from 'element-plus'
import { ElMessage } from '@/utils/notify'

// 后端所有端点都在 /api/v1 下；各 api 模块用 '/cards' 这样的相对路径拼接。
const http = axios.create({
  baseURL: '/api/v1',
  timeout: 20000
})

let offlineLoading = null
let healthTimer = null
let authExpiredHandled = false

function isNetworkError(err) {
  return err.code === 'ERR_NETWORK' || err.message === 'Network Error'
}

// FastAPI 的 422 校验错误 detail 是数组，原样丢给 ElMessage 只会显示 [object Object]，
// 这里归一化成「字段: 说明」的可读文本。
function errorText(detail, fallback) {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => {
        if (typeof d === 'string') return d
        const loc = Array.isArray(d?.loc) ? d.loc.filter((x) => x !== 'body').join('.') : ''
        const msg = d?.msg || d?.type || ''
        return loc ? `${loc}: ${msg}` : msg
      })
      .filter(Boolean)
    if (parts.length) return parts.join('；')
  }
  if (detail && typeof detail === 'object') {
    const msg = detail.msg || detail.message
    if (typeof msg === 'string' && msg.trim()) return msg
  }
  return fallback
}

function startHealthPolling() {
  if (healthTimer) return
  healthTimer = setInterval(async () => {
    try {
      const resp = await fetch('/api/health', { cache: 'no-store' })
      if (resp.ok) hideOfflineOverlay()
    } catch (_) {
      // 仍断连，等下一次探测
    }
  }, 3000)
}

function showOfflineOverlay() {
  if (offlineLoading) return
  offlineLoading = ElLoading.service({
    fullscreen: true,
    lock: true,
    text: '无法连接后端，请检查服务器是否启动',
    background: 'rgba(0, 0, 0, 0.7)'
  })
  startHealthPolling()
}

function hideOfflineOverlay() {
  if (offlineLoading) {
    offlineLoading.close()
    offlineLoading = null
  }
  if (healthTimer) {
    clearInterval(healthTimer)
    healthTimer = null
  }
}

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (res) => {
    hideOfflineOverlay()
    authExpiredHandled = false
    return res.data
  },
  (err) => {
    if (err.code === 'ERR_CANCELED' || err.name === 'CanceledError') {
      return Promise.reject(err)
    }
    if (isNetworkError(err)) {
      showOfflineOverlay()
      return Promise.reject(err)
    }
    if (err.response?.status === 401) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_user')
      // 并发请求会同时收到 401，只提示一次并跳登录页
      if (!authExpiredHandled) {
        authExpiredHandled = true
        ElMessage.error(errorText(err.response?.data?.detail, '登录已过期，请重新登录'))
        if (window.location.hash !== '#/login') window.location.hash = '#/login'
      }
      return Promise.reject(err)
    }
    ElMessage.error(errorText(err.response?.data?.detail, err.message || '请求失败'))
    return Promise.reject(err)
  }
)

export default http
