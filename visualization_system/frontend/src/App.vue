<template>
  <div id="app">
    <el-container>
      <el-aside width="240px" class="sidebar">
        <div class="logo-container">
          <div class="logo">
            <span class="logo-icon">📊</span>
            <h2 class="logo-text">微博仿真</h2>
          </div>
          <p class="logo-subtitle">可视化系统</p>
        </div>
        
        <el-menu
          :default-active="currentRoute"
          class="sidebar-menu"
          router
        >
          <template v-for="section in navSections" :key="section.label || 'main'">
            <div v-if="section.label" class="menu-group-label">{{ section.label }}</div>
            <el-menu-item
              v-for="item in section.items"
              :key="item.path"
              :index="item.path"
            >
              <span class="menu-icon">{{ item.icon }}</span>
              <span>{{ item.title }}</span>
            </el-menu-item>
          </template>
        </el-menu>
        
        <div class="sidebar-footer">
          <p class="footer-text">Powered by OASIS</p>
          <p class="footer-version">v1.0.0</p>
        </div>
      </el-aside>
      
      <el-container>
        <el-header height="60px" class="top-header">
          <div class="header-content">
            <h3 class="page-title">{{ pageTitle }}</h3>
            <div class="header-actions">
              <el-button class="btn-animate" type="primary" size="small">
                <span>🔄</span>
                刷新数据
              </el-button>
            </div>
          </div>
        </el-header>
        
        <el-main class="main-content">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { navSections, pageTitles } from '@/router'

const route = useRoute()

const currentRoute = computed(() => route.path)
const pageTitle = computed(() => pageTitles[route.path] || '微博仿真可视化系统')
</script>

<style scoped>
#app {
  height: 100vh;
  overflow: hidden;
}

.el-container {
  height: 100%;
}

.sidebar {
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.logo-container {
  padding: var(--spacing-xl) var(--spacing-lg);
  text-align: center;
  border-bottom: 1px solid var(--border-color);
}

.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
}

.logo-icon {
  font-size: 32px;
}

.logo-text {
  font-size: 20px;
  font-weight: 700;
  background: var(--primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0;
}

.logo-subtitle {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: var(--spacing-xs);
  letter-spacing: 2px;
}

.sidebar-menu {
  flex: 1;
  border: none;
  background: transparent;
  padding: var(--spacing-md) 0;
}

.sidebar-menu .el-menu-item {
  height: 48px;
  line-height: 48px;
  margin: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  transition: all 0.3s ease;
}

.sidebar-menu .el-menu-item:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.sidebar-menu .el-menu-item.is-active {
  background: var(--primary-gradient);
  color: white;
  box-shadow: var(--shadow-glow);
}

.menu-icon {
  font-size: 18px;
  margin-right: var(--spacing-sm);
}

.menu-group-label {
  padding: var(--spacing-md) var(--spacing-lg) var(--spacing-xs);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1px;
  color: var(--text-muted);
  text-transform: uppercase;
}

.sidebar-footer {
  padding: var(--spacing-lg);
  border-top: 1px solid var(--border-color);
  text-align: center;
}

.footer-text {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
}

.footer-version {
  font-size: 10px;
  color: var(--text-muted);
  opacity: 0.6;
}

.top-header {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  padding: 0;
}

.header-content {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--spacing-xl);
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.main-content {
  background: var(--bg-color);
  padding: var(--spacing-xl);
  overflow-y: auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
