<template>
  <a-drawer
    :open="open"
    :title="null"
    :closable="false"
    :width="drawerWidth"
    placement="right"
    destroyOnClose
    class="chain-drawer-root"
    @close="handleClose"
  >
    <div ref="scrollContainerRef" class="chain-drawer-scroll-wrapper" @scroll="handleScroll">
      <!-- 头部自定义导航与控制栏 (随页面一体自然滚动) -->
      <div class="chain-drawer-header">
      <div class="drawer-header-left">
        <div class="drawer-header-badge">
          <compass-outlined class="drawer-compass-icon" />
        </div>
        <div>
          <div class="drawer-title-text">
            <span>全链路资产画像</span>
            <a-tag color="blue" class="drawer-target-tag">{{ target }}</a-tag>
          </div>
          <div class="drawer-subtitle-text">
            已聚合 13 维资产暴露面与安全状态 · 点击下方指标胶囊可锚点直达
          </div>
        </div>
      </div>
      <div class="drawer-header-right">
        <a-tooltip title="复制目标">
          <a-button size="small" @click="handleCopyTarget">
            <template #icon><copy-outlined /></template>
          </a-button>
        </a-tooltip>
        <a-tooltip title="导出画像 (JSON)">
          <a-button size="small" :disabled="!chainData" @click="downloadChainJson">
            <template #icon><download-outlined /></template>
            导出画像
          </a-button>
        </a-tooltip>
        <a-button type="text" size="small" @click="handleClose">
          <template #icon><close-outlined /></template>
        </a-button>
      </div>
    </div>

    <!-- 抽屉主体内容区 -->
    <div class="chain-drawer-body">
      <a-spin :spinning="loading" tip="正在聚合多维全链路资产画像...">
        <!-- 仅当未发起查询或请求失败无数据对象时展示空白提示 -->
        <div v-if="!loading && !chainData" class="drawer-empty-box">
          <a-empty description="暂未检索到该资产的全链路关联记录">
            <template #image>
              <compass-outlined style="font-size: 56px; color: var(--arl-theme-color); opacity: 0.6;" />
            </template>
            <div style="margin-top: 12px; color: var(--arl-text-secondary); font-size: 13px;">
              目标暂未完成深度资产测绘，或未在当前资产组范围中命中关联数据
            </div>
          </a-empty>
        </div>

        <div v-else-if="chainData" class="chain-sections-container">
          <!-- 13 维统计指标与锚点导航胶囊行 (常驻展示，支持点击平滑滚动) -->
          <div class="chain-metric-row">
            <div
              v-for="chip in metricChips"
              :key="chip.id"
              class="chain-metric-chip"
              :class="{ 'is-zero': chip.count === 0 }"
              @click="scrollToSection(chip.id)"
              :title="`点击快速跳转至${chip.label}`"
            >
              <component :is="chip.icon" :style="{ color: chip.color }" class="metric-icon" />
              <span class="metric-label">{{ chip.label }}</span>
              <b :class="{ 'zero-num': chip.count === 0 }">{{ chip.count }}</b>
            </div>
          </div>

          <!-- 1. 站点基础信息与截图 -->
          <a-card id="chain-sec-site" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <global-outlined style="color: #1890ff;" />
                <span>站点基础信息</span>
                <a-badge :count="chainData.site?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.site?.length, '#1890ff')" />
              </div>
            </template>
            <div v-if="!chainData.site || chainData.site.length === 0" class="drawer-empty-row">
              <inbox-outlined class="empty-row-icon" />
              <span>未发现关联站点记录</span>
            </div>
            <div v-else class="drawer-site-list">
              <div v-for="(siteItem, idx) in chainData.site" :key="idx" class="drawer-site-item">
                <div class="drawer-site-meta">
                  <div class="site-title-row">
                    <img v-if="siteItem.favicon && siteItem.favicon.data" :src="`data:image/png;base64,${siteItem.favicon.data}`" class="drawer-favicon" />
                    <a :href="siteItem.site" target="_blank" class="site-link">{{ siteItem.site }}</a>
                    <a-tag :color="siteItem.status === 200 ? 'success' : (siteItem.status >= 400 ? 'error' : 'default')">
                      HTTP {{ siteItem.status || '-' }}
                    </a-tag>
                  </div>
                  <div class="site-kv-grid">
                    <div class="kv-item"><span class="kv-label">标题：</span><span class="kv-value">{{ siteItem.title || '-' }}</span></div>
                    <div class="kv-item"><span class="kv-label">Server：</span><span class="kv-value">{{ siteItem.http_server || '-' }}</span></div>
                    <div class="kv-item"><span class="kv-label">IP：</span><span class="kv-value font-mono">{{ siteItem.ip || '-' }}</span></div>
                    <div class="kv-item"><span class="kv-label">更新：</span><span class="kv-value">{{ siteItem.update_date || siteItem.save_date || '-' }}</span></div>
                  </div>
                  <div v-if="siteItem.finger && siteItem.finger.length" class="site-finger-row">
                    <span class="kv-label">指纹：</span>
                    <a-tag v-for="f in siteItem.finger" :key="f.name" color="blue" size="small">{{ f.name }}</a-tag>
                  </div>
                </div>
                <div v-if="siteItem.screenshot" class="drawer-site-shot">
                  <a-image :src="`/api${siteItem.screenshot}`" alt="截图" />
                </div>
              </div>
            </div>
          </a-card>

          <!-- 2. 子域名与解析记录 -->
          <a-card id="chain-sec-domain" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <link-outlined style="color: #52c41a;" />
                <span>子域名解析记录</span>
                <a-badge :count="chainData.domain_records?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.domain_records?.length, '#52c41a')" />
              </div>
            </template>
            <div v-if="!chainData.domain_records || chainData.domain_records.length === 0" class="drawer-empty-row">
              <inbox-outlined class="empty-row-icon" />
              <span>未发现子域名解析记录</span>
            </div>
            <a-table
              v-else
              :dataSource="chainData.domain_records"
              :columns="domainCols"
              :pagination="false"
              size="small"
              :rowKey="(r, i) => i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'domain'">
                  <span class="font-mono font-bold">{{ record.domain }}</span>
                </template>
                <template v-else-if="column.key === 'ips'">
                  <div v-if="Array.isArray(record.ips)">
                    <span v-for="(ip, idx) in record.ips" :key="idx" class="font-mono font-tag">{{ ip }}</span>
                  </div>
                  <span v-else class="font-mono">{{ record.ips || '-' }}</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 3. IP 与网络归属 -->
          <a-card id="chain-sec-ip" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <cloud-server-outlined style="color: #722ed1;" />
                <span>IP 与网络归属</span>
                <a-badge :count="chainData.ip?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.ip?.length, '#722ed1')" />
              </div>
            </template>
            <div v-if="!chainData.ip || chainData.ip.length === 0" class="drawer-empty-row">
              <inbox-outlined class="empty-row-icon" />
              <span>未发现关联 IP 资产记录</span>
            </div>
            <a-table
              v-else
              :dataSource="chainData.ip"
              :columns="ipCols"
              :pagination="false"
              size="small"
              :rowKey="(r, i) => i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'ip'">
                  <span class="font-mono font-bold">{{ record.ip }}</span>
                </template>
                <template v-else-if="column.key === 'port_info'">
                  <span>{{ record.port_info && record.port_info.length ? record.port_info.map(p => p.port_id).join(', ') : '-' }}</span>
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
          <a-card id="chain-sec-cert" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <safety-certificate-outlined style="color: #13c2c2;" />
                <span>SSL 证书</span>
                <a-badge :count="chainData.cert?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.cert?.length, '#13c2c2')" />
              </div>
            </template>
            <div v-if="!chainData.cert || chainData.cert.length === 0" class="drawer-empty-row">
              <inbox-outlined class="empty-row-icon" />
              <span>未发现关联 SSL 证书记录</span>
            </div>
            <div v-else>
              <div v-for="(certItem, idx) in chainData.cert" :key="idx" class="drawer-cert-item">
                <div class="cert-host-tag">{{ certItem.ip || certItem.host }}{{ certItem.port ? ':' + certItem.port : '' }}</div>
                <div v-if="certItem.cert" class="cert-fields">
                  <div><b>主题名称：</b>{{ certItem.cert.subject_dn || '-' }}</div>
                  <div><b>签发机构：</b>{{ certItem.cert.issuer_dn || '-' }}</div>
                  <div v-if="certItem.cert.extensions?.subjectAltName"><b>备用名称 (SAN)：</b>{{ certItem.cert.extensions.subjectAltName }}</div>
                  <div><b>有效期限：</b>{{ certItem.cert.validity?.start || '-' }} 至 {{ certItem.cert.validity?.end || '-' }}</div>
                </div>
              </div>
            </div>
          </a-card>

          <!-- 5. 系统服务 -->
          <a-card id="chain-sec-service" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <api-outlined style="color: #fa8c16;" />
                <span>开放系统服务</span>
                <a-badge :count="chainData.service?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.service?.length, '#fa8c16')" />
              </div>
            </template>
            <div v-if="!chainData.service || chainData.service.length === 0" class="drawer-empty-row">
              <inbox-outlined class="empty-row-icon" />
              <span>未发现开放系统服务记录</span>
            </div>
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
          <a-card id="chain-sec-fileleak" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <file-search-outlined style="color: #faad14;" />
                <span>敏感文件泄露</span>
                <a-badge :count="chainData.fileleak?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.fileleak?.length, '#faad14')" />
              </div>
            </template>
            <div v-if="!chainData.fileleak || chainData.fileleak.length === 0" class="drawer-empty-row">
              <inbox-outlined class="empty-row-icon" />
              <span>未发现疑似敏感文件泄露</span>
            </div>
            <a-table
              v-else
              :dataSource="chainData.fileleak"
              :columns="fileleakCols"
              :pagination="false"
              size="small"
              :rowKey="(r, i) => r.url || i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'url'">
                  <a :href="record.url" target="_blank" style="font-family: monospace; word-break: break-all;">{{ record.url }}</a>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 7. URL 信息 -->
          <a-card id="chain-sec-url" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <deployment-unit-outlined style="color: #2f54eb;" />
                <span>关联探测 URL</span>
                <a-badge :count="chainData.url?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.url?.length, '#2f54eb')" />
              </div>
            </template>
            <div v-if="!chainData.url || chainData.url.length === 0" class="drawer-empty-row">
              <inbox-outlined class="empty-row-icon" />
              <span>未发现关联探测 URL 记录</span>
            </div>
            <a-table
              v-else
              :dataSource="chainData.url"
              :columns="urlCols"
              :pagination="false"
              size="small"
              :rowKey="(r, i) => r.url || i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'url'">
                  <a :href="record.url" target="_blank" style="font-family: monospace; word-break: break-all;">{{ record.url }}</a>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 8. C 段网段 -->
          <a-card id="chain-sec-cip" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <cluster-outlined style="color: #eb2f96;" />
                <span>关联 C 段网段</span>
                <a-badge :count="chainData.cip?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.cip?.length, '#eb2f96')" />
              </div>
            </template>
            <div v-if="!chainData.cip || chainData.cip.length === 0" class="drawer-empty-row">
              <inbox-outlined class="empty-row-icon" />
              <span>未发现关联 C 段资产记录</span>
            </div>
            <a-table
              v-else
              :dataSource="chainData.cip"
              :columns="cipCols"
              :pagination="false"
              size="small"
              :rowKey="(r, i) => r.cidr_ip || i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'cidr_ip'">
                  <span class="font-mono font-bold">{{ record.cidr_ip || '-' }}</span>
                </template>
                <template v-else-if="column.key === 'ip_count'">
                  <a-tag color="purple" class="font-mono">{{ record.ip_count ?? (record.ip_list?.length || 0) }} 个 IP</a-tag>
                </template>
                <template v-else-if="column.key === 'domain_count'">
                  <a-tag color="blue" class="font-mono">{{ record.domain_count ?? (record.domain_list?.length || 0) }} 个域名</a-tag>
                </template>
                <template v-else-if="column.key === 'update_date'">
                  <span style="font-size: 12px; color: var(--arl-text-secondary);">{{ record.update_date || record.save_date || '-' }}</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 9. 指纹统计 -->
          <a-card id="chain-sec-stat-finger" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <tag-outlined style="color: #1d39c4;" />
                <span>关联指纹统计</span>
                <a-badge :count="statFingerList.length" :show-zero="true" :number-style="getBadgeStyle(statFingerList.length, '#1d39c4')" />
              </div>
            </template>
            <div v-if="statFingerList.length === 0" class="drawer-empty-row">
              <inbox-outlined class="empty-row-icon" />
              <span>未识别到关联技术栈与组件指纹</span>
            </div>
            <a-table
              v-else
              :dataSource="statFingerList"
              :columns="fingerCols"
              :pagination="false"
              size="small"
              :rowKey="(r, i) => r.finger_name || i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'finger_name'">
                  <a-tag color="blue">{{ record.finger_name }}</a-tag>
                </template>
                <template v-else-if="column.key === 'cnt'">
                  <span class="font-mono font-bold">{{ record.cnt }} 个站点</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 10. WIH 敏感信息 -->
          <a-card id="chain-sec-wih" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <radar-chart-outlined style="color: #fa8c16;" />
                <span>WEB Info Hunter (WIH)</span>
                <a-badge :count="chainData.wih?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.wih?.length, '#fa8c16')" />
              </div>
            </template>
            <div v-if="!chainData.wih || chainData.wih.length === 0" class="drawer-empty-row">
              <inbox-outlined class="empty-row-icon" />
              <span>未发现 WEB Info Hunter (WIH) 泄露信息</span>
            </div>
            <a-table
              v-else
              :dataSource="chainData.wih"
              :columns="wihCols"
              :pagination="false"
              size="small"
              :rowKey="(r, i) => r._id || i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'content'">
                  <span style="font-family: monospace; word-break: break-all; color: #fa8c16; font-weight: 500;">
                    {{ record.content }}
                  </span>
                </template>
                <template v-else-if="column.key === 'source'">
                  <a v-if="record.source || record.site" :href="record.source || record.site" target="_blank" style="font-family: monospace; word-break: break-all;">
                    {{ record.source || record.site }}
                  </a>
                  <span v-else>-</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 11. 应用风险漏洞 -->
          <a-card id="chain-sec-vuln" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <bug-outlined style="color: #f5222d;" />
                <span>应用风险漏洞 (PoC)</span>
                <a-badge :count="chainData.vuln?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.vuln?.length, '#f5222d')" />
              </div>
            </template>
            <div v-if="!chainData.vuln || chainData.vuln.length === 0" class="drawer-empty-row">
              <inbox-outlined class="empty-row-icon" />
              <span>未检测到应用服务漏洞风险</span>
            </div>
            <div v-else class="drawer-vuln-list">
              <div v-for="(v, idx) in chainData.vuln" :key="'v-'+idx" class="vuln-item-card">
                <div class="vuln-header">
                  <a-tag color="error">风险</a-tag>
                  <span class="vuln-name">{{ v.vul_name || v.title || '未知风险' }}</span>
                </div>
                <div class="vuln-target font-mono">{{ v.target }}</div>
              </div>
            </div>
          </a-card>

          <!-- 12. 服务 (Python NPOC) -->
          <a-card id="chain-sec-npoc" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <code-outlined style="color: #722ed1;" />
                <span>服务探测 (Python NPOC)</span>
                <a-badge :count="chainData.npoc_service?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.npoc_service?.length, '#722ed1')" />
              </div>
            </template>
            <div v-if="!chainData.npoc_service || chainData.npoc_service.length === 0" class="drawer-empty-row">
              <inbox-outlined class="empty-row-icon" />
              <span>未发现 Python NPOC 探测服务记录</span>
            </div>
            <a-table
              v-else
              :dataSource="chainData.npoc_service"
              :columns="npocCols"
              :pagination="false"
              size="small"
              :rowKey="(r, i) => r._id || i"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'scheme'">
                  <a-tag color="purple">{{ record.scheme || '-' }}</a-tag>
                </template>
                <template v-else-if="column.key === 'target'">
                  <span class="font-mono">{{ record.target || '-' }}</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 13. Nuclei 扫描发现 -->
          <a-card id="chain-sec-nuclei" :bordered="false" class="drawer-chain-card">
            <template #title>
              <div class="drawer-card-title">
                <fire-outlined style="color: #fa541c;" />
                <span>Nuclei 漏洞发现</span>
                <a-badge :count="chainData.nuclei_result?.length || 0" :show-zero="true" :number-style="getBadgeStyle(chainData.nuclei_result?.length, '#fa541c')" />
              </div>
            </template>
            <div v-if="!chainData.nuclei_result || chainData.nuclei_result.length === 0" class="drawer-empty-row">
              <inbox-outlined class="empty-row-icon" />
              <span>未命中 Nuclei 漏洞特征</span>
            </div>
            <div v-else class="drawer-vuln-list">
              <div v-for="(n, idx) in chainData.nuclei_result" :key="'n-'+idx" class="vuln-item-card">
                <div class="vuln-header">
                  <a-tag color="volcano">Nuclei</a-tag>
                  <span class="vuln-name">{{ n.vuln_name || n.template_id }}</span>
                  <a-tag size="small" :color="getSeverityColor(n.vuln_severity || n.vul_severity)">
                    {{ (n.vuln_severity || n.vul_severity || 'HIGH').toUpperCase() }}
                  </a-tag>
                </div>
                <div class="vuln-target font-mono">{{ n.vuln_url || n.target }}</div>
              </div>
            </div>
          </a-card>

        </div>
      </a-spin>
    </div>
    </div>

    <!-- 右下角悬浮回到顶端按钮 (大号圆形科技质感悬浮球) -->
    <transition name="fade">
      <div
        v-if="showBackTop"
        class="chain-back-top-btn"
        @click="scrollToTop"
      >
        <a-tooltip title="回到顶端" placement="left">
          <div class="back-top-circle">
            <vertical-align-top-outlined class="back-top-icon" />
          </div>
        </a-tooltip>
      </div>
    </transition>
  </a-drawer>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue';
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
  InboxOutlined,
  VerticalAlignTopOutlined
} from '@ant-design/icons-vue';
import request from '../utils/request';
import { formatGeo } from '../utils/formatGeo';
import { copyText } from '../utils/clipboard';

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
const showBackTop = ref(false);

