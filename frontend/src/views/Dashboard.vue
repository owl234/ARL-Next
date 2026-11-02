<template>
  <div class="dashboard-container" :class="{ 'page-wide-text': pageLocale !== 'zh-CN' }">
    <!-- Row 1: 4 组安全态势感知核心大卡 (Security Posture Priority Cards) -->
    <div class="dashboard-section section-posture">
      <a-row :gutter="[14, 14]" class="stat-row">
        <!-- 卡片 1: 总资产暴露面 -->
        <a-col :xs="24" :sm="12" :md="12" :lg="6">
          <a-card class="modern-stat-card posture-card clickable-card card-asset" :bordered="false" @click="router.push('/asset-search')">
            <div class="card-ambient-glow primary"></div>
            <a-skeleton :loading="initialLoading" active :paragraph="{ rows: 2 }" :title="false">
              <div class="card-inner">
                <div class="card-top-header">
                  <span class="card-title-text">{{ pageText('pages.totalWebsiteAssets') }}</span>
                  <div class="stat-icon-box primary">
                    <DatabaseOutlined />
                  </div>
                </div>
                <div class="card-metric-num">
                  {{ Number(stats.total_assets || 0).toLocaleString() }}
                </div>
                <div class="card-footer-ribbon">
                  <div class="status-indicator">
                    <span class="pulse-beacon green"></span>
                    <span class="status-text">{{ pageText('pages.websiteMonitoringActive') }}</span>
                  </div>
                  <div class="trend-badge positive">
                    {{ pageText('pages.todayNewWebsitesCount', { count: stats.today_new_assets || 0 }) }}
                  </div>
                </div>
              </div>
            </a-skeleton>
          </a-card>
        </a-col>

        <!-- 卡片 2: 今日侦察动向 -->
        <a-col :xs="24" :sm="12" :md="12" :lg="6">
          <a-card class="modern-stat-card posture-card card-recon" :bordered="false">
            <div class="card-ambient-glow success"></div>
            <a-skeleton :loading="initialLoading" active :paragraph="{ rows: 2 }" :title="false">
              <div class="card-inner">
                <div class="card-top-header">
                  <span class="card-title-text">{{ pageText('pages.todaySScanningActivity') }}</span>
                  <div class="stat-icon-box success">
                    <SyncOutlined />
                  </div>
                </div>
                <div class="dual-metric-wrap">
                  <div class="metric-cell clickable-cell" @click="router.push({ path: '/taskList', query: { tab: 'task' } })">
                    <div class="cell-val success-val">{{ stats.today_tasks || 0 }}</div>
                    <div class="cell-lbl">{{ pageText('pages.newScanningTasks') }}</div>
                  </div>
                  <div class="metric-divider"></div>
                  <div class="metric-cell clickable-cell" @click="router.push('/asset-search')">
                    <div class="cell-val primary-val">{{ stats.today_new_assets || 0 }}</div>
                    <div class="cell-lbl">{{ pageText('pages.newWebsitesDiscovered') }}</div>
                  </div>
                </div>
                <div class="card-footer-ribbon">
                  <div class="status-indicator">
                    <span class="beacon-dot"></span>
                    <span class="status-text">{{ pageText('pages.activeAssetDiscovery') }}</span>
                  </div>
                  <span class="footer-link-hint" @click="router.push({ path: '/taskList', query: { tab: 'task' } })">{{ pageText('pages.viewTaskActivity') }}</span>
                </div>
              </div>
            </a-skeleton>
          </a-card>
        </a-col>

        <!-- 卡片 3: 漏洞风险全景矩阵 -->
        <a-col :xs="24" :sm="12" :md="12" :lg="6">
          <a-card class="modern-stat-card posture-card card-vuln" :bordered="false">
            <div class="card-ambient-glow danger"></div>
            <a-skeleton :loading="initialLoading" active :paragraph="{ rows: 2 }" :title="false">
              <div class="card-inner">
                <div class="card-top-header">
                  <span class="card-title-text">{{ pageText('pages.vulnerabilityOverview') }}</span>
                  <div class="stat-icon-box danger">
                    <AlertOutlined />
                  </div>
                </div>
                <div class="vuln-matrix-header">
                  <div class="vuln-total-num">
                    {{ totalVulnCount }}
                    <span class="vuln-total-unit">{{ pageText('pages.findingsAllEnginesCombinedWithoutDeduplication') }}</span>
                  </div>
                  <a-tag v-if="criticalVulnCount > 0" color="error" class="critical-alert-tag">
                    <template #icon><span class="pulse-beacon red"></span></template>
                    {{ pageText('pages.highCriticalCount', { count: criticalVulnCount }) }}
                  </a-tag>
                  <a-tag v-else color="success" class="critical-alert-tag">
                    {{ pageText('pages.nucleiNoCriticalOrHighFindings') }}
                  </a-tag>
                </div>
                <div class="vuln-pill-row">
                  <a-tooltip :title="pageText('pages.criticalVulnerabilitiesNuclei')">
                    <div 
                      class="vuln-pill critical" 
                      :class="{ empty: !(stats.vuln?.nuclei_critical) }"
                      @click="router.push({ path: '/asset-search', query: { tab: 'nuclei_result', vuln_severity: 'critical' } })"
                    >
                      <span class="pill-name">{{ pageText('assets.critical') }}</span>
                      <span class="pill-cnt">{{ stats.vuln?.nuclei_critical || 0 }}</span>
                    </div>
                  </a-tooltip>

                  <a-tooltip :title="pageText('pages.highVulnerabilitiesNuclei')">
                    <div 
                      class="vuln-pill high" 
                      :class="{ empty: !(stats.vuln?.nuclei_high) }"
                      @click="router.push({ path: '/asset-search', query: { tab: 'nuclei_result', vuln_severity: 'high' } })"
                    >
                      <span class="pill-name">{{ pageText('assets.high') }}</span>
                      <span class="pill-cnt">{{ stats.vuln?.nuclei_high || 0 }}</span>
                    </div>
                  </a-tooltip>

                  <a-tooltip :title="pageText('pages.mediumVulnerabilitiesNuclei')">
                    <div 
                      class="vuln-pill medium" 
                      :class="{ empty: !(stats.vuln?.nuclei_medium) }"
                      @click="router.push({ path: '/asset-search', query: { tab: 'nuclei_result', vuln_severity: 'medium' } })"
                    >
                      <span class="pill-name">{{ pageText('assets.medium') }}</span>
                      <span class="pill-cnt">{{ stats.vuln?.nuclei_medium || 0 }}</span>
                    </div>
                  </a-tooltip>

                  <a-tooltip :title="pageText('pages.lowVulnerabilitiesNuclei')">
                    <div 
                      class="vuln-pill low" 
                      :class="{ empty: !(stats.vuln?.nuclei_low) }"
                      @click="router.push({ path: '/asset-search', query: { tab: 'nuclei_result', vuln_severity: 'low' } })"
                    >
                      <span class="pill-name">{{ pageText('assets.low') }}</span>
                      <span class="pill-cnt">{{ stats.vuln?.nuclei_low || 0 }}</span>
                    </div>
                  </a-tooltip>

                  <a-tooltip :title="pageText('pages.arlBuiltInVulnerabilityChecks')">
                    <div 
                      class="vuln-pill arl" 
                      :class="{ empty: !(stats.vuln?.arl_total) }"
                      @click="router.push({ path: '/asset-search', query: { tab: 'vuln' } })"
                    >
                      <span class="pill-name">ARL</span>
                      <span class="pill-cnt">{{ stats.vuln?.arl_total || 0 }}</span>
                    </div>
                  </a-tooltip>
                </div>
              </div>
            </a-skeleton>
          </a-card>
        </a-col>

        <!-- 卡片 4: GitHub 威胁与情报 (今日) -->
        <a-col :xs="24" :sm="12" :md="12" :lg="6">
          <a-card class="modern-stat-card posture-card clickable-card card-github" :bordered="false" @click="router.push('/GitHubTasks/GitHubTasksList')">
            <div class="card-ambient-glow dark"></div>
            <a-skeleton :loading="initialLoading" active :paragraph="{ rows: 2 }" :title="false">
              <div class="card-inner">
                <div class="card-top-header">
                  <span class="card-title-text">{{ pageText('pages.githubThreatsAndIntelligenceToday') }}</span>
                  <div class="stat-icon-box dark">
                    <GithubOutlined />
                  </div>
                </div>
                <div class="dual-metric-wrap">
                  <div class="metric-cell clickable-cell" @click.stop="router.push('/GitHubTasks/GitHubTasksList?tab=scheduler')">
                    <div class="cell-val danger-val">
                      {{ sysInfo.github_today?.leaks || 0 }}
                      <span v-if="(sysInfo.github_today?.leaks || 0) > 0" class="pulse-beacon red inline-pulse"></span>
                    </div>
                    <div class="cell-lbl">{{ pageText('pages.codeLeaksToday') }}</div>
                  </div>
                  <div class="metric-divider"></div>
                  <a-tooltip placement="bottom">
                    <template #title>
                      <div class="intel-tooltip-box">
                        <div class="tooltip-title">{{ pageText('pages.newIntelligenceToday') }}</div>
                        <div>{{ pageText('pages.newCves') }}{{ sysInfo.github_today_breakdown?.cves || 0 }}</div>
                        <div>{{ pageText('pages.trackedResearchers') }}{{ sysInfo.github_today_breakdown?.hackers || 0 }}</div>
                        <div>{{ pageText('pages.otherIntelligence') }}{{ sysInfo.github_today_breakdown?.general || 0 }}</div>
                        <div class="tooltip-sep"></div>
                        <div class="tooltip-title">{{ pageText('pages.allTimeTotals') }}</div>
                        <div>{{ pageText('pages.cves') }}{{ sysInfo.github_totals?.cves || 0 }}</div>
                        <div>{{ pageText('pages.monitoredTools') }}{{ sysInfo.github_totals?.tools || 0 }}</div>
                        <div>{{ pageText('pages.trackedResearchers') }}{{ sysInfo.github_totals?.hackers || 0 }}</div>
                      </div>
                    </template>
                    <div class="metric-cell clickable-cell" @click.stop="router.push('/GitHubTasks/GitHubTasksList?tab=cve_history')">
                      <div class="cell-val warning-val">{{ sysInfo.github_today?.intel || 0 }}</div>
                      <div class="cell-lbl">{{ pageText('pages.threatIntelligenceToday') }}</div>
                    </div>
                  </a-tooltip>
                </div>
                <div class="card-footer-ribbon">
                  <div class="status-indicator">
                    <span class="beacon-dot"></span>
                    <span class="status-text">{{ pageText('pages.monitorTaskCount', { count: stats.github_monitors || 0 }) }}</span>
                  </div>
                  <span class="footer-link-hint" @click="router.push('/GitHubTasks/GitHubTasksList')">{{ pageText('pages.intelligenceDashboard') }}</span>
                </div>
              </div>
            </a-skeleton>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- Row 2: 紧凑型系统算力与调度健康度胶囊条 (Compact Health Ribbon) -->
    <div class="dashboard-section section-health-ribbon">
      <div class="health-ribbon-bar">
        <a-skeleton :loading="initialLoading" active :paragraph="{ rows: 1 }" :title="false">
          <div class="ribbon-items-container">
            <!-- CPU 指标 -->
            <div class="ribbon-item">
              <span class="ribbon-icon cpu-color"><DashboardOutlined /></span>
              <span class="ribbon-name">CPU</span>
              <span class="ribbon-val" :class="{ 'text-danger': sysInfo.cpu_percent > 80 }">
                {{ sysInfo.cpu_percent }}%
              </span>
              <div class="ribbon-progress-track">
                <div 
                  class="ribbon-progress-bar" 
                  :style="{ 
                    width: sysInfo.cpu_percent + '%', 
                    background: sysInfo.cpu_percent > 80 ? '#ff4d4f' : 'var(--arl-theme-color)' 
                  }"
                ></div>
              </div>
            </div>

            <div class="ribbon-divider"></div>

            <!-- 内存指标 -->
            <a-tooltip placement="bottom">
              <template #title>
                <div style="font-size: 12px; line-height: 1.6;">
                  <div>{{ pageText('pages.hostPhysicalMemory') }}{{ sysInfo.mem_used_gb }} / {{ sysInfo.mem_total_gb }} {{ pageText('pages.gbAvailable') }} {{ sysInfo.mem_available_gb }} GB）</div>
                  <div>{{ pageText('pages.swapUsage') }} {{ sysInfo.swap_percent }}{{ pageText('pages.total') }} {{ sysInfo.swap_total_gb }} GB）</div>
                  <div v-if="sysInfo.mem_alert === 'critical'" class="page-error-note">{{ pageText('pages.hostMemoryUsageIsVeryHighReviewTheNumber') }}</div>
                  <div v-else-if="sysInfo.mem_alert === 'warning'" class="page-warning-note">{{ pageText('pages.hostMemoryUsageIsElevatedMonitorOverallResourceUsage') }}</div>
                </div>
              </template>
              <div class="ribbon-item cursor-help">
                <span class="ribbon-icon mem-color"><DatabaseOutlined /></span>
                <span class="ribbon-name">{{ pageText('pages.memory') }}</span>
                <span class="ribbon-val" :class="{ 'text-danger': sysInfo.mem_alert === 'critical', 'text-warning': sysInfo.mem_alert === 'warning' }">
                  {{ sysInfo.mem_percent }}%
                </span>
                <span class="ribbon-subval">({{ sysInfo.mem_used_gb }}/{{ sysInfo.mem_total_gb }}G)</span>
                <div class="ribbon-progress-track">
                  <div 
                    class="ribbon-progress-bar" 
                    :style="{ 
                      width: sysInfo.mem_percent + '%', 
                      background: sysInfo.mem_alert === 'critical' ? '#ff4d4f' : (sysInfo.mem_alert === 'warning' ? '#faad14' : 'var(--arl-theme-color)') 
                    }"
                  ></div>
                </div>
                <a-tag v-if="sysInfo.mem_alert === 'critical'" color="red" class="ribbon-alert-tag">{{ pageText('pages.criticalWarning') }}</a-tag>
                <a-tag v-else-if="sysInfo.mem_alert === 'warning'" color="orange" class="ribbon-alert-tag">{{ pageText('pages.elevated') }}</a-tag>
              </div>
            </a-tooltip>

            <div class="ribbon-divider"></div>

            <!-- 磁盘指标 -->
            <div class="ribbon-item">
              <span class="ribbon-icon disk-color"><HddOutlined /></span>
              <span class="ribbon-name">{{ pageText('pages.disk') }}</span>
              <span class="ribbon-val" :class="{ 'text-danger': sysInfo.disk_percent > 90 }">
                {{ sysInfo.disk_percent }}%
              </span>
              <div class="ribbon-progress-track">
                <div 
                  class="ribbon-progress-bar" 
                  :style="{ 
                    width: sysInfo.disk_percent + '%', 
                    background: sysInfo.disk_percent > 90 ? '#ff4d4f' : '#52c41a' 
                  }"
                ></div>
              </div>
            </div>

            <div class="ribbon-divider"></div>

            <!-- 扫描调度流水线 (Celery) -->
            <div class="ribbon-item cursor-pointer ribbon-tasks-item" @click="handleTaskRibbonClick">
              <span class="ribbon-icon celery-color"><ThunderboltOutlined /></span>
              <span class="ribbon-name">{{ pageText('pages.scanScheduling') }}</span>
              <div class="ribbon-task-badges">
                <span class="task-badge running" @click.stop="handleRunningBadgeClick">
                  <span v-if="(sysInfo.tasks?.running || 0) > 0" class="pulse-beacon green inline-pulse"></span>
                  <span class="num">{{ sysInfo.tasks?.running || 0 }}</span> {{ pageText('pages.running') }}
                </span>
                <span class="task-badge waiting" @click.stop="handleWaitingBadgeClick">
                  <span class="num">{{ sysInfo.tasks?.waiting || 0 }}</span> {{ pageText('pages.queued') }}
                </span>
              </div>
              <RightOutlined class="ribbon-arrow" />
            </div>
          </div>
        </a-skeleton>
      </div>
    </div>

    <!-- Row 3: 主体态势（近7天/多维趋势图 310px + 高信噪比智能过滤安全动态流 310px） -->
    <div class="dashboard-section section-main">
      <a-row :gutter="[14, 14]" class="main-row">
        <!-- 左侧：近7天站点与风险演进趋势 -->
        <a-col :xs="24" :lg="16" class="main-col">
          <a-card class="main-card trend-card" :bordered="false">
            <template #title>
              <div class="card-header-flex">
                <div class="card-header-title">
                  <LineChartOutlined class="card-header-icon" />
                  <span>{{ pageText('pages.websiteExposureAndRiskTrends') }}</span>
                </div>
                <div class="trend-controls">
                  <div class="metric-filter-group">
                    <span 
                      class="filter-pill" 
                      :class="{ active: trendFilter === 'all' }"
                      @click="setTrendFilter('all')"
                    >{{ pageText('pages.combined') }}</span>
                    <span 
                      class="filter-pill" 
                      :class="{ active: trendFilter === 'assets' }"
                      @click="setTrendFilter('assets')"
                    >{{ pageText('pages.websitesOnly') }}</span>
                    <span 
                      class="filter-pill" 
                      :class="{ active: trendFilter === 'risks' }"
                      @click="setTrendFilter('risks')"
                    >{{ pageText('pages.risksAndIntelligenceOnly') }}</span>
                  </div>
                  <div class="range-tag">{{ pageText('tasks.last7Days') }}</div>
                </div>
              </div>
            </template>
            <div class="card-body-wrapper">
              <a-skeleton v-if="initialLoading" active :paragraph="{ rows: 6 }" style="padding: 12px;" />
              <div v-show="!initialLoading" ref="chartRef" class="echarts-box"></div>
            </div>
          </a-card>
        </a-col>

        <!-- 右侧：高信噪比安全动态流 (智能去噪与日志分类) -->
        <a-col :xs="24" :lg="8" class="main-col">
          <a-card class="main-card log-card" :bordered="false">
            <template #title>
              <div class="card-header-flex">
                <div class="card-header-title">
                  <ClockCircleOutlined class="card-header-icon" />
                  <span>{{ pageText('pages.securityAndSchedulingActivity') }}</span>
                </div>
                <div class="log-filter-group">
                  <span 
                    class="log-tab-item" 
                    :class="{ active: logFilter === 'all' }"
                    @click="logFilter = 'all'"
                  >{{ pageText('pages.all') }}</span>
                  <span 
                    class="log-tab-item" 
                    :class="{ active: logFilter === 'warn' }"
                    @click="logFilter = 'warn'"
                  >{{ pageText('pages.warningsErrors') }}</span>
                  <span 
                    class="log-tab-item" 
                    :class="{ active: logFilter === 'task' }"
                    @click="logFilter = 'task'"
                  >{{ pageText('pages.taskActivity') }}</span>
                </div>
              </div>
            </template>
            <div class="card-body-wrapper">
              <a-skeleton v-if="initialLoading" active :paragraph="{ rows: 4 }" style="padding: 12px;" />
              <div v-else class="log-scroll-area">
                <div v-if="filteredGroupedLogs.length > 0" class="log-list-container">
                  <template v-for="(item, idx) in filteredGroupedLogs" :key="idx">
                    <!-- 心跳聚合折叠条 -->
                    <div 
                      v-if="item.isHeartbeatGroup" 
                      class="heartbeat-group-row"
                      @click="item.expanded = !item.expanded"
                    >
                      <div class="heartbeat-info">
                        <SyncOutlined class="heartbeat-spin" />
                        <span>{{ pageText('pages.schedulerHeartbeatsGrouped', { count: item.count }) }}</span>
                      </div>
                      <span class="heartbeat-toggle">
                        {{ item.expanded ? pageText('pages.collapse') : pageText('pages.expand') }}
                        <DownOutlined v-if="!item.expanded" style="font-size: 10px;" />
                        <UpOutlined v-else style="font-size: 10px;" />
                      </span>
                    </div>

                    <!-- 展开的心跳详情 -->
                    <div v-if="item.isHeartbeatGroup && item.expanded" class="heartbeat-expanded-box">
                      <div 
                        v-for="(subLog, subIdx) in item.items" 
                        :key="subIdx" 
                        class="log-stream-item heartbeat-sub-item"
                        @click="showLogDetail(subLog)"
                      >
                        <span class="log-tag info">{{ pageText('pages.schedulerHeartbeat') }}</span>
                        <span class="log-msg-preview">{{ subLog.message }}</span>
                        <span class="log-time">{{ subLog.create_time ? subLog.create_time.substring(11, 19) : '' }}</span>
                      </div>
                    </div>

                    <!-- 普通业务/告警动态条目 -->
                    <div 
                      v-if="!item.isHeartbeatGroup" 
                      class="log-stream-item"
                      :class="[getLogMeta(item).type, { 'has-alert': item.level === 'error' || item.level === 'warning' }]"
                      @click="showLogDetail(item)"
                    >
                      <div class="log-indicator-stripe" :class="getLogMeta(item).type"></div>
                      <div class="log-stream-body">
                        <div class="log-item-top">
                          <div class="log-tag-group">
                            <span class="log-type-tag" :class="getLogMeta(item).type">
                              <AlertOutlined v-if="getLogMeta(item).type === 'cve' || getLogMeta(item).type === 'error' || getLogMeta(item).type === 'warning'" class="log-tag-icon" />
                              <SyncOutlined v-else-if="getLogMeta(item).type === 'monitor'" class="log-tag-icon" />
                              <ClockCircleOutlined v-else class="log-tag-icon" />
                              {{ getLogMeta(item).tag }}
                            </span>
                            <span v-if="getLogMeta(item).isCve" class="cve-inline-pill">{{ getLogMeta(item).mainText }}</span>
                          </div>
                          <span class="log-item-time">{{ formatTime(item.create_time) }}</span>
                        </div>
                        <div class="log-item-msg">
                          <span v-if="!getLogMeta(item).isCve">{{ getLogMeta(item).desc || item.message }}</span>
                          <span v-else class="cve-msg-highlight">{{ pageText('pages.assetDiscoveryFoundAPotentialDisclosureThreatAndSaved') }}</span>
                        </div>
                      </div>
                    </div>
                  </template>
                </div>
                <div v-else class="empty-log-box">
                  <a-empty :description="pageText('pages.noActivityInThisCategory')" :image="simpleImage" />
                </div>
              </div>
            </div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- Row 4: 业务拓展行 (Web指纹TOP5 + 双引擎漏洞环形图 + 实时侦察流水线) -->
    <div class="dashboard-section section-widgets">
      <a-row :gutter="[14, 14]" class="widget-row">
        <!-- 模块 1: Web 指纹与组件 TOP 5 (占比与分类徽标) -->
        <a-col :xs="24" :lg="8" class="widget-col">
          <a-card class="widget-card" :bordered="false">
            <template #title>
              <div class="card-header-flex">
                <div class="card-header-title">
                  <TagsOutlined class="card-header-icon" />
                  <span>{{ pageText('pages.top5WebTechnologyFingerprints') }}</span>
                </div>
                <span class="widget-extra-link" @click="router.push('/fingerprint')">
                  {{ pageText('pages.fingerprintLibrary') }} <RightOutlined class="page-small-label" />
                </span>
              </div>
            </template>
            <div class="widget-body-wrapper">
              <a-skeleton v-if="initialLoading" active :paragraph="{ rows: 4 }" />
              <div v-else-if="widgetsData.top_fingerprints && widgetsData.top_fingerprints.length > 0" class="finger-list-container">
                <div 
                  v-for="(item, idx) in widgetsData.top_fingerprints" 
                  :key="idx" 
                  class="finger-rank-row"
                  @click="router.push({ path: '/asset-search', query: { tab: 'site', finger: item.name } })"
                  :title="pageText('pages.clickToFindWebsitesWithThisFingerprint')"
                >
                  <div class="finger-left-box">
                    <span class="rank-badge" :class="'rank-' + (idx + 1)">{{ idx + 1 }}</span>
                    <span class="finger-name" :title="item.name">{{ item.name }}</span>
                    <span class="finger-category-tag" :class="getFingerCategory(item.name).toLowerCase()">
                      {{ formatFingerCategory(getFingerCategory(item.name)) }}
                    </span>
                  </div>
                  <a-tooltip :title="pageText('pages.barLengthsAreRelativeToTheMostCommonFingerprint')">
                    <div class="finger-bar-wrap">
                      <div class="finger-progress-bar">
                        <div class="finger-progress-fill" :style="{ width: getFingerPercent(item.count) + '%' }"></div>
                      </div>
                    </div>
                  </a-tooltip>
                  <div class="finger-count-box">
                    <span class="finger-count-num">{{ item.count }}</span>
                    <span class="finger-pct-lbl">{{ getFingerRatio(item.count) }}</span>
                  </div>
                </div>
              </div>
              <div v-else class="empty-widget-box">
                <a-empty :description="pageText('pages.noAggregatedFingerprintData')" :image="simpleImage" />
              </div>
            </div>
          </a-card>
        </a-col>

        <!-- 模块 2: 漏洞严重级别分布 (双引擎发光环形图) -->
        <a-col :xs="24" :lg="8" class="widget-col">
          <a-card class="widget-card" :bordered="false">
            <template #title>
              <div class="card-header-flex">
                <div class="card-header-title">
                  <PieChartOutlined class="card-header-icon" />
                  <span>{{ pageText('pages.vulnerabilitySeverityDistribution') }}</span>
                </div>
                <div class="vuln-engine-switch">
                  <span 
                    class="engine-pill" 
                    :class="{ active: vulnEngineMode === 'all' }"
                    @click="setVulnEngineMode('all')"
                  >{{ pageText('pages.allLabel2') }}</span>
                  <span 
                    class="engine-pill" 
                    :class="{ active: vulnEngineMode === 'nuclei' }"
                    @click="setVulnEngineMode('nuclei')"
                  >Nuclei</span>
                  <span 
                    class="engine-pill" 
                    :class="{ active: vulnEngineMode === 'arl' }"
                    @click="setVulnEngineMode('arl')"
                  >ARL</span>
                </div>
              </div>
            </template>
            <div class="widget-body-wrapper">
              <a-skeleton v-if="initialLoading" active :paragraph="{ rows: 4 }" />
              <div v-show="!initialLoading" ref="vulnChartRef" class="echarts-widget-box"></div>
            </div>
          </a-card>
        </a-col>

        <!-- 模块 3: 实时侦察流水线 (呼吸状态灯与耗时指示) -->
        <a-col :xs="24" :lg="8" class="widget-col">
          <a-card class="widget-card" :bordered="false">
            <template #title>
              <div class="card-header-flex">
                <div class="card-header-title">
                  <ThunderboltOutlined class="card-header-icon" />
                  <span>{{ pageText('pages.liveDiscoveryPipeline') }}</span>
                </div>
                <span class="widget-extra-link" @click="router.push({ path: '/taskList', query: { tab: 'task' } })">
                  {{ pageText('pages.tasks') }} <RightOutlined class="page-small-label" />
                </span>
              </div>
            </template>
            <div class="widget-body-wrapper">
              <a-skeleton v-if="initialLoading" active :paragraph="{ rows: 4 }" />
              <div v-else-if="widgetsData.active_tasks && widgetsData.active_tasks.length > 0" class="task-stream-container">
                <div 
                  v-for="(task, idx) in widgetsData.active_tasks" 
                  :key="idx" 
                  class="task-card-item"
                  @click="router.push({ path: '/taskList', query: { tab: 'task' } })"
                >
                  <div class="task-card-top">
                    <div class="task-name-box">
                      <span class="task-type-badge" :class="task.type || 'scan'">
                        {{ task.type === 'ip' ? 'IP' : (task.type === 'domain' ? pageText('tasks.domains') : pageText('pages.scan')) }}
                      </span>
                      <span class="task-name" :title="task.name">{{ formatTaskTitle(task.name) }}</span>
                    </div>
                    <div class="task-status-pill" :class="task.status">
                      <span v-if="task.status === 'running'" class="pulse-beacon green inline-beacon"></span>
                      <SyncOutlined v-if="task.status === 'running'" spin class="status-icon" />
                      <ClockCircleOutlined v-else-if="task.status === 'waiting'" class="status-icon" />
                      <CheckCircleOutlined v-else class="status-icon" />
                      <span class="status-text">{{ getTaskStatusLabel(task.status) }}</span>
                    </div>
                  </div>
                  <div class="task-card-bottom">
                    <span class="task-target" :title="task.target">
                      <span class="target-lbl">{{ pageText('assets.target') }}</span> <code>{{ task.target }}</code>
                    </span>
                    <span class="task-time-wrap">
                      <ClockCircleOutlined style="font-size: 10px; margin-right: 4px; opacity: 0.7;" />
                      {{ task.start_time ? task.start_time.substring(5, 16) : '-' }}
                    </span>
                  </div>
                </div>
              </div>
              <div v-else class="empty-widget-box">
                <a-empty :description="pageText('pages.noActiveScanningTasks')" :image="simpleImage">
                  <a-button type="primary" size="small" @click="router.push({ path: '/taskList', query: { tab: 'task' } })">{{ pageText('pages.newDiscoveryTask') }}</a-button>
                </a-empty>
              </div>
            </div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 系统动态详情弹窗 -->
    <a-modal
      v-model:open="isLogModalVisible"
      :title="pageText('pages.systemActivityDetails')"
      :footer="null"
      width="600px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
    >
      <div v-if="currentLog" class="log-detail-content">
        <p><strong>{{ pageText('pages.level') }}</strong> <a-tag :color="getLogColor(currentLog.level)">{{ currentLog.level }}</a-tag></p>
        <p><strong>{{ pageText('pages.time') }}</strong> {{ currentLog.create_time }}</p>
        <p><strong>{{ pageText('pages.title') }}</strong> {{ currentLog.title || (currentLog.level === 'error' ? pageText('pages.systemError') : pageText('pages.notification')) }}</p>
        <div style="margin-top: 16px;">
          <strong>{{ pageText('pages.details') }}</strong>
          <div class="log-message-box">
            {{ currentLog.message }}
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
defineOptions({
  name: 'Dashboard'
});

