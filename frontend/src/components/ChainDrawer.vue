<template>
  <a-drawer
    :open="open"
    :title="null"
    :closable="false"
    :width="drawerWidth"
    placement="right"
    destroyOnClose
    rootClassName="chain-drawer-root"
    :bodyStyle="drawerBodyStyle"
    @close="handleClose"
  >
    <!-- 顶部双吸顶控制区：主头部 + 单行维度锚点导航条 -->
    <div class="chain-drawer-sticky-top">
      <div class="chain-drawer-header">
        <div class="drawer-header-left">
          <div class="drawer-header-badge">
            <compass-outlined class="drawer-compass-icon" />
          </div>
          <div class="drawer-header-titles">
            <div class="drawer-title-text">
              <span class="drawer-title-main">{{ assetText('assets.assetRelationshipProfile') }}</span>
              <a-tag color="blue" class="drawer-target-tag" :title="target">{{ target }}</a-tag>
            </div>
            <div class="drawer-subtitle-text">
              <template v-if="loading">
                {{ assetText('assets.loadingAssetRelationshipsAcrossCategories') }}
              </template>
              <template v-else-if="chainData">
                {{ assetText('assets.chainHitSummary', { hit: hitCategoryCount, totalCategories: metricChips.length, totalRecords }) }}
              </template>
              <template v-else>
                {{ assetText('assets.explore13AssetAndSecurityCategoriesClickA') }}
              </template>
            </div>
          </div>
        </div>
        <div class="drawer-header-right">
          <a-tooltip
            v-if="!loading && chainData"
            :title="showEmptySections
              ? assetText('assets.allCategoriesVisibleTooltip')
              : assetText('assets.showEmptyCategoriesTooltip', { count: emptyCategoryCount })"
          >
            <div class="chain-empty-toggle" :class="{ 'is-active': showEmptySections }">
              <a-switch v-model:checked="showEmptySections" size="small" />
              <span class="chain-empty-toggle-label" @click="showEmptySections = !showEmptySections">
                {{ assetText('assets.showEmptyCategories') }}
              </span>
              <span
                v-if="!showEmptySections && emptyCategoryCount > 0"
                class="chain-empty-count"
                @click="showEmptySections = !showEmptySections"
              >
                {{ emptyCategoryCount }}
              </span>
            </div>
          </a-tooltip>
          <a-tooltip :title="assetText('assets.copyTarget')">
            <a-button size="small" :disabled="!target" @click="handleCopyTarget">
              <template #icon><copy-outlined /></template>
            </a-button>
          </a-tooltip>
          <a-tooltip :title="assetText('assets.exportProfileJson')">
            <a-button size="small" :disabled="!chainData" @click="downloadChainJson">
              <template #icon><download-outlined /></template>
              {{ assetText('assets.exportProfile') }}
            </a-button>
          </a-tooltip>
          <a-button type="text" size="small" class="drawer-close-btn" @click="handleClose">
            <template #icon><close-outlined /></template>
          </a-button>
        </div>
      </div>

      <!-- 紧凑维度锚点条 (默认仅展示命中维度；支持横向滚动与正文滚动联动高亮) -->
      <div v-if="!loading && chainData && visibleNavChips.length > 0" class="chain-nav-bar">
        <div ref="navRailRef" class="chain-metric-row">
          <button
            v-for="chip in visibleNavChips"
            :key="chip.id"
            :ref="(el) => setChipRef(chip.id, el)"
            type="button"
            class="chain-metric-chip"
            :class="{
              'is-zero': chip.count === 0,
              'is-active': activeSectionId === chip.id
            }"
            :title="assetText('assets.jumpToSection', { section: chip.label })"
            @click="scrollToSection(chip.id)"
          >
            <component :is="chip.icon" :style="{ color: chip.color }" class="metric-icon" />
            <span class="metric-label">{{ chip.label }}</span>
            <b :class="{ 'zero-num': chip.count === 0 }">{{ chip.count }}</b>
          </button>
        </div>
      </div>
    </div>

    <!-- 独立滚动正文容器 -->
    <div ref="scrollContainerRef" class="chain-drawer-scroll-wrapper" @scroll="handleScroll">
      <div class="chain-drawer-body">
        <!-- 1. 首次加载或切换目标时的骨架屏，保持布局稳定 -->
        <div v-if="loading" class="chain-skeleton-wrap">
          <div class="chain-skeleton-pills">
            <span v-for="i in 6" :key="i" class="chain-skeleton-pill" />
          </div>
          <a-card v-for="n in 3" :key="n" :bordered="false" class="drawer-chain-card">
            <a-skeleton active :title="{ width: '32%' }" :paragraph="{ rows: n === 1 ? 4 : 3 }" />
          </a-card>
        </div>

        <!-- 2. 请求失败或无数据对象时展示统一空状态 -->
        <div v-else-if="!chainData" class="drawer-empty-box">
          <ArlEmpty :description="assetText('assets.noRelatedAssetRecordsFoundForThisTarget')">
            <div class="drawer-empty-subtip">
              {{ assetText('assets.theTargetMayNotHaveCompletedDetailedDiscovery') }}
            </div>
          </ArlEmpty>
        </div>

        <!-- 3. 全部 13 维均无记录且未开启显示空维度时，提供一键展开入口 -->
        <div v-else-if="totalRecords === 0 && !showEmptySections" class="drawer-empty-box">
          <ArlEmpty :description="assetText('assets.noRelatedAssetRecordsFoundForThisTarget')">
            <div class="drawer-empty-subtip">
              {{ assetText('assets.theTargetMayNotHaveCompletedDetailedDiscovery') }}
            </div>
            <div class="drawer-empty-action">
              <a-button size="small" @click="showEmptySections = true">
                {{ assetText('assets.viewAllCategories') }}
              </a-button>
            </div>
          </ArlEmpty>
        </div>

        <!-- 4. 维度详情卡片列表（默认仅渲染有数据的维度） -->
        <div v-else class="chain-sections-container">
          <!-- 1. 站点基础信息与截图 -->
          <a-card v-if="shouldShowSection(chainData.site?.length)" id="chain-sec-site" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <global-outlined style="color: #1890ff;" />
                <span>{{ assetText('assets.websiteInformation') }}</span>
                <a-badge :count="chainData.site?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.site?.length, '#1890ff')" />
              </div>
            </template>
            <ArlEmpty v-if="!chainData.site || chainData.site.length === 0" compact :description="assetText('assets.noRelatedWebsitesFound')" />
            <div v-else class="drawer-site-list">
              <div v-for="(siteItem, idx) in chainData.site" :key="idx" class="drawer-site-item">
                <div class="drawer-site-meta">
                  <div class="site-title-row">
                    <img v-if="siteItem.favicon && siteItem.favicon.data" :src="`data:image/png;base64,${siteItem.favicon.data}`" class="drawer-favicon" />
                    <a :href="siteItem.site" target="_blank" rel="noopener noreferrer" class="site-link">{{ siteItem.site }}</a>
                    <a-tag :color="siteItem.status === 200 ? 'success' : (siteItem.status >= 400 ? 'error' : 'default')">
                      HTTP {{ siteItem.status || '-' }}
                    </a-tag>
                  </div>
                  <div class="site-kv-grid">
                    <div class="kv-item"><span class="kv-label">{{ assetText('assets.title') }}</span><span class="kv-value">{{ siteItem.title || '-' }}</span></div>
                    <div class="kv-item"><span class="kv-label">{{ assetText('assets.webServerLabel') }}</span><span class="kv-value">{{ siteItem.http_server || '-' }}</span></div>
                    <div class="kv-item"><span class="kv-label">{{ assetText('assets.ipLabel') }}</span><span class="kv-value font-mono">{{ siteItem.ip || '-' }}</span></div>
                    <div class="kv-item"><span class="kv-label">{{ assetText('assets.updated') }}</span><span class="kv-value">{{ siteItem.update_date || siteItem.save_date || '-' }}</span></div>
                  </div>
                  <div v-if="siteItem.finger && siteItem.finger.length" class="site-finger-row">
                    <span class="kv-label">{{ assetText('assets.fingerprints') }}</span>
                    <a-tag v-for="(f, fIdx) in siteItem.finger" :key="f.name || f || fIdx" color="blue">{{ f.name || f }}</a-tag>
                  </div>
                </div>
                <div v-if="siteItem.screenshot" class="drawer-site-shot">
                  <AuthenticatedImage :src="`/api${siteItem.screenshot}`" :alt="assetText('tasks.screenshot')" />
                </div>
              </div>
            </div>
          </a-card>

          <!-- 2. 子域名与解析记录 -->
          <a-card v-if="shouldShowSection(chainData.domain_records?.length)" id="chain-sec-domain" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <link-outlined style="color: #52c41a;" />
                <span>{{ assetText('assets.subdomainDnsRecords') }}</span>
                <a-badge :count="chainData.domain_records?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.domain_records?.length, '#52c41a')" />
              </div>
            </template>
            <ArlEmpty v-if="!chainData.domain_records || chainData.domain_records.length === 0" compact :description="assetText('assets.noSubdomainDnsRecordsFound')" />
            <a-table
              v-else
              :dataSource="chainData.domain_records"
              :columns="domainCols"
              :pagination="tablePagination"
              :scroll="{ x: 'max-content' }"
              size="small"
              :rowKey="(r, i) => i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'domain'">
                  <span class="font-mono font-bold">{{ record.domain }}</span>
                </template>
                <template v-else-if="column.key === 'ips'">
                  <div v-if="Array.isArray(record.ips)" class="cell-tag-wrap">
                    <span v-for="(ip, idx) in record.ips" :key="idx" class="font-mono font-tag">{{ ip }}</span>
                  </div>
                  <span v-else class="font-mono">{{ record.ips || '-' }}</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 3. IP 与网络归属 -->
          <a-card v-if="shouldShowSection(chainData.ip?.length)" id="chain-sec-ip" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <cloud-server-outlined style="color: #722ed1;" />
                <span>{{ assetText('assets.ipsAndNetworkOwnership') }}</span>
                <a-badge :count="chainData.ip?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.ip?.length, '#722ed1')" />
              </div>
            </template>
            <ArlEmpty v-if="!chainData.ip || chainData.ip.length === 0" compact :description="assetText('assets.noRelatedIpAssetsFound')" />
            <a-table
              v-else
              :dataSource="chainData.ip"
              :columns="ipCols"
              :pagination="tablePagination"
              :scroll="{ x: 'max-content' }"
              size="small"
              :rowKey="(r, i) => i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'ip'">
                  <span class="font-mono font-bold">{{ record.ip }}</span>
                </template>
                <template v-else-if="column.key === 'cdn'">
                  <a-tag v-if="record.is_cdn || record.cdn_name" color="blue">
                    {{ record.cdn_name || assetText('tasks.cdnNode') }}
                  </a-tag>
                  <a-tag v-else color="green">
                    {{ assetText('tasks.originServer') }}
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'port_info'">
                  <span class="font-mono">{{ record.port_info && record.port_info.length ? record.port_info.map(p => p.port_id).join(', ') : '-' }}</span>
                </template>
                <template v-else-if="column.key === 'geo'">
                  <span>{{ formatGeo(record.geo_city) }}</span>
                </template>
                <template v-else-if="column.key === 'asn'">
                  <span>{{ record.geo_asn?.organization || '-' }}</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 4. SSL 证书 -->
          <a-card v-if="shouldShowSection(chainData.cert?.length)" id="chain-sec-cert" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <safety-certificate-outlined style="color: #13c2c2;" />
                <span>{{ assetText('assets.sslCertificates') }}</span>
                <a-badge :count="chainData.cert?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.cert?.length, '#13c2c2')" />
              </div>
            </template>
            <ArlEmpty v-if="!chainData.cert || chainData.cert.length === 0" compact :description="assetText('assets.noRelatedSslCertificatesFound')" />
            <div v-else class="drawer-cert-list">
              <div v-for="(certItem, idx) in chainData.cert" :key="idx" class="drawer-cert-item">
                <div class="cert-host-tag">{{ certItem.ip || certItem.host }}{{ certItem.port ? ':' + certItem.port : '' }}</div>
                <div v-if="certItem.cert" class="cert-fields">
                  <div class="cert-field-row"><b>{{ assetText('assets.subject') }}</b><span>{{ certItem.cert.subject_dn || '-' }}</span></div>
                  <div class="cert-field-row"><b>{{ assetText('assets.issuer') }}</b><span>{{ certItem.cert.issuer_dn || '-' }}</span></div>
                  <div v-if="certItem.cert.extensions?.subjectAltName" class="cert-field-row">
                    <b>{{ assetText('assets.subjectAlternativeNamesSan') }}</b>
                    <span class="cert-san-value font-mono">{{ certItem.cert.extensions.subjectAltName }}</span>
                  </div>
                  <div class="cert-field-row"><b>{{ assetText('assets.validity') }}</b><span>{{ certItem.cert.validity?.start || '-' }} {{ assetText('tasks.to') }} {{ certItem.cert.validity?.end || '-' }}</span></div>
                </div>
              </div>
            </div>
          </a-card>

          <!-- 5. 系统服务 -->
          <a-card v-if="shouldShowSection(chainData.service?.length)" id="chain-sec-service" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <api-outlined style="color: #fa8c16;" />
                <span>{{ assetText('assets.openNetworkServices') }}</span>
                <a-badge :count="chainData.service?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.service?.length, '#fa8c16')" />
              </div>
            </template>
            <ArlEmpty v-if="!chainData.service || chainData.service.length === 0" compact :description="assetText('assets.noOpenNetworkServicesFound')" />
            <div v-else class="drawer-services-grid">
              <div v-for="(srv, idx) in chainData.service" :key="idx" class="service-pill">
                <div class="service-name-tag">{{ srv.service_name || 'service' }}</div>
                <div v-for="(inf, i) in (srv.service_info || [])" :key="i" class="service-endpoint">
                  <span class="font-mono">{{ inf.ip }}:{{ inf.port_id }}</span>
                  <span v-if="inf.product" class="service-product">{{ inf.product }}</span>
                </div>
              </div>
            </div>
          </a-card>

          <!-- 6. 文件泄露 -->
          <a-card v-if="shouldShowSection(chainData.fileleak?.length)" id="chain-sec-fileleak" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <file-search-outlined style="color: #faad14;" />
                <span>{{ assetText('assets.sensitiveFileDisclosures') }}</span>
                <a-badge :count="chainData.fileleak?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.fileleak?.length, '#faad14')" />
              </div>
            </template>
            <ArlEmpty v-if="!chainData.fileleak || chainData.fileleak.length === 0" compact :description="assetText('assets.noSuspectedSensitiveFileDisclosuresFound')" />
            <a-table
              v-else
              :dataSource="chainData.fileleak"
              :columns="fileleakCols"
              :pagination="tablePagination"
              :scroll="{ x: 'max-content' }"
              size="small"
              :rowKey="(r, i) => r.url || i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'url'">
                  <a :href="record.url" target="_blank" rel="noopener noreferrer" class="drawer-break-link font-mono">{{ record.url }}</a>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 7. URL 信息 -->
          <a-card v-if="shouldShowSection(chainData.url?.length)" id="chain-sec-url" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <deployment-unit-outlined style="color: #2f54eb;" />
                <span>{{ assetText('assets.relatedDiscoveredUrls') }}</span>
                <a-badge :count="chainData.url?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.url?.length, '#2f54eb')" />
              </div>
            </template>
            <ArlEmpty v-if="!chainData.url || chainData.url.length === 0" compact :description="assetText('assets.noRelatedDiscoveredUrlsFound')" />
            <a-table
              v-else
              :dataSource="chainData.url"
              :columns="urlCols"
              :pagination="tablePagination"
              :scroll="{ x: 'max-content' }"
              size="small"
              :rowKey="(r, i) => r.url || i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'url'">
                  <a :href="record.url" target="_blank" rel="noopener noreferrer" class="drawer-break-link font-mono">{{ record.url }}</a>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 8. C 段网段 -->
          <a-card v-if="shouldShowSection(chainData.cip?.length)" id="chain-sec-cip" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <cluster-outlined style="color: #eb2f96;" />
                <span>{{ assetText('assets.relatedCClassNetworks') }}</span>
                <a-badge :count="chainData.cip?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.cip?.length, '#eb2f96')" />
              </div>
            </template>
            <ArlEmpty v-if="!chainData.cip || chainData.cip.length === 0" compact :description="assetText('assets.noRelatedCClassNetworksFound')" />
            <a-table
              v-else
              :dataSource="chainData.cip"
              :columns="cipCols"
              :pagination="tablePagination"
              :scroll="{ x: 'max-content' }"
              size="small"
              :rowKey="(r, i) => r.cidr_ip || i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'cidr_ip'">
                  <span class="font-mono font-bold">{{ record.cidr_ip || '-' }}</span>
                </template>
                <template v-else-if="column.key === 'ip_count'">
                  <a-tag color="purple" class="font-mono">{{ assetText('assets.ipCount', { count: record.ip_count ?? (record.ip_list?.length || 0) }) }}</a-tag>
                </template>
                <template v-else-if="column.key === 'domain_count'">
                  <a-tag color="blue" class="font-mono">{{ assetText('assets.domainCount', { count: record.domain_count ?? (record.domain_list?.length || 0) }) }}</a-tag>
                </template>
                <template v-else-if="column.key === 'update_date'">
                  <span class="drawer-muted-time">{{ record.update_date || record.save_date || '-' }}</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 9. 指纹统计 -->
          <a-card v-if="shouldShowSection(statFingerList.length)" id="chain-sec-stat-finger" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <tag-outlined style="color: #1d39c4;" />
                <span>{{ assetText('assets.relatedFingerprintStatistics') }}</span>
                <a-badge :count="statFingerList.length" :show-zero="true" :number-style="getBadgeStyle(statFingerList.length, '#1d39c4')" />
              </div>
            </template>
            <ArlEmpty v-if="statFingerList.length === 0" compact :description="assetText('assets.noRelatedTechnologyOrComponentFingerprintsFound')" />
            <a-table
              v-else
              :dataSource="statFingerList"
              :columns="fingerCols"
              :pagination="tablePagination"
              :scroll="{ x: 'max-content' }"
              size="small"
              :rowKey="(r, i) => r.finger_name || i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'finger_name'">
                  <a-tag color="blue">{{ record.finger_name }}</a-tag>
                </template>
                <template v-else-if="column.key === 'cnt'">
                  <span class="font-mono font-bold">{{ assetText('assets.websiteCount', { count: record.cnt }) }}</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 10. WIH 敏感信息 -->
          <a-card v-if="shouldShowSection(chainData.wih?.length)" id="chain-sec-wih" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <radar-chart-outlined style="color: #fa8c16;" />
                <span>WEB Info Hunter (WIH)</span>
                <a-badge :count="chainData.wih?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.wih?.length, '#fa8c16')" />
              </div>
            </template>
            <ArlEmpty v-if="!chainData.wih || chainData.wih.length === 0" compact :description="assetText('assets.noWebInfoHunterWihDisclosureRecordsFound')" />
            <a-table
              v-else
              :dataSource="chainData.wih"
              :columns="wihCols"
              :pagination="tablePagination"
              :scroll="{ x: 'max-content' }"
              size="small"
              :rowKey="(r, i) => r._id || i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'content'">
                  <span class="wih-content-text font-mono">
                    {{ record.content }}
                  </span>
                </template>
                <template v-else-if="column.key === 'source'">
                  <a v-if="record.source || record.site" :href="record.source || record.site" target="_blank" rel="noopener noreferrer" class="drawer-break-link font-mono">
                    {{ record.source || record.site }}
                  </a>
                  <span v-else>-</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 11. 应用风险漏洞 -->
          <a-card v-if="shouldShowSection(chainData.vuln?.length)" id="chain-sec-vuln" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <bug-outlined style="color: #f5222d;" />
                <span>{{ assetText('assets.applicationVulnerabilitiesPoc') }}</span>
                <a-badge :count="chainData.vuln?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.vuln?.length, '#f5222d')" />
              </div>
            </template>
            <ArlEmpty v-if="!chainData.vuln || chainData.vuln.length === 0" compact :description="assetText('assets.noApplicationVulnerabilitiesDetected')" />
            <div v-else class="drawer-vuln-list">
              <div v-for="(v, idx) in chainData.vuln" :key="'v-'+idx" class="vuln-item-card">
                <div class="vuln-header">
                  <a-tag color="error">{{ assetText('tasks.risks') }}</a-tag>
                  <span class="vuln-name">{{ v.vul_name || v.title || assetText('assets.unknownRisk') }}</span>
                </div>
                <div class="vuln-target font-mono">{{ v.target }}</div>
              </div>
            </div>
          </a-card>

          <!-- 12. 服务 (Python NPOC) -->
          <a-card v-if="shouldShowSection(chainData.npoc_service?.length)" id="chain-sec-npoc" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <code-outlined style="color: #722ed1;" />
                <span>{{ assetText('assets.serviceDetectionPythonNpoc') }}</span>
                <a-badge :count="chainData.npoc_service?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.npoc_service?.length, '#722ed1')" />
              </div>
            </template>
            <ArlEmpty v-if="!chainData.npoc_service || chainData.npoc_service.length === 0" compact :description="assetText('assets.noPythonNpocServiceRecordsFound')" />
            <a-table
              v-else
              :dataSource="chainData.npoc_service"
              :columns="npocCols"
              :pagination="tablePagination"
              :scroll="{ x: 'max-content' }"
              size="small"
              :rowKey="(r, i) => r._id || i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'scheme'">
                  <a-tag color="purple">{{ record.scheme || '-' }}</a-tag>
                </template>
                <template v-else-if="column.key === 'target'">
                  <span class="font-mono drawer-break-link">{{ record.target || '-' }}</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 13. Nuclei 扫描发现 -->
          <a-card v-if="shouldShowSection(chainData.nuclei_result?.length)" id="chain-sec-nuclei" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <fire-outlined style="color: #fa541c;" />
                <span>{{ assetText('assets.nucleiVulnerabilityFindings') }}</span>
                <a-badge :count="chainData.nuclei_result?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.nuclei_result?.length, '#fa541c')" />
              </div>
            </template>
            <ArlEmpty v-if="!chainData.nuclei_result || chainData.nuclei_result.length === 0" compact :description="assetText('assets.noNucleiVulnerabilitySignaturesMatched')" />
            <div v-else class="drawer-vuln-list">
              <div
                v-for="(n, idx) in chainData.nuclei_result"
                :key="'n-'+idx"
                class="vuln-item-card"
                :style="{ borderLeftColor: getSeverityColor(n.vuln_severity || n.vul_severity) }"
              >
                <div class="vuln-header">
                  <a-tag color="volcano">Nuclei</a-tag>
                  <span class="vuln-name">{{ n.vuln_name || n.template_id }}</span>
                  <a-tag :color="getSeverityColor(n.vuln_severity || n.vul_severity)">
                    {{ (n.vuln_severity || n.vul_severity || 'HIGH').toUpperCase() }}
                  </a-tag>
                </div>
                <div class="vuln-target font-mono">{{ n.vuln_url || n.target }}</div>
              </div>
            </div>
          </a-card>
        </div>
      </div>
    </div>

    <!-- 右下角悬浮回到顶端按钮 -->
    <transition name="fade">
      <a-tooltip v-if="showBackTop" :title="assetText('assets.backToTop')" placement="left">
        <button
          type="button"
          class="chain-back-top-btn"
          :aria-label="assetText('assets.backToTop')"
          @click="scrollToTop"
        >
          <span class="back-top-circle">
            <vertical-align-top-outlined class="back-top-icon" />
          </span>
        </button>
      </a-tooltip>
    </transition>
  </a-drawer>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { message } from 'ant-design-vue';
