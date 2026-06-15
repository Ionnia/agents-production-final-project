import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, setTokenGetter } from '../api/endpoints'
import { ApiClientError } from '../api/client'
import { useSessionsStore } from './sessions'
import { useGroupsStore } from './groups'
import { useChatStore } from './chat'
import { usePlansStore } from './plans'
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
  // The SPA keeps Pinia stores alive across a login/logout (no full page reload),
  // so every session boundary must purge the previous user's per-user caches —
  // otherwise the next user keeps seeing the prior user's history/groups/plans
  // (the side-panel lists only refetch when empty).
  function resetUserData() {
    useSessionsStore().reset(); useGroupsStore().reset(); usePlansStore().reset(); useChatStore().reset()
  }
  function clearAuth() { user.value = null; accessToken.value = null; refreshToken.value = null; localStorage.removeItem(LS); resetUserData() }

  async function login(email: string, password: string) {
    resetUserData()
    const r = await api.login({ email, password })
    accessToken.value = r.access_token; refreshToken.value = r.refresh_token; user.value = r.user; persist()
  }
  async function register(name: string, email: string, password: string) {
    resetUserData()
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
    } catch (e) {
      // Only a genuine 401 (invalid/expired refresh) should clear the stored token.
      // Transient failures (500/502/503, network blips) must leave it intact so the
      // session is recoverable on the next boot instead of forcing a re-login.
      if (e instanceof ApiClientError && e.status === 401) clearAuth()
    }
  }
  async function logout() {
    if (refreshToken.value) { try { await api.logout(refreshToken.value) } catch {} }
    clearAuth()
  }
  return { user, accessToken, refreshToken, ready, isAuthenticated, login, register, restore, logout }
})
