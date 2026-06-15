import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, client } from '../api/endpoints'
import { streamRun } from '../api/sse'
import { useToasts } from '../composables/useToasts'
import type { Message, ClarifyingQuestion, PlanBuildStatus, ChatRequest } from '../api/types'

interface UiMessage extends Pick<Message, 'id' | 'role' | 'content'> { streaming?: boolean; created_at?: string }

export const useChatStore = defineStore('chat', () => {
  const sessionId = ref<string | null>(null)
  const messages = ref<UiMessage[]>([])
  const pendingQuestion = ref<ClarifyingQuestion | null>(null)
  const planStatus = ref<PlanBuildStatus | null>(null)
  const planId = ref<string | null>(null)
  const running = ref(false)
  let runDone: Promise<void> = Promise.resolve()

  function reset() { sessionId.value = null; messages.value = []; pendingQuestion.value = null; planStatus.value = null; planId.value = null }
  function hydrate(id: string, msgs: Message[]) { sessionId.value = id; messages.value = msgs.map(m => ({ id: m.id, role: m.role, content: m.content, created_at: m.created_at })); pendingQuestion.value = msgs.at(-1)?.question ?? null }

  async function startRun(req: ChatRequest) {
    running.value = true; pendingQuestion.value = null
    runDone = (async () => {
      let assistant: UiMessage | null = null
      try {
        const acc = await api.chat(req); sessionId.value = acc.session_id
        const { ticket } = await api.streamTicket(acc.run_id)
        for await (const ev of streamRun({ baseUrl: client.baseUrl, runId: acc.run_id, ticket })) {
          if (ev.event === 'message_delta') {
            if (!assistant) { assistant = { id: ev.data.message_id, role: 'assistant', content: '', streaming: true, created_at: new Date().toISOString() }; messages.value.push(assistant) }
            assistant.content += ev.data.delta
          } else if (ev.event === 'message') {
            // The live backend emits a single final `message` with no preceding
            // `message_delta` chunks, so create the bubble here if streaming never started.
            if (!assistant) { assistant = { id: ev.data.message.id, role: 'assistant', content: '' }; messages.value.push(assistant) }
            assistant.content = ev.data.message.content; assistant.streaming = false
            assistant.created_at = ev.data.message.created_at
            if (ev.data.message.plan_ref) planId.value = ev.data.message.plan_ref.plan_id
          } else if (ev.event === 'clarifying_question') { pendingQuestion.value = ev.data.question }
          else if (ev.event === 'plan_status') { planStatus.value = ev.data.status; planId.value = ev.data.plan_id }
          else if (ev.event === 'run_status' && (ev.data.status === 'completed' || ev.data.status === 'error' || ev.data.status === 'cancelled')) break
        }
      } catch {
        planStatus.value = 'error'
        useToasts().push({ kind: 'error', text: 'Не удалось получить ответ. Попробуйте ещё раз.' })
      } finally {
        running.value = false
        if (assistant) assistant.streaming = false
      }
    })()
    return runDone
  }

  async function send(text: string) {
    messages.value.push({ id: `u-${Date.now()}`, role: 'user', content: text, created_at: new Date().toISOString() })
    return startRun({ message: text, session_id: sessionId.value ?? undefined })
  }
  async function answer(questionId: string, optionIds: string[], freeform?: string) {
    const label = pendingQuestion.value?.options.filter(o => optionIds.includes(o.id)).map(o => o.label).join(', ') || freeform || ''
    if (label) messages.value.push({ id: `u-${Date.now()}`, role: 'user', content: label, created_at: new Date().toISOString() })
    return startRun({ session_id: sessionId.value ?? undefined, in_reply_to_question_id: questionId, selected_option_ids: optionIds, freeform })
  }
  const waitForIdle = () => runDone
  return { sessionId, messages, pendingQuestion, planStatus, planId, running, reset, hydrate, send, answer, waitForIdle }
})