import dayjs from 'dayjs';
import {
  CompassOutlined,
  GlobalOutlined,
  LinkOutlined,
  CloudServerOutlined,
  ClusterOutlined,
  SafetyCertificateOutlined,
  ApiOutlined,
  BugOutlined,
  CopyOutlined,
  CloseOutlined,
  DownloadOutlined,
  FileSearchOutlined,
  DeploymentUnitOutlined,
  TagOutlined,
  RadarChartOutlined,
  CodeOutlined,
  FireOutlined,
  VerticalAlignTopOutlined
} from '@ant-design/icons-vue';
import request from '../utils/request';
import AuthenticatedImage from './AuthenticatedImage.vue';
import { formatGeo } from '../utils/formatGeo';
import { copyText } from '../utils/clipboard';

const { t: assetText } = useI18n({ useScope: 'global' });

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  target: {
    type: String,
    default: ''
  },
  scopeId: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:open', 'close']);

const loading = ref(false);
const chainData = ref(null);
const scrollContainerRef = ref(null);
const navRailRef = ref(null);
const showBackTop = ref(false);
const showEmptySections = ref(false);
const activeSectionId = ref('');
const viewportWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1280);

const chipRefs = new Map();
let programmaticScrollTimer = null;
let isProgrammaticScroll = false;
let fetchSeq = 0;