import { ref, computed, reactive, onMounted, onUnmounted, onActivated, onDeactivated, nextTick, watch } from 'vue';
import { useRouter } from 'vue-router';
import { 
  DatabaseOutlined, 
  SyncOutlined, 
  AlertOutlined, 
  GithubOutlined,
  LineChartOutlined,
  ClockCircleOutlined,
  TagsOutlined,
  PieChartOutlined,
  ThunderboltOutlined,
  RightOutlined,
  CheckCircleOutlined,
  DashboardOutlined,
  HddOutlined,
  DownOutlined,
  UpOutlined
} from '@ant-design/icons-vue';
import { Empty } from 'ant-design-vue';
import * as echarts from 'echarts/core';
import { LineChart, BarChart, PieChart } from 'echarts/charts';
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  LineChart,
  BarChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  CanvasRenderer
]);
import request from '@/utils/request';
import { formatTaskStatus } from '@/constants/taskStatus';

const { t: pageText, locale: pageLocale } = useI18n({ useScope: 'global' });

const simpleImage = Empty.PRESENTED_IMAGE_SIMPLE;
const router = useRouter();

// 首次加载骨架屏标记
const initialLoading = ref(true);
const isDarkMode = ref(localStorage.getItem('darkMode') === 'true');

// 趋势图控制器
const chartRef = ref(null);
let myChart = null;
let lastTrendData = null;
let resizeObserver = null;
const trendFilter = ref('all'); // 'all', 'assets', 'risks'

