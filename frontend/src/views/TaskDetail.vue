<template>
  <div style="background-color: var(--arl-bg-layout); padding: 24px; min-height: calc(100vh - 64px);">
    <EnterpriseTaskDetailPanel v-if="isEnterpriseTask" />
    <div v-else>
      <div ref="actionBarRef" style="position: sticky; top: 0px; z-index: 10; background-color: var(--arl-bg-layout); margin: -24px -24px 16px -24px; padding: 24px 24px 16px 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
    <a-page-header
      @back="handleBack"
      style="padding: 0 0 24px 0;"
    >
      <template #title>
        <a-tooltip placement="bottomLeft">
          <template #title>
            <div style="word-break: break-all; max-height: 300px; overflow-y: auto; font-weight: normal; font-size: 14px;">
              <div v-for="(item, index) in targetList" :key="index">
                {{ item }}
              </div>
            </div>
          </template>
          <span>{{ displayTitle }}</span>
        </a-tooltip>
      </template>
    </a-page-header>

    <a-tabs v-model:activeKey="activeTab" type="card" class="arl-detail-tabs" style="margin-bottom: 16px;">
      <a-tab-pane key="site" :tab="taskId ? taskText('tasks.websitesCountLabel', { count: queryCounts.site }) : taskText('tasks.websites')"></a-tab-pane>
      <a-tab-pane key="domain" :tab="taskId ? taskText('tasks.subdomainsCount', { count: queryCounts.domain }) : taskText('tasks.subdomains')"></a-tab-pane>
      <a-tab-pane key="ip" :tab="taskId ? `IP - ${queryCounts.ip}` : 'IP'"></a-tab-pane>
      <a-tab-pane key="cert" :tab="taskId ? taskText('tasks.sslCertificatesCount', { count: queryCounts.cert }) : taskText('tasks.sslCertificates')"></a-tab-pane>
      <a-tab-pane key="service" :tab="taskId ? taskText('tasks.servicesCount', { count: (queryCounts.service || 0) + (queryCounts.npoc_service || 0) }) : taskText('tasks.services')"></a-tab-pane>
      <a-tab-pane key="fileleak" :tab="taskId ? taskText('tasks.fileDisclosuresCount', { count: queryCounts.fileleak }) : taskText('tasks.fileDisclosure')"></a-tab-pane>
      <a-tab-pane key="url" :tab="taskId ? taskText('tasks.urlsCount', { count: queryCounts.url }) : taskText('tasks.urls')"></a-tab-pane>
      <a-tab-pane key="cip" :tab="taskId ? taskText('tasks.cClassNetworksCount', { count: queryCounts.cip }) : taskText('tasks.cClassNetworks')"></a-tab-pane>
      <a-tab-pane key="stat_finger" :tab="taskId ? taskText('tasks.fingerprintStatisticsCount', { count: queryCounts.stat_finger }) : taskText('tasks.fingerprintStatistics')"></a-tab-pane>
      <a-tab-pane key="wih" :tab="taskId ? `WIH - ${queryCounts.wih}` : 'WIH'"></a-tab-pane>
      <a-tab-pane key="vuln" :tab="taskId ? taskText('tasks.risksCountLabel', { count: queryCounts.vuln }) : taskText('tasks.risks')"></a-tab-pane>
      <a-tab-pane key="nuclei_result" :tab="taskId ? `nuclei - ${queryCounts.nuclei_result}` : 'nuclei'"></a-tab-pane>
      <a-tab-pane v-if="taskId" key="syslog" :tab="taskText('tasks.taskLogs')"></a-tab-pane>
    </a-tabs>

    <div v-if="activeTab === 'service'" style="margin-bottom: 16px; display: flex; align-items: center; gap: 12px; background: var(--arl-bg-light); padding: 10px 16px; border-radius: 6px; border: 1px solid var(--arl-border-color);">
      <span class="task-option-heading">{{ taskText('tasks.detectionEngine') }}</span>
      <a-radio-group v-model:value="serviceEngineType" button-style="solid" size="small" @change="onServiceEngineChange">
        <a-radio-button value="nmap">{{ taskText('tasks.portServicesNmap') }} <span v-if="taskId">({{ queryCounts.service || 0 }})</span></a-radio-button>
        <a-radio-button value="npoc">{{ taskText('tasks.pythonPluginServices') }} <span v-if="taskId">({{ queryCounts.npoc_service || 0 }})</span></a-radio-button>
      </a-radio-group>
    </div>

    <div v-if="tabConfig[effectiveTab]?.searchFields && activeTab !== 'syslog'" style="margin-bottom: 16px;">
      <a-form :model="searchForm" layout="inline" style="row-gap: 16px;">
      <a-form-item v-for="field in tabConfig[effectiveTab].searchFields" :key="field.key" :label="field.label + '：'">
        <HttpStatusFilter
          v-if="field.type === 'httpStatus'"
          v-model:value="searchForm[field.key]"
          @change="onSearch"
        />
                <a-select
            v-else-if="field.type === 'select'"
            v-model:value="searchForm[field.key]"
            :placeholder="taskText('tasks.selectField', { field: field.label })"
            style="width: 200px;"
            allowClear
            @change="onSearch"
        >
          <a-select-option v-for="opt in field.options" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </a-select-option>
        </a-select>

        <div
            v-else-if="field.hasOperatorSelect"
            style="display: flex; align-items: center; border: 1px solid var(--arl-border-color); border-radius: 2px; width: 280px; background: var(--arl-bg-white);"
        >
          <template v-if="field.type === 'select'">
            <a-select
                v-model:value="searchForm[field.key]"
                :placeholder="taskText('tasks.selectField', { field: field.label })"
                :bordered="false"
                style="flex: 1; box-shadow: none;"
                allowClear
                @change="onSearch"
            >
              <a-select-option v-for="opt in field.options" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </a-select-option>
            </a-select>
          </template>
          <template v-else>
            <a-input
                v-model:value="searchForm[field.key]"
                :placeholder="field.placeholder || taskText('tasks.enterField', { field: field.label })"
                :bordered="false"
                style="flex: 1; box-shadow: none;"
                allowClear
                @pressEnter="onSearch"
            >
              <template #suffix>
                <search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" />
              </template>
            </a-input>
          </template>
          <div style="width: 1px; height: 16px; background-color: var(--arl-border-color);"></div>
          <a-select
              v-model:value="field.operator"
              :bordered="false"
              style="width: 90px; box-shadow: none;"
              @change="onSearch"
          >
            <a-select-option v-for="op in field.operators" :key="op" :value="op">{{ formatAssetFilterOperator(op) }}</a-select-option>
          </a-select>
        </div>

        <a-input
            v-else
            v-model:value="searchForm[field.key]"
            :placeholder="taskText('tasks.enterField', { field: field.label })"
            style="width: 200px;"
            allowClear
            @pressEnter="onSearch"
        >
          <template #suffix>
            <search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" />
          </template>
        </a-input>
      </a-form-item>
      </a-form>
    </div>

    <div v-show="activeTab !== 'syslog'" style="margin-bottom: 16px;">
      <a-button class="task-spaced-option" @click="resetSearch">{{ taskText('tasks.clearFilters') }}</a-button>
      <a-button v-if="canDeleteAssets" :disabled="!hasSelected" class="task-spaced-option" @click="handleBatchDelete">{{ taskText('tasks.deleteSelected') }}</a-button>
      <a-button v-if="tabConfig[effectiveTab]?.exportName" type="primary" class="task-spaced-option" @click="handleExport">{{ taskText('tasks.exportAssetType', { type: tabConfig[effectiveTab].exportName }) }}</a-button>
      <a-button v-if="activeTab === 'site'" type="primary" @click="openRiskModal">{{ taskText('tasks.createRiskScanningTask') }}</a-button>
    </div>
    </div>

    <a-table
        :sticky="stickyConfig"
        v-show="activeTab !== 'syslog'"
        :row-selection="canSelectAssets ? { selectedRowKeys: selectedRowKeys, onChange: onSelectChange } : null"
        :loading="loading"
        :dataSource="dataSource"
        :columns="columns"
        :pagination="false"
        :scroll="pagination.pageSize >= 100 ? { y: 'calc(100vh - 380px)', x: 'max-content' } : { x: 'max-content' }"
        :virtual="pagination.pageSize >= 100"
        size="middle"
        :rowKey="getAssetRowKey"
    >
      <template #bodyCell="{ column, record, index }">

        <template v-if="column.key === 'index'">{{ (pagination.current - 1) * pagination.pageSize + index + 1 }}</template>