const drawerBodyStyle = {
  padding: 0,
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  overflow: 'hidden',
  background: 'var(--arl-bg-layout)',
  position: 'relative'
};

const tablePagination = {
  defaultPageSize: 10,
  hideOnSinglePage: true,
  showSizeChanger: false,
  size: 'small'
};

const handleWindowResize = () => {
  viewportWidth.value = window.innerWidth;
};

onMounted(() => {
  window.addEventListener('resize', handleWindowResize, { passive: true });
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleWindowResize);
  if (programmaticScrollTimer) {
    clearTimeout(programmaticScrollTimer);
    programmaticScrollTimer = null;
  }
  chipRefs.clear();
});

const drawerWidth = computed(() => {
  return viewportWidth.value > 1400 ? '900px' : (viewportWidth.value > 992 ? '800px' : '94vw');
});

const setChipRef = (id, el) => {
  if (el) {
    chipRefs.set(id, el);
  } else {
    chipRefs.delete(id);
  }
};

const syncActiveChipIntoView = (secId) => {
  const chipEl = chipRefs.get(secId);
  if (chipEl && typeof chipEl.scrollIntoView === 'function') {
    chipEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
  }
};

const updateActiveSectionFromScroll = () => {
  const container = scrollContainerRef.value;
  const chips = visibleNavChips.value;
  if (!container || chips.length === 0) return;

  const atBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 12;
  if (atBottom) {
    const lastId = chips[chips.length - 1].id;
    if (activeSectionId.value !== lastId) {
      activeSectionId.value = lastId;
      syncActiveChipIntoView(lastId);
    }
    return;
  }

  const thresholdTop = container.getBoundingClientRect().top + 28;
  let currentId = chips[0].id;
  for (const chip of chips) {
    const el = document.getElementById(chip.id);
    if (el && el.getBoundingClientRect().top <= thresholdTop) {
      currentId = chip.id;
    }
  }
  if (activeSectionId.value !== currentId) {
    activeSectionId.value = currentId;
    syncActiveChipIntoView(currentId);
  }
};