// 漏洞环形图控制器
const vulnChartRef = ref(null);
let myVulnChart = null;
let vulnResizeObserver = null;
const vulnEngineMode = ref('all'); // 'all', 'nuclei', 'arl'

// 日志动态筛选与弹窗
const logFilter = ref('all'); // 'all', 'warn', 'task'
const isLogModalVisible = ref(false);
const currentLog = ref(null);

const showLogDetail = (log) => {
  currentLog.value = log;
  isLogModalVisible.value = true;
};

// 响应式业务状态数据
const stats = ref({
  total_assets: 0,
  today_tasks: 0,
  today_new_assets: 0,
  vuln: { arl_total: 0, nuclei_critical: 0, nuclei_high: 0, nuclei_medium: 0, nuclei_low: 0 },
  github_monitors: 0
});

const sysInfo = ref({
  cpu_percent: 0,
  mem_percent: 0,
  mem_total_gb: 0,
  mem_used_gb: 0,
  mem_available_gb: 0,
  mem_alert: 'ok',
  swap_percent: 0,
  swap_total_gb: 0,
  disk_percent: 0,
  tasks: { running: 0, waiting: 0, task_waiting: 0, icp_waiting: 0, task_running: 0, icp_running: 0 },
  github_today: { leaks: 0, intel: 0 },
  github_today_breakdown: { cves: 0, hackers: 0, general: 0 },
  github_totals: { cves: 0, tools: 0, hackers: 0 }
});

