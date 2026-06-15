import { it, expect } from 'vitest'
import { parseEventStream } from './sse'

function streamOf(text: string): ReadableStream<Uint8Array> {
  const enc = new TextEncoder()
  return new ReadableStream({ start(c) { c.enqueue(enc.encode(text)); c.close() } })
}

function streamChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder()
  return new ReadableStream({
    start(c) {
      for (const chunk of chunks) c.enqueue(enc.encode(chunk))
      c.close()
    },
  })
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

it('parses CRLF-delimited frames from the backend stream', async () => {
  const body = [
    'id: 1',
    'event: run_status',
    'data: {"run_id":"r1","status":"started"}',
    '',
    'id: 2',
    'event: clarifying_question',
    'data: {"run_id":"r1","question":{"id":"q1","text":"Уточните даты поездки","options":[],"allow_freeform":true}}',
    '',
    '',
  ].join('\r\n')
  const out: any[] = []
  for await (const ev of parseEventStream(streamOf(body))) out.push(ev)
  expect(out).toHaveLength(2)
  expect(out[1]).toEqual({
    event: 'clarifying_question',
    data: {
      run_id: 'r1',
      question: {
        id: 'q1',
        text: 'Уточните даты поездки',
        options: [],
        allow_freeform: true,
      },
    },
  })
})

it('does not split a CRLF line ending across chunks into an empty frame', async () => {
  const out: any[] = []
  for await (const ev of parseEventStream(streamChunks([
    'id: 1\r',
    '\nevent: run_status\r',
    '\ndata: {"run_id":"r1","status":"started"}\r',
    '\n\r',
    '\n',
  ]))) out.push(ev)
  expect(out).toEqual([{ event: 'run_status', data: { run_id: 'r1', status: 'started' } }])
})