const handleScroll = (e) => {
  const scrollTop = e?.target?.scrollTop ?? 0;
  showBackTop.value = scrollTop > 200;
  if (!isProgrammaticScroll) {
    updateActiveSectionFromScroll();
  }
};

const scrollToTop = () => {
  if (scrollContainerRef.value) {
    scrollContainerRef.value.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  }
};

const domainCols = [
  { get title() { return assetText('tasks.subdomains'); }, dataIndex: 'domain', key: 'domain' },
  { get title() { return assetText('tasks.type'); }, dataIndex: 'type', key: 'type', width: 90, align: 'center' },
  { get title() { return assetText('assets.resolvedIps'); }, key: 'ips' }
];

const ipCols = [
  { title: 'IP', dataIndex: 'ip', key: 'ip', width: 140 },
  { title: 'CDN', key: 'cdn', width: 140 },
  { get title() { return assetText('tasks.openPorts'); }, key: 'port_info' },
  { get title() { return assetText('assets.location'); }, key: 'geo', width: 140 },
  { get title() { return assetText('assets.asOrganization'); }, key: 'asn' }
];

const cipCols = [
  { get title() { return assetText('assets.cClassNetwork'); }, dataIndex: 'cidr_ip', key: 'cidr_ip', width: 180 },
  { get title() { return assetText('tasks.associatedIps'); }, key: 'ip_count', width: 120, align: 'center' },
  { get title() { return assetText('tasks.associatedDomains'); }, key: 'domain_count', width: 120, align: 'center' },
  { get title() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', width: 160 }
];

const npocCols = [
  { get title() { return assetText('tasks.protocol'); }, dataIndex: 'scheme', key: 'scheme', width: 100, align: 'center' },
  { get title() { return assetText('tasks.target'); }, dataIndex: 'target', key: 'target' }
];

const fileleakCols = [
  { title: 'URL', key: 'url' },
  { get title() { return assetText('tasks.title'); }, dataIndex: 'title', key: 'title', width: 160 },
  { get title() { return assetText('tasks.statusCode'); }, dataIndex: 'status_code', key: 'status_code', width: 80, align: 'center' },
  { get title() { return assetText('assets.updatedAtLabel'); }, dataIndex: 'update_date', key: 'update_date', width: 160 }
];

const urlCols = [
  { title: 'URL', key: 'url' },
  { get title() { return assetText('tasks.title'); }, dataIndex: 'title', key: 'title', width: 160 },
  { get title() { return assetText('tasks.statusCode'); }, dataIndex: 'status_code', key: 'status_code', width: 80, align: 'center' },
  { get title() { return assetText('tasks.source'); }, dataIndex: 'source', key: 'source', width: 110 },
  { get title() { return assetText('assets.updatedAtLabel'); }, dataIndex: 'update_date', key: 'update_date', width: 160 }
];

const fingerCols = [
  { get title() { return assetText('assets.fingerprintComponent'); }, dataIndex: 'finger_name', key: 'finger_name' },
  { get title() { return assetText('assets.relatedWebsites'); }, key: 'cnt', width: 140, align: 'center' }
];

const wihCols = [
  { get title() { return assetText('tasks.type'); }, dataIndex: 'record_type', key: 'record_type', width: 100 },
  { get title() { return assetText('assets.sensitiveContent'); }, dataIndex: 'content', key: 'content' },
  { get title() { return assetText('assets.sourceJavascriptWebsite'); }, key: 'source', width: 220 },
  { get title() { return assetText('assets.updatedAtLabel'); }, dataIndex: 'update_date', key: 'update_date', width: 160 }
];

// 动态汇总当前目标关联站点的技术栈与指纹
const statFingerList = computed(() => {
  if (!chainData.value || !Array.isArray(chainData.value.site)) return [];
  const map = {};
  for (const s of chainData.value.site) {
    if (Array.isArray(s.finger)) {
      for (const f of s.finger) {
        const name = f?.name || f;
        if (name && typeof name === 'string' && name.trim()) {
          map[name.trim()] = (map[name.trim()] || 0) + 1;
        }
      }
    }
  }
  return Object.entries(map)
    .map(([finger_name, cnt]) => ({ finger_name, cnt }))
    .sort((a, b) => b.cnt - a.cnt);
});

// 13 维统计指标与锚点导航列表
const metricChips = computed(() => {
  if (!chainData.value) return [];
  const d = chainData.value;
  return [
    { id: 'chain-sec-site', label: assetText('tasks.websites'), count: d.site?.length || 0, icon: GlobalOutlined, color: '#1890ff' },
    { id: 'chain-sec-domain', label: assetText('tasks.subdomains'), count: d.domain_records?.length || 0, icon: LinkOutlined, color: '#52c41a' },
    { id: 'chain-sec-ip', label: 'IP', count: d.ip?.length || 0, icon: CloudServerOutlined, color: '#722ed1' },
    { id: 'chain-sec-cert', label: assetText('assets.sslCertificates'), count: d.cert?.length || 0, icon: SafetyCertificateOutlined, color: '#13c2c2' },
    { id: 'chain-sec-service', label: assetText('tasks.services'), count: d.service?.length || 0, icon: ApiOutlined, color: '#fa8c16' },
    { id: 'chain-sec-fileleak', label: assetText('tasks.fileDisclosure'), count: d.fileleak?.length || 0, icon: FileSearchOutlined, color: '#faad14' },
    { id: 'chain-sec-url', label: assetText('tasks.urls'), count: d.url?.length || 0, icon: DeploymentUnitOutlined, color: '#2f54eb' },
    { id: 'chain-sec-cip', label: assetText('tasks.cClassNetworks'), count: d.cip?.length || 0, icon: ClusterOutlined, color: '#eb2f96' },
    { id: 'chain-sec-stat-finger', label: assetText('tasks.fingerprintStatistics'), count: statFingerList.value.length, icon: TagOutlined, color: '#1d39c4' },
    { id: 'chain-sec-wih', label: 'WIH', count: d.wih?.length || 0, icon: RadarChartOutlined, color: '#fa8c16' },
    { id: 'chain-sec-vuln', label: assetText('tasks.risks'), count: d.vuln?.length || 0, icon: BugOutlined, color: '#f5222d' },
    { id: 'chain-sec-npoc', label: assetText('assets.pythonPluginServicesLabel'), count: d.npoc_service?.length || 0, icon: CodeOutlined, color: '#722ed1' },
    { id: 'chain-sec-nuclei', label: 'nuclei', count: d.nuclei_result?.length || 0, icon: FireOutlined, color: '#fa541c' }
  ];
});

const visibleNavChips = computed(() => {
  return showEmptySections.value
    ? metricChips.value
    : metricChips.value.filter((chip) => chip.count > 0);
});

const hitCategoryCount = computed(() => metricChips.value.filter((c) => c.count > 0).length);
const emptyCategoryCount = computed(() => metricChips.value.length - hitCategoryCount.value);
const totalRecords = computed(() => metricChips.value.reduce((sum, c) => sum + c.count, 0));

const shouldShowSection = (count) => showEmptySections.value || (count || 0) > 0;

watch(visibleNavChips, (chips) => {
  nextTick(() => {
    if (!chips.length) {
      activeSectionId.value = '';
      return;
    }
    if (!chips.some((chip) => chip.id === activeSectionId.value)) {
      activeSectionId.value = chips[0].id;
    }
  });
});

// 平滑滚动定位到独立滚动容器内的目标资产卡片
const scrollToSection = (secId) => {
  const container = scrollContainerRef.value;
  const el = document.getElementById(secId);
  if (!container || !el) return;

  activeSectionId.value = secId;
  syncActiveChipIntoView(secId);

  isProgrammaticScroll = true;
  if (programmaticScrollTimer) {
    clearTimeout(programmaticScrollTimer);
  }
  programmaticScrollTimer = setTimeout(() => {
    isProgrammaticScroll = false;
    programmaticScrollTimer = null;
  }, 480);

  const delta = el.getBoundingClientRect().top - container.getBoundingClientRect().top;
  const targetTop = Math.max(0, container.scrollTop + delta - 16);
  container.scrollTo({ top: targetTop, behavior: 'smooth' });
};

const getBadgeStyle = (cnt, activeColor) => {
  if (cnt && cnt > 0) {
    return { backgroundColor: activeColor };
  }
  return { backgroundColor: 'var(--arl-bg-hover)', color: 'var(--arl-text-secondary)' };
};

const getSeverityColor = (sev) => {
  const s = String(sev || '').toLowerCase();
  if (s === 'critical') return '#f5222d';
  if (s === 'high') return '#fa541c';
  if (s === 'medium') return '#fa8c16';
  if (s === 'low') return '#faad14';
  return '#1890ff';
};

const fetchChainData = async () => {
  if (!props.target || !props.scopeId) return;
  const currentSeq = ++fetchSeq;
  loading.value = true;
  chainData.value = null;
  try {
    const res = await request.get('/asset_site/subdomain_chain/', {
      params: {
        scope_id: props.scopeId,
        domain: props.target.trim()
      }
    });
    if (currentSeq !== fetchSeq) return;
    if (res.code === 200) {
      chainData.value = res.data || {};
    } else {
      message.error(res.message || assetText('assets.failedToLoadAssetProfile'));
    }
  } catch (e) {
    if (currentSeq === fetchSeq) {
      message.error(assetText('tasks.networkRequestFailed'));
    }
  } finally {
    if (currentSeq === fetchSeq) {
      loading.value = false;
    }
  }
};

watch(
  () => [props.open, props.target],
  ([isOpen, newTarget], prev) => {
    const prevOpen = prev?.[0];
    const prevTarget = prev?.[1];
    if (!isOpen) {
      showEmptySections.value = false;
      activeSectionId.value = '';
      showBackTop.value = false;
      if (programmaticScrollTimer) {
        clearTimeout(programmaticScrollTimer);
        programmaticScrollTimer = null;
        isProgrammaticScroll = false;
      }
      fetchSeq += 1;
      return;
    }

    if (!prevOpen || newTarget !== prevTarget) {
      showBackTop.value = false;
      activeSectionId.value = '';
      nextTick(() => {
        if (scrollContainerRef.value) {
          scrollContainerRef.value.scrollTop = 0;
        }
      });
      if (newTarget) {
        fetchChainData();
      } else {
        fetchSeq += 1;
        chainData.value = null;
        loading.value = false;
      }
    }
  },
  { immediate: true }
);

const handleClose = () => {
  emit('update:open', false);
  emit('close');
};

const handleCopyTarget = async () => {
  const ok = await copyText(props.target);
  if (ok) message.success(assetText('assets.targetCopied') + props.target);
};

const downloadChainJson = () => {
  if (!chainData.value) {
    message.warning(assetText('assets.noProfileDataToExport'));
    return;
  }
  try {
    const jsonStr = JSON.stringify(chainData.value, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json;charset=utf-8' });
    const blobUrl = URL.createObjectURL(blob);
    const downloadAnchor = document.createElement('a');
    const safeTarget = String(props.target || 'target').replace(/[/:\\?*"<>|]+/g, '_');
    const filename = `arl_chain_${safeTarget}_${dayjs().format('YYYYMMDD_HHmmss')}.json`;
    downloadAnchor.href = blobUrl;
    downloadAnchor.download = filename;
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    URL.revokeObjectURL(blobUrl);
    message.success(assetText('assets.assetProfileExportedTarget', { target: filename }));
  } catch (err) {
    message.error(assetText('assets.failedToExportAssetProfile'));
  }
};
</script>

<style scoped>
.chain-drawer-root :deep(.ant-drawer-body) {
  padding: 0;
  background: var(--arl-bg-layout);
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
}

.chain-drawer-sticky-top {
  flex-shrink: 0;
  background: var(--arl-bg-card);
  border-bottom: 1px solid var(--arl-border-color);
  z-index: 10;
}

.chain-drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
}

.drawer-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  flex: 1;
}

.drawer-header-badge {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--arl-theme-soft-bg);
  border: 1px solid var(--arl-theme-soft-border);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.drawer-compass-icon {
  font-size: 19px;
  color: var(--arl-theme-color);
}

.drawer-header-titles {
  min-width: 0;
  flex: 1;
}

.drawer-title-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--arl-text-color);
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex-wrap: wrap;
}

