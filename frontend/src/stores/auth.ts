import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, setTokenGetter } from '../api/endpoints'
import type { User } from '../api/types'

const LS = 'travel.auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  const ready = ref(false)
  const isAuthenticated = computed(() => !!accessToken.value)
  setTokenGetter(() => accessToken.value)

  function persist() { localStorage.setItem(LS, JSON.stringify({ refreshToken: refreshToken.value })) }

  async function login(email: string, password: string) {
    const r = await api.login({ email, password })
    accessToken.value = r.access_token; refreshToken.value = r.refresh_token; user.value = r.user; persist()
  }
  async function register(name: string, email: string, password: string) {
    const r = await api.register({ name, email, password })
    accessToken.value = r.tokens.access_token; refreshToken.value = r.tokens.refresh_token; user.value = r.user; persist()
  }
  async function restore() {
    ready.value = true
    const raw = localStorage.getItem(LS); if (!raw) return
    try {
      const { refreshToken: rt } = JSON.parse(raw) as { refreshToken: string | null }
      if (!rt) return
      const r = await api.refresh(rt); accessToken.value = r.access_token; refreshToken.value = r.refresh_token; persist(); user.value = await api.me()
    } catch { localStorage.removeItem(LS) }
  }
  async function logout() {
    if (refreshToken.value) { try { await api.logout(refreshToken.value) } catch {} }
    user.value = null; accessToken.value = null; refreshToken.value = null; localStorage.removeItem(LS)
  }
  return { user, accessToken, refreshToken, ready, isAuthenticated, login, register, restore, logout }
})
