<template>
  <div style="padding: 24px; background: var(--arl-bg-white); min-height: 100%;">
    <h2 style="margin-bottom: 24px;">系统设置</h2>
    
    <a-tabs v-model:activeKey="activeKey">
      <!-- 统一字典管理 Tab -->
      <a-tab-pane key="dictionary" tab="字典管理">
        <a-spin :spinning="loading || bruteLoading">
            <div style="display: flex; gap: 0; height: calc(100vh - 180px); min-height: 580px; border: 1px solid var(--arl-border-color); border-radius: 4px; overflow: hidden;"> <!-- 左侧语义化菜单与独立滚动 -->
            <div style="width: 256px; flex-shrink: 0; border-right: 1px solid var(--arl-border-color); background: var(--arl-bg-white); display: flex; flex-direction: column;">
              <div style="padding: 16px; border-bottom: 1px solid var(--arl-border-color);">
                <a-input-search v-model:value="menuSearch" placeholder="搜索字典名称..." style="width: 100%; border-radius: 4px;" />
              </div>
              <div style="flex: 1; overflow-y: auto;">
                <a-menu
                  v-model:selectedKeys="unifiedSelectedKeys"
                  v-model:openKeys="menuOpenKeys"
                  mode="inline"
                  :style="{ borderRight: 'none' }"
                  @select="handleUnifiedMenuSelect"
                >
                  <a-sub-menu v-for="group in filteredTreeData" :key="group.key">
                    <template #title>
                      <span style="font-weight: 600; color: var(--arl-text-color);">{{ group.title }}</span>
                    </template>
                    <a-menu-item v-for="item in group.children" :key="item.key" style="height: auto; line-height: normal; padding-top: 8px; padding-bottom: 8px;">
                      <div style="display: flex; flex-direction: column; gap: 4px;">
                        <span style="color: var(--arl-text-color); font-size: 13px; font-weight: 500;">{{ item.mainTitle }}</span>
                        <span style="color: var(--arl-text-color); opacity: 0.65; font-size: 11px;">{{ item.subTitle }}</span>
                      </div>
                    </a-menu-item>
                  </a-sub-menu>
                </a-menu>
              </div>
            </div>

            <!-- 右侧统一操作面板 -->
            <div style="flex: 1; overflow: hidden; display: flex; flex-direction: column; min-width: 0; background: var(--arl-bg-white);">

              <!-- 未选中时占位（健康看板） -->
              <div v-if="!unifiedSelectedType" style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--arl-text-color); gap: 16px; overflow-y: auto;">
                <div style="font-size: 48px; margin-bottom: 8px;">📊</div>
                <h3 style="margin: 0; color: var(--arl-text-color); font-weight: bold;">字典库健康概览</h3>
                <div style="display: flex; gap: 24px; margin-top: 16px;">
                  <div style="text-align: center; background: var(--arl-bg-light); padding: 20px 32px; border-radius: 8px; border: 1px solid var(--arl-border-color); min-width: 160px;">
                    <div style="font-size: 28px; font-weight: bold; color: var(--arl-theme-color);">{{ dictList.length }}</div>
                    <div style="font-size: 13px; color: var(--arl-text-color); margin-top: 6px;">核心资产字典数</div>
                  </div>
                  <div style="text-align: center; background: var(--arl-bg-white)7e6; padding: 20px 32px; border-radius: 8px; border: 1px solid var(--arl-border-color); min-width: 160px;">
                    <div style="font-size: 28px; font-weight: bold; color: #fa8c16;">{{ bruteDictList.length }}</div>
                    <div style="font-size: 13px; color: var(--arl-text-color); margin-top: 6px;">弱口令字典数</div>
                  </div>
                </div>
                <div style="font-size: 13px; color: var(--arl-text-color); opacity: 0.45; margin-top: 24px;">👈 请在左侧选择要管理的字典文件</div>
              </div>

              <!-- 统一操作面板（沉浸式预览与悬浮操作） -->
              <div v-else style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
                <!-- 头部标题与操作栏 -->
                <div style="padding: 24px; border-bottom: 1px solid var(--arl-border-color); display: flex; justify-content: space-between; align-items: flex-start; background: var(--arl-bg-white); flex-shrink: 0;">
                   <div>
                     <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                       <h3 style="margin: 0; font-size: 18px; font-weight: 600; color: var(--arl-text-color);">{{ unifiedSelectedName }}</h3>
                       <a-tag :color="unifiedSelectedType === 'asset' ? 'blue' : 'orange'" style="margin: 0;">
                         {{ unifiedSelectedType === 'asset' ? '资产发现字典' : '弱口令字典' }}
                       </a-tag>
                     </div>
                     <div style="color: var(--arl-text-color); opacity: 0.65; font-size: 13px;">{{ unifiedSelectedDesc }} | 共 <span style="font-weight: 600; color: var(--arl-text-color);">{{ totalLines }}</span> 行记录</div>
                   </div>
                   <div style="display: flex; gap: 12px;">
                     <a-button @click="searchDrawerVisible = true">
                       <template #icon><span style="margin-right:4px;">🔍</span></template> 检索与清理
                     </a-button>
                     <a-button type="primary" @click="appendDrawerVisible = true">
                       <template #icon><span style="margin-right:4px;">➕</span></template> 追加数据
                     </a-button>
                   </div>
                </div>
                
                <!-- 沉浸式内容预览 -->
                <div style="flex: 1; overflow-y: auto; padding: 24px; background: transparent;">
                   <div style="background: var(--arl-bg-white); border-radius: 8px; border: 1px solid var(--arl-border-color); padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                     <div style="font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; font-size: 13px; color: var(--arl-text-color); line-height: 1.6; white-space: pre-wrap; word-break: break-all;">
                       <div v-if="!previewContent" style="color: var(--arl-text-color); opacity: 0.25; text-align: center; padding: 60px 0;">该字典暂无内容</div>
                       <template v-else>{{ previewContent }}</template>
                     </div>
                     <div v-if="totalLines > previewLimit" style="text-align: center; margin-top: 24px; padding-top: 16px; border-top: 1px dashed var(--arl-border-color); color: var(--arl-text-color); opacity: 0.45; font-size: 12px;">
                       仅预览前 {{ previewLimit }} 行内容
                     </div>
                   </div>
                </div>
              </div>

            </div>
          </div>
        </a-spin>

        <!-- 追加数据抽屉 -->
        <a-drawer v-model:open="appendDrawerVisible" title="追加字典数据" placement="right" width="450">
          <div style="margin-bottom: 12px; color: var(--arl-text-color); font-size: 13px;">请粘贴要追加的条目（每行一个）：</div>
          <a-textarea v-model:value="newEntries" :rows="25" placeholder="例如：
admin
root" style="font-family: monospace; font-size: 12px; margin-bottom: 24px;" />
          <div style="display: flex; justify-content: flex-end; gap: 12px;">
            <a-button @click="appendDrawerVisible = false">取消</a-button>
            <a-button type="primary" @click="handleAppendAndClose" :loading="submitLoading" :disabled="!newEntries.trim()">提交保存</a-button>
          </div>
        </a-drawer>

        <!-- 搜索清理抽屉 -->
        <a-drawer v-model:open="searchDrawerVisible" title="检索与清理" placement="right" width="450">
          <div style="margin-bottom: 24px;">
            <div style="margin-bottom: 8px; font-weight: 500; font-size: 14px;">🎯 精准检索</div>
            <a-input-search
              v-model:value="searchKeyword"
              placeholder="输入关键词精确搜索条目"
              @search="handleSearch"
              :loading="searchLoading"
            >
              <template #enterButton><a-button type="primary">搜索</a-button></template>
            </a-input-search>
            
            <div v-if="searchResult !== null" style="margin-top: 12px;">
              <div v-if="searchResult.length > 0" style="margin-bottom: 8px; color: #52c41a; font-size: 13px;">✅ 找到 {{ searchResult.length }} 条匹配项</div>
              <div v-else style="margin-bottom: 8px; color: #ff4d4f; font-size: 13px;">❌ 未找到匹配条目</div>
              <div v-if="searchResult.length > 0" style="max-height: 300px; overflow-y: auto;">
                <div v-for="(item, idx) in searchResult" :key="idx" style="display: flex; align-items: center; justify-content: space-between; padding: 6px 12px; border-bottom: 1px solid var(--arl-border-color); background: var(--arl-bg-light); margin-bottom: 4px; border-radius: 4px;">
                  <span style="font-family: monospace; font-size: 12px; word-break: break-all; color: var(--arl-text-color);">{{ item }}</span>
                  <a-button type="text" danger size="small" @click="handleDeleteSingle(item)" :loading="deleteLoading">删除</a-button>
                </div>
              </div>
              <div v-if="searchResult.length === 100" style="color: #faad14; font-size: 12px; margin-top: 8px;">* 仅显示前 100 条，请细化关键词</div>
            </div>
          </div>
          
          <a-divider />
          
          <div>
            <div style="margin-bottom: 8px; font-weight: 500; font-size: 14px; color: #ff4d4f;">🗑️ 批量删除</div>
            <div style="margin-bottom: 8px; color: var(--arl-text-color); opacity: 0.45; font-size: 12px;">输入要删除的准确条目，每行一个：</div>
            <a-textarea v-model:value="batchDeleteEntries" :rows="10" placeholder="例如：
