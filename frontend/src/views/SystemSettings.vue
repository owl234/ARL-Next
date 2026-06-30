<template>
  <div style="padding: 24px; background: #fff; min-height: 100%;">
    <h2 style="margin-bottom: 24px;">系统设置</h2>
    
    <a-tabs v-model:activeKey="activeKey">
      <!-- 字典管理 Tab -->
      <a-tab-pane key="dictionary" tab="字典管理">
        <a-spin :spinning="loading">
          <div style="display: flex; gap: 24px; min-height: 500px;">
            <!-- 左侧一键选择菜单 -->
            <div style="width: 280px; flex-shrink: 0;">
              <a-menu 
                v-model:selectedKeys="selectedDictKeys" 
                mode="inline" 
                style="border-right: 1px solid #f0f0f0;"
                @select="handleMenuSelect"
              >
                <a-menu-item-group v-for="(dicts, cat) in groupedDicts" :key="cat" :title="cat">
                  <a-menu-item v-for="dict in dicts" :key="dict.name">
                    <span style="font-size: 14px;">{{ dict.name }}</span>
                    <span style="color: #aaa; font-size: 12px; margin-left: 8px;">{{ (dict.size / 1024).toFixed(1) }} KB</span>
                  </a-menu-item>
                </a-menu-item-group>
              </a-menu>
            </div>

            <!-- 右侧操作区 -->
            <div style="flex: 1; max-width: 800px;" v-if="selectedDict">
              <!-- 搜索功能 -->
              <div style="margin-bottom: 20px;">
                <span style="margin-right: 16px; font-weight: bold;">字典条目搜索:</span>
                <a-input-search
                  v-model:value="searchKeyword"
                  placeholder="精确匹配搜索条目是否存在"
                  style="width: 300px"
                  @search="handleSearch"
                  :loading="searchLoading"
                >
                  <template #enterButton>
                    <a-button type="primary">搜索</a-button>
                  </template>
                </a-input-search>
                <div v-if="searchResult !== null" style="margin-top: 8px;">
                  <div v-if="searchResult.length > 0" style="margin-bottom: 8px; color: #52c41a;">
                    ✅ 找到 {{ searchResult.length }} 条包含该关键词的条目:
                  </div>
                  <div v-else style="margin-bottom: 8px; color: #ff4d4f;">
                    ❌ 未找到包含该关键词的条目
                  </div>
                  
                  <div v-if="searchResult.length > 0" style="max-height: 200px; overflow-y: auto; background: #fafafa; padding: 12px; border: 1px solid #f0f0f0; border-radius: 4px;">
                    <div v-for="(item, idx) in searchResult" :key="idx" style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; padding-bottom: 4px; border-bottom: 1px solid #f5f5f5;">
                      <span style="font-family: monospace; word-break: break-all; font-size: 13px;">{{ item }}</span>
                      <a-button 
                        type="link" 
                        danger 
                        size="small" 
                        @click="handleDeleteSingle(item)" 
                        :loading="deleteLoading"
                      >
                        删除
                      </a-button>
                    </div>
                  </div>
                  <div v-if="searchResult.length === 100" style="color: #faad14; font-size: 12px; margin-top: 4px;">
                    * 仅显示前 100 条匹配项，请细化搜索词。
                  </div>
                </div>
              </div>

              <!-- 预览区 -->
              <div style="margin-bottom: 24px;">
                <div style="margin-bottom: 8px; font-weight: bold;">
                  字典内容预览 (显示前 {{ previewLimit }} 行, 总行数: {{ totalLines }}):
                </div>
                <a-textarea 
                  v-model:value="previewContent" 
                  :rows="12" 
                  readonly 
                  style="background-color: #f5f5f5;"
                />
              </div>

              <!-- 新增与批量删除区 -->
              <div style="margin-bottom: 24px;">
                <div style="margin-bottom: 8px; font-weight: bold;">新增 / 批量删除条目 (每行一个):</div>
                <a-textarea 
                  v-model:value="newEntries" 
                  :rows="6" 
                  placeholder="输入要操作的条目，点击“追加保存”或“批量删除”..." 
                />
                <div style="margin-top: 16px; display: flex; gap: 12px;">
                  <a-button type="primary" @click="handleAppend" :loading="submitLoading" :disabled="!newEntries.trim()">
                    追加保存
                  </a-button>
                  <a-button danger @click="handleDeleteBatch" :loading="deleteLoading" :disabled="!newEntries.trim()">
                    批量删除
                  </a-button>
                </div>
              </div>
            </div>
            
            <div style="flex: 1; display: flex; align-items: center; justify-content: center; color: #999; font-size: 16px;" v-else>
              👈 请在左侧菜单点击选择一个字典文件
            </div>
          </div>
        </a-spin>
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
          <a-button type="primary" style="background-color: #52c41a; border-color: #52c41a;" @click="saveCdnData" :loading="cdnSaveLoading">保存全量更改到服务器</a-button>
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
        <div style="max-width: 800px;">
          <div style="margin-bottom: 16px; color: #888;">
            此处的配置项用于全局的安全限制，防止系统对指定范围的 IP 或域名发起扫描。保存后立即生效，无需重启。
          </div>
          <a-spin :spinning="securityLoading">
            <a-form layout="vertical" style="margin-top: 20px;">
              <a-form-item label="IP 黑名单 (支持 CIDR，如 127.0.0.0/8, 192.168.0.0/16，每行一个)">
                <a-textarea v-model:value="securityForm.blackIpsText" :rows="8" placeholder="例如：\n127.0.0.0/8\n10.0.0.0/8" />
              </a-form-item>
              
              <a-form-item label="禁止扫描域名 (支持后缀匹配，如 gov.cn, edu.cn，每行一个)">
                <a-textarea v-model:value="securityForm.forbiddenDomainsText" :rows="8" placeholder="例如：\ngov.cn\nedu.cn" />
              </a-form-item>

              <a-form-item>
                <a-button type="primary" style="background-color: #52c41a; border-color: #52c41a;" @click="saveSecurityPolicy" :loading="securitySaveLoading">
                  保存安全策略
                </a-button>
              </a-form-item>
            </a-form>
          </a-spin>
        </div>
      </a-tab-pane>
      <!-- 性能与并发配置 Tab -->
      <a-tab-pane key="performance" tab="性能与并发配置" force-render>
        <div style="max-width: 800px;">
          <div style="margin-bottom: 16px; color: #888;">
            此处的配置用于调整扫描节点 (Worker) 的任务并发处理能力。修改保存后，需要手动重启底层的 Celery Worker 进程或容器以使新配置生效。
          </div>
          <a-spin :spinning="performanceLoading">
            <a-form layout="vertical" style="margin-top: 20px;">
              <a-form-item label="Celery 并发数 (Concurrency)">
                <a-input-number v-model:value="performanceForm.celeryConcurrency" :min="1" :max="128" style="width: 200px" />
                <div style="margin-top: 8px; color: #aaa; font-size: 13px;">
                  设置过大可能会导致内存溢出或目标服务器宕机，建议根据机器配置调整（每增加1个并发约增加 100MB 内存消耗，默认为 2）。
                </div>
              </a-form-item>

              <a-form-item>
                <a-button type="primary" style="background-color: #52c41a; border-color: #52c41a;" @click="savePerformanceConfig" :loading="performanceSaveLoading">
                  保存性能配置
                </a-button>
              </a-form-item>
            </a-form>
          </a-spin>
        </div>
      </a-tab-pane>

      <!-- 三方 API 配置 Tab -->
      <a-tab-pane key="api_config" tab="三方 API 配置" force-render>
        <div style="max-width: 900px;">
          <div style="margin-bottom: 16px; color: #888;">
            此处的配置项用于三方情报或搜索接口的 API 凭证管理，配置保存后将动态应用至对应的域名/资产收集任务。
          </div>
          <a-spin :spinning="generalLoading">
            <a-form layout="vertical">
              <a-row :gutter="24">
                <a-col :span="12">
                  <a-form-item label="FOFA URL">
                    <a-input v-model:value="generalForm.fofa_url" placeholder="例如：https://fofa.info" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="FOFA KEY">
                    <a-input-password v-model:value="generalForm.fofa_key" placeholder="请输入您的 FOFA API KEY" />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-row :gutter="24">
                <a-col :span="12">
                  <a-form-item label="FOFA 最大查询页数 (Max Page)">
                    <a-input-number v-model:value="generalForm.fofa_max_page" :min="1" style="width: 100%" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="FOFA 每页条数 (Page Size)">
                    <a-input-number v-model:value="generalForm.fofa_page_size" :min="1" style="width: 100%" />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-row :gutter="24">
                <a-col :span="24">
                  <a-form-item label="GitHub Token (监控任务调用)">
                    <a-input-password v-model:value="generalForm.github_token" placeholder="请输入您的 GitHub Personal Access Token" />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-form-item label="域名收集插件配置 (QUERY_PLUGIN)">
                <div style="background: #fafafa; border: 1px solid #f0f0f0; border-radius: 4px; padding: 16px;">
                  <a-row :gutter="[16, 16]">
                    <a-col :span="8" v-for="(conf, pluginName) in generalForm.query_plugin_config" :key="pluginName">
                      <div style="border: 1px solid #e8e8e8; background: #fff; padding: 12px; border-radius: 4px; min-height: 100px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                          <span style="font-weight: bold; text-transform: uppercase;">{{ pluginName }}</span>
                          <a-checkbox v-model:checked="conf.enable">启用</a-checkbox>
                        </div>
                        <a-input 
                          v-if="conf.hasOwnProperty('api_key')" 
                          v-model:value="conf.api_key" 
                          placeholder="API Key" 
                          size="small" 
                        />
                        <div v-if="pluginName === 'hunter_qax'" style="margin-top: 4px; display: flex; gap: 4px;">
                          <a-input-number v-model:value="conf.max_page" placeholder="Max Page" size="small" style="flex: 1;" />
                          <a-input-number v-model:value="conf.page_size" placeholder="Page Size" size="small" style="flex: 1;" />
                        </div>
                        <div v-if="pluginName === 'certspotter'" style="margin-top: 4px; display: flex; gap: 4px;">
                          <a-input-number v-model:value="conf.max_page" placeholder="Max Page" size="small" style="width: 100%;" />
                        </div>
                        <a-input 
                          v-if="conf.hasOwnProperty('quake_token')" 
                          v-model:value="conf.quake_token" 
                          placeholder="Quake Token" 
                          size="small" 
                        />
                        <div v-if="pluginName === 'passivetotal'" style="margin-top: 4px; display: flex; flex-direction: column; gap: 4px;">
                          <a-input v-model:value="conf.auth_email" placeholder="Auth Email" size="small" style="margin-bottom: 4px;" />
                          <a-input v-model:value="conf.auth_key" placeholder="Auth Key" size="small" />
                        </div>
                      </div>
                    </a-col>
                  </a-row>
                </div>
              </a-form-item>

              <a-form-item>
                <a-button type="primary" style="background-color: #52c41a; border-color: #52c41a;" @click="saveGeneralConfig" :loading="generalSaveLoading">
                  保存三方 API 配置
                </a-button>
              </a-form-item>
            </a-form>
          </a-spin>
        </div>
      </a-tab-pane>

      <!-- 消息推送与回调 Tab -->
      <a-tab-pane key="message_push" tab="消息推送与回调" force-render>
        <div style="max-width: 900px;">
          <div style="margin-bottom: 16px; color: #888;">
            此处的配置项用于监控任务结束后的结果推送（支持钉钉、飞书、企业微信和 SMTP 邮件）以及自动化 Webhook 接口回调。
          </div>
          <a-spin :spinning="generalLoading">
            <a-form layout="vertical">
              <a-collapse v-model:activeKey="activePushPanels" style="margin-bottom: 24px;">
                <a-collapse-panel key="dingding" header="钉钉推送配置">
                  <a-row :gutter="24">
                    <a-col :span="12">
                      <a-form-item label="Webhook Access Token">
                        <a-input v-model:value="generalForm.dingding.access_token" placeholder="钉钉机器人 Token" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="12">
                      <a-form-item label="Webhook Secret (加签安全设置)">
                        <a-input-password v-model:value="generalForm.dingding.secret" placeholder="钉钉机器人 Secret" />
                      </a-form-item>
                    </a-col>
                  </a-row>
                </a-collapse-panel>

                <a-collapse-panel key="feishu" header="飞书推送配置">
                  <a-row :gutter="24">
                    <a-col :span="12">
                      <a-form-item label="Webhook URL">
                        <a-input v-model:value="generalForm.feishu.webhook_url" placeholder="飞书自定义机器人 Webhook 地址" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="12">
                      <a-form-item label="Webhook Secret (安全校验)">
                        <a-input-password v-model:value="generalForm.feishu.secret" placeholder="签名校验密钥" />
                      </a-form-item>
                    </a-col>
                  </a-row>
                </a-collapse-panel>

                <a-collapse-panel key="wxwork" header="企业微信推送配置">
                  <a-form-item label="Webhook URL">
                    <a-input v-model:value="generalForm.wxwork.webhook_url" placeholder="企业微信群机器人 Webhook 地址" />
                  </a-form-item>
                </a-collapse-panel>

                <a-collapse-panel key="email" header="邮件推送配置">
                  <a-row :gutter="24">
                    <a-col :span="12">
                      <a-form-item label="SMTP 主机地址 (SMTP Host)">
                        <a-input v-model:value="generalForm.email.host" placeholder="例如：smtp.qq.com" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="12">
                      <a-form-item label="SMTP 端口 (SMTP Port)">
                        <a-input-number v-model:value="generalForm.email.port" placeholder="例如：465" style="width: 100%;" />
                      </a-form-item>
                    </a-col>
                  </a-row>
                  <a-row :gutter="24">
                    <a-col :span="12">
                      <a-form-item label="发件人邮箱用户名 (Username)">
                        <a-input v-model:value="generalForm.email.username" placeholder="请输入账号，通常为发信邮箱地址" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="12">
                      <a-form-item label="发件人授权码密码 (Password)">
                        <a-input-password v-model:value="generalForm.email.password" placeholder="授权码密码" />
                      </a-form-item>
                    </a-col>
                  </a-row>
                  <a-form-item label="收件人邮箱列表 (To，多个用英文逗号分隔)">
                    <a-input v-model:value="generalForm.email.to" placeholder="例如：receiver1@test.com,receiver2@test.com" />
                  </a-form-item>
                </a-collapse-panel>

                <a-collapse-panel key="webhook" header="系统全局监控 Webhook 自动化回调">
                  <a-row :gutter="24">
                    <a-col :span="12">
                      <a-form-item label="回调 POST URL">
                        <a-input v-model:value="generalForm.webhook_url" placeholder="监控结束后接收 JSON 数据的接口 URL" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="12">
                      <a-form-item label="身份校验 Token">
                        <a-input v-model:value="generalForm.webhook_token" placeholder="校验身份的 Token，将带在 Header 字段" />
                      </a-form-item>
                    </a-col>
                  </a-row>
                </a-collapse-panel>
              </a-collapse>

              <a-form-item>
                <a-button type="primary" style="background-color: #52c41a; border-color: #52c41a;" @click="saveGeneralConfig" :loading="generalSaveLoading">
                  保存消息推送与回调
                </a-button>
              </a-form-item>
            </a-form>
          </a-spin>
        </div>
      </a-tab-pane>

      <!-- 高级扫描与环境配置 Tab -->
      <a-tab-pane key="system_general" tab="高级扫描与环境配置" force-render>
        <div style="max-width: 900px;">
          <div style="margin-bottom: 16px; color: #888;">
            此处的配置项用于代理、全局端口字典及扫描线程的调优。底部只读展示系统底层关键连接。
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
                <div style="background: #fafafa; border: 1px solid #f0f0f0; border-radius: 4px; padding: 16px;">
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

              <a-form-item>
                <a-button type="primary" style="background-color: #52c41a; border-color: #52c41a;" @click="saveGeneralConfig" :loading="generalSaveLoading">
                  保存高级配置
                </a-button>
              </a-form-item>
            </a-form>
          </a-spin>
        </div>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { message } from 'ant-design-vue';
