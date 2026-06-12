<script setup lang="ts">
import mountainsBackground from '../../assets/images/mountains_background.webp'
import mountainEagleCutout from '../../assets/images/mountain_eagle_cutout.webp'
import mountainHikerCutout from '../../assets/images/mountain_hiker_cutout.webp'
import mountainPineCutout from '../../assets/images/mountain_pine_cutout.webp'
import mountainsFireplaceCutout from '../../assets/images/mountains_fireplace_cutout.webp'
import mountainsTentCutout from '../../assets/images/mountains_tent_cutout.webp'
import CutoutLayer from './CutoutLayer.vue'
import { useSceneParallax } from './useSceneParallax'

const { skyLayerStyle, midLayerStyle, foregroundLayerStyle } = useSceneParallax()
</script>

<template>
  <div>
    <img
      class="page-background__background-image"
      :src="mountainsBackground"
      alt=""
      decoding="async"
      draggable="false"
    />

    <div class="page-background__layer" :style="skyLayerStyle">
      <CutoutLayer
        :src="mountainEagleCutout"
        alt=""
        :x="70"
        :y="18"
        width="9vw"
      />
    </div>

    <div class="page-background__layer" :style="midLayerStyle">
      <CutoutLayer
        :src="mountainPineCutout"
        alt=""
        :x="10"
        :y="60"
        width="14vw"
      />
    </div>

    <div class="page-background__layer" :style="foregroundLayerStyle">
      <CutoutLayer
        :src="mountainsTentCutout"
        alt=""
        :x="65"
        :y="80"
        width="16vw"
      />
      <CutoutLayer
        :src="mountainsFireplaceCutout"
        alt=""
        :x="48"
        :y="86"
        width="9vw"
      />
      <CutoutLayer
        :src="mountainHikerCutout"
        alt=""
        :x="25"
        :y="82"
        width="9vw"
      />
    </div>
  </div>
</template>