admin123
123456" style="font-family: monospace; font-size: 12px; margin-bottom: 16px;" />
            <a-button danger block @click="handleDeleteBatchCustom" :loading="deleteLoading" :disabled="!batchDeleteEntries.trim()">执行批量删除</a-button>
          </div>
        </a-drawer>
      </a-tab-pane>

      <!-- CDN 字典管理 Tab -->
      <a-tab-pane key="cdn" tab="CDN字典管理" force-render>
        <div style="margin-bottom: 16px; display: flex; justify-content: space-between;">
          <div style="display: flex; gap: 8px;">
            <a-button type="primary" @click="openCdnModal()">添加CDN特征</a-button>
            <a-upload
              name="file"
              :show-upload-list="false"
              :customRequest="handleCdnImport"
              accept=".json"
            >
              <a-button>一键导入CDN</a-button>
            </a-upload>
          </div>
          <a-button type="primary" @click="saveCdnData" :loading="cdnSaveLoading">保存全量更改到服务器</a-button>
        </div>
        
        <a-table 
          :dataSource="cdnList" 
          :columns="cdnColumns" 
          rowKey="name"
          :pagination="{ pageSize: 20 }"
          size="middle"
          :loading="cdnLoading"
        >
          <template #bodyCell="{ column, record, index }">
            <template v-if="column.key === 'cname_domain'">
              <div style="max-height: 100px; overflow-y: auto;">
                <a-tag v-for="cname in (record.cname_domain || [])" :key="cname" color="blue" style="margin-bottom: 4px;">{{ cname }}</a-tag>
              </div>
            </template>
            <template v-else-if="column.key === 'ip_cidr'">
              <div style="max-height: 100px; overflow-y: auto;">
                <a-tag v-for="ip in (record.ip_cidr || [])" :key="ip" color="green" style="margin-bottom: 4px;">{{ ip }}</a-tag>
              </div>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-button type="link" @click="openCdnModal(record, index)">编辑</a-button>
              <a-popconfirm title="确定要删除该CDN特征吗？此操作需点击右上角保存后才能持久化" @confirm="deleteCdnItem(index)">
                <a-button type="link" danger>删除</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>

        <!-- CDN 编辑弹窗 -->
        <a-modal
          v-model:open="cdnModalVisible"
          :title="isEditingCdn ? '编辑CDN特征' : '添加CDN特征'"
          @ok="submitCdnModal"
          width="700px"
          destroyOnClose
        >
          <a-form :model="currentCdnForm" :label-col="{ span: 4 }" :wrapper-col="{ span: 19 }" style="margin-top: 20px;">
            <a-form-item label="CDN名称" required>
              <a-input v-model:value="currentCdnForm.name" placeholder="例如：阿里云CDN" />
            </a-form-item>
            <a-form-item label="CNAME后缀">
              <a-textarea v-model:value="currentCdnForm.cnameText" :rows="4" placeholder="每行输入一个CNAME后缀，如: kunlunpi.com" />
            </a-form-item>
            <a-form-item label="IP网段(CIDR)">
              <a-textarea v-model:value="currentCdnForm.ipText" :rows="4" placeholder="每行输入一个IP网段，如: 103.21.244.0/22" />
            </a-form-item>
          </a-form>
        </a-modal>
      </a-tab-pane>

      <!-- 安全策略管理 Tab -->
      <a-tab-pane key="security" tab="安全策略管理" force-render>
        <div style="max-width: 1000px; padding-bottom: 40px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <span style="color: var(--arl-text-color); opacity: 0.45;">
              此处的配置项用于全局的安全限制，防止系统对指定范围的 IP 或域名发起扫描。保存后立即生效，无需重启。
            </span>
            <a-button type="primary" @click="saveSecurityPolicy" :loading="securitySaveLoading">
              保存安全策略
            </a-button>
          </div>
          <a-spin :spinning="securityLoading">
            <a-form layout="vertical">
              <a-form-item label="IP 黑名单 (支持 CIDR，如 127.0.0.0/8, 192.168.0.0/16，每行一个)">
                <a-textarea v-model:value="securityForm.blackIpsText" :rows="8" placeholder="例如：\n127.0.0.0/8\n10.0.0.0/8" />
              </a-form-item>
              
              <a-form-item label="禁止扫描域名 (支持后缀匹配，如 gov.cn, edu.cn，每行一个)">
                <a-textarea v-model:value="securityForm.forbiddenDomainsText" :rows="8" placeholder="例如：\ngov.cn\nedu.cn" />
              </a-form-item>
            </a-form>
          </a-spin>
        </div>
      </a-tab-pane>
      <!-- 性能与并发配置 Tab -->
      <a-tab-pane key="performance" tab="性能与并发配置" force-render>
        <div style="max-width: 1000px; padding-bottom: 40px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <span style="color: var(--arl-text-color); opacity: 0.45;">
              此处的配置用于精细化控制轻/重任务队列的并发处理能力。
            </span>
            <div>

              <a-button type="primary" @click="savePerformanceConfig" :loading="performanceSaveLoading">
                保存性能配置
              </a-button>
            </div>
          </div>
          <a-spin :spinning="performanceLoading">
            <a-form layout="vertical">
              <a-row :gutter="24">
                <a-col :span="12">
                  <a-card title="⚙️ 重任务 (Heavy Task) 调度" size="small" style="margin-bottom: 16px; border-radius: 6px; border-left: 4px solid #ff4d4f;">
                    <a-form-item>
                      <template #label>
                        重任务并发数
                        <a-popover placement="right">
                          <template #content>
                            <div style="max-width: 320px;">
                              <div style="font-weight: bold; margin-bottom: 8px;">[分配规则] 阻塞式长线任务：</div>
                              <ul style="padding-left: 18px; margin: 0; line-height: 1.8;">
                                <li>常规域名 / IP 扫描任务</li>
                                <li>风险巡航任务 (批量漏洞检测)</li>
                                <li>定时域名 / IP 监控任务</li>
                              </ul>
                            </div>
                          </template>
                          <InfoCircleOutlined style="margin-left: 4px; color: #888; cursor: pointer;" />
                        </a-popover>
                      </template>
                      <a-input-number v-model:value="performanceForm.celery_heavy_concurrency" :min="1" :max="128" style="width: 100%" />
                      <div style="margin-top: 8px; color: var(--arl-text-color); opacity: 0.45; font-size: 13px;">
                        控制常规扫描、风险巡航等长线任务的并发数。单个任务峰值占用内存1G左右，建议配置与内存相同的并发数，过大易导致系统 OOM 或压垮目标。
                      </div>
                    </a-form-item>
                  </a-card>
                </a-col>
                <a-col :span="12">
                  <a-card title="⚡ 轻任务 (Light Task) 调度" size="small" style="margin-bottom: 16px; border-radius: 6px; border-left: 4px solid #52c41a;">
                    <a-form-item>
                      <template #label>
                        轻任务并发数
                        <a-popover placement="right">
                          <template #content>
                            <div style="max-width: 320px;">
                              <div style="font-weight: bold; margin-bottom: 8px;">[分配规则] 非阻塞单点 API 任务：</div>
                              <ul style="padding-left: 18px; margin: 0; line-height: 1.8;">
                                <li>空间测绘查询 (FOFA 等)</li>
                                <li>更新单个站点信息 (截图/指纹)</li>
                                <li>Web 目录敏感信息单点提取 (WIH)</li>
                                <li>手动添加站点</li>
                                <li>任务数据强制同步重置</li>
                              </ul>
                            </div>
                          </template>
                          <InfoCircleOutlined style="margin-left: 4px; color: #888; cursor: pointer;" />
                        </a-popover>
                      </template>
                      <a-input-number v-model:value="performanceForm.celery_light_concurrency" :min="1" :max="256" style="width: 100%" />
                      <div style="margin-top: 8px; color: var(--arl-text-color); opacity: 0.45; font-size: 13px;">
                        走专用独立通道，不受重任务排队阻塞影响。可以根据带宽资源按需放大 (默认 2)。
                      </div>
                    </a-form-item>
                  </a-card>
                </a-col>
              </a-row>

            </a-form>
          </a-spin>
        </div>
      </a-tab-pane>

      <!-- 三方 API 配置 Tab -->
      <a-tab-pane key="api_config" tab="三方 API 配置" force-render>
        <div style="max-width: 1000px; padding-bottom: 40px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <span style="color: var(--arl-text-color); opacity: 0.45;">
              此处的配置项用于三方情报或搜索接口的 API 凭证管理，配置保存后将动态应用至对应的域名/资产收集任务。
            </span>
            <a-button type="primary" @click="saveGeneralConfig" :loading="generalSaveLoading">
              保存 API 配置
            </a-button>
          </div>
          
          <a-spin :spinning="generalLoading">
            <a-form layout="vertical">
              
              <!-- 1. 空间测绘情报 -->
              <a-card title="🌐 空间测绘情报 (FOFA)" size="small" style="margin-bottom: 16px; border-radius: 6px;">
                <a-row :gutter="24">
                  <a-col :span="12">
                    <a-form-item label="FOFA URL" style="margin-bottom: 12px;">
                      <a-input v-model:value="generalForm.fofa_url" placeholder="例如：https://fofa.info" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="FOFA KEY" style="margin-bottom: 12px;">
                      <a-input-password v-model:value="generalForm.fofa_key" placeholder="请输入您的 FOFA API KEY" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="最大查询页数 (Max Page)" style="margin-bottom: 0;">
                      <a-input-number v-model:value="generalForm.fofa_max_page" :min="1" style="width: 100%" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="每页条数 (Page Size)" style="margin-bottom: 0;">
                      <a-input-number v-model:value="generalForm.fofa_page_size" :min="1" style="width: 100%" />
                    </a-form-item>
                  </a-col>
                </a-row>
              </a-card>

              <a-row :gutter="16">
                <!-- 2. 企业与代码监控 (左半边) -->
                <a-col :span="12">
                  <a-card title="🏢 企业资产查询 (天眼查)" size="small" style="margin-bottom: 16px; border-radius: 6px; height: 190px;">
                    <a-form-item label="天眼查 ID (X-Tycid)" style="margin-bottom: 12px;">
                      <a-input v-model:value="generalForm.tyc_id" placeholder="请输入天眼查 ID" />
                    </a-form-item>
                    <a-form-item label="天眼查 Token (X-Auth-Token)" style="margin-bottom: 0;">
                      <a-input-password v-model:value="generalForm.tyc_token" placeholder="请输入 JWT Token" />
                    </a-form-item>
                  </a-card>
                </a-col>

                <!-- 3. 代码与搜索引擎 (右半边) -->
                <a-col :span="12">
                  <a-card title="🔍 搜索引擎 & 开源情报" size="small" style="margin-bottom: 16px; border-radius: 6px; height: 190px;">
                    <a-form-item label="GitHub Token (监控任务调用)" style="margin-bottom: 12px;">
                      <a-input-password v-model:value="generalForm.github_token" placeholder="请输入您的 GitHub PAT" />
                    </a-form-item>
                    <a-form-item label="360搜索 Cookie (反爬绕过)" style="margin-bottom: 0;">
                      <a-input-password v-model:value="generalForm.so_search_cookie" placeholder="so_search_cookie" />
                    </a-form-item>
                  </a-card>
                </a-col>
              </a-row>

              <!-- 单独一行放必应，如果上面放不下 -->
              <a-card size="small" style="margin-bottom: 16px; border-radius: 6px;">
                 <a-form-item label="必应搜索 Cookie (bing_search_cookie)" style="margin-bottom: 0;">
                   <a-input-password v-model:value="generalForm.bing_search_cookie" placeholder="请输入必应搜索 Cookie" />
                 </a-form-item>
              </a-card>

              <!-- 4. 插件配置 -->
              <a-card title="🧩 域名收集扩展插件配置 (QUERY_PLUGIN)" size="small" style="border-radius: 6px;">
                <div style="background: var(--arl-bg-light); border-radius: 4px; padding: 12px;">
                  <a-row :gutter="[12, 12]">
                    <a-col :span="8" v-for="(conf, pluginName) in generalForm.query_plugin_config" :key="pluginName">
                      <div style="border: 1px solid var(--arl-border-color); background: var(--arl-bg-white); padding: 12px; border-radius: 4px; min-height: 110px; position: relative;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                          <a style="font-weight: 600; text-transform: uppercase; ">{{ pluginName }}</a>
                          <a-switch v-model:checked="conf.enable" size="small" />
                        </div>
                        
                        <a-input 
                          v-if="conf.hasOwnProperty('api_key')" 
                          v-model:value="conf.api_key" 
                          placeholder="API Key" 
                          size="small" 
                        />
                        <div v-if="pluginName === 'hunter_qax'" style="margin-top: 8px; display: flex; gap: 8px;">
                          <a-input-number v-model:value="conf.max_page" placeholder="Max Page" size="small" style="flex: 1;" />
                          <a-input-number v-model:value="conf.page_size" placeholder="Page Size" size="small" style="flex: 1;" />
                        </div>
                        <div v-if="pluginName === 'certspotter'" style="margin-top: 8px;">
                          <a-input-number v-model:value="conf.max_page" placeholder="Max Page" size="small" style="width: 100%;" />
                        </div>
                        <a-input 
                          v-if="conf.hasOwnProperty('quake_token')" 
                          v-model:value="conf.quake_token" 
                          placeholder="Quake Token" 
                          size="small"
                          style="margin-top: 8px;"
                        />
                        <div v-if="pluginName === 'passivetotal'" style="margin-top: 8px; display: flex; flex-direction: column; gap: 8px;">
                          <a-input v-model:value="conf.auth_email" placeholder="Auth Email" size="small" />
                          <a-input v-model:value="conf.auth_key" placeholder="Auth Key" size="small" />
                        </div>
                      </div>
                    </a-col>
                  </a-row>
                </div>
              </a-card>

            </a-form>
          </a-spin>
        </div>
      </a-tab-pane>

      <!-- 消息推送与回调 Tab -->
      <a-tab-pane key="message_push" tab="消息推送与回调" force-render>
        <div style="max-width: 1100px; padding-bottom: 40px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <span style="color: var(--arl-text-color); opacity: 0.45;">
              此处的配置项用于监控任务结束后的结果推送以及自动化 Webhook 接口回调。
            </span>
            <a-button type="primary" @click="saveGeneralConfig" :loading="generalSaveLoading">
              保存推送配置
            </a-button>
          </div>

          <a-spin :spinning="generalLoading">
            <a-form layout="vertical">
              
              <!-- 1. 订阅消息类型 -->
              <a-card title="🔔 订阅消息类型" size="small" style="margin-bottom: 16px; border-radius: 6px; border-left: 4px solid var(--arl-theme-color);">
                <a-checkbox-group v-model:value="generalForm.push_options" style="width: 100%;">
                  <a-row>
                    <a-col :span="6" style="margin-bottom: 8px;"><a-checkbox value="task_complete">资产侦察任务完成</a-checkbox></a-col>
                    <a-col :span="6" style="margin-bottom: 8px;"><a-checkbox value="github_leak">GitHub 关键字告警</a-checkbox></a-col>
                    <a-col :span="6" style="margin-bottom: 8px;"><a-checkbox value="github_cve">GitHub CVE 更新</a-checkbox></a-col>
                    <a-col :span="6" style="margin-bottom: 8px;"><a-checkbox value="github_tools">GitHub 武器库更新</a-checkbox></a-col>
                    <a-col :span="6"><a-checkbox value="github_hackers">GitHub 黑客动态监控</a-checkbox></a-col>
                    <a-col :span="6"><a-checkbox value="asset_site">资产站点监控更新</a-checkbox></a-col>
                  </a-row>
                </a-checkbox-group>
              </a-card>

              <!-- 2. 即时通讯推送配置 (2列) -->
              <a-row :gutter="16">
                <!-- 钉钉 -->
                <a-col :span="12">
                  <a-card title="💬 钉钉机器人" size="small" style="margin-bottom: 16px; border-radius: 6px; height: 180px;">
                    <template #extra>
                      <a-button type="link" size="small" @click="handleTestPush('dingding')" :loading="testPushLoading.dingding">测试发送</a-button>
                    </template>
                    <a-row :gutter="12">
                      <a-col :span="12">
                        <a-form-item label="Access Token" style="margin-bottom: 0;">
                          <a-input v-model:value="generalForm.dingding.access_token" placeholder="钉钉 Token" size="small" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="12">
                        <a-form-item label="Secret (加签)" style="margin-bottom: 0;">
                          <a-input-password v-model:value="generalForm.dingding.secret" placeholder="钉钉 Secret" size="small" />
                        </a-form-item>
                      </a-col>
                    </a-row>
                  </a-card>
                </a-col>

                <!-- 飞书 -->
                <a-col :span="12">
                  <a-card title="🕊️ 飞书机器人" size="small" style="margin-bottom: 16px; border-radius: 6px; height: 180px;">
                    <template #extra>
                      <a-button type="link" size="small" @click="handleTestPush('feishu')" :loading="testPushLoading.feishu">测试发送</a-button>
                    </template>
                    <a-form-item label="Webhook URL" style="margin-bottom: 8px;">
                      <a-input v-model:value="generalForm.feishu.webhook_url" placeholder="飞书 Webhook 地址" size="small" />
                    </a-form-item>
                    <a-form-item label="Secret (加签)" style="margin-bottom: 0;">
                      <a-input-password v-model:value="generalForm.feishu.secret" placeholder="飞书 Secret" size="small" />
                    </a-form-item>
                  </a-card>
                </a-col>

                <!-- 企业微信 -->
                <a-col :span="12">
                  <a-card title="🏢 企业微信机器人" size="small" style="margin-bottom: 16px; border-radius: 6px; height: 180px;">
                    <template #extra>
                      <a-button type="link" size="small" @click="handleTestPush('wxwork')" :loading="testPushLoading.wxwork">测试发送</a-button>
                    </template>
                    <a-form-item label="Webhook URL" style="margin-bottom: 0;">
                      <a-input v-model:value="generalForm.wxwork.webhook_url" placeholder="企微 Webhook 地址" size="small" />
                    </a-form-item>
                  </a-card>
                </a-col>

                <!-- Telegram -->
                <a-col :span="12">
                  <a-card title="✈️ Telegram 机器人" size="small" style="margin-bottom: 16px; border-radius: 6px; height: 180px;">
                    <template #extra>
                      <a-button type="link" size="small" @click="handleTestPush('telegram')" :loading="testPushLoading.telegram">测试发送</a-button>
                    </template>
                    <a-row :gutter="12">
                      <a-col :span="12">
                        <a-form-item label="Bot Token" style="margin-bottom: 0;">
                          <a-input v-model:value="generalForm.telegram.bot_token" placeholder="Bot Token" size="small" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="12">
                        <a-form-item label="Chat ID" style="margin-bottom: 0;">
                          <a-input v-model:value="generalForm.telegram.chat_id" placeholder="接收方 Chat ID" size="small" />
                        </a-form-item>
                      </a-col>
                    </a-row>
                  </a-card>
                </a-col>
              </a-row>

              <!-- 3. Webhook & Email (较复杂的配置放下方) -->
              <a-row :gutter="16">
                <!-- 全局 Webhook -->
                <a-col :span="12">
                  <a-card title="🔗 系统全局 Webhook 回调" size="small" style="margin-bottom: 16px; border-radius: 6px; height: 260px;">
                    <template #extra>
                      <a-button type="link" size="small" @click="handleTestPush('webhook')" :loading="testPushLoading.webhook">测试发送</a-button>
                    </template>
                    <a-form-item label="回调 POST URL" style="margin-bottom: 12px;">
                      <a-input v-model:value="generalForm.webhook_url" placeholder="接收 JSON 数据的接口 URL" size="small" />
                    </a-form-item>
                    <a-form-item label="身份校验 Token (Header)" style="margin-bottom: 0;">
                      <a-input v-model:value="generalForm.webhook_token" placeholder="校验身份的 Token" size="small" />
                    </a-form-item>
                  </a-card>
                </a-col>

                <!-- SMTP 邮件 -->
                <a-col :span="12">
                  <a-card title="✉️ SMTP 邮件推送" size="small" style="margin-bottom: 16px; border-radius: 6px; height: 260px;">
                    <template #extra>
                      <a-button type="link" size="small" @click="handleTestPush('email')" :loading="testPushLoading.email">测试发送</a-button>
                    </template>
                    <a-row :gutter="12">
                      <a-col :span="16">
                        <a-form-item label="SMTP 主机" style="margin-bottom: 8px;">
                          <a-input v-model:value="generalForm.email.host" placeholder="smtp.qq.com" size="small" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="8">
                        <a-form-item label="端口" style="margin-bottom: 8px;">
                          <a-input-number v-model:value="generalForm.email.port" style="width: 100%;" size="small" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="12">
                        <a-form-item label="发件人 (Username)" style="margin-bottom: 8px;">
                          <a-input v-model:value="generalForm.email.username" placeholder="发信账号" size="small" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="12">
                        <a-form-item label="授权码 (Password)" style="margin-bottom: 8px;">
                          <a-input-password v-model:value="generalForm.email.password" placeholder="授权密码" size="small" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="24">
                        <a-form-item label="收件人 (To, 多个用逗号分隔)" style="margin-bottom: 0;">
                          <a-input v-model:value="generalForm.email.to" placeholder="receiver@test.com" size="small" />
                        </a-form-item>
                      </a-col>
                    </a-row>
                  </a-card>
                </a-col>
              </a-row>

            </a-form>
          </a-spin>
        </div>
      </a-tab-pane>

      <!-- 高级扫描与环境配置 Tab -->
      <a-tab-pane key="system_general" tab="高级扫描与环境配置" force-render>
        <div style="max-width: 1000px; padding-bottom: 40px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <span style="color: var(--arl-text-color); opacity: 0.45;">
              此处的配置项用于代理、全局端口字典及扫描线程的调优。底部只读展示系统底层关键连接。
            </span>
            <a-button type="primary" @click="saveGeneralConfig" :loading="generalSaveLoading">
              保存高级配置
            </a-button>
          </div>
          <a-spin :spinning="generalLoading">
            <a-form layout="vertical">
              <a-row :gutter="24">
                <a-col :span="12">
                  <a-form-item label="系统代理地址 (PROXY HTTP_URL)">
                    <a-input v-model:value="generalForm.proxy_url" placeholder="例如：http://127.0.0.1:8080" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="端口扫描前端测试选项 Top 10 WEB 端口串">
                    <a-input v-model:value="generalForm.port_top_10" placeholder="以英文逗号分隔" />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-row :gutter="24">
                <a-col :span="12">
                  <a-form-item label="常规域名爆破并行线程数">
                    <a-input-number v-model:value="generalForm.domain_brute_concurrent" :min="1" style="width: 100%" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="DNS智能生成并发并行线程数">
                    <a-input-number v-model:value="generalForm.alt_dns_concurrent" :min="1" style="width: 100%" />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-row :gutter="24">
                <a-col :span="12">
                  <a-form-item label="文件泄露字典路径 (FILE_LEAK_DICT)">
                    <a-input v-model:value="generalForm.file_leak_dict" placeholder="字典文件绝对路径" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="域名爆破默认大字典路径 (DOMAIN_DICT)">
                    <a-input v-model:value="generalForm.domain_dict" placeholder="字典文件绝对路径" />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-row :gutter="24">
                <a-col :span="12">
                  <a-form-item label="API 安全认证机制">
                    <a-switch v-model:checked="generalForm.auth" checked-children="开启" un-checked-children="关闭" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="API Token (Swagger API Key)">
                    <a-input-password v-model:value="generalForm.api_key" placeholder="API KEY (不带 API 认证时无须配置)" />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-form-item label="底层系统基础设施服务连接信息 (只读)">
                <div style="background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); border-radius: 4px; padding: 16px;">
                  <a-descriptions bordered size="small" :column="1">
                    <a-descriptions-item label="Celery 消息队列 (Broker URL)">
                      <code style="word-break: break-all;">{{ generalForm.celery_broker_url }}</code>
                    </a-descriptions-item>
                    <a-descriptions-item label="MongoDB 数据库 (URI)">
                      <code style="word-break: break-all;">{{ generalForm.mongo_url }}</code>
                    </a-descriptions-item>
                    <a-descriptions-item label="MongoDB 默认数据库名 (DB)">
                      <code>{{ generalForm.mongo_db }}</code>
                    </a-descriptions-item>
                    <a-descriptions-item label="GeoIP 城市位置库绝对路径">
                      <code style="word-break: break-all;">{{ generalForm.geoip_city }}</code>
                    </a-descriptions-item>
                    <a-descriptions-item label="GeoIP ASN数据绝对路径">
                      <code style="word-break: break-all;">{{ generalForm.geoip_asn }}</code>
                    </a-descriptions-item>
                  </a-descriptions>
                </div>
              </a-form-item>
            </a-form>
          </a-spin>
        </div>
      </a-tab-pane>
      <a-tab-pane key="system_update" tab="系统版本与更新" force-render>
        <div class="tab-content" style="padding: 20px;">
          <a-card title="系统更新管理" :bordered="false" style="max-width: 800px;">
            <a-descriptions bordered :column="1">
              <a-descriptions-item label="当前本地版本">
                <a-tag color="blue">{{ localVersion || '获取中...' }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="最新可用版本">
                <a-tag :color="hasNewVersion ? 'red' : 'green'">{{ remoteVersion || '获取中...' }}</a-tag>
                <span v-if="hasNewVersion" style="margin-left: 10px; color: #f5222d; font-weight: bold;">
                  发现新版本！建议立即更新。
                </span>
                <span v-else-if="remoteVersion" style="margin-left: 10px; color: #52c41a;">
                  已是最新版本。
                </span>
              </a-descriptions-item>
              <a-descriptions-item v-if="hasNewVersion" label="更新日志" style="white-space: pre-wrap;">
                {{ releaseNotes }}
              </a-descriptions-item>
            </a-descriptions>
            
            <div style="margin-top: 20px; text-align: center;">
              <a-popconfirm title="此操作将拉取最新镜像并重启系统容器，大概需要几分钟时间，请确认当前无正在执行的重要任务。确定执行更新吗？" @confirm="startUpdate">
                <a-button type="primary" size="large" danger :loading="updateButtonLoading" :disabled="!hasNewVersion && !forceUpdateMode">
                  一键系统更新
                </a-button>
              </a-popconfirm>
              <div style="margin-top: 10px;">
                <a-checkbox v-model:checked="forceUpdateMode">强制显示更新按钮</a-checkbox>
              </div>
            </div>
          </a-card>
        </div>
      </a-tab-pane>
    </a-tabs>

    <!-- 系统更新日志 Modal -->
    <a-modal v-model:open="updateModalVisible" title="系统更新中，请勿关闭页面" :closable="false" :maskClosable="false" :footer="null" width="800px">
      <div style="margin-bottom: 15px;">
        <a-progress :percent="updateProgress" :status="updateHasError ? 'exception' : (updateFinished ? 'success' : 'active')" />
      </div>
      <div style="background-color: #1e1e1e; color: #00ff00; padding: 15px; border-radius: 4px; font-family: 'Consolas', 'Courier New', monospace; height: 400px; overflow-y: auto;" ref="terminalRef">
        <pre style="margin: 0; white-space: pre-wrap; font-family: inherit; color: inherit; background: transparent; border: none; padding: 0;">{{ updateLogs }}</pre>
      </div>
      <div v-if="updateFinished" style="margin-top: 15px; text-align: center;">
        <a-button v-if="!updateHasError" type="primary" size="large" @click="reloadPage">🎉 更新完成，点击重新加载页面</a-button>
        <a-button v-else type="default" size="large" @click="updateModalVisible = false">关闭窗口</a-button>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { InfoCircleOutlined, ThunderboltOutlined } from '@ant-design/icons-vue';
import { ref, reactive, onMounted, onUnmounted, computed, nextTick } from 'vue';
import { message } from 'ant-design-vue';
import request from '@/utils/request';
import { useRoute } from 'vue-router';

const reloadPage = () => {
  window.location.reload();
};

const route = useRoute();
const activeKey = ref('dictionary');
const loading = ref(false);
const searchLoading = ref(false);
const submitLoading = ref(false);
const deleteLoading = ref(false);

const menuSearch = ref('');
const menuOpenKeys = ref([]);
const appendDrawerVisible = ref(false);
const searchDrawerVisible = ref(false);
const batchDeleteEntries = ref('');

import { watch } from 'vue';

const generalLoading = ref(false);
const generalSaveLoading = ref(false);
const activePushPanels = ref(['dingding', 'feishu', 'wxwork', 'telegram', 'email', 'webhook']);

const testPushLoading = reactive({
  dingding: false,
  feishu: false,
  wxwork: false,
  telegram: false,
  email: false,
  webhook: false
});

const handleTestPush = async (type) => {
  let config = {};
  if (type === 'webhook') {
    config = {
      webhook_url: generalForm.value.webhook_url,
      webhook_token: generalForm.value.webhook_token
    };
  } else {
    config = generalForm.value[type];
  }
  
  testPushLoading[type] = true;
  try {
    const res = await request.post('/api/system_config/test_push', {
      push_type: type,
      config: config
    });
    
    if (res.code === 200) {
      message.success(res.message || '测试推送成功');
    } else {
      message.error(res.message || '测试推送失败');
    }
  } catch (error) {
    message.error('测试请求发生异常，请检查网络');
    console.error(error);
  } finally {
    testPushLoading[type] = false;
  }
};

const generalForm = ref({
  celery_broker_url: '',
  mongo_url: '',
  mongo_db: '',
  geoip_city: '',
  geoip_asn: '',
  
  fofa_key: '',
  fofa_url: '',
  fofa_max_page: 5,
  fofa_page_size: 2000,
  github_token: '',
  tyc_id: '',
  tyc_token: '',
  so_search_cookie: '',
  bing_search_cookie: '',
  
  proxy_url: '',
  port_top_10: '',
  domain_brute_concurrent: 300,
  alt_dns_concurrent: 1500,
  
  file_leak_dict: '',
  domain_dict: '',
  
  auth: false,
  api_key: '',
  
  webhook_url: '',
  webhook_token: '',
  
  dingding: { secret: '', access_token: '' },
  feishu: { webhook_url: '', secret: '' },
  wxwork: { webhook_url: '' },
  telegram: { bot_token: '', chat_id: '' },
  email: { host: '', port: 465, username: '', password: '', to: '' },
  query_plugin_config: {},
  push_options: ['task_complete', 'github_leak', 'github_cve', 'github_tools', 'github_hackers', 'asset_site']
});

const fetchGeneralConfig = async () => {
  generalLoading.value = true;
  try {
    const res = await request.get('/api/system_config/general');
    if (res.code === 200) {
      // 深度合并防止旧数据结构缺失导致报错
      generalForm.value = {
        ...generalForm.value,
        ...res.data,
        dingding: { ...generalForm.value.dingding, ...(res.data.dingding || {}) },
        feishu: { ...generalForm.value.feishu, ...(res.data.feishu || {}) },
        wxwork: { ...generalForm.value.wxwork, ...(res.data.wxwork || {}) },
        telegram: { ...generalForm.value.telegram, ...(res.data.telegram || {}) },
        email: { ...generalForm.value.email, ...(res.data.email || {}) }
      };
    } else {
      message.error(res.message || '获取常规全局配置失败');
    }
  } catch (error) {
    message.error('请求常规全局配置出错');
    console.error(error);
  } finally {
    generalLoading.value = false;
  }
};

const saveGeneralConfig = async () => {
  generalSaveLoading.value = true;
  try {
    const res = await request.post('/api/system_config/general', generalForm.value);
    if (res.code === 200) {
      message.success('系统全局配置保存成功！');
    } else {
      message.error(res.message || '保存常规全局配置失败');
    }
  } catch (error) {
    message.error('请求保存全局配置出错');
    console.error(error);
  } finally {
    generalSaveLoading.value = false;
  }
};

const dictList = ref([]);
const selectedDict = ref(null);
const bruteLoading = ref(false);
const bruteDictList = ref([]);  // [{name, size}, ...]

// ======================= 字典元数据配置 =======================
const ASSET_DICT_META = {
  'domain_2w.txt':       { label: '子域名爆破主字典 (2万)', group: '📍 子域名发现模块调用' },
  'altdnsdict.txt':      { label: '子域名智能生成辅助词',   group: '📍 子域名发现模块调用' },
  'dnsserver.txt':       { label: 'DNS 解析服务器列表',     group: '📍 子域名发现模块调用' },
  'file_top_200.txt':    { label: 'Top 200 路径字典',       group: '📍 目录与文件泄露扫描调用' },
  'file_top_2000.txt':   { label: 'Top 2000 路径字典',      group: '📍 目录与文件泄露扫描调用' },
  'file_test.txt':       { label: '测试路径字典',           group: '📍 目录与文件泄露扫描调用' },
  'port_top100.txt':     { label: '常用 100 端口',          group: '📍 端口扫描策略调用' },
  'port_top1000.txt':    { label: '常用 1000 端口',         group: '📍 端口扫描策略调用' },
  'port_custom.txt':     { label: '自定义端口',             group: '📍 端口扫描策略调用' },
  'port_all.txt':        { label: '全端口 (1-65535)',       group: '📍 端口扫描策略调用' },
  'port_test.txt':       { label: '测试端口',               group: '📍 端口扫描策略调用' },
  'blackdomain.txt':     { label: '根域名爆破拦截字典',     group: '🛡️ 系统全局黑名单拦截' },
  'black_asset_site.txt':{ label: '恶意/干扰站点拦截字典',  group: '🛡️ 系统全局黑名单拦截' },
  'blackhexie.txt':      { label: '敏感词汇过滤字典',       group: '🛡️ 系统全局黑名单拦截' },
};

// 资产字典按调用方/使用地点分组
const assetMenuGroups = computed(() => {
  const groups = { '📍 子域名发现模块调用': [], '📍 目录与文件泄露扫描调用': [], '📍 端口扫描策略调用': [], '🛡️ 系统全局黑名单拦截': [], '其他（未分类调用）': [] };
  dictList.value.forEach(dict => {
    const meta = ASSET_DICT_META[dict.name];
    const g = meta ? meta.group : '其他（未分类调用）';
    if (!groups[g]) groups[g] = [];
    // 覆盖默认的 name 为更友好的 label，如果没有则显示原名
    groups[g].push({
      ...dict,
      title: meta ? meta.label : dict.name
    });
  });
  return groups;
});

// 弱口令字典：按服务名分组（提取 username_ssh.txt → SSH）
const bruteSvcGroups = computed(() => {
  const groups = {};
  const SVC_LABEL = {
    ssh: 'SSH', ftp: 'FTP', mysql: 'MySQL', redis: 'Redis', mongodb: 'MongoDB',
    postgresql: 'PostgreSQL', sqlserver: 'SQL Server', rdp: 'RDP',
    tomcat: 'Tomcat', jenkins: 'Jenkins', gitlab: 'GitLab', grafana: 'Grafana',
    harbor: 'Harbor', nexus: 'Nexus', nacos: 'Nacos', apisix: 'APISIX',
    activemq: 'ActiveMQ', openfire: 'OpenFire', manageiq: 'ManageIQ',
    shiro: 'Shiro Key', imap: 'IMAP', pop3: 'POP3', smtp: 'SMTP',
    exchange: 'Exchange', csts: 'CSTS', clickhouse: 'ClickHouse',
    'alibaba-druid': 'Alibaba Druid'
  };
  bruteDictList.value.forEach(item => {
    const m = item.name.match(/^(?:username|password)_(.+)\.txt$/);
    if (!m) return;
    const svcKey = m[1];
    const svc = SVC_LABEL[svcKey] || svcKey.toUpperCase();
    if (!groups[svc]) groups[svc] = [];
    // username_* 排前面
    if (item.name.startsWith('username_')) groups[svc].unshift(item);
    else groups[svc].push(item);
  });
  return groups;
});

const treeData = computed(() => {
  const data = [];
  // 资产字典分组
  Object.entries(assetMenuGroups.value).forEach(([group, items]) => {
    if (items.length) {
      const children = items.map(item => {
        const friendly = item.title && item.title !== item.name ? item.title : item.name;
        return {
          mainTitle: friendly,
          subTitle: item.name,
          key: `asset__${item.name}`,
        };
      });
      data.push({ title: group, key: `group_asset_${group}`, selectable: false, children });
    }
  });
  // 弱口令字典分组（将所有协议合并到一个大组，极大提升简洁度）
  const npocChildren = [];
  Object.entries(bruteSvcGroups.value).forEach(([svc, items]) => {
    if (items.length) {
      items.forEach(item => {
        // 自动将 username_/password_ 翻译为友好的中文前缀
        let friendlyPrefix = '';
        if (item.name.startsWith('username_')) friendlyPrefix = '账号字典';
        else if (item.name.startsWith('password_')) friendlyPrefix = '密码字典';
        else if (item.name.includes('common_')) friendlyPrefix = '通用弱口令';
        
        npocChildren.push({
          mainTitle: `[${svc}] ${friendlyPrefix || item.name}`,
          subTitle: item.name,
          key: `brute__${item.name}`,
        });
      });
    }
  });
  if (npocChildren.length > 0) {
    data.push({ title: '🔑 NPoC 弱口令爆破', key: 'group_brute_all', selectable: false, children: npocChildren });
  }
  return data;
});

const filteredTreeData = computed(() => {
  if (!menuSearch.value.trim()) return treeData.value;
  const kw = menuSearch.value.toLowerCase();
  return treeData.value.map(group => {
    const matchedChildren = group.children.filter(c => 
      (c.mainTitle && c.mainTitle.toLowerCase().includes(kw)) || 
      (c.subTitle && c.subTitle.toLowerCase().includes(kw))
    );
    return { ...group, children: matchedChildren };
  }).filter(group => group.children.length > 0);
});

watch(treeData, (newVal) => {
  if (menuOpenKeys.value.length === 0 && newVal.length > 0) {
    menuOpenKeys.value = newVal.map(g => g.key);
  }
}, { immediate: true });

const handleUnifiedMenuSelect = ({ key }) => {
  handleUnifiedSelect([key]);
};

const handleAppendAndClose = async () => {
  await handleAppend();
  appendDrawerVisible.value = false;
};

const handleDeleteBatchCustom = async () => {
  newEntries.value = batchDeleteEntries.value;
  await handleDeleteBatch();
  batchDeleteEntries.value = '';
};

// 统一字典选择状态
const unifiedSelectedKeys = ref([]);
const unifiedSelectedType = ref('');  // 'asset' | 'brute'
const unifiedSelectedName = ref('');
const unifiedSelectedDesc = ref('');

const handleUnifiedSelect = (selectedKeys, info) => {
  console.log('handleUnifiedSelect called', selectedKeys, info);
  const key = Array.isArray(selectedKeys) ? selectedKeys[0] : selectedKeys;
  console.log('selected key resolved', key);
  unifiedSelectedKeys.value = [key];
  searchKeyword.value = '';
  searchResult.value = null;
  newEntries.value = '';
  previewContent.value = '';
  totalLines.value = 0;
  if (key && key.startsWith('asset__')) {
    const name = key.slice(7);
    unifiedSelectedType.value = 'asset';
    unifiedSelectedName.value = name;
    unifiedSelectedDesc.value = ASSET_DICT_META[name] ? ASSET_DICT_META[name].label : '资产发现字典';
    selectedDict.value = name;
    fetchPreview(name);
  } else if (key && key.startsWith('brute__')) {
    const name = key.slice(7);
    unifiedSelectedType.value = 'brute';
    unifiedSelectedName.value = name;
    unifiedSelectedDesc.value = name.startsWith('username_') ? '账号字典（用于弱口令爆破）' : '密码字典（用于弱口令爆破）';
    selectedDict.value = name;
    fetchPreview(name);
  } else {
    unifiedSelectedType.value = '';
    unifiedSelectedName.value = '';
    unifiedSelectedDesc.value = '';
    selectedDict.value = null;
  }
};

const previewContent = ref('');
const totalLines = ref(0);
const previewLimit = ref(500);

const searchKeyword = ref('');
const searchResult = ref(null);

const newEntries = ref('');

// 根据当前选中类型返回 API 前缀
const dictApiBase = computed(() =>
  unifiedSelectedType.value === 'brute' ? '/api/brute_dict' : '/api/dictionary'
);

// 获取字典列表
const fetchDictList = async () => {
  loading.value = true;
  try {
    const res = await request.get('/api/dictionary/list');
    if (res.code === 200) {
      dictList.value = res.data || [];
    } else {
      message.error(res.message || '获取字典列表失败');
    }
  } catch (error) {
    message.error('请求字典列表出错');
    console.error(error);
  } finally {
    loading.value = false;
  }
};

// 获取预览（自动路由到对应 API）
const fetchPreview = async (name) => {
  if (!name) return;
  loading.value = true;
  try {
    const res = await request.get(`${dictApiBase.value}/preview`, {
      params: { name, limit: previewLimit.value }
    });
    if (res.code === 200) {
      previewContent.value = res.data.lines.join('\n');
      totalLines.value = res.data.total;
    } else {
      message.error(res.message || '获取预览失败');
    }
  } catch (error) {
    message.error('请求预览内容出错');
    console.error(error);
  } finally {
    loading.value = false;
  }
};

// 搜索功能（自动路由）
const handleSearch = async () => {
  if (!searchKeyword.value.trim()) {
    message.warning('请输入搜索关键词');
    return;
  }
  searchLoading.value = true;
  try {
    const res = await request.get(`${dictApiBase.value}/search`, {
      params: { name: selectedDict.value, keyword: searchKeyword.value }
    });
    if (res.code === 200) {
      searchResult.value = res.data.matches;
      if (res.data.matches.length > 0) {
        message.success(`找到 ${res.data.matches.length} 条匹配项！`);
      } else {
        message.info('未找到包含该关键词的条目。');
      }
    } else {
      message.error(res.message || '搜索失败');
    }
  } catch (error) {
    message.error('请求搜索出错');
    console.error(error);
  } finally {
    searchLoading.value = false;
  }
};

// 追加条目（自动路由）
const handleAppend = async () => {
  if (!newEntries.value.trim()) return;
  
  // 智能格式校验（阻断无效输入）
  const lines = newEntries.value.split('\n').map(s => s.trim()).filter(s => s);
  if (selectedDict.value && selectedDict.value.startsWith('port_')) {
    const invalidPorts = lines.filter(p => !/^\d+$/.test(p) || parseInt(p) < 1 || parseInt(p) > 65535);
    if (invalidPorts.length > 0) {
      message.error(`校验失败：包含无效端口号 (如 ${invalidPorts[0]})，请输入 1-65535 之间的纯数字`);
      return;
    }
  } else if (selectedDict.value && selectedDict.value.includes('domain')) {
    const invalidDomains = lines.filter(d => /[\s,;!@#%^&*()<>{}\[\]]/.test(d));
    if (invalidDomains.length > 0) {
       message.error(`校验失败：子域名字典包含非法字符 (如空格或特殊符号)`);
       return;
    }
  }

  submitLoading.value = true;
  try {
    const res = await request.post(`${dictApiBase.value}/append`, {
      name: selectedDict.value,
      content: newEntries.value
    });
    if (res.code === 200) {
      message.success(`保存成功！共提交 ${res.data.total_submitted} 项，实际追加新条目 ${res.data.added} 项。`);
      newEntries.value = '';
      fetchDictList();
      fetchBruteDictList();
      fetchPreview(selectedDict.value);
    } else {
      message.error(res.message || '保存失败');
    }
  } catch (error) {
    message.error('请求保存出错');
    console.error(error);
  } finally {
    submitLoading.value = false;
  }
};

// 批量删除
const handleDeleteBatch = async () => {
  if (!newEntries.value.trim()) return;
  await deleteEntries(newEntries.value);
};

// 单条删除
const handleDeleteSingle = async (item) => {
  if (!item) return;
  await deleteEntries(item);
  if (searchResult.value) {
    searchResult.value = searchResult.value.filter(x => x !== item);
  }
};

// 公共删除逻辑（自动路由）
const deleteEntries = async (content) => {
  deleteLoading.value = true;
  try {
    const res = await request.post(`${dictApiBase.value}/delete_entries`, {
      name: selectedDict.value,
      content: content
    });
    if (res.code === 200) {
      message.success(`删除成功！尝试删除 ${res.data.total_submitted} 项，实际成功删除 ${res.data.deleted} 项。`);
      newEntries.value = '';
      fetchDictList();
      fetchBruteDictList();
      fetchPreview(selectedDict.value);
    } else {
      message.error(res.message || '删除失败');
    }
  } catch (error) {
    message.error('请求删除出错');
    console.error(error);
  } finally {
    deleteLoading.value = false;
  }
};

// ======================= CDN 管理逻辑 =======================
const cdnList = ref([]);
const cdnLoading = ref(false);
const cdnSaveLoading = ref(false);

const cdnColumns = [
  { title: '名称', dataIndex: 'name', key: 'name', width: '20%' },
  { title: 'CNAME域名', dataIndex: 'cname_domain', key: 'cname_domain', width: '35%' },
  { title: 'IP网段', dataIndex: 'ip_cidr', key: 'ip_cidr', width: '30%' },
  { title: '操作', key: 'action', width: '15%' }
];

const cdnModalVisible = ref(false);
const isEditingCdn = ref(false);
const currentEditIndex = ref(-1);
const currentCdnForm = ref({ name: '', cnameText: '', ipText: '' });

// 拉取 CDN 列表
const fetchCdnList = async () => {
  cdnLoading.value = true;
  try {
    const res = await request.get('/api/cdn_dict/list');
    if (res.code === 200) {
      cdnList.value = res.data || [];
    } else {
      message.error(res.message || '获取CDN列表失败');
    }
  } catch (error) {
    message.error('请求CDN列表出错');
    console.error(error);
  } finally {
    cdnLoading.value = false;
  }
};

// 打开新增/编辑弹窗
const openCdnModal = (record = null, index = -1) => {
  if (record) {
    isEditingCdn.value = true;
    currentEditIndex.value = index;
    currentCdnForm.value = {
      name: record.name || '',
      cnameText: (record.cname_domain || []).join('\n'),
      ipText: (record.ip_cidr || []).join('\n')
    };
  } else {
    isEditingCdn.value = false;
    currentEditIndex.value = -1;
    currentCdnForm.value = { name: '', cnameText: '', ipText: '' };
  }
  cdnModalVisible.value = true;
};

// 提交本地编辑
const submitCdnModal = () => {
  if (!currentCdnForm.value.name.trim()) {
    message.warning('请输入CDN名称');
    return;
  }
  
  const cname_domain = currentCdnForm.value.cnameText.split('\n').map(s => s.trim()).filter(s => s);
  const ip_cidr = currentCdnForm.value.ipText.split('\n').map(s => s.trim()).filter(s => s);
  
  const newItem = {
    name: currentCdnForm.value.name.trim(),
    cname_domain,
    ip_cidr
  };
  
  if (isEditingCdn.value && currentEditIndex.value > -1) {
    cdnList.value.splice(currentEditIndex.value, 1, newItem);
  } else {
    cdnList.value.push(newItem);
  }
  
  cdnModalVisible.value = false;
  message.info('本地修改成功，请记得点击【保存全量更改到服务器】');
};

// 删除单条 CDN 记录
const deleteCdnItem = (index) => {
  cdnList.value.splice(index, 1);
  message.info('本地删除成功，请记得点击【保存全量更改到服务器】');
};

// 保存全量数据到服务器
const saveCdnData = async () => {
  cdnSaveLoading.value = true;
  try {
    const res = await request.post('/api/cdn_dict/save', {
      data: cdnList.value
    });
    if (res.code === 200) {
      message.success('全量保存成功！');
      fetchCdnList(); // 重新拉取确认
    } else {
      message.error(res.message || '保存失败');
    }
  } catch (error) {
    message.error('请求保存出错');
    console.error(error);
  } finally {
    cdnSaveLoading.value = false;
  }
};

// CDN 一键导入
const handleCdnImport = (options) => {
  const { file, onSuccess, onError } = options;
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const importedData = JSON.parse(e.target.result);
      if (Array.isArray(importedData)) {
        cdnList.value = [...cdnList.value, ...importedData];
        message.success(`成功导入 ${importedData.length} 条数据，请确认后点击【保存全量更改到服务器】`);
        onSuccess(null, file);
      } else {
        message.error('文件格式错误，应为 JSON 数组');
        onError(new Error('Format error'));
      }
    } catch (err) {
      message.error('解析 JSON 失败');
      onError(err);
    }
  };
  reader.onerror = (err) => {
    message.error('读取文件失败');
    onError(err);
  };
  reader.readAsText(file);
};

// ======================= 安全策略管理逻辑 =======================
const securityForm = ref({ blackIpsText: '', forbiddenDomainsText: '' });
const securityLoading = ref(false);
const securitySaveLoading = ref(false);

const fetchSecurityPolicy = async () => {
  securityLoading.value = true;
  try {
    const res = await request.get('/api/system_config/security_policy');
    if (res.code === 200) {
      securityForm.value.blackIpsText = (res.data.black_ips || []).join('\n');
      securityForm.value.forbiddenDomainsText = (res.data.forbidden_domains || []).join('\n');
    } else {
      message.error(res.message || '获取安全策略失败');
    }
  } catch (error) {
    message.error('请求安全策略出错');
    console.error(error);
  } finally {
    securityLoading.value = false;
  }
};

const saveSecurityPolicy = async () => {
  securitySaveLoading.value = true;
  try {
    const black_ips = securityForm.value.blackIpsText.split('\n').map(s => s.trim()).filter(s => s);
    const forbidden_domains = securityForm.value.forbiddenDomainsText.split('\n').map(s => s.trim()).filter(s => s);

    const res = await request.post('/api/system_config/security_policy', {
      black_ips,
      forbidden_domains
    });
    
    if (res.code === 200) {
      message.success('安全策略更新成功！');
      fetchSecurityPolicy(); // 重新拉取确认
    } else {
      message.error(res.message || '保存失败');
    }
  } catch (error) {
    message.error('请求保存安全策略出错');
    console.error(error);
  } finally {
    securitySaveLoading.value = false;
  }
};

// ======================= 性能配置管理逻辑 =======================
const performanceForm = ref({ celery_heavy_concurrency: 2, celery_light_concurrency: 2 });
const performanceLoading = ref(false);
const performanceSaveLoading = ref(false);

const fetchPerformanceConfig = async () => {
  performanceLoading.value = true;
  try {
    const res = await request.get('/api/system_config/performance');
    if (res.code === 200) {
      performanceForm.value.celery_heavy_concurrency = res.data.celery_heavy_concurrency || 2;
      performanceForm.value.celery_light_concurrency = res.data.celery_light_concurrency || 3;
    } else {
      message.error(res.message || '获取性能配置失败');
    }
  } catch (error) {
    message.error('请求性能配置出错');
    console.error(error);
  } finally {
    performanceLoading.value = false;
  }
};

const savePerformanceConfig = async () => {
  performanceSaveLoading.value = true;
  try {
    const res = await request.post('/api/system_config/performance', {
      celery_heavy_concurrency: performanceForm.value.celery_heavy_concurrency,
      celery_light_concurrency: performanceForm.value.celery_light_concurrency
    });
    
    if (res.code === 200) {
      message.success(res.message || '性能配置更新成功！');
      fetchPerformanceConfig();
    } else {
      message.error(res.message || '保存失败');
    }
  } catch (error) {
    message.error('请求保存性能配置出错');
    console.error(error);
  } finally {
    performanceSaveLoading.value = false;
  }
};

// ======================= 弱口令字典管理逻辑 =======================
// (Moved bruteLoading and bruteDictList to the top to avoid TDZ)

const fetchBruteDictList = async () => {
  bruteLoading.value = true;
  try {
    const res = await request.get('/api/brute_dict/list');
    if (res.code === 200) {
      bruteDictList.value = res.data || [];
    } else {
      message.error(res.message || '获取弱口令字典列表失败');
    }
  } catch (error) {
    message.error('请求弱口令字典列表出错');
    console.error(error);
  } finally {
    bruteLoading.value = false;
  }
};

const localVersion = ref('');
const remoteVersion = ref('');
const releaseNotes = ref('');
const hasNewVersion = ref(false);
const forceUpdateMode = ref(false);

const updateModalVisible = ref(false);
const updateLogs = ref('');
const updateProgress = ref(0);
const updateFinished = ref(false);
const terminalRef = ref(null);
const updateButtonLoading = ref(false);
const updateHasError = ref(false);
const updateOfflineNotices = ref('');
const updatePollInterval = ref(null);

const checkVersion = async () => {
  try {
    const res = await request.get('/api/system_config/local_version');
    if (res.code === 200) {
      localVersion.value = res.data.version;
    }
    
    // 提取并复用检查版本大小的方法
    const isGreater = (v1, v2) => {
      const cleanV1 = v1.replace(/^v/, '');
      const cleanV2 = v2.replace(/^v/, '');
      
      const [base1, suffix1] = cleanV1.split('-');
      const [base2, suffix2] = cleanV2.split('-');
      
      const parts1 = base1.split('.').map(Number);
      const parts2 = base2.split('.').map(Number);
      
      for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
        const num1 = parts1[i] || 0;
        const num2 = parts2[i] || 0;
        if (num1 > num2) return true;
        if (num1 < num2) return false;
      }
      
      // 基础版本号相同，比较后缀
      if (suffix1 && !suffix2) return true;
      if (!suffix1 && suffix2) return false;
      
      if (suffix1 && suffix2) {
        const num1 = parseInt((suffix1.match(/\d+/) || [0])[0], 10);
        const num2 = parseInt((suffix2.match(/\d+/) || [0])[0], 10);
        if (num1 !== num2) return num1 > num2;
        return suffix1 > suffix2;
      }
      
      return false;
    };

    const ghRes = await fetch('https://api.github.com/repos/owl234/ARL-Next/tags');
    if (ghRes.ok) {
      const ghData = await ghRes.json();
      if (ghData && ghData.length > 0) {
        // 对 API 返回的标签使用 isGreater 进行降序排序
        ghData.sort((a, b) => isGreater(a.name, b.name) ? -1 : (isGreater(b.name, a.name) ? 1 : 0));
        
        remoteVersion.value = ghData[0].name;
        
        // 获取该 tag 对应的 commit 以提取更新日志 (Commit Message)
        const commitUrl = ghData[0].commit.url;
        if (commitUrl) {
          const commitRes = await fetch(commitUrl);
          if (commitRes.ok) {
            const commitData = await commitRes.json();
            releaseNotes.value = commitData.commit.message;
          }
        }
      }
    }
      
    if (localVersion.value && localVersion.value !== '未知版本' && remoteVersion.value) {
      hasNewVersion.value = isGreater(remoteVersion.value, localVersion.value);
    }
  } catch (e) {
    console.error('检查版本失败', e);
  }
};

