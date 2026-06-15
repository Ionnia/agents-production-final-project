import { it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MarkdownText from './MarkdownText.vue'

it('renders bold, lists and newlines from markdown', () => {
  const w = mount(MarkdownText, {
    props: { text: 'Детали:\n\n1. Дата.\n2. Бюджет **на человека**.' },
  })
  expect(w.find('ol').exists()).toBe(true)
  expect(w.findAll('li')).toHaveLength(2)
  expect(w.find('strong').text()).toBe('на человека')
  // plain text still present for text-based assertions
  expect(w.text()).toContain('Дата.')
})

it('converts a single newline to a line break (pre-wrap parity)', () => {
  const w = mount(MarkdownText, { props: { text: 'строка 1\nстрока 2' } })
  expect(w.find('br').exists()).toBe(true)
})

it('sanitizes dangerous HTML / scripts', () => {
  const w = mount(MarkdownText, { props: { text: '<img src=x onerror=alert(1)>\n\n<script>alert(2)<\/script> ok' } })
  expect(w.html()).not.toContain('onerror')
  expect(w.html()).not.toContain('<script')
  expect(w.text()).toContain('ok')
})
