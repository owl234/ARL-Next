<template>
  <div style="background-color: #fff; padding: 24px; min-height: calc(100vh - 64px);">
    <a-page-header
      :title="`${targetName} 相关资产`"
      @back="() => router.back()"
      style="padding: 0 0 24px 0;"
    />

    <a-tabs v-model:activeKey="activeTab" type="card" class="arl-detail-tabs">
      <a-tab-pane key="site" :tab="`站点 - ${queryCounts.site}`"></a-tab-pane>
      <a-tab-pane key="domain" :tab="`子域名 - ${queryCounts.domain}`"></a-tab-pane>
      <a-tab-pane key="ip" :tab="`IP - ${queryCounts.ip}`"></a-tab-pane>
      <a-tab-pane key="cert" :tab="`SSL证书 - ${queryCounts.cert}`"></a-tab-pane>
      <a-tab-pane key="service" :tab="`服务 - ${queryCounts.service}`"></a-tab-pane>
      <a-tab-pane key="fileleak" :tab="`文件泄露 - ${queryCounts.fileleak}`"></a-tab-pane>
      <a-tab-pane key="url" :tab="`URL信息 - ${queryCounts.url}`"></a-tab-pane>
      <a-tab-pane key="vuln" :tab="`风险 - ${queryCounts.vuln}`"></a-tab-pane>
      <a-tab-pane key="npoc_service" :tab="`服务（python） - ${queryCounts.npoc_service}`"></a-tab-pane>
      <a-tab-pane key="cip" :tab="`C段 - ${queryCounts.cip}`"></a-tab-pane>
      <a-tab-pane key="nuclei_result" :tab="`nuclei - ${queryCounts.nuclei_result}`"></a-tab-pane>
      <a-tab-pane key="stat_finger" :tab="`指纹统计 - ${queryCounts.stat_finger}`"></a-tab-pane>
      <a-tab-pane key="wih" :tab="`WIH - ${queryCounts.wih}`"></a-tab-pane>
    </a-tabs>

    <div v-if="tabConfig[activeTab]?.searchFields" class="search-row" style="margin-bottom: 16px;">
      <div v-for="field in tabConfig[activeTab].searchFields" :key="field.key" class="search-item">
        <span class="label">{{ field.label }}：</span>

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
            style="display: flex; align-items: center; border: 1px solid #d9d9d9; border-radius: 2px; width: 280px; background: #fff;"
        >
          <a-input
              v-model:value="searchForm[field.key]"
              :placeholder="`请输入${field.label}`"
              :bordered="false"
              style="flex: 1; box-shadow: none;"
              allowClear
              @pressEnter="onSearch"
          >
            <template #suffix>
              <search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" />
            </template>
          </a-input>
          <div style="width: 1px; height: 16px; background-color: #d9d9d9;"></div>
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
            <search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" />
          </template>
        </a-input>
      </div>
    </div>

    <div style="margin-bottom: 16px;">
      <a-button :disabled="!hasSelected" style="margin-right: 16px;" @click="handleBatchDelete">批量删除</a-button>
      <a-button style="margin-right: 16px;" @click="resetSearch">清 除</a-button>
      <a-button v-if="tabConfig[activeTab]?.exportName" type="primary" style="background-color: #00bcd4; border-color: #00bcd4; margin-right: 16px;" @click="handleExport">导出{{ tabConfig[activeTab].exportName }}</a-button>
      <a-button v-if="activeTab === 'site'" type="primary" style="background-color: #00bcd4; border-color: #00bcd4;" @click="openRiskModal">风险任务下发</a-button>
    </div>

    <a-table
        :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
        :loading="loading"
        :dataSource="dataSource"
        :columns="columns"
        :pagination="false"
        :scroll="{ x: 'max-content' }"
        size="middle"
        :rowKey="(record) => record._id || record.id"
    >
      <template #bodyCell="{ column, record, index }">

        <template v-if="column.key === 'index'">{{ (pagination.current - 1) * pagination.pageSize + index + 1 }}</template>
