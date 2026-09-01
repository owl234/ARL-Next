<template>
  <div style="background-color: var(--arl-bg-layout); padding: 24px; min-height: calc(100vh - 64px);">
    <div ref="actionBarRef" style="position: sticky; top: 0px; z-index: 10; background-color: var(--arl-bg-layout); margin: -24px -24px 16px -24px; padding: 24px 24px 16px 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
    <a-page-header
      @back="() => router.back()"
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
      <a-tab-pane key="site" :tab="query.task_id ? `站点 - ${queryCounts.site}` : '站点'"></a-tab-pane>
      <a-tab-pane key="domain" :tab="query.task_id ? `子域名 - ${queryCounts.domain}` : '子域名'"></a-tab-pane>
      <a-tab-pane key="ip" :tab="query.task_id ? `IP - ${queryCounts.ip}` : 'IP'"></a-tab-pane>
      <a-tab-pane key="cert" :tab="query.task_id ? `SSL证书 - ${queryCounts.cert}` : 'SSL证书'"></a-tab-pane>
      <a-tab-pane key="service" :tab="query.task_id ? `服务 - ${queryCounts.service}` : '服务'"></a-tab-pane>
      <a-tab-pane key="fileleak" :tab="query.task_id ? `文件泄露 - ${queryCounts.fileleak}` : '文件泄露'"></a-tab-pane>
      <a-tab-pane key="url" :tab="query.task_id ? `URL信息 - ${queryCounts.url}` : 'URL信息'"></a-tab-pane>
      <a-tab-pane key="vuln" :tab="query.task_id ? `风险 - ${queryCounts.vuln}` : '风险'"></a-tab-pane>
      <a-tab-pane key="npoc_service" :tab="query.task_id ? `服务（python） - ${queryCounts.npoc_service}` : '服务（python）'"></a-tab-pane>
      <a-tab-pane key="cip" :tab="query.task_id ? `C段 - ${queryCounts.cip}` : 'C段'"></a-tab-pane>
      <a-tab-pane key="nuclei_result" :tab="query.task_id ? `nuclei - ${queryCounts.nuclei_result}` : 'nuclei'"></a-tab-pane>
      <a-tab-pane key="stat_finger" :tab="query.task_id ? `指纹统计 - ${queryCounts.stat_finger}` : '指纹统计'"></a-tab-pane>
      <a-tab-pane key="wih" :tab="query.task_id ? `WIH - ${queryCounts.wih}` : 'WIH'"></a-tab-pane>
      <a-tab-pane v-if="query.task_id" key="syslog" tab="任务日志"></a-tab-pane>
    </a-tabs>

    <div v-if="tabConfig[activeTab]?.searchFields && activeTab !== 'syslog'" style="margin-bottom: 16px;">
      <a-form :model="searchForm" layout="inline" style="row-gap: 16px;">
      <a-form-item v-for="field in tabConfig[activeTab].searchFields" :key="field.key" :label="field.label + '：'">
                <a-select
            v-if="field.type === 'select'"
            v-model:value="searchForm[field.key]"
            :placeholder="`请选择${field.label}`"
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
                :placeholder="`请选择${field.label}`"
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
                :placeholder="`请输入${field.label}`"
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
            <a-select-option v-for="op in field.operators" :key="op" :value="op">{{ op }}</a-select-option>
          </a-select>
        </div>

        <a-input
            v-else
            v-model:value="searchForm[field.key]"
            :placeholder="`请输入${field.label}`"
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
      <a-button style="margin-right: 16px;" @click="resetSearch">清 除</a-button>
      <a-button :disabled="!hasSelected" style="margin-right: 16px;" @click="handleBatchDelete">批量删除</a-button>
      <a-button v-if="tabConfig[activeTab]?.exportName" type="primary" style="margin-right: 16px;" @click="handleExport">导出{{ tabConfig[activeTab].exportName }}</a-button>
      <a-button v-if="activeTab === 'site'" type="primary" @click="openRiskModal">风险任务下发</a-button>
    </div>
    </div>

    <a-table
        :sticky="stickyConfig"
        v-show="activeTab !== 'syslog'"
        :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
        :loading="loading"
        :dataSource="dataSource"
        :columns="columns"
        :pagination="false"
        :scroll="pagination.pageSize >= 100 ? { y: 'calc(100vh - 380px)', x: 'max-content' } : { x: 'max-content' }"
        :virtual="pagination.pageSize >= 100"
        size="middle"
        :rowKey="(record) => record._id || record.id"
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

            <p v-if="record.favicon && record.favicon.hash" class="site-word">Favicon Hash: {{ record.favicon.hash }}</p>
            <p v-else-if="record.favicon_hash" class="site-word">Favicon Hash: {{ record.favicon_hash }}</p>

            <div class="mt5" style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">

              <a-tag v-if="record.is_entry || record.isEntry" closable style="background: var(--arl-bg-light); color: var(--arl-text-color); border-color: var(--arl-border-color);">入口</a-tag>

              <template v-for="(t, idx) in (record.tags || record.tag || [])" :key="idx">
                <a-tag closable style="background: var(--arl-bg-light); color: var(--arl-text-color); border-color: var(--arl-border-color);">
                  {{ typeof t === 'string' ? t : (t.name || t.tag_name || t) }}
                </a-tag>
              </template>

              <span class="add-tag" @click="openTagModal(record)" style="cursor: pointer;">添加标签</span>
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
                <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 2px;">...等 {{ record.ips.length }} 个</div>
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
                <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 2px;">...等 {{ record.domain.length }} 个</div>
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
          <span>{{ record.geo_city ? `${record.geo_city.country_name || 'null'} / ${record.geo_city.city || 'null'}` : '-' }}</span>
        </template>
        <template v-else-if="column.key === 'geo_asn'">
          <span>{{ record.geo_asn?.organization || '-' }}</span>
        </template>

        <template v-else-if="column.key === 'host'">
          <span>{{ record.ip || record.host }}{{ record.port ? ':' + record.port : '' }}</span>
        </template>
        <template v-else-if="column.key === 'cert_detail'">
          <div v-if="record.cert" style="font-size: 13px; line-height: 1.8; color: var(--arl-text-color); padding: 12px 0;">

            <div style="font-weight: 600; font-size: 14px; margin-bottom: 12px;">基本信息</div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">主题名称</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.subject_dn || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">签发者名称</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.issuer_dn || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">使用者备用名称</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.extensions?.subjectAltName || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">序列号</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.serial_number || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 16px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">时间</div>
              <div style="flex: 1; color: var(--arl-text-color);">{{ record.cert.validity?.start || '-' }} 至 {{ record.cert.validity?.end || '-' }}</div>
            </div>

            <div style="font-weight: 600; font-size: 14px; margin-bottom: 12px;">指纹</div>

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
          <a-tag v-if="record.change_status === 'new' || activeTab === 'stat_finger'" color="green">新增</a-tag>
          <a-popover v-else-if="record.change_status === 'update' && activeTab !== 'stat_finger'" placement="right">
            <template #content>
              <div style="margin-bottom: 8px; font-weight: bold; color: var(--arl-text-color); border-bottom: 1px solid var(--arl-border-color); padding-bottom: 4px;">关键变更预览：</div>
              <div style="max-height: 200px; overflow-y: auto;">
                <div v-for="(diff, field) in record.update_diff" :key="field" style="margin-bottom: 6px; font-size: 13px;">
                  <span style="color: var(--arl-text-color); font-weight: 500; margin-right: 4px;">{{ fieldMap[field] || field }}:</span>
                  <template v-if="formatDiffValue(diff.before) === '[长文本已折叠]' || formatDiffValue(diff.after) === '[长文本已折叠]'">
                    <span style="color: #8c8c8c; font-style: italic;">[长文本内容变动]</span>
                  </template>
                  <template v-else>
                    <span style="color: #ff4d4f; text-decoration: line-through;">{{ formatDiffValue(diff.before) }}</span>
                    <span style="margin: 0 4px; color: #bfbfbf;">➔</span>
                    <span style="color: #52c41a; font-weight: bold;">{{ formatDiffValue(diff.after) }}</span>
                  </template>
                </div>
              </div>
              <a style="display: block; margin-top: 12px; text-align: center; cursor: pointer; border-top: 1px dashed var(--arl-border-color); padding-top: 8px;" @click="openDiffModal(record)">🔍 点击查看完整明细差异</a>
            </template>
            <a-tag color="blue" style="cursor: help;">更新</a-tag>
          </a-popover>
          <span v-else style="color: rgba(255,255,255,0.25);">-</span>
        </template>

        <template v-else-if="column.key === 'ip_port'">
          <div v-if="record.service_info && record.service_info.length">
            <div v-for="(info, i) in record.service_info" :key="i" style="line-height: 1.8;">
              {{ info.ip }}:{{ info.port_id }}
            </div>
          </div>
          <span v-else>-</span>
        </template>
        <template v-else-if="column.key === 'product'">
          <div v-if="record.service_info && record.service_info.length">
            <div v-for="(info, i) in record.service_info" :key="i" style="line-height: 1.8;">
              {{ info.product || '-' }}
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
              <a-badge :count="`+${record.sites.length - 1} 站点`" :number-style="{ backgroundColor: '#1890ff', color: '#fff', cursor: 'pointer', borderRadius: '4px', padding: '0 6px', fontSize: '12px' }" />
            </a-popover>
          </div>
        </template>

        <template v-else-if="column.key === 'wih_risk_level'">
          <a-tag :color="record.risk_level === 'CRITICAL' ? 'red' : (record.risk_level === 'MEDIUM' ? 'orange' : 'default')">
            {{ record.risk_level || 'LOW' }}
          </a-tag>
        </template>

        <template v-else-if="column.key === 'ip_cdn_tag'">
          <a-tag v-if="record.is_cdn || record.cdn_name" color="blue">{{ record.cdn_name || 'CDN节点' }}</a-tag>
          <a-tag v-else color="green">独立源站</a-tag>
        </template>

        <template v-else-if="column.key === 'content' && activeTab === 'wih'">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <span style="word-break: break-all;">{{ record.content }}</span>
            <a-button type="link" size="small" style="padding: 0;" @click="copyText(record.content)">复制</a-button>
          </div>
        </template>

      </template>
    </a-table>

    <!-- 综合C段详情弹窗 (提取为组件) -->
    <CidrDetailModal v-model:open="cipDetailModalVisible" :record="currentCidrRecord" />

    <!-- 指纹统计关联站点弹窗 -->
    <a-modal v-model:open="fingerModalVisible" :title="`指纹关联站点：${currentFingerName}`" :footer="null" width="800px">
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

    <div v-if="tabConfig[activeTab] && activeTab !== 'syslog'" style="display: flex; justify-content: space-between; align-items: center; padding: 0 16px;">
      <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
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
          <div v-if="syslogList.length === 0 && !syslogLoading" style="color: rgba(255,255,255,0.45); font-style: italic;">[System] 暂无日志记录... (等待日志生成)</div>
          <div v-if="syslogLoading && syslogList.length === 0" style="color: rgba(255,255,255,0.45); font-style: italic;">[System] 正在拉取日志...</div>
        </div>
      </div>
    </div>

    <a-modal v-model:open="previewVisible" :footer="null" width="85vw" centered @cancel="previewVisible = false" :bodyStyle="{ padding: '16px' }">
      <img :src="previewImage" style="width: 100%; max-height: 85vh; object-fit: contain; display: block;" />
    </a-modal>

    <!-- 添加标签弹窗 -->
    <a-modal v-model:open="tagVisible" title="添加标签" @ok="submitTag" :confirmLoading="tagSubmitLoading" width="400px" okText="确 定" cancelText="取 消">
      <div style="margin-top: 20px;">
        <a-input v-model:value="newTagValue" placeholder="请输入标签名称" />
      </div>
    </a-modal>
