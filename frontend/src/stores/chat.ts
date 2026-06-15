import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, client } from '../api/endpoints'
import { streamRun } from '../api/sse'
import { useToasts } from '../composables/useToasts'
import type { Message, ClarifyingQuestion, PlanBuildStatus, ChatRequest, ChatAccepted } from '../api/types'

interface UiMessage extends Pick<Message, 'id' | 'role' | 'content'> { streaming?: boolean; created_at?: string }

export const useChatStore = defineStore('chat', () => {
  const sessionId = ref<string | null>(null)
  const messages = ref<UiMessage[]>([])
  const pendingQuestion = ref<ClarifyingQuestion | null>(null)
  const planStatus = ref<PlanBuildStatus | null>(null)
  const planId = ref<string | null>(null)
  const running = ref(false)
  let runDone: Promise<void> = Promise.resolve()
  // Tracks the in-flight run so a new run / reset can cancel it. The token guards
  // a stale stream loop from mutating the store after it has been superseded.
  let controller: AbortController | null = null
  let runToken = 0

  function cancelRun() { controller?.abort(); controller = null; runToken++; running.value = false }
  function reset() { cancelRun(); sessionId.value = null; messages.value = []; pendingQuestion.value = null; planStatus.value = null; planId.value = null }
  function hydrate(id: string, msgs: Message[]) {
    cancelRun()
    sessionId.value = id
    planStatus.value = null
    planId.value = null
    const last = msgs.at(-1)
    pendingQuestion.value = last?.question ?? null
    // The active (trailing) clarifying question renders as the question panel, not
    // also as a plain bubble — otherwise it shows up twice after a reload/navigation.
    const bubbles = pendingQuestion.value ? msgs.slice(0, -1) : msgs
    messages.value = bubbles.map(m => ({ id: m.id, role: m.role, content: m.content, created_at: m.created_at }))
  }

  // Push a message and return the array's reactive proxy so later mutations
  // (streaming deltas / final content) trigger re-renders.
  function pushMessage(m: UiMessage): UiMessage {
    messages.value.push(m)
    return messages.value[messages.value.length - 1]
  }

  // Demote a still-pending clarifying question to a plain assistant bubble (its
  // text) before the next run starts. The backend persists every clarifying
  // question as an assistant message, so hydrate() renders earlier (non-trailing)
  // questions as bubbles; without this, an answered/superseded question would
  // vanish from the live thread the moment the next run begins and only reappear
  // after a manual reload. We do NOT also emit the question text as a `message`
  // (the agent's prose and the question text are identical), so this stays a
  // single bubble — no duplicate.
  function flushPendingQuestion() {
    const q = pendingQuestion.value
    if (!q) return
    pushMessage({ id: q.id, role: 'assistant', content: q.text, created_at: new Date().toISOString() })
    pendingQuestion.value = null
  }

  async function startRun(req: ChatRequest): Promise<ChatAccepted> {
    // Cancel any prior in-flight run so its stream can't keep mutating the store
    // (e.g. after a new send or a reset/new-chat).
    cancelRun()
    const token = ++runToken
    const ctrl = controller = new AbortController()
    running.value = true; pendingQuestion.value = null; planStatus.value = null; planId.value = null
    let acc: ChatAccepted
    try {
      acc = await api.chat(req)
    } catch (e) {
      if (token === runToken) running.value = false
      useToasts().push({ kind: 'error', text: 'Не удалось получить ответ. Попробуйте ещё раз.' })
      throw e
    }
    // Expose the session id immediately so the caller can update the URL before
    // the (potentially slow) agent run finishes; the stream below keeps filling
    // the same store reactively.
    sessionId.value = acc.session_id
    runDone = (async () => {
      let assistant: UiMessage | null = null
      let hasAssistantReply = false
      try {
        const { ticket } = await api.streamTicket(acc.run_id)
        for await (const ev of streamRun({ baseUrl: client.baseUrl, runId: acc.run_id, ticket, signal: ctrl.signal })) {
          // A newer run or a reset has superseded this one — stop mutating shared state.
          if (token !== runToken) return
          if (ev.event === 'message_delta') {
            hasAssistantReply = true
            if (planStatus.value !== 'ready') planStatus.value = null
            if (!assistant) assistant = pushMessage({ id: ev.data.message_id, role: 'assistant', content: '', streaming: true, created_at: new Date().toISOString() })
            assistant.content += ev.data.delta
          } else if (ev.event === 'message') {
            hasAssistantReply = true
            if (planStatus.value !== 'ready') planStatus.value = null
            // The live backend may emit a single final `message` with no preceding
            // `message_delta` chunks, so create the bubble here if streaming never started.
            if (!assistant) assistant = pushMessage({ id: ev.data.message.id, role: 'assistant', content: '' })
            assistant.content = ev.data.message.content; assistant.streaming = false
            assistant.created_at = ev.data.message.created_at
            if (ev.data.message.plan_ref) planId.value = ev.data.message.plan_ref.plan_id
          } else if (ev.event === 'clarifying_question') { pendingQuestion.value = ev.data.question }
          else if (ev.event === 'plan_status') {
            if (ev.data.status !== 'error' || !hasAssistantReply) planStatus.value = ev.data.status
            else if (planStatus.value !== 'ready') planStatus.value = null
            if (ev.data.status !== 'error' || !hasAssistantReply) planId.value = ev.data.plan_id
            else planId.value = null
          }
          else if (ev.event === 'error') {
            // A well-formed `error` frame reports a failed run; surface it instead of
            // letting the stream close silently with no assistant text.
            if (!hasAssistantReply) planStatus.value = 'error'
            useToasts().push({ kind: 'error', text: ev.data.error.message || 'Ошибка агента' })
          }
          // No early break on a terminal `run_status`: the server closes the stream
          // once the run is terminal and drained, so we keep reading to avoid dropping
          // a `message` that arrives after `run_status: completed` (otherwise the reply
          // only appears after a manual page reload).
        }
      } catch {
        // An aborted run is intentional cancellation, not a failure — stay quiet.
        if (token === runToken) {
          planStatus.value = 'error'
          useToasts().push({ kind: 'error', text: 'Не удалось получить ответ. Попробуйте ещё раз.' })
        }
      } finally {
        if (token === runToken) { running.value = false; controller = null }
        if (assistant) assistant.streaming = false
      }
    })()
    return acc
  }

  async function send(text: string): Promise<ChatAccepted> {
    flushPendingQuestion()
    messages.value.push({ id: `u-${Date.now()}`, role: 'user', content: text, created_at: new Date().toISOString() })
    return startRun({ message: text, session_id: sessionId.value ?? undefined })
  }
  async function answer(questionId: string, optionIds: string[], freeform?: string): Promise<ChatAccepted> {
    // Read the label off the active question first, then demote it to a bubble so
    // the answered question stays in the live thread above the user's reply.
    const label = pendingQuestion.value?.options.filter(o => optionIds.includes(o.id)).map(o => o.label).join(', ') || freeform || ''
    flushPendingQuestion()
    if (label) messages.value.push({ id: `u-${Date.now()}`, role: 'user', content: label, created_at: new Date().toISOString() })
    return startRun({ session_id: sessionId.value ?? undefined, in_reply_to_question_id: questionId, selected_option_ids: optionIds, freeform })
  }
  const waitForIdle = () => runDone
  return { sessionId, messages, pendingQuestion, planStatus, planId, running, reset, hydrate, send, answer, waitForIdle }
})