const handleRunningBadgeClick = () => {
  const icpRun = sysInfo.value?.tasks?.icp_running || 0;
  const taskRun = sysInfo.value?.tasks?.task_running || 0;
  if (icpRun > 0 && taskRun === 0) {
    router.push({ path: '/taskList', query: { tab: 'enterprise', status: 'running' } });
  } else {
    router.push({ path: '/taskList', query: { tab: 'task', status: 'running' } });
  }
};

const handleWaitingBadgeClick = () => {
  const icpWait = sysInfo.value?.tasks?.icp_waiting || 0;
  const taskWait = sysInfo.value?.tasks?.task_waiting || 0;
  if (icpWait > 0 && taskWait === 0) {
    router.push({ path: '/taskList', query: { tab: 'enterprise', status: 'waiting' } });
  } else {
    router.push({ path: '/taskList', query: { tab: 'task', status: 'waiting' } });
  }
};

const handleTaskRibbonClick = () => {
  const waiting = sysInfo.value?.tasks?.waiting || 0;
  const running = sysInfo.value?.tasks?.running || 0;
  if (waiting > 0 && running === 0) {
    handleWaitingBadgeClick();
  } else if (running > 0) {
    handleRunningBadgeClick();
  } else {
    router.push({ path: '/taskList', query: { tab: 'task' } });
  }
};

const widgetsData = ref({
  top_fingerprints: [],
  active_tasks: []
});

const logs = ref([]);

// 全库漏洞总数计算
const totalVulnCount = computed(() => {
  const v = stats.value.vuln || {};
  return (v.nuclei_critical || 0) + (v.nuclei_high || 0) + (v.nuclei_medium || 0) + (v.nuclei_low || 0) + (v.arl_total || 0);
});

// 高危/严重漏洞计数
const criticalVulnCount = computed(() => {
  const v = stats.value.vuln || {};
  return (v.nuclei_critical || 0) + (v.nuclei_high || 0);
});

// 格式化任务标题（去除冗余的一次性前缀，突出目标与实体）
const formatTaskTitle = (name) => {
  if (!name) return pageText('pages.unnamedTask');
  return name.replace(/^(一次性扫描|周期监控|定时任务)-/, '');
};

// 智能结构化日志元数据解析
const getLogMeta = (item) => {
  const msg = item?.message || '';
  const title = item?.title || '';
  const level = item?.level || 'info';

  if (msg.includes('New CVE found:')) {
    const cve = msg.replace('New CVE found:', '').trim();
    return {
      type: 'cve',
      tag: pageText('pages.cveDiscovered'),
      mainText: cve,
      isCve: true
    };
  }
  if (msg.includes('Starting Github CVE Monitor Task')) {
    return {
      type: 'monitor',
      tag: pageText('pages.githubMonitoring'),
      mainText: pageText('pages.startCveMonitoringTask'),
      desc: pageText('pages.searchForCvesAndOpenSourceThreatIntelligence'),
      isCve: false
    };
  }
  if (level === 'error') {
    return {
      type: 'error',
      tag: pageText('pages.systemError'),
      mainText: title || pageText('pages.errorAlert'),
      isCve: false
    };
  }
  if (level === 'warning') {
    return {
      type: 'warning',
      tag: pageText('pages.riskWarning'),
      mainText: title || pageText('pages.alert'),
      isCve: false
    };
  }
  return {
    type: 'info',
    tag: title === 'run' ? pageText('pages.scheduledActivity') : (title || pageText('pages.schedulingNotification')),
    mainText: msg,
    isCve: false
  };
};

const formatTime = (timeStr) => {
  if (!timeStr) return '';
  if (timeStr.length >= 19) {
    return timeStr.substring(5, 19);
  }
  return timeStr;
};

// 动态获取日志等级颜色
const getLogColor = (level) => {
  const map = {
    'info': 'blue',
    'success': 'green',
    'warning': 'orange',
    'error': 'red'
  };
  return map[level] || 'gray';
};

// 任务状态文案映射（唯一事实源见 @/constants/taskStatus）
const getTaskStatusLabel = (status) => {
  return status ? formatTaskStatus(status) : pageText('tasks.unknown');
};

// 指纹分类识别器
const getFingerCategory = (name) => {
  const n = (name || '').toLowerCase();
  if (n.includes('cdn') || n.includes('cloudflare') || n.includes('akamai') || n.includes('bytedance-cdn')) return 'CDN';
  if (n.includes('nginx') || n.includes('apache') || n.includes('iis') || n.includes('tengine') || n.includes('openresty')) return 'Server';
  if (n.includes('vue') || n.includes('react') || n.includes('jquery') || n.includes('bootstrap')) return 'Front';
  if (n.includes('spring') || n.includes('django') || n.includes('laravel') || n.includes('express') || n.includes('flask')) return 'Frame';
  if (n.includes('tomcat') || n.includes('jboss') || n.includes('weblogic') || n.includes('sunlogin')) return 'App';
  return 'Web';
};

// 分类标识继续用于样式选择，显示名称单独响应语言切换。
const fingerCategoryKeys = {
  CDN: 'pages.fingerCategoryCdn', Server: 'pages.fingerCategoryServer',
  Front: 'pages.fingerCategoryFrontend', Frame: 'pages.fingerCategoryFramework',
  App: 'pages.fingerCategoryApplication', Web: 'pages.fingerCategoryWeb'
};
const formatFingerCategory = (category) => pageText(fingerCategoryKeys[category] || fingerCategoryKeys.Web);

// 指纹占比进度条宽度 (相对于 TOP1)
const maxFingerCount = computed(() => {
  if (!widgetsData.value.top_fingerprints || widgetsData.value.top_fingerprints.length === 0) return 1;
  return Math.max(...widgetsData.value.top_fingerprints.map(x => x.count || 0), 1);
});

const getFingerPercent = (cnt) => {
  if (!cnt) return 0;
  return Math.min(Math.round((cnt / maxFingerCount.value) * 100), 100);
};

// 指纹相对全库站点的绝对占比（与左侧“以 TOP1 为基准”的条形长度口径不同）
const getFingerRatio = (cnt) => {
  if (!cnt || !stats.value.total_assets) return '0%';
  const ratio = (cnt / stats.value.total_assets) * 100;
  return ratio < 0.1 ? '<0.1%' : ratio.toFixed(1) + '%';
};

// 日志智能聚类与去噪处理 (收敛 [run_forever] start scheduler server 等心跳刷屏)
const filteredGroupedLogs = computed(() => {
  const raw = logs.value || [];
  let filtered = raw;

  if (logFilter.value === 'warn') {
    filtered = raw.filter(x => x.level === 'error' || x.level === 'warning');
  } else if (logFilter.value === 'task') {
    filtered = raw.filter(x => !((x.message || '').includes('start scheduler server') || (x.title || '').includes('run_forever')));
  }

  const result = [];
  let heartbeatBuffer = [];

  const flushHeartbeats = () => {
    if (heartbeatBuffer.length === 0) return;
    if (heartbeatBuffer.length === 1) {
      result.push(heartbeatBuffer[0]);
    } else {
      result.push({
        isHeartbeatGroup: true,
        count: heartbeatBuffer.length,
        items: [...heartbeatBuffer],
        expanded: false
      });
    }
    heartbeatBuffer = [];
  };

  for (const log of filtered) {
    const isHeartbeat = (log.message || '').includes('start scheduler server') || (log.title || '') === 'run_forever';
    if (isHeartbeat) {
      heartbeatBuffer.push(log);
    } else {
      flushHeartbeats();
      result.push(log);
    }
  }
  flushHeartbeats();

  return result;
});

// 颜色工具
const colorToRgba = (color, opacity = 1) => {
  if (!color) return `rgba(24, 144, 255, ${opacity})`;
  const c = color.trim();
  if (c.startsWith('#')) {
    let hex = c.slice(1);
    if (hex.length === 3 || hex.length === 4) {
      hex = hex.slice(0, 3).split('').map(char => char + char).join('');
    } else if (hex.length >= 6) {
      hex = hex.slice(0, 6);
    }
    const r = parseInt(hex.substring(0, 2), 16) || 0;
    const g = parseInt(hex.substring(2, 4), 16) || 0;
    const b = parseInt(hex.substring(4, 6), 16) || 0;
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }
  if (c.startsWith('rgb(')) {
    return c.replace('rgb(', 'rgba(').replace(')', `, ${opacity})`);
  }
  if (c.startsWith('rgba(')) {
    return c.replace(/rgba\(([^,]+),([^,]+),([^,]+),[^)]+\)/, `rgba($1,$2,$3, ${opacity})`);
  }
  return c;
};

