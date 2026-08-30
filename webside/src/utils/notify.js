import { ElMessage as RawElMessage } from 'element-plus'

// 同一条错误在并发请求下会连弹好几遍（比如 3 个请求同时 401）。这里做去重：
// 相同文案在 1.5 秒内只显示一次。
const recent = new Map()
const DEDUP_MS = 1500

function dedup(type, message) {
  const key = `${type}:${message}`
  const now = Date.now()
  const last = recent.get(key)
  if (last && now - last < DEDUP_MS) return true
  recent.set(key, now)
  // 顺手清理过期的键，别让 Map 无限增长
  if (recent.size > 50) {
    for (const [k, t] of recent) {
      if (now - t > DEDUP_MS) recent.delete(k)
    }
  }
  return false
}

function make(type) {
  return (options) => {
    const message = typeof options === 'string' ? options : options?.message
    if (message && dedup(type, message)) return
    return RawElMessage(typeof options === 'string' ? { message: options, type } : { ...options, type })
  }
}

export const ElMessage = Object.assign(make('info'), {
  success: make('success'),
  warning: make('warning'),
  info: make('info'),
  error: make('error')
})
