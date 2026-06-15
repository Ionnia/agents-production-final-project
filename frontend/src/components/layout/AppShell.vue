<script setup lang="ts">
import DitheredBackground from '../background/DitheredBackground.vue'
import MenuButton from './MenuButton.vue'
import SidePanel from './SidePanel.vue'
import ToastHost from '../ui/ToastHost.vue'
import { ref } from 'vue'
import { useAuthStore } from '../../stores/auth'
import logoUrl from '../../assets/logo.png'
const auth = useAuthStore()
const panelOpen = ref(false)
</script>

<template>
  <DitheredBackground />
  <MenuButton v-show="!panelOpen && auth.isAuthenticated" @toggle="panelOpen = !panelOpen" />
  <img class="logo" :src="logoUrl" alt="КудаЕдем" />
  <SidePanel v-if="auth.isAuthenticated" :open="panelOpen" @close="panelOpen = false" />
  <main class="pane"><slot /></main>
  <ToastHost />
</template>

<style scoped>
.pane { position: fixed; inset: 0; z-index: 1; }
/* Wordmark top-right. Rendered white (the source is dark) with a soft shadow so it
   stays legible over both light and dark background scenes, matching the hero text. */
.logo { position: fixed; top: 22px; right: 22px; z-index: 30; height: 28px; width: auto; pointer-events: none; user-select: none;
  filter: brightness(0) invert(1) drop-shadow(0 2px 5px rgba(0, 0, 0, .6)); }
@media (max-width: 480px) { .logo { height: 22px; top: 20px; right: 16px; } }
</style>
