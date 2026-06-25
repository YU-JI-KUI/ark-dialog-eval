import axios from 'axios'

const http = axios.create({ baseURL: '/api', timeout: 60000 })

export const api = {
  getConfig: () => http.get('/meta/config').then((r) => r.data),
  getBus: () => http.get('/meta/bus').then((r) => r.data.bus),
  getIntents: (bu = 'securities') => http.get('/meta/intents', { params: { bu } }).then((r) => r.data.intents),

  runSample: (bu = 'securities', kind = 'calib') =>
    http.get('/eval/sample', { params: { bu, kind } }).then((r) => r.data),
  upload: (file, bu = 'securities', onProgress) => {
    const fd = new FormData()
    fd.append('file', file)
    return http
      .post('/eval/upload', fd, {
        params: { bu },
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
        },
      })
      .then((r) => r.data)
  },

  listTasks: () => http.get('/eval/tasks').then((r) => r.data.tasks),
  getTask: (id) => http.get(`/eval/tasks/${id}`).then((r) => r.data),
  getResult: (id) => http.get(`/eval/tasks/${id}/result`).then((r) => r.data),
  resume: (id) => http.post(`/eval/tasks/${id}/resume`).then((r) => r.data),
  exportUrl: (id) => `/api/eval/tasks/${id}/export`,
  exportReportUrl: (id) => `/api/eval/tasks/${id}/export/report`,
  exportRowsUrl: (id) => `/api/eval/tasks/${id}/export/rows`,
}
