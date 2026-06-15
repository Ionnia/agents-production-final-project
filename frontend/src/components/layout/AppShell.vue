<script setup lang="ts">
import DitheredBackground from '../background/DitheredBackground.vue'
import MenuButton from './MenuButton.vue'
import SidePanel from './SidePanel.vue'
import ToastHost from '../ui/ToastHost.vue'
import { ref } from 'vue'
import { useAuthStore } from '../../stores/auth'
const auth = useAuthStore()
const panelOpen = ref(false)
</script>

<template>
  <DitheredBackground />
  <MenuButton v-show="!panelOpen && auth.isAuthenticated" @toggle="panelOpen = !panelOpen" />
  <SidePanel v-if="auth.isAuthenticated" :open="panelOpen" @close="panelOpen = false" />
  <main class="pane"><slot /></main>
  <ToastHost />
</template>

<style scoped>
.pane { position: fixed; inset: 0; z-index: 1; }
</style>