const startUpdate = async () => {
  if (updateButtonLoading.value) return;
  updateButtonLoading.value = true;
  try {
    const res = await request.post('/api/system_config/request_update_token');
    if (res.code !== 200) {
      message.error(res.message || '获取更新令牌失败');
      updateButtonLoading.value = false;
      return;
    }
    const token = res.data.token;
    
    updateModalVisible.value = true;
    updateHasError.value = false;
    updateOfflineNotices.value = '';
    updateLogs.value = '⏳ 正在触发更新服务...\n';
    updateProgress.value = 10;
    updateFinished.value = false;
    updateButtonLoading.value = false;
    
    // 1. 触发更新
    const triggerUrl = `/update_stream/trigger?token=${token}`;
    try {
      const triggerRes = await fetch(triggerUrl);
      if (!triggerRes.ok) {
        updateLogs.value += '[ERROR] 触发更新失败，服务返回异常状态码。\n';
        updateFinished.value = true;
        updateHasError.value = true;
        return;
      }
    } catch (e) {
      updateLogs.value += '[ERROR] 无法连接到更新服务，请检查网络。\n';
      updateFinished.value = true;
      updateHasError.value = true;
      return;
    }

    // 2. 开始轮询日志
    const pollUrl = `/update_stream/log`;
    updatePollInterval.value = setInterval(async () => {
      try {
        const logRes = await fetch(pollUrl);
        if (!logRes.ok) {
          if (logRes.status === 401) {
            clearInterval(updatePollInterval.value);
            updateProgress.value = 100;
            updateFinished.value = true;
            updateLogs.value += '\n[DONE] 🎉 系统更新成功！\n🔒 检测到基础安全防护 (Basic Auth) 已生效。\n👉 请手动刷新页面，并在弹出的提示框中输入密码重新登录。';
            scrollToBottom();
            message.success('🎉 系统更新成功！请手动刷新页面。', 8);
            return;
          }
          // 502 可能是网关重启，不报错，仅记录
          if (!updateOfflineNotices.value.includes('等待网络恢复')) {
            updateOfflineNotices.value += '⏳ 网关重启中或服务暂时不可达，正在等待网络恢复...\n';
            updateLogs.value += '⏳ 网关重启中或服务暂时不可达，正在等待网络恢复...\n';
            scrollToBottom();
          }
          return;
        }
        const logText = await logRes.text();
        
        // 解析进度，简单计算进度条
        if (logText.includes('后台任务已启动')) updateProgress.value = 20;
        if (logText.includes('同步完毕')) updateProgress.value = 50;
        if (logText.includes('开始执行 start-')) updateProgress.value = 85;
        
        const combinedLogs = logText + (updateOfflineNotices.value ? '\n' + updateOfflineNotices.value : '');
        if (updateLogs.value !== combinedLogs) {
          updateLogs.value = combinedLogs;
          scrollToBottom();
        }

        // 检查是否结束
        if (logText.includes('[DONE]')) {
          clearInterval(updatePollInterval.value);
          updateProgress.value = 100;
          updateFinished.value = true;
          updateOfflineNotices.value = '';
          updateLogs.value = logText;
          message.success('🎉 系统更新成功！请点击下方的按钮重新加载页面。', 5);
        } else if (logText.includes('[ERROR]')) {
          clearInterval(updatePollInterval.value);
          updateFinished.value = true;
          updateHasError.value = true;
          updateOfflineNotices.value = '';
          updateLogs.value = logText;
          message.error('❌ 系统更新遇到错误，请查看日志！', 8);
        }
      } catch (err) {
        // 网络请求失败（容器重启时）忽略错误，继续轮询
        if (!updateOfflineNotices.value.includes('等待容器恢复')) {
          updateOfflineNotices.value += '⏳ 网络暂时断开，正在等待容器恢复...\n';
          updateLogs.value += '⏳ 网络暂时断开，正在等待容器恢复...\n';
          scrollToBottom();
        }
      }
    }, 1500);
    
  } catch (e) {
    message.error('启动更新失败');
    console.error(e);
    updateButtonLoading.value = false;
  }
};

const scrollToBottom = () => {
  nextTick(() => {
    if (terminalRef.value) {
      terminalRef.value.scrollTop = terminalRef.value.scrollHeight;
    }
  });
};

onMounted(() => {
  if (route.query.tab) {
    activeKey.value = route.query.tab;
  }
  checkVersion();
  fetchDictList();
  fetchBruteDictList();
  fetchCdnList();
  fetchSecurityPolicy();
  fetchPerformanceConfig();
  fetchGeneralConfig();
});

onUnmounted(() => {
  if (updatePollInterval.value) {
    clearInterval(updatePollInterval.value);
  }
});
</script>

<style scoped>
/* 可以在此处添加自定义样式 */
</style>