<!--    风险任务下发弹窗-->
    <a-modal
        v-model:open="riskVisible"
        title="添加风险巡航任务"
        @ok="submitRiskTask"
        :confirmLoading="riskSubmitLoading"
        width="520px"
        wrapClassName="arl-theme-modal"
        rootClassName="arl-theme-modal"
        okText="确 定"
        cancelText="取 消"
    >
      <a-form :model="riskForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 17 }" style="margin-top: 20px;">
        <a-form-item label="策略名称" name="policy_id" :rules="[{ required: true, message: '请选择策略' }]">
          <a-select
              v-model:value="riskForm.policy_id"
              placeholder="请选择策略"
              :options="policyOptions"
              show-search
              option-filter-prop="label"
              @change="handlePolicyChange"
          />
        </a-form-item>

        <a-form-item label="任务名称" name="name" :rules="[{ required: true, message: '请输入任务名称' }]">
          <a-input v-model:value="riskForm.name" />
        </a-form-item>

        <div style="margin-left: 104px; color: var(--arl-text-color); margin-top: 16px;">
          目标：选择目标数 {{ targetCount }}
        </div>
      </a-form>
    </a-modal>

    <a-modal v-model:open="diffModalVisible" title="更新差异明细" :footer="null" width="600px">
      <div style="max-height: 500px; overflow-y: auto;">
        <div v-for="(diff, field) in currentDiffData" :key="field" style="margin-bottom: 12px; border: 1px solid var(--arl-border-color); border-radius: 4px; padding: 12px; background: var(--arl-bg-light);">
          <div style="font-weight: bold; font-size: 14px; margin-bottom: 8px; border-bottom: 1px solid var(--arl-border-color); padding-bottom: 4px;">字段: {{ field }}</div>
          <div style="color: #ff4d4f; word-break: break-all; font-family: monospace; line-height: 1.6; margin-bottom: 8px;">
            <div style="font-weight: bold; margin-bottom: 4px;">- 旧值:</div>
            <div style="white-space: pre-wrap; background: rgba(255, 77, 79, 0.1); padding: 8px; border-radius: 4px;">{{ diff.before ?? '空' }}</div>
          </div>
          <div style="color: #52c41a; word-break: break-all; font-family: monospace; line-height: 1.6;">
            <div style="font-weight: bold; margin-bottom: 4px;">+ 新值:</div>
            <div style="white-space: pre-wrap; background: rgba(82, 196, 26, 0.1); padding: 8px; border-radius: 4px;">{{ diff.after ?? '空' }}</div>
          </div>
        </div>
      </div>
    </a-modal>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, reactive, watch, nextTick, computed, createVNode } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import request from '../utils/request';
