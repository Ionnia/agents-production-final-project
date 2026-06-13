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

/** Accent color the chat input picks up per scene (caret + focus glow). */
const sceneAccents: Record<BackgroundScene, { accent: string; glow: string }> =
  {
    city: { accent: "#c0563a", glow: "rgba(192, 86, 58, 0.4)" },
    desert: { accent: "#e8920c", glow: "rgba(232, 146, 12, 0.42)" },
    island: { accent: "#2278cf", glow: "rgba(34, 120, 207, 0.4)" },
    mountain: { accent: "#5f432c", glow: "rgba(95, 67, 44, 0.45)" },
    northernLights: { accent: "#1fc3a4", glow: "rgba(31, 195, 164, 0.45)" },
  };

const sceneThemeVars = {
  "--scene-accent": sceneAccents[background].accent,
  "--scene-glow": sceneAccents[background].glow,
};
</script>

<template>
  <PageBackground :background="background" />
  <AgentChat :style="sceneThemeVars" />
</template>