const handleDarkModeChange = (e) => {
  isDarkMode.value = typeof e?.detail === 'boolean' ? e.detail : (localStorage.getItem('darkMode') === 'true');
  nextTick(() => {
    renderTrendChart();
    renderVulnChart();
  });
};

const handleThemeChange = (e) => {
  const newColor = typeof e?.detail === 'string' ? e.detail : undefined;
  nextTick(() => {
    renderTrendChart(newColor);
    renderVulnChart();
  });
};

// 切换趋势图过滤维度
const setTrendFilter = (filterType) => {
  trendFilter.value = filterType;
  renderTrendChart();
};

// 切换漏洞引擎环形图
const setVulnEngineMode = (mode) => {
  vulnEngineMode.value = mode;
  renderVulnChart();
};

watch(pageLocale, () => {
  renderTrendChart();
  renderVulnChart();
  myChart?.resize();
  myVulnChart?.resize();
}, { flush: 'post' });

const fetchStats = async () => {
  try {
    const res = await request.get('/api/dashboard/stats');
    if (res.code === 200) {
      stats.value = res.data;
      renderVulnChart();
    }
  } catch (error) {
    console.error('Failed to fetch stats:', error);
  }
};

const fetchSysInfo = async () => {
  try {
    const res = await request.get('/api/dashboard/sysinfo');
    if (res.code === 200) {
      sysInfo.value = { ...sysInfo.value, ...res.data };
    }
  } catch (error) {
    console.error('Failed to fetch sysinfo:', error);
  }
};

const fetchWidgetsData = async () => {
  try {
    const res = await request.get('/api/dashboard/widgets');
    if (res.code === 200) {
      widgetsData.value = res.data || { top_fingerprints: [], active_tasks: [] };
    }
  } catch (error) {
    console.error('Failed to fetch widgets data:', error);
  }
};

const fetchLogs = async () => {
  try {
    const res = await request.get('/api/dashboard/logs');
    if (res.code === 200) {
      logs.value = res.data.logs || [];
    }
  } catch (error) {
    console.error('Failed to fetch logs:', error);
  }
};

// 渲染趋势图 (平滑贝塞尔曲线 + 科技渐变微光 + 动态指标切换)
const renderTrendChart = (customColor) => {
  if (!chartRef.value) return;
  if (!myChart) {
    myChart = echarts.getInstanceByDom(chartRef.value) || echarts.init(chartRef.value);
  }
  if (!myChart || !lastTrendData) return;

  const days = lastTrendData.days || [];
  const assets = lastTrendData.assets || [];
  const vulns = lastTrendData.vulns || [];
  const leaks = lastTrendData.leaks || [];
  const cves = lastTrendData.cves || [];

  const themeColor = customColor || getComputedStyle(document.documentElement).getPropertyValue('--arl-theme-color').trim() || '#1890ff';
  const isDark = isDarkMode.value;

  const seriesList = [];
  const legends = [];

  // 1. 新增站点系列
  if (trendFilter.value === 'all' || trendFilter.value === 'assets') {
    legends.push(pageText('pages.newWebsites'));
    seriesList.push({
      name: pageText('pages.newWebsites'),
      type: 'line',
      smooth: 0.35,
      symbol: 'circle',
      symbolSize: 4,
      data: assets,
      itemStyle: { color: themeColor },
      lineStyle: { width: 3, color: themeColor, shadowColor: colorToRgba(themeColor, 0.4), shadowBlur: 8 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: colorToRgba(themeColor, 0.28) },
          { offset: 1, color: colorToRgba(themeColor, 0.0) }
        ])
      }
    });
  }

  // 2. 漏洞系列
  if (trendFilter.value === 'all' || trendFilter.value === 'risks') {
    legends.push(pageText('pages.vulnerabilitiesDetected'));
    seriesList.push({
      name: pageText('pages.vulnerabilitiesDetected'),
      type: 'bar',
      yAxisIndex: 1,
      barMaxWidth: 12,
      itemStyle: { 
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: isDark ? '#ff7875' : '#ff4d4f' },
          { offset: 1, color: isDark ? 'rgba(255, 77, 79, 0.3)' : 'rgba(255, 77, 79, 0.15)' }
        ]),
        borderRadius: [4, 4, 0, 0] 
      },
      data: vulns
    });

    legends.push(pageText('pages.codeLeaks'));
    seriesList.push({
      name: pageText('pages.codeLeaks'),
      type: 'line',
      yAxisIndex: 1,
      smooth: 0.35,
      symbol: 'circle',
      symbolSize: 4,
      data: leaks,
      itemStyle: { color: '#fa8c16' },
      lineStyle: { width: 2, type: 'dashed', color: '#fa8c16' }
    });

    legends.push(pageText('pages.cveIntelligence'));
    seriesList.push({
      name: pageText('pages.cveIntelligence'),
      type: 'line',
      yAxisIndex: 1,
      smooth: 0.35,
      symbol: 'circle',
      symbolSize: 4,
      data: cves,
      itemStyle: { color: isDark ? '#b37feb' : '#722ed1' },
      lineStyle: { width: 2.2, color: isDark ? '#b37feb' : '#722ed1', shadowColor: 'rgba(114, 46, 209, 0.35)', shadowBlur: 6 }
    });
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { 
        type: 'cross',
        crossStyle: { color: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.15)', width: 1, type: 'dashed' },
        lineStyle: { color: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.12)', width: 1 }
      },
      backgroundColor: isDark ? 'rgba(20, 20, 20, 0.88)' : 'rgba(255, 255, 255, 0.95)',
      borderColor: isDark ? 'rgba(255, 255, 255, 0.12)' : '#e2e8f0',
      textStyle: { 
        color: isDark ? 'rgba(255, 255, 255, 0.9)' : '#262626', 
        fontSize: 12,
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace'
      },
      extraCssText: 'backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); border-radius: 8px; box-shadow: 0 8px 32px rgba(0,0,0,0.22);',
      padding: [10, 14]
    },
    legend: {
      data: legends,
      top: 0,
      textStyle: { 
        color: isDark ? 'rgba(255, 255, 255, 0.75)' : '#555', 
        fontWeight: 500, 
        fontSize: 12 
      },
      itemGap: 16,
      itemWidth: 14,
      itemHeight: 10
    },
    grid: {
      left: 12,
      right: 12,
      bottom: 8,
      top: 36,
      containLabel: true
    },
    xAxis: [
      {
        type: 'category',
        data: days,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { 
          color: isDark ? 'rgba(255, 255, 255, 0.45)' : '#888', 
          margin: 10,
          fontSize: 11,
          fontFamily: 'ui-monospace, monospace'
        }
      }
    ],
    yAxis: [
      {
        type: 'value',
        name: pageText('pages.websiteCount'),
        nameTextStyle: { color: isDark ? 'rgba(255, 255, 255, 0.45)' : '#888', padding: [0, 0, 0, 16], fontSize: 11 },
        axisLabel: { color: isDark ? 'rgba(255, 255, 255, 0.45)' : '#888', fontSize: 11, fontFamily: 'monospace' },
        minInterval: 1,
        splitLine: { 
          show: true,
          lineStyle: { color: isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.05)', type: 'dashed' }
        },
        axisLine: { show: false },
        axisTick: { show: false }
      },
      {
        type: 'value',
        name: pageText('pages.risksEvents'),
        nameTextStyle: { color: isDark ? 'rgba(255, 255, 255, 0.45)' : '#888', padding: [0, 16, 0, 0], fontSize: 11 },
        axisLabel: { color: isDark ? 'rgba(255, 255, 255, 0.45)' : '#888', fontSize: 11, fontFamily: 'monospace' },
        minInterval: 1,
        splitLine: { show: false },
        axisLine: { show: false },
        axisTick: { show: false }
      }
    ],
    series: seriesList
  };
  
  myChart.setOption(option, true);
};

