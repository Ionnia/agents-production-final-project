import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../components/auth/AuthView.vue'), meta: { public: true } },
    { path: '/', name: 'chat', component: () => import('../components/chat/ChatView.vue') },
    { path: '/c/:sessionId', name: 'session', component: () => import('../components/chat/ChatView.vue'), props: true },
    { path: '/plans/:planId', name: 'plan', component: () => import('../components/plan/PlanView.vue'), props: true },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const { useAuthStore } = await import('../stores/auth')
  const auth = useAuthStore()
  if (!auth.ready) await auth.restore()
  if (!to.meta.public && !auth.isAuthenticated) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.name === 'login' && auth.isAuthenticated) return { path: '/' }
  return true
})

export default router
