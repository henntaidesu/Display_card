import http from './http'

export const authApi = {
  login: (payload) => http.post('/auth/login', payload),
  me: () => http.get('/auth/me'),
  changePassword: (payload) => http.post('/auth/change-password', payload)
}

export const cardsApi = {
  list: (params) => http.get('/cards', { params }),
  // 顶部统计：对当前筛选下的全部卡做汇总（同一套筛选参数）
  stats: (params) => http.get('/cards/stats', { params }),
  get: (id) => http.get(`/cards/${id}`),
  create: (payload) => http.post('/cards', payload),
  // 新增弹窗打开即建的空草稿卡，只为拿到 id，好让图片立刻能传
  createDraft: () => http.post('/cards/draft'),
  update: (id, payload) => http.put(`/cards/${id}`, payload),
  changeStatus: (id, payload) => http.patch(`/cards/${id}/status`, payload),
  refreshFx: (id) => http.post(`/cards/${id}/refresh-fx`),
  remove: (id, purgeMedia = false) => http.delete(`/cards/${id}`, { params: { purge_media: purgeMedia } }),
  nextMgmtNo: () => http.get('/cards/next-mgmt-no')
}

// 库存合并列表：显卡与整机在同一张表里，行上带 kind 区分。筛选、排序、分页
// 都在后端统一做，前端不必自己把两个列表拼起来。
export const inventoryApi = {
  list: (params) => http.get('/inventory', { params }),
  stats: (params) => http.get('/inventory/stats', { params })
}

// 整机设备的增删改查：一次购入（一个总价）拆成多个部件分别出售。部件随设备整体
// 提交，保存时后端按提交的数组整体覆盖 device_parts。列表走上面的 inventoryApi。
export const devicesApi = {
  get: (id) => http.get(`/devices/${id}`),
  create: (payload) => http.post('/devices', payload),
  // 新增弹窗打开即建的空草稿设备，只为拿到 id 与管理编号
  createDraft: () => http.post('/devices/draft'),
  update: (id, payload) => http.put(`/devices/${id}`, payload),
  changeStatus: (id, payload) => http.patch(`/devices/${id}/status`, payload),
  refreshFx: (id) => http.post(`/devices/${id}/refresh-fx`),
  remove: (id) => http.delete(`/devices/${id}`),
  nextMgmtNo: () => http.get('/devices/next-mgmt-no')
}

export const mediaApi = {
  // 上传走 multipart，交给调用方自己构造 FormData
  upload: (formData) =>
    http.post('/media/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 600000 }),
  listForCard: (cardId) => http.get(`/media/card/${cardId}`),
  reorder: (mediaIds) => http.put('/media/reorder', { media_ids: mediaIds }),
  remove: (mediaId, purge = true) => http.delete(`/media/${mediaId}`, { params: { purge } })
}

export const fxApi = {
  rate: (params) => http.get('/fx/rate', { params }),
  history: (params) => http.get('/fx/history', { params }),
  refresh: (params) => http.post('/fx/refresh', null, { params }),
  getConfig: () => http.get('/fx/config'),
  setConfig: (params) => http.put('/fx/config', null, { params })
}

// 资金池：注资、扣款与 FIFO 分摊。写操作的响应里直接带回重算后的总账与两张明细表，
// 前端拿到就能整页刷新，不必再补一次 GET。
export const fundsApi = {
  overview: () => http.get('/funds'),
  summary: () => http.get('/funds/summary'),
  injections: () => http.get('/funds/injections'),
  createInjection: (payload) => http.post('/funds/injections', payload),
  updateInjection: (id, payload) => http.put(`/funds/injections/${id}`, payload),
  removeInjection: (id) => http.delete(`/funds/injections/${id}`),
  draws: (params) => http.get('/funds/draws', { params }),
  createDraw: (payload) => http.post('/funds/draws', payload),
  updateDraw: (id, payload) => http.put(`/funds/draws/${id}`, payload),
  removeDraw: (id) => http.delete(`/funds/draws/${id}`),
  rebuild: () => http.post('/funds/rebuild')
}

export const optionsApi = {
  enums: () => http.get('/options/enums'),
  brands: () => http.get('/options/brands'),
  createBrand: (payload) => http.post('/options/brands', payload),
  removeBrand: (id) => http.delete(`/options/brands/${id}`),
  models: () => http.get('/options/models'),
  createModel: (payload) => http.post('/options/models', payload),
  removeModel: (id) => http.delete(`/options/models/${id}`),
  usedBrands: () => http.get('/options/used-brands')
}

export const dashboardApi = {
  summary: (params) => http.get('/dashboard/summary', { params }),
  recent: (params) => http.get('/dashboard/recent', { params }),
  topModels: (params) => http.get('/dashboard/top-models', { params })
}

export const systemApi = {
  getImageHosting: () => http.get('/system/image-hosting'),
  saveImageHosting: (payload) => http.put('/system/image-hosting', payload),
  testImageHosting: () => http.post('/system/image-hosting/test'),
  databaseStatus: () => http.get('/system/database'),
  databaseReconnect: () => http.post('/system/database/reconnect')
}
