import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import router from './router'

async function bootstrap() {
  // Mocks run by default in dev, but an explicit `VITE_USE_MOCKS=false` opts out
  // (e.g. to run the dev server against the real backend via VITE_API_BASE).
  const useMocks =
    import.meta.env.VITE_USE_MOCKS !== 'false' &&
    (import.meta.env.DEV || import.meta.env.VITE_USE_MOCKS === 'true')
  if (useMocks) {
    const { worker } = await import('./mocks/browser')
    await worker.start({ onUnhandledRequest: 'bypass' })
  }
  createApp(App).use(createPinia()).use(router).mount('#app')
}
bootstrap()