<!--表格-站点列-->
        <template v-else-if="column.key === 'site'">
          <div class="site-header">
            <a :href="record.site || record.url" target="_blank" style="font-weight: 500;">
              <img v-if="record.favicon && record.favicon.data" :src="`data:image/png;base64,${record.favicon.data}`" class="site-img" />
              <img v-else-if="typeof record.favicon === 'string'" :src="`data:image/png;base64,${record.favicon}`" class="site-img" />

              {{ record.site || record.url }}
            </a>

            <p v-if="record.favicon && record.favicon.hash" class="site-word">{{ taskText('tasks.faviconHash') }}: {{ record.favicon.hash }}</p>
            <p v-else-if="record.favicon_hash" class="site-word">{{ taskText('tasks.faviconHash') }}: {{ record.favicon_hash }}</p>

            <div class="mt5" style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">

              <!-- 1. 入口标签 -->
              <a-tag v-if="record.is_entry || record.isEntry" style="background: var(--arl-bg-light); color: var(--arl-text-color); border-color: var(--arl-border-color);">
                {{ taskText('tasks.entryPoint') }}
                <a-popconfirm
                  :title="taskText('tasks.removeTheEntryPointTag')"
                  :ok-text="taskText('tasks.confirm')"
                  :cancel-text="taskText('tasks.cancel')"
                  @confirm="handleDeleteTag(record, '入口')"
                >
                  <span class="ant-tag-close-icon" @click.stop>
                    <close-outlined />
                  </span>
                </a-popconfirm>
              </a-tag>

              <!-- 2. 其余业务自定义标签 -->
              <template v-for="(t, idx) in (record.tags || record.tag || []).filter(Boolean)" :key="idx">
                <a-tag style="background: var(--arl-bg-light); color: var(--arl-text-color); border-color: var(--arl-border-color);">
                  {{ typeof t === 'string' ? t : (t?.name || t?.tag_name || t) }}
                  <a-popconfirm
                    :title="taskText('tasks.removeTagTag', { tag: typeof t === 'string' ? t : (t?.name || t?.tag_name || t) })"
                    :ok-text="taskText('tasks.confirm')"
                    :cancel-text="taskText('tasks.cancel')"
                    @confirm="handleDeleteTag(record, typeof t === 'string' ? t : (t?.name || t?.tag_name || t))"
                  >
                    <span class="ant-tag-close-icon" @click.stop>
                      <close-outlined />
                    </span>
                  </a-popconfirm>
                </a-tag>
              </template>

              <span class="add-tag task-clickable" @click="openTagModal(record)" >{{ taskText('tasks.addTag') }}</span>
            </div>
          </div>
        </template>

        <template v-else-if="column.key === 'title'">
          <a-tooltip placement="topLeft" :overlayStyle="{ maxWidth: '400px' }">
            <template #title>
              <div style="word-break: break-all;">
                {{ record.title }}
              </div>
            </template>
            <div style="max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
              {{ record.title }}
            </div>
          </a-tooltip>
        </template>

        <template v-else-if="column.key === 'headers'">
          <div class="scroll-x"><pre>{{ record.headers }}</pre></div>
        </template>



        <template v-else-if="column.key === 'finger'">
          <div v-if="record.finger && record.finger.length > 0" style="display: flex; flex-wrap: wrap; gap: 4px;">
            <a-tag v-for="f in record.finger.slice(0, 3)" :key="f.name" color="blue" style="margin: 0; white-space: normal; height: auto; text-align: left;">{{ f.name }}</a-tag>
            <a-popover v-if="record.finger.length > 3" placement="top">
              <template #content>
                <div style="display: flex; flex-wrap: wrap; gap: 4px; max-width: 300px; max-height: 200px; overflow-y: auto;">
                  <a-tag v-for="f in record.finger" :key="f.name" color="blue" style="margin: 0; white-space: normal; height: auto; text-align: left;">{{ f.name }}</a-tag>
                </div>
              </template>
              <a-tag style="margin: 0; cursor: pointer; border-style: dashed;">+{{ record.finger.length - 3 }}</a-tag>
            </a-popover>
          </div>
        </template>


        <template v-else-if="column.key === 'screenshot'">
          <img v-if="record.screenshot" :src="`/api${record.screenshot}`" style="width: 280px; height: 160px; object-fit: cover; object-position: top; cursor: pointer; border: 1px solid var(--arl-border-color); border-radius: 4px;" @click="handlePreview(`/api${record.screenshot}`)" />
          <span v-else>-</span>
        </template>
<!--        插槽-->
        <template v-else-if="column.key === 'record'">
          <div v-if="record.record && record.record.length">
            <div v-for="(r, i) in record.record" :key="i">{{ r }}</div>
          </div>
          <span v-else>-</span>
        </template>

        <template v-else-if="column.key === 'ips'">
          <div v-if="record.ips && record.ips.length">

            <a-tooltip
                v-if="record.ips.length > 5"
                placement="top"
                :overlayInnerStyle="{ maxHeight: '400px', overflowY: 'auto' }"
            >
              <template #title>
                <div v-for="(ip, i) in record.ips" :key="'all-'+i">{{ ip }}</div>
              </template>

              <div style="cursor: pointer;">
                <div v-for="(ip, i) in record.ips.slice(0, 5)" :key="i">{{ ip }}</div>
                <div class="task-field-hint">{{ taskText('tasks.andMore') }} {{ record.ips.length }} {{ taskText('tasks.itemsLabel') }}</div>
              </div>
            </a-tooltip>

            <div v-else>
              <div v-for="(ip, i) in record.ips" :key="i">{{ ip }}</div>
            </div>

          </div>
          <span v-else>-</span>
        </template>
        <template v-else-if="column.key === 'os_info'">
          <span>{{ record.os_info?.name || '-' }}</span>
        </template>
        <template v-else-if="column.key === 'port_info'">
          <span>{{ record.port_info && record.port_info.length ? record.port_info.map(p => p.port_id).join(', ') : '-' }}</span>
        </template>
        <template v-else-if="column.key === 'domain'">

          <div v-if="Array.isArray(record.domain) && record.domain.length">
            <a-tooltip v-if="record.domain.length > 5" placement="top" :overlayInnerStyle="{ maxHeight: '400px', overflowY: 'auto' }">
              <template #title>
                <div v-for="(dom, i) in record.domain" :key="'all-dom-'+i">{{ dom }}</div>
              </template>
              <div style="cursor: pointer;">
                <div v-for="(dom, i) in record.domain.slice(0, 5)" :key="i">{{ dom }}</div>
                <div class="task-field-hint">{{ taskText('tasks.andMore') }} {{ record.domain.length }} {{ taskText('tasks.itemsLabel') }}</div>
              </div>
            </a-tooltip>
            <div v-else>
              <div v-for="(dom, i) in record.domain" :key="i">{{ dom }}</div>
            </div>
          </div>

          <span v-else-if="typeof record.domain === 'string'">{{ record.domain }}</span>

          <span v-else>-</span>
        </template>
        <template v-else-if="column.key === 'geo_city'">
          <span>{{ formatGeo(record.geo_city) }}</span>
        </template>
        <template v-else-if="column.key === 'geo_asn'">
          <span>{{ record.geo_asn?.organization || '-' }}</span>
        </template>

        <template v-else-if="column.key === 'host'">
          <span>{{ record.ip || record.host }}{{ record.port ? ':' + record.port : '' }}</span>
        </template>
        <template v-else-if="column.key === 'cert_detail'">
          <div v-if="record.cert" style="font-size: 13px; line-height: 1.8; color: var(--arl-text-color); padding: 12px 0;">

            <div class="task-section-heading">{{ taskText('tasks.basicInformation') }}</div>

            <div style="display: flex; margin-bottom: 6px;">
              <div class="task-option-label">{{ taskText('tasks.subject') }}</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.subject_dn || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div class="task-option-label">{{ taskText('tasks.issuer') }}</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.issuer_dn || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div class="task-option-label">{{ taskText('tasks.subjectAlternativeNames') }}</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.extensions?.subjectAltName || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div class="task-option-label">{{ taskText('tasks.serialNumber') }}</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.serial_number || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 16px;">
              <div class="task-option-label">{{ taskText('tasks.time') }}</div>
              <div class="task-option-value">{{ record.cert.validity?.start || '-' }} {{ taskText('tasks.to') }} {{ record.cert.validity?.end || '-' }}</div>
            </div>

            <div class="task-section-heading">{{ taskText('tasks.fingerprints') }}</div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">SHA-256</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.fingerprint?.sha256 || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">SHA-1</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.fingerprint?.sha1 || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">MD5</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.fingerprint?.md5 || '-' }}</div>
            </div>

          </div>
          <span v-else>-</span>
        </template>

        <template v-else-if="column.key === 'change_status'">
          <a-tag v-if="record.change_status === 'new' || activeTab === 'stat_finger'" color="green">{{ taskText('tasks.added') }}</a-tag>
          <a-popover v-else-if="record.change_status === 'update' && activeTab !== 'stat_finger'" placement="right">
            <template #content>
              <div class="task-rule-heading">{{ taskText('tasks.keyChanges') }}</div>
              <div style="max-height: 200px; overflow-y: auto;">
                <div v-for="(diff, field) in record.update_diff" :key="field" style="margin-bottom: 6px; font-size: 13px;">
                  <span style="color: var(--arl-text-color); font-weight: 500; margin-right: 4px;">{{ fieldMap[field] || field }}:</span>
                  <template v-if="formatDiffValue(diff.before) === taskText('tasks.longTextCollapsed') || formatDiffValue(diff.after) === taskText('tasks.longTextCollapsed')">
                    <span class="task-empty-hint">{{ taskText('tasks.longTextChanged') }}</span>
                  </template>
                  <template v-else>
                    <span style="color: #ff4d4f; text-decoration: line-through;">{{ formatDiffValue(diff.before) }}</span>
                    <span style="margin: 0 4px; color: #bfbfbf;">➔</span>
                    <span style="color: #52c41a; font-weight: bold;">{{ formatDiffValue(diff.after) }}</span>
                  </template>
                </div>
              </div>
              <a class="task-details-toggle" @click="openDiffModal(record)">{{ taskText('tasks.viewTheCompleteDiff') }}</a>
            </template>
            <a-tag color="blue" class="task-help">{{ taskText('tasks.updated') }}</a-tag>
          </a-popover>
          <span v-else style="color: rgba(255,255,255,0.25);">-</span>
        </template>

        <template v-else-if="column.key === 'ip_port'">
          <div v-if="record.service_info && record.service_info.length">
            <div v-for="(info, i) in record.service_info.slice(0, 3)" :key="i" style="line-height: 1.8; font-family: monospace;">
              {{ info.ip }}:{{ info.port_id }}
            </div>
            <div v-if="record.service_info.length > 3" style="margin-top: 4px;">
              <a-button
                type="link"
                size="small"
                style="padding: 0; height: auto; font-size: 12px;"
                @click="openServiceDetailModal(record)"
              >
                {{ taskText('tasks.viewAllTotal', { count: record.service_info.length }) }}
              </a-button>
            </div>
          </div>
          <span v-else>-</span>
        </template>
        <template v-else-if="column.key === 'product'">
          <div v-if="record.service_info && record.service_info.length">
            <div v-for="(info, i) in record.service_info.slice(0, 3)" :key="i" style="line-height: 1.8;">
              {{ info.product || '-' }}
            </div>
            <div
              v-if="record.service_info.length > 3"
              style="margin-top: 4px; height: 22px; line-height: 22px; color: var(--arl-text-color); opacity: 0.45; font-size: 12px;"
            >
              ...
            </div>
          </div>
          <span v-else>-</span>
        </template>

        <template v-else-if="column.key === 'fileleak_url' || column.key === 'url_link' || column.key === 'nuclei_vuln_url'">
          <a :href="record.url || record.vuln_url" target="_blank" style="word-break: break-all;">
            {{ record.url || record.vuln_url || '-' }}
          </a>
        </template>

        <template v-else-if="column.key === 'verify_data'">
          <div style="max-height: 100px; overflow-y: auto; color: #d93026; font-family: monospace; font-size: 12px; word-break: break-all;">
            {{ record.verify_data || record.proof || '-' }}
          </div>
        </template>

        <template v-else-if="column.key === 'cidr_ip'">
          <a style="cursor: pointer; font-family: monospace; font-size: 14px;" @click="openCidrDetail(record)">{{ record.cidr_ip || '-' }}</a>
        </template>

        <template v-else-if="column.key === 'ip_count_col'">
          <span>{{ record.ip_count || 0 }}</span>
        </template>

        <template v-else-if="column.key === 'domain_count_col'">
          <span>{{ record.domain_count || 0 }}</span>
        </template>

        <template v-else-if="column.key === 'verify_command'">
          <div style="max-height: 100px; overflow-y: auto; background: var(--arl-bg-light); padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 12px; word-break: break-all;">
            {{ record.verify_command || record.curl_command || '-' }}
          </div>
        </template>

        <template v-else-if="column.key === 'finger_name'">
          <a style="cursor: pointer; text-decoration: underline;" @click="openFingerModal(record.name)">{{ record.name || '-' }}</a>
        </template>

        <template v-else-if="column.key === 'wih_source'">
          <div style="word-break: break-all; color: var(--arl-text-color); line-height: 1.6;">
            {{ record.source || '-' }}
          </div>
        </template>

        <template v-else-if="column.key === 'wih_site'">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a :href="record.site" target="_blank" style="word-break: break-all;">
              {{ record.site || '-' }}
            </a>
            <a-popover v-if="record.sites && record.sites.length > 1" placement="topLeft">
              <template #content>
                <div style="max-height: 300px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px;">
                  <a v-for="(s, idx) in record.sites.slice(1)" :key="idx" :href="s" target="_blank" style="word-break: break-all;">
                    {{ s }}
                  </a>
                </div>
              </template>
              <a-badge class="task-site-count" :count="taskText('tasks.countWebsites', { count: record.sites.length - 1 })" />
            </a-popover>
          </div>
        </template>

        <template v-else-if="column.key === 'wih_risk_level'">
          <!-- 缺失风险等级时如实显示“未知”，避免被误读为已确认低危 -->
          <a-tag :color="record.risk_level === 'CRITICAL' ? 'red' : (record.risk_level === 'MEDIUM' ? 'orange' : 'default')">
            {{ record.risk_level || taskText('tasks.unknown') }}
          </a-tag>
        </template>

        <template v-else-if="column.key === 'ip_cdn_tag'">
          <a-tag v-if="record.is_cdn || record.cdn_name" color="blue">{{ record.cdn_name || taskText('tasks.cdnNode') }}</a-tag>
          <!-- is_cdn 为 null/undefined 表示该字段未采集，不应表述为“已确认独立源站” -->
          <a-tag v-else-if="record.is_cdn === false" color="green">{{ taskText('tasks.originServer') }}</a-tag>
          <a-tag v-else color="default">{{ taskText('tasks.unidentified') }}</a-tag>
        </template>

        <template v-else-if="column.key === 'content' && activeTab === 'wih'">
          <div class="wih-api-content">
            <span>{{ record.content }}</span>
            <div class="wih-api-actions">
              <a-button v-if="isApiEndpointRecord(record)" type="link" size="small" @click="showWihApiDetails(record)">{{ taskText('wihApi.viewDetails') }}</a-button>
              <a-button type="link" size="small" class="task-icon-action" @click="copyText(record.content)">{{ taskText('tasks.copy') }}</a-button>
            </div>
          </div>
        </template>

      </template>
    </a-table>

    <WihApiDetailsDrawer v-model:open="wihApiDetailsOpen" :record="wihApiDetailsRecord" :context-key="route.fullPath + ':' + activeTab" />

    <!-- 综合C段详情弹窗 (提取为组件) -->
    <CidrDetailModal v-model:open="cipDetailModalVisible" :record="currentCidrRecord" />

    <!-- 系统服务端点详情弹窗 (提取为组件) -->
    <ServiceDetailModal v-model:open="serviceDetailModalVisible" :record="currentServiceRecord" />

    <!-- 指纹统计关联站点弹窗 -->
    <a-modal v-model:open="fingerModalVisible" :title="taskText('tasks.websitesWithFingerprintName', { name: currentFingerName })" :footer="null" width="800px">
      <a-table
        :dataSource="fingerModalData"
        :columns="fingerModalColumns"
        :loading="fingerModalLoading"
        :pagination="false"
        size="small"
        rowKey="_id"
        :scroll="{ y: 400 }"
      >
        <template #bodyCell="{ column, record, index }">
          <template v-if="column.key === 'index'">{{ index + 1 }}</template>
          <template v-else-if="column.key === 'site'">
            <a :href="record.site || record.url" target="_blank">{{ record.site || record.url }}</a>
          </template>
          <template v-else-if="column.key === 'title'">
            <a-tooltip placement="topLeft" :overlayStyle="{ maxWidth: '400px' }">
              <template #title>
                <div style="word-break: break-all;">
                  {{ record.title }}
                </div>
              </template>
              <div style="max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                {{ record.title }}
              </div>
            </a-tooltip>
          </template>
        </template>
      </a-table>
    </a-modal>

    <div v-if="tabConfig[effectiveTab] && activeTab !== 'syslog'" style="display: flex; justify-content: space-between; align-items: center; padding: 0 16px;">
      <div class="task-muted">{{ taskText('tasks.paginationSummary', { pages: Math.ceil(pagination.total / pagination.pageSize) || 1, total: pagination.total }) }}</div>
      <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" @showSizeChange="handleTableChange" />
    </div>

    <div v-show="activeTab === 'syslog'">
      <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; padding: 8px; background-color: var(--arl-bg-light);">
        <div ref="terminalContainer" style="background-color: #001529; color: #e6f7ff; font-family: 'Fira Code', Consolas, 'Courier New', monospace; padding: 16px; border-radius: 4px; height: calc(100vh - 240px); overflow-y: auto; font-size: 13px; line-height: 1.6; box-shadow: inset 0 2px 8px rgba(0,0,0,0.2);" @mouseenter="pauseScroll = true" @mouseleave="pauseScroll = false">
          <div v-for="(log, idx) in syslogList" :key="log._id || log.id || idx" style="margin-bottom: 6px; word-break: break-all; border-bottom: 1px dashed rgba(255,255,255,0.1); padding-bottom: 4px;">
            <a style="margin-right: 8px;">[{{ log.create_time }}]</a>
            <span :style="{ color: log.level === 'error' ? '#ff4d4f' : log.level === 'warning' ? '#faad14' : '#52c41a', fontWeight: 'bold', marginRight: '8px' }">[{{ (log.level || 'info').toUpperCase() }}]</span>
            <a style="margin-right: 8px;" v-if="log.title">[{{ log.title }}]</a>
            <span style="color: #e6f7ff;">{{ log.message }}</span>
          </div>
          <div v-if="syslogList.length === 0 && !syslogLoading" class="task-log-empty">{{ taskText('tasks.systemNoLogsYetWaitingForLogs') }}</div>
          <div v-if="syslogLoading && syslogList.length === 0" class="task-log-empty">{{ taskText('tasks.systemLoadingLogs') }}</div>
        </div>
      </div>
    </div>

    <a-modal v-model:open="previewVisible" :footer="null" width="85vw" centered @cancel="previewVisible = false" :bodyStyle="{ padding: '16px' }">
      <img :src="previewImage" style="width: 100%; max-height: 85vh; object-fit: contain; display: block;" />
    </a-modal>

    <!-- 添加标签弹窗 -->
    <a-modal v-model:open="tagVisible" :title="taskText('tasks.addTag')" @ok="submitTag" :confirmLoading="tagSubmitLoading" width="400px" :okText="taskText('tasks.confirm')" :cancelText="taskText('tasks.cancel')">
      <div style="margin-top: 20px;">
        <a-input v-model:value="newTagValue" :placeholder="taskText('tasks.enterATagName')" />
      </div>
    </a-modal>
