<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { useToasts } from '../../composables/useToasts'
import { ApiClientError } from '../../api/client'

const auth = useAuthStore(); const router = useRouter(); const route = useRoute(); const { push } = useToasts()
const mode = ref<'login' | 'register'>('login')
const name = ref(''); const email = ref('demo@travel.app'); const password = ref('password'); const busy = ref(false)

async function submit() {
  busy.value = true
  try {
    if (mode.value === 'login') await auth.login(email.value, password.value)
    else await auth.register(name.value, email.value, password.value)
    router.replace((route.query.redirect as string) || '/')
  } catch (e) {
    push({ kind: 'error', text: e instanceof ApiClientError ? e.message : 'Не удалось войти' })
  } finally { busy.value = false }
}
</script>

<template>
  <div class="wrap">
    <form class="card glass" @submit.prevent="submit">
      <h1>{{ mode === 'login' ? 'С возвращением' : 'Создать аккаунт' }}</h1>
      <input v-if="mode === 'register'" v-model="name" class="f" placeholder="Имя" required />
      <input v-model="email" class="f" type="email" placeholder="Email" required />
      <input v-model="password" class="f" type="password" placeholder="Пароль" minlength="8" required />
      <button class="submit" :disabled="busy">{{ busy ? '…' : (mode === 'login' ? 'Войти' : 'Зарегистрироваться') }}</button>
      <p class="alt">
        {{ mode === 'login' ? 'Нет аккаунта?' : 'Уже есть аккаунт?' }}
        <button type="button" class="link" @click="mode = mode === 'login' ? 'register' : 'login'">{{ mode === 'login' ? 'Регистрация' : 'Вход' }}</button>
      </p>
    </form>
  </div>
</template>

<style scoped>
.wrap { position: fixed; inset: 0; display: grid; place-items: center; z-index: 1; }
.card { width: min(380px, 92%); padding: 28px; border-radius: 24px / 18px; display: flex; flex-direction: column; gap: 12px; }
h1 { margin: 0 0 6px; font-size: 24px; color: #1c150f; }
.f { padding: 12px 14px; border: none; border-radius: 12px; background: rgba(255,255,255,.45); color: var(--ink); font: inherit; }
.f::placeholder { color: var(--ink-soft); }
.submit { margin-top: 4px; padding: 12px; border: none; border-radius: 12px; background: var(--accent); color: #fff; font-weight: 600; cursor: pointer; }
.submit:disabled { opacity: .6; }
.alt { font-size: 13px; color: var(--ink-soft); text-align: center; margin: 4px 0 0; }
.alt .link { padding: 0; border: none; background: none; font: inherit; color: var(--accent-press); font-weight: 600; cursor: pointer; }
</style>
