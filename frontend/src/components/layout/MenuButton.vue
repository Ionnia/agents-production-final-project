<script setup lang="ts">defineEmits<{ toggle: [] }>()</script>
<template><button type="button" @click="$emit('toggle')" /></template>
