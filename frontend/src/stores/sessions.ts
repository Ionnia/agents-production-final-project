import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/endpoints'
import type { SessionSummary, SessionDetail } from '../api/types'

export const useSessionsStore = defineStore('sessions', () => {
  const list = ref<SessionSummary[]>([])
  const current = ref<SessionDetail | null>(null)
  const loading = ref(false)

  async function loadList() { loading.value = true; try { list.value = (await api.sessions()).items } finally { loading.value = false } }
  async function loadDetail(id: string) { loading.value = true; try { current.value = await api.session(id) } finally { loading.value = false } }
  function clearCurrent() { current.value = null }
  return { list, current, loading, loadList, loadDetail, clearCurrent }
})