// 渲染漏洞环形图 (支持全量/Nuclei/ARL 模式切换 + 发光微动效)
const renderVulnChart = () => {
  if (!vulnChartRef.value) return;
  if (!myVulnChart) {
    myVulnChart = echarts.getInstanceByDom(vulnChartRef.value) || echarts.init(vulnChartRef.value);
  }
  if (!myVulnChart) return;

  const v = stats.value.vuln || {};
  let dataList = [];

  if (vulnEngineMode.value === 'nuclei') {
    dataList = [
      { value: v.nuclei_critical || 0, name: pageText('assets.critical'), itemStyle: { color: '#e53935' }, tabKey: 'critical' },
      { value: v.nuclei_high || 0, name: pageText('assets.high'), itemStyle: { color: '#f4511e' }, tabKey: 'high' },
      { value: v.nuclei_medium || 0, name: pageText('assets.medium'), itemStyle: { color: '#fb8c00' }, tabKey: 'medium' },
      { value: v.nuclei_low || 0, name: pageText('assets.low'), itemStyle: { color: '#1e88e5' }, tabKey: 'low' }
    ];
  } else if (vulnEngineMode.value === 'arl') {
    dataList = [
      { value: v.arl_total || 0, name: pageText('pages.arlBuiltIn'), itemStyle: { color: '#8e24aa' }, tabKey: 'arl' }
    ];
  } else {
    dataList = [
      { value: v.nuclei_critical || 0, name: pageText('assets.critical'), itemStyle: { color: '#e53935' }, tabKey: 'critical' },
      { value: v.nuclei_high || 0, name: pageText('assets.high'), itemStyle: { color: '#f4511e' }, tabKey: 'high' },
      { value: v.nuclei_medium || 0, name: pageText('assets.medium'), itemStyle: { color: '#fb8c00' }, tabKey: 'medium' },
      { value: v.nuclei_low || 0, name: pageText('assets.low'), itemStyle: { color: '#1e88e5' }, tabKey: 'low' },
      { value: v.arl_total || 0, name: pageText('pages.arlBuiltIn'), itemStyle: { color: '#8e24aa' }, tabKey: 'arl' }
    ];
  }

  const totalFilteredVulns = dataList.reduce((acc, cur) => acc + cur.value, 0);
  const isDark = isDarkMode.value;

  const option = {
    tooltip: {
      trigger: 'item',
      backgroundColor: isDark ? 'rgba(20, 20, 20, 0.9)' : 'rgba(255, 255, 255, 0.95)',
      borderColor: isDark ? 'rgba(255, 255, 255, 0.12)' : '#e2e8f0',
      textStyle: { color: isDark ? 'rgba(255, 255, 255, 0.9)' : '#262626', fontSize: 12 },
      formatter: value => pageText('pages.chartFindingCount', { name: value.name, count: value.value, percent: value.percent })
    },
    legend: {
      orient: 'vertical',
      right: '4%',
      top: 'center',
      itemWidth: 10,
      itemHeight: 10,
      itemGap: 10,
      textStyle: {
        color: isDark ? 'rgba(255, 255, 255, 0.75)' : '#555',
        fontSize: 11
      },
      formatter: (name) => {
        const item = dataList.find(d => d.name === name);
        const val = item ? item.value : 0;
        const pct = totalFilteredVulns > 0 ? ((val / totalFilteredVulns) * 100).toFixed(0) : 0;
        return `${name}  ${val} (${pct}%)`;
      }
    },
    series: [
      {
        name: pageText('pages.vulnerabilitySeverity'),
        type: 'pie',
        radius: ['56%', '78%'],
        center: ['34%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 6,
          borderColor: isDark ? '#141414' : '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          position: 'center',
          formatter: () => `{total|${totalFilteredVulns}}\n{label|${vulnEngineMode.value === 'nuclei' ? pageText('pages.nucleiFindings') : (vulnEngineMode.value === 'arl' ? pageText('pages.arlBuiltInLabel2') : pageText('pages.allFindings'))}}`,
          rich: {
            total: {
              fontSize: 24,
              fontWeight: 700,
              color: isDark ? 'rgba(255,255,255,0.95)' : '#262626',
              lineHeight: 28,
              fontFamily: 'ui-monospace, monospace'
            },
            label: {
              fontSize: 11,
              color: isDark ? 'rgba(255,255,255,0.45)' : '#8c8c8c',
              padding: [4, 0, 0, 0]
            }
          }
        },
        labelLine: { show: false },
        data: dataList
      }
    ]
  };

  myVulnChart.setOption(option, true);

  // 绑定扇区点击跳转
  myVulnChart.off('click');
  myVulnChart.on('click', (params) => {
    const item = dataList.find(d => d.name === params.name);
    if (!item) return;
    if (item.tabKey === 'arl') {
      router.push({ path: '/asset-search', query: { tab: 'vuln' } });
    } else {
      router.push({ path: '/asset-search', query: { tab: 'nuclei_result', vuln_severity: item.tabKey } });
    }
  });
};

const fetchTrendAndRender = async () => {
  try {
    const res = await request.get('/api/dashboard/trend');
    if (res.code === 200) {
      lastTrendData = res.data;
      await nextTick();
      renderTrendChart();
    }
  } catch (error) {
    console.error('Failed to fetch trend:', error);
  }
};

const initResizeObserver = () => {
  if (typeof ResizeObserver !== 'undefined' && chartRef.value) {
    if (resizeObserver) resizeObserver.disconnect();
    resizeObserver = new ResizeObserver(() => {
      if (myChart && chartRef.value && chartRef.value.clientWidth > 0 && chartRef.value.clientHeight > 0) {
        myChart.resize();
      }
    });
    resizeObserver.observe(chartRef.value);
  }

  if (typeof ResizeObserver !== 'undefined' && vulnChartRef.value) {
    if (vulnResizeObserver) vulnResizeObserver.disconnect();
    vulnResizeObserver = new ResizeObserver(() => {
      if (myVulnChart && vulnChartRef.value && vulnChartRef.value.clientWidth > 0 && vulnChartRef.value.clientHeight > 0) {
        myVulnChart.resize();
      }
    });
    vulnResizeObserver.observe(vulnChartRef.value);
  }
};

const fetchAllData = async (isInitial = false) => {
  if (isInitial) {
    initialLoading.value = true;
  }
  try {
    await Promise.allSettled([
      fetchStats(),
      fetchLogs(),
      fetchTrendAndRender(),
      fetchSysInfo(),
      fetchWidgetsData()
    ]);
  } finally {
    if (isInitial) {
      initialLoading.value = false;
      await nextTick();
      if (chartRef.value) {
        if (!myChart) myChart = echarts.getInstanceByDom(chartRef.value) || echarts.init(chartRef.value);
        if (lastTrendData) renderTrendChart();
      }
      if (vulnChartRef.value) {
        if (!myVulnChart) myVulnChart = echarts.getInstanceByDom(vulnChartRef.value) || echarts.init(vulnChartRef.value);
        renderVulnChart();
      }
      initResizeObserver();
      if (myChart && chartRef.value?.clientWidth > 0) myChart.resize();
      if (myVulnChart && vulnChartRef.value?.clientWidth > 0) myVulnChart.resize();
    }
  }
};

let sysInfoTimer = null;
let isFirstMounted = true;
const isPageActive = ref(false);

const startPolling = () => {
  stopPolling();
  sysInfoTimer = setInterval(() => {
    if (isPageActive.value && document.visibilityState === 'visible') {
      fetchSysInfo();
      fetchWidgetsData();
    }
  }, 5000);
};

const stopPolling = () => {
  if (sysInfoTimer) {
    clearInterval(sysInfoTimer);
    sysInfoTimer = null;
  }
};

const handleVisibilityChange = () => {
  if (isPageActive.value && document.visibilityState === 'visible') {
    fetchSysInfo();
    fetchWidgetsData();
    startPolling();
  } else {
    stopPolling();
  }
};

const handleResize = () => {
  if (myChart && chartRef.value?.clientWidth > 0) myChart.resize();
  if (myVulnChart && vulnChartRef.value?.clientWidth > 0) myVulnChart.resize();
};

onMounted(async () => {
  window.addEventListener('theme-changed', handleThemeChange);
  window.addEventListener('dark-mode-changed', handleDarkModeChange);
  window.addEventListener('resize', handleResize);
  document.addEventListener('visibilitychange', handleVisibilityChange);

  isPageActive.value = true;
  await fetchAllData(true);
  startPolling();
  isFirstMounted = false;
});

onActivated(() => {
  isPageActive.value = true;
  isDarkMode.value = localStorage.getItem('darkMode') === 'true';
  if (!isFirstMounted) {
    fetchAllData(false);
    startPolling();
  }
  nextTick(() => {
    if (chartRef.value) {
      if (!myChart) myChart = echarts.getInstanceByDom(chartRef.value) || echarts.init(chartRef.value);
      if (lastTrendData) renderTrendChart();
    }
    if (vulnChartRef.value) {
      if (!myVulnChart) myVulnChart = echarts.getInstanceByDom(vulnChartRef.value) || echarts.init(vulnChartRef.value);
      renderVulnChart();
    }
    initResizeObserver();
    if (myChart && chartRef.value?.clientWidth > 0) myChart.resize();
    if (myVulnChart && vulnChartRef.value?.clientWidth > 0) myVulnChart.resize();
  });
});

onDeactivated(() => {
  isPageActive.value = false;
  stopPolling();
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (vulnResizeObserver) {
    vulnResizeObserver.disconnect();
    vulnResizeObserver = null;
  }
});

onUnmounted(() => {
  isPageActive.value = false;
  stopPolling();
  window.removeEventListener('theme-changed', handleThemeChange);
  window.removeEventListener('dark-mode-changed', handleDarkModeChange);
  window.removeEventListener('resize', handleResize);
  document.removeEventListener('visibilitychange', handleVisibilityChange);

  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (vulnResizeObserver) {
    vulnResizeObserver.disconnect();
    vulnResizeObserver = null;
  }

  if (myChart) {
    myChart.dispose();
    myChart = null;
  }
  if (myVulnChart) {
    myVulnChart.dispose();
    myVulnChart = null;
  }
});
</script>

<style scoped>
.dashboard-container {
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  padding: 16px;
  background: var(--arl-bg-layout);
  gap: 14px;
  min-height: 100%;
}

.dashboard-section {
  width: 100%;
}

.stat-row,
.main-row,
.widget-row {
  margin-left: -7px !important;
  margin-right: -7px !important;
  margin-top: 0 !important;
  margin-bottom: 0 !important;
  align-items: stretch;
}

.main-col,
.widget-col {
  display: flex;
  flex-direction: column;
}

/* ========================================================
   先锋科技感安全态势卡片 (Tech-Modern Posture Cards)
   ======================================================== */
.modern-stat-card {
  height: 100%;
  border-radius: 12px;
  transition: all 0.28s cubic-bezier(0.2, 0, 0, 1);
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
  border: 1px solid var(--arl-border-color);
  background: var(--arl-bg-container);
  position: relative;
}

.modern-stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 24px -4px rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(var(--arl-theme-color-rgb, 24, 144, 255), 0.25);
}

.card-ambient-glow {
  position: absolute;
  right: -24px;
  top: -24px;
  width: 110px;
  height: 110px;
  border-radius: 50%;
  filter: blur(34px);
  pointer-events: none;
  opacity: 0.45;
  z-index: 0;
  transition: opacity 0.3s ease;
}
.modern-stat-card:hover .card-ambient-glow {
  opacity: 0.75;
}
.card-ambient-glow.primary { background: rgba(var(--arl-theme-color-rgb, 24, 144, 255), 0.45); }
.card-ambient-glow.success { background: rgba(82, 196, 26, 0.4); }
.card-ambient-glow.danger { background: rgba(245, 34, 45, 0.38); }
.card-ambient-glow.dark { background: rgba(114, 46, 209, 0.35); }

.modern-stat-card :deep(.ant-card-body) {
  padding: 14px 16px;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 1;
}

.clickable-card {
  cursor: pointer;
}

.card-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  justify-content: space-between;
}

.card-top-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.card-title-text {
  font-size: 13px;
  color: var(--arl-text-color);
  opacity: 0.78;
  font-weight: 500;
  letter-spacing: 0.2px;
}

