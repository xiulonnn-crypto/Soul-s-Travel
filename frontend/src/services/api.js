import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const tripApi = {
  list: (params) => api.get('/trips', { params }).then(r => r.data),
  get: (id) => api.get(`/trips/${id}`).then(r => r.data),
  create: (data) => api.post('/trips', data).then(r => r.data),
  update: (id, data) => api.put(`/trips/${id}`, data).then(r => r.data),
  delete: (id) => api.delete(`/trips/${id}`).then(r => r.data),
  createShare: (id) => api.post(`/trips/${id}/share`).then(r => r.data),
  revokeShare: (id) => api.delete(`/trips/${id}/share`).then(r => r.data),
}

export const statsApi = {
  overview: () => api.get('/stats/overview').then(r => r.data),
  destinations: () => api.get('/stats/destinations').then(r => r.data),
  expenses: () => api.get('/stats/expenses').then(r => r.data),
}

export const shareApi = {
  get: (token) => api.get(`/share/${token}`).then(r => r.data),
}

export const evaluationApi = {
  get: (tripId) => api.get(`/trips/${tripId}/evaluation`).then(r => r.data),
  regenerate: (tripId) => api.post(`/trips/${tripId}/evaluation`).then(r => r.data),
}

export const parseApi = {
  text: (text) => api.post('/parse', { text }).then(r => r.data),
  file: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/parse', form).then(r => r.data)
  },
}

export default api
