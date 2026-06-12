<script setup lang="ts">
import AgentChat from './components/AgentChat/AgentChat.vue'
import PageBackground, {
  type BackgroundScene,
} from './components/PageBackground/PageBackground.vue'

const scenes: BackgroundScene[] = [
  "city",
  "desert",
  "island",
  "mountain",
  "northernLights",
];
const background = scenes[Math.floor(Math.random() * scenes.length)]!;
</script>

<template>
  <PageBackground :background="background" />
  <AgentChat />
</template>