const handleScroll = (e) => {
  const scrollTop = e?.target?.scrollTop ?? 0;
  showBackTop.value = scrollTop > 200;
};

const scrollToTop = () => {
  if (scrollContainerRef.value) {
    scrollContainerRef.value.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  }
};

const drawerWidth = computed(() => {
  return window.innerWidth > 1400 ? '900px' : (window.innerWidth > 992 ? '800px' : '92vw');
});

const domainCols = [
  { title: '子域名', dataIndex: 'domain', key: 'domain' },
  { title: '类型', dataIndex: 'type', key: 'type', width: 90, align: 'center' },
  { title: '解析IP', key: 'ips' }
];

const ipCols = [
  { title: 'IP', dataIndex: 'ip', key: 'ip', width: 140 },
  { title: '开放端口', key: 'port_info' },
  { title: '地理位置', key: 'geo', width: 140 },
  { title: 'AS机构', key: 'asn' }
];

const cipCols = [
  { title: 'C段网段', dataIndex: 'cidr_ip', key: 'cidr_ip', width: 180 },
  { title: '关联IP', key: 'ip_count', width: 120, align: 'center' },
  { title: '关联域名', key: 'domain_count', width: 120, align: 'center' },
  { title: '更新时间', key: 'update_date', width: 160 }
];