import { message, Modal } from 'ant-design-vue';
import {
  ExclamationCircleOutlined
} from '@ant-design/icons-vue';
import CidrDetailModal from '../components/CidrDetailModal.vue';
import { useSticky } from '../utils/useSticky';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { copyText as copyToClipboard } from '../utils/clipboard';

// 更新差异弹窗状态
const diffModalVisible = ref(false);
const currentDiffData = ref({});

const openDiffModal = (record) => {
  currentDiffData.value = record.update_diff || {};
  diffModalVisible.value = true;
};

// 字段汉化映射
const fieldMap = {
  status_code: '状态码',
  title: '标题',
  content_length: '响应长度',
  ip: 'IP地址',
  port: '开放端口',
  port_id: '开放端口',
  product: '服务产品',
  service_name: '服务名称',
  vul_name: '漏洞名称',
  vuln_name: '漏洞名称',
  vul_category: '漏洞类别',
  record: '解析记录',
  type: '记录类型',
  url: '链接',
  domain: '域名',
  os_info: '操作系统',
  cdn_name: 'CDN',
};

const formatDiffValue = (val) => {
  if (val === null || val === undefined) return '空';
  let str = typeof val === 'object' ? JSON.stringify(val) : String(val);
  if (str.length > 30) {
    return '[长文本已折叠]';
  }
  return str;
};

