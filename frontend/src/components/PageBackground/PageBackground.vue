<script lang="ts">
import { defineAsyncComponent, defineComponent, h, type Component } from 'vue'

export type BackgroundScene = 'city' | 'desert' | 'island' | 'mountain' | 'northernLights'

const SceneLoadError = defineComponent({
  name: 'PageBackgroundSceneLoadError',
  setup() {
    return () => h('div', { class: 'page-background__scene page-background__fallback' })
  },
})

function createSceneLoader(loader: () => Promise<{ default: Component }>) {
  return defineAsyncComponent({
    loader,
    errorComponent: SceneLoadError,
    onError(_error, retry, fail, attempts) {
      if (attempts <= 3) {
        retry()
      }
      else {
        fail()
      }
    },
  })
}

export const sceneComponents = {
  city: createSceneLoader(() => import('./PageBackgroundCity.vue')),
  desert: createSceneLoader(() => import('./PageBackgroundDesert.vue')),
  island: createSceneLoader(() => import('./PageBackgroundIsland.vue')),
  mountain: createSceneLoader(() => import('./PageBackgroundMountain.vue')),
  northernLights: createSceneLoader(() => import('./PageBackgroundNorthernLights.vue')),
} as const satisfies Record<BackgroundScene, ReturnType<typeof defineAsyncComponent>>
</script>

<script setup lang="ts">
import { computed } from 'vue'
import './page-background.css'

const props = defineProps<{
  background: BackgroundScene
}>()

const sceneComponent = computed(() => sceneComponents[props.background] ?? sceneComponents.city)
</script>

<template>
  <div class="page-background" aria-hidden="true">
    <Suspense>
      <component
        :is="sceneComponent"
        :key="background"
        class="page-background__scene"
      />
      <template #fallback>
        <div class="page-background__scene page-background__fallback" />
      </template>
    </Suspense>
  </div>
</template>
