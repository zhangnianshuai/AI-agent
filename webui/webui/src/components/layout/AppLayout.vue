<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TopBar from './TopBar.vue'
import CompanySidebar from './CompanySidebar.vue'
import ProfileSidebar from './ProfileSidebar.vue'
import SqlAgentChat from '@/components/SqlAgentChat.vue'

const route = useRoute()

const layout = computed(() => route.meta.layout || 'topbar')
</script>

<template>
  <!-- Full-page: login, register -->
  <div v-if="layout === 'none'" class="full-page">
    <router-view v-slot="{ Component }">
      <transition name="page-fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>

  <!-- Top bar + body -->
  <el-container v-else class="app-root" direction="vertical">
    <!-- Top navigation bar -->
    <TopBar />

    <!-- Body: sidebar(s) + content -->
    <el-container class="app-body">
      <!-- Company context sidebar -->
      <CompanySidebar v-if="layout === 'company'" />

      <!-- Profile context sidebar -->
      <ProfileSidebar v-if="layout === 'profile'" />

      <!-- Main content area -->
      <el-main
        class="app-main"
        :class="{
          'has-sidebar': layout === 'company' || layout === 'profile',
          'is-dashboard': layout === 'dashboard',
        }"
      >
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>

    <!-- SQL Agent floating chat (admin) -->
    <SqlAgentChat v-if="layout !== 'none'" />
  </el-container>
</template>

<style scoped>
/* ── Full-page (auth) ── */
.full-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #FFFFFF;
}

/* ── App root ── */
.app-root {
  height: 100vh;
  overflow: hidden;
}

/* ── Body: fill remaining height after top bar ── */
.app-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ── Main content ── */
.app-main {
  background: #FFFFFF;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0;
  flex: 1;
  min-height: 0;
}

/* Dashboard — full-width, no centering */
.app-main.is-dashboard {
  padding: 0;
}

.app-main.is-dashboard > :deep(*) {
  max-width: none;
  margin: 0;
}

/* Generic topbar pages — centered */
.app-main:not(.is-dashboard):not(.has-sidebar) {
  padding: 20px 24px;
}

.app-main:not(.is-dashboard):not(.has-sidebar) > :deep(*) {
  max-width: 1000px;
  margin: 0 auto;
  width: 100%;
}

/* Sidebar pages get standard padding */
.app-main.has-sidebar {
  padding: var(--space-6) var(--space-8);
}

/* Sidebar pages don't need extra centering */
.app-main.has-sidebar > :deep(*) {
  max-width: none;
  margin: 0;
}

@media (max-width: 1024px) {
  .app-main.has-sidebar {
    padding: var(--space-5);
  }
}

@media (max-width: 768px) {
  .app-main.has-sidebar {
    padding: var(--space-4);
  }
}
</style>