const route = useRoute();
const router = useRouter();
const query = route?.query || {};

const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

// 复制文字并提示 (复用 utils/clipboard 兼容非 HTTPS 环境)
const copyText = async (text, label = '内容') => {
  if (!text) return;
  const ok = await copyToClipboard(text);
  if (ok) {
    message.success(`已复制 ${label} 到剪贴板`);
  } else {
    message.info('复制失败，请手动选取复制');
  }
};

// C段详情弹窗 (提取为组件)
const cipDetailModalVisible = ref(false);
const currentCidrRecord = ref(null);

const openCidrDetail = (record) => {
  currentCidrRecord.value = record;
  cipDetailModalVisible.value = true;
};

// 弹窗状态与方法
const fingerModalVisible = ref(false);
const currentFingerName = ref('');
const fingerModalData = ref([]);
const fingerModalLoading = ref(false);

const fingerModalColumns = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '站点 URL', key: 'site', width: 300 },
  { title: '标题', key: 'title', dataIndex: 'title', width: 200 },
  { title: '状态码', key: 'status_code', dataIndex: 'status_code', width: 100 }
];

const openFingerModal = async (fingerName) => {
  currentFingerName.value = fingerName;
  fingerModalVisible.value = true;
  fingerModalLoading.value = true;
  fingerModalData.value = [];
  try {
    const res = await request.get('/site/', {
      params: {
        task_id: query.task_id,
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
    message.error('获取关联站点失败');
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
    return message.warning('标签名称不能为空');
  }
  tagSubmitLoading.value = true;
  try {
    const res = await request.post('/site/add_tag/', {
      _id: currentTagRecord.value._id || currentTagRecord.value.id,
      tag: newTagValue.value.trim()
    });
    if (res.code === 200) {
      message.success('添加标签成功');
      tagVisible.value = false;
      fetchData(); // 重新加载数据
    } else {
      message.error(res.message || '添加标签失败');
    }
  } catch (error) {
    message.error('请求异常');
  } finally {
    tagSubmitLoading.value = false;
  }
};

const targetName = ref(query.targetName || '未知目标');
const targetList = computed(() => {
  return String(targetName.value).split(/[,\s]+/).filter(Boolean);
});
const displayTitle = computed(() => {
  const list = targetList.value;
  if (list.length <= 1) return `${targetName.value} 相关资产`;
  return `${list[0]} 等 ${list.length} 个目标相关资产`;
});
const activeTab = ref('site');
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
  site: Number(query.site_cnt) || 0,
  domain: Number(query.domain_cnt) || 0,
  ip: Number(query.ip_cnt) || 0,
  cert: Number(query.cert_cnt) || 0,
  service: Number(query.service_cnt) || 0,
  fileleak: Number(query.fileleak_cnt) || 0,
  url: Number(query.url_cnt) || 0,
  vuln: Number(query.vuln_cnt) || 0,
  npoc_service: Number(query.npoc_service_cnt) || 0,
  cip: Number(query.cip_cnt) || 0,
  nuclei_result: Number(query.nuclei_result_cnt) || 0,
  stat_finger: Number(query.stat_finger_cnt) || 0,
  wih: Number(query.wih_cnt) || 0,
});

const selectedRowKeys = ref([]);
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
const onSelectChange = (keys) => { selectedRowKeys.value = keys; };

const searchForm = ref({});
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});