.drawer-title-main {
  flex-shrink: 0;
}

.drawer-target-tag {
  font-family: var(--arl-font-mono);
  font-size: 12px;
  border-radius: 4px;
  margin-inline-end: 0;
  max-width: min(360px, 100%);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
}

.drawer-subtitle-text {
  font-size: 12px;
  color: var(--arl-text-secondary);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.drawer-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.drawer-close-btn {
  color: var(--arl-text-secondary);
}

.chain-empty-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 24px;
  padding: 0 8px;
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
  background: var(--arl-bg-subtle);
  font-size: 12px;
  color: var(--arl-text-secondary);
  user-select: none;
  transition: border-color 0.2s ease, background-color 0.2s ease, color 0.2s ease;
}

.chain-empty-toggle.is-active {
  border-color: var(--arl-theme-soft-border);
  background: var(--arl-theme-soft-bg);
  color: var(--arl-theme-color);
}

.chain-empty-toggle-label {
  cursor: pointer;
  white-space: nowrap;
}

.chain-empty-count {
  cursor: pointer;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--arl-bg-hover);
  color: var(--arl-text-secondary);
  font-family: var(--arl-font-mono);
  font-size: 11px;
  line-height: 16px;
}

.chain-nav-bar {
  border-top: 1px solid var(--arl-border-color);
  padding: 8px 20px;
  background: var(--arl-bg-subcard);
}