<!--    风险任务下发弹窗-->
    <a-modal
        v-model:open="riskVisible"
        :title="taskText('tasks.addRiskScanningTask')"
        @ok="submitRiskTask"
        :confirmLoading="riskSubmitLoading"
        width="520px"
        wrapClassName="arl-theme-modal"
        rootClassName="arl-theme-modal"
        :okText="taskText('tasks.confirm')"
        :cancelText="taskText('tasks.cancel')"
    >
      <a-form :label-wrap="true" :model="riskForm" :label-col="{ span: taskLocale !== 'zh-CN' ? 7 : 5 }" :wrapper-col="{ span: taskLocale !== 'zh-CN' ? 15 : 17 }" class="task-risk-form">
        <a-form-item :label="taskText('tasks.policyName')" name="policy_id" :rules="[{ required: true, message: taskText('tasks.selectAPolicy') }]">
          <a-select
              v-model:value="riskForm.policy_id"
              :placeholder="taskText('tasks.selectAPolicy')"
              :options="policyOptions"
              show-search
              option-filter-prop="label"
              @change="handlePolicyChange"
          />
        </a-form-item>

        <a-form-item :label="taskText('tasks.taskName')" name="name" :rules="[{ required: true, message: taskText('tasks.enterATaskName') }]">
          <a-input v-model:value="riskForm.name" />
        </a-form-item>

        <div style="margin-left: 104px; color: var(--arl-text-color); margin-top: 16px;">
          {{ taskText('tasks.targetsNumberSelected') }} {{ targetCount }}
        </div>
      </a-form>
    </a-modal>

    <a-modal v-model:open="diffModalVisible" :title="taskText('tasks.updateDetails')" :footer="null" width="600px">
      <div style="max-height: 500px; overflow-y: auto;">
        <div v-for="(diff, field) in currentDiffData" :key="field" style="margin-bottom: 12px; border: 1px solid var(--arl-border-color); border-radius: 4px; padding: 12px; background: var(--arl-bg-light);">
          <div class="task-diff-heading">{{ taskText('tasks.field') }} {{ field }}</div>
          <div style="color: #ff4d4f; word-break: break-all; font-family: monospace; line-height: 1.6; margin-bottom: 8px;">
            <div class="task-diff-caption">{{ taskText('tasks.previousValue') }}</div>
            <div class="task-diff-before">{{ diff.before ?? taskText('tasks.empty') }}</div>
          </div>
          <div style="color: #52c41a; word-break: break-all; font-family: monospace; line-height: 1.6;">
            <div class="task-diff-caption">{{ taskText('tasks.newValue') }}</div>
            <div class="task-diff-after">{{ diff.after ?? taskText('tasks.empty') }}</div>
          </div>
        </div>
      </div>
    </a-modal>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';

defineOptions({ name: 'TaskDetail' });
import { ref, onMounted, onUnmounted, onActivated, onDeactivated, reactive, watch, nextTick, computed, createVNode } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import request from '../utils/request';
import HttpStatusFilter from '../components/HttpStatusFilter.vue';
import { formatAssetFilterOperator, buildAssetFilterParams } from '../utils/assetFilters';
import { message, Modal } from 'ant-design-vue';
import {
  ExclamationCircleOutlined,
  CloseOutlined
} from '@ant-design/icons-vue';
import CidrDetailModal from '../components/CidrDetailModal.vue';
import WihApiDetailsDrawer from '../components/WihApiDetailsDrawer.vue';
import { isApiEndpointRecord } from '../utils/wihApi';
import ServiceDetailModal from '../components/ServiceDetailModal.vue';
import EnterpriseTaskDetailPanel from '../components/EnterpriseTaskDetailPanel.vue';
import { useSticky } from '../utils/useSticky';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { copyText as copyToClipboard } from '../utils/clipboard';
import { createTabStateCache } from '../utils/useTabStateCache';
import { formatGeo } from '../utils/formatGeo';