// 💥 核心修改 3：在配置字典中加入 deleteUrl
const tabConfig = reactive({
  site: {
    url: '/site/',
    deleteUrl: '/site/delete/',
    searchFields: [
      { label: '站点', key: 'site', operator: '=' },
      { label: 'IP', key: 'ip', operator: '=' },
      { label: '主机名', key: 'hostname', operator: '=' },
      { label: '标题', key: 'title', operator: '=' },
      { label: 'Web Server', key: 'http_server', operator: '=' },
      { label: '状态码', key: 'status', operator: '=' },
      { label: '标头', key: 'headers', operator: '=' },
      { label: '指纹', key: 'finger', operator: '=' },
      { label: 'favicon hash', key: 'favicon.hash', operator: '=' },
      { label: '标签', key: 'tag', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '变更状态', key: 'change_status', width: 100, align: 'center' },
      { title: '站点', key: 'site', width: 250 },
      { title: '状态码', dataIndex: 'status', key: 'status', width: 100, align: 'center' },
      { title: '标题', dataIndex: 'title', key: 'title', width: 200 },
      { title: 'headers', key: 'headers',width: 500},
      { title: 'finger', key: 'finger', width: 150 },
      { title: '截图', key: 'screenshot', width: 280 }
    ]
  },
  domain: {
    url: '/domain/',
    deleteUrl: '/domain/delete/',
    exportUrl: '/domain/export/',
    exportName: '子域名',
    searchFields: [
      { label: '域名', key: 'domain', operator: '=' },
      { label: '记录值', key: 'record', operator: '=' },
      { label: '类型', key: 'type', operator: '=' },
      { label: 'IP', key: 'ips', operator: '=' },
      { label: '来源', key: 'source', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '变更状态', key: 'change_status', width: 100, align: 'center' },
      { title: '域名', dataIndex: 'domain', key: 'domain', width: 250 },
      { title: '解析类型', dataIndex: 'type', key: 'type', width: 120 },
      { title: '记录值', key: 'record', width: 300 },
      { title: '关联IP', key: 'ips', width: 250 },
      { title: '来源', dataIndex: 'source', key: 'source', width: 150 }
    ]
  },
  ip: {
    url: '/ip/',
    deleteUrl: '/ip/delete/',
    exportUrl: '/ip/export/',
    exportName: ' IP 端口',
    searchFields: [
      { label: 'IP', key: 'ip', operator: '=' },
      { label: 'C段', key: 'c_segment', operator: '=' },
      { label: '端口', key: 'port_info.port_id', operator: '=' },
      { label: '操作系统', key: 'os_info.name', operator: '=' },
      { label: '域名', key: 'domain', operator: '=' },
      { label: 'CDN', key: 'cdn_name', operator: '=' },
      {
        label: 'IP类别',
        key: 'ip_type',
        operator: '=',
        type: 'select',
        options: [
          { label: 'PUBLIC (公网)', value: 'PUBLIC' },
          { label: 'PRIVATE (内网)', value: 'PRIVATE' }
        ]
      }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '变更状态', key: 'change_status', width: 100, align: 'center' },
      { title: 'IP', dataIndex: 'ip', key: 'ip', width: 160 },
      { title: 'C段', dataIndex: 'c_segment', key: 'c_segment', width: 140 },
      { title: '操作系统', key: 'os_info', width: 150 },
      { title: '开放端口', key: 'port_info', width: 200 },
      { title: '关联域名', key: 'domain', width: 250 },
      { title: 'CDN状态', key: 'ip_cdn_tag', width: 150 },
      { title: 'Geo', key: 'geo_city', width: 180 },
      { title: 'AS', key: 'geo_asn', width: 280 }
    ]
  },
  cert: {
    url: '/cert/',
    deleteUrl: '/cert/delete/',
    searchFields: [
      { label: 'IP字段', key: 'ip', operator: '=' },
      { label: '签发者名称', key: 'cert.issuer_dn', operator: '=' },
      { label: '主题名称', key: 'cert.subject_dn', operator: '=' },
      { label: 'SHA-1', key: 'cert.fingerprint.sha1', operator: '=' },
      { label: '使用者备用名称', key: 'cert.extensions.subjectAltName', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '变更状态', key: 'change_status', width: 100, align: 'center' },
      { title: 'HOST', key: 'host', width: 180 },
      { title: 'CERT', key: 'cert_detail', width: 900 }
    ]
  },
  service: {
    url: '/service/',
    deleteUrl: '/service/delete/',
    searchFields: [
      { label: '服务', key: 'service_name', operator: '=' },
      { label: 'IP', key: 'service_info.ip', operator: '=' },
      { label: '端口', key: 'service_info.port_id', operator: '=' },
      { label: '产品', key: 'service_info.product', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '变更状态', key: 'change_status', width: 100, align: 'center' },
      { title: '服务', dataIndex: 'service_name', key: 'service_name', width: 150, align: 'center' },
      { title: 'IP端口', key: 'ip_port', width: 300 },
      { title: 'Product', key: 'product', width: 250 }
    ]
  },
  fileleak: {
    url: '/fileleak/',
    deleteUrl: '/fileleak/delete/',
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { label: '标题', key: 'title', operator: '=' },
      { label: '状态码', key: 'status_code', operator: '=' },
      { label: 'body 长度', key: 'content_length', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '变更状态', key: 'change_status', width: 100, align: 'center' },
      { title: 'URL', key: 'fileleak_url', width: 500 },
      { title: '标题', dataIndex: 'title', key: 'title', width: 250 },
      { title: '状态码', dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { title: 'body 长度', dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' }
    ]
  },
  url: {
    url: '/url/',
    deleteUrl: '/site/delete/',
    exportUrl: '/url/export/',
    exportName: 'URL信息',
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { label: '标题', key: 'title', operator: '=' },
      { label: '状态码', key: 'status_code', operator: '=' },
      { 
        label: 'body 长度', 
        key: 'content_length', 
        operator: '等于',
        hasOperatorSelect: true,
        operators: ['等于', '大于', '小于']
      },
      { 
        label: '来源', 
        key: 'source', 
        type: 'select',
        options: [
          { label: '爬虫(site_spider)', value: 'site_spider' },
          { label: '搜索引擎(search_engine)', value: 'search_engine' },
          { label: 'AlienVault', value: 'alienvault' },
          { label: 'WaybackMachine', value: 'waybackmachine' },
          { label: 'CommonCrawl', value: 'commoncrawl' },
          { label: 'Fuzz', value: 'fuzz' }
        ],
        operator: '=' 
      }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '变更状态', key: 'change_status', width: 100, align: 'center' },
      { title: 'URL', key: 'url_link', width: 450 },
      { title: '标题', dataIndex: 'title', key: 'title', width: 200 },
      { title: '状态码', dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { title: 'body 长度', dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' },
      { title: '来源', dataIndex: 'source', key: 'source', width: 150 }
    ]
  },
  vuln: {
    url: '/vuln/',
    deleteUrl: '/vuln/delete/',
    searchFields: [
      { label: '漏洞名称', key: 'vul_name', operator: '=' },
      { label: '类别', key: 'vul_category', operator: '=' },
      { label: '应用名', key: 'app_name', operator: '=' },
      { label: '目标', key: 'target', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '变更状态', key: 'change_status', width: 100, align: 'center' },
      { title: '漏洞名称', dataIndex: 'vul_name', key: 'vul_name', width: 250 },
      { title: '类别', dataIndex: 'vul_category', key: 'vul_category', width: 120 },
      { title: '应用名', dataIndex: 'app_name', key: 'app_name', width: 150 },
      { title: '目标', dataIndex: 'target', key: 'target', width: 200 },
      { title: '凭证', key: 'verify_data', width: 350 },
      { title: '发现时间', dataIndex: 'insert_time', key: 'insert_time', width: 160 }
    ]
  },
  npoc_service: {
    url: '/npoc_service/',
    deleteUrl: '/npoc_service/delete/',
    searchFields: [
      { label: '协议', key: 'scheme', operator: '=' },
      { label: '主机', key: 'host', operator: '=' },
      { label: '端口', key: 'port', operator: '=' },
      { label: '目标', key: 'target', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '变更状态', key: 'change_status', width: 100, align: 'center' },
      { title: '协议', dataIndex: 'scheme', key: 'scheme', width: 150 },
      { title: '主机', dataIndex: 'host', key: 'host', width: 200 },
      { title: '端口', dataIndex: 'port', key: 'port', width: 100, align: 'center' },
      { title: '目标', dataIndex: 'target', key: 'target', width: 250 },
      { title: '保存时间', dataIndex: 'insert_time', key: 'insert_time', width: 180 }
    ]
  },
  cip: {
    url: '/cip/',
    deleteUrl: '/site/delete/',
    exportUrl: '/cip/export/',
    exportName: 'C段',
    searchFields: [
      { label: 'C段', key: 'cidr_ip', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '变更状态', key: 'change_status', width: 100, align: 'center' },
      { title: 'C段', dataIndex: 'cidr_ip', key: 'cidr_ip', width: 300 },
      { title: 'IP数', key: 'ip_count_col', width: 150, align: 'center' },
      { title: '域名数', key: 'domain_count_col', width: 150, align: 'center' }
    ]
  },
  nuclei_result: {
    url: '/nuclei_result/',
    deleteUrl: '/nuclei_result/delete/',
    searchFields: [
      { label: '模版ID', key: 'template_id', operator: '=' },
      { label: '目标', key: 'target', operator: '=' },
      { label: '漏洞URL', key: 'vuln_url', operator: '=' },
      { label: '漏洞名称', key: 'vuln_name', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '变更状态', key: 'change_status', width: 100, align: 'center' },
      { title: '模版ID', dataIndex: 'template_id', key: 'template_id', width: 180 },
      { title: '目标', dataIndex: 'target', key: 'target', width: 200 },
      { title: '漏洞URL', key: 'nuclei_vuln_url', width: 300 },
      { title: '漏洞名称', dataIndex: 'vuln_name', key: 'vuln_name', width: 200 },
      { title: '漏洞等级', dataIndex: 'vuln_severity', key: 'vuln_severity', width: 100, align: 'center' },
      { title: '保存时间', dataIndex: 'insert_time', key: 'insert_time', width: 160 },
      { title: '验证命令', key: 'verify_command', width: 350 }
    ]
  },
  stat_finger: {
    url: '/stat_finger/',
    deleteUrl: '/site/delete/',
    searchFields: [
      { 
        label: 'finger', 
        key: 'name', 
        operator: '模糊匹配',
        hasOperatorSelect: true,
        operators: ['模糊匹配', '精确匹配']
      }
    ],
    cols: [
      { title: '序号', key: 'index', width: 80, align: 'center' },
      { title: '变更状态', key: 'change_status', width: 100, align: 'center' },
      { title: 'finger', key: 'finger_name', width: 500 }, // 用专用 key 渲染青蓝字体
      { title: '数量', dataIndex: 'cnt', key: 'cnt', width: 200 }
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
        label: '记录类型',
        key: 'record_type',
        operator: '='
      },
      { label: '内容', key: 'content', operator: '=' },
      { label: '来源 JS', key: 'source', operator: '=' },
      { label: '来源站点', key: 'site', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '变更状态', key: 'change_status', width: 100, align: 'center' },
      { title: '记录类型', dataIndex: 'record_type', key: 'record_type', width: 120 },
      { title: '内容', dataIndex: 'content', key: 'content', width: 250 },
      { title: '来源 JS', key: 'wih_source', width: 450 },
      { title: '来源站点', dataIndex: 'site', key: 'wih_site', width: 250 }
    ]
  }
});