.stat-icon-box {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 19px;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
  transition: transform 0.25s cubic-bezier(0.2, 0, 0, 1);
}
.modern-stat-card:hover .stat-icon-box {
  transform: scale(1.1);
}
.stat-icon-box.primary {
  background: rgba(24, 144, 255, 0.12);
  color: var(--arl-theme-color);
}
.stat-icon-box.success {
  background: rgba(82, 196, 26, 0.12);
  color: #52c41a;
}
.stat-icon-box.danger {
  background: rgba(245, 34, 45, 0.12);
  color: #f5222d;
}
.stat-icon-box.dark {
  background: var(--arl-bg-light);
  color: var(--arl-text-color);
}

.card-metric-num {
  font-size: 32px;
  font-weight: 700;
  color: var(--arl-text-color);
  line-height: 1.15;
  letter-spacing: -0.5px;
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  margin: 4px 0 8px 0;
}

.card-footer-ribbon {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 6px;
  border-top: 1px dashed var(--arl-border-color);
  font-size: 12px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-text {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.55;
}

.beacon-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--arl-theme-color);
}

.pulse-beacon {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
  position: relative;
}
.pulse-beacon.green {
  background: #52c41a;
  box-shadow: 0 0 0 rgba(82, 196, 26, 0.6);
  animation: beacon-pulse 2s infinite cubic-bezier(0.4, 0, 0.2, 1);
}
.pulse-beacon.red {
  background: #ff4d4f;
  box-shadow: 0 0 0 rgba(255, 77, 79, 0.6);
  animation: beacon-pulse-danger 1.8s infinite cubic-bezier(0.4, 0, 0.2, 1);
}
.inline-pulse {
  vertical-align: middle;
  margin-left: 4px;
}

@keyframes beacon-pulse {
  0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(82, 196, 26, 0.7); }
  70% { transform: scale(1.1); box-shadow: 0 0 0 6px rgba(82, 196, 26, 0); }
  100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(82, 196, 26, 0); }
}

@keyframes beacon-pulse-danger {
  0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(255, 77, 79, 0.7); }
  70% { transform: scale(1.1); box-shadow: 0 0 0 6px rgba(255, 77, 79, 0); }
  100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(255, 77, 79, 0); }
}

.trend-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}
.trend-badge.positive {
  background: rgba(82, 196, 26, 0.1);
  color: #52c41a;
}

.footer-link-hint {
  font-size: 11px;
  color: var(--arl-theme-color);
  cursor: pointer;
  opacity: 0.85;
  transition: opacity 0.2s;
}
.footer-link-hint:hover {
  opacity: 1;
  text-decoration: underline;
}

