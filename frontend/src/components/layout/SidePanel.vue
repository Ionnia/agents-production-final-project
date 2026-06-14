<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import SessionList from './SessionList.vue'
import GroupList from './GroupList.vue'
import PlanList from './PlanList.vue'
import { useChatStore } from '../../stores/chat'
import { useAuthStore } from '../../stores/auth'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const router = useRouter(); const chat = useChatStore(); const auth = useAuthStore()
const filter = ref('')
function newChat() { chat.reset(); router.push('/'); emit('close') }
async function logout() { await auth.logout(); router.push('/login') }
</script>

<template>
  <transition name="slide">
    <aside v-show="open" class="panel glass" @keydown.esc="emit('close')">
      <div class="title">Маршруты</div>
      <button class="newchat" @click="newChat">＋ Новый чат</button>
      <input v-model="filter" class="search" placeholder="Поиск по чатам…" />
      <div class="scroll">
        <SessionList :filter="filter" @navigate="emit('close')" />
        <GroupList :filter="filter" />
        <PlanList @navigate="emit('close')" />
      </div>
      <button class="logout" @click="logout">Выйти</button>
    </aside>
  </transition>
</template>

<style scoped>
.panel { position: fixed; top: 0; left: 0; bottom: 0; width: 308px; z-index: 25; padding: 16px; display: flex; flex-direction: column; gap: 12px;
  border-radius: 0 22px 22px 0; color: var(--ink); }
.title { font-weight: 700; padding: 6px 4px 0 54px; color: #1c150f; }
.newchat { padding: 11px 13px; border: none; border-radius: 13px; cursor: pointer; font-weight: 600; background: var(--accent); color: #fff; }
.search { padding: 9px 12px; border: none; border-radius: 11px; background: rgba(255,255,255,.4); color: var(--ink); font-size: 13.5px; }
.search::placeholder { color: var(--ink-soft); }
.scroll { flex: 1; overflow: auto; display: flex; flex-direction: column; gap: 6px; }
.logout { padding: 9px; border: none; border-radius: 10px; background: rgba(0,0,0,.08); color: #3a3024; cursor: pointer; }
.slide-enter-active, .slide-leave-active { transition: transform .42s cubic-bezier(.5,.05,.1,1); }
.slide-enter-from, .slide-leave-to { transform: translateX(-104%); }
@media (max-width: 480px) { .panel { width: 100vw; border-radius: 0; } }
</style>