const columns = ref(tabConfig.site.cols);

// 加载数据 (兼容单任务与全局查看)
const fetchData = async (isPolling = false) => {
  const taskId = query.task_id;
  // 🚨 核心修改 1：删除了 if (!taskId) return; 让全局查看也能放行！

  const config = tabConfig[activeTab.value];
  if (!config) {
    dataSource.value = [];
    return;
  }

  if (!isPolling) {
    loading.value = true;
  }
  try {
    // 🚨 核心修改 2：动态拼装参数，有 taskId 才传
    const params = { page: pagination.current, size: pagination.pageSize };
    if (taskId) {
      params.task_id = taskId;
    }

    for (const key in searchForm.value) {
      if (searchForm.value[key] !== '' && searchForm.value[key] != null) {
        let paramKey = key;
        const fieldConfig = config.searchFields?.find(f => f.key === key);
        if (fieldConfig && fieldConfig.hasOperatorSelect) {
          if (fieldConfig.operator === '大于') paramKey += '__gt';
          else if (fieldConfig.operator === '小于') paramKey += '__lt';
          else if (fieldConfig.operator === '不等于') paramKey += '__neq';
          else if (fieldConfig.operator === '不包含') paramKey += '__not';
          else if (fieldConfig.operator === '精确匹配') paramKey += '__eq';
        }
        params[paramKey] = searchForm.value[key];
      }
    }

    const res = await request.get(config.url, { params });
    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      selectedRowKeys.value = [];
    }
  } catch (error) {
    if (!isPolling) {
      message.error('加载资产数据失败');
    }
  } finally {
    if (!isPolling) {
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
  const config = tabConfig[activeTab.value];
  if (!config || !config.exportUrl) return;

  try {
    message.loading({ content: `正在生成${config.exportName}导出文件...`, key: 'export_data' });

    const params = { page: 1, size: 100000 };
    if (query.task_id) params.task_id = query.task_id;
    for (const key in searchForm.value) {
      if (searchForm.value[key] !== '' && searchForm.value[key] != null) {
        let paramKey = key;
        const fieldConfig = config.searchFields?.find(f => f.key === key);
        if (fieldConfig && fieldConfig.hasOperatorSelect) {
          if (fieldConfig.operator === '大于') paramKey += '__gt';
          else if (fieldConfig.operator === '小于') paramKey += '__lt';
          else if (fieldConfig.operator === '不等于') paramKey += '__neq';
          else if (fieldConfig.operator === '不包含') paramKey += '__not';
          else if (fieldConfig.operator === '精确匹配') paramKey += '__eq';
        }
        params[paramKey] = searchForm.value[key];
      }
    }

    const res = await request.get(config.exportUrl, {
      params,
      responseType: 'blob'
    });

    const blob = new Blob([res], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_${activeTab.value}_Export_${query.task_id ? query.task_id.substring(0, 8) : 'Global'}.txt`;
    document.body.appendChild(link);
    link.click();

    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: `${config.exportName}导出成功！`, key: 'export_data', duration: 2 });
  } catch (error) {
    console.error('导出异常:', error);
    message.error({ content: '导出异常，请查看控制台', key: 'export_data', duration: 2 });
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
    message.error('未能获取到有效的资产ID，请按 F12 检查接口返回的字段名！');
    return;
  }

  const config = tabConfig[activeTab.value];
  if (!config || !config.deleteUrl) {
    message.warning('当前资产类型暂不支持批量删除');
    return;
  }

  Modal.confirm({
    title: '操作确认',
    icon: createVNode(ExclamationCircleOutlined),
    content: `确认要删除选中的 ${validKeys.length} 项资产吗？`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        // 3. 将干净的有效 ID 数组发送给后端
        const res = await request.post(config.deleteUrl, {
          _id: validKeys
        });

        if (res.code === 200) {
          message.success(`成功删除 ${validKeys.length} 项资产！`);
          selectedRowKeys.value = []; // 清空勾选
          fetchData(); // 重新拉取表格数据更新界面
        } else {
          message.error('删除失败: ' + (res.message || '未知错误'));
        }
      } catch (error) {
        console.error('批量删除异常:', error);
      }
    }
  });
};

const onSearch = () => {
  pagination.current = 1;
  fetchData();
};

const resetSearch = () => {
  searchForm.value = {};
  onSearch();
};

const handleTableChange = (page, pageSize) => {
  pagination.current = page;
  pagination.pageSize = pageSize;
  fetchData();
};

// 💡 独立任务日志状态与拉取机制 (与通用资产表格及 pagination 彻底解耦，防止污染全局分页)
const syslogList = ref([]);
const syslogLoading = ref(false);
let syslogTimer = null;

const fetchSyslog = async (isPolling = false) => {
  const taskId = query.task_id;
  if (!taskId) return;
  try {
    if (!isPolling) syslogLoading.value = true;
    const res = await request.get('/syslog/', {
      params: {
        task_id: taskId,
        size: 5000,
        order: 'create_time',
        _t: Date.now()
      }
    });
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
      message.error('加载任务日志失败');
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
  const taskId = query.task_id;
  if (!taskId) return;
  try {
    const res = await request.get('/task/', { params: { _id: taskId } });
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

      // 如果任务已结束，停止轮询
      if (task.status === 'done' || task.status === 'error' || task.status === 'stop') {
        stopTaskStatusTimer();
      }
    }
  } catch (err) {
    console.error('拉取任务全局状态失败:', err);
  }
};

const startTaskStatusTimer = () => {
  if (!query.task_id) return;
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

watch(activeTab, (newVal) => {
  if (newVal === 'syslog') {
    stopSyslogTimer();
    startSyslogTimer();
  } else if (tabConfig[newVal]) {
    stopSyslogTimer();
    columns.value = tabConfig[newVal].cols;
    searchForm.value = {};
    pagination.current = 1;
    fetchData();
  } else {
    stopSyslogTimer();
    dataSource.value = [];
    columns.value = [];
  }
});

onMounted(() => {
  if (activeTab.value === 'syslog') {
    startSyslogTimer();
  } else {
    fetchData();
  }
  startTaskStatusTimer();
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
    message.warning('当前没有可下发的资产目标！');
    return;
  }

  riskForm.policy_id = undefined;
  riskForm.name = '';
  currentResultSetId.value = '';

  message.loading({ content: '正在打包资产并拉取策略...', key: 'risk_prepare' });

  try {
    const policyPromise = request.get('/policy/', { params: { size: 1000 } });

    const setParams = {};
    if (hasSelected.value) {
      setParams._id = selectedRowKeys.value.join(',');
    } else {
      if (query.task_id) setParams.task_id = query.task_id;
      for (const key in searchForm.value) {
        if (searchForm.value[key] !== '' && searchForm.value[key] != null) {
          setParams[key] = searchForm.value[key];
        }
      }
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

    message.success({ content: '数据准备就绪', key: 'risk_prepare', duration: 2 });
    riskVisible.value = true;
  } catch (error) {
    console.error('准备风险任务异常:', error);
    message.error({ content: '准备数据失败，请查看控制台', key: 'risk_prepare', duration: 2 });
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
    message.warning('请选择策略并输入任务名称');
    return;
  }
  if (!currentResultSetId.value) {
    message.error('未能获取到资产集合 ID，请关闭弹窗重试');
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
      message.success('风险任务下发成功 🚀');
      riskVisible.value = false;
      selectedRowKeys.value = [];
    } else {
      message.error('下发失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    message.error('网络请求异常');
  } finally {
    riskSubmitLoading.value = false;
  }
};




</script>

<style scoped>
.site-header { line-height: 1.5; word-break: break-all; }
.site-img { width: 16px; height: 16px; margin-right: 8px; vertical-align: middle; }
.site-word { color: var(--arl-text-color); opacity: 0.45; font-size: 12px; margin: 4px 0; }
/* 完美复刻原版的 "添加标签" 按钮 (灰色虚线框) */
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
/* 完美复刻 Favicon Hash 的次级文本灰色与紧凑间距 */
/* 修复 Favicon Hash 发虚的问题：恢复原版字号和深色 */
.site-word {
  color: var(--arl-text-color) !important; /* 恢复为标准的深黑色，去掉导致发虚的浅灰 */
  font-size: 14px !important;            /* 恢复标准字号，不缩小 */
  margin-top: 4px;
  margin-bottom: 0;
  line-height: 1.5;
}
</style>