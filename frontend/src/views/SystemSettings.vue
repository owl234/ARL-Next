<template>
  <div style="padding: 24px; background: var(--arl-bg-white); min-height: 100%;">
    

    <a-tabs v-model:activeKey="activeKey">
      <!-- 统一字典管理 Tab -->
      <a-tab-pane key="dictionary" tab="字典管理">
        <a-spin :spinning="loading || bruteLoading">
            <div style="display: flex; gap: 0; height: calc(100vh - 180px); min-height: 580px; border-radius: 12px; overflow: hidden; box-shadow: 0 12px 48px rgba(0, 0, 0, 0.08), 0 4px 16px rgba(0, 0, 0, 0.04); border: 1px solid rgba(0,0,0,0.05); background: var(--arl-bg-white);"> <!-- 左侧语义化菜单与独立滚动 -->
            <div style="width: 256px; flex-shrink: 0; border-right: 1px solid var(--arl-border-color); background: var(--arl-bg-white); display: flex; flex-direction: column;">
              <div style="padding: 16px; border-bottom: 1px solid var(--arl-border-color); display: flex; align-items: center; min-height: 64px; box-sizing: border-box;">
                <span style="font-weight: 600; font-size: 14px; color: var(--arl-text-color);">字典分类</span>
              </div>
              <div class="hide-scrollbar" style="flex: 1; overflow-y: auto;">
                <div style="padding: 12px 8px; display: flex; flex-direction: column; gap: 4px;">
                  <div
                    v-for="group in treeData" :key="group.key"
                    class="custom-list-item"
                    :class="{ 'is-active': selectedCategoryKeys.includes(group.key) }"
                    @click="handleCategorySelect({ key: group.key })"
                  >
                    <div style="display: flex; align-items: center; gap: 8px;">
                      <span style="opacity: 0.9;">🗂️</span>
                      <span class="dict-title" style="font-weight: 600;">{{ group.title }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 2. 中间：字典列表 -->
            <div style="width: 250px; flex-shrink: 0; border-right: 1px solid var(--arl-border-color); background: var(--arl-bg-white); display: flex; flex-direction: column;">
              <div style="padding: 16px; border-bottom: 1px solid var(--arl-border-color); min-height: 64px; box-sizing: border-box;">
                <div style="display: flex; gap: 8px;">
                  <a-input-search v-model:value="menuSearch" placeholder="搜索当前分类下的字典..." style="flex: 1; border-radius: 4px;" />
                  <a-button type="primary" @click="openCreateDictDrawer" style="padding: 0 8px;" title="新建字典">
                    <template #icon><span style="margin-right:0px;">➕</span></template>
                  </a-button>
                </div>
              </div>
              <div class="hide-scrollbar" style="flex: 1; overflow-y: auto; padding: 12px 8px;">
                <div v-if="currentFilteredDicts.length === 0" style="padding: 48px 24px; text-align: center; color: var(--arl-text-color); opacity: 0.65; display: flex; flex-direction: column; align-items: center; gap: 12px;">
                  <span style="font-size: 32px; opacity: 0.8;">📭</span>
                  <span style="font-size: 13px; font-weight: 500;">分类下暂无字典</span>
                  <span style="font-size: 12px; opacity: 0.7;">点击上方 ➕ 新建或者换个分类</span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 4px;">
                  <div
                    v-for="item in currentFilteredDicts" :key="item.key"
                    class="custom-list-item"
                    :class="{ 'is-active': unifiedSelectedKeys.includes(item.key) }"
                    @click="handleUnifiedSelect([item.key])"
                  >
                    <div style="display: flex; align-items: flex-start; gap: 8px;">
                      <span style="font-size: 16px; margin-top: 2px; opacity: 0.9;">📄</span>
                      <div style="display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 0;">
                        <span class="dict-title" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500;">{{ item.mainTitle }}</span>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                          <span class="dict-subtitle">{{ item.subTitle }}</span>
                          <div style="display: flex; gap: 4px; align-items: center;">
                            <a-tag v-if="item.is_builtin" color="purple" style="margin: 0; font-size: 10px; line-height: 16px; padding: 0 4px; border-radius: 2px;">内置</a-tag>
                            <span class="dict-badge">txt</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 右侧统一操作面板 -->
            <div style="flex: 1; overflow: hidden; display: flex; flex-direction: column; min-width: 0; background: var(--arl-bg-white); position: relative;">

              <!-- 未选中时占位（健康看板） -->
              <div v-if="!unifiedSelectedType" class="health-dashboard-wrapper">
                <div class="health-dashboard-bg"></div>
                <div class="health-content">
                  <div class="health-icon-pulse">
                    <span style="font-size: 56px;">🌌</span>
                  </div>
                  <h3 class="health-title">字典库健康概览</h3>
                  <div class="health-stats-container">
                    <div class="health-stat-card primary-stat">
                      <div class="stat-value">{{ dictList.length }}</div>
                      <div class="stat-label">核心资产字典数</div>
                    </div>
                    <div class="health-stat-card warning-stat">
                      <div class="stat-value">{{ bruteDictList.length }}</div>
                      <div class="stat-label">弱口令字典数</div>
                    </div>
                  </div>
                  <div class="health-hint">
                    <span class="pulse-dot"></span>
                    <span>系统状态良好，请在左侧选择要管理的字典文件</span>
                  </div>
                </div>
              </div>

              <!-- 统一操作面板（沉浸式代码编辑器预览与悬浮操作） -->
              <div v-else class="native-preview-container">
                <!-- 顶部固定操作栏 -->
                <div class="native-toolbar">
                   <div>
                     <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
                       <h3 style="margin: 0; font-size: 16px; font-weight: 600; color: var(--arl-text-color);">{{ unifiedSelectedName }}</h3>
                       <a-tag :color="unifiedSelectedType === 'asset' ? 'blue' : 'orange'" style="margin: 0;">
                         {{ unifiedSelectedType === 'asset' ? '资产发现' : '弱口令' }}
                       </a-tag>
                       <a-tag v-if="unifiedSelectedIsBuiltin" color="purple" style="margin: 0;">
                         🔒 系统内置
                       </a-tag>
                     </div>
                     <div style="color: var(--arl-text-color); opacity: 0.55; font-size: 12px; font-family: 'Fira Code', monospace;">{{ unifiedSelectedDesc }} | Total: {{ totalLines }} lines</div>
                   </div>
                   <div style="display: flex; gap: 8px; align-items: center;">
                      <a-button @click="handleDownloadDict" :loading="downloadLoading" title="导出字典文件">
                        <template #icon><span style="margin-right:4px;">📥</span></template> 导出字典
                      </a-button>
                      <a-tooltip v-if="unifiedSelectedIsBuiltin" title="系统预置核心字典受安全保护，禁止彻底删除">
                        <a-button danger disabled>
                          <template #icon><span style="margin-right:4px;">🗑️</span></template> 删除字典
                        </a-button>
                      </a-tooltip>
                      <a-popconfirm
                        v-else
                        title="确定要彻底删除该字典文件吗？此操作不可逆！"
                        placement="bottomRight"
                        @confirm="handleDeleteDict"
                      >
                        <a-button danger>
                          <template #icon><span style="margin-right:4px;">🗑️</span></template> 删除字典
                        </a-button>
                      </a-popconfirm>
                     <a-button @click="searchDrawerVisible = true">
                       <template #icon><span style="margin-right:4px;">🔍</span></template> 检索清理
                     </a-button>
                     <a-button type="primary" @click="appendDrawerVisible = true">
                       <template #icon><span style="margin-right:4px;">➕</span></template> 追加数据
                     </a-button>
                   </div>
                </div>
                
                <!-- 极简内容预览区 -->
                <div class="native-preview-area hide-scrollbar" style="display: flex; flex-direction: column; gap: 12px;">
                  <div style="display: flex; justify-content: space-between; align-items: center; background: var(--arl-bg-white); padding: 8px 16px; border-radius: 8px; border: 1px solid var(--arl-border-color); box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                    <div style="display: flex; align-items: center; gap: 8px;">
                      <span style="font-size: 13px; font-weight: 500; color: var(--arl-text-color);">
                        📄 内容预览 (展示前 {{ previewLimit }} 行 / 共 {{ totalLines }} 行)
                      </span>
                    </div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                      <span style="font-size: 12px; opacity: 0.65; color: var(--arl-text-color);">预览行数:</span>
                      <a-radio-group v-model:value="previewLimit" size="small" @change="() => fetchPreview(selectedDict)">
                        <a-radio-button :value="50">50</a-radio-button>
                        <a-radio-button :value="100">100</a-radio-button>
                        <a-radio-button :value="500">500</a-radio-button>
                        <a-radio-button :value="1000">1000</a-radio-button>
                      </a-radio-group>
                      <a-button size="small" @click="copyPreviewContent">
                        <template #icon><span style="margin-right:2px;">📋</span></template> 复制预览
                      </a-button>
                    </div>
                  </div>

                  <div class="native-code-wrapper" style="flex: 1;">
                    <div class="native-line-numbers" v-if="previewContent">
                      <div v-for="n in previewLinesCount" :key="n" class="line-number">{{ n }}</div>
                    </div>
                    <div class="native-code-content">
                      <div v-if="!previewContent" class="empty-code">
                        <span>/* 该字典暂无内容 */</span>
                      </div>
                      <pre v-else class="code-text">{{ previewContent }}</pre>
                      <div v-if="totalLines > previewLimit" class="code-limit-hint">
                        // 仅预览前 {{ previewLimit }} 行内容 (总计 {{ totalLines }} 行)...
                      </div>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </a-spin>

        <!-- 新建字典抽屉 -->
        <a-drawer v-model:open="createDictDrawerVisible" title="新建字典" placement="right" width="450" @close="resetCreateDictForm">
          <a-tabs v-model:activeKey="createDictTabKey">
            <!-- 手动输入新建 -->
            <a-tab-pane key="manual" tab="手动输入新建">
              <div style="margin-bottom: 16px; color: var(--arl-text-color); font-size: 13px;">请选择字典分类并输入初始内容，系统将自动创建 .txt 文件。</div>
              <a-form layout="vertical">
                <a-form-item label="字典分类" required>
                  <a-select v-model:value="createDictForm.prefix">
                    <a-select-option value="domain_">🌍 子域名爆破 (domain_)</a-select-option>
                    <a-select-option value="altdns_">🧠 智能子域爆破 (altdns_)</a-select-option>
                    <a-select-option value="file_">📂 目录文件泄露 (file_)</a-select-option>
                    <a-select-option value="black">🛡️ 全局黑名单拦截 (black*)</a-select-option>
                    <a-select-option value="port_">🔌 端口扫描策略 (port_)</a-select-option>
                    <a-select-option value="dnsserver_">🌐 DNS 解析配置 (dnsserver_)</a-select-option>
                    <a-select-option value="username_">👤 弱口令账号 (username_)</a-select-option>
                    <a-select-option value="password_">🔑 弱口令密码 (password_)</a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item label="字典名称 (仅英文、数字、下划线)" required>
                  <a-input v-model:value="createDictForm.customName" placeholder="例如: top100" />
                </a-form-item>
                <a-form-item label="初始字典内容 (可选)">
                  <a-textarea v-model:value="createDictForm.content" placeholder="每行一个条目，支持批量粘贴" :rows="8" />
                </a-form-item>
              </a-form>
              <div style="text-align: right; margin-top: 24px;">
                <a-button @click="createDictDrawerVisible = false" style="margin-right: 8px;">取消</a-button>
                <a-button type="primary" :loading="createDictLoading" :disabled="!isCreateDictValid" @click="handleCreateDictManual">确定新建</a-button>
              </div>
            </a-tab-pane>

            <!-- 文件上传新建 -->
            <a-tab-pane key="upload" tab="文件上传新建">
              <div style="margin-bottom: 16px; color: var(--arl-text-color); font-size: 13px;">请选择字典分类并上传一个包含条目的 .txt 文件，我们将自动进行去重。</div>
              <a-form layout="vertical">
                <a-form-item label="字典分类" required>
                  <a-select v-model:value="createDictForm.prefix">
                    <a-select-option value="domain_">🌍 子域名爆破 (domain_)</a-select-option>
                    <a-select-option value="altdns_">🧠 智能子域爆破 (altdns_)</a-select-option>
                    <a-select-option value="file_">📂 目录文件泄露 (file_)</a-select-option>
                    <a-select-option value="black">🛡️ 全局黑名单拦截 (black*)</a-select-option>
                    <a-select-option value="port_">🔌 端口扫描策略 (port_)</a-select-option>
                    <a-select-option value="dnsserver_">🌐 DNS 解析配置 (dnsserver_)</a-select-option>
                    <a-select-option value="username_">👤 弱口令账号 (username_)</a-select-option>
                    <a-select-option value="password_">🔑 弱口令密码 (password_)</a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item label="字典名称 (仅英文、数字、下划线)" required>
                  <a-input v-model:value="createDictForm.customName" placeholder="例如: top100" />
                </a-form-item>
                <a-form-item label="选择字典文件 (.txt)" required>
                  <a-upload :file-list="createDictForm.fileList" :before-upload="(f) => { createDictForm.fileList = [f]; return false; }" @remove="createDictForm.fileList = []" accept=".txt">
                    <a-button><template #icon>📁</template> 点击选择文件</a-button>
                  </a-upload>
                </a-form-item>
              </a-form>
              <div style="text-align: right; margin-top: 24px;">
                <a-button @click="handleCreateDictUploadCancel" style="margin-right: 8px;">取消</a-button>
                <a-button type="primary" :loading="createDictLoading" :disabled="!isCreateDictValid || createDictForm.fileList.length === 0" @click="handleCreateDictUpload">开始上传并新建</a-button>
              </div>
            </a-tab-pane>
          </a-tabs>
        </a-drawer>

        <!-- 上传字典弹窗 -->
        <!-- 追加数据抽屉（合并手动输入与大文件上传） -->
        <a-drawer v-model:open="appendDrawerVisible" title="追加字典数据" placement="right" width="450">
          <a-tabs v-model:activeKey="appendMode" style="margin-bottom: 16px;">
            <a-tab-pane key="text" tab="手动粘贴">
              <div style="margin-bottom: 12px; color: var(--arl-text-color); font-size: 13px;">请粘贴要追加的条目（每行一个）：</div>
              <a-textarea v-model:value="newEntries" :rows="22" placeholder="例如：
admin
root" style="font-family: monospace; font-size: 12px; margin-bottom: 24px;" />
              <div style="display: flex; justify-content: flex-end; gap: 12px;">
                <a-button @click="appendDrawerVisible = false">取消</a-button>
                <a-button type="primary" @click="handleAppendAndClose" :loading="submitLoading" :disabled="!newEntries.trim()">提交保存</a-button>
              </div>
            </a-tab-pane>
            <a-tab-pane key="file" tab="文件上传">
              <div>
                <div style="margin-bottom: 16px; color: var(--arl-text-color); font-size: 13px;">
                  支持上传数百万行的 TXT 文本，后台将自动去重并合并到当前字典中。
                </div>
                <a-upload-dragger
                  name="file"
                  :multiple="false"
                  :customRequest="handleLargeUpload"
                  accept=".txt"
                  :showUploadList="false"
                >
                  <p class="ant-upload-drag-icon" style="font-size: 48px; margin-bottom: 16px;">
                    📄
                  </p>
                  <p class="ant-upload-text">点击或将 TXT 文件拖拽到这里上传</p>
                  <p class="ant-upload-hint">
                    仅支持纯文本格式，每行一个词条
                  </p>
                </a-upload-dragger>
              </div>
            </a-tab-pane>
          </a-tabs>
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
        <a-spin :spinning="cdnLoading">
          <div style="display: flex; gap: 0; height: calc(100vh - 180px); min-height: 580px; border-radius: 12px; overflow: hidden; box-shadow: 0 12px 48px rgba(0, 0, 0, 0.08), 0 4px 16px rgba(0, 0, 0, 0.04); border: 1px solid rgba(0,0,0,0.05); background: var(--arl-bg-white);"> 
            
            <!-- 左侧：CDN 列表 -->
            <div style="width: 256px; flex-shrink: 0; border-right: 1px solid var(--arl-border-color); background: var(--arl-bg-white); display: flex; flex-direction: column;">
              <div style="padding: 16px; border-bottom: 1px solid var(--arl-border-color); min-height: 64px; box-sizing: border-box;">
                <div style="display: flex; gap: 8px;">
                  <a-input-search v-model:value="cdnSearchText" placeholder="搜索 CDN..." style="flex: 1; border-radius: 4px;" />
                  <a-button 
                    v-if="isCdnDirty" 
                    type="primary" 
                    class="breathing-btn" 
                    @click="saveCdnData" 
                    :loading="cdnSaveLoading" 
                    style="padding: 0 8px; background-color: #52c41a; border-color: #52c41a;" 
                    title="有未保存的更改"
                  >
                    <template #icon><span style="margin-right:0px;">💾</span></template>
                  </a-button>
                  <a-button type="primary" @click="openCdnDrawer" style="padding: 0 8px;" title="添加CDN特征">
                    <template #icon><span style="margin-right:0px;">➕</span></template>
                  </a-button>
                </div>
              </div>
              <div class="hide-scrollbar" style="flex: 1; overflow-y: auto; padding: 12px 8px;">
                <div v-if="filteredCdnList.length === 0" style="padding: 48px 24px; text-align: center; color: var(--arl-text-color); opacity: 0.65; display: flex; flex-direction: column; align-items: center; gap: 12px;">
                  <span style="font-size: 32px; opacity: 0.8;">📭</span>
                  <span style="font-size: 13px; font-weight: 500;">未找到 CDN</span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 4px;">
                  <div
                    v-for="item in filteredCdnList" :key="item.name"
                    class="custom-list-item"
                    :class="{ 'is-active': selectedCdnName === item.name }"
                    @click="selectedCdnName = item.name"
                  >
                    <div style="display: flex; align-items: flex-start; gap: 8px;">
                      <span style="font-size: 16px; margin-top: 2px; opacity: 0.9;">🌐</span>
                      <div style="display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 0;">
                        <span class="dict-title" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500;">{{ item.name }}</span>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                          <span class="dict-subtitle">{{ (item.cname_domain || []).length }} CNAME, {{ (item.ip_cidr || []).length }} IPs</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 右侧：详情面板 -->
            <div style="flex: 1; overflow: hidden; display: flex; flex-direction: column; min-width: 0; background: var(--arl-bg-white); position: relative;">
              <!-- 健康概览 -->
              <div v-if="!selectedCdn" class="health-dashboard-wrapper">
                <div class="health-dashboard-bg"></div>
                <div class="health-content">
                  <div class="health-icon-pulse">
                    <span style="font-size: 56px;">🌍</span>
                  </div>
                  <h3 class="health-title">CDN 数据健康概览</h3>
                  <div class="health-stats-container">
                    <div class="health-stat-card primary-stat">
                      <div class="stat-value">{{ cdnList.length }}</div>
                      <div class="stat-label">总计 CDN 厂商</div>
                    </div>
                    <div class="health-stat-card warning-stat">
                      <div class="stat-value">{{ totalCnameCount }}</div>
                      <div class="stat-label">CNAME 规则总数</div>
                    </div>
                    <div class="health-stat-card danger-stat" style="background: rgba(245, 34, 45, 0.04); border: 1px solid rgba(245, 34, 45, 0.1);">
                      <div class="stat-value" style="color: #cf1322;">{{ totalIpCount }}</div>
                      <div class="stat-label" style="color: #cf1322;">IP 段规则总数</div>
                    </div>
                  </div>
                  <div class="health-hint">
                    <span class="pulse-dot"></span>
                    <span>状态良好，请在左侧选择特定 CDN 进行管理</span>
                  </div>
                </div>
              </div>
              
              <!-- CDN 详情与编辑 -->
              <div v-else class="native-preview-container">
                <div class="native-toolbar">
                   <div>
                     <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
                       <h3 style="margin: 0; font-size: 16px; font-weight: 600; color: var(--arl-text-color);">{{ selectedCdn.name }}</h3>
                       <a-tag color="cyan" style="margin: 0;">CDN特征</a-tag>
                     </div>
                     <div style="color: var(--arl-text-color); opacity: 0.55; font-size: 12px;">包含 {{ (selectedCdn.cname_domain || []).length }} 条 CNAME，{{ (selectedCdn.ip_cidr || []).length }} 条 IP 段</div>
                   </div>
                   <div style="display: flex; gap: 8px; align-items: center;">
                      <a-button 
                        v-if="isCdnDirty" 
                        type="primary" 
                        @click="saveCdnData" 
                        :loading="cdnSaveLoading"
                        class="breathing-btn"
                        style="background-color: #52c41a; border-color: #52c41a;"
                      >
                        <template #icon><span style="margin-right:4px;">💾</span></template> 保存更改
                      </a-button>
                      <a-popconfirm title="确定要删除该 CDN 吗？需保存全量更改后生效。" placement="bottomRight" @confirm="deleteSelectedCdn">
                        <a-button danger><template #icon><span style="margin-right:4px;">🗑️</span></template> 删除特征</a-button>
                      </a-popconfirm>
                      <a-button type="primary" ghost @click="editSelectedCdn"><template #icon><span style="margin-right:4px;">✏️</span></template> 编辑特征</a-button>
                   </div>
                </div>

                <!-- 极简内容预览区 (双区块) -->
                <div class="native-preview-area hide-scrollbar" style="display: flex; flex-direction: column; gap: 16px; padding-bottom: 24px;">
                  
                  <!-- CNAME 规则 -->
                  <div class="native-code-wrapper" style="flex: none; display: flex; flex-direction: column; padding: 0;">
                    <div style="padding: 8px 16px; background: rgba(0,0,0,0.02); border-bottom: 1px solid var(--arl-border-color); font-weight: 500; font-size: 13px; color: var(--arl-text-color); display: flex; justify-content: space-between; align-items: center;">
                      <span>🌍 CNAME 规则 ({{ (selectedCdn.cname_domain || []).length }})</span>
                      <a-button size="small" type="text" @click="() => copyTextList(selectedCdn.cname_domain, 'CNAME 规则')">
                        📋 复制
                      </a-button>
                    </div>
                    <div style="display: flex; position: relative; padding: 16px;">
                      <div class="native-line-numbers" v-if="selectedCdn.cname_domain && selectedCdn.cname_domain.length > 0">
                        <div v-for="n in selectedCdn.cname_domain.length" :key="'cname-'+n" class="line-number">{{ n }}</div>
                      </div>
                      <div class="native-code-content" style="min-height: 40px;">
                        <div v-if="!(selectedCdn.cname_domain && selectedCdn.cname_domain.length > 0)" class="empty-code" style="padding-top: 0;">
                          <span>/* 暂无 CNAME 规则 */</span>
                        </div>
                        <pre v-else class="code-text">{{ selectedCdn.cname_domain.join('\n') }}</pre>
                      </div>
                    </div>
                  </div>

                  <!-- IP CIDR 规则 -->
                  <div class="native-code-wrapper" style="flex: none; display: flex; flex-direction: column; padding: 0;">
                    <div style="padding: 8px 16px; background: rgba(0,0,0,0.02); border-bottom: 1px solid var(--arl-border-color); font-weight: 500; font-size: 13px; color: var(--arl-text-color); display: flex; justify-content: space-between; align-items: center;">
                      <span>🔌 IP CIDR 规则 ({{ (selectedCdn.ip_cidr || []).length }})</span>
                      <a-button size="small" type="text" @click="() => copyTextList(selectedCdn.ip_cidr, 'IP CIDR 规则')">
                        📋 复制
                      </a-button>
                    </div>
                    <div style="display: flex; position: relative; padding: 16px;">
                      <div class="native-line-numbers" v-if="selectedCdn.ip_cidr && selectedCdn.ip_cidr.length > 0">
                        <div v-for="n in selectedCdn.ip_cidr.length" :key="'ip-'+n" class="line-number">{{ n }}</div>
                      </div>
                      <div class="native-code-content" style="min-height: 40px;">
                        <div v-if="!(selectedCdn.ip_cidr && selectedCdn.ip_cidr.length > 0)" class="empty-code" style="padding-top: 0;">
                          <span>/* 暂无 IP CIDR 规则 */</span>
                        </div>
                        <pre v-else class="code-text">{{ selectedCdn.ip_cidr.join('\n') }}</pre>
                      </div>
                    </div>
                  </div>

                </div>
              </div>

            </div>
          </div>
        </a-spin>

        <a-drawer
          v-model:open="cdnDrawerVisible"
          :title="isEditingCdn ? '编辑CDN特征' : '添加CDN特征'"
          placement="right"
          width="450"
          @close="resetCdnForm"
        >
          <div style="display: flex; flex-direction: column; height: 100%;">
            <div class="hide-scrollbar" style="flex: 1; overflow-y: auto; padding-right: 4px;">
              <a-form :model="currentCdnForm" layout="vertical">
                <a-form-item label="CDN名称" required>
                  <a-input v-model:value="currentCdnForm.name" placeholder="例如：阿里云CDN" />
                </a-form-item>
                <a-form-item label="CNAME后缀">
                  <a-textarea v-model:value="currentCdnForm.cnameText" :rows="8" placeholder="每行输入一个CNAME后缀，如: kunlunpi.com" />
                </a-form-item>
                <a-form-item label="IP网段(CIDR)">
                  <a-textarea v-model:value="currentCdnForm.ipText" :rows="8" placeholder="每行输入一个IP网段，如: 103.21.244.0/22" />
                </a-form-item>
              </a-form>
            </div>
            <div style="border-top: 1px solid var(--arl-border-color); padding-top: 16px; text-align: right; margin-top: 16px;">
              <a-button @click="cdnDrawerVisible = false" style="margin-right: 8px;">取消</a-button>
              <a-button type="primary" @click="submitCdnDrawer">确定保存</a-button>
            </div>
          </div>
        </a-drawer>
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
              <a-row :gutter="24">
                <a-col :span="12">
                  <a-card title="🌍 外网情报侦察任务调度" size="small" style="margin-bottom: 16px; border-radius: 6px; border-left: 4px solid #1890ff;">
                    <a-form-item>
                      <template #label>
                        OSINT 任务并发数
                        <a-popover placement="right">
                          <template #content>
                            <div style="max-width: 320px;">
                              <div style="font-weight: bold; margin-bottom: 8px;">[分配规则] 外网情报侦察任务：</div>
                              <ul style="padding-left: 18px; margin: 0; line-height: 1.8;">
                                <li>ICP 备案查询 (网站/APP/小程序)</li>
                                <li>天眼查 (TYC) 股权穿透与资产收集</li>
                              </ul>
                            </div>
                          </template>
                          <InfoCircleOutlined style="margin-left: 4px; color: #888; cursor: pointer;" />
                        </a-popover>
                      </template>
                      <a-input-number v-model:value="performanceForm.osint_concurrency" :min="1" :max="128" style="width: 100%" />
                      <div style="margin-top: 8px; color: var(--arl-text-color); opacity: 0.45; font-size: 13px;">
                        控制 OSINT 模块对外部目标（如天眼查、工信部备案等）的并发请求数。建议保持默认值 1，避免因外网请求过快导致接口熔断或 IP 被封禁。修改后将在 10 秒内由后台看门狗自动热更新生效。
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
              <a-descriptions-item v-if="hasNewVersion" label="更新日志">
                <div class="markdown-release-notes hide-scrollbar" v-html="renderedReleaseNotes" style="max-height: 380px; overflow-y: auto; line-height: 1.6; font-size: 13px; background: rgba(0,0,0,0.02); padding: 12px 16px; border-radius: 6px; border: 1px solid var(--arl-border-color);"></div>
              </a-descriptions-item>
            </a-descriptions>
            
            <div style="margin-top: 20px; text-align: center;">
              <a-popconfirm title="此操作将拉取最新镜像并重启系统容器，大概需要几分钟时间，请确认当前无正在执行的重要任务。确定执行更新吗？" @confirm="handleStartUpdateClick">
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
import { ref, reactive, onMounted, onUnmounted, computed, nextTick, watch } from 'vue';
import { message, Modal } from 'ant-design-vue';
import request from '@/utils/request';
import { copyText } from '@/utils/clipboard';
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
// ======================= 新建字典模块 =======================
const createDictDrawerVisible = ref(false);
const createDictTabKey = ref('manual');
const createDictLoading = ref(false);
const createDictForm = reactive({
  prefix: 'domain_',
  customName: '',
  content: '',
  fileList: []
});

const openCreateDictDrawer = () => {
  createDictDrawerVisible.value = true;
  if (selectedCategoryKeys.value.length > 0) {
    const key = selectedCategoryKeys.value[0];
    if (key.includes('子域名爆破')) {
      createDictForm.prefix = 'domain_';
    } else if (key.includes('智能子域爆破')) {
      createDictForm.prefix = 'altdns_';
    } else if (key.includes('目录文件泄露')) {
      createDictForm.prefix = 'file_';
    } else if (key.includes('端口扫描策略')) {
      createDictForm.prefix = 'port_';
    } else if (key.includes('DNS 解析')) {
      createDictForm.prefix = 'dnsserver_';
    } else if (key.includes('全局黑名单拦截')) {
      createDictForm.prefix = 'black';
    } else if (key.includes('group_brute_')) {
      createDictForm.prefix = 'username_';
    }
  }
};

const isCreateDictValid = computed(() => {
  return createDictForm.customName && /^[a-zA-Z0-9_]+$/.test(createDictForm.customName);
});

// 新建字典时按前缀自动路由：username_/password_ → 弱口令字典目录 (brute_dict)，其余 → 资产字典目录 (dictionary)
const isBruteCreatePrefix = computed(() => {
  return createDictForm.prefix === 'username_' || createDictForm.prefix === 'password_';
});
const createDictApiBase = computed(() => isBruteCreatePrefix.value ? '/api/brute_dict' : '/api/dictionary');

const resetCreateDictForm = () => {
  createDictForm.prefix = 'domain_';
  createDictForm.customName = '';
  createDictForm.content = '';
  createDictForm.fileList = [];
  createDictTabKey.value = 'manual';
};

const handleCreateDictManual = async () => {
  let targetName = `${createDictForm.prefix}${createDictForm.customName}.txt`;

  createDictLoading.value = true;
  try {
    const res = await request.post(`${createDictApiBase.value}/create`, {
      name: targetName,
      content: createDictForm.content
    });
    if (res.code === 200) {
      message.success(`字典 ${targetName} 新建成功！`);
      // 先捕获前缀判定再重置表单，避免 resetCreateDictForm 将 prefix 重置为 domain_ 导致刷新错列表
      const isBrute = isBruteCreatePrefix.value;
      createDictDrawerVisible.value = false;
      resetCreateDictForm();
      if (isBrute) {
        fetchBruteDictList();
      } else {
        fetchDictList();
      }
    } else {
      message.error(res.message || '新建失败');
    }
  } catch (error) {
    message.error('新建请求出错');
  } finally {
    createDictLoading.value = false;
  }
};

const handleCreateDictUploadCancel = () => {
  if (createDictLoading.value) {
    message.warning('正在上传中，请勿取消');
    return;
  }
  createDictDrawerVisible.value = false;
  resetCreateDictForm();
};

const handleCreateDictUpload = async () => {
  let targetName = `${createDictForm.prefix}${createDictForm.customName}.txt`;

  const file = createDictForm.fileList[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', targetName);

  createDictLoading.value = true;
  try {
    const res = await request.post(`${createDictApiBase.value}/upload_large`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    if (res.code === 200) {
      const hideMsg = message.loading(`字典 ${targetName} 正在后台导入中，您可以继续其他操作...`, 0);
      // 先捕获前缀判定与 API 基址再重置表单，避免 resetCreateDictForm 将 prefix 重置为 domain_ 导致轮询/刷新错命名空间
      const apiBase = createDictApiBase.value;
      const isBrute = isBruteCreatePrefix.value;
      createDictDrawerVisible.value = false;
      resetCreateDictForm();

      const pollTimer = setInterval(async () => {
        try {
          const statusRes = await request.get(`${apiBase}/upload_status`, { params: { task_id: res.task_id } });
          if (statusRes.code === 200) {
            if (statusRes.data.status === 'completed') {
              clearInterval(pollTimer);
              hideMsg();
              message.success(`字典 ${targetName} 导入完成！新增 ${statusRes.data.inserted_lines} 条，忽略重复 ${statusRes.data.ignored_lines} 条`);
              if (isBrute) {
                fetchBruteDictList(false);
              } else {
                fetchDictList(false);
              }
            } else if (statusRes.data.status === 'error') {
              clearInterval(pollTimer);
              hideMsg();
              message.error(`导入 ${targetName} 失败: ${statusRes.data.message}`);
            }
          } else {
            // 任务不存在/状态丢失（如后端容器重启），停止轮询避免定时器泄漏
            clearInterval(pollTimer);
            hideMsg();
            message.warning(`导入任务状态已丢失 (${statusRes.message || '任务不存在'})，请刷新页面后确认。`);
          }
        } catch (e) {
          // 忽略轮询时的网络抖动
        }
      }, 2000);
    } else {
      message.error(res.message || '上传失败');
    }
  } catch (error) {
    message.error('上传请求出错');
  } finally {
    createDictLoading.value = false;
  }
};

// ======================= 追加字典逻辑 =======================
const appendDrawerVisible = ref(false);
const appendMode = ref('text');

// 上传字典状态
// 执行大文件上传
const handleLargeUpload = async (info) => {
  const file = info.file;
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', unifiedSelectedName.value);
  
  const targetName = unifiedSelectedName.value;
  const currentType = unifiedSelectedType.value;
  
  const uploadUrl = currentType === 'asset' ? '/api/dictionary/upload_large' : '/api/brute_dict/upload_large';
  const statusUrl = currentType === 'asset' ? '/api/dictionary/upload_status' : '/api/brute_dict/upload_status';

  try {
    const res = await request.post(uploadUrl, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });

    if (res.code === 200) {
      const hideMsg = message.loading(`字典 ${targetName} 正在后台追加导入中，您可以继续其他操作...`, 0);
      appendDrawerVisible.value = false;
      
      const pollTimer = setInterval(async () => {
        try {
          const statusRes = await request.get(statusUrl, { params: { task_id: res.task_id } });
          if (statusRes.code === 200) {
            if (statusRes.data.status === 'completed') {
              clearInterval(pollTimer);
              hideMsg();
              message.success(`字典 ${targetName} 追加导入完成！新增 ${statusRes.data.inserted_lines} 条，忽略重复 ${statusRes.data.ignored_lines} 条`);
              
              if (currentType === 'asset') {
                fetchDictList(false);
                fetchPreview(targetName);
              } else {
                fetchBruteDictList(false);
                fetchPreview(targetName);
              }
            } else if (statusRes.data.status === 'error') {
              clearInterval(pollTimer);
              hideMsg();
              message.error(`字典 ${targetName} 追加失败: ${statusRes.data.message}`);
            }
          } else {
            // 任务不存在/状态丢失，停止轮询避免定时器泄漏
            clearInterval(pollTimer);
            hideMsg();
            message.warning('追加任务状态已丢失，请刷新页面后确认。');
          }
        } catch (e) {
          // 忽略轮询时的网络抖动
        }
      }, 2000);
    } else {
      message.error(res.message || '上传失败');
    }
  } catch (error) {
    message.error('网络或服务器错误');
  }
};
const searchDrawerVisible = ref(false);
const batchDeleteEntries = ref('');

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
  'domain_2w.txt':       { label: '子域名爆破主字典 (2万)', group: '🌍 子域名爆破' },
  'altdnsdict.txt':      { label: '子域名智能生成辅助词',   group: '🧠 智能子域爆破' },
  'dnsserver.txt':       { label: 'DNS 解析服务器列表',     group: '🌐 DNS 解析配置' },
  'file_top_200.txt':    { label: 'Top 200 路径字典',       group: '📂 目录文件泄露' },
  'file_top_2000.txt':   { label: 'Top 2000 路径字典',      group: '📂 目录文件泄露' },

  'port_top100.txt':     { label: '常用 100 端口',          group: '🔌 端口扫描策略' },
  'port_top1000.txt':    { label: '常用 1000 端口',         group: '🔌 端口扫描策略' },
  'port_custom.txt':     { label: '自定义端口',             group: '🔌 端口扫描策略' },
  'port_all.txt':        { label: '全端口 (1-65535)',       group: '🔌 端口扫描策略' },

  'blackdomain.txt':     { label: '根域名爆破拦截字典',     group: '🛡️ 全局黑名单拦截' },
  'black_asset_site.txt':{ label: '恶意/干扰站点拦截字典',  group: '🛡️ 全局黑名单拦截' },
  'blackhexie.txt':      { label: '敏感词汇过滤字典',       group: '🛡️ 全局黑名单拦截' },
};

const assetMenuGroups = computed(() => {
  const groups = { '🌍 子域名爆破': [], '🧠 智能子域爆破': [], '📂 目录文件泄露': [], '🔌 端口扫描策略': [], '🌐 DNS 解析配置': [], '🛡️ 全局黑名单拦截': [] };
  
  const getGroupAndLabel = (dictName) => {
    if (ASSET_DICT_META[dictName]) {
      return { group: ASSET_DICT_META[dictName].group, label: ASSET_DICT_META[dictName].label };
    }
    if (dictName.startsWith('domain_')) return { group: '🌍 子域名爆破', label: dictName };
    if (dictName.startsWith('altdns_')) return { group: '🧠 智能子域爆破', label: dictName };
    if (dictName.startsWith('dnsserver_')) return { group: '🌐 DNS 解析配置', label: dictName };
    if (dictName.startsWith('file_')) return { group: '📂 目录文件泄露', label: dictName };
    if (dictName.startsWith('black')) return { group: '🛡️ 全局黑名单拦截', label: dictName };
    if (dictName.startsWith('port_')) return { group: '🔌 端口扫描策略', label: dictName };
    return null;
  };

  dictList.value.forEach(dict => {
    const meta = getGroupAndLabel(dict.name);
    if (!meta) return;
    
    if (!groups[meta.group]) groups[meta.group] = [];
    groups[meta.group].push({
      ...dict,
      title: meta.label
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
    // 通用弱口令字典（如 common_password.txt）归入独立分组
    if (item.name.startsWith('common_') && item.name.endsWith('.txt')) {
      if (!groups['通用弱口令']) groups['通用弱口令'] = [];
      groups['通用弱口令'].push(item);
      return;
    }
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
          is_builtin: item.is_builtin
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

        // 通用弱口令组内直接显示文件名，避免 "[通用弱口令] 通用弱口令" 冗余
        const mainTitle = svc === '通用弱口令'
          ? (friendlyPrefix === '通用弱口令' ? item.name : `${friendlyPrefix || item.name}`)
          : `[${svc}] ${friendlyPrefix || item.name}`;

        npocChildren.push({
          mainTitle,
          subTitle: item.name,
          key: `brute__${item.name}`,
          is_builtin: item.is_builtin
        });
      });
    }
  });
  if (npocChildren.length > 0) {
    data.push({ title: '🔑 弱口令字典', key: 'group_brute_all', children: npocChildren });
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
  if (newVal.length > 0 && (!selectedCategoryKeys.value.length || !newVal.find(g => g.key === selectedCategoryKeys.value[0]))) {
    selectedCategoryKeys.value = [newVal[0].key];
  }
}, { immediate: true });

const handleUnifiedMenuSelect = ({ key }) => {
  handleUnifiedSelect([key]);
};

const handleAppendAndClose = async () => {
  const ok = await handleAppend();
  if (ok) appendDrawerVisible.value = false;
};

const handleDeleteBatchCustom = async () => {
  if (!batchDeleteEntries.value.trim()) return;
  const ok = await deleteEntries(batchDeleteEntries.value);
  if (ok) {
    batchDeleteEntries.value = '';
    searchDrawerVisible.value = false;
  }
};

// 分类选择状态（默认对齐首个分类的唯一分组 key）
const selectedCategoryKeys = ref(['group_asset_🌍 子域名爆破']);

const handleCategorySelect = ({ key }) => {
  selectedCategoryKeys.value = [key];
  menuSearch.value = '';
};

// 统一字典选择状态
const unifiedSelectedKeys = ref([]);
const unifiedSelectedType = ref('');  // 'asset' | 'brute'
const unifiedSelectedName = ref('');
const unifiedSelectedDesc = ref('');

const unifiedSelectedIsBuiltin = computed(() => {
  if (!unifiedSelectedName.value) return false;
  if (unifiedSelectedType.value === 'asset') {
    const item = dictList.value.find(d => d.name === unifiedSelectedName.value);
    return item ? Boolean(item.is_builtin) : false;
  } else if (unifiedSelectedType.value === 'brute') {
    const item = bruteDictList.value.find(d => d.name === unifiedSelectedName.value);
    return item ? Boolean(item.is_builtin) : false;
  }
  return false;
});

const currentFilteredDicts = computed(() => {
  if (!selectedCategoryKeys.value.length) return [];
  const activeKey = selectedCategoryKeys.value[0];
  const group = filteredTreeData.value.find(g => g.key === activeKey);
  return group ? group.children || [] : [];
});

const handleUnifiedSelect = (selectedKeys, info) => {
  const key = Array.isArray(selectedKeys) ? selectedKeys[0] : selectedKeys;
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
const previewLimit = ref(100);

const previewLinesCount = computed(() => {
  if (!previewContent.value) return 0;
  return previewContent.value.split('\n').length;
});

const downloadLoading = ref(false);
const handleDownloadDict = async () => {
  if (!selectedDict.value) return;
  downloadLoading.value = true;
  try {
    const res = await request.get(`${dictApiBase.value}/download`, {
      params: { name: selectedDict.value },
      responseType: 'blob'
    });
    // 后端异常时以 HTTP 4xx/5xx 返回，axios 会走 catch 分支
    const blob = new Blob([res], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = selectedDict.value;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
    message.success(`字典 ${selectedDict.value} 导出成功！`);
  } catch (e) {
    let errMsg = '导出字典失败';
    if (e.response && e.response.data instanceof Blob) {
      try {
        const text = await e.response.data.text();
        const parsed = JSON.parse(text);
        if (parsed.message) errMsg = parsed.message;
      } catch (_) { /* ignore parse errors */ }
    }
    message.error(errMsg);
    console.error(e);
  } finally {
    downloadLoading.value = false;
  }
};

const copyPreviewContent = async () => {
  if (!previewContent.value) {
    message.warning('当前没有可复制的内容');
    return;
  }
  const ok = await copyText(previewContent.value);
  if (ok) {
    message.success('预览内容已成功复制到剪贴板！');
  } else {
    message.error('复制失败，请手动选择复制');
  }
};

const searchKeyword = ref('');
const searchResult = ref(null);

const newEntries = ref('');

// 根据当前选中类型返回 API 前缀
const dictApiBase = computed(() =>
  unifiedSelectedType.value === 'brute' ? '/api/brute_dict' : '/api/dictionary'
);

// 获取字典列表
const fetchDictList = async (showLoading = true) => {
  if (showLoading) loading.value = true;
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
    if (showLoading) loading.value = false;
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

// 追加条目（自动路由），返回是否成功
const handleAppend = async () => {
  if (!newEntries.value.trim()) return false;

  // 智能格式校验（阻断无效输入）
  const lines = newEntries.value.split('\n').map(s => s.trim()).filter(s => s);
  if (selectedDict.value && selectedDict.value.startsWith('port_')) {
    const invalidPorts = lines.filter(p => !/^\d+$/.test(p) || parseInt(p) < 1 || parseInt(p) > 65535);
    if (invalidPorts.length > 0) {
      message.error(`校验失败：包含无效端口号 (如 ${invalidPorts[0]})，请输入 1-65535 之间的纯数字`);
      return false;
    }
  } else if (selectedDict.value && selectedDict.value.includes('domain')) {
    const invalidDomains = lines.filter(d => /[\s,;!@#%^&*()<>{}\[\]]/.test(d));
    if (invalidDomains.length > 0) {
       message.error(`校验失败：子域名字典包含非法字符 (如空格或特殊符号)`);
       return false;
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
      return true;
    } else {
      message.error(res.message || '保存失败');
      return false;
    }
  } catch (error) {
    message.error('请求保存出错');
    console.error(error);
    return false;
  } finally {
    submitLoading.value = false;
  }
};

// 批量删除
const handleDeleteBatch = async () => {
  if (!newEntries.value.trim()) return false;
  const ok = await deleteEntries(newEntries.value);
  if (ok) {
    newEntries.value = '';
  }
  return ok;
};

// 单条删除
const handleDeleteSingle = async (item) => {
  if (!item) return false;
  const ok = await deleteEntries(item);
  if (ok && searchResult.value) {
    searchResult.value = searchResult.value.filter(x => x !== item);
  }
  return ok;
};

// 删除选中字典文件
const handleDeleteDict = async () => {
  if (!selectedDict.value) return;
  
  loading.value = true;
  try {
    const res = await request.post(`${dictApiBase.value}/delete_file`, {
      name: selectedDict.value
    });
    if (res.code === 200) {
      message.success(`字典 ${selectedDict.value} 删除成功！`);
      // 重置选中状态
      unifiedSelectedKeys.value = [];
      selectedDict.value = '';
      previewContent.value = '';
      totalLines.value = 0;
      
      // 重新拉取列表
      if (unifiedSelectedType.value === 'brute') {
        fetchBruteDictList();
      } else {
        fetchDictList();
      }
      unifiedSelectedType.value = '';
    } else {
      message.error(res.message || '删除失败');
    }
  } catch (error) {
    message.error('请求删除出错');
    console.error(error);
  } finally {
    loading.value = false;
  }
};

// 公共删除逻辑（自动路由）
const deleteEntries = async (content) => {
  if (!content || !content.trim()) return false;
  deleteLoading.value = true;
  try {
    const res = await request.post(`${dictApiBase.value}/delete_entries`, {
      name: selectedDict.value,
      content: content
    });
    if (res.code === 200) {
      message.success(`删除成功！尝试删除 ${res.data.total_submitted} 项，实际成功删除 ${res.data.deleted} 项。`);
      fetchDictList();
      fetchBruteDictList();
      fetchPreview(selectedDict.value);
      return true;
    } else {
      message.error(res.message || '删除失败');
      return false;
    }
  } catch (error) {
    message.error('请求删除出错');
    console.error(error);
    return false;
  } finally {
    deleteLoading.value = false;
  }
};

// ======================= CDN 管理逻辑 =======================
const cdnList = ref([]);
const originalCdnList = ref([]);
const cdnLoading = ref(false);
const cdnSaveLoading = ref(false);

const isCdnDirty = computed(() => {
  return JSON.stringify(cdnList.value) !== JSON.stringify(originalCdnList.value);
});

const cdnSearchText = ref('');
const selectedCdnName = ref('');

const filteredCdnList = computed(() => {
  if (!cdnSearchText.value) return cdnList.value;
  return cdnList.value.filter(item => 
    item.name.toLowerCase().includes(cdnSearchText.value.toLowerCase())
  );
});

const selectedCdn = computed(() => {
  if (!selectedCdnName.value) return null;
  return cdnList.value.find(item => item.name === selectedCdnName.value);
});

const totalCnameCount = computed(() => {
  return cdnList.value.reduce((acc, curr) => acc + (curr.cname_domain || []).length, 0);
});

const totalIpCount = computed(() => {
  return cdnList.value.reduce((acc, curr) => acc + (curr.ip_cidr || []).length, 0);
});

const copyTextList = async (list, label = '内容') => {
  if (!list || !list.length) {
    message.warning(`${label}暂无数据`);
    return;
  }
  const ok = await copyText(list.join('\n'));
  if (ok) {
    message.success(`${label}已复制到剪贴板！`);
  } else {
    message.error('复制失败，请手动选择复制');
  }
};

const cdnDrawerVisible = ref(false);
const isEditingCdn = ref(false);
const currentCdnForm = reactive({
  name: '',
  cnameText: '',
  ipText: ''
});
const currentEditIndex = ref(-1);

const openCdnDrawer = () => {
  isEditingCdn.value = false;
  currentEditIndex.value = -1;
  currentCdnForm.name = '';
  currentCdnForm.cnameText = '';
  currentCdnForm.ipText = '';
  cdnDrawerVisible.value = true;
};

const editSelectedCdn = () => {
  if (!selectedCdn.value) return;
  isEditingCdn.value = true;
  currentEditIndex.value = cdnList.value.findIndex(c => c.name === selectedCdn.value.name);
  currentCdnForm.name = selectedCdn.value.name;
  currentCdnForm.cnameText = (selectedCdn.value.cname_domain || []).join('\n');
  currentCdnForm.ipText = (selectedCdn.value.ip_cidr || []).join('\n');
  cdnDrawerVisible.value = true;
};

const deleteSelectedCdn = () => {
  if (!selectedCdn.value) return;
  const index = cdnList.value.findIndex(c => c.name === selectedCdn.value.name);
  if (index > -1) {
    cdnList.value.splice(index, 1);
    selectedCdnName.value = '';
    message.success('已删除，请记得保存全量更改');
  }
};

const resetCdnForm = () => {
  cdnDrawerVisible.value = false;
};

const submitCdnDrawer = () => {
  if (!currentCdnForm.name.trim()) {
    message.warning('请输入 CDN 名称');
    return;
  }
  const cname_domain = currentCdnForm.cnameText.split('\n').map(s => s.trim()).filter(s => s);
  const ip_cidr = currentCdnForm.ipText.split('\n').map(s => s.trim()).filter(s => s);

  // IP / 网段格式校验（IPv4 或 IPv4 CIDR），阻断明显非法输入写入全局探测配置
  const cidrRe = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/;
  const invalidCidr = ip_cidr.filter(cidr => {
    if (!cidrRe.test(cidr)) return true;
    const parts = cidr.split('/');
    const octets = parts[0].split('.').map(Number);
    if (octets.some(o => o < 0 || o > 255)) return true;
    if (parts[1] && (parseInt(parts[1]) < 0 || parseInt(parts[1]) > 32)) return true;
    return false;
  });
  if (invalidCidr.length > 0) {
    message.error(`IP 格式不合法 (如 ${invalidCidr[0]})，应为 IPv4 地址或 CIDR 网段，例如 1.1.1.1 或 103.21.244.0/22`);
    return;
  }
  // CNAME 后缀校验：不允许空白与路径分隔符
  const invalidCname = cname_domain.filter(d => /[\s/\\]/.test(d));
  if (invalidCname.length > 0) {
    message.error(`CNAME 后缀格式不合法 (如 ${invalidCname[0]})，应为纯域名后缀`);
    return;
  }

  if (isEditingCdn.value && currentEditIndex.value > -1) {
    cdnList.value[currentEditIndex.value] = {
      name: currentCdnForm.name.trim(),
      cname_domain,
      ip_cidr
    };
    selectedCdnName.value = currentCdnForm.name.trim();
  } else {
    if (cdnList.value.find(c => c.name === currentCdnForm.name.trim())) {
      message.warning('该 CDN 名称已存在');
      return;
    }
    cdnList.value.unshift({
      name: currentCdnForm.name.trim(),
      cname_domain,
      ip_cidr
    });
    selectedCdnName.value = currentCdnForm.name.trim();
  }
  cdnDrawerVisible.value = false;
};


// 拉取 CDN 列表
const fetchCdnList = async () => {
  cdnLoading.value = true;
  try {
    const res = await request.get('/api/cdn_dict/list');
    if (res.code === 200) {
      cdnList.value = res.data || [];
      originalCdnList.value = JSON.parse(JSON.stringify(cdnList.value));
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

// 保存全量数据到服务器
const saveCdnData = async () => {
  cdnSaveLoading.value = true;
  try {
    const res = await request.post('/api/cdn_dict/save', {
      data: cdnList.value
    });
    if (res.code === 200) {
      message.success('全量保存成功！');
      originalCdnList.value = JSON.parse(JSON.stringify(cdnList.value));
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
const performanceForm = ref({ celery_heavy_concurrency: 2, celery_light_concurrency: 2, osint_concurrency: 1 });
const performanceLoading = ref(false);
const performanceSaveLoading = ref(false);

const fetchPerformanceConfig = async () => {
  performanceLoading.value = true;
  try {
    const res = await request.get('/api/system_config/performance');
    if (res.code === 200) {
      performanceForm.value.celery_heavy_concurrency = res.data.celery_heavy_concurrency || 2;
      performanceForm.value.celery_light_concurrency = res.data.celery_light_concurrency || 3;
      performanceForm.value.osint_concurrency = res.data.osint_concurrency || 1;
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
      celery_light_concurrency: performanceForm.value.celery_light_concurrency,
      osint_concurrency: performanceForm.value.osint_concurrency
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

const fetchBruteDictList = async (showLoading = true) => {
  if (showLoading) bruteLoading.value = true;
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
    if (showLoading) bruteLoading.value = false;
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
const updatePollInterval = ref(null); // 🛠️ 修复：声明轮询定时器句柄
const logByteOffset = ref(0);         // 🛠️ 增量 Byte-Offset 偏移量指针
const updateFinished = ref(false);
const terminalRef = ref(null);
const updateButtonLoading = ref(false);
const updateHasError = ref(false);
const updateOfflineNotices = ref('');

const renderedReleaseNotes = computed(() => {
  if (!releaseNotes.value) return '';
  let html = releaseNotes.value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  
  html = html.replace(/^### (.*$)/gim, '<h4 style="margin: 12px 0 6px 0; font-weight: 600; font-size: 13px; color: var(--arl-text-color);">$1</h4>');
  html = html.replace(/^## (.*$)/gim, '<h3 style="margin: 14px 0 8px 0; font-weight: 700; font-size: 14px; color: var(--arl-text-color);">$1</h3>');
  html = html.replace(/^# (.*$)/gim, '<h2 style="margin: 16px 0 8px 0; font-weight: 700; font-size: 15px; color: var(--arl-text-color);">$1</h2>');
  
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong style="font-weight: 600;">$1</strong>');
  html = html.replace(/`([^`]+)`/g, '<code style="background: rgba(0,0,0,0.06); padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 12px;">$1</code>');
  
  html = html.replace(/^\s*-\s+(.*$)/gim, '<li style="margin-left: 18px; line-height: 1.8; list-style-type: disc;">$1</li>');
  html = html.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li style="margin-left: 18px; line-height: 1.8; list-style-type: decimal;">$2</li>');
  
  html = html.replace(/\n\n/g, '<div style="height: 6px;"></div>');
  html = html.replace(/\n/g, '<br/>');
  html = html.replace(/<br\/>\s*<li/g, '<li').replace(/<\/li>\s*<br\/>/g, '</li>');
  
  return html;
});

const checkVersion = async (force = false) => {
  try {
    const res = await request.get('/api/system_config/check_update', { params: force ? { refresh: 1 } : {} });
    if (res.code === 200 && res.data) {
      localVersion.value = res.data.local_version || '未知版本';
      remoteVersion.value = res.data.remote_version || localVersion.value;
      hasNewVersion.value = Boolean(res.data.has_new_version);
      releaseNotes.value = res.data.release_notes || '';
    }
  } catch (e) {
    console.error('检查版本更新失败', e);
    // 降级使用 local_version 接口兜底
    try {
      const localRes = await request.get('/api/system_config/local_version');
      if (localRes.code === 200) {
        localVersion.value = localRes.data.version;
      }
    } catch (_) {}
  }
};

const handleStartUpdateClick = async () => {
  try {
    const res = await request.get('/api/system_config/running_task_count');
    const runningCount = res.code === 200 && res.data ? (res.data.running_count || 0) : 0;
    if (runningCount > 0) {
      Modal.confirm({
        title: '⚠️ 正在运行的任务告警',
        content: `系统检测到当前有 ${runningCount} 个正在执行的扫描任务。执行系统更新将重启后台 Worker 容器并中断这些任务（重启后任务将标记为中断状态）。是否确认继续更新？`,
        okText: '确认强制中断并更新',
        okType: 'danger',
        cancelText: '取消并等待任务完成',
        onOk: () => {
          startUpdate();
        }
      });
      return;
    }
  } catch (e) {
    console.warn('获取运行中任务数量失败，跳过前置阻断', e);
  }
  startUpdate();
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
    logByteOffset.value = 0;
    
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

    // 2. 开始增量轮询日志
    if (updatePollInterval.value) {
      clearInterval(updatePollInterval.value);
    }
    
    updatePollInterval.value = setInterval(async () => {
      try {
        const pollUrl = `/update_stream/log?offset=${logByteOffset.value}`;
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
            updateOfflineNotices.value = '⏳ 网关重启中或服务暂时不可达，正在等待网络恢复...\n';
            updateLogs.value += '⏳ 网关重启中或服务暂时不可达，正在等待网络恢复...\n';
            scrollToBottom();
          }
          return;
        }

        const contentType = logRes.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          const data = await logRes.json();
          logByteOffset.value = data.offset !== undefined ? data.offset : logByteOffset.value;
          if (data.chunk) {
            updateLogs.value += data.chunk;
            scrollToBottom();
          }
          
          // 动态解析进度
          if (updateLogs.value.includes('后台任务已启动')) updateProgress.value = Math.max(updateProgress.value, 20);
          if (updateLogs.value.includes('基础架构同步完毕')) updateProgress.value = Math.max(updateProgress.value, 40);
          if (updateLogs.value.includes('正在从阿里云镜像库极速拉取')) updateProgress.value = Math.max(updateProgress.value, 60);
          if (updateLogs.value.includes('开始执行 start-')) updateProgress.value = Math.max(updateProgress.value, 80);
          if (updateLogs.value.includes('后端服务已完全就绪')) updateProgress.value = Math.max(updateProgress.value, 95);

          if (data.done) {
            clearInterval(updatePollInterval.value);
            updateProgress.value = 100;
            updateFinished.value = true;
            updateOfflineNotices.value = '';
            message.success('🎉 系统更新成功！请点击下方按钮重新加载页面。', 5);
          } else if (data.error) {
            clearInterval(updatePollInterval.value);
            updateFinished.value = true;
            updateHasError.value = true;
            updateOfflineNotices.value = '';
            message.error('❌ 系统更新遇到错误，请查看日志！', 8);
          }
        } else {
          // 纯文本兜底
          const logText = await logRes.text();
          updateLogs.value = logText;
          scrollToBottom();
          if (logText.includes('[DONE]')) {
            clearInterval(updatePollInterval.value);
            updateProgress.value = 100;
            updateFinished.value = true;
            message.success('🎉 系统更新成功！', 5);
          } else if (logText.includes('[ERROR]')) {
            clearInterval(updatePollInterval.value);
            updateFinished.value = true;
            updateHasError.value = true;
            message.error('❌ 系统更新遇到错误！', 8);
          }
        }
      } catch (err) {
        // 网络请求失败（容器重启时）忽略错误，继续轮询
        if (!updateOfflineNotices.value.includes('等待容器恢复')) {
          updateOfflineNotices.value = '⏳ 网络暂时断开，正在等待容器恢复...\n';
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
    updatePollInterval.value = null;
  }
});
</script>

<style scoped>
/* 可以在此处添加自定义样式 */

.cdn-textarea {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  padding: 16px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 14px;
  color: #a6e22e;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
.cdn-textarea::placeholder {
  color: rgba(255, 255, 255, 0.2);
}
.purple-glow:hover {
  box-shadow: 0 12px 48px rgba(114, 46, 209, 0.25) !important;
}
.pulse-btn {
  animation: btnPulse 2s infinite;
}
@keyframes btnPulse {
  0% { box-shadow: 0 0 0 0 rgba(24, 144, 255, 0.7); }
  70% { box-shadow: 0 0 0 10px rgba(24, 144, 255, 0); }
  100% { box-shadow: 0 0 0 0 rgba(24, 144, 255, 0); }
}

/* 字典管理现代化升级样式 */
.custom-list-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid transparent;
  color: var(--arl-text-color);
}
.custom-list-item:hover {
  background: var(--arl-bg-light);
  transform: translateX(4px);
}
.custom-list-item.is-active {
  background: var(--arl-theme-color);
  color: #fff;
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
}
.custom-list-item.is-active .dict-title,
.custom-list-item.is-active .dict-subtitle {
  color: #fff;
}
.custom-list-item.is-active .dict-badge {
  background: rgba(255,255,255,0.2);
  color: #fff;
}
.dict-subtitle {
  font-size: 12px;
  opacity: 0.65;
}
.dict-badge {
  font-size: 10px;
  background: rgba(0,0,0,0.05);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--arl-text-color);
  opacity: 0.6;
}
.hide-scrollbar::-webkit-scrollbar {
  display: none;
}
.hide-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

/* 仪表盘（空状态）样式 */
.health-dashboard-wrapper {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  overflow: hidden;
}
.health-dashboard-bg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: radial-gradient(circle at 50% -20%, rgba(24, 144, 255, 0.08), transparent 60%),
              radial-gradient(circle at -20% 80%, rgba(114, 46, 209, 0.05), transparent 50%);
  pointer-events: none;
}
.health-content {
  position: relative;
  z-index: 1;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.health-icon-pulse {
  animation: float 4s ease-in-out infinite;
  margin-bottom: 8px;
}
@keyframes float {
  0% { transform: translateY(0px); }
  50% { transform: translateY(-10px); }
  100% { transform: translateY(0px); }
}
.health-title {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
  letter-spacing: 0.5px;
}
.health-stats-container {
  display: flex;
  gap: 24px;
  margin-top: 16px;
}
.health-stat-card {
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 16px;
  padding: 24px 40px;
  min-width: 180px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.02), inset 0 1px 0 rgba(255,255,255,1);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.health-stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,1);
}
.stat-value {
  font-size: 36px;
  font-weight: 800;
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  line-height: 1.2;
}
.primary-stat .stat-value {
  background-image: linear-gradient(135deg, #1890ff 0%, #36cfc9 100%);
}
.warning-stat .stat-value {
  background-image: linear-gradient(135deg, #fa8c16 0%, #ffc53d 100%);
}
.stat-label {
  font-size: 14px;
  color: #64748b;
  margin-top: 8px;
  font-weight: 500;
}
.health-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 32px;
  color: #94a3b8;
  font-size: 13px;
  background: rgba(255,255,255,0.5);
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.6);
}
.pulse-dot {
  width: 8px;
  height: 8px;
  background: #52c41a;
  border-radius: 50%;
  box-shadow: 0 0 0 0 rgba(82, 196, 26, 0.7);
  animation: dotPulse 2s infinite;
}
@keyframes dotPulse {
  0% { box-shadow: 0 0 0 0 rgba(82, 196, 26, 0.7); }
  70% { box-shadow: 0 0 0 8px rgba(82, 196, 26, 0); }
  100% { box-shadow: 0 0 0 0 rgba(82, 196, 26, 0); }
}

/* 代码区还原极简素雅风格 */
.native-preview-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--arl-bg-white);
  position: relative;
  overflow: hidden;
}
.native-toolbar {
  padding: 16px 24px;
  border-bottom: 1px solid var(--arl-border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--arl-bg-white);
  min-height: 64px;
}
.native-preview-area {
  flex: 1;
  display: flex;
  overflow-y: auto;
  padding: 24px;
  background: var(--arl-bg-light); /* 非常浅的底色区分 */
}
.native-code-wrapper {
  flex: 1;
  display: flex;
  background: var(--arl-bg-white);
  border: 1px solid var(--arl-border-color);
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.02);
  font-family: 'Fira Code', 'SFMono-Regular', Consolas, Menlo, monospace;
  font-size: 13px;
  line-height: 1.6;
}
.native-line-numbers {
  display: flex;
  flex-direction: column;
  padding-right: 16px;
  border-right: 1px solid var(--arl-border-color);
  margin-right: 16px;
  color: var(--arl-text-color);
  opacity: 0.35;
  text-align: right;
  user-select: none;
  min-width: 40px;
}
.line-number {
  height: 21px; /* 与 line-height: 1.6 和 font-size: 13px 对应，大致是 20.8px */
}
.native-code-content {
  flex: 1;
  min-width: 0;
}
.code-text {
  margin: 0;
  color: var(--arl-text-color);
  opacity: 0.85;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
}
.empty-code {
  color: var(--arl-text-color);
  opacity: 0.3;
  font-style: italic;
  padding-top: 20px;
  text-align: center;
}
.code-limit-hint {
  color: var(--arl-theme-color);
  margin-top: 24px;
  font-style: italic;
  border-top: 1px dashed var(--arl-border-color);
  padding-top: 16px;
  opacity: 0.7;
}

@keyframes btn-breathing {
  0% { box-shadow: 0 0 0 0 rgba(82, 196, 26, 0.4); }
  70% { box-shadow: 0 0 0 6px rgba(82, 196, 26, 0); }
  100% { box-shadow: 0 0 0 0 rgba(82, 196, 26, 0); }
}
.breathing-btn {
  animation: btn-breathing 2s infinite;
}
</style>
