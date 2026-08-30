import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(safeParse(localStorage.getItem('auth_user')))

  function safeParse(raw) {
    try {
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  }

  async function login(username, password) {
    const res = await authApi.login({ username, password })
    localStorage.setItem('auth_token', res.token)
    localStorage.setItem('auth_user', JSON.stringify(res.user))
    user.value = res.user
    return res.user
  }

  function logout() {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    user.value = null
    window.location.hash = '#/login'
  }

  return { user, login, logout }
})