<!--表格-站点列-->
        <template v-else-if="column.key === 'site'">
          <div class="site-header">
            <a :href="record.site || record.url" target="_blank" style="color: #00bcd4; font-weight: 500;">
              <img v-if="record.favicon && record.favicon.data" :src="`data:image/png;base64,${record.favicon.data}`" class="site-img" />
              <img v-else-if="typeof record.favicon === 'string'" :src="`data:image/png;base64,${record.favicon}`" class="site-img" />

              {{ record.site || record.url }}
            </a>

            <p v-if="record.favicon && record.favicon.hash" class="site-word">Favicon Hash: {{ record.favicon.hash }}</p>
            <p v-else-if="record.favicon_hash" class="site-word">Favicon Hash: {{ record.favicon_hash }}</p>

            <div class="mt5" style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">

              <a-tag v-if="record.is_entry || record.isEntry" closable style="background: #fafafa; color: #666; border-color: #d9d9d9;">入口</a-tag>

              <template v-for="(t, idx) in (record.tags || record.tag || [])" :key="idx">
                <a-tag closable style="background: #fafafa; color: #666; border-color: #d9d9d9;">
                  {{ typeof t === 'string' ? t : (t.name || t.tag_name || t) }}
                </a-tag>
              </template>

              <span class="add-tag">添加标签</span>
            </div>
          </div>
        </template>

        <template v-else-if="column.key === 'headers'">
          <div class="scroll-x"><pre>{{ record.headers }}</pre></div>
        </template>



        <template v-else-if="column.key === 'finger'">
          <div v-if="record.finger">
            <p v-for="f in record.finger" :key="f.name" style="margin-bottom: 4px; color: rgba(0,0,0,0.65);">{{ f.name }}</p>
          </div>
        </template>


        <template v-else-if="column.key === 'screenshot'">
          <img v-if="record.screenshot" :src="`/api${record.screenshot}`" style="width: 280px; cursor: pointer; border: 1px solid #f0f0f0;" @click="handlePreview(`/api${record.screenshot}`)" />
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
                <div style="color: #999; margin-top: 2px;">...等 {{ record.ips.length }} 个</div>
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
                <div style="color: #999; margin-top: 2px;">...等 {{ record.domain.length }} 个</div>
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
          <span>{{ record.ip }}:{{ record.port }}</span>
        </template>
        <template v-else-if="column.key === 'cert_detail'">
          <div v-if="record.cert" style="font-size: 13px; line-height: 1.8; color: #333; padding: 12px 0;">

            <div style="font-weight: 600; font-size: 14px; margin-bottom: 12px;">基本信息</div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">主题名称</div>
              <div style="flex: 1; word-break: break-all; color: #555;">{{ record.cert.subject_dn || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">签发者名称</div>
              <div style="flex: 1; word-break: break-all; color: #555;">{{ record.cert.issuer_dn || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">使用者备用名称</div>
              <div style="flex: 1; word-break: break-all; color: #555;">{{ record.cert.extensions?.subjectAltName || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">序列号</div>
              <div style="flex: 1; word-break: break-all; color: #555;">{{ record.cert.serial_number || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 16px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">时间</div>
              <div style="flex: 1; color: #555;">{{ record.cert.validity?.start || '-' }} 至 {{ record.cert.validity?.end || '-' }}</div>
            </div>

            <div style="font-weight: 600; font-size: 14px; margin-bottom: 12px;">指纹</div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">SHA-256</div>
              <div style="flex: 1; word-break: break-all; color: #555;">{{ record.cert.fingerprint?.sha256 || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">SHA-1</div>
              <div style="flex: 1; word-break: break-all; color: #555;">{{ record.cert.fingerprint?.sha1 || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">MD5</div>
              <div style="flex: 1; word-break: break-all; color: #555;">{{ record.cert.fingerprint?.md5 || '-' }}</div>
            </div>

          </div>
          <span v-else>-</span>
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
          <a :href="record.url || record.vuln_url" target="_blank" style="color: #00bcd4; word-break: break-all;">
            {{ record.url || record.vuln_url || '-' }}
          </a>
        </template>

        <template v-else-if="column.key === 'verify_data'">
          <div style="max-height: 100px; overflow-y: auto; color: #d93026; font-family: monospace; font-size: 12px; word-break: break-all;">
            {{ record.verify_data || record.proof || '-' }}
          </div>
        </template>

        <template v-else-if="column.key === 'ip_count_col'">
          <span style="color: #00bcd4; cursor: pointer;">{{ record.ip_count || 0 }}</span>
        </template>

        <template v-else-if="column.key === 'domain_count_col'">
          <span style="color: #00bcd4; cursor: pointer;">{{ record.domain_count || 0 }}</span>
        </template>

        <template v-else-if="column.key === 'verify_command'">
          <div style="max-height: 100px; overflow-y: auto; background: #f5f5f5; padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 12px; word-break: break-all;">
            {{ record.verify_command || record.curl_command || '-' }}
          </div>
        </template>

        <template v-else-if="column.key === 'finger_name'">
          <span style="color: #00bcd4; cursor: pointer;">{{ record.name || '-' }}</span>
        </template>

        <template v-else-if="column.key === 'wih_source'">
          <div style="word-break: break-all; color: #333; line-height: 1.6;">
            {{ record.source || '-' }}
          </div>
        </template>

      </template>
    </a-table>

    <div v-if="tabConfig[activeTab]" style="display: flex; justify-content: space-between; align-items: center; padding: 0 16px;">
      <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" @showSizeChange="handleTableChange" />
    </div>

    <a-modal v-model:open="previewVisible" :footer="null" width="85vw" centered @cancel="previewVisible = false" :bodyStyle="{ padding: '16px' }">
      <img :src="previewImage" style="width: 100%; max-height: 85vh; object-fit: contain; display: block;" />
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

        <div style="margin-left: 104px; color: rgba(0,0,0,0.85); margin-top: 16px;">
          目标：选择目标数 {{ targetCount }}
        </div>
      </a-form>
    </a-modal>

  </div>
</template>

<script setup>
// 💥 核心修改 2：引入 createVNode 和 Modal、ExclamationCircleOutlined
import { ref, onMounted, reactive, watch, computed, createVNode } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import request from '../utils/request';
import { message, Modal } from 'ant-design-vue';
import { SearchOutlined, ExclamationCircleOutlined } from '@ant-design/icons-vue';

const route = useRoute();
const router = useRouter();
const query = route?.query || {};
const targetName = ref(query.targetName || '未知目标');
const activeTab = ref('site');
const loading = ref(false);
const dataSource = ref([]);

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
const pagination = reactive({ current: 1, pageSize: 10, total: 0 });

// 💥 核心修改 3：在配置字典中加入 deleteUrl
const tabConfig = {
  site: {
    url: '/site/',
    deleteUrl: '/site/delete/',
    searchFields: [
      { label: '站点', key: 'site', operator: '=' },
      { label: '主机名', key: 'hostname', operator: '=' },
      { label: '标题', key: 'title', operator: '=' },
      { label: 'Web Server', key: 'server', operator: '=' },
      { label: '状态码', key: 'status_code', operator: '=' },
      { label: '标头', key: 'headers', operator: '=' },
      { label: '指纹', key: 'finger', operator: '=' },
      { label: 'favicon hash', key: 'favicon_hash', operator: '=' },
      { label: '标签', key: 'tag', operator: '=' }
    ],
    // 💥 修复：删除了瞎加的 IP、端口和操作列，完全对齐原版站点表格！表格控制
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '站点', key: 'site', width: 250 },
      { title: '标题', dataIndex: 'title', key: 'title', width: 200 },
      // 删除了你加的 server 和 status 列
      { title: 'headers', key: 'headers',width: 500},
      { title: 'finger', key: 'finger', width: 50 },
      { title: '截图', key: 'screenshot', width: 280 } // 保持宽度给图片留足空间
    ]
  },
  // 💡 新增：子域名 Tab 的 1:1 配置
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
      { title: '域名', dataIndex: 'domain', key: 'domain', width: 250 },
      { title: '解析类型', dataIndex: 'type', key: 'type', width: 120 },
      { title: '记录值', key: 'record', width: 300 },
      { title: '关联IP', key: 'ips', width: 250 },
      { title: '来源', dataIndex: 'source', key: 'source', width: 150 }
    ]
  },

  // 💡 新增：IP Tab 的 1:1 配置
// 💡 新增：IP Tab 的 1:1 配置
  ip: {
    url: '/ip/',
    deleteUrl: '/ip/delete/', // 视上一轮测试情况，如果删不掉请改回 '/site/delete/'
    exportUrl: '/ip/export/',
    exportName: ' IP 端口',
    searchFields: [
      { label: 'IP', key: 'ip', operator: '=' },
      // 🚨 核心修复：对齐后端的嵌套对象查询字段
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
      // ... 列配置保持不变 ...
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'IP', dataIndex: 'ip', key: 'ip', width: 160 },
      { title: '操作系统', key: 'os_info', width: 150 },
      { title: '开放端口', key: 'port_info', width: 200 },
      { title: '关联域名', key: 'domain', width: 250 },
      { title: 'CDN', dataIndex: 'cdn_name', key: 'cdn_name', width: 150 },
      { title: 'Geo', key: 'geo_city', width: 180 },
      { title: 'AS', key: 'geo_asn', width: 280 }
    ]
  },
  // 💡 重新构建：1:1 对齐截图的 SSL证书 配置
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
      { title: 'HOST', key: 'host', width: 180 },
      { title: 'CERT', key: 'cert_detail', width: 900 } // 留出巨大的空间给卡片
    ]
  },

  // 💡 新增：服务 Tab 的 1:1 配置
  service: {
    url: '/service/',
    deleteUrl: '/service/delete/',
    // 🚨 故意不写 exportUrl，完美对齐原版不带导出功能的 UI
    searchFields: [
      { label: '服务', key: 'service_name', operator: '=' },
      { label: 'IP', key: 'service_info.ip', operator: '=' },
      { label: '端口', key: 'service_info.port_id', operator: '=' },
      { label: '产品', key: 'service_info.product', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '服务', dataIndex: 'service_name', key: 'service_name', width: 150, align: 'center' },
      { title: 'IP端口', key: 'ip_port', width: 300 },
      { title: 'Product', key: 'product', width: 250 }
    ]
  },

  // 💡 新增：文件泄露 Tab 的 1:1 配置
  fileleak: {
    url: '/fileleak/',
    deleteUrl: '/fileleak/delete/',
    // 🚨 同样不配置 exportUrl，隐身导出按钮
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { label: '标题', key: 'title', operator: '=' },
      { label: '状态码', key: 'status_code', operator: '=' },
      { label: 'body 长度', key: 'content_length', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'URL', key: 'fileleak_url', width: 500 }, // 用专属 key 渲染超链接
      { title: '标题', dataIndex: 'title', key: 'title', width: 250 },
      { title: '状态码', dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { title: 'body 长度', dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' }
    ]
  },

  // 💡 新增：URL信息 Tab 的 1:1 配置
  url: {
    url: '/url/',
    deleteUrl: '/site/delete/',
    exportUrl: '/url/export/', // 恢复导出接口
    exportName: 'URL信息',     // 自动生成“导出URL信息”按钮
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { label: '标题', key: 'title', operator: '=' },
      { label: '状态码', key: 'status_code', operator: '=' },
      { label: 'body 长度', key: 'content_length', operator: '=' },
      { label: '来源', key: 'source', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'URL', key: 'url_link', width: 450 }, // 专用 key 渲染超链接
      { title: '标题', dataIndex: 'title', key: 'title', width: 200 },
      { title: '状态码', dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { title: 'body 长度', dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' },
      { title: '来源', dataIndex: 'source', key: 'source', width: 150 }
    ]
  },

  // 💡 新增：风险 Tab 的 1:1 配置
  vuln: {
    url: '/vuln/',
    deleteUrl: '/vuln/delete/',
    // 🚨 截图显示无导出按钮，所以不配置 exportUrl
    searchFields: [
      { label: '漏洞名称', key: 'vul_name', operator: '=' },
      { label: '类别', key: 'vul_category', operator: '=' }, // ARL 常用的类别字段名
      { label: '应用名', key: 'app_name', operator: '=' },
      { label: '目标', key: 'target', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '漏洞名称', dataIndex: 'vul_name', key: 'vul_name', width: 250 },
      { title: '类别', dataIndex: 'vul_category', key: 'vul_category', width: 120 },
      { title: '应用名', dataIndex: 'app_name', key: 'app_name', width: 150 },
      { title: '目标', dataIndex: 'target', key: 'target', width: 200 },
      { title: '凭证', key: 'verify_data', width: 350 }, // 凭证通常较长，用插槽渲染
      { title: '发现时间', dataIndex: 'insert_time', key: 'insert_time', width: 160 }
    ]
  },

  // 💡 新增：服务(python) Tab 的 1:1 配置
  npoc_service: {
    url: '/npoc_service/',
    deleteUrl: '/npoc_service/delete/',
    // 🚨 截图显示无导出按钮，不配置 exportUrl
    searchFields: [
      { label: '协议', key: 'protocol', operator: '=' },
      { label: '主机', key: 'host', operator: '=' },
      { label: '端口', key: 'port', operator: '=' },
      { label: '目标', key: 'target', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '协议', dataIndex: 'protocol', key: 'protocol', width: 150 },
      { title: '主机', dataIndex: 'host', key: 'host', width: 200 },
      { title: '端口', dataIndex: 'port', key: 'port', width: 100, align: 'center' },
      { title: '目标', dataIndex: 'target', key: 'target', width: 250 },
      { title: '保存时间', dataIndex: 'insert_time', key: 'insert_time', width: 180 }
    ]
  },

  // 💡 新增：C段 Tab 的 1:1 配置
  cip: {
    url: '/cip/',
    deleteUrl: '/site/delete/',
    exportUrl: '/cip/export/', // 恢复导出接口
    exportName: 'C段',         // 自动生成“导出C段”按钮
    searchFields: [
      { label: 'C段', key: 'cidr_ip', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'C段', dataIndex: 'cidr_ip', key: 'cidr_ip', width: 300 },
      { title: 'IP数', key: 'ip_count_col', width: 150, align: 'center' },
      { title: '域名数', key: 'domain_count_col', width: 150, align: 'center' }
    ]
  },

  // 💡 新增：nuclei Tab 的 1:1 配置
  nuclei_result: {
    url: '/nuclei_result/',
    deleteUrl: '/nuclei_result/delete/', // 视后端情况，如果报错可改为 '/site/delete/'
    // 🚨 截图显示无导出按钮，不配置 exportUrl
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
      { title: '漏洞URL', key: 'nuclei_vuln_url', width: 300 }, // 用专用 key 渲染超链接
      { title: '漏洞名称', dataIndex: 'vuln_name', key: 'vul_name', width: 200 },
      { title: '漏洞等级', dataIndex: 'vuln_severity', key: 'vuln_severity', width: 100, align: 'center' },
      { title: '保存时间', dataIndex: 'insert_time', key: 'insert_time', width: 160 },
      { title: '验证命令', key: 'verify_command', width: 350 } // 命令可能很长，用插槽防撑破
    ]
  },

  // 💡 新增：指纹统计 Tab 的 1:1 配置
  stat_finger: {
    url: '/stat_finger/',
    deleteUrl: '/site/delete/', // 视后端情况，如果报错可改为 '/site/delete/'
    // 🚨 截图显示无导出按钮
    searchFields: [
      { label: 'finger', key: 'name', operator: '=' } // 后端字段是 name
    ],
    cols: [
      { title: '序号', key: 'index', width: 80, align: 'center' },
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
        // 🚨 核心修改：移除 type: 'select'，加入这三个属性触发高级组合框
        operator: '包含',
        hasOperatorSelect: true,
        operators: ['包含', '不包含', '不等于']
      },
      { label: '内容', key: 'content', operator: '=' },
      { label: '来源 JS', key: 'source', operator: '=' },
      { label: '来源站点', key: 'site', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '记录类型', dataIndex: 'record_type', key: 'record_type', width: 120 },
      { title: '内容', dataIndex: 'content', key: 'content', width: 250 },
      { title: '来源 JS', key: 'wih_source', width: 450 },
      { title: '来源站点', dataIndex: 'site', key: 'site', width: 250 }
    ]
  }



};

const columns = ref(tabConfig.site.cols);

// 加载数据 (兼容单任务与全局查看)
const fetchData = async () => {
  const taskId = query.task_id;
  // 🚨 核心修改 1：删除了 if (!taskId) return; 让全局查看也能放行！

  const config = tabConfig[activeTab.value];
  if (!config) {
    dataSource.value = [];
    return;
  }

  loading.value = true;
  try {
    // 🚨 核心修改 2：动态拼装参数，有 taskId 才传
    const params = { page: pagination.current, size: pagination.pageSize };
    if (taskId) {
      params.task_id = taskId;
    }

    for (const key in searchForm.value) {
      if (searchForm.value[key] !== '' && searchForm.value[key] != null) {
        params[key] = searchForm.value[key];
      }
    }

    const res = await request.get(config.url, { params });
    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      selectedRowKeys.value = [];
    }
  } catch (error) {
    message.error('加载资产数据失败');
  } finally {
    loading.value = false;
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
        params[key] = searchForm.value[key];
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

watch(activeTab, (newVal) => {
  if (tabConfig[newVal]) {
    columns.value = tabConfig[newVal].cols;
    searchForm.value = {};
    pagination.current = 1;
    fetchData();
  } else {
    dataSource.value = [];
    columns.value = [];
  }
});

onMounted(fetchData);

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
.site-header { line-height: 1.5; }
.site-img { width: 16px; height: 16px; margin-right: 8px; vertical-align: middle; }
.site-word { color: #999; font-size: 12px; margin: 4px 0; }
/* 完美复刻原版的 "添加标签" 按钮 (灰色虚线框) */
.add-tag {
  color: #666;
  cursor: pointer;
  font-size: 12px;
  margin-left: 8px;
  border: 1px dashed #d9d9d9;
  padding: 0 7px;
  border-radius: 2px;
  background: #fafafa;
  transition: all 0.3s;
}
.add-tag:hover {
  color: #00bcd4;
  border-color: #00bcd4;
}
.mt5 { margin-top: 5px; }

.search-row { display: flex; flex-wrap: wrap; gap: 16px 24px; }
.search-item { display: flex; align-items: center; }
.search-item .label { color: rgba(0,0,0,0.85); margin-right: 8px; min-width: 80px; text-align: right; }

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
  color: rgba(0, 0, 0, 0.65);
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
  border: 1px solid #e8e8e8 !important;
  background: #fafafa !important;
  transition: all 0.3s;
}
:deep(.ant-tabs-card-bar .ant-tabs-tab-active) {
  background: #fff !important;
  border-bottom-color: transparent !important;
  color: #00bcd4 !important;
  font-weight: 500;
}
:deep(.ant-tabs-tab:hover) {
  color: #00bcd4 !important;
}
/* ================= 6. 站点列细节补充 ================= */
/* 完美复刻 Favicon Hash 的次级文本灰色与紧凑间距 */
/* 修复 Favicon Hash 发虚的问题：恢复原版字号和深色 */
.site-word {
  color: rgba(0, 0, 0, 0.85) !important; /* 恢复为标准的深黑色，去掉导致发虚的浅灰 */
  font-size: 14px !important;            /* 恢复标准字号，不缩小 */
  margin-top: 4px;
  margin-bottom: 0;
  line-height: 1.5;
}
</style>