.chain-metric-row {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  padding-bottom: 2px;
}

.chain-metric-row::-webkit-scrollbar {
  height: 4px;
}

.chain-metric-row::-webkit-scrollbar-thumb {
  background: var(--arl-border-color);
  border-radius: 999px;
}

.chain-metric-chip {
  appearance: none;
  font-family: inherit;
  background: var(--arl-bg-card);
  border: 1px solid var(--arl-border-color);
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 18px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--arl-text-color);
  cursor: pointer;
  user-select: none;
  flex-shrink: 0;
  white-space: nowrap;
  transition: all 0.18s ease;
}

.chain-metric-chip:hover {
  border-color: var(--arl-theme-color);
  color: var(--arl-theme-color);
}

.chain-metric-chip:focus-visible {
  outline: 2px solid var(--arl-theme-color);
  outline-offset: 1px;
}

.chain-metric-chip.is-active {
  border-color: var(--arl-theme-color);
  background: var(--arl-theme-soft-bg);
  color: var(--arl-theme-color);
  font-weight: 500;
  box-shadow: 0 1px 4px color-mix(in srgb, var(--arl-theme-color) 16%, transparent);
}

.chain-metric-chip.is-zero {
  opacity: 0.62;
  background: var(--arl-bg-subtle);
}

.chain-metric-chip.is-zero:hover,
.chain-metric-chip.is-zero.is-active {
  opacity: 1;
}

