<script setup lang="ts">
import backgroundImg from "../../assets/images/northern_lights_background.webp";
import hutImg from "../../assets/images/northern_lights_hut_cutout.webp";
import pineImg from "../../assets/images/northern_lights_pine_cutout.webp";
import manImg from "../../assets/images/northern_lights_man_cutout.webp";
import huskyImg from "../../assets/images/northern_lights_husky_cutout.webp";
import CutoutLayer from "./CutoutLayer.vue";
import { useSceneParallax } from "./useSceneParallax";

const { midLayerStyle, foregroundLayerStyle } = useSceneParallax();
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

    <div class="page-background__layer" :style="midLayerStyle">
      <CutoutLayer
        :src="hutImg"
        alt=""
        :x="88"
        :y="83"
        width="30vw"
        wiggle-origin="14% 9%"
      />
      <CutoutLayer
        :src="pineImg"
        alt=""
        :x="10"
        :y="78"
        width="24vw"
        wiggle-origin="82% 11%"
      />
    </div>

    <div class="page-background__layer" :style="foregroundLayerStyle">
      <CutoutLayer
        :src="manImg"
        alt=""
        :x="40"
        :y="85"
        width="12vw"
        wiggle-origin="18% 8%"
      />
      <CutoutLayer
        :src="huskyImg"
        alt=""
        :x="88"
        :y="82"
        width="8vw"
        wiggle-origin="78% 12%"
      />
    </div>
  </div>
</template>
