import http from './http'

export const authApi = {
  login: (payload) => http.post('/auth/login', payload),
  me: () => http.get('/auth/me'),
  changePassword: (payload) => http.post('/auth/change-password', payload)
}

export const cardsApi = {
  list: (params) => http.get('/cards', { params }),
  get: (id) => http.get(`/cards/${id}`),
  create: (payload) => http.post('/cards', payload),
  update: (id, payload) => http.put(`/cards/${id}`, payload),
  changeStatus: (id, payload) => http.patch(`/cards/${id}/status`, payload),
  refreshFx: (id) => http.post(`/cards/${id}/refresh-fx`),
  remove: (id, purgeMedia = false) => http.delete(`/cards/${id}`, { params: { purge_media: purgeMedia } }),
  nextMgmtNo: () => http.get('/cards/next-mgmt-no')
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
