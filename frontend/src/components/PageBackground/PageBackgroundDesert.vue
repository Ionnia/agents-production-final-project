<script setup lang="ts">
import desertBackground from '../../assets/images/desert_background.webp'
import desertBalloon from '../../assets/images/desert_balloon_cutout.webp'
import desertCactus from '../../assets/images/desert_cactus_cutout.webp'
import desertSign from '../../assets/images/desert_sign_cutout.webp'
import desertVan from '../../assets/images/desert_van_cutout.webp'
import CutoutLayer from './CutoutLayer.vue'
import { useSceneParallax } from './useSceneParallax'

const { skyLayerStyle, midLayerStyle, foregroundLayerStyle } = useSceneParallax()
</script>

<template>
  <div>
    <img
      class="page-background__background-image"
      :src="desertBackground"
      alt=""
      decoding="async"
      draggable="false"
    />

    <div class="page-background__layer" :style="skyLayerStyle">
      <CutoutLayer
        :src="desertBalloon"
        alt=""
        :x="78"
        :y="20"
        width="12vw"
      />
    </div>

    <div class="page-background__layer" :style="midLayerStyle">
      <CutoutLayer
        :src="desertCactus"
        alt=""
        :x="85"
        :y="62"
        width="10vw"
      />
      <CutoutLayer
        :src="desertSign"
        alt=""
        :x="35"
        :y="65"
        width="7vw"
      />
    </div>

    <div class="page-background__layer" :style="foregroundLayerStyle">
      <CutoutLayer
        :src="desertVan"
        alt=""
        :x="50"
        :y="82"
        width="21vw"
      />
    </div>
  </div>
</template>
