<template>
  <div style="background-color: var(--arl-bg-layout); padding: 24px; min-height: calc(100vh - 64px);">
    <div ref="actionBarRef" style="position: sticky; top: 0px; z-index: 10; background-color: var(--arl-bg-layout); margin: -24px -24px 16px -24px; padding: 24px 24px 16px 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">

    <a-page-header
      @back="() => $router.push('/group')"
      style="padding: 0 0 24px 0;"
    >
      <template #title>
        <span>{{ targetName }}相关资产</span>
      </template>
    </a-page-header>

        <a-tabs v-model:activeKey="activeTab" type="card" class="arl-detail-tabs" style="margin-bottom: 16px;">
      <a-tab-pane key="site_chain" tab="全链路画像"></a-tab-pane>
      <a-tab-pane key="site" tab="站点"></a-tab-pane>
      <a-tab-pane key="domain" tab="子域名"></a-tab-pane>
      <a-tab-pane key="ip" tab="IP"></a-tab-pane>
      <a-tab-pane key="cert" tab="SSL证书"></a-tab-pane>
      <a-tab-pane key="service" tab="服务"></a-tab-pane>
      <a-tab-pane key="fileleak" tab="文件泄露"></a-tab-pane>
      <a-tab-pane key="url" tab="URL信息"></a-tab-pane>
      <a-tab-pane key="cip" tab="C段"></a-tab-pane>
      <a-tab-pane key="stat_finger" tab="指纹统计"></a-tab-pane>
      <a-tab-pane key="wih" tab="WIH"></a-tab-pane>
      <a-tab-pane key="vuln" tab="风险"></a-tab-pane>
      <a-tab-pane key="npoc_service" tab="服务（python）"></a-tab-pane>
      <a-tab-pane key="nuclei_result" tab="nuclei"></a-tab-pane>
    </a-tabs>

    <!-- 全链路画像专属搜索栏 -->
    <div v-if="activeTab === 'site_chain'" style="margin-bottom: 16px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
      <span style="font-weight: 500; font-size: 14px; color: var(--arl-text-color);">子域名/IP 查询：</span>
      <a-auto-complete
        v-model:value="chainSearchDomain"
        :options="domainSuggestions"
        style="width: 360px;"
        placeholder="请输入或选择子域名/IP（回车直接搜索）"
        allow-clear
        @select="(val) => handleChainSearch(val)"
        @search="handleDomainSearchInput"
        @pressEnter="() => handleChainSearch()"
      />
      <a-button type="primary" :loading="chainLoading" @click="() => handleChainSearch()">
        <template #icon><search-outlined /></template>
        查 询
      </a-button>
      <a-button @click="resetChainSearch">清 除</a-button>
      <a-button v-if="chainData" @click="downloadChainJson">
        <template #icon><download-outlined /></template>
        导出画像 (JSON)
      </a-button>
      <span v-if="chainData" style="font-size: 13px; color: var(--arl-text-secondary); margin-left: 8px;">
        已命中关联 IP: <b style="color: var(--arl-primary-color); font-family: monospace;">{{ chainData.resolved_ips?.length || 0 }}</b> 个
      </span>
    </div>

    <div v-if="tabConfig[activeTab]?.searchFields" style="margin-bottom: 16px;">
      <a-form :model="searchForm" layout="inline" style="row-gap: 16px;">
      <a-form-item v-for="field in tabConfig[activeTab].searchFields" :key="field.key" :label="field.label + '：'">
                <a-select
            v-if="field.type === 'select'"
            v-model:value="searchForm[field.key]"
            :placeholder="`请选择${field.label}进行搜索`"
            style="width: 180px;"
            allowClear
            @change="onSearch"
        >
          <a-select-option v-for="opt in field.options" :key="opt.value" :value="opt.value">{{ opt.label }}</a-select-option>
        </a-select>

        <a-range-picker
            v-else-if="field.type === 'dateRange'"
            v-model:value="searchForm[field.key]"
            :placeholder="['开始日期', '结束日期']"
            style="width: 260px;"
            @change="onSearch"
        />

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
            :placeholder="`请输入${field.label}进行搜索`"
            style="width: 180px;"
            allowClear
            @pressEnter="onSearch"
        >
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
        </a-input>
      </a-form-item>
      </a-form>
    </div>

    <div v-if="activeTab !== 'site_chain'" style="margin-bottom: 16px; display: flex; gap: 8px;">
      <a-button @click="resetSearch">清 除</a-button>
      <a-button :disabled="!hasSelected" @click="handleBatchDelete">批量删除</a-button>
      <a-button v-if="activeTab === 'site'" type="primary" @click="openAddSiteModal">添加站点</a-button>
      <a-button v-if="activeTab === 'domain'" type="primary" @click="openAddDomainModal">添加子域名</a-button>

      <a-button v-if="activeTab !== 'ip' && tabConfig[activeTab]?.exportUrl" type="primary" @click="handleExport">导出{{ tabConfig[activeTab].tabName }}</a-button>
      <template v-if="activeTab === 'ip'">
        <a-button type="primary" @click="handleIPExport('port')">导出 IP 端口</a-button>
        <a-button type="primary" @click="handleIPExport('domain')">导出域名</a-button>
        <a-button type="primary" @click="handleIPExport('ip')">导出IP</a-button>
      </template>
      <a-button v-if="activeTab === 'site'" type="primary" @click="openRiskModal">风险任务下发</a-button>
    </div>
    </div>

    <a-table v-if="activeTab !== 'site_chain'" :sticky="stickyConfig" :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }" :loading="loading" :dataSource="dataSource" :columns="columns" :pagination="false" :scroll="{ x: 'max-content' }" size="middle" :rowKey="(record) => record._id || record.id">
      <template #bodyCell="{ column, record, index }">

        <template v-if="column.key === 'index'">
          <a style="">{{ (pagination.current - 1) * pagination.pageSize + index + 1 }}</a>
        </template>

        <template v-else-if="column.key === 'site'">
          <div class="site-header">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
              <a :href="record.site || record.url" target="_blank" style="font-weight: 500; word-break: break-all;">
                <img v-if="record.favicon && record.favicon.data" :src="`data:image/png;base64,${record.favicon.data}`" class="site-img" />
                {{ record.site || record.url }}
              </a>
              <a-button type="link" size="small" style="padding: 0; height: auto; font-size: 12px; flex-shrink: 0;" @click="jumpToChain(record.hostname || record.site)">
                <compass-outlined />画像
              </a-button>
            </div>
            <div class="mt5" style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">
              <!-- 1. 置顶渲染「待测试」标签，主题色自适应柔和质感 + Popconfirm 防误触删除 -->
              <a-popconfirm
                v-if="getTags(record).includes('待测试')"
                title="确定移除「待测试」标签吗？"
                ok-text="确认"
                cancel-text="取消"
                @confirm="handleDeleteTag(record, '待测试')"
              >
                <a-tag
                  closable
                  class="tag-pending-test"
                  @close.prevent
                >待测试</a-tag>
              </a-popconfirm>

              <!-- 2. 渲染「入口」标签 -->
              <a-popconfirm
                v-if="getTags(record).includes('入口')"
                title="确定移除「入口」标签吗？"
                ok-text="确认"
                cancel-text="取消"
                @confirm="handleDeleteTag(record, '入口')"
              >
                <a-tag
                  closable
                  style="background: var(--arl-bg-light); color: var(--arl-text-color); border-color: var(--arl-border-color);"
                  @close.prevent
                >入口</a-tag>
              </a-popconfirm>

              <!-- 3. 渲染其余业务自定义标签 -->
              <template v-for="(t, idx) in getTags(record)" :key="idx">
                <a-popconfirm
                  v-if="t !== '待测试' && t !== '入口'"
                  :title="`确定移除「${t}」标签吗？`"
                  ok-text="确认"
                  cancel-text="取消"
                  @confirm="handleDeleteTag(record, t)"
                >
                  <a-tag
                    closable
                    style="background: var(--arl-bg-light); color: var(--arl-text-color); border-color: var(--arl-border-color);"
                    @close.prevent
                  >{{ t }}</a-tag>
                </a-popconfirm>
              </template>
              <span class="add-tag" @click="openTagModal(record)" style="cursor: pointer;">添加标签</span>
            </div>
          </div>
        </template>

        <template v-else-if="column.key === 'screenshot'">
          <img v-if="record.screenshot" :src="`/api${record.screenshot}`" style="width: 280px; height: 160px; object-fit: cover; object-position: top; cursor: pointer; border: 1px solid var(--arl-border-color); border-radius: 4px;" @click="handlePreview(`/api${record.screenshot}`)" />
          <span v-else>-</span>
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

        <template v-else-if="column.key === 'headers'"><div class="scroll-x"><pre>{{ record.headers }}</pre></div></template>
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

        <template v-else-if="column.key === 'record'">
          <div v-if="record.record && record.record.length"><div v-for="(r, i) in record.record" :key="i">{{ r }}</div></div>
          <span v-else-if="typeof record.record === 'string'">{{ record.record }}</span>
          <span v-else>-</span>
        </template>
        <template v-else-if="column.key === 'ips'">
          <div v-if="record.ips && record.ips.length">
            <a-tooltip v-if="record.ips.length > 5" placement="top" :overlayInnerStyle="{ maxHeight: '400px', overflowY: 'auto' }">
              <template #title><div v-for="(ip, i) in record.ips" :key="'all-ip-'+i">{{ ip }}</div></template>
              <div style="cursor: pointer;">
                <div v-for="(ip, i) in record.ips.slice(0, 5)" :key="i">{{ ip }}</div>
                <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 2px;">...等 {{ record.ips.length }} 个</div>
              </div>
            </a-tooltip>
            <div v-else><div v-for="(ip, i) in record.ips" :key="i">{{ ip }}</div></div>
          </div>
          <span v-else>-</span>
        </template>

        <template v-else-if="column.key === 'ip'">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <span style="font-weight: 500; font-family: monospace;">{{ record.ip }}</span>
            <a-button type="link" size="small" style="padding: 0; height: auto; font-size: 12px; flex-shrink: 0;" @click="jumpToChain(record.ip)">
              <compass-outlined />画像
            </a-button>
          </div>
        </template>

        <template v-else-if="column.key === 'port_info'">
          <span>{{ record.port_info && record.port_info.length ? record.port_info.map(p => p.port_id).join(', ') : '-' }}</span>
        </template>
        <template v-else-if="column.key === 'os_info'"><span>{{ record.os_info?.name || '-' }}</span></template>
        <template v-else-if="column.key === 'geo_city'"><span>{{ formatGeo(record.geo_city) }}</span></template>
        <template v-else-if="column.key === 'geo_asn'"><span>{{ record.geo_asn?.organization || '-' }}</span></template>
        <template v-else-if="column.key === 'domain'">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <div v-if="Array.isArray(record.domain)">
              <div v-for="(dom, i) in record.domain" :key="i">{{ dom }}</div>
            </div>
            <span v-else style="font-weight: 500;">{{ record.domain }}</span>
            <a-button v-if="!Array.isArray(record.domain)" type="link" size="small" style="padding: 0; height: auto; font-size: 12px; flex-shrink: 0;" @click="jumpToChain(record.domain)">
              <compass-outlined />画像
            </a-button>
          </div>
        </template>

        <template v-else-if="column.key === 'source'">
          <div style="word-break: break-all; color: var(--arl-text-color); line-height: 1.6;">
            <a :href="record.source" target="_blank" style="color: var(--arl-text-color); text-decoration: none;">
              {{ record.source || '-' }}
            </a>
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

      
        <template v-else-if="column.key === 'cert_detail'">
          <div v-if="record.cert" style="font-size: 13px; line-height: 1.8; color: var(--arl-text-color); padding: 12px 0;">
            <div style="font-weight: 600; font-size: 14px; margin-bottom: 12px;">基本信息</div>
            <div style="display: flex; margin-bottom: 6px;"><div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">主题名称</div><div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.subject_dn || '-' }}</div></div>
            <div style="display: flex; margin-bottom: 6px;"><div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">签发者名称</div><div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.issuer_dn || '-' }}</div></div>
            <div style="display: flex; margin-bottom: 6px;"><div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">使用者备用名称</div><div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.extensions?.subjectAltName || '-' }}</div></div>
            <div style="display: flex; margin-bottom: 6px;"><div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">序列号</div><div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.serial_number || '-' }}</div></div>
            <div style="display: flex; margin-bottom: 16px;"><div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">时间</div><div style="flex: 1; color: var(--arl-text-color);">{{ record.cert.validity?.start || '-' }} 至 {{ record.cert.validity?.end || '-' }}</div></div>
            <div style="font-weight: 600; font-size: 14px; margin-bottom: 12px;">指纹</div>
            <div style="display: flex; margin-bottom: 6px;"><div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">SHA-256</div><div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.fingerprint?.sha256 || '-' }}</div></div>
            <div style="display: flex; margin-bottom: 6px;"><div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">SHA-1</div><div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.fingerprint?.sha1 || '-' }}</div></div>
            <div style="display: flex; margin-bottom: 6px;"><div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">MD5</div><div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.fingerprint?.md5 || '-' }}</div></div>
          </div>
          <span v-else>-</span>
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
                查看全部 (共 {{ record.service_info.length }} 项) &gt;&gt;
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
          <a :href="record.url || record.vuln_url" target="_blank" style="word-break: break-all;">{{ record.url || record.vuln_url || '-' }}</a>
        </template>
        <template v-else-if="column.key === 'verify_data'">
          <div style="max-height: 100px; overflow-y: auto; color: #e57373; font-family: monospace; font-size: 12px; word-break: break-all;">{{ record.verify_data || record.proof || '-' }}</div>
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
          <div style="max-height: 100px; overflow-y: auto; background: var(--arl-bg-light); padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 12px; word-break: break-all;">{{ record.verify_command || record.curl_command || '-' }}</div>
        </template>
        <template v-else-if="column.key === 'finger_name'">
          <a style="cursor: pointer;" @click="openFingerModal(record.name)">{{ record.name || '-' }}</a>
        </template>
        <template v-else-if="column.key === 'host'">
          <span>{{ record.ip || record.host }}{{ record.port ? ':' + record.port : '' }}</span>
        </template>
        <template v-else-if="column.key === 'update_date'">
          <span>{{ record.update_date || record.insert_time || '-' }}</span>
        </template>

      </template>
    </a-table>

    <!-- ================= 站点信息查询（全链路透视画像） ================= -->
    <template v-if="activeTab === 'site_chain'">
      <!-- 1. 初始未搜索：空白引导态 -->
      <div v-if="!chainSearched" style="background: var(--arl-bg-white); border-radius: 8px; padding: 70px 24px; text-align: center; border: 1px dashed var(--arl-border-color); margin-top: 8px;">
        <a-empty description="请输入或选择子域名展开全链路资产画像">
          <template #image>
            <compass-outlined style="font-size: 64px; color: var(--arl-theme-color); opacity: 0.75;" />
          </template>
          <div style="color: var(--arl-text-secondary); margin-top: 12px; font-size: 13px;">
            自上而下顺次透视：站点元数据与截图 ➔ 子域名解析 ➔ 关联IP与归属 ➔ 关联C段网段 ➔ SSL证书 ➔ 开放服务与NPOC ➔ 敏感文件、URL与WIH ➔ 风险漏洞与Nuclei
          </div>
        </a-empty>
      </div>

      <!-- 2. 查询中或已有数据时的展示区 -->
      <a-spin v-else :spinning="chainLoading" tip="正在全息聚合各资产板块数据...">
        <div v-if="chainData" style="display: flex; flex-direction: column; gap: 16px; margin-top: 8px;">

          <!-- 板块 1：站点基础信息与截图 (chainData.site) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <global-outlined class="chain-icon" />
                <span class="chain-title">站点基础信息</span>
                <a-badge :count="chainData.site?.length || 0" :number-style="{ backgroundColor: '#1890ff' }" style="margin-left: 8px;" />
              </div>
            </template>

            <div v-if="!chainData.site || chainData.site.length === 0" class="chain-empty-tip">
              暂无关联站点记录
            </div>
            <div v-else style="display: flex; flex-direction: column; gap: 16px;">
              <div v-for="siteItem in chainData.site" :key="siteItem._id || siteItem.site" class="chain-site-item">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; flex-wrap: wrap;">
                  <!-- 站点详情信息 -->
                  <div style="flex: 1; min-width: 320px;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                      <img v-if="siteItem.favicon && siteItem.favicon.data" :src="`data:image/png;base64,${siteItem.favicon.data}`" class="site-img" />
                      <a :href="siteItem.site" target="_blank" style="font-size: 16px; font-weight: 600; color: var(--arl-theme-color); word-break: break-all;">
                        {{ siteItem.site }}
                      </a>
                      <a-tag :color="siteItem.status === 200 ? 'success' : (siteItem.status >= 400 ? 'error' : 'default')">
                        HTTP {{ siteItem.status || '-' }}
                      </a-tag>
                    </div>

                    <div class="chain-info-grid">
                      <div class="chain-info-row">
                        <span class="chain-info-label">网页标题：</span>
                        <span class="chain-info-value" style="font-weight: 500;">{{ siteItem.title || '-' }}</span>
                      </div>
                      <div class="chain-info-row">
                        <span class="chain-info-label">Web Server：</span>
                        <span class="chain-info-value">{{ siteItem.http_server || '-' }}</span>
                      </div>
                      <div class="chain-info-row">
                        <span class="chain-info-label">关联 IP：</span>
                        <span class="chain-info-value" style="font-family: monospace;">{{ siteItem.ip || '-' }}</span>
                      </div>
                      <div class="chain-info-row">
                        <span class="chain-info-label">更新时间：</span>
                        <span class="chain-info-value">{{ siteItem.update_date || siteItem.save_date || '-' }}</span>
                      </div>
                      <div class="chain-info-row">
                        <span class="chain-info-label">指纹识别：</span>
                        <div class="chain-info-value" style="display: flex; flex-wrap: wrap; gap: 4px;">
                          <template v-if="siteItem.finger && siteItem.finger.length > 0">
                            <a-tag v-for="f in siteItem.finger" :key="f.name" color="blue">{{ f.name }}</a-tag>
                          </template>
                          <span v-else>-</span>
                        </div>
                      </div>
                      <div class="chain-info-row">
                        <span class="chain-info-label">业务标签：</span>
                        <div class="chain-info-value" style="display: flex; flex-wrap: wrap; gap: 4px;">
                          <template v-if="getTags(siteItem) && getTags(siteItem).length > 0">
                            <a-tag v-for="t in getTags(siteItem)" :key="t" color="orange">{{ t }}</a-tag>
                          </template>
                          <span v-else>-</span>
                        </div>
                      </div>
                      <div v-if="siteItem.headers" class="chain-info-row">
                        <span class="chain-info-label">响应标头：</span>
                        <a-popover placement="bottomLeft" trigger="click">
                          <template #content>
                            <pre style="max-height: 250px; max-width: 500px; overflow: auto; font-size: 11px; margin: 0;">{{ siteItem.headers }}</pre>
                          </template>
                          <a-button type="link" size="small" style="padding: 0; height: auto;">查看 Headers</a-button>
                        </a-popover>
                      </div>
                    </div>
                  </div>

                  <!-- 站点网页截图预览 -->
                  <div style="width: 240px; text-align: center; flex-shrink: 0;">
                    <div v-if="siteItem.screenshot" style="border: 1px solid var(--arl-border-color); border-radius: 4px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06); cursor: pointer;" @click="handlePreview(`/api${siteItem.screenshot}`)">
                      <img :src="`/api${siteItem.screenshot}`" style="width: 100%; height: 140px; object-fit: cover; object-position: top; display: block;" />
                      <div style="background: var(--arl-bg-light); font-size: 11px; padding: 4px; color: var(--arl-text-secondary);">点击放大截图</div>
                    </div>
                    <div v-else style="width: 100%; height: 140px; border: 1px dashed var(--arl-border-color); border-radius: 4px; display: flex; align-items: center; justify-content: center; color: var(--arl-text-secondary); font-size: 12px; background: var(--arl-bg-light);">
                      暂无网页截图
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </a-card>

          <!-- 板块 2：子域名与解析记录 (chainData.domain_records) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <link-outlined class="chain-icon" />
                <span class="chain-title">子域名与解析记录</span>
                <a-badge :count="chainData.domain_records?.length || 0" :number-style="{ backgroundColor: '#52c41a' }" style="margin-left: 8px;" />
              </div>
            </template>
            <a-table
              :dataSource="chainData.domain_records || []"
              :columns="chainDomainCols"
              :pagination="false"
              size="middle"
              :rowKey="(record) => record._id || record.id || record.domain"
              :locale="{ emptyText: '暂无子域名解析记录' }"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                <template v-else-if="column.key === 'domain'"><span style="font-weight: 500;">{{ record.domain }}</span></template>
                <template v-else-if="column.key === 'record'">
                  <div v-if="Array.isArray(record.record)"><div v-for="(r, i) in record.record" :key="i">{{ r }}</div></div>
                  <span v-else>{{ record.record || '-' }}</span>
                </template>
                <template v-else-if="column.key === 'ips'">
                  <div v-if="Array.isArray(record.ips)"><div v-for="(ip, i) in record.ips" :key="i" style="font-family: monospace;">{{ ip }}</div></div>
                  <span v-else>{{ record.ips || '-' }}</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 板块 3：IP 与网络归属 (chainData.ip) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <cloud-server-outlined class="chain-icon" />
                <span class="chain-title">IP 与网络归属</span>
                <a-badge :count="chainData.ip?.length || 0" :number-style="{ backgroundColor: '#722ed1' }" style="margin-left: 8px;" />
              </div>
            </template>
            <a-table
              :dataSource="chainData.ip || []"
              :columns="chainIpCols"
              :pagination="false"
              :scroll="{ x: 'max-content' }"
              size="middle"
              :rowKey="(record) => record._id || record.id || record.ip"
              :locale="{ emptyText: '暂无关联 IP 资产记录' }"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                <template v-else-if="column.key === 'ip'"><span style="font-weight: 500; font-family: monospace;">{{ record.ip }}</span></template>
                <template v-else-if="column.key === 'port_info'">
                  <span v-if="record.port_info && record.port_info.length">{{ record.port_info.map(p => p.port_id).join(', ') }}</span>
                  <span v-else>-</span>
                </template>
                <template v-else-if="column.key === 'os_info'"><span>{{ record.os_info?.name || '-' }}</span></template>
                <template v-else-if="column.key === 'domain'">
                  <div v-if="Array.isArray(record.domain) && record.domain.length">
                    <div v-for="(dom, i) in record.domain" :key="i" style="font-family: monospace;">{{ dom }}</div>
                  </div>
                  <span v-else-if="record.domain && !Array.isArray(record.domain)" style="font-family: monospace;">{{ record.domain }}</span>
                  <span v-else>-</span>
                </template>
                <template v-else-if="column.key === 'geo_city'"><span>{{ formatGeo(record.geo_city) }}</span></template>
                <template v-else-if="column.key === 'geo_asn'"><span>{{ record.geo_asn?.organization || '-' }}</span></template>
              </template>
            </a-table>
          </a-card>

          <!-- 板块 4：关联 C 段网段 (chainData.cip) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <cluster-outlined class="chain-icon" />
                <span class="chain-title">关联 C 段网段</span>
                <a-badge :count="chainData.cip?.length || 0" :number-style="{ backgroundColor: '#eb2f96' }" style="margin-left: 8px;" />
              </div>
            </template>
            <a-table
              :dataSource="chainData.cip || []"
              :columns="chainCipCols"
              :pagination="false"
              size="middle"
              :rowKey="(record) => record._id || record.id || record.cidr_ip"
              :locale="{ emptyText: '暂无关联 C 段资产记录' }"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                <template v-else-if="column.key === 'cidr_ip'">
                  <a style="cursor: pointer; font-family: monospace; font-size: 14px; font-weight: 600; color: var(--arl-primary-color);" @click="openCidrDetail(record)">
                    {{ record.cidr_ip || '-' }}
                  </a>
                </template>
                <template v-else-if="column.key === 'ip_count'">
                  <a-tag color="purple" style="font-family: monospace;">
                    {{ record.ip_count ?? (record.ip_list ? record.ip_list.length : 0) }} 个 IP
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'domain_count'">
                  <a-tag color="blue" style="font-family: monospace;">
                    {{ record.domain_count ?? (record.domain_list ? record.domain_list.length : 0) }} 个域名
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'update_date'">
                  <span style="font-size: 13px; color: var(--arl-text-secondary);">
                    {{ record.update_date || record.save_date || '-' }}
                  </span>
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" size="small" @click="openCidrDetail(record)">
                    查看详情
                  </a-button>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 板块 5：SSL 证书 (chainData.cert) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <safety-certificate-outlined class="chain-icon" />
                <span class="chain-title">SSL 证书</span>
                <a-badge :count="chainData.cert?.length || 0" :number-style="{ backgroundColor: '#13c2c2' }" style="margin-left: 8px;" />
              </div>
            </template>
            <a-table
              :dataSource="chainData.cert || []"
              :columns="chainCertCols"
              :pagination="false"
              size="middle"
              :rowKey="(record) => record._id || record.id"
              :locale="{ emptyText: '暂无关联 SSL 证书' }"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                <template v-else-if="column.key === 'host'"><span>{{ record.ip || record.host }}{{ record.port ? ':' + record.port : '' }}</span></template>
                <template v-else-if="column.key === 'cert_detail'">
                  <div v-if="record.cert" style="font-size: 12px; line-height: 1.6;">
                    <div><b>主题名称：</b>{{ record.cert.subject_dn || '-' }}</div>
                    <div><b>签发者：</b>{{ record.cert.issuer_dn || '-' }}</div>
                    <div v-if="record.cert.extensions?.subjectAltName"><b>备用名 (SAN)：</b>{{ record.cert.extensions.subjectAltName }}</div>
                    <div><b>有效期限：</b>{{ record.cert.validity?.start || '-' }} 至 {{ record.cert.validity?.end || '-' }}</div>
                  </div>
                  <span v-else>-</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 板块 6：开放服务与 NPOC (chainData.service & chainData.npoc_service) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <api-outlined class="chain-icon" />
                <span class="chain-title">开放服务与 NPOC</span>
                <a-badge :count="(chainData.service?.length || 0) + (chainData.npoc_service?.length || 0)" :number-style="{ backgroundColor: '#fa8c16' }" style="margin-left: 8px;" />
              </div>
            </template>
            <div style="display: flex; flex-direction: column; gap: 16px;">
              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  🔌 资产系统服务 ({{ chainData.service?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.service || []"
                  :columns="chainServiceCols"
                  :pagination="false"
                  size="middle"
                  :rowKey="(record) => record._id || record.id"
                  :locale="{ emptyText: '暂无开放服务记录' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'service_name'"><a-tag color="cyan">{{ record.service_name }}</a-tag></template>
                    <template v-else-if="column.key === 'ip_port'">
                      <div v-if="record.service_info && record.service_info.length">
                        <div v-for="(info, i) in record.service_info" :key="i" style="font-family: monospace;">
                          {{ info.ip }}:{{ info.port_id }}
                        </div>
                      </div>
                      <span v-else>-</span>
                    </template>
                    <template v-else-if="column.key === 'product'">
                      <div v-if="record.service_info && record.service_info.length">
                        <div v-for="(info, i) in record.service_info" :key="i">
                          {{ info.product || '-' }} {{ info.version ? `(${info.version})` : '' }}
                        </div>
                      </div>
                      <span v-else>-</span>
                    </template>
                  </template>
                </a-table>
              </div>

              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  🐍 Python NPOC 探测服务 ({{ chainData.npoc_service?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.npoc_service || []"
                  :columns="chainNpocCols"
                  :pagination="false"
                  size="small"
                  :rowKey="(record) => record._id || record.id"
                  :locale="{ emptyText: '暂无 NPOC 探测服务记录' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'scheme'"><a-tag color="purple">{{ record.scheme || '-' }}</a-tag></template>
                    <template v-else-if="column.key === 'target'">
                      <span style="font-family: monospace;">{{ record.target || '-' }}</span>
                    </template>
                  </template>
                </a-table>
              </div>
            </div>
          </a-card>

          <!-- 板块 7：文件泄露、敏感 URL 与 WIH (chainData.fileleak & chainData.url & chainData.wih) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <file-search-outlined class="chain-icon" />
                <span class="chain-title">文件泄露、敏感 URL 与 WIH</span>
                <a-badge :count="(chainData.fileleak?.length || 0) + (chainData.url?.length || 0) + (chainData.wih?.length || 0)" :number-style="{ backgroundColor: '#faad14' }" style="margin-left: 8px;" />
              </div>
            </template>

            <div style="display: flex; flex-direction: column; gap: 16px;">
              <!-- 7.1 文件泄露 -->
              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  📄 疑似敏感文件泄露 ({{ chainData.fileleak?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.fileleak || []"
                  :columns="chainFileleakCols"
                  :pagination="false"
                  size="small"
                  :rowKey="(record) => record._id || record.id || record.url"
                  :locale="{ emptyText: '暂无文件泄露记录' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'url'">
                      <a :href="record.url" target="_blank" style="font-family: monospace; word-break: break-all;">
                        {{ record.url }}
                      </a>
                    </template>
                  </template>
                </a-table>
              </div>

              <!-- 7.2 关联 URL -->
              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  🔗 关联探测 URL ({{ chainData.url?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.url || []"
                  :columns="chainUrlCols"
                  :pagination="false"
                  size="small"
                  :rowKey="(record) => record._id || record.id || record.url"
                  :locale="{ emptyText: '暂无关联 URL 记录' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'url'">
                      <a :href="record.url" target="_blank" style="font-family: monospace; word-break: break-all;">
                        {{ record.url }}
                      </a>
                    </template>
                  </template>
                </a-table>
              </div>

              <!-- 7.3 WIH 敏感信息 -->
              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  🔍 WEB Info Hunter 泄露信息 ({{ chainData.wih?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.wih || []"
                  :columns="chainWihCols"
                  :pagination="false"
                  size="small"
                  :rowKey="(record) => record._id || record.id"
                  :locale="{ emptyText: '暂无 WIH 泄露记录' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'content'">
                      <span style="font-family: monospace; word-break: break-all; color: #fa8c16; font-weight: 500;">
                        {{ record.content }}
                      </span>
                    </template>
                    <template v-else-if="column.key === 'site' || column.key === 'source'">
                      <a v-if="record[column.key]" :href="record[column.key]" target="_blank" style="font-family: monospace; word-break: break-all;">
                        {{ record[column.key] }}
                      </a>
                      <span v-else>-</span>
                    </template>
                  </template>
                </a-table>
              </div>
            </div>
          </a-card>

          <!-- 板块 8：风险漏洞与 Nuclei (chainData.vuln & chainData.nuclei_result) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <bug-outlined class="chain-icon" />
                <span class="chain-title">风险漏洞与 Nuclei 结果</span>
                <a-badge :count="(chainData.vuln?.length || 0) + (chainData.nuclei_result?.length || 0)" :number-style="{ backgroundColor: '#f5222d' }" style="margin-left: 8px;" />
              </div>
            </template>

            <div style="display: flex; flex-direction: column; gap: 16px;">
              <!-- 7.1 常规漏洞 / PoC 结果 -->
              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  🛡️ 应用与服务漏洞 ({{ chainData.vuln?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.vuln || []"
                  :columns="chainVulnCols"
                  :pagination="false"
                  size="small"
                  :rowKey="(record) => record._id || record.id"
                  :locale="{ emptyText: '暂无漏洞风险记录' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'target'">
                      <a v-if="record.target && (record.target.startsWith('http://') || record.target.startsWith('https://'))" :href="record.target" target="_blank" style="word-break: break-all;">{{ record.target }}</a>
                      <span v-else style="font-family: monospace; word-break: break-all;">{{ record.target || '-' }}</span>
                    </template>
                    <template v-else-if="column.key === 'verify_data'">
                      <div style="max-height: 80px; overflow-y: auto; color: #f5222d; font-family: monospace; font-size: 12px; word-break: break-all;">
                        {{ record.verify_data || record.proof || '-' }}
                      </div>
                    </template>
                  </template>
                </a-table>
              </div>

              <!-- 7.2 Nuclei 命中结果 -->
              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  🎯 Nuclei 扫描发现 ({{ chainData.nuclei_result?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.nuclei_result || []"
                  :columns="chainNucleiCols"
                  :pagination="false"
                  size="small"
                  :rowKey="(record) => record._id || record.id"
                  :locale="{ emptyText: '暂无 Nuclei 扫描发现' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'vuln_severity'">
                      <a-tag :color="getSeverityColor(record.vuln_severity || record.vul_severity)">
                        {{ (record.vuln_severity || record.vul_severity || 'info').toUpperCase() }}
                      </a-tag>
                    </template>
                    <template v-else-if="column.key === 'vuln_url'">
                      <a v-if="(record.vuln_url || record.target) && ((record.vuln_url || record.target).startsWith('http://') || (record.vuln_url || record.target).startsWith('https://'))" :href="record.vuln_url || record.target" target="_blank" style="word-break: break-all;">
                        {{ record.vuln_url || record.target }}
                      </a>
                      <span v-else style="font-family: monospace; word-break: break-all;">{{ record.vuln_url || record.target || '-' }}</span>
                    </template>
                    <template v-else-if="column.key === 'verify_command'">
                      <div style="max-height: 80px; overflow-y: auto; background: var(--arl-bg-light); padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 11px; word-break: break-all;">
                        {{ record.verify_command || record.curl_command || '-' }}
                      </div>
                    </template>
                  </template>
                </a-table>
              </div>
            </div>
          </a-card>

        </div>
      </a-spin>
    </template>


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

    <!-- 综合C段详情弹窗 (提取为组件) -->
    <CidrDetailModal v-model:open="cipDetailModalVisible" :record="currentCidrRecord" />

    <!-- 系统服务端点详情弹窗 (提取为组件) -->
    <ServiceDetailModal v-model:open="serviceDetailModalVisible" :record="currentServiceRecord" />

    <!-- 图片预览组件 -->
    <a-modal v-model:open="previewVisible" :footer="null" width="85vw" centered @cancel="previewVisible = false" :bodyStyle="{ padding: '16px' }">
      <img :src="previewImage" style="width: 100%; max-height: 85vh; object-fit: contain; display: block;" />
    </a-modal>

    <!-- 添加标签弹窗 -->
    <a-modal v-model:open="tagVisible" title="添加标签" @ok="submitTag" :confirmLoading="tagSubmitLoading" width="400px" okText="确 定" cancelText="取 消">
      <div style="margin-top: 20px;">
        <a-input v-model:value="newTagValue" placeholder="请输入标签名称" />
      </div>
    </a-modal>


    <div v-if="tabConfig[activeTab] && activeTab !== 'site_chain'" style="display: flex; justify-content: space-between; align-items: center; padding: 0 16px; margin-top: 16px;">
      <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" />
    </div>

    <a-modal v-model:open="addSiteVisible" title="添加站点" @ok="submitAddSite" :confirmLoading="addSiteLoading" width="520px" okText="确 定" cancelText="取 消" destroyOnClose>
      <a-form ref="addSiteFormRef" :model="addSiteForm" :rules="addSiteRules" :label-col="{ span: 4 }" :wrapper-col="{ span: 19 }" style="margin-top: 20px;">
        <a-form-item label="站点" name="site">
          <a-textarea v-model:value="addSiteForm.site" :rows="4" placeholder="会对站点进行探测，获取标题、headers, finger等信息。示例：https://www.freebuf.com/" />
        </a-form-item>
        <a-form-item label="策略" name="policy_id">
          <a-select v-model:value="addSiteForm.policy_id" placeholder="请选择策略">
            <a-select-option v-for="p in policies" :key="p._id" :value="p._id">{{ p.name }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="riskModalVisible" title="添加风险巡航任务" @ok="submitRiskTask" :confirmLoading="riskLoading" width="520px" okText="确 定" cancelText="取 消" destroyOnClose>
      <a-form ref="riskFormRef" :model="riskForm" :rules="riskRules" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">

        <a-form-item label="策略名称" name="policy_id">
          <a-select v-model:value="riskForm.policy_id" placeholder="请选择策略" @change="handleRiskPolicyChange">
            <a-select-option v-for="p in policies" :key="p._id" :value="p._id">
              {{ p.name }} (PoC : {{ getPocCount(p) }})
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="任务名称" name="name">
          <a-input v-model:value="riskForm.name" placeholder="请输入任务名称" allowClear />
        </a-form-item>

        <a-form-item label="目标" style="margin-bottom: 0;">
          <span style="color: var(--arl-text-color); opacity: 0.65;">选择目标数 {{ currentTargetCount }}</span>
        </a-form-item>

      </a-form>
    </a-modal>

    <a-modal v-model:open="addDomainVisible" title="添加子域名" @ok="submitAddDomain" :confirmLoading="addDomainLoading" width="520px" okText="确 定" cancelText="取 消" destroyOnClose>
      <a-form ref="addDomainFormRef" :model="addDomainForm" :rules="addDomainRules" :label-col="{ span: 4 }" :wrapper-col="{ span: 19 }" style="margin-top: 20px;">
        <a-form-item label="子域名" name="domain">
          <a-textarea v-model:value="addDomainForm.domain" :rows="4" placeholder="会对子域名自动下发侦察任务，获取子域名关联的ip、站点等信息。示例：live.freebuf.com" />
        </a-form-item>
        <a-form-item label="策略" name="policy_id">
          <a-select v-model:value="addDomainForm.policy_id" placeholder="请选择策略">
            <a-select-option v-for="p in policies" :key="p._id" :value="p._id">{{ p.name }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

  </div>
</template>

<script setup>

import { ref, onMounted, reactive, watch, computed, createVNode, onUnmounted, nextTick } from 'vue';
import { useSticky } from '../utils/useSticky';
const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

import { useRoute, useRouter } from 'vue-router';
import request from '../utils/request';
import { formatGeo } from '../utils/formatGeo';
import { message, Modal } from 'ant-design-vue';
import * as echarts from 'echarts';
import dayjs from 'dayjs';
import CidrDetailModal from '../components/CidrDetailModal.vue';
import ServiceDetailModal from '../components/ServiceDetailModal.vue';
import {
  SearchOutlined,
  ExclamationCircleOutlined,
  LeftOutlined,
  GlobalOutlined,
  CloudServerOutlined,
  SafetyCertificateOutlined,
  ApiOutlined,
  FileSearchOutlined,
  BugOutlined,
  CompassOutlined,
  ClusterOutlined,
  LinkOutlined,
  DownloadOutlined
} from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { createTabStateCache } from '../utils/useTabStateCache';

const route = useRoute();
const router = useRouter();
// 🚨 修复 1：使用 computed，让路由参数具备真正的响应式
const scope_id = computed(() => route.query.scope_id || '');
const targetName = computed(() => route.query.targetName || '未知资产');

const isScopeSwitching = ref(false);
const activeTab = ref('site');
const loading = ref(false);
const dataSource = ref([]);

// ================= 全链路子域名画像检索逻辑 =================
const chainSearchDomain = ref('');
const chainLoading = ref(false);
const chainSearched = ref(false);
const chainData = ref(null);
const domainSuggestions = ref([]);

const chainDomainCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '子域名', dataIndex: 'domain', key: 'domain', width: 220 },
  { title: '解析类型', dataIndex: 'type', key: 'type', width: 100, align: 'center' },
  { title: '记录值', key: 'record', width: 250 },
  { title: '关联IP', key: 'ips', width: 250 },
  { title: '来源', dataIndex: 'source', key: 'source', width: 150 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const chainIpCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: 'IP', dataIndex: 'ip', key: 'ip', width: 160 },
  { title: '操作系统', key: 'os_info', width: 140 },
  { title: '开放端口', key: 'port_info', width: 220 },
  { title: '关联域名', key: 'domain', width: 250 },
  { title: 'Geo 归属', key: 'geo_city', width: 180 },
  { title: 'AS 归属', key: 'geo_asn', width: 260 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const chainCipCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: 'C段网段', dataIndex: 'cidr_ip', key: 'cidr_ip', width: 220 },
  { title: '关联 IP 数量', key: 'ip_count', width: 140, align: 'center' },
  { title: '关联域名数量', key: 'domain_count', width: 140, align: 'center' },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 },
  { title: '操作', key: 'action', width: 120, align: 'center' }
];

const chainCertCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: 'HOST', key: 'host', width: 180 },
  { title: '证书详情', key: 'cert_detail' },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const chainServiceCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '服务', dataIndex: 'service_name', key: 'service_name', width: 120, align: 'center' },
  { title: 'IP:端口', key: 'ip_port', width: 220 },
  { title: 'Product / 版本', key: 'product', width: 300 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const chainFileleakCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: 'URL', key: 'url' },
  { title: '标题', dataIndex: 'title', key: 'title', width: 200 },
  { title: '状态码', key: 'status_code', width: 90, align: 'center' },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const chainUrlCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: 'URL', key: 'url' },
  { title: '标题', dataIndex: 'title', key: 'title', width: 200 },
  { title: '状态码', key: 'status_code', width: 90, align: 'center' },
  { title: '来源', dataIndex: 'source', key: 'source', width: 140 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const chainVulnCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '漏洞名称', dataIndex: 'vul_name', key: 'vul_name', width: 220 },
  { title: '类别', dataIndex: 'vul_category', key: 'vul_category', width: 120 },
  { title: '目标', key: 'target', width: 220 },
  { title: '凭证', key: 'verify_data' },
  { title: '发现时间', dataIndex: 'insert_time', key: 'insert_time', width: 160 }
];

const chainNucleiCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '危害等级', key: 'vuln_severity', width: 100, align: 'center' },
  { title: '模版ID', dataIndex: 'template_id', key: 'template_id', width: 180 },
  { title: '漏洞名称', dataIndex: 'vuln_name', key: 'vul_name', width: 200 },
  { title: '漏洞 URL', key: 'vuln_url', width: 260 },
  { title: '验证命令', key: 'verify_command' },
  { title: '保存时间', dataIndex: 'insert_time', key: 'insert_time', width: 160 }
];

const chainNpocCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '协议', dataIndex: 'scheme', key: 'scheme', width: 120, align: 'center' },
  { title: '主机', dataIndex: 'host', key: 'host', width: 180 },
  { title: '端口', dataIndex: 'port', key: 'port', width: 90, align: 'center' },
  { title: '目标', dataIndex: 'target', key: 'target', width: 220 },
  { title: '保存时间', dataIndex: 'insert_time', key: 'insert_time', width: 180 }
];

const chainWihCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '类型', dataIndex: 'record_type', key: 'record_type', width: 120 },
  { title: '敏感内容', dataIndex: 'content', key: 'content' },
  { title: '来源 JS', dataIndex: 'source', key: 'source', width: 350 },
  { title: '来源站点', dataIndex: 'site', key: 'site', width: 220 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const syncChainQuery = (target) => {
  const currentQuery = { ...route.query };
  if (target) {
    currentQuery.chain_target = target;
  } else {
    delete currentQuery.chain_target;
  }
  router.replace({ query: currentQuery });
};

const downloadChainJson = () => {
  if (!chainData.value) {
    message.warning('当前无画像数据可导出');
    return;
  }
  try {
    const jsonStr = JSON.stringify(chainData.value, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json;charset=utf-8' });
    const blobUrl = URL.createObjectURL(blob);
    const downloadAnchor = document.createElement('a');
    const targetLabel = chainSearchDomain.value || 'target';
    const filename = `arl_chain_${targetLabel}_${dayjs().format('YYYYMMDD_HHmmss')}.json`;
    downloadAnchor.href = blobUrl;
    downloadAnchor.download = filename;
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    URL.revokeObjectURL(blobUrl);
    message.success(`已成功导出画像数据: ${filename}`);
  } catch (err) {
    message.error('导出画像数据失败');
  }
};

const jumpToChain = (target) => {
  if (!target) return;
  let dom = String(target).trim();
  if (dom.includes('://')) {
    try {
      dom = new URL(dom).hostname;
    } catch (e) {
      dom = dom.split('://')[1].split('/')[0];
    }
  } else if (dom.includes('/')) {
    dom = dom.split('/')[0];
  }
  if (dom.includes(':') && !dom.startsWith('[')) {
    dom = dom.split(':')[0];
  }
  dom = dom.replace(/^\[|\]$/g, '').trim().toLowerCase();
  chainSearchDomain.value = dom;
  activeTab.value = 'site_chain';
  nextTick(() => {
    handleChainSearch();
  });
};

const getSeverityColor = (sev) => {
  const s = String(sev || '').toLowerCase();
  if (s === 'critical') return '#f5222d';
  if (s === 'high') return '#fa541c';
  if (s === 'medium') return '#fa8c16';
  if (s === 'low') return '#faad14';
  return '#1890ff';
};

const fetchDomainSuggestions = async (keyword = '') => {
  if (!scope_id.value) return;
  try {
    const params = {
      scope_id: scope_id.value,
      page: 1,
      size: 30
    };
    if (keyword && typeof keyword === 'string' && keyword.trim()) {
      params.domain = keyword.trim();
    }
    const res = await request.get('/asset_domain/', { params });
    if (res && res.items) {
      const domains = Array.from(new Set(res.items.map(item => item.domain).filter(Boolean)));
      domainSuggestions.value = domains.map(d => ({ value: d, label: d }));
    }
  } catch (err) {
    console.error('获取子域名建议失败', err);
  }
};

let domainSuggestTimer = null;
const handleDomainSearchInput = (value) => {
  if (domainSuggestTimer) clearTimeout(domainSuggestTimer);
  domainSuggestTimer = setTimeout(() => {
    fetchDomainSuggestions(value);
  }, 300);
};

onUnmounted(() => {
  if (domainSuggestTimer) {
    clearTimeout(domainSuggestTimer);
    domainSuggestTimer = null;
  }
});

const handleChainSearch = async (val) => {
  if (typeof val === 'string' && val.trim()) {
    chainSearchDomain.value = val.trim();
  }
  const queryDomain = (chainSearchDomain.value || '').trim();
  if (!queryDomain) {
    message.warning('请输入或选择子域名/IP进行查询');
    return;
  }
  if (!scope_id.value) {
    message.warning('资产组 ID 不存在');
    return;
  }

  syncChainQuery(queryDomain);

  chainLoading.value = true;
  chainSearched.value = true;
  try {
    const res = await request.get('/asset_site/subdomain_chain/', {
      params: {
        scope_id: scope_id.value,
        domain: queryDomain
      }
    });

    if (res.code === 200) {
      chainData.value = res.data || {};
      const d = chainData.value;
      const totalFound = (
        (d.site?.length || 0) +
        (d.domain_records?.length || 0) +
        (d.ip?.length || 0) +
        (d.cip?.length || 0) +
        (d.cert?.length || 0) +
        (d.service?.length || 0) +
        (d.npoc_service?.length || 0) +
        (d.fileleak?.length || 0) +
        (d.url?.length || 0) +
        (d.wih?.length || 0) +
        (d.vuln?.length || 0) +
        (d.nuclei_result?.length || 0)
      );
      if (totalFound === 0) {
        message.info('未检索到该子域名/IP的关联资产记录');
      }
    } else {
      message.error(res.message || '查询失败');
    }
  } catch (err) {
    message.error('请求全链路资产画像异常');
  } finally {
    chainLoading.value = false;
  }
};

const resetChainSearch = () => {
  chainSearchDomain.value = '';
  chainSearched.value = false;
  chainData.value = null;
  syncChainQuery('');
  fetchDomainSuggestions();
};

const previewVisible = ref(false);
const previewImage = ref('');
const handlePreview = (url) => { previewImage.value = url; previewVisible.value = true; };
const searchForm = ref({});
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});

const selectedRowKeys = ref([]);
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
const onSelectChange = (keys) => { selectedRowKeys.value = keys; };

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

const getTags = (record) => {
  if (!record || !record.tag) return [];
  return Array.isArray(record.tag) ? record.tag : [record.tag];
};

const submitTag = async () => {
  if (!newTagValue.value.trim()) {
    message.warning('标签内容不能为空');
    return;
  }
  tagSubmitLoading.value = true;
  try {
    const targetId = currentTagRecord.value?._id || currentTagRecord.value?.id;
    const tag = newTagValue.value.trim();
    const res = await request.post('/asset_site/add_tag/', {
      _id: targetId,
      tag: tag
    });
    if (res.code === 200) {
      message.success('添加标签成功');
      tagVisible.value = false;
      if (currentTagRecord.value) {
        if (!Array.isArray(currentTagRecord.value.tag)) {
          currentTagRecord.value.tag = currentTagRecord.value.tag ? [currentTagRecord.value.tag] : [];
        }
        if (!currentTagRecord.value.tag.includes(tag)) {
          currentTagRecord.value.tag.push(tag);
        }
      }
      tabCache.invalidateMemoryCache(activeTab.value);
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

const handleDeleteTag = async (record, tag) => {
  const targetId = record?._id || record?.id;
  if (!targetId) return;
  try {
    const res = await request.post('/asset_site/delete_tag/', {
      _id: targetId,
      tag: tag
    });
    if (res.code === 200) {
      message.success(`已移除标签「${tag}」`);
      const currentTags = Array.isArray(record.tag) ? record.tag : (record.tag ? [record.tag] : []);
      record.tag = currentTags.filter(t => t !== tag);
    } else {
      message.error(res.message || '删除标签失败');
    }
  } catch (error) {
    message.error('请求异常');
  }
};

// 指纹统计弹窗状态与方法
const fingerModalVisible = ref(false);
const currentFingerName = ref('');
const fingerModalData = ref([]);
const fingerModalLoading = ref(false);

const fingerModalColumns = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '站点 URL', key: 'site', width: 300 },
  { title: '标题', key: 'title', dataIndex: 'title', width: 200 },
  { title: '状态码', key: 'status', dataIndex: 'status', width: 100 }
];

const openFingerModal = async (fingerName) => {
  currentFingerName.value = fingerName;
  fingerModalVisible.value = true;
  fingerModalLoading.value = true;
  fingerModalData.value = [];
  try {
    const res = await request.get('/asset_site/', {
      params: {
        scope_id: scope_id.value,
        finger: fingerName,
        page: 1,
        size: 100
      }
    });
    fingerModalData.value = res.items || res.data?.items || [];
  } catch (error) {
    console.error('Fetch finger sites failed:', error);
    message.error('获取关联站点失败');
  } finally {
    fingerModalLoading.value = false;
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


// 💡 针对分组详情定制的 Config (以站点为例，去掉了截图，加了更新时间)
// 💡 完整版的 Config：涵盖站点、域名、IP、WIH
// 💡 修复版 Config：使用 asset_ 前缀的专属接口，并修正日期字段
const tabConfig = reactive({
  site: {
    url: '/asset_site/', // 🚨 核心修复：加了 asset_ 前缀
    exportUrl: '/asset_site/export/', // 🚨 绑定抓包里的导出 URL
    tabName: '站点',
    searchFields: [
      { label: '站点', key: 'site', operator: '=' },
      { label: '标题', key: 'title', operator: '=' },
      { label: 'Web Server', key: 'http_server', operator: '=' },
      { label: '状态码', key: 'status', operator: '=' },
      // 🚨 补充丢失的 4 个字段
      { label: '标头', key: 'headers', operator: '=' },
      { label: '指纹', key: 'finger', operator: '=' },
      { label: 'favicon hash', key: 'favicon.hash', operator: '=' },
      { label: '标签', key: 'tag', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '站点', dataIndex: 'site', key: 'site', width: 250 },
      { title: '状态码', dataIndex: 'status', key: 'status', width: 100, align: 'center' },
      { title: '标题', dataIndex: 'title', key: 'title', width: 200 },
      { title: 'headers', key: 'headers', width: 400 },
      { title: 'finger', key: 'finger', width: 150 },
      { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }, // 修正字段名
      { title: '截图', key: 'screenshot', width: 300 }
    ]
  },
  domain: {
    url: '/asset_domain/',
    exportUrl: '/asset_domain/export/',
    tabName: '域名',
    // 🚨 修复：严格对齐截图中的 6 个搜索框顺序和文案
    searchFields: [
      { label: '域名', key: 'domain', operator: '=' },
      { label: '记录值', key: 'record', operator: '=' },
      { label: '类型', key: 'type', operator: '=' }, // 调整到第 3 位
      { label: 'IP', key: 'ips', operator: '=' },    // 调整到第 4 位
      { label: '来源', key: 'source', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      // ... cols 保持不变，上一轮猜得完全正确 ...
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '域名', dataIndex: 'domain', key: 'domain', width: 220 },
      { title: '解析类型', dataIndex: 'type', key: 'type', width: 100 },
      { title: '记录值', key: 'record', width: 280 },
      { title: '关联IP', key: 'ips', width: 280 },
      { title: '来源', dataIndex: 'source', key: 'source', width: 150 },
      { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
    ]
  },
  ip: {
    url: '/asset_ip/',
    tabName: 'IP',
    // 🚨 修复：完美对齐截图的 7 个搜索字段，首个为下拉框
    searchFields: [
      { label: 'IP类别', key: 'ip_type', type: 'select', options: [{label: 'PUBLIC', value: 'PUBLIC'}, {label: 'PRIVATE', value: 'PRIVATE'}] },
      { label: 'IP', key: 'ip', operator: '=' },
      { label: '端口', key: 'port_info.port_id', operator: '=' },
      { label: '操作系统', key: 'os_info.name', operator: '=' }, // ARL 默认 OS 字段名
      { label: '域名', key: 'domain', operator: '=' },
      { label: 'CDN', key: 'cdn_name', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    // 🚨 修复：移除原本多余的 CDN 列，严格对齐截图列名
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'IP', dataIndex: 'ip', key: 'ip', width: 160 },
      { title: '操作系统', key: 'os_info', width: 150 },
      { title: '开放端口', key: 'port_info', width: 200 },
      { title: '关联域名', key: 'domain', width: 250 },
      { title: 'Geo', key: 'geo_city', width: 180 },
      { title: 'AS', key: 'geo_asn', width: 280 },
      { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
    ]
  },
  wih: {
    url: '/asset_wih/',
    exportUrl: '/asset_wih/export/', // 🚨 激活“导出WIH”按钮
    tabName: 'WIH',
    // 🚨 完美对齐截图的 4 个搜索框，记录类型带下拉选择
    searchFields: [
      {
        label: '记录类型',
        key: 'record_type',
        operator: '等于',
        hasOperatorSelect: true,
        operators: ['等于', '不等于']
      },
      { label: '内容', key: 'content', operator: '=' },
      { label: '来源 JS', key: 'source', operator: '=' },
      { label: '来源站点', key: 'site', operator: '=' }
    ],
    // 🚨 完美对齐抓包数据的列，特别是 source 键名
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '记录类型', dataIndex: 'record_type', key: 'record_type', width: 120 },
      { title: '内容', dataIndex: 'content', key: 'content', width: 250 },
      { title: '来源 JS', dataIndex: 'source', key: 'source', width: 450 }, // 绑定 source
      { title: '来源站点', dataIndex: 'site', key: 'wih_site', width: 250 },
      { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
    ]
  },
  cert: {
    url: '/asset_cert/',
    exportUrl: '/asset_cert/export/',
    tabName: 'SSL证书',
    searchFields: [
      { label: 'IP字段', key: 'ip', operator: '=' },
      { label: '签发者名称', key: 'cert.issuer_dn', operator: '=' },
      { label: '主题名称', key: 'cert.subject_dn', operator: '=' },
      { label: 'SHA-1', key: 'cert.fingerprint.sha1', operator: '=' },
      { label: '使用者备用名称', key: 'cert.extensions.subjectAltName', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'HOST', key: 'host', width: 180 },
      { title: 'CERT', key: 'cert_detail', width: 900 },
      { title: '更新时间', key: 'update_date', width: 180 }
    ]
  },
  service: {
    url: '/asset_service/',
    tabName: '服务',
    searchFields: [
      { label: '服务', key: 'service_name', operator: '=' },
      { label: 'IP', key: 'service_info.ip', operator: '=' },
      { label: '端口', key: 'service_info.port_id', operator: '=' },
      { label: '产品', key: 'service_info.product', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '服务', dataIndex: 'service_name', key: 'service_name', width: 150, align: 'center' },
      { title: 'IP端口', key: 'ip_port', width: 300 },
      { title: 'Product', key: 'product', width: 250 },
      { title: '更新时间', key: 'update_date', width: 180 }
    ]
  },
  fileleak: {
    url: '/asset_fileleak/',
    tabName: '文件泄露',
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { label: '标题', key: 'title', operator: '=' },
      { label: '状态码', key: 'status_code', operator: '=' },
      { label: 'body 长度', key: 'content_length', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'URL', key: 'fileleak_url', width: 500 },
      { title: '标题', dataIndex: 'title', key: 'title', width: 250 },
      { title: '状态码', dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { title: 'body 长度', dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' },
      { title: '更新时间', key: 'update_date', width: 180 }
    ]
  },
  url: {
    url: '/asset_url/',
    exportUrl: '/asset_url/export/',
    tabName: 'URL信息',
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { label: '标题', key: 'title', operator: '=' },
      { label: '状态码', key: 'status_code', operator: '=' },
      { label: 'body 长度', key: 'content_length', operator: '=' },
      { label: '来源', key: 'source', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'URL', key: 'url_link', width: 450 },
      { title: '标题', dataIndex: 'title', key: 'title', width: 200 },
      { title: '状态码', dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { title: 'body 长度', dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' },
      { title: '来源', dataIndex: 'source', key: 'source', width: 150 },
      { title: '更新时间', key: 'update_date', width: 180 }
    ]
  },
  vuln: {
    url: '/asset_vuln/',
    tabName: '风险',
    searchFields: [
      { label: '漏洞名称', key: 'vul_name', operator: '=' },
      { label: '类别', key: 'vul_category', operator: '=' },
      { label: '应用名', key: 'app_name', operator: '=' },
      { label: '目标', key: 'target', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '漏洞名称', dataIndex: 'vul_name', key: 'vul_name', width: 250 },
      { title: '类别', dataIndex: 'vul_category', key: 'vul_category', width: 120 },
      { title: '应用名', dataIndex: 'app_name', key: 'app_name', width: 150 },
      { title: '目标', dataIndex: 'target', key: 'target', width: 200 },
      { title: '凭证', key: 'verify_data', width: 350 },
      { title: '发现时间', dataIndex: 'insert_time', key: 'insert_time', width: 160 }
    ]
  },
  npoc_service: {
    url: '/asset_npoc_service/',
    tabName: '服务(python)',
    searchFields: [
      { label: '协议', key: 'scheme', operator: '=' },
      { label: '主机', key: 'host', operator: '=' },
      { label: '端口', key: 'port', operator: '=' },
      { label: '目标', key: 'target', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '协议', dataIndex: 'scheme', key: 'scheme', width: 150 },
      { title: '主机', dataIndex: 'host', key: 'host', width: 200 },
      { title: '端口', dataIndex: 'port', key: 'port', width: 100, align: 'center' },
      { title: '目标', dataIndex: 'target', key: 'target', width: 250 },
      { title: '保存时间', dataIndex: 'insert_time', key: 'insert_time', width: 180 }
    ]
  },
  cip: {
    url: '/asset_cip/',
    exportUrl: '/asset_cip/export/',
    tabName: 'C段',
    searchFields: [
      { label: 'C段', key: 'cidr_ip', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'C段', dataIndex: 'cidr_ip', key: 'cidr_ip', width: 300 },
      { title: 'IP数', key: 'ip_count_col', width: 150, align: 'center' },
      { title: '域名数', key: 'domain_count_col', width: 150, align: 'center' },
      { title: '更新时间', key: 'update_date', width: 180 }
    ]
  },
  nuclei_result: {
    url: '/asset_nuclei_result/',
    tabName: 'nuclei',
    searchFields: [
      { label: '模版ID', key: 'template_id', operator: '=' },
      { label: '目标', key: 'target', operator: '=' },
      { label: '漏洞URL', key: 'vuln_url', operator: '=' },
      { label: '漏洞名称', key: 'vuln_name', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '模版ID', dataIndex: 'template_id', key: 'template_id', width: 180 },
      { title: '目标', dataIndex: 'target', key: 'target', width: 200 },
      { title: '漏洞URL', key: 'nuclei_vuln_url', width: 300 },
      { title: '漏洞名称', dataIndex: 'vuln_name', key: 'vul_name', width: 200 },
      { title: '漏洞等级', dataIndex: 'vuln_severity', key: 'vul_severity', width: 100, align: 'center' },
      { title: '保存时间', dataIndex: 'insert_time', key: 'insert_time', width: 160 },
      { title: '验证命令', key: 'verify_command', width: 350 }
    ]
  },
  stat_finger: {
    url: '/asset_stat_finger/',
    tabName: '指纹统计',
    searchFields: [
      { 
        label: 'finger', 
        key: 'name', 
        operator: '模糊匹配',
        hasOperatorSelect: true,
        operators: ['模糊匹配', '精确匹配']
      },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 80, align: 'center' },
      { title: 'finger', key: 'finger_name', width: 500 },
      { title: '数量', dataIndex: 'cnt', key: 'cnt', width: 200 },
      { title: '更新时间', key: 'update_date', width: 180 }
    ]
  },
  site_chain: {
    tabName: '全链路画像'
  }
});

const tabCache = createTabStateCache({
  getStorageKey: () => scope_id.value ? `ARL_GROUP_TAB_STATE_${scope_id.value}` : null,
  tabConfig,
  defaultTab: 'site'
});

const columns = ref(tabConfig.site.cols);

const fetchData = async () => {
  if (activeTab.value === 'site_chain') return;
  const config = tabConfig[activeTab.value];
  if (!config) return;

  const currentReqTab = activeTab.value;
  loading.value = true;
  try {
    // 🚨 修复 2：获取 computed 响应式对象的最新值
    const params = { page: pagination.current, size: pagination.pageSize, scope_id: scope_id.value };

    for (const key in searchForm.value) {
      if (searchForm.value[key] !== '' && searchForm.value[key] != null) {
        const fieldConfig = config.searchFields?.find(f => f.key === key);
        // 🚨 防御幽灵过滤：若该字段不在当前 Tab 的契约中，直接丢弃
        if (config.searchFields && !fieldConfig) continue;

        // 如果是时间范围数组，则特殊处理给后端
        if (key === 'update_date' && Array.isArray(searchForm.value[key])) {
          // 🚨 核心对齐：精准替换为 ARL 专属的 __dgt 和 __dlt 参数名，并格式化为全时分秒
          params.update_date__dgt = searchForm.value[key][0].format('YYYY-MM-DD HH:mm:ss');
          params.update_date__dlt = searchForm.value[key][1].format('YYYY-MM-DD HH:mm:ss');
        } else {
          let paramKey = key;
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
    }
    const res = await request.get(config.url, { params });
    // 竞态防御：若响应到达时 Tab 已切换，丢弃过期响应
    if (activeTab.value !== currentReqTab) return;

    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      selectedRowKeys.value = [];
      // 更新当前 Tab 内存数据缓存并持久化轻量搜索状态
      tabCache.updateMemoryCache(activeTab.value, dataSource.value, pagination.total);
      tabCache.saveCurrentTab(activeTab.value, searchForm.value, pagination.current);
    }
  } catch (error) {
    if (activeTab.value === currentReqTab) {
      message.error('加载数据失败');
    }
  } finally {
    if (activeTab.value === currentReqTab) {
      loading.value = false;
    }
  }
};

const onSearch = () => {
  pagination.current = 1;
  tabCache.saveCurrentTab(activeTab.value, searchForm.value, 1);
  fetchData();
};
const resetSearch = () => {
  searchForm.value = {};
  tabCache.resetTabState(activeTab.value);
  pagination.current = 1;
  fetchData();
};
const handleTableChange = (page, pageSize) => {
  pagination.current = page;
  pagination.pageSize = pageSize;
  tabCache.saveCurrentTab(activeTab.value, searchForm.value, page);
  fetchData();
};

// ================= 批量删除功能 (兼容所有 Tab) =================
const handleBatchDelete = () => {
  Modal.confirm({
    title: '批量删除确认',
    icon: createVNode(ExclamationCircleOutlined),
    content: `确定要从当前分组中删除选中的 ${selectedRowKeys.value.length} 条资产吗？删除后不可恢复。`,
    okText: '确 定',
    okType: 'danger',
    cancelText: '取 消',
    onOk: async () => {
      try {
        const config = tabConfig[activeTab.value];
        if (!config || !config.url) return;

        // 🚨 优先读取专用配置，否则动态拼接删除 API 路径：例如 /asset_domain/ -> /asset_domain/delete/
        const deleteUrl = config.deleteUrl || `${config.url}delete/`;

        // 🚨 严格按照抓包 Payload：键名为 _id
        const res = await request.post(deleteUrl, {
          _id: selectedRowKeys.value
        });

        if (res.code === 200) {
          message.success('批量删除成功！');

          // 如果删光了当前页的数据且不在第一页，自动回退一页
          if (dataSource.value.length === selectedRowKeys.value.length && pagination.current > 1) {
            pagination.current -= 1;
          }

          selectedRowKeys.value = []; // 清空选中状态
          tabCache.invalidateMemoryCache(activeTab.value);
          fetchData(); // 🚨 完美对齐抓包里的第二个请求：自动刷新表格数据
        } else {
          message.error('删除失败: ' + res.message);
        }
      } catch (error) {
        message.error('请求异常，删除失败');
      }
    }
  });
};
const openAction = (action) => { message.info(`准备开发弹窗: ${action}`); };

watch(activeTab, (newVal, oldVal) => {
  if (oldVal && tabConfig[oldVal] && !isScopeSwitching.value) {
    // 离开旧选项卡前，仅在非切组且有效交互时保存当前搜索表单、操作符和页码
    tabCache.saveCurrentTab(oldVal, searchForm.value, pagination.current);
  }

  if (newVal === 'site_chain') {
    fetchDomainSuggestions();
    if (route.query.chain_target && !chainSearchDomain.value) {
      chainSearchDomain.value = String(route.query.chain_target);
      nextTick(() => {
        handleChainSearch();
      });
    }
    return;
  }

  if (tabConfig[newVal]) {
    columns.value = tabConfig[newVal].cols;
    selectedRowKeys.value = [];

    // 恢复新选项卡的搜索表单、操作符与页码
    searchForm.value = tabCache.getTabSearchForm(newVal);
    tabCache.applyTabOperators(newVal);
    pagination.current = tabCache.getTabPage(newVal);

    // 检查内存数据缓存：若已加载过则直接秒开渲染，不重复向后端发请求
    const cached = tabCache.getMemoryCache(newVal);
    if (cached) {
      dataSource.value = cached.dataSource;
      pagination.total = cached.total;
    } else {
      fetchData();
    }
  }
});

// 🚨 修复 3：监听 scope_id 的变化，无论是初次进入还是组件复用，只要 ID 变了就刷新数据！
watch(scope_id, (newId) => {
  if (newId) {
    isScopeSwitching.value = true;
    dataSource.value = [];
    selectedRowKeys.value = [];
    resetChainSearch();

    // 若路由携带 chain_target，直接深链穿透至全链路画像并触发拉取
    if (route.query.chain_target) {
      activeTab.value = 'site_chain';
      chainSearchDomain.value = String(route.query.chain_target);
      nextTick(() => {
        isScopeSwitching.value = false;
        fetchDomainSuggestions();
        handleChainSearch();
      });
      return;
    }

    const restoredTab = tabCache.init();
    if (restoredTab && tabConfig[restoredTab] && restoredTab !== activeTab.value) {
      activeTab.value = restoredTab;
      nextTick(() => {
        isScopeSwitching.value = false;
        if (activeTab.value === 'site_chain') {
          fetchDomainSuggestions();
        }
      });
    } else {
      if (activeTab.value === 'site_chain') {
        fetchDomainSuggestions();
        nextTick(() => {
          isScopeSwitching.value = false;
        });
      } else {
        if (tabConfig[activeTab.value]) {
          columns.value = tabConfig[activeTab.value].cols;
          searchForm.value = tabCache.getTabSearchForm(activeTab.value);
          tabCache.applyTabOperators(activeTab.value);
          pagination.current = tabCache.getTabPage(activeTab.value);
        }
        const cached = tabCache.getMemoryCache(activeTab.value);
        if (cached) {
          dataSource.value = cached.dataSource;
          pagination.total = cached.total;
        } else {
          fetchData();
        }
        nextTick(() => {
          isScopeSwitching.value = false;
        });
      }
    }
  }
}, { immediate: true }); // immediate: true 完美替代了 onMounted 的作用


// ================= 导出功能 (站点、域名、WIH 通用) =================
const handleExport = async () => {
  const config = tabConfig[activeTab.value];
  if (!config || !config.exportUrl) return;

  try {
    message.loading({ content: `正在生成导出文件...`, key: 'export_data' });

    // 🚨 动态映射真实的 tabIndex
    const tabIndexMap = { site: 0, domain: 1, ip: 2, cert: 3, service: 4, fileleak: 5, url: 6, cip: 7, stat_finger: 8, wih: 9, vuln: 10, npoc_service: 11, nuclei_result: 12 };

    // 🚨 完美对齐 WIH 抓包：size 扩大到十万级 100000，并带上动态的 tabIndex
    const params = {
      page: 1,
      size: 100000,
      scope_id: scope_id.value,
      targetName: targetName.value,
      tabIndex: tabIndexMap[activeTab.value]
    };

    // 🚨 补全缺失的搜索参数：确保用户过滤后导出的数据也是精准的！
    for (const key in searchForm.value) {
      if (searchForm.value[key] !== '' && searchForm.value[key] != null) {
        const fieldConfig = config.searchFields?.find(f => f.key === key);
        // 🚨 防御幽灵过滤：若该字段不在当前 Tab 的契约中，直接丢弃
        if (config.searchFields && !fieldConfig) continue;

        if (key === 'update_date' && Array.isArray(searchForm.value[key])) {
          params.update_date__dgt = searchForm.value[key][0].format('YYYY-MM-DD HH:mm:ss');
          params.update_date__dlt = searchForm.value[key][1].format('YYYY-MM-DD HH:mm:ss');
        } else {
          let paramKey = key;
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
    }

    const res = await request.get(config.exportUrl, { params, responseType: 'blob' });

    const blob = new Blob([res], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_Group_Export_${activeTab.value}_${new Date().getTime()}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: `导出成功！`, key: 'export_data', duration: 2 });
  } catch (error) {
    message.error({ content: `导出异常`, key: 'export_data', duration: 2 });
  }
};



// ================= IP专属导出占位 =================
// ================= IP专属导出 =================
const handleIPExport = async (type) => {
  let exportUrl = '';
  let typeName = '';

  // 🚨 完美映射抓包里的 3 个真实 API 路径
  if (type === 'port') {
    exportUrl = '/asset_ip/export/';
    typeName = 'IP端口';
  } else if (type === 'domain') {
    exportUrl = '/asset_ip/export_domain/';
    typeName = '域名';
  } else if (type === 'ip') {
    exportUrl = '/asset_ip/export_ip/';
    typeName = 'IP';
  }

  if (!exportUrl) return;

  try {
    message.loading({ content: `正在打包生成文件...`, key: 'export_ip_data' });

    // 🚨 完美对齐 Payload，并自动带上当前所有的搜索过滤条件
    const params = {
      page: 1,
      size: 10000,
      scope_id: scope_id.value,
      targetName: targetName.value,
      tabIndex: 2
    };

    for (const key in searchForm.value) {
      if (searchForm.value[key] !== '' && searchForm.value[key] != null) {
        if (key === 'update_date' && Array.isArray(searchForm.value[key])) {
          params.update_date__dgt = searchForm.value[key][0].format('YYYY-MM-DD HH:mm:ss');
          params.update_date__dlt = searchForm.value[key][1].format('YYYY-MM-DD HH:mm:ss');
        } else {
          params[key] = searchForm.value[key];
        }
      }
    }

    // 发起 Blob 下载请求
    const res = await request.get(exportUrl, { params, responseType: 'blob' });

    // 触发浏览器的原生下载动作
    const blob = new Blob([res], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_Group_Export_${typeName}_${new Date().getTime()}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: `导出 ${typeName} 成功！`, key: 'export_ip_data', duration: 2 });
  } catch (error) {
    message.error({ content: `导出异常，请重试`, key: 'export_ip_data', duration: 2 });
  }
};


// ================= 添加站点弹窗 =================
const addSiteVisible = ref(false);
const addSiteLoading = ref(false);
const addSiteFormRef = ref();
const policies = ref([]);

const addSiteForm = reactive({ site: '', policy_id: undefined });
const addSiteRules = {
  site: [{ required: true, message: '请输入站点' }],
  policy_id: [{ required: true, message: '请选择策略' }]
};

const openAddSiteModal = async () => {
  addSiteForm.site = '';
  addSiteForm.policy_id = undefined;
  addSiteVisible.value = true;
  // 获取策略下拉列表
  if(policies.value.length === 0) {
    const res = await request.get('/policy/', { params: { size: 1000 } });
    if(res.code === 200) policies.value = res.items || [];
  }
};

const submitAddSite = async () => {
  await addSiteFormRef.value.validate();
  addSiteLoading.value = true;
  try {
    const res = await request.post('/asset_site/', {
      scope_id: scope_id.value,
      site: addSiteForm.site,
      policy_id: addSiteForm.policy_id
    });

    // 🚨 完美还原抓包：正常成功是 200，如果资产不在范围内是 802
    if (res.code === 200) {
      message.success('添加站点成功！');
      addSiteVisible.value = false;
      tabCache.invalidateAllMemoryCaches();
      fetchData(); // 刷新表格
    } else if (res.code === 802) {
      message.error(res.message); // 弹出 "任务目标不在资产组中"
    } else {
      message.error('添加失败: ' + res.message);
    }
  } catch (e) {
    message.error('请求异常');
  } finally {
    addSiteLoading.value = false;
  }
};

// ================= 风险任务下发 =================
const riskModalVisible = ref(false);
const riskLoading = ref(false);
const riskFormRef = ref();
const currentResultSetId = ref(''); // 保存弹药箱 ID
const currentTargetCount = ref(0); // 保存查出来的目标数量

const riskForm = reactive({ name: '', policy_id: undefined });
const riskRules = {
  name: [{ required: true, message: '请输入任务名称' }],
  policy_id: [{ required: true, message: '请选择策略' }]
};
// 统计目标数量
const getPocCount = (policy) => {
  return policy.policy?.poc_config?.filter(poc => poc.enable)?.length || 0;
};

// 1. 打开弹窗：打包结果集 & 获取策略
const openRiskModal = async () => {
  try {
    message.loading({ content: '正在打包目标集合...', key: 'risk_task' });

    // 构建过滤参数（和搜索一模一样，确保下发的就是当前查出来的）
    const params = { scope_id: scope_id.value };
    for (const key in searchForm.value) {
      if (searchForm.value[key] !== '' && searchForm.value[key] != null) {
        if (key === 'update_date' && Array.isArray(searchForm.value[key])) {
          params.update_date__dgt = searchForm.value[key][0].format('YYYY-MM-DD HH:mm:ss');
          params.update_date__dlt = searchForm.value[key][1].format('YYYY-MM-DD HH:mm:ss');
        } else {
          params[key] = searchForm.value[key];
        }
      }
    }

    // 发起结果集保存请求
    const setRes = await request.get('/asset_site/save_result_set/', { params });
    if (setRes.code !== 200) throw new Error('生成结果集失败');

    currentResultSetId.value = setRes.data.result_set_id;
    // 🚨 将后端返回的真实数量赋给弹窗展示
    currentTargetCount.value = setRes.data.result_total || 0;

    // 复用之前的 policies 拉取逻辑，没有才去拉
    if (policies.value.length === 0) {
      const polRes = await request.get('/policy/', { params: { size: 1000 } });
      if (polRes.code === 200) policies.value = polRes.items || [];
    }

    message.success({ content: `成功锁定 ${setRes.data.result_total} 条资产准备下发`, key: 'risk_task' });

    // 初始化弹窗数据
    riskForm.name = '';
    riskForm.policy_id = undefined;
    riskModalVisible.value = true;
  } catch (e) {
    message.error({ content: '准备下发任务失败', key: 'risk_task' });
  }
};

// 2. 选择策略时：极客级自动推导任务名称
const handleRiskPolicyChange = (val) => {
  const selected = policies.value.find(p => p._id === val);
  if (selected) {
    // 🚨 调用公共函数获取 PoC 数量
    const pocCount = getPocCount(selected);
    riskForm.name = `风险巡航任务-${selected.name} (PoC : ${pocCount})`;
  }
};

// 3. 提交任务
const submitRiskTask = async () => {
  await riskFormRef.value.validate();
  riskLoading.value = true;
  try {
    const payload = {
      name: riskForm.name,
      task_tag: 'risk_cruising',
      target: '', // 因为用了结果集，所以 target 留空
      policy_id: riskForm.policy_id,
      result_set_id: currentResultSetId.value
    };

    const res = await request.post('/task/policy/', payload);

    if (res.code === 200) {
      message.success('风险任务下发成功！');
      riskModalVisible.value = false;
    } else {
      message.error('下发失败: ' + res.message);
    }
  } catch (e) {
    console.warn('请求异常', e);
  } finally {
    riskLoading.value = false;
  }
};

// ================= 添加子域名弹窗 =================
const addDomainVisible = ref(false);
const addDomainLoading = ref(false);
const addDomainFormRef = ref();

const addDomainForm = reactive({ domain: '', policy_id: undefined });
const addDomainRules = {
  domain: [{ required: true, message: '请输入子域名' }],
  policy_id: [{ required: true, message: '请选择策略' }]
};

const openAddDomainModal = async () => {
  addDomainForm.domain = '';
  addDomainForm.policy_id = undefined;
  addDomainVisible.value = true;

  // 复用之前写好的拉取策略逻辑，避免重复请求
  if(policies.value.length === 0) {
    const res = await request.get('/policy/', { params: { size: 1000 } });
    if(res.code === 200) policies.value = res.items || [];
  }
};

const submitAddDomain = async () => {
  await addDomainFormRef.value.validate();
  addDomainLoading.value = true;
  try {
    const res = await request.post('/asset_domain/', {
      scope_id: scope_id.value,
      domain: addDomainForm.domain, // 🚨 注意这里 payload 的 key 是 domain
      policy_id: addDomainForm.policy_id
    });

    // 🚨 完美拦截原版状态码：成功是 200，越界是 701
    if (res.code === 200) {
      message.success('添加子域名成功！');
      addDomainVisible.value = false;
      tabCache.invalidateAllMemoryCaches();
      fetchData(); // 自动刷新当前页面的域名列表
    } else if (res.code === 701) {
      message.error(res.message); // 原汁原味抛出：域名不在给定的资产范围中
    } else {
      message.error('添加失败: ' + res.message);
    }
  } catch (e) {
    message.error('请求异常');
  } finally {
    addDomainLoading.value = false;
  }
};

</script>

<style scoped>
/* 🚨 将原本的 gap: 16px 24px 改为更紧凑的 16px 12px */
.scroll-x { width: 100%; max-width: 400px; overflow-x: auto; }
.scroll-x pre { margin: 0; font-family: Consolas, monospace; font-size: 12px; color: var(--arl-text-color); opacity: 0.65; }
:deep(.ant-tabs-card-bar .ant-tabs-tab) { border-radius: 2px 2px 0 0 !important; margin-right: 4px !important; border: 1px solid var(--arl-border-color) !important; background: var(--arl-bg-light) !important; }
:deep(.ant-tabs-card-bar .ant-tabs-tab-active) { background: var(--arl-bg-white) !important;  font-weight: 500; border-bottom-color: transparent !important; }

.site-header { line-height: 1.5; word-break: break-all; }
.site-img { width: 16px; height: 16px; margin-right: 8px; vertical-align: middle; }
.add-tag { color: var(--arl-text-color); cursor: pointer; font-size: 12px; border: 1px dashed var(--arl-border-color); padding: 0 7px; border-radius: 2px; background: var(--arl-bg-light); transition: all 0.3s; }
.add-tag:hover { color: var(--arl-theme-color); border-color: var(--arl-theme-color); }
.mt5 { margin-top: 5px; }

.tag-pending-test {
  background: color-mix(in srgb, var(--arl-theme-color) 15%, transparent) !important;
  color: var(--arl-theme-color) !important;
  border-color: var(--arl-theme-color) !important;
  font-weight: 500;
  transition: all 0.3s;
}
.tag-pending-test :deep(.anticon-close) {
  color: var(--arl-theme-color) !important;
}
.tag-pending-test :deep(.anticon-close:hover) {
  opacity: 0.75;
}

.chain-card {
  border-radius: 6px;
  background: var(--arl-bg-white);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
  border: 1px solid var(--arl-border-color);
}
.chain-card-header {
  display: flex;
  align-items: center;
  font-size: 15px;
  font-weight: 600;
  color: var(--arl-text-color);
}
.chain-icon {
  margin-right: 8px;
  color: var(--arl-theme-color);
  font-size: 16px;
}
.chain-empty-tip {
  color: var(--arl-text-secondary);
  text-align: center;
  padding: 24px 0;
  font-size: 13px;
}
.chain-site-item {
  padding: 16px;
  background: var(--arl-bg-light);
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
}
.chain-info-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}
.chain-info-row {
  display: flex;
  align-items: baseline;
  line-height: 1.6;
}
.chain-info-label {
  width: 95px;
  color: var(--arl-text-secondary);
  flex-shrink: 0;
}
.chain-info-value {
  flex: 1;
  color: var(--arl-text-color);
  word-break: break-all;
}

</style>