const { t: taskText, locale: taskLocale } = useI18n({ useScope: 'global' });

const wihApiDetailsOpen = ref(false);
const wihApiDetailsRecord = ref(null);
const showWihApiDetails = record => {
  if (!isApiEndpointRecord(record)) return;
  wihApiDetailsRecord.value = record;
  wihApiDetailsOpen.value = true;
};

// 更新差异弹窗状态
const diffModalVisible = ref(false);
const currentDiffData = ref({});

const openDiffModal = (record) => {
  currentDiffData.value = record.update_diff || {};
  diffModalVisible.value = true;
};

// 字段汉化映射
const fieldMap = {
  get status_code() { return taskText('tasks.statusCode'); },
  get title() { return taskText('tasks.title'); },
  get content_length() { return taskText('tasks.responseLength'); },
  get ip() { return taskText('tasks.ipAddress'); },
  get port() { return taskText('tasks.openPorts'); },
  get port_id() { return taskText('tasks.openPorts'); },
  get product() { return taskText('tasks.serviceProduct'); },
  get service_name() { return taskText('tasks.serviceName'); },
  get vul_name() { return taskText('tasks.vulnerabilityName'); },
  get vuln_name() { return taskText('tasks.vulnerabilityName'); },
  get vul_category() { return taskText('tasks.vulnerabilityCategory'); },
  get record() { return taskText('tasks.dnsRecord'); },
  get type() { return taskText('tasks.recordType'); },
  get url() { return taskText('tasks.link'); },
  get domain() { return taskText('tasks.domains'); },
  get os_info() { return taskText('tasks.operatingSystem'); },
  cdn_name: 'CDN',
};

const formatDiffValue = (val) => {
  if (val === null || val === undefined) return taskText('tasks.empty');
  let str = typeof val === 'object' ? JSON.stringify(val) : String(val);
  if (str.length > 30) {
    return taskText('tasks.longTextCollapsed');
  }
  return str;
};

const route = useRoute();
const router = useRouter();
const taskId = computed(() => (route.query?.task_id ? String(route.query.task_id) : ''));

const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

// 复制文字并提示 (复用 utils/clipboard 兼容非 HTTPS 环境)
const copyText = async (text, label = taskText('tasks.content')) => {
  if (!text) return;
  const ok = await copyToClipboard(text);
  if (ok) {
    message.success(taskText('tasks.copiedLabelToClipboard', { label: label }));
  } else {
    message.info(taskText('tasks.copyFailedPleaseSelectAndCopyManually'));
  }
};

// C段详情弹窗 (提取为组件)
const cipDetailModalVisible = ref(false);
const currentCidrRecord = ref(null);

const openCidrDetail = (record) => {
  currentCidrRecord.value = record;
  cipDetailModalVisible.value = true;
};

// 系统服务端点详情弹窗
const serviceDetailModalVisible = ref(false);
const currentServiceRecord = ref(null);

const openServiceDetailModal = (record) => {
  currentServiceRecord.value = record;
  serviceDetailModalVisible.value = true;
};

// 弹窗状态与方法
const fingerModalVisible = ref(false);
const currentFingerName = ref('');
const fingerModalData = ref([]);
const fingerModalLoading = ref(false);

const fingerModalColumns = [
  { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
  { get title() { return taskText('tasks.websiteUrl'); }, key: 'site', width: 300 },
  { get title() { return taskText('tasks.title'); }, key: 'title', dataIndex: 'title', width: 200 },
  { get title() { return taskText('tasks.statusCode'); }, key: 'status_code', dataIndex: 'status_code', width: 100 }
];

const openFingerModal = async (fingerName) => {
  currentFingerName.value = fingerName;
  fingerModalVisible.value = true;
  fingerModalLoading.value = true;
  fingerModalData.value = [];
  try {
    const res = await request.get('/site/', {
      params: {
        task_id: taskId.value || undefined,
        finger: fingerName,
        page: 1,
        size: 100
      }
    });
    const rawItems = res.items || res.data?.items || [];
    const uniqueItems = [];
    const siteSet = new Set();
    for (const item of rawItems) {
      const siteUrl = item.site || item.url;
      if (!siteSet.has(siteUrl)) {
        siteSet.add(siteUrl);
        uniqueItems.push(item);
      }
    }
    fingerModalData.value = uniqueItems;
  } catch (error) {
    console.error('Fetch finger sites failed:', error);
    message.error(taskText('tasks.failedToLoadAssociatedWebsites'));
  } finally {
    fingerModalLoading.value = false;
  }
};

// 标签管理逻辑
const tagVisible = ref(false);
const tagSubmitLoading = ref(false);
const newTagValue = ref('');
const currentTagRecord = ref(null);

const openTagModal = (record) => {
  currentTagRecord.value = record;
  newTagValue.value = '';
  tagVisible.value = true;
};

const submitTag = async () => {
  if (!newTagValue.value.trim()) {
    return message.warning(taskText('tasks.tagNameCannotBeEmpty'));
  }
  tagSubmitLoading.value = true;
  try {
    const res = await request.post('/site/add_tag/', {
      _id: currentTagRecord.value._id || currentTagRecord.value.id,
      tag: newTagValue.value.trim()
    });
    if (res.code === 200) {
      message.success(taskText('tasks.tagAdded'));
      tagVisible.value = false;
      tabCache.invalidateMemoryCache(activeTab.value);
      fetchData(); // 重新加载数据
    } else {
      message.error(res.message || taskText('tasks.failedToAddTag'));
    }
  } catch (error) {
    message.error(taskText('tasks.requestFailed'));
  } finally {
    tagSubmitLoading.value = false;
  }
};

const handleDeleteTag = async (record, tag) => {
  const targetId = record._id || record.id;
  if (!targetId || !tag) return;
  try {
    const res = await request.post('/site/delete_tag/', {
      _id: targetId,
      tag: tag
    });
    if (res.code === 200) {
      message.success(taskText('tasks.removedTagTag', { tag: tag }));
      const currentTags = Array.isArray(record.tag) ? record.tag : (record.tag ? [record.tag] : (record.tags || []));
      record.tag = currentTags.filter(t => (typeof t === 'string' ? t : (t?.name || t?.tag_name)) !== tag);
      if (record.tags) {
        record.tags = record.tag;
      }
      if (tag === '入口') {
        record.is_entry = false;
        record.isEntry = false;
      }
      tabCache.invalidateMemoryCache(activeTab.value);
    } else {
      message.error(res.message || taskText('tasks.failedToDeleteTag'));
    }
  } catch (error) {
    message.error(taskText('tasks.requestFailed'));
  }
};

const targetName = ref(route.query?.targetName || '');
const displayTarget = computed(() => !taskId.value && targetName.value === '全局'
  ? taskText('tasks.globalTargets') : targetName.value || taskText('tasks.unknownTarget'));

const targetList = computed(() => {
  return String(targetName.value).split(/[,\s]+/).filter(Boolean);
});
const displayTitle = computed(() => {
  const list = targetList.value;
  if (list.length <= 1) return taskText('tasks.assetsRelatedToTarget', { target: displayTarget.value });
  return taskText('tasks.assetsRelatedToTargetAndOtherTargetsCount', { target: list[0], count: list.length });
});
const isEnterpriseTask = computed(() => {
  const t = route.query?.task_type;
  return t === 'tyc' || t === 'icp';
});
const handleBack = () => {
  if (isEnterpriseTask.value) {
    router.push({ path: '/taskList', query: { tab: 'enterprise' } });
  } else {
    router.push({ path: '/taskList', query: { tab: 'task' } });
  }
};
const taskStatus = ref('');
const isTaskRunning = computed(() => !!taskId.value && !['done', 'error', 'stop'].includes(taskStatus.value));
const isHydrating = ref(true);

const activeTab = ref('site');
const serviceEngineType = ref('nmap'); // 'nmap' | 'npoc'
const effectiveTab = computed(() => {
  if (activeTab.value === 'service' && serviceEngineType.value === 'npoc') {
    return 'npoc_service';
  }
  return activeTab.value;
});

const onServiceEngineChange = () => {
  const currentTab = effectiveTab.value;
  selectedRowKeys.value = [];
  columns.value = tabConfig[currentTab]?.cols || [];
  searchForm.value = tabCache.getTabSearchForm(currentTab);
  tabCache.applyTabOperators(currentTab);
  pagination.current = tabCache.getTabPage(currentTab) || 1;
  const cached = tabCache.getMemoryCache(currentTab, pagination.pageSize);
  if (cached) {
    dataSource.value = cached.dataSource;
    pagination.total = cached.total;
    lastFetchedPage = pagination.current;
    lastFetchedSize = pagination.pageSize;
  } else {
    fetchData();
  }
};
const loading = ref(false);
const dataSource = ref([]);

const terminalContainer = ref(null);
const pauseScroll = ref(false);

// 弹窗状态
const previewVisible = ref(false);
const previewImage = ref('');

const handlePreview = (url) => {
  previewImage.value = url;
  previewVisible.value = true;
};

// URL 数量解析
const queryCounts = reactive({
  site: 0,
  domain: 0,
  ip: 0,
  cert: 0,
  service: 0,
  fileleak: 0,
  url: 0,
  vuln: 0,
  npoc_service: 0,
  cip: 0,
  nuclei_result: 0,
  stat_finger: 0,
  wih: 0,
});

const syncQueryCounts = (q = route.query) => {
  queryCounts.site = Number(q?.site_cnt) || 0;
  queryCounts.domain = Number(q?.domain_cnt) || 0;
  queryCounts.ip = Number(q?.ip_cnt) || 0;
  queryCounts.cert = Number(q?.cert_cnt) || 0;
  queryCounts.service = Number(q?.service_cnt) || 0;
  queryCounts.fileleak = Number(q?.fileleak_cnt) || 0;
  queryCounts.url = Number(q?.url_cnt) || 0;
  queryCounts.vuln = Number(q?.vuln_cnt) || 0;
  queryCounts.npoc_service = Number(q?.npoc_service_cnt) || 0;
  queryCounts.cip = Number(q?.cip_cnt) || 0;
  queryCounts.nuclei_result = Number(q?.nuclei_result_cnt) || 0;
  queryCounts.stat_finger = Number(q?.stat_finger_cnt) || 0;
  queryCounts.wih = Number(q?.wih_cnt) || 0;
};
syncQueryCounts();

const selectedRowKeys = ref([]);
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
const onSelectChange = (keys) => { selectedRowKeys.value = keys; };

const searchForm = ref({});
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });
let lastFetchedPage = 1;
let lastFetchedSize = globalPageSize.value;