/* 双指标单元排版 (今日侦察 & GitHub) */
.dual-metric-wrap {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 4px 0 8px 0;
}
.metric-cell {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 2px 4px;
  border-radius: 6px;
  transition: background 0.2s;
}
.metric-cell.clickable-cell:hover {
  background: var(--arl-bg-light);
}
.cell-val {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
}
.cell-val.success-val { color: #52c41a; }
.cell-val.primary-val { color: var(--arl-theme-color); }
.cell-val.danger-val { color: #ff4d4f; }
.cell-val.warning-val { color: #faad14; }

.cell-lbl {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.55;
  margin-top: 2px;
  white-space: nowrap;
}
.metric-divider {
  width: 1px;
  height: 28px;
  background: var(--arl-border-color);
  margin: 0 8px;
  flex-shrink: 0;
}

/* 漏洞全景矩阵 */
.vuln-matrix-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin: 4px 0 8px 0;
}
.vuln-total-num {
  font-size: 26px;
  font-weight: 700;
  color: var(--arl-text-color);
  font-variant-numeric: tabular-nums;
}
.vuln-total-unit {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.5;
  font-weight: normal;
  margin-left: 4px;
}
.critical-alert-tag {
  font-size: 11px;
  border-radius: 4px;
  margin: 0;
  padding: 0 6px;
  line-height: 20px;
}

.vuln-pill-row {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 4px;
}
.vuln-pill {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3px 2px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  line-height: 1.2;
}
.vuln-pill:hover {
  transform: translateY(-2px);
  filter: brightness(1.12);
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.12);
}
.vuln-pill .pill-name {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.85);
  font-weight: 500;
}
.vuln-pill .pill-cnt {
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  font-family: monospace;
}
.vuln-pill.critical { background: linear-gradient(180deg, #ef4444 0%, #dc2626 100%); }
.vuln-pill.high { background: linear-gradient(180deg, #f97316 0%, #ea580c 100%); }
.vuln-pill.medium { background: linear-gradient(180deg, #f59e0b 0%, #d97706 100%); }
.vuln-pill.low { background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%); }
.vuln-pill.arl { background: linear-gradient(180deg, #a855f7 0%, #9333ea 100%); }
.vuln-pill.empty {
  opacity: 0.5;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  box-shadow: none;
}
.vuln-pill.empty .pill-name,
.vuln-pill.empty .pill-cnt {
  color: var(--arl-text-color);
  opacity: 0.7;
}

.intel-tooltip-box {
  font-size: 12px;
  line-height: 1.6;
}
.tooltip-title {
  font-weight: 600;
  color: #faad14;
  margin-bottom: 2px;
}
.tooltip-sep {
  border-top: 1px dashed rgba(255,255,255,0.3);
  margin: 6px 0;
}

/* ========================================================
   Row 2: 紧凑型系统算力与调度健康度胶囊条 (Compact Health Ribbon)
   ======================================================== */
.health-ribbon-bar {
  background: var(--arl-bg-container);
  border: 1px solid var(--arl-border-color);
  border-radius: 12px;
  padding: 8px 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
  display: flex;
  align-items: center;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.ribbon-items-container {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  flex-wrap: wrap;
  gap: 12px;
}

.ribbon-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.ribbon-item.cursor-pointer {
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}
.ribbon-item.cursor-pointer:hover {
  background: var(--arl-bg-light);
}

.ribbon-icon {
  font-size: 14px;
}
.ribbon-icon.cpu-color { color: var(--arl-theme-color); }
.ribbon-icon.mem-color { color: #fa8c16; }
.ribbon-icon.disk-color { color: #52c41a; }
.ribbon-icon.celery-color { color: #722ed1; }

.ribbon-name {
  color: var(--arl-text-color);
  opacity: 0.65;
  font-weight: 500;
}

.ribbon-val {
  font-weight: 600;
  font-family: monospace;
  color: var(--arl-text-color);
}
.ribbon-val.text-danger { color: #ff4d4f !important; }
.ribbon-val.text-warning { color: #faad14 !important; }

.ribbon-subval {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.45;
  font-family: monospace;
}

.ribbon-progress-track {
  width: 50px;
  height: 5px;
  background: var(--arl-border-color);
  border-radius: 3px;
  overflow: hidden;
}

.ribbon-progress-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.ribbon-alert-tag {
  margin: 0;
  padding: 0 4px;
  font-size: 10px;
  line-height: 16px;
}

.ribbon-divider {
  width: 1px;
  height: 16px;
  background: var(--arl-border-color);
}

.ribbon-task-badges {
  display: flex;
  align-items: center;
  gap: 8px;
}
.task-badge {
  font-size: 12px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 0.2s ease;
}
.task-badge:hover {
  background: var(--arl-badge-hover-bg, rgba(0, 0, 0, 0.06));
  filter: brightness(1.1);
}
.task-badge.running { color: #52c41a; }
.task-badge.waiting { color: #fa8c16; }
.task-badge .num {
  font-family: monospace;
  font-weight: 700;
}

.ribbon-arrow {
  font-size: 10px;
  color: var(--arl-text-color);
  opacity: 0.4;
}

/* ========================================================
   主体卡片与联动布局 (Main Cards: Chart & Log)
   ======================================================== */
.main-card {
  height: 310px;
  display: flex;
  flex-direction: column;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
  border: 1px solid var(--arl-border-color);
  background: var(--arl-bg-container);
}

.main-card :deep(.ant-card-head),
.widget-card :deep(.ant-card-head) {
  min-height: 44px;
  padding: 0 16px;
  border-bottom: 1px solid var(--arl-border-color);
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.main-card :deep(.ant-card-head-wrapper),
.widget-card :deep(.ant-card-head-wrapper) {
  width: 100%;
}

.main-card :deep(.ant-card-body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 10px 14px;
  overflow: hidden;
}

.card-header-flex {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.card-header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--arl-text-color);
}

.card-header-icon {
  color: var(--arl-theme-color);
  font-size: 16px;
}

.trend-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.metric-filter-group {
  display: flex;
  align-items: center;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  padding: 2px;
  gap: 2px;
}

.filter-pill {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 4px;
  cursor: pointer;
  color: var(--arl-text-color);
  opacity: 0.65;
  transition: all 0.2s ease;
  user-select: none;
}
.filter-pill:hover {
  opacity: 1;
}
.filter-pill.active {
  background: var(--arl-bg-container);
  color: var(--arl-theme-color);
  opacity: 1;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.range-tag {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.5;
  border: 1px solid var(--arl-border-color);
  padding: 2px 6px;
  border-radius: 4px;
}

.card-body-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  width: 100%;
  position: relative;
}

.echarts-box {
  width: 100%;
  height: 100%;
  min-height: 240px;
}

/* ========================================================
   系统动态与审计流 (Smart Audit Stream)
   ======================================================== */
.log-filter-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.log-tab-item {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  cursor: pointer;
  color: var(--arl-text-color);
  opacity: 0.6;
  transition: all 0.2s;
}
.log-tab-item:hover {
  opacity: 0.9;
}
.log-tab-item.active {
  background: var(--arl-bg-light);
  color: var(--arl-theme-color);
  font-weight: 600;
  opacity: 1;
}

.log-scroll-area {
  flex: 1;
  min-height: 0;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px;
}

.log-scroll-area::-webkit-scrollbar,
.task-stream-container::-webkit-scrollbar {
  width: 5px;
}
.log-scroll-area::-webkit-scrollbar-track,
.task-stream-container::-webkit-scrollbar-track {
  background: transparent;
}
.log-scroll-area::-webkit-scrollbar-thumb,
.task-stream-container::-webkit-scrollbar-thumb {
  background: var(--arl-border-color);
  border-radius: 4px;
  transition: background-color 0.2s;
}
.log-scroll-area::-webkit-scrollbar-thumb:hover,
.task-stream-container::-webkit-scrollbar-thumb:hover {
  background: var(--arl-theme-color);
}

.log-list-container {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.heartbeat-group-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 8px;
  background: var(--arl-bg-light);
  border-radius: 6px;
  border: 1px dashed var(--arl-border-color);
  cursor: pointer;
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.7;
  transition: all 0.2s;
}
.heartbeat-group-row:hover {
  opacity: 1;
  border-color: var(--arl-theme-color);
}
.heartbeat-info {
  display: flex;
  align-items: center;
  gap: 6px;
}
.heartbeat-spin {
  font-size: 10px;
  color: var(--arl-theme-color);
}
.heartbeat-toggle {
  font-size: 10px;
  color: var(--arl-theme-color);
  display: flex;
  align-items: center;
  gap: 2px;
}

.heartbeat-expanded-box {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-left: 10px;
  border-left: 2px solid var(--arl-border-color);
}
.heartbeat-sub-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  padding: 3px 6px;
}

.log-stream-item {
  cursor: pointer;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  transition: all 0.22s ease;
  display: flex;
  gap: 10px;
  position: relative;
  overflow: hidden;
}
.log-stream-item:hover {
  border-color: var(--arl-theme-color);
  background: var(--arl-bg-container);
  transform: translateX(3px);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
}
.log-stream-item.has-alert {
  border-color: rgba(255, 77, 79, 0.35);
  background: rgba(255, 77, 79, 0.04);
}

.log-indicator-stripe {
  width: 3px;
  border-radius: 3px;
  align-self: stretch;
  flex-shrink: 0;
  background: var(--arl-theme-color);
}
.log-indicator-stripe.cve { background: #fa8c16; }
.log-indicator-stripe.monitor { background: #722ed1; }
.log-indicator-stripe.error { background: #ff4d4f; }
.log-indicator-stripe.warning { background: #faad14; }
.log-indicator-stripe.info { background: var(--arl-theme-color); }

.log-stream-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.log-item-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.log-tag-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.log-type-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  line-height: 16px;
}
.log-type-tag.cve {
  background: rgba(250, 140, 22, 0.12);
  color: #fa8c16;
}
.log-type-tag.monitor {
  background: rgba(114, 46, 209, 0.12);
  color: #722ed1;
}
.log-type-tag.error {
  background: rgba(255, 77, 79, 0.12);
  color: #ff4d4f;
}
.log-type-tag.warning {
  background: rgba(250, 173, 20, 0.12);
  color: #faad14;
}
.log-type-tag.info {
  background: rgba(24, 144, 255, 0.12);
  color: var(--arl-theme-color);
}
.log-tag-icon {
  font-size: 10px;
}

.cve-inline-pill {
  font-size: 11px;
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #e53935;
  background: rgba(229, 57, 53, 0.08);
  padding: 0 5px;
  border-radius: 3px;
  line-height: 16px;
}

.log-item-time {
  font-size: 10px;
  color: var(--arl-text-color);
  opacity: 0.45;
  font-family: monospace;
}

.log-item-msg {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.8;
  line-height: 1.45;
  word-break: break-all;
}
.cve-msg-highlight {
  color: var(--arl-text-color);
  opacity: 0.75;
}

.empty-log-box {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
}

/* ========================================================
   Row 4: 拓展卡片 (Widgets: Fingerprint, Vuln Pie, Tasks)
   ======================================================== */
.widget-card {
  height: 255px;
  display: flex;
  flex-direction: column;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
  border: 1px solid var(--arl-border-color);
  background: var(--arl-bg-container);
}

.widget-card :deep(.ant-card-body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 10px 14px;
  overflow: hidden;
}

.widget-extra-link {
  font-size: 12px;
  color: var(--arl-theme-color);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 2px;
  transition: opacity 0.2s;
}
.widget-extra-link:hover {
  opacity: 0.8;
  text-decoration: underline;
}

.widget-body-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  width: 100%;
  position: relative;
}

.echarts-widget-box {
  width: 100%;
  height: 100%;
  min-height: 180px;
}

.empty-widget-box {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 指纹列表 */
.finger-list-container {
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding-top: 2px;
}

.finger-rank-row {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 6px;
  transition: all 0.2s;
}
.finger-rank-row:hover {
  background-color: var(--arl-bg-light);
  transform: translateX(2px);
}

.finger-left-box {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 1 auto;
  max-width: 200px;
  min-width: 110px;
  flex-shrink: 0;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: #cbd5e1;
  flex-shrink: 0;
}
.rank-badge.rank-1 {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  box-shadow: 0 2px 6px rgba(245, 158, 11, 0.4);
}
.rank-badge.rank-2 {
  background: linear-gradient(135deg, #94a3b8 0%, #64748b 100%);
}
.rank-badge.rank-3 {
  background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
}

.finger-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--arl-text-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.finger-category-tag {
  font-size: 9px;
  padding: 0 4px;
  border-radius: 3px;
  line-height: 14px;
  border: 1px solid var(--arl-border-color);
  color: var(--arl-text-color);
  opacity: 0.7;
}
.finger-category-tag.cdn { background: rgba(24, 144, 255, 0.1); color: var(--arl-theme-color); }
.finger-category-tag.server { background: rgba(82, 196, 26, 0.1); color: #52c41a; }
.finger-category-tag.frame { background: rgba(114, 46, 209, 0.1); color: #722ed1; }

.finger-bar-wrap {
  flex: 1;
  min-width: 0;
}

.finger-progress-bar {
  height: 6px;
  background: var(--arl-border-color);
  border-radius: 3px;
  overflow: hidden;
}

.finger-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--arl-theme-color) 0%, rgba(var(--arl-theme-color-rgb, 24, 144, 255), 0.35) 100%);
  border-radius: 3px;
  transition: width 0.4s ease;
}

.finger-count-box {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 4px;
  width: 78px;
  flex-shrink: 0;
}

.finger-count-num {
  font-size: 12px;
  font-weight: 600;
  color: var(--arl-text-color);
  font-family: monospace;
}

.finger-pct-lbl {
  font-size: 10px;
  color: var(--arl-text-color);
  opacity: 0.45;
  font-family: monospace;
}

/* 漏洞引擎切换控件 */
.vuln-engine-switch {
  display: flex;
  align-items: center;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  border-radius: 5px;
  padding: 1px;
  gap: 2px;
}
.engine-pill {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  cursor: pointer;
  color: var(--arl-text-color);
  opacity: 0.6;
  transition: all 0.2s;
  user-select: none;
}
.engine-pill:hover { opacity: 0.9; }
.engine-pill.active {
  background: var(--arl-bg-container);
  color: var(--arl-theme-color);
  font-weight: 600;
  opacity: 1;
  box-shadow: 0 1px 2px rgba(0,0,0,0.06);
}

/* 实时任务流 */
.task-stream-container {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-card-item {
  padding: 6px 10px;
  border-radius: 8px;
  background: var(--arl-bg-light);
  cursor: pointer;
  transition: all 0.22s ease;
  border: 1px solid var(--arl-border-color);
}
.task-card-item:hover {
  border-color: var(--arl-theme-color);
  background: var(--arl-bg-container);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
}

.task-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 3px;
}

.task-name-box {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.task-type-badge {
  font-size: 9px;
  font-weight: 600;
  padding: 0 4px;
  border-radius: 3px;
  line-height: 15px;
  flex-shrink: 0;
}
.task-type-badge.ip {
  background: rgba(24, 144, 255, 0.12);
  color: var(--arl-theme-color);
}
.task-type-badge.domain {
  background: rgba(114, 46, 209, 0.12);
  color: #722ed1;
}
.task-type-badge.scan {
  background: rgba(82, 196, 26, 0.12);
  color: #52c41a;
}

.task-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--arl-text-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 12px;
  line-height: 16px;
  flex-shrink: 0;
  background: rgba(82, 196, 26, 0.1);
  color: #52c41a;
  border: 1px solid rgba(82, 196, 26, 0.25);
}
.task-status-pill .status-icon {
  font-size: 10px;
}
.task-status-pill.running {
  background: rgba(24, 144, 255, 0.1);
  color: var(--arl-theme-color);
  border-color: rgba(var(--arl-theme-color-rgb, 24, 144, 255), 0.25);
}
.task-status-pill.waiting {
  background: rgba(250, 140, 22, 0.1);
  color: #fa8c16;
  border-color: rgba(250, 140, 22, 0.25);
}
.task-status-pill.error {
  background: rgba(255, 77, 79, 0.1);
  color: #ff4d4f;
  border-color: rgba(255, 77, 79, 0.25);
}

.task-card-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.65;
}

.task-target {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.task-target code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  background: rgba(0, 0, 0, 0.04);
  padding: 1px 4px;
  border-radius: 3px;
  color: var(--arl-text-color);
}
.target-lbl {
  opacity: 0.6;
  margin-right: 2px;
}

.task-time-wrap {
  flex-shrink: 0;
  margin-left: 8px;
  font-family: monospace;
  font-size: 10px;
  display: flex;
  align-items: center;
}

.log-message-box {
  margin-top: 8px;
  padding: 12px;
  background-color: var(--arl-bg-light);
  border-radius: 6px;
  font-family: monospace;
  white-space: pre-wrap;
  word-wrap: break-word;
  color: var(--arl-text-color);
  border: 1px solid var(--arl-border-color);
}

@media (max-width: 991px) {
  .main-row,
  .widget-row {
    flex-direction: column;
    gap: 14px;
  }
  .main-col,
  .widget-col {
    width: 100%;
  }
  .main-card,
  .widget-card {
    height: auto;
    min-height: 255px;
  }
}

.page-error-note { color: #ff4d4f; margin-top: 2px; }
.page-warning-note { color: #faad14; margin-top: 2px; }
.page-small-label { font-size: 11px; }

.page-wide-text .vuln-matrix-header { flex-direction: column; align-items: flex-start; gap: 6px; }
.page-wide-text .vuln-total-unit { display: block; margin-left: 0; line-height: 1.5; }
.page-wide-text .critical-alert-tag { white-space: normal; max-width: 100%; }
.page-wide-text .cell-lbl { white-space: normal; line-height: 1.5; }
.page-wide-text .card-header-flex { flex-wrap: wrap; row-gap: 8px; }
.page-wide-text .trend-controls { flex-wrap: wrap; }
.page-wide-text .main-card :deep(.ant-card-head-title) { white-space: normal; }
@media (min-width: 992px) and (max-width: 1599px) {
  .page-wide-text .stat-row > :deep(.ant-col) { flex: 0 0 50%; max-width: 50%; }
}
</style>
