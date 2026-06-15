<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useEventListener } from '@vueuse/core'
import SessionList from './SessionList.vue'
import GroupList from './GroupList.vue'
import PlanList from './PlanList.vue'
import { useChatStore } from '../../stores/chat'
import { useAuthStore } from '../../stores/auth'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const router = useRouter(); const chat = useChatStore(); const auth = useAuthStore()
const filter = ref('')
useEventListener(window, 'keydown', (e) => { if (props.open && e.key === 'Escape') emit('close') })
function newChat() { chat.reset(); router.push('/'); emit('close') }
async function logout() { emit('close'); await auth.logout(); router.push('/login') }
</script>

<template>
  <transition name="fade">
    <div v-if="open" class="scrim" @click="emit('close')" />
  </transition>
  <transition name="slide">
    <aside v-show="open" class="panel glass">
      <div class="header">
        <span class="title">Маршруты</span>
        <button class="close" type="button" aria-label="Закрыть" @click="emit('close')">✕</button>
      </div>
      <button class="newchat" @click="newChat">＋ Новый чат</button>
      <input v-model="filter" class="search" placeholder="Поиск по чатам…" />
      <div class="scroll">
        <GroupList :filter="filter" />
        <PlanList :filter="filter" @navigate="emit('close')" />
        <SessionList :filter="filter" @navigate="emit('close')" />
      </div>
      <button class="logout" @click="logout">Выйти</button>
    </aside>
  </transition>
</template>

<style scoped>
.scrim { position: fixed; inset: 0; z-index: 30; background: rgba(0, 0, 0, .25); }
.panel { position: fixed; top: 0; left: 0; bottom: 0; width: 308px; z-index: 35; padding: 16px; display: flex; flex-direction: column; gap: 12px;
  border-radius: 0 22px 22px 0; color: var(--ink); }
.header { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 4px 2px 0; }
.title { font-weight: 700; color: #1c150f; }
.close { width: 32px; height: 32px; flex: none; border: none; border-radius: 9px; cursor: pointer; font-size: 15px; line-height: 1;
  background: rgba(0, 0, 0, .08); color: #3a3024; transition: var(--tap); }
@media (hover: hover) { .close:hover { background: rgba(0, 0, 0, .14); transform: translateY(-1px); } }
.close:active { transform: translateY(0) scale(.97); }
.fade-enter-active, .fade-leave-active { transition: opacity .42s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.newchat { padding: 11px 13px; border: none; border-radius: 13px; cursor: pointer; font-weight: 600; background: var(--accent); color: #fff; transition: var(--tap); }
@media (hover: hover) { .newchat:not(:disabled):hover { filter: brightness(1.06); transform: translateY(-1px); box-shadow: var(--accent-glow); } }
.newchat:not(:disabled):active { transform: translateY(0) scale(.97); filter: brightness(.95); box-shadow: var(--accent-glow-press); }
.newchat:disabled { transform: none; }
.search { padding: 9px 12px; border: none; border-radius: 11px; background: rgba(255,255,255,.4); color: var(--ink); font-size: 13.5px; }
.search::placeholder { color: var(--ink-soft); }
/* No shared scrollbar: each section scrolls on its own. Groups/Plans cap their
   own height; the History section grows to fill and scrolls internally. */
.scroll { flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column; gap: 6px; }
.logout { padding: 9px; border: none; border-radius: 10px; background: rgba(0,0,0,.08); color: #3a3024; cursor: pointer; transition: var(--tap); }
@media (hover: hover) { .logout:hover { background: rgba(0,0,0,.14); transform: translateY(-1px); } }
.logout:active { transform: translateY(0) scale(.97); }
.slide-enter-active, .slide-leave-active { transition: transform .42s cubic-bezier(.5,.05,.1,1); }
.slide-enter-from, .slide-leave-to { transform: translateX(-104%); }
@media (max-width: 480px) { .panel { width: 100vw; border-radius: 0; } }
</style>
