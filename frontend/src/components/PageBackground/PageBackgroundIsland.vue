<script setup lang="ts">
import islandBackground from '../../assets/images/island_background.webp'
import islandBoat from '../../assets/images/island_boat_cutout.webp'
import islandPalm from '../../assets/images/island_palm_cutout.webp'
import islandHammock from '../../assets/images/island_hammock_cutout.webp'
import islandTraveler from '../../assets/images/island_man_cutout.webp'
import CutoutLayer from './CutoutLayer.vue'
import { useSceneParallax } from './useSceneParallax'

const { skyLayerStyle, midLayerStyle, foregroundLayerStyle } = useSceneParallax()
</script>

<template>
  <div>
    <img
      class="page-background__background-image"
      :src="islandBackground"
      alt=""
      draggable="false"
      decoding="async"
    />

    <div class="page-background__layer" :style="skyLayerStyle">
      <CutoutLayer
        :src="islandBoat"
        alt=""
        :x="60"
        :y="30"
        width="12vw"
      />
    </div>

    <div class="page-background__layer" :style="midLayerStyle">
      <CutoutLayer
        :src="islandPalm"
        alt=""
        :x="12"
        :y="55"
        width="16vw"
      />
    </div>

    <div class="page-background__layer" :style="foregroundLayerStyle">
      <CutoutLayer
        :src="islandHammock"
        alt=""
        :x="75"
        :y="70"
        width="18vw"
      />
      <CutoutLayer
        :src="islandTraveler"
        alt=""
        :x="40"
        :y="78"
        width="9vw"
      />
    </div>
  </div>
</template>
