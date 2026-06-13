<script setup lang="ts">
import desertBackground from "../../assets/images/desert_background.webp";
import desertBalloon from "../../assets/images/desert_balloon_cutout.webp";
import desertCactus from "../../assets/images/desert_cactus_cutout.webp";
import desertSign from "../../assets/images/desert_sign_cutout.webp";
import desertVan from "../../assets/images/desert_van_cutout.webp";
import CutoutLayer from "./CutoutLayer.vue";
import { useSceneParallax } from "./useSceneParallax";

const { skyLayerStyle, midLayerStyle, foregroundLayerStyle } =
  useSceneParallax();
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
      <CutoutLayer :src="desertBalloon" alt="" :x="78" :y="34" width="18vw" />
    </div>

    <div class="page-background__layer" :style="midLayerStyle">
      <CutoutLayer :src="desertCactus" alt="" :x="85" :y="79" width="15vw" />
      <CutoutLayer :src="desertCactus" alt="" :x="6" :y="63" width="3.5vw" />
      <CutoutLayer :src="desertSign" alt="" :x="38" :y="65" width="7vw" />
      <CutoutLayer :src="desertCactus" alt="" :x="53" :y="63" width="3.5vw" />
    </div>

    <div class="page-background__layer" :style="foregroundLayerStyle">
      <CutoutLayer :src="desertVan" alt="" :x="22" :y="102" width="34vw" />
    </div>
  </div>
</template>
