import type { SseEvent } from './types'

/** Parse a text/event-stream ReadableStream into typed {event,data} frames. */
export async function* parseEventStream(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let idx: number
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const frame = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      const ev = parseFrame(frame)
      if (ev) yield ev
    }
  }
}

function parseFrame(frame: string): SseEvent | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    // id:/retry: ignored here
  }
  if (!dataLines.length) return null
  try { return { event, data: JSON.parse(dataLines.join('\n')) } as SseEvent }
  catch { return null }
}

export interface StreamRunArgs { baseUrl: string; runId: string; ticket: string; signal?: AbortSignal; fetch?: typeof fetch }

/** Open the run stream and yield typed events until the connection closes. */
export async function* streamRun(args: StreamRunArgs): AsyncGenerator<SseEvent> {
  const f = args.fetch ?? globalThis.fetch.bind(globalThis)
  const res = await f(`${args.baseUrl}/chat/${args.runId}/stream?ticket=${encodeURIComponent(args.ticket)}`, {
    headers: { accept: 'text/event-stream' }, signal: args.signal,
  })
  if (!res.ok || !res.body) throw new Error(`stream failed: ${res.status}`)
  yield* parseEventStream(res.body)
}