import request from '@/utils/request';

const activeKey = ref('dictionary');
const loading = ref(false);
const searchLoading = ref(false);
const submitLoading = ref(false);
const deleteLoading = ref(false);

const generalLoading = ref(false);
const generalSaveLoading = ref(false);
const activePushPanels = ref(['dingding']);

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
  email: { host: '', port: null, username: '', password: '', to: '' },
  query_plugin_config: {}
});

const fetchGeneralConfig = async () => {
  generalLoading.value = true;
  try {
    const res = await request.get('/api/system_config/general');
    if (res.code === 200) {
      generalForm.value = res.data;
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
      fetchGeneralConfig(); // 重新拉取确认
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
const groupedDicts = computed(() => {
  const groups = {};
  dictList.value.forEach(dict => {
    const cat = dict.category || '其他 (Others)';
    if (!groups[cat]) {
      groups[cat] = [];
    }
    groups[cat].push(dict);
  });
  return groups;
});
const selectedDictKeys = ref([]);
const selectedDict = ref(null);

const previewContent = ref('');
const totalLines = ref(0);
const previewLimit = ref(500);

const searchKeyword = ref('');
const searchResult = ref(null);

const newEntries = ref('');

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

// 获取预览
const fetchPreview = async (name) => {
  if (!name) return;
  loading.value = true;
  try {
    const res = await request.get(`/api/dictionary/preview`, {
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

// 左侧菜单选择字典
const handleMenuSelect = ({ key }) => {
  selectedDict.value = key;
  searchKeyword.value = '';
  searchResult.value = null;
  newEntries.value = '';
  fetchPreview(key);
};

// 搜索功能
const handleSearch = async () => {
  if (!searchKeyword.value.trim()) {
    message.warning('请输入搜索关键词');
    return;
  }
  searchLoading.value = true;
  try {
    const res = await request.get('/api/dictionary/search', {
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

// 追加条目
const handleAppend = async () => {
  if (!newEntries.value.trim()) return;
  
  submitLoading.value = true;
  try {
    const res = await request.post('/api/dictionary/append', {
      name: selectedDict.value,
      content: newEntries.value
    });
    
    if (res.code === 200) {
      message.success(`保存成功！共提交 ${res.data.total_submitted} 项，实际追加新条目 ${res.data.added} 项。`);
      newEntries.value = ''; // 清空输入框
      // 刷新预览和大小
      fetchDictList();
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
  // 删除成功后，从搜索结果列表中移除该条目
  if (searchResult.value) {
    searchResult.value = searchResult.value.filter(x => x !== item);
  }
};

// 公共删除逻辑
const deleteEntries = async (content) => {
  deleteLoading.value = true;
  try {
    const res = await request.post('/api/dictionary/delete_entries', {
      name: selectedDict.value,
      content: content
    });
    
    if (res.code === 200) {
      message.success(`删除成功！尝试删除 ${res.data.total_submitted} 项，实际成功删除 ${res.data.deleted} 项。`);
      newEntries.value = '';
      // 刷新预览和大小
      fetchDictList();
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
const performanceForm = ref({ celeryConcurrency: 2 });
const performanceLoading = ref(false);
const performanceSaveLoading = ref(false);

const fetchPerformanceConfig = async () => {
  performanceLoading.value = true;
  try {
    const res = await request.get('/api/system_config/performance');
    if (res.code === 200) {
      performanceForm.value.celeryConcurrency = res.data.celery_concurrency || 2;
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
      celery_concurrency: performanceForm.value.celeryConcurrency
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

onMounted(() => {
  fetchDictList();
  fetchCdnList();
  fetchSecurityPolicy();
  fetchPerformanceConfig();
  fetchGeneralConfig();
});
</script>

<style scoped>
/* 可以在此处添加自定义样式 */
</style>
