<script setup lang="ts">
import islandBackground from "../../assets/images/island_background.webp";
import islandBoat from "../../assets/images/island_boat_cutout.webp";
import islandPalm from "../../assets/images/island_palm_cutout.webp";
import islandHammock from "../../assets/images/island_hammock_cutout.webp";
import islandTraveler from "../../assets/images/island_man_cutout.webp";
import CutoutLayer from "./CutoutLayer.vue";
import { useSceneParallax } from "./useSceneParallax";

const { skyLayerStyle, midLayerStyle, foregroundLayerStyle } =
  useSceneParallax();
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
      <CutoutLayer :src="islandBoat" alt="" :x="80" :y="45" width="18vw" />
    </div>

    <div class="page-background__layer" :style="midLayerStyle">
      <CutoutLayer :src="islandPalm" alt="" :x="12" :y="85" width="30vw" />
    </div>

    <div class="page-background__layer" :style="foregroundLayerStyle">
      <CutoutLayer :src="islandHammock" alt="" :x="88" :y="96" width="24vw" />
      <CutoutLayer :src="islandTraveler" alt="" :x="50" :y="100" width="20vw" />
    </div>
  </div>
</template>