const npocCols = [
  { title: '协议', dataIndex: 'scheme', key: 'scheme', width: 100, align: 'center' },
  { title: '目标', dataIndex: 'target', key: 'target' }
];

const fileleakCols = [
  { title: 'URL', key: 'url' },
  { title: '标题', dataIndex: 'title', key: 'title', width: 160 },
  { title: '状态码', dataIndex: 'status_code', key: 'status_code', width: 80, align: 'center' },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 160 }
];

const urlCols = [
  { title: 'URL', key: 'url' },
  { title: '标题', dataIndex: 'title', key: 'title', width: 160 },
  { title: '状态码', dataIndex: 'status_code', key: 'status_code', width: 80, align: 'center' },
  { title: '来源', dataIndex: 'source', key: 'source', width: 110 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 160 }
];

const fingerCols = [
  { title: '指纹组件名称', dataIndex: 'finger_name', key: 'finger_name' },
  { title: '关联站点数量', key: 'cnt', width: 140, align: 'center' }
];

const wihCols = [
  { title: '类型', dataIndex: 'record_type', key: 'record_type', width: 100 },
  { title: '敏感内容', dataIndex: 'content', key: 'content' },
  { title: '来源 JS/站点', key: 'source', width: 220 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 160 }
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

// 13 维统计指标与锚点导航胶囊列表
const metricChips = computed(() => {
  if (!chainData.value) return [];
  const d = chainData.value;
  return [
    { id: 'chain-sec-site', label: '站点', count: d.site?.length || 0, icon: GlobalOutlined, color: '#1890ff' },
    { id: 'chain-sec-domain', label: '子域名', count: d.domain_records?.length || 0, icon: LinkOutlined, color: '#52c41a' },
    { id: 'chain-sec-ip', label: 'IP', count: d.ip?.length || 0, icon: CloudServerOutlined, color: '#722ed1' },
    { id: 'chain-sec-cert', label: 'SSL证书', count: d.cert?.length || 0, icon: SafetyCertificateOutlined, color: '#13c2c2' },
    { id: 'chain-sec-service', label: '服务', count: d.service?.length || 0, icon: ApiOutlined, color: '#fa8c16' },
    { id: 'chain-sec-fileleak', label: '文件泄露', count: d.fileleak?.length || 0, icon: FileSearchOutlined, color: '#faad14' },
    { id: 'chain-sec-url', label: 'URL信息', count: d.url?.length || 0, icon: DeploymentUnitOutlined, color: '#2f54eb' },
    { id: 'chain-sec-cip', label: 'C段', count: d.cip?.length || 0, icon: ClusterOutlined, color: '#eb2f96' },
    { id: 'chain-sec-stat-finger', label: '指纹统计', count: statFingerList.value.length, icon: TagOutlined, color: '#1d39c4' },
    { id: 'chain-sec-wih', label: 'WIH', count: d.wih?.length || 0, icon: RadarChartOutlined, color: '#fa8c16' },
    { id: 'chain-sec-vuln', label: '风险', count: d.vuln?.length || 0, icon: BugOutlined, color: '#f5222d' },
    { id: 'chain-sec-npoc', label: '服务(python)', count: d.npoc_service?.length || 0, icon: CodeOutlined, color: '#722ed1' },
    { id: 'chain-sec-nuclei', label: 'nuclei', count: d.nuclei_result?.length || 0, icon: FireOutlined, color: '#fa541c' }
  ];
});

// 平滑滚动定位到指定资产卡片
const scrollToSection = (secId) => {
  const el = document.getElementById(secId);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
};

const getBadgeStyle = (cnt, activeColor) => {
  if (cnt && cnt > 0) {
    return { backgroundColor: activeColor };
  }
  return { backgroundColor: '#f0f0f0', color: '#8c8c8c' };
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
  loading.value = true;
  chainData.value = null;
  try {
    const res = await request.get('/asset_site/subdomain_chain/', {
      params: {
        scope_id: props.scopeId,
        domain: props.target.trim()
      }
    });
    if (res.code === 200) {
      chainData.value = res.data || {};
    } else {
      message.error(res.message || '获取画像失败');
    }
  } catch (e) {
    message.error('网络请求异常');
  } finally {
    loading.value = false;
  }
};

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    showBackTop.value = false;
    nextTick(() => {
      if (scrollContainerRef.value) {
        scrollContainerRef.value.scrollTop = 0;
      }
    });
    if (props.target) {
      fetchChainData();
    }
  }
});

