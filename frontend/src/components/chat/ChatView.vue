<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ChatComposer from './ChatComposer.vue'
import MessageList from './MessageList.vue'
import { useChatStore } from '../../stores/chat'
import { useSessionsStore } from '../../stores/sessions'
import { useToasts } from '../../composables/useToasts'

const props = defineProps<{ sessionId?: string }>()
const chat = useChatStore(); const sessions = useSessionsStore(); const router = useRouter(); const { push } = useToasts()
const draft = ref('')
const started = computed(() => chat.messages.length > 0)
// Only animate the composer from centre → bottom when the user sends the first
// message from the hero state. A direct load (/c/:id) hydrates messages already
// "started", so it renders at the bottom immediately instead of sliding down.
const animate = ref(false)
// Hero only belongs on the home route. On a session route (/c/:id) it must never
// show — not even briefly while messages hydrate — or it flashes over the bubbles.
const heroVisible = computed(() => !started.value && !props.sessionId)

onMounted(async () => {
  if (props.sessionId) { await sessions.loadDetail(props.sessionId); if (sessions.current) chat.hydrate(sessions.current.id, sessions.current.messages) }
  else chat.reset()
})
watch(() => props.sessionId, async (id) => {
  // Skip when the route just caught up to the session we already have live in the
  // store (e.g. router.replace after the first message) — re-hydrating from the
  // server here would clobber live state such as the pending clarifying question.
  if (id === chat.sessionId) return
  if (id) { await sessions.loadDetail(id); if (sessions.current) chat.hydrate(sessions.current.id, sessions.current.messages) }
  else chat.reset()
})

async function onSubmit(text: string) {
  if (chat.running) return
  const wasNew = !props.sessionId
  if (!started.value) animate.value = true // hero → chat: slide the composer down
  try {
    await chat.send(text)
    if (chat.sessionId && wasNew) router.replace(`/c/${chat.sessionId}`)
    sessions.loadList() // refresh history so the new/updated chat appears in the side panel
  } catch {
    push({ kind: 'error', text: 'Не удалось получить ответ. Попробуйте ещё раз.' })
  }
}
async function onAnswer(optionIds: string[], freeform?: string) {
  if (chat.running || !chat.pendingQuestion) return
  await chat.answer(chat.pendingQuestion.id, optionIds, freeform)
  sessions.loadList()
}
</script>

<template>
  <div class="chat" :class="{ chatting: started }">
    <transition name="hero">
      <div v-if="heroVisible" class="hero">
        <h1>Куда отправимся?</h1>
        <p>Опишите поездку — соберу маршрут, отели и туры под вашу группу.</p>
      </div>
    </transition>

    <div v-if="started" class="thread">
      <MessageList :messages="chat.messages" :question="chat.pendingQuestion" :plan-status="chat.planStatus" :plan-id="chat.planId" :running="chat.running" @answer="onAnswer" />
    </div>

    <div class="composer-slot" :class="{ bottom: started, animate }">
      <ChatComposer v-model="draft" :busy="chat.running" @submit="onSubmit" />
    </div>
  </div>
</template>

<style scoped>
.chat { position: fixed; inset: 0; }
.hero { position: absolute; left: 0; right: 0; top: 31%; text-align: center; }
.hero h1 { font-size: 38px; font-weight: 600; letter-spacing: -.8px; margin: 0; color: #fff; text-shadow: 0 2px 4px rgba(0,0,0,.85), 0 4px 18px rgba(0,0,0,.7), 0 8px 40px rgba(0,0,0,.6); }
.hero p { position: relative; isolation: isolate; width: fit-content; max-width: 94vw; margin: 12px auto 0; color: #e7ddcf; text-shadow: 0 1px 4px rgba(0,0,0,.7); }
.hero p::before { content: ""; position: absolute; inset: -.5em -1em; z-index: -1; pointer-events: none; background: radial-gradient(ellipse at center, rgba(0,0,0,.55) 0%, rgba(0,0,0,.36) 50%, rgba(0,0,0,0) 78%); filter: blur(11px); }
.thread { position: absolute; left: 50%; transform: translateX(-50%); top: 78px; bottom: 110px; width: min(720px, 92%); }
.composer-slot { position: absolute; left: 50%; transform: translateX(-50%); top: 48%; display: flex; justify-content: center; width: 100%; }
/* Transition only when explicitly enabled (hero → first message); direct loads snap to the bottom. */
.composer-slot.animate { transition: top .6s cubic-bezier(.55,.06,.12,1); }
.composer-slot.bottom { top: calc(100% - 96px); }
.hero-enter-active, .hero-leave-active { transition: opacity .35s, transform .35s; }
.hero-enter-from, .hero-leave-to { opacity: 0; transform: translateY(-14px); }
@media (max-width: 600px) { .hero h1 { font-size: 28px; } .thread { width: 94%; } }
</style>
