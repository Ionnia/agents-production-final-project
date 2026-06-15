<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useGroupsStore } from "../../stores/groups";
import CollapsibleSection from "./CollapsibleSection.vue";
import EmptyState from "../ui/EmptyState.vue";
const groups = useGroupsStore();
const props = defineProps<{ filter: string }>();
// Most recent first; the section caps the visible window to ~3 rows and scrolls.
const filtered = computed(() =>
  groups.list
    .filter((g) => g.name.toLowerCase().includes(props.filter.toLowerCase()))
    .slice()
    .sort((a, b) => b.created_at.localeCompare(a.created_at)),
);
onMounted(() => {
  if (!groups.list.length) groups.loadList();
});
</script>
<template>
  <CollapsibleSection title="Группы">
    <EmptyState v-if="!filtered.length" title="Нет групп" />
    <div v-for="g in filtered" :key="g.id" class="item">
      <span class="lbl">{{ g.name }}</span> <small>{{ g.member_count }}</small>
    </div>
  </CollapsibleSection>
</template>
<style scoped>
.item {
  display: flex;
  gap: 9px;
  padding: 8px 10px;
  border-radius: 9px;
  color: #3a3024;
  font-size: 14px;
  transition: var(--tap);
}
@media (hover: hover) {
  .item:hover {
    background: rgba(255, 255, 255, 0.4);
  }
}
.item:active {
  background: rgba(255, 255, 255, 0.5);
  transform: scale(0.99);
}
.lbl {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
small {
  color: #8a7f70;
}
</style>