watch(() => props.target, (newTarget) => {
  if (props.open && newTarget) {
    fetchChainData();
  }
});

const handleClose = () => {
  emit('update:open', false);
  emit('close');
};

const handleCopyTarget = async () => {
  const ok = await copyText(props.target);
  if (ok) message.success('已复制目标: ' + props.target);
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
    const targetLabel = props.target || 'target';
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
</script>

<style scoped>
.chain-drawer-root :deep(.ant-drawer-body) {
  padding: 0;
  background: var(--arl-bg-layout);
  height: 100%;
  overflow: hidden;
  position: relative;
}

.chain-drawer-scroll-wrapper {
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}

.chain-drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: var(--arl-bg-white);
  border-bottom: 1px solid var(--arl-border-color);
}

.drawer-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.drawer-header-badge {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: rgba(250, 84, 28, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
}

.drawer-compass-icon {
  font-size: 20px;
  color: var(--arl-theme-color);
}

.drawer-title-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--arl-text-color);
  display: flex;
  align-items: center;
  gap: 8px;
}

.drawer-target-tag {
  font-family: monospace;
  font-size: 13px;
  border-radius: 4px;
}

.drawer-subtitle-text {
  font-size: 12px;
  color: var(--arl-text-secondary);
  margin-top: 2px;
}

