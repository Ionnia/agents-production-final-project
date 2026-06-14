<script setup lang="ts">defineProps<{ open: boolean }>(); defineEmits<{ close: [] }>()</script>
<template><aside v-show="open" /></template>