.chain-metric-chip b {
  color: var(--arl-theme-color);
  font-family: var(--arl-font-mono);
}

.chain-metric-chip b.zero-num {
  color: var(--arl-text-secondary);
}

.chain-drawer-scroll-wrapper {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.chain-drawer-body {
  padding: 16px 20px 32px;
}

.chain-skeleton-wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.chain-skeleton-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chain-skeleton-pill {
  display: inline-block;
  width: 92px;
  height: 28px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--arl-bg-subtle) 25%, var(--arl-bg-hover) 50%, var(--arl-bg-subtle) 75%);
  background-size: 200% 100%;
  animation: chain-shimmer 1.4s ease infinite;
}

@keyframes chain-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.drawer-empty-box {
  background: var(--arl-bg-card);
  border-radius: 8px;
  padding: 64px 24px;
  text-align: center;
  border: 1px dashed var(--arl-border-color);
}

.drawer-empty-subtip {
  margin-top: 8px;
  color: var(--arl-text-secondary);
  font-size: 13px;
}

.drawer-empty-action {
  margin-top: 16px;
}

.chain-sections-container {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.drawer-chain-card {
  border-radius: 8px;
  background: var(--arl-bg-card);
  border: 1px solid var(--arl-border-color);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.drawer-chain-card :deep(.ant-card-head) {
  min-height: 44px;
  padding: 0 16px;
  border-bottom-color: var(--arl-border-color);
}

.drawer-chain-card :deep(.ant-card-body) {
  padding: 14px 16px;
}

/* 回到顶端悬浮按钮 */
.chain-back-top-btn {
  appearance: none;
  border: 0;
  background: transparent;
  padding: 0;
  position: absolute;
  right: 24px;
  bottom: 24px;
  z-index: 20;
  cursor: pointer;
  user-select: none;
}

.chain-back-top-btn:focus-visible {
  outline: none;
}

.chain-back-top-btn:focus-visible .back-top-circle {
  box-shadow: 0 0 0 3px var(--arl-theme-soft-bg), 0 6px 18px color-mix(in srgb, var(--arl-theme-color) 38%, transparent);
}

.back-top-circle {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: linear-gradient(135deg, color-mix(in srgb, var(--arl-theme-color) 78%, #ffffff) 0%, var(--arl-theme-color) 55%, color-mix(in srgb, var(--arl-theme-color) 80%, #000000) 100%);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 18px color-mix(in srgb, var(--arl-theme-color) 38%, transparent), 0 2px 6px rgba(0, 0, 0, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.3);
  transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
  backdrop-filter: blur(4px);
}

.back-top-icon {
  font-size: 20px;
  line-height: 1;
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.chain-back-top-btn:hover .back-top-circle {
  transform: translateY(-3px) scale(1.06);
  box-shadow: 0 10px 24px color-mix(in srgb, var(--arl-theme-color) 50%, transparent), 0 4px 10px rgba(0, 0, 0, 0.15);
}

.chain-back-top-btn:hover .back-top-icon {
  transform: translateY(-2px);
}

.chain-back-top-btn:active .back-top-circle {
  transform: translateY(-1px) scale(0.96);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.22s cubic-bezier(0.4, 0, 0.2, 1), transform 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.85);
}

.drawer-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--arl-text-color);
}

.drawer-site-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.drawer-site-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 12px;
  border-radius: 6px;
  background: var(--arl-bg-subcard);
  border: 1px solid var(--arl-border-color);
}

.drawer-site-meta {
  flex: 1;
  min-width: 0;
}

.site-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.drawer-favicon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.site-link {
  font-weight: 600;
  font-size: 14px;
  color: var(--arl-theme-color);
  word-break: break-all;
}

.site-kv-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 14px;
  font-size: 12px;
}