.drawer-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chain-drawer-body {
  padding: 20px;
}

.drawer-empty-box {
  background: var(--arl-bg-white);
  border-radius: 8px;
  padding: 80px 24px;
  text-align: center;
  border: 1px dashed var(--arl-border-color);
}

.chain-sections-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chain-metric-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
  padding: 4px 0 8px 0;
}

.chain-metric-chip {
  background: var(--arl-bg-white);
  border: 1px solid var(--arl-border-color);
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--arl-text-color);
  cursor: pointer;
  user-select: none;
  transition: all 0.2s ease;
}

.chain-metric-chip:hover {
  border-color: var(--arl-theme-color);
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
}

.chain-metric-chip.is-zero {
  opacity: 0.6;
  background: rgba(0, 0, 0, 0.02);
}

.chain-metric-chip.is-zero:hover {
  opacity: 1;
}

.chain-metric-chip b {
  color: var(--arl-primary-color);
  font-family: monospace;
}

.chain-metric-chip b.zero-num {
  color: var(--arl-text-secondary);
}

.drawer-chain-card {
  border-radius: 8px;
  background: var(--arl-bg-white);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  scroll-margin-top: 16px;
}

/* 回到顶端悬浮按钮 (48px 科技质感圆形悬浮球) */
.chain-back-top-btn {
  position: absolute;
  right: 28px;
  bottom: 32px;
  z-index: 100;
  cursor: pointer;
  user-select: none;
}

