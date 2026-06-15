import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/endpoints'
import type { GroupSummary, Group, CreateGroupRequest } from '../api/types'

export const useGroupsStore = defineStore('groups', () => {
  const list = ref<GroupSummary[]>([])
  const current = ref<Group | null>(null)
  async function loadList() { list.value = (await api.groups()).items }
  async function load(id: string) { current.value = await api.group(id) }
  async function create(body: CreateGroupRequest) { const g = await api.createGroup(body); current.value = g; return g }
  // Drop the signed-in user's cached groups so the next user can't see them.
  function reset() { list.value = []; current.value = null }
  return { list, current, loadList, load, create, reset }
})
