<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, useTemplateRef } from 'vue'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { MapPoint } from '../../api/types'

const props = defineProps<{ points: MapPoint[] }>()
const el = useTemplateRef<HTMLElement>('el')
let map: maplibregl.Map | null = null
let markers: maplibregl.Marker[] = []

// Free, no-API-key raster style (CARTO dark basemap).
const STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: { carto: { type: 'raster', tiles: ['https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap, © CARTO' } },
  layers: [{ id: 'carto', type: 'raster', source: 'carto' }],
}

function render() {
  if (!map) return
  markers.forEach(m => m.remove()); markers = []
  const pts = [...props.points].sort((a, b) => a.order - b.order)
  if (!pts.length) return
  for (const p of pts) {
    const e = document.createElement('div'); e.className = 'pin'; e.title = p.name
    markers.push(new maplibregl.Marker({ element: e }).setLngLat([p.lng, p.lat]).setPopup(new maplibregl.Popup({ offset: 16 }).setText(p.name)).addTo(map))
  }
  const line = { type: 'Feature' as const, geometry: { type: 'LineString' as const, coordinates: pts.map(p => [p.lng, p.lat]) }, properties: {} }
  const src = map.getSource('route') as maplibregl.GeoJSONSource | undefined
  if (src) src.setData(line as any)
  else { map.addSource('route', { type: 'geojson', data: line as any }); map.addLayer({ id: 'route', type: 'line', source: 'route', paint: { 'line-color': '#d97757', 'line-width': 3, 'line-dasharray': [2, 1.5] } }) }
  const b = new maplibregl.LngLatBounds(); pts.forEach(p => b.extend([p.lng, p.lat]))
  map.fitBounds(b, { padding: 70, maxZoom: 6, duration: 600 })
}

onMounted(() => {
  map = new maplibregl.Map({ container: el.value!, style: STYLE, center: [37.6, 55.75], zoom: 3, attributionControl: { compact: true } })
  map.on('load', render)
})
watch(() => props.points, render, { deep: true })
onBeforeUnmount(() => map?.remove())
</script>

<template><div ref="el" class="map" /></template>

<style scoped>
.map { width: 100%; height: 100%; border-radius: 16px; overflow: hidden; }
:global(.pin) { width: 16px; height: 16px; border-radius: 50% 50% 50% 0; background: var(--accent); transform: rotate(-45deg); box-shadow: 0 0 0 3px rgba(217,119,87,.35); }
</style>