.back-top-circle {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #40a9ff 0%, #1890ff 50%, #096dd9 100%);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 18px rgba(24, 144, 255, 0.38), 0 2px 6px rgba(0, 0, 0, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.3);
  transition: all 0.28s cubic-bezier(0.34, 1.56, 0.64, 1);
  backdrop-filter: blur(4px);
}

.back-top-icon {
  font-size: 22px;
  line-height: 1;
  transition: transform 0.28s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.chain-back-top-btn:hover .back-top-circle {
  transform: translateY(-4px) scale(1.08);
  box-shadow: 0 10px 24px rgba(24, 144, 255, 0.52), 0 4px 10px rgba(0, 0, 0, 0.15);
  background: linear-gradient(135deg, #69c0ff 0%, #1890ff 45%, #0050b3 100%);
}

.chain-back-top-btn:hover .back-top-icon {
  transform: translateY(-2px);
}

.chain-back-top-btn:active .back-top-circle {
  transform: translateY(-1px) scale(0.96);
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1), transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(16px) scale(0.8);
}

.drawer-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}

/* 紧凑型空状态行 */
.drawer-empty-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  background: var(--arl-bg-light);
  border-radius: 6px;
  color: var(--arl-text-secondary);
  font-size: 12px;
  border: 1px dashed var(--arl-border-color);
}

