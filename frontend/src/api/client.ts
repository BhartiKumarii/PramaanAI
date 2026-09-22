import axios from 'axios'

// Dev: Vite proxies /api -> http://127.0.0.1:8000 (see vite.config.ts), so
// the browser only ever talks to one origin. Prod build can override via
// VITE_API_BASE_URL to point straight at the deployed backend.
export const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export const apiClient = axios.create({ baseURL })

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('bsa_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('bsa_access_token')
      localStorage.removeItem('bsa_user')
      if (!window.location.pathname.startsWith('/login')) {
        window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  },
)
