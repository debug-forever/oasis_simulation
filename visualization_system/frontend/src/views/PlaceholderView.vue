<template>
  <div class="placeholder-view">
    <div class="card empty-content">
      <div class="icon">{{ icon }}</div>
      <h2>{{ title }}</h2>
      <p>{{ description }}</p>
      <p class="hint">此视图将展示{{ featureDescription }}</p>
    </div>
  </div>
</template>

<script setup>
import { defineProps } from 'vue'

const props = defineProps({
  icon: { type: String, default: '🚧' },
  title: { type: String, default: '视图开发中' },
  description: { type: String, default: '该功能正在开发中，敬请期待' },
  featureDescription: { type: String, default: '更多精彩内容' }
})
</script>

<style scoped>
.placeholder-view {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-content {
  text-align: center;
  max-width: 500px;
  padding: var(--spacing-xl) * 2;
}

.icon {
  font-size: 80px;
  margin-bottom: var(--spacing-lg);
}

h2 {
  font-size: 24px;
  color: var(--text-primary);
  margin-bottom: var(--spacing-md);
}

p {
  color: var(--text-secondary);
  margin-bottom: var(--spacing-sm);
}

.hint {
  color: var(--text-muted);
  font-size: 14px;
}
</style>
