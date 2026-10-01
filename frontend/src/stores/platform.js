// ARL-Next/frontend/src/stores/platform.js
/**
 * 漏洞平台聚合状态管理（Pinia）
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getPlatforms,
  getProjects,
  getProjectDetail,
  fetchProjects as apiFetchProjects,
  deleteProject as apiDeleteProject,
  scanProject as apiScanProject,
  submitProjectVulns as apiSubmitProjectVulns,
  submitVuln as apiSubmitVuln,
  batchSubmitVulns as apiBatchSubmitVulns,
  getSubmitRecords,
  getSchedules,
  upsertSchedule,
  toggleSchedule,
  removeSchedule,
  getTargets,
} from '@/api/platform'


export const usePlatformStore = defineStore('platform', () => {

  // ═══════════════════════════════════════════════════
  // State
  // ═══════════════════════════════════════════════════

  const platforms = ref([])
  const projects = ref([])
  const projectDetail = ref(null)
  const targets = ref([])
  const submitRecords = ref([])
  const schedules = ref([])

  const projectTotal = ref(0)
  const targetTotal = ref(0)
  const recordTotal = ref(0)

  const loading = ref({
    platforms: false,
    projects: false,
    projectDetail: false,
    targets: false,
    submitRecords: false,
    schedules: false,
  })


  // ═══════════════════════════════════════════════════
  // Getters
  // ═══════════════════════════════════════════════════

  const enabledPlatforms = computed(() =>
    platforms.value.filter(p => p.enabled !== false)
  )

  const projectStats = computed(() => {
    const stats = {
      total: projectTotal.value,
      byPlatform: {},
      byStatus: { active: 0, expired: 0 },
    }
    for (const p of projects.value) {
      stats.byPlatform[p.platform] =
        (stats.byPlatform[p.platform] || 0) + 1
      if (stats.byStatus[p.status] !== undefined) {
        stats.byStatus[p.status] += 1
      }
    }
    return stats
  })


  // ═══════════════════════════════════════════════════
  // Actions
  // ═══════════════════════════════════════════════════

  // ── 平台 ──────────────────────────────────────
  async function loadPlatforms() {
    loading.value.platforms = true
    try {
      const data = await getPlatforms()
      console.log('data', data);
      
      platforms.value = data?.items || []
      return platforms.value
    } finally {
      loading.value.platforms = false
    }
  }

  // ── 项目列表 ──────────────────────────────────
  async function loadProjects(params = {}) {
    loading.value.projects = true
    try {
      const data = await getProjects({
        page: params.page || 1,
        size: params.page_size || params.size || 20,
        platform: params.platform || undefined,
        status: params.status || undefined,
        keyword: params.keyword || undefined,
      })
      projects.value = data?.items || []
      projectTotal.value = data?.total || 0
      return data
    } finally {
      loading.value.projects = false
    }
  }

  // ── 项目详情 ──────────────────────────────────
  async function loadProjectDetail(fingerprint) {
    loading.value.projectDetail = true
    try {
      const data = await getProjectDetail(fingerprint)
      projectDetail.value = data?.data || data || null
      return projectDetail.value
    } finally {
      loading.value.projectDetail = false
    }
  }

  // ── 触发抓取 ──────────────────────────────────
  async function triggerFetch(payload = {}) {
    return apiFetchProjects(payload)
  }

  // ── 删除项目 ──────────────────────────────────
  async function removeProject(fingerprint) {
    return apiDeleteProject(fingerprint)
  }

  // ── 下发扫描 ──────────────────────────────────
  async function triggerScan(fingerprint, payload = {}) {
    return apiScanProject(fingerprint, payload)
  }

  // ── 提交项目漏洞 ──────────────────────────────
  async function submitAllProjectVulns(fingerprint) {
    return apiSubmitProjectVulns(fingerprint)
  }

  // ── 目标列表 ──────────────────────────────────
  async function loadTargets(params = {}) {
    loading.value.targets = true
    try {
      const data = await getTargets({
        page: params.page || 1,
        size: params.page_size || params.size || 20,
        project_fingerprint:
          params.project_fingerprint || undefined,
        platform: params.platform || undefined,
        scanned: params.scanned,
      })
      targets.value = data?.items || []
      targetTotal.value = data?.total || 0
      return data
    } finally {
      loading.value.targets = false
    }
  }

  // ── 提交记录 ──────────────────────────────────
  async function loadSubmitRecords(params = {}) {
    loading.value.submitRecords = true
    try {
      const data = await getSubmitRecords({
        page: params.page || 1,
        size: params.page_size || params.size || 20,
        platform: params.platform || undefined,
        status: params.status || undefined,
        project_fingerprint:
          params.project_fingerprint || undefined,
      })
      submitRecords.value = data?.items || []
      recordTotal.value = data?.total || 0
      return data
    } finally {
      loading.value.submitRecords = false
    }
  }

  // ── 单个漏洞提交 ──────────────────────────────
  async function submitSingleVuln(vulnId, payload = {}) {
    return apiSubmitVuln(vulnId, payload)
  }

  // ── 批量提交 ──────────────────────────────────
  async function submitVulnsBatch(payload) {
    return apiBatchSubmitVulns(payload)
  }

  // ── 调度 ──────────────────────────────────────
  async function loadSchedules(params = {}) {
    loading.value.schedules = true
    try {
      const data = await getSchedules({
        page: params.page || 1,
        size: params.page_size || params.size || 20,
        project_fingerprint:
          params.project_fingerprint || undefined,
        profile: params.profile || undefined,
        enabled: params.enabled,
      })
      schedules.value = data?.items || []
      return data
    } finally {
      loading.value.schedules = false
    }
  }

  async function saveSchedule(payload) {
    return upsertSchedule(payload)
  }

  async function switchSchedule(id, enabled) {
    return toggleSchedule(id, enabled)
  }

  async function deleteSchedule(id) {
    return removeSchedule(id)
  }

  // ── 重置 ──────────────────────────────────────
  function $reset() {
    platforms.value = []
    projects.value = []
    projectDetail.value = null
    targets.value = []
    submitRecords.value = []
    schedules.value = []
    projectTotal.value = 0
    targetTotal.value = 0
    recordTotal.value = 0
    loading.value = {
      platforms: false,
      projects: false,
      projectDetail: false,
      targets: false,
      submitRecords: false,
      schedules: false,
    }
  }


  // ═══════════════════════════════════════════════════
  // 导出
  // ═══════════════════════════════════════════════════

  return {
    // state
    platforms,
    projects,
    projectDetail,
    targets,
    submitRecords,
    schedules,
    projectTotal,
    targetTotal,
    recordTotal,
    loading,
    // getters
    enabledPlatforms,
    projectStats,
    // actions
    loadPlatforms,
    loadProjects,
    loadProjectDetail,
    triggerFetch,
    removeProject,
    triggerScan,
    submitAllProjectVulns,
    loadTargets,
    loadSubmitRecords,
    submitSingleVuln,
    submitVulnsBatch,
    loadSchedules,
    saveSchedule,
    switchSchedule,
    deleteSchedule,
    $reset,
  }
})