.kv-item {
  display: flex;
  align-items: baseline;
  gap: 4px;
  min-width: 0;
}

.kv-label {
  color: var(--arl-text-secondary);
  flex-shrink: 0;
}

.kv-value {
  color: var(--arl-text-color);
  min-width: 0;
  overflow-wrap: anywhere;
}

.site-finger-row {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.drawer-site-shot {
  flex-shrink: 0;
}

.drawer-site-shot :deep(img) {
  width: 140px;
  height: 90px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid var(--arl-border-color);
}

.font-mono {
  font-family: var(--arl-font-mono);
}

.font-bold {
  font-weight: 600;
}

.cell-tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.font-tag {
  display: inline-block;
  background: var(--arl-bg-hover);
  color: var(--arl-text-color);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.drawer-break-link {
  word-break: break-all;
}

.drawer-muted-time {
  font-size: 12px;
  color: var(--arl-text-secondary);
}

.wih-content-text {
  word-break: break-all;
  color: #fa8c16;
  font-weight: 500;
}

.drawer-cert-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.drawer-cert-item {
  padding: 10px 12px;
  background: var(--arl-bg-subcard);
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
}

.cert-host-tag {
  font-weight: 600;
  font-family: var(--arl-font-mono);
  color: var(--arl-theme-color);
  margin-bottom: 6px;
}

.cert-fields {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--arl-text-color);
}

.cert-field-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  flex-wrap: wrap;
  overflow-wrap: anywhere;
}

.cert-san-value {
  display: block;
  max-height: 96px;
  overflow-y: auto;
  word-break: break-all;
  color: var(--arl-text-secondary);
}

.drawer-services-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 8px;
}

.service-pill {
  padding: 8px 10px;
  background: var(--arl-bg-subcard);
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
  min-width: 0;
}

.service-name-tag {
  font-size: 12px;
  font-weight: 600;
  color: var(--arl-theme-color);
  margin-bottom: 4px;
}

.service-endpoint {
  font-size: 11px;
  display: flex;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
}

.service-product {
  color: var(--arl-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drawer-vuln-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.vuln-item-card {
  padding: 10px 12px;
  background: var(--arl-bg-subcard);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  border-left: 3px solid #f5222d;
}

.vuln-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
}

.vuln-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--arl-text-color);
  overflow-wrap: anywhere;
}

.vuln-target {
  font-size: 12px;
  color: var(--arl-text-secondary);
  word-break: break-all;
}

@media (max-width: 720px) {
  .chain-drawer-header {
    flex-wrap: wrap;
    padding: 12px 16px;
  }

  .drawer-header-right {
    width: 100%;
    justify-content: flex-end;
    flex-wrap: wrap;
  }

  .chain-nav-bar {
    padding: 8px 16px;
  }

  .chain-drawer-body {
    padding: 12px 16px 28px;
  }

  .drawer-site-item {
    flex-direction: column;
  }

  .site-kv-grid {
    grid-template-columns: 1fr;
  }

  .drawer-site-shot :deep(img) {
    width: 100%;
    max-width: 240px;
    height: auto;
  }
}
</style>