.empty-row-icon {
  font-size: 14px;
  opacity: 0.55;
}

.drawer-site-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.drawer-site-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 12px;
  border-radius: 6px;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
}

.drawer-site-meta {
  flex: 1;
}

.site-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.drawer-favicon {
  width: 16px;
  height: 16px;
}

.site-link {
  font-weight: 600;
  font-size: 14px;
  color: var(--arl-theme-color);
  word-break: break-all;
}

.site-kv-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px 12px;
  font-size: 12px;
}

.kv-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.kv-label {
  color: var(--arl-text-secondary);
}

.kv-value {
  color: var(--arl-text-color);
}

.site-finger-row {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.drawer-site-shot :deep(img) {
  width: 140px;
  height: 90px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid var(--arl-border-color);
}

.font-mono {
  font-family: monospace;
}

.font-bold {
  font-weight: 600;
}

.font-tag {
  display: inline-block;
  background: rgba(0, 0, 0, 0.04);
  padding: 2px 6px;
  border-radius: 4px;
  margin-right: 4px;
  margin-bottom: 2px;
}

.drawer-cert-item {
  padding: 10px;
  background: var(--arl-bg-light);
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
  margin-bottom: 8px;
}

.cert-host-tag {
  font-weight: 600;
  font-family: monospace;
  color: var(--arl-primary-color);
  margin-bottom: 6px;
}

.cert-fields {
  font-size: 12px;
  line-height: 1.6;
  color: var(--arl-text-color);
}

.drawer-services-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
}

.service-pill {
  padding: 8px;
  background: var(--arl-bg-light);
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
}

.service-name-tag {
  font-size: 12px;
  font-weight: 600;
  color: var(--arl-primary-color);
  margin-bottom: 4px;
}

.service-endpoint {
  font-size: 11px;
  display: flex;
  justify-content: space-between;
  gap: 4px;
}

.service-product {
  color: var(--arl-text-secondary);
}

.drawer-vuln-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.vuln-item-card {
  padding: 8px 12px;
  background: var(--arl-bg-light);
  border-radius: 6px;
  border-left: 3px solid #f5222d;
}

.vuln-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.vuln-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--arl-text-color);
}

.vuln-target {
  font-size: 12px;
  color: var(--arl-text-secondary);
}
</style>
