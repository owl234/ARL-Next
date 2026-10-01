// ARL-Next/frontend/src/api/platform.js
/**
 * 漏洞平台聚合 API 封装
 * 复用 @/utils/request 通用请求
 */

import request from '@/utils/request'

const BASE = '/api/platform'


// ═══════════════════════════════════════════════════════════
// 平台
// ═══════════════════════════════════════════════════════════

export function getPlatforms() {
  return request({
    url: `${BASE}/platforms/`,
    method: 'get',
  })
}


// ═══════════════════════════════════════════════════════════
// 项目
// ═══════════════════════════════════════════════════════════

/**
 * 项目列表（分页）
 * @param {Object} params - { page, size, platform, status, keyword }
 */
export function getProjects(params) {
  return request({
    url: `${BASE}/projects/`,
    method: 'get',
    params,
  })
}

/**
 * 项目详情（含目标、漏洞）
 * @param {String} fingerprint - 项目指纹
 */
export function getProjectDetail(fingerprint) {
  return request({
    url: `${BASE}/projects/${fingerprint}/`,
    method: 'get',
  })
}

/**
 * 触发抓取
 * @param {Object} data - { platform }（不传则全平台）
 */
export function fetchProjects(data) {
  return request({
    url: `${BASE}/projects/`,
    method: 'post',
    data,
  })
}

/**
 * 删除项目
 */
export function deleteProject(fingerprint) {
  return request({
    url: `${BASE}/projects/${fingerprint}/`,
    method: 'delete',
  })
}

/**
 * 下发扫描
 * @param {String} fingerprint
 * @param {Object} data - { profile }
 */
export function scanProject(fingerprint, data) {
  return request({
    url: `${BASE}/projects/${fingerprint}/scan/`,
    method: 'post',
    data,
  })
}

/**
 * 提交项目所有漏洞
 */
export function submitProjectVulns(fingerprint) {
  return request({
    url: `${BASE}/projects/${fingerprint}/submit_vulns/`,
    method: 'post',
  })
}


// ═══════════════════════════════════════════════════════════
// 目标
// ═══════════════════════════════════════════════════════════

export function getTargets(params) {
  return request({
    url: `${BASE}/targets/`,
    method: 'get',
    params,
  })
}


// ═══════════════════════════════════════════════════════════
// 漏洞提交
// ═══════════════════════════════════════════════════════════

/**
 * 提交单个漏洞
 * @param {String} vulnId
 * @param {Object} data - { platform, force }
 */
export function submitVuln(vulnId, data) {
  return request({
    url: `${BASE}/vulns/${vulnId}/submit/`,
    method: 'post',
    data,
  })
}

/**
 * 批量提交漏洞
 * @param {Object} data - { vuln_ids, platform }
 */
export function batchSubmitVulns(data) {
  return request({
    url: `${BASE}/vulns/batch_submit/`,
    method: 'post',
    data,
  })
}


// ═══════════════════════════════════════════════════════════
// 提交记录
// ═══════════════════════════════════════════════════════════

export function getSubmitRecords(params) {
  return request({
    url: `${BASE}/submit_records/`,
    method: 'get',
    params,
  })
}


// ═══════════════════════════════════════════════════════════
// 调度
// ═══════════════════════════════════════════════════════════

export function getSchedules(params) {
  return request({
    url: `${BASE}/schedules/`,
    method: 'get',
    params,
  })
}

/**
 * 创建/更新调度
 * @param {Object} data - {
 *   project_fingerprint, profile, cron_expression, enabled
 * }
 */
export function upsertSchedule(data) {
  return request({
    url: `${BASE}/schedules/`,
    method: 'post',
    data,
  })
}

export function toggleSchedule(id, enabled) {
  return request({
    url: `${BASE}/schedules/${id}/`,
    method: 'put',
    data: { enabled },
  })
}

export function removeSchedule(id) {
  return request({
    url: `${BASE}/schedules/${id}/`,
    method: 'delete',
  })
}