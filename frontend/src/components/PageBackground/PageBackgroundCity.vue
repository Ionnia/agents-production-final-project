<script setup lang="ts">
import backgroundImg from '../../assets/images/city_background.webp'
import lanternImg from '../../assets/images/city_lantern_cutout.webp'
import pigeonsImg from '../../assets/images/city_pigeons_cutout.webp'
import cafeImg from '../../assets/images/city_restaurant_table_cutout.webp'
import vespaImg from '../../assets/images/city_vespa_cutout.webp'
import touristImg from '../../assets/images/city_woman_cutout.webp'
import CutoutLayer from './CutoutLayer.vue'
import { useSceneParallax } from './useSceneParallax'

const { skyLayerStyle, midLayerStyle, foregroundLayerStyle } = useSceneParallax()
</script>

<template>
  <div>
    <img
      class="page-background__background-image"
      :src="backgroundImg"
      alt=""
      decoding="async"
      draggable="false"
    />

    <div class="page-background__layer" :style="skyLayerStyle">
      <CutoutLayer
        :src="pigeonsImg"
        alt=""
        :x="55"
        :y="15"
        width="11vw"
        wiggle-origin="18% 82%"
      />
    </div>

    <div class="page-background__layer" :style="midLayerStyle">
      <CutoutLayer
        :src="lanternImg"
        alt=""
        :x="88"
        :y="55"
        width="7vw"
        wiggle-origin="22% 8%"
      />
    </div>

    <div class="page-background__layer" :style="foregroundLayerStyle">
      <CutoutLayer
        :src="cafeImg"
        alt=""
        :x="70"
        :y="75"
        width="18vw"
        wiggle-origin="28% 12%"
      />
      <CutoutLayer
        :src="touristImg"
        alt=""
        :x="35"
        :y="80"
        width="9vw"
        wiggle-origin="32% 10%"
      />
      <CutoutLayer
        :src="vespaImg"
        alt=""
        :x="15"
        :y="83"
        width="14vw"
        wiggle-origin="78% 18%"
      />
    </div>
  </div>
</template>
