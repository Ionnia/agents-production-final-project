import { it, expect } from 'vitest'
import { parseEventStream } from './sse'

function streamOf(text: string): ReadableStream<Uint8Array> {
  const enc = new TextEncoder()
  return new ReadableStream({ start(c) { c.enqueue(enc.encode(text)); c.close() } })
}

it('parses named SSE frames into typed events', async () => {
  const body = [
    'id: 1', 'event: run_status', 'data: {"run_id":"r1","status":"started"}', '',
    'event: message_delta', 'data: {"run_id":"r1","message_id":"m1","delta":"Hi"}', '',
    '',
  ].join('\n')
  const out: any[] = []
  for await (const ev of parseEventStream(streamOf(body))) out.push(ev)
  expect(out[0]).toEqual({ event: 'run_status', data: { run_id: 'r1', status: 'started' } })
  expect(out[1].data.delta).toBe('Hi')
})