watch(() => pagination.pageSize, (newSize) => {
  const target = Number(newSize) || 10;
  if (globalPageSize.value !== target) {
    globalPageSize.value = target;
  }
});

watch(globalPageSize, (newSize) => {
  const target = Number(newSize) || 10;
  if (pagination.pageSize !== target) {
    pagination.pageSize = target;
    tabCache.invalidateAllMemoryCaches();
    if (tabConfig[effectiveTab.value] && activeTab.value !== 'syslog') {
      fetchData();
    }
  }
});

// 💥 核心修改 3：在配置字典中加入 deleteUrl
const tabConfig = reactive({
  site: {
    url: '/site/',
    exportUrl: '/site/export/',
    get exportName() { return taskText('tasks.websites'); },
    deleteUrl: '/site/delete/',
    searchFields: [
      { get label() { return taskText('tasks.websites'); }, key: 'site', operator: '=' },
      { label: 'IP', key: 'ip', operator: '=' },
      { get label() { return taskText('tasks.title'); }, key: 'title', operator: '=' },
      { get label() { return taskText('tasks.webServer'); }, key: 'http_server', operator: '=' },
      { get label() { return taskText('tasks.statusCode'); }, key: 'status', type: 'httpStatus' },
      { get label() { return taskText('tasks.headers'); }, key: 'headers', operator: '=' },
      { get label() { return taskText('tasks.fingerprints'); }, key: 'finger', operator: '=' },
      { get label() { return taskText('tasks.faviconHash'); }, key: 'favicon.hash', operator: '=' },
      { get label() { return taskText('tasks.tags'); }, key: 'tag', operator: '=' }
    ],
    cols: [
      { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return taskText('tasks.changeStatus'); }, key: 'change_status', width: 100, align: 'center' },
      { get title() { return taskText('tasks.websites'); }, key: 'site', width: 250 },
      { get title() { return taskText('tasks.statusCode'); }, dataIndex: 'status', key: 'status', width: 100, align: 'center' },
      { get title() { return taskText('tasks.title'); }, dataIndex: 'title', key: 'title', width: 200 },
      { get title() { return taskText('tasks.headers'); }, key: 'headers',width: 500},
      { get title() { return taskText('tasks.fingerprints'); }, key: 'finger', width: 150 },
      { get title() { return taskText('tasks.screenshot'); }, key: 'screenshot', width: 280 }
    ]
  },
  domain: {
    url: '/domain/',
    deleteUrl: '/domain/delete/',
    exportUrl: '/domain/export/',
    get exportName() { return taskText('tasks.subdomains'); },
    searchFields: [
      { get label() { return taskText('tasks.domains'); }, key: 'domain', operator: '=' },
      { get label() { return taskText('tasks.recordValue'); }, key: 'record', operator: '=' },
      { get label() { return taskText('tasks.type'); }, key: 'type', operator: '=' },
      { label: 'IP', key: 'ips', operator: '=' },
      { get label() { return taskText('tasks.source'); }, key: 'source', operator: '=' }
    ],
    cols: [
      { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return taskText('tasks.changeStatus'); }, key: 'change_status', width: 100, align: 'center' },
      { get title() { return taskText('tasks.domains'); }, dataIndex: 'domain', key: 'domain', width: 250 },
      { get title() { return taskText('tasks.dnsRecordType'); }, dataIndex: 'type', key: 'type', width: 120 },
      { get title() { return taskText('tasks.recordValue'); }, key: 'record', width: 300 },
      { get title() { return taskText('tasks.associatedIps'); }, key: 'ips', width: 250 },
      { get title() { return taskText('tasks.source'); }, dataIndex: 'source', key: 'source', width: 150 }
    ]
  },
  ip: {
    url: '/ip/',
    deleteUrl: '/ip/delete/',
    exportUrl: '/ip/export/',
    get exportName() { return taskText('tasks.ipPorts'); },
    searchFields: [
      { label: 'IP', key: 'ip', operator: '=' },
      { get label() { return taskText('tasks.cClassNetworks'); }, key: 'c_segment', operator: '=' },
      { get label() { return taskText('tasks.port'); }, key: 'port_info.port_id', operator: '=' },
      { get label() { return taskText('tasks.operatingSystem'); }, key: 'os_info.name', operator: '=' },
      { get label() { return taskText('tasks.domains'); }, key: 'domain', operator: '=' },
      { label: 'CDN', key: 'cdn_name', operator: '=', get placeholder() { return taskText('tasks.enterACdnProviderOrOriginServer'); } },
      {
        get label() { return taskText('tasks.ipType'); },
        key: 'ip_type',
        operator: '=',
        type: 'select',
        options: [
          { get label() { return taskText('tasks.publicPublic'); }, value: 'PUBLIC' },
          { get label() { return taskText('tasks.privatePrivate'); }, value: 'PRIVATE' }
        ]
      }
    ],
    cols: [
      { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return taskText('tasks.changeStatus'); }, key: 'change_status', width: 100, align: 'center' },
      { title: 'IP', dataIndex: 'ip', key: 'ip', width: 160 },
      { get title() { return taskText('tasks.cClassNetworks'); }, dataIndex: 'c_segment', key: 'c_segment', width: 140 },
      { get title() { return taskText('tasks.operatingSystem'); }, key: 'os_info', width: 150 },
      { get title() { return taskText('tasks.openPorts'); }, key: 'port_info', width: 200 },
      { get title() { return taskText('tasks.associatedDomains'); }, key: 'domain', width: 250 },
      { get title() { return taskText('tasks.cdnStatus'); }, key: 'ip_cdn_tag', width: 150 },
      { get title() { return taskText('tasks.geoLocation'); }, key: 'geo_city', width: 180 },
      { title: 'AS', key: 'geo_asn', width: 280 }
    ]
  },
  cert: {
    url: '/cert/',
    deleteUrl: '/cert/delete/',
    exportUrl: '/cert/export/',
    get exportName() { return taskText('tasks.sslCertificateInformation'); },
    searchFields: [
      { get label() { return taskText('tasks.ipFields'); }, key: 'ip', operator: '=' },
      { get label() { return taskText('tasks.issuer'); }, key: 'cert.issuer_dn', operator: '=' },
      { get label() { return taskText('tasks.subject'); }, key: 'cert.subject_dn', operator: '=' },
      { label: 'SHA-1', key: 'cert.fingerprint.sha1', operator: '=' },
      { get label() { return taskText('tasks.subjectAlternativeNames'); }, key: 'cert.extensions.subjectAltName', operator: '=' }
    ],
    cols: [
      { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return taskText('tasks.changeStatus'); }, key: 'change_status', width: 100, align: 'center' },
      { get title() { return taskText('tasks.host'); }, key: 'host', width: 180 },
      { get title() { return taskText('tasks.sslCertificateInformation'); }, key: 'cert_detail', width: 900 }
    ]
  },
  service: {
    url: '/service/',
    deleteUrl: '/service/delete/',
    searchFields: [
      { get label() { return taskText('tasks.services'); }, key: 'service_name', operator: '=' },
      { label: 'IP', key: 'service_info.ip', operator: '=' },
      { get label() { return taskText('tasks.port'); }, key: 'service_info.port_id', operator: '=' },
      { get label() { return taskText('tasks.product'); }, key: 'service_info.product', operator: '=' }
    ],
    cols: [
      { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return taskText('tasks.changeStatus'); }, key: 'change_status', width: 100, align: 'center' },
      { get title() { return taskText('tasks.services'); }, dataIndex: 'service_name', key: 'service_name', width: 150, align: 'center' },
      { get title() { return taskText('tasks.ipPort'); }, key: 'ip_port', width: 300 },
      { get title() { return taskText('tasks.product'); }, key: 'product', width: 250 }
    ]
  },
  fileleak: {
    url: '/fileleak/',
    deleteUrl: '/fileleak/delete/',
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { get label() { return taskText('tasks.title'); }, key: 'title', operator: '=' },
      { get label() { return taskText('tasks.statusCode'); }, key: 'status_code', type: 'httpStatus' },
      { get label() { return taskText('tasks.bodyLength'); }, key: 'content_length', operator: '=' }
    ],
    cols: [
      { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return taskText('tasks.changeStatus'); }, key: 'change_status', width: 100, align: 'center' },
      { title: 'URL', key: 'fileleak_url', width: 500 },
      { get title() { return taskText('tasks.title'); }, dataIndex: 'title', key: 'title', width: 250 },
      { get title() { return taskText('tasks.statusCode'); }, dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { get title() { return taskText('tasks.bodyLength'); }, dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' }
    ]
  },
  url: {
    // 任务视图查询任务结果集合；全局查看与同页其他页签一致，使用资产组集合。
    url: '/url/',
    globalUrl: '/asset_url/',
    deleteUrl: '/url/delete/',
    exportUrl: '/url/export/',
    get exportName() { return taskText('tasks.urls'); },
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { get label() { return taskText('tasks.title'); }, key: 'title', operator: '=' },
      { get label() { return taskText('tasks.statusCode'); }, key: 'status_code', type: 'httpStatus' },
      {
        get label() { return taskText('tasks.bodyLength'); },
        key: 'content_length',
        operator: '等于',
        hasOperatorSelect: true,
        operators: ['等于', '大于', '小于']
      },
      {
        get label() { return taskText('tasks.source'); },
        key: 'source',
        type: 'select',
        options: [
          { get label() { return taskText('tasks.crawlerSiteSpider'); }, value: 'site_spider' },
          { get label() { return taskText('tasks.searchEngineSearchEngine'); }, value: 'search_engine' },
          { label: 'AlienVault', value: 'alienvault' },
          { label: 'WaybackMachine', value: 'waybackmachine' },
          { label: 'CommonCrawl', value: 'commoncrawl' },
          { get label() { return taskText('tasks.fuzzing'); }, value: 'fuzz' }
        ],
        operator: '='
      }
    ],
    cols: [
      { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return taskText('tasks.changeStatus'); }, key: 'change_status', width: 100, align: 'center' },
      { title: 'URL', key: 'url_link', width: 450 },
      { get title() { return taskText('tasks.title'); }, dataIndex: 'title', key: 'title', width: 200 },
      { get title() { return taskText('tasks.statusCode'); }, dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { get title() { return taskText('tasks.bodyLength'); }, dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' },
      { get title() { return taskText('tasks.source'); }, dataIndex: 'source', key: 'source', width: 150 }
    ]
  },
  vuln: {
    url: '/vuln/',
    deleteUrl: '/vuln/delete/',
    searchFields: [
      { get label() { return taskText('tasks.vulnerabilityName'); }, key: 'vul_name', operator: '=' },
      { get label() { return taskText('tasks.category'); }, key: 'vul_category', operator: '=' },
      { get label() { return taskText('tasks.applicationName'); }, key: 'app_name', operator: '=' },
      { get label() { return taskText('tasks.target'); }, key: 'target', operator: '=' }
    ],
    cols: [
      { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return taskText('tasks.changeStatus'); }, key: 'change_status', width: 100, align: 'center' },
      { get title() { return taskText('tasks.vulnerabilityName'); }, dataIndex: 'vul_name', key: 'vul_name', width: 250 },
      { get title() { return taskText('tasks.category'); }, dataIndex: 'vul_category', key: 'vul_category', width: 120 },
      { get title() { return taskText('tasks.applicationName'); }, dataIndex: 'app_name', key: 'app_name', width: 150 },
      { get title() { return taskText('tasks.target'); }, dataIndex: 'target', key: 'target', width: 200 },
      { get title() { return taskText('tasks.credentials'); }, key: 'verify_data', width: 350 },
      { get title() { return taskText('tasks.discoveredAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 160 }
    ]
  },
  npoc_service: {
    url: '/npoc_service/',
    deleteUrl: '/npoc_service/delete/',
    exportUrl: '/npoc_service/export/',
    get exportName() { return taskText('tasks.pythonPluginServices'); },
    searchFields: [
      { get label() { return taskText('tasks.protocol'); }, key: 'scheme', operator: '=' },
      { get label() { return taskText('tasks.host'); }, key: 'host', operator: '=' },
      { get label() { return taskText('tasks.port'); }, key: 'port', operator: '=' },
      { get label() { return taskText('tasks.target'); }, key: 'target', operator: '=' }
    ],
    cols: [
      { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return taskText('tasks.changeStatus'); }, key: 'change_status', width: 100, align: 'center' },
      { get title() { return taskText('tasks.protocol'); }, dataIndex: 'scheme', key: 'scheme', width: 150 },
      { get title() { return taskText('tasks.host'); }, dataIndex: 'host', key: 'host', width: 200 },
      { get title() { return taskText('tasks.port'); }, dataIndex: 'port', key: 'port', width: 100, align: 'center' },
      { get title() { return taskText('tasks.target'); }, dataIndex: 'target', key: 'target', width: 250 },
      { get title() { return taskText('tasks.savedAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 180 }
    ]
  },
  cip: {
    url: '/cip/',
    globalUrl: '/asset_cip/',
    deleteUrl: '/cip/delete/',
    exportUrl: '/cip/export/',
    get exportName() { return taskText('tasks.cClassNetworks'); },
    searchFields: [
      { get label() { return taskText('tasks.cClassNetworks'); }, key: 'cidr_ip', operator: '=' }
    ],
    cols: [
      { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return taskText('tasks.changeStatus'); }, key: 'change_status', width: 100, align: 'center' },
      { get title() { return taskText('tasks.cClassNetworks'); }, dataIndex: 'cidr_ip', key: 'cidr_ip', width: 300 },
      { get title() { return taskText('tasks.ipCount'); }, key: 'ip_count_col', width: 150, align: 'center' },
      { get title() { return taskText('tasks.domainCount'); }, key: 'domain_count_col', width: 150, align: 'center' }
    ]
  },
  nuclei_result: {
    url: '/nuclei_result/',
    deleteUrl: '/nuclei_result/delete/',
    searchFields: [
      { get label() { return taskText('tasks.templateId'); }, key: 'template_id', operator: '=' },
      { get label() { return taskText('tasks.target'); }, key: 'target', operator: '=' },
      { get label() { return taskText('tasks.vulnerableUrl'); }, key: 'vuln_url', operator: '=' },
      { get label() { return taskText('tasks.vulnerabilityName'); }, key: 'vuln_name', operator: '=' }
    ],
    cols: [
      { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return taskText('tasks.changeStatus'); }, key: 'change_status', width: 100, align: 'center' },
      { get title() { return taskText('tasks.templateId'); }, dataIndex: 'template_id', key: 'template_id', width: 180 },
      { get title() { return taskText('tasks.target'); }, dataIndex: 'target', key: 'target', width: 200 },
      { get title() { return taskText('tasks.vulnerableUrl'); }, key: 'nuclei_vuln_url', width: 300 },
      { get title() { return taskText('tasks.vulnerabilityName'); }, dataIndex: 'vuln_name', key: 'vuln_name', width: 200 },
      { get title() { return taskText('tasks.severity'); }, dataIndex: 'vuln_severity', key: 'vuln_severity', width: 100, align: 'center' },
      { get title() { return taskText('tasks.savedAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 160 },
      { get title() { return taskText('tasks.verificationCommand'); }, key: 'verify_command', width: 350 }
    ]
  },
  stat_finger: {
    url: '/stat_finger/',
    globalUrl: '/asset_stat_finger/',
    searchFields: [
      {
        get label() { return taskText('tasks.fingerprints'); },
        key: 'name',
        operator: '模糊匹配',
        hasOperatorSelect: true,
        operators: ['模糊匹配', '精确匹配']
      }
    ],
    cols: [
      { get title() { return taskText('tasks.no'); }, key: 'index', width: 80, align: 'center' },
      { get title() { return taskText('tasks.changeStatus'); }, key: 'change_status', width: 100, align: 'center' },
      { get title() { return taskText('tasks.fingerprints'); }, key: 'finger_name', width: 500 }, // 用专用 key 渲染青蓝字体
      { get title() { return taskText('tasks.count'); }, dataIndex: 'cnt', key: 'cnt', width: 200 }
    ]
  },


  // 💡 新增：WIH (Web Info Hunter) Tab 的 1:1 配置
// 💡 修复：WIH (Web Info Hunter) Tab 配置
  wih: {
    url: '/wih/',
    deleteUrl: '/wih/delete/',
    exportUrl: '/wih/export/',
    exportName: 'WIH',
    searchFields: [
      {
        get label() { return taskText('tasks.recordType'); },
        key: 'record_type',
        operator: '等于',
        hasOperatorSelect: true,
        operators: ['等于', '不等于']
      },
      { get label() { return taskText('tasks.content'); }, key: 'content', operator: '=' },
      { get label() { return taskText('tasks.sourceJs'); }, key: 'source', operator: '=' },
      { get label() { return taskText('tasks.sourceWebsite'); }, key: 'site', operator: '=' }
    ],
    cols: [
      { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return taskText('tasks.changeStatus'); }, key: 'change_status', width: 100, align: 'center' },
      { get title() { return taskText('tasks.recordType'); }, dataIndex: 'record_type', key: 'record_type', width: 120 },
      { get title() { return taskText('tasks.content'); }, dataIndex: 'content', key: 'content', width: 250 },
      { get title() { return taskText('tasks.sourceJs'); }, key: 'wih_source', width: 450 },
      { get title() { return taskText('tasks.sourceWebsite'); }, dataIndex: 'site', key: 'wih_site', width: 250 }
    ]
  }
});

// 任务视图查询任务结果集合；全局查看与同页其他页签一致，使用资产组集合。
const resolveAssetEndpoint = (config) => (taskId.value ? config?.url : config?.globalUrl || config?.url);

// 任务集合中的记录可按 ID 删除；指纹统计为聚合结果，全局视图为资产组集合。
const canDeleteAssets = computed(() => !!taskId.value && !!tabConfig[effectiveTab.value]?.deleteUrl);
const canSelectAssets = computed(() => canDeleteAssets.value ||
  (!!taskId.value && effectiveTab.value === 'stat_finger'));
const getAssetRowKey = (record) => record._id || record.id || (
  effectiveTab.value === 'stat_finger' ? record.name : undefined
);

const tabCache = createTabStateCache({
  getStorageKey: () => taskId.value ? `ARL_TASK_TAB_STATE_${taskId.value}` : 'ARL_TASK_TAB_STATE_GLOBAL',
  tabConfig,
  defaultTab: 'site',
  canUseMemoryCache: () => !isTaskRunning.value
});

const columns = ref(tabConfig.site.cols);

// 加载数据 (兼容单任务与全局查看)
const fetchData = async (isPolling = false) => {
  const currentTaskId = taskId.value;
  // 🚨 核心修改 1：删除了 if (!taskId) return; 让全局查看也能放行！

  const config = tabConfig[effectiveTab.value];
  if (!config) {
    dataSource.value = [];
    return;
  }

  const currentReqTab = effectiveTab.value;
  if (!isPolling) {
    loading.value = true;
  }
  try {
    // 🚨 核心修改 2：动态拼装参数，有 taskId 才传
    const params = { page: pagination.current, size: pagination.pageSize };
    if (currentTaskId) {
      params.task_id = currentTaskId;
    }

    Object.assign(params, buildAssetFilterParams(searchForm.value, config.searchFields));

    const res = await request.get(resolveAssetEndpoint(config), { params });
    // 竞态防御：若响应到达时 Tab 已切换，丢弃过期响应
    if (effectiveTab.value !== currentReqTab) return;

    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      selectedRowKeys.value = [];
      lastFetchedPage = pagination.current;
      lastFetchedSize = pagination.pageSize;
      tabCache.updateMemoryCache(effectiveTab.value, dataSource.value, pagination.total, pagination.pageSize);
      tabCache.saveCurrentTab(effectiveTab.value, searchForm.value, pagination.current);
    }
  } catch (error) {
    if (!isPolling && effectiveTab.value === currentReqTab) {
      message.error(taskText('tasks.failedToLoadAssetData'));
    }
  } finally {
    if (!isPolling && effectiveTab.value === currentReqTab) {
      loading.value = false;
    }
  }
};

// ==========================================
// 💥 导出站点：1:1 对齐导出纯文本文件流
// ==========================================
// ==========================================
// 💥 智能导出：自动识别当前 Tab 导出纯文本
// ==========================================
const handleExport = async () => {
  const config = tabConfig[effectiveTab.value];
  if (!config || !config.exportUrl) return;

  try {
    message.loading({ content: taskText('tasks.generatingTypeExport', { type: config.exportName }), key: 'export_data' });

    const params = { page: 1, size: 100000 };
    if (taskId.value) params.task_id = taskId.value;
    Object.assign(params, buildAssetFilterParams(searchForm.value, config.searchFields));

    const res = await request.get(config.exportUrl, {
      params,
      responseType: 'blob'
    });

    const isCert = effectiveTab.value === 'cert';
    const mimeType = isCert ? 'application/json;charset=utf-8' : 'text/plain;charset=utf-8';
    const ext = isCert ? 'json' : 'txt';

    const blob = new Blob([res], { type: mimeType });
    const downloadUrl = window.URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_${effectiveTab.value}_Export_${taskId.value ? taskId.value.substring(0, 8) : 'Global'}.${ext}`;
    document.body.appendChild(link);
    link.click();

    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: taskText('tasks.typeExportCompleted', { type: config.exportName }), key: 'export_data', duration: 2 });
  } catch (error) {
    console.error('导出异常:', error);
    message.error({ content: taskText('tasks.exportFailedCheckTheConsole'), key: 'export_data', duration: 2 });
  }
};

// 💥 核心修改 4：通用批量删除函数
// 💥 核心修复：增加 null/undefined 过滤机制
const handleBatchDelete = () => {
  if (!hasSelected.value) return;

  // 1. 数据消杀：过滤掉数组中的 undefined 和 null，拿到真正纯净的 ID
  const validKeys = selectedRowKeys.value.filter(key => key != null);

  // 2. 如果过滤后全是空的，说明 rowKey 绑定失败，直接拦截并弹窗警告
  if (validKeys.length === 0) {
    message.error(taskText('tasks.noDeletableAssetRecordsFoundRefreshThePage'));
    return;
  }

  const config = tabConfig[effectiveTab.value];
  if (!config || !canDeleteAssets.value) {
    message.warning(taskText('tasks.thisAssetTypeDoesNotSupportBatchDeletion'));
    return;
  }

  Modal.confirm({
    title: taskText('tasks.deleteSelectedRecords'),
    icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
    content: taskText('tasks.deleteTheSelectedRecordsCountFromType', { count: validKeys.length, type: config.exportName || taskText('tasks.assets') }),
    okText: taskText('tasks.confirm'),
    cancelText: taskText('tasks.cancel'),
    onOk: async () => {
      try {
        // 3. 将干净的有效 ID 数组发送给后端
        const res = await request.post(config.deleteUrl, {
          _id: validKeys
        });

        if (res.code === 200) {
          message.success(taskText('tasks.assetsDeletedCount', { count: validKeys.length }));
          selectedRowKeys.value = []; // 清空勾选
          tabCache.invalidateMemoryCache(effectiveTab.value);
          fetchData(); // 重新拉取表格数据更新界面
        } else {
          message.error(taskText('tasks.deletionFailed') + (res.message || taskText('tasks.unknownError')));
        }
      } catch (error) {
        console.error('批量删除异常:', error);
      }
    }
  });
};

const onSearch = () => {
  pagination.current = 1;
  tabCache.saveCurrentTab(effectiveTab.value, searchForm.value, 1);
  fetchData();
};

const resetSearch = () => {
  searchForm.value = {};
  tabCache.resetTabState(effectiveTab.value);
  pagination.current = 1;
  fetchData();
};

const handleTableChange = (page, pageSize) => {
  const targetSize = Number(pageSize) || Number(pagination.pageSize) || 10;
  const sizeChanged = targetSize !== lastFetchedSize;
  const targetPage = sizeChanged ? 1 : (Number(page) || 1);

  // 防御重复触发：只有在单页条数未变且目标页码与已拉取页码完全相同时才阻断
  if (!sizeChanged && targetPage === lastFetchedPage && targetSize === lastFetchedSize) {
    return;
  }

  lastFetchedPage = targetPage;
  lastFetchedSize = targetSize;

  pagination.current = targetPage;
  pagination.pageSize = targetSize;

  if (sizeChanged) {
    tabCache.invalidateAllMemoryCaches();
    globalPageSize.value = targetSize;
  }

  tabCache.saveCurrentTab(effectiveTab.value, searchForm.value, pagination.current);
  fetchData();
};

// 💡 独立任务日志状态与拉取机制 (与通用资产表格及 pagination 彻底解耦，防止污染全局分页)
const syslogList = ref([]);
const syslogLoading = ref(false);
let syslogTimer = null;

const fetchSyslog = async (isPolling = false) => {
  const currentTaskId = taskId.value;
  if (!currentTaskId) return;
  try {
    if (!isPolling) syslogLoading.value = true;
    const res = await request.get('/syslog/', {
      params: {
        task_id: currentTaskId,
        size: 5000,
        order: 'create_time',
        _t: Date.now()
      }
    });
    if (activeTab.value !== 'syslog') return;
    if (res.code === 200) {
      syslogList.value = res.items || [];
      if (!pauseScroll.value) {
        nextTick(() => {
          if (terminalContainer.value) {
            terminalContainer.value.scrollTop = terminalContainer.value.scrollHeight;
          }
        });
      }
    }
  } catch (error) {
    if (!isPolling) {
      message.error(taskText('tasks.failedToLoadTaskLogs'));
    }
  } finally {
    if (!isPolling) {
      syslogLoading.value = false;
    }
  }
};

const startSyslogTimer = () => {
  if (syslogTimer) clearInterval(syslogTimer);
  fetchSyslog();
  syslogTimer = setInterval(() => {
    fetchSyslog(true);
  }, 5000); // 每 5 秒拉取一次最新日志
};

const stopSyslogTimer = () => {
  if (syslogTimer) {
    clearInterval(syslogTimer);
    syslogTimer = null;
  }
};

// 💡 新增：全局任务状态轮询，用于实时更新 Tab 栏计数值
let taskStatusTimer = null;

const fetchTaskStats = async () => {
  const currentTaskId = taskId.value;
  if (!currentTaskId) return;
  try {
    const res = await request.get('/task/', { params: { _id: currentTaskId } });
    if (res.code === 200 && res.data && res.data.items && res.data.items.length > 0) {
      const task = res.data.items[0];
      const stat = task.statistic || {};
      queryCounts.site = stat.site_cnt ?? task.site_cnt ?? 0;
      queryCounts.domain = stat.domain_cnt ?? task.domain_cnt ?? 0;
      queryCounts.ip = stat.ip_cnt ?? task.ip_cnt ?? 0;
      queryCounts.cert = stat.cert_cnt ?? task.cert_cnt ?? 0;
      queryCounts.service = stat.service_cnt ?? task.service_cnt ?? 0;
      queryCounts.fileleak = stat.fileleak_cnt ?? task.fileleak_cnt ?? 0;
      queryCounts.url = stat.url_cnt ?? task.url_cnt ?? 0;
      queryCounts.vuln = stat.vuln_cnt ?? task.vuln_cnt ?? 0;
      queryCounts.npoc_service = stat.npoc_service_cnt ?? task.npoc_service_cnt ?? 0;
      queryCounts.cip = stat.cip_cnt ?? task.cip_cnt ?? 0;
      queryCounts.nuclei_result = stat.nuclei_result_cnt ?? task.nuclei_result_cnt ?? 0;
      queryCounts.stat_finger = stat.stat_finger_cnt ?? task.stat_finger_cnt ?? 0;
      queryCounts.wih = stat.wih_cnt ?? task.wih_cnt ?? 0;

      const previousStatus = taskStatus.value;
      taskStatus.value = task.status || '';

      // 如果任务刚变为结束状态，停止轮询，失效旧缓存并自动拉取最新完成数据
      if (task.status === 'done' || task.status === 'error' || task.status === 'stop') {
        stopTaskStatusTimer();
        if (previousStatus && !['done', 'error', 'stop'].includes(previousStatus)) {
          tabCache.invalidateAllMemoryCaches();
          if (activeTab.value !== 'syslog') {
            fetchData();
          }
        }
      }
    }
  } catch (err) {
    console.error('拉取任务全局状态失败:', err);
  }
};

const startTaskStatusTimer = () => {
  if (!taskId.value) return;
  if (taskStatusTimer) clearInterval(taskStatusTimer);
  fetchTaskStats(); // 初始拉取一次
  taskStatusTimer = setInterval(() => {
    fetchTaskStats();
  }, 5000); // 每 5 秒更新一次导航栏计数
};

const stopTaskStatusTimer = () => {
  if (taskStatusTimer) {
    clearInterval(taskStatusTimer);
    taskStatusTimer = null;
  }
};

watch(activeTab, (newVal, oldVal) => {
  const oldEffective = (oldVal === 'service' && serviceEngineType.value === 'npoc') ? 'npoc_service' : oldVal;
  const newEffective = (newVal === 'service' && serviceEngineType.value === 'npoc') ? 'npoc_service' : newVal;

  if (oldVal === 'syslog') {
    stopSyslogTimer();
  } else if (oldEffective && tabConfig[oldEffective] && !isHydrating.value) {
    tabCache.saveCurrentTab(oldEffective, searchForm.value, pagination.current);
  }

  if (newVal === 'syslog') {
    stopSyslogTimer();
    startSyslogTimer();
  } else if (tabConfig[newEffective]) {
    stopSyslogTimer();
    columns.value = tabConfig[newEffective].cols;
    selectedRowKeys.value = [];

    // 恢复新选项卡的搜索表单、操作符与页码
    searchForm.value = tabCache.getTabSearchForm(newEffective);
    tabCache.applyTabOperators(newEffective);
    pagination.current = tabCache.getTabPage(newEffective) || 1;

    // 检查内存数据缓存（传入 pagination.pageSize 进行容量匹配校验）
    const cached = tabCache.getMemoryCache(newEffective, pagination.pageSize);
    if (cached) {
      dataSource.value = cached.dataSource;
      pagination.total = cached.total;
      lastFetchedPage = pagination.current;
      lastFetchedSize = pagination.pageSize;
    } else {
      fetchData();
    }
  } else {
    stopSyslogTimer();
    dataSource.value = [];
    columns.value = [];
  }
});

const loadedTaskId = ref('');

const reloadTaskData = () => {
  stopSyslogTimer();
  stopTaskStatusTimer();

  loadedTaskId.value = taskId.value;
  targetName.value = route.query?.targetName || '';
  syncQueryCounts(route.query);
  taskStatus.value = '';
  dataSource.value = [];
  selectedRowKeys.value = [];

  let restoredTab = tabCache.init();
  if (restoredTab === 'npoc_service') {
    serviceEngineType.value = 'npoc';
    restoredTab = 'service';
  }
  if (restoredTab && tabConfig[restoredTab] && restoredTab !== activeTab.value) {
    activeTab.value = restoredTab;
    nextTick(() => {
      isHydrating.value = false;
    });
  } else {
    if (activeTab.value === 'syslog') {
      startSyslogTimer();
    } else if (tabConfig[effectiveTab.value]) {
      columns.value = tabConfig[effectiveTab.value].cols;
      searchForm.value = tabCache.getTabSearchForm(effectiveTab.value);
      tabCache.applyTabOperators(effectiveTab.value);
      pagination.current = tabCache.getTabPage(effectiveTab.value) || 1;

      const cached = tabCache.getMemoryCache(effectiveTab.value, pagination.pageSize);
      if (cached) {
        dataSource.value = cached.dataSource;
        pagination.total = cached.total;
        lastFetchedPage = pagination.current;
        lastFetchedSize = pagination.pageSize;
      } else {
        fetchData();
      }
    }
    nextTick(() => {
      isHydrating.value = false;
    });
  }
  startTaskStatusTimer();
};

watch(() => [taskId.value, isEnterpriseTask.value], ([newId, isEnterprise]) => {
  if (!route.path.startsWith('/taskList/taskDetail')) return;
  if (isEnterprise) return;
  reloadTaskData();
});

onMounted(() => {
  if (isEnterpriseTask.value) {
    return;
  }
  reloadTaskData();
});

onUnmounted(() => {
  stopSyslogTimer();
  stopTaskStatusTimer();
});

// ==========================================
// 💥 风险任务下发：生成临时集合、拉取策略、下发任务
// ==========================================
const riskVisible = ref(false);
const riskSubmitLoading = ref(false);
const policyOptions = ref([]);
const riskForm = reactive({ policy_id: undefined, name: '' });
const targetCount = ref(0);
const currentResultSetId = ref('');

// 1. 打开弹窗
const openRiskModal = async () => {
  targetCount.value = hasSelected.value ? selectedRowKeys.value.length : pagination.total;
  if (targetCount.value === 0) {
    message.warning(taskText('tasks.noAssetTargetsAreAvailableForScanning'));
    return;
  }

  riskForm.policy_id = undefined;
  riskForm.name = '';
  currentResultSetId.value = '';

  message.loading({ content: taskText('tasks.preparingAssetsAndLoadingPolicies'), key: 'risk_prepare' });

  try {
    const policyPromise = request.get('/policy/', { params: { size: 1000 } });

    const setParams = {};
    if (hasSelected.value) {
      setParams._id = selectedRowKeys.value.join(',');
    } else {
      if (taskId.value) setParams.task_id = taskId.value;
      Object.assign(setParams, buildAssetFilterParams(searchForm.value, tabConfig[effectiveTab.value].searchFields));
    }
    const resultSetPromise = request.get('/site/save_result_set/', { params: setParams });

    const [policyRes, resultSetRes] = await Promise.all([policyPromise, resultSetPromise]);

    if (policyRes.code === 200) {
      policyOptions.value = (policyRes.items || []).map(item => {
        const pocCount = item.policy?.poc_config?.length || 0;
        return {
          value: item._id,
          label: `${item.name} (PoC : ${pocCount})`
        };
      });
    }

    if (resultSetRes.code === 200) {
      currentResultSetId.value = resultSetRes.data.result_set_id;
      if (resultSetRes.data.result_total !== undefined) {
        targetCount.value = resultSetRes.data.result_total;
      }
    }

    message.success({ content: taskText('tasks.dataIsReady'), key: 'risk_prepare', duration: 2 });
    riskVisible.value = true;
  } catch (error) {
    console.error('准备风险任务异常:', error);
    message.error({ content: taskText('tasks.failedToPrepareDataCheckTheConsole'), key: 'risk_prepare', duration: 2 });
  }
};

// 2. 监听下拉框选择，自动拼装任务名称
const handlePolicyChange = (val, option) => {
  if (option) {
    riskForm.name = `风险巡航任务-${option.label}`;
  }
};

// 3. 确定下发任务
const submitRiskTask = async () => {
  if (!riskForm.policy_id || !riskForm.name) {
    message.warning(taskText('tasks.selectAPolicyAndEnterATaskName'));
    return;
  }
  if (!currentResultSetId.value) {
    message.error(taskText('tasks.assetSetIdIsUnavailableCloseTheDialog'));
    return;
  }

  riskSubmitLoading.value = true;
  try {
    const res = await request.post('/task/policy/', {
      name: riskForm.name,
      task_tag: 'risk_cruising',
      target: '',
      policy_id: riskForm.policy_id,
      result_set_id: currentResultSetId.value
    });

    if (res.code === 200) {
      message.success(taskText('tasks.riskScanningTaskCreated'));
      riskVisible.value = false;
      selectedRowKeys.value = [];
    } else {
      message.error(taskText('tasks.failedToCreateTaskLabel') + (res.message || taskText('tasks.unknownError')));
    }
  } catch (error) {
    message.error(taskText('tasks.networkRequestFailed'));
  } finally {
    riskSubmitLoading.value = false;
  }
};

onActivated(() => {
  if (isEnterpriseTask.value) return;
  if (loadedTaskId.value !== taskId.value) {
    reloadTaskData();
  } else {
    if (activeTab.value === 'syslog') {
      startSyslogTimer();
    }
    startTaskStatusTimer();
  }
});

onDeactivated(() => {
  stopSyslogTimer();
  stopTaskStatusTimer();
  diffModalVisible.value = false;
  cipDetailModalVisible.value = false;
  serviceDetailModalVisible.value = false;
  fingerModalVisible.value = false;
  tagVisible.value = false;
  previewVisible.value = false;
  riskVisible.value = false;
});
</script>

<style scoped>
.wih-api-content { display: flex; flex-direction: column; gap: 4px; overflow-wrap: anywhere; }
.wih-api-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }

.task-option-heading { font-weight: 600; font-size: 13px; color: var(--arl-text-color); }
.task-spaced-option { margin-right: 16px; }
.task-clickable { cursor: pointer; }
.task-field-hint { color: var(--arl-text-color); opacity: 0.45; margin-top: 2px; }
.task-section-heading { font-weight: 600; font-size: 14px; margin-bottom: 12px; }
.task-option-label { width: 120px; text-align: right; margin-right: 12px; font-weight: 500; }
.task-option-value { flex: 1; color: var(--arl-text-color); }
.task-rule-heading { margin-bottom: 8px; font-weight: bold; color: var(--arl-text-color); border-bottom: 1px solid var(--arl-border-color); padding-bottom: 4px; }
.task-empty-hint { color: #8c8c8c; font-style: italic; }
.task-details-toggle { display: block; margin-top: 12px; text-align: center; cursor: pointer; border-top: 1px dashed var(--arl-border-color); padding-top: 8px; }
.task-help { cursor: help; }
.task-icon-action { padding: 0; }
.task-muted { color: var(--arl-text-color); opacity: 0.65; }
.task-log-empty { color: rgba(255,255,255,0.45); font-style: italic; }
.task-diff-heading { font-weight: bold; font-size: 14px; margin-bottom: 8px; border-bottom: 1px solid var(--arl-border-color); padding-bottom: 4px; }
.task-diff-caption { font-weight: bold; margin-bottom: 4px; }
.task-diff-before { white-space: pre-wrap; background: rgba(255, 77, 79, 0.1); padding: 8px; border-radius: 4px; }
.task-diff-after { white-space: pre-wrap; background: rgba(82, 196, 26, 0.1); padding: 8px; border-radius: 4px; }

.task-risk-form { margin-top: 20px; }
.task-site-count :deep(.ant-badge-count) { background-color: #1890ff; color: #fff; cursor: pointer; border-radius: 4px; padding: 0 6px; font-size: 12px; }

.site-header { line-height: 1.5; word-break: break-all; }
.site-img { width: 16px; height: 16px; margin-right: 8px; vertical-align: middle; }
.site-word { color: var(--arl-text-color); opacity: 0.45; font-size: 12px; margin: 4px 0; }
/* "添加标签" 按钮样式 (灰色虚线框) */
.add-tag {
  color: var(--arl-text-color);
  cursor: pointer;
  font-size: 12px;
  margin-left: 8px;
  border: 1px dashed var(--arl-border-color);
  padding: 0 7px;
  border-radius: 2px;
  background: var(--arl-bg-light);
  transition: all 0.3s;
}
.add-tag:hover {
  color: var(--arl-theme-color);
  border-color: var(--arl-theme-color);
}
.mt5 { margin-top: 5px; }

/* ================= Headers 样式 ================= */
.scroll-x {
  /* 🚨 核心修复：删除了 max-height，让内容自然撑开表格的高度 */
  background: transparent;
  border: none;
  padding: 8px;
  width: 100%;
  max-width: 600px; /* 保持最大宽度，防止撑破整个表格列 */
  overflow-x: auto; /* 单行太长时，出现横向滚动条 */
  overflow-y: hidden; /* 绝对禁止内部出现垂直滚动条 */
}

.scroll-x pre {
  margin: 0;
  padding: 0;
  background-color: transparent;
  border: none;
  font-family: Consolas, Menlo, Courier, monospace;
  font-size: 12px;
  line-height: 1.5;
  color: var(--arl-text-color); opacity: 0.65;
  white-space: pre; /* 🚨 核心修复：强制不换行，这是触发横向滚动条的关键 */
  word-wrap: normal;
}

/* 定制横向滚动条的纤细样式，让它不那么突兀 */
.scroll-x::-webkit-scrollbar {
  height: 6px;
}
.scroll-x::-webkit-scrollbar-track {
  background: transparent;
}
.scroll-x::-webkit-scrollbar-thumb {
  background-color: rgba(144, 147, 153, 0.3);
  border-radius: 4px;
}
.scroll-x::-webkit-scrollbar-thumb:hover {
  background-color: rgba(144, 147, 153, 0.6);
}

:deep(.ant-tabs-card-bar .ant-tabs-tab) {
  border-radius: 2px 2px 0 0 !important;
  margin-right: 4px !important;
  border: 1px solid var(--arl-border-color) !important;
  background: var(--arl-bg-light) !important;
  transition: all 0.3s;
}
:deep(.ant-tabs-card-bar .ant-tabs-tab-active) {
  background: var(--arl-bg-white) !important;
  border-bottom-color: transparent !important;

  font-weight: 500;
}
:deep(.ant-tabs-tab:hover) {

}
/* ================= 6. 站点列细节补充 ================= */
/* Favicon Hash 次级文本与紧凑间距样式 */
/* 修复 Favicon Hash 发虚的问题：恢复原版字号和深色 */
.site-word {
  color: var(--arl-text-color) !important; /* 恢复为标准的深黑色，去掉导致发虚的浅灰 */
  font-size: 14px !important;            /* 恢复标准字号，不缩小 */
  margin-top: 4px;
  margin-bottom: 0;
  line-height: 1.5;
}
</style>
