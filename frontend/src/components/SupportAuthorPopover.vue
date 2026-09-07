<template>
  <a-popover
    v-model:open="visible"
    trigger="hover"
    placement="bottomRight"
    overlay-class-name="support-author-popover-overlay"
    :mouse-enter-delay="0.15"
    :mouse-leave-delay="0.25"
  >
    <!-- 顶部导航栏入口触发器 -->
    <div class="support-header-entry header-text-action" :class="{ 'is-active': visible }">
      <span class="support-heart-icon" :class="{ 'pulse-anim': SUPPORT_CONFIG.entry.showPulse }">
        {{ SUPPORT_CONFIG.entry.icon }}
      </span>
      <span class="support-entry-text">{{ SUPPORT_CONFIG.entry.text }}</span>
    </div>

    <!-- 浮层卡片内容 -->
    <template #content>
      <div class="support-popover-card">
        <!-- 卡片头部标题 -->
        <div class="support-card-header">
          <div class="support-card-title-row">
            <span class="support-sparkle">✨</span>
            <span class="support-card-title">支持 ARL-Next 持续进化</span>
          </div>
          <p class="support-card-desc">您的每一次关注、反馈与赞助，都是项目持续迭代的动力！</p>
        </div>

        <!-- 紧凑切换胶囊 Tabs -->
        <div class="support-tabs-bar">
          <button
            type="button"
            class="support-tab-btn"
            :class="{ active: activeTab === 'reward' }"
            @click="activeTab = 'reward'"
          >
            <CoffeeOutlined class="tab-icon" />
            <span>{{ SUPPORT_CONFIG.reward.tabTitle }}</span>
          </button>
          <button
            type="button"
            class="support-tab-btn"
            :class="{ active: activeTab === 'official' }"
            @click="activeTab = 'official'"
          >
            <NotificationOutlined class="tab-icon" />
            <span>{{ SUPPORT_CONFIG.official.tabTitle }}</span>
          </button>
          <button
            type="button"
            class="support-tab-btn"
            :class="{ active: activeTab === 'wechat' }"
            @click="activeTab = 'wechat'"
          >
            <WechatOutlined class="tab-icon" />
            <span>{{ SUPPORT_CONFIG.wechat.tabTitle }}</span>
          </button>
        </div>

        <!-- 卡片主体内容 -->
        <div class="support-card-body">
          <!-- 1. 赞助打赏面板 -->
          <div v-show="activeTab === 'reward'" class="support-panel fade-in">
            <div class="qrcode-wrapper">
              <img
                :src="rewardQrcode"
                alt="赞赏码"
                class="qrcode-img"
              />
            </div>
            <div class="support-panel-info">
              <div class="support-panel-title">{{ SUPPORT_CONFIG.reward.title }}</div>
              <p class="support-panel-desc">{{ SUPPORT_CONFIG.reward.desc }}</p>
              <div class="support-tip-tag">
                <GiftOutlined style="margin-right: 4px;" />
                {{ SUPPORT_CONFIG.reward.subText }}
              </div>
            </div>
          </div>

          <!-- 2. 官方公众号面板 -->
          <div v-show="activeTab === 'official'" class="support-panel fade-in">
            <div class="qrcode-wrapper">
              <img
                :src="mpQrcode"
                alt="公众号二维码"
                class="qrcode-img"
              />
            </div>
            <div class="support-panel-info">
              <div class="support-panel-title">
                <span>公众号：</span>
                <span class="highlight-text">{{ SUPPORT_CONFIG.official.name }}</span>
              </div>
              <p class="support-panel-desc">{{ SUPPORT_CONFIG.official.desc }}</p>
              <div class="support-tip-tag">
                <CheckCircleOutlined style="margin-right: 4px;" />
                {{ SUPPORT_CONFIG.official.subText }}
              </div>
            </div>
          </div>

          <!-- 3. 作者微信号/交流群面板 -->
          <div v-show="activeTab === 'wechat'" class="support-panel fade-in">
            <div class="qrcode-wrapper">
              <img
                :src="wechatQrcode"
                alt="微信二维码"
                class="qrcode-img"
              />
            </div>
            <div class="support-panel-info">
              <div class="wechat-copy-box">
                <span class="wechat-label">微信号：</span>
                <span class="wechat-id">{{ SUPPORT_CONFIG.wechat.wechatId }}</span>
                <a-tooltip :title="copied ? '已复制！' : '点击复制微信号'">
                  <button type="button" class="copy-wechat-btn" @click="handleCopyWechat">
                    <CheckOutlined v-if="copied" style="color: #52c41a; font-size: 13px;" />
                    <CopyOutlined v-else style="font-size: 13px;" />
                    <span>{{ copied ? '已复制' : '复制' }}</span>
                  </button>
                </a-tooltip>
              </div>
              <p class="support-panel-desc">{{ SUPPORT_CONFIG.wechat.desc }}</p>
              <div class="support-tip-tag">
                <UserAddOutlined style="margin-right: 4px;" />
                {{ SUPPORT_CONFIG.wechat.subText }}
              </div>
            </div>
          </div>
        </div>

        <!-- 卡片底部寄语 -->
        <div class="support-card-footer">
          <span>☕ 持续开源 · 用心维护 · 共同构建下一代资产测绘平台</span>
        </div>
      </div>
    </template>
  </a-popover>
</template>

<script setup>
import { ref, computed } from 'vue';
import { message } from 'ant-design-vue';
import {
  CoffeeOutlined,
  NotificationOutlined,
  WechatOutlined,
  CopyOutlined,
  CheckOutlined,
  GiftOutlined,
  CheckCircleOutlined,
  UserAddOutlined
} from '@ant-design/icons-vue';
import { SUPPORT_CONFIG } from '@/config/support';

const visible = ref(false);
const activeTab = ref(SUPPORT_CONFIG.defaultTab || 'reward');
const copied = ref(false);

// 动态匹配图片资源（优先加载用户放入的 png/jpg，无则使用 svg 矢量占位图）
const supportImages = import.meta.glob('@/assets/support/*.(png|jpg|jpeg|svg)', {
  eager: true,
  import: 'default'
});

const resolveImage = (baseName) => {
  const extensions = ['png', 'jpg', 'jpeg', 'svg'];
  const keys = Object.keys(supportImages);
  for (const ext of extensions) {
    const targetSuffix = `${baseName}.${ext}`;
    const matchedKey = keys.find(k => k.endsWith(targetSuffix));
    if (matchedKey) {
      return supportImages[matchedKey];
    }
  }
  return '';
};

const rewardQrcode = computed(() => resolveImage('reward'));
const mpQrcode = computed(() => resolveImage('mp'));
const wechatQrcode = computed(() => resolveImage('wechat'));

// 一键复制微信号（含 fallback 降级兼容）
const handleCopyWechat = async () => {
  const text = SUPPORT_CONFIG.wechat.wechatId;
  if (!text) return;

  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }
    copied.value = true;
    message.success(`作者微信号「${text}」已复制到剪贴板！`);
    setTimeout(() => {
      copied.value = false;
    }, 2500);
  } catch (err) {
    console.error('复制失败:', err);
    message.error('复制失败，请长按手动选择复制');
  }
};
</script>

<style scoped>
/* 导航栏触发入口 */
.support-header-entry {
  cursor: pointer;
  margin-right: 24px;
  display: inline-flex;
  align-items: center;
  user-select: none;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.25s ease;
  position: relative;
}

.support-heart-icon {
  display: inline-block;
  font-size: 16px;
  margin-right: 5px;
  line-height: 1;
  transform-origin: center;
}

.pulse-anim {
  animation: heartPulse 2.2s infinite ease-in-out;
  will-change: transform;
}

@keyframes heartPulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.92;
  }
  14% {
    transform: scale(1.18);
    opacity: 1;
  }
  28% {
    transform: scale(1);
    opacity: 0.92;
  }
  42% {
    transform: scale(1.12);
    opacity: 1;
  }
  70% {
    transform: scale(1);
    opacity: 0.92;
  }
}

.support-header-entry:hover .support-entry-text,
.support-header-entry.is-active .support-entry-text {
  color: var(--arl-theme-color);
}

.support-header-entry:hover .support-heart-icon {
  transform: scale(1.25);
  transition: transform 0.2s ease;
}

/* 浮层卡片整体 */
.support-popover-card {
  width: 320px;
  padding: 4px;
  box-sizing: border-box;
  color: var(--arl-text-color, #1e293b);
  user-select: none;
}

/* 卡片头部 */
.support-card-header {
  padding: 8px 12px 10px;
  text-align: center;
  border-bottom: 1px solid var(--arl-border-color, rgba(0, 0, 0, 0.06));
}

.support-card-title-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.support-sparkle {
  font-size: 14px;
}

.support-card-title {
  font-size: 15px;
  font-weight: 600;
  background: linear-gradient(135deg, var(--arl-theme-color, #fa541c), #ff7a45);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.support-card-desc {
  margin: 4px 0 0;
  font-size: 11px;
  opacity: 0.7;
  line-height: 1.4;
}

/* 切换胶囊 Tabs */
.support-tabs-bar {
  display: flex;
  gap: 4px;
  padding: 8px 8px 4px;
  background: rgba(125, 125, 125, 0.06);
  border-radius: 8px;
  margin: 8px 0;
}

.support-tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 6px 4px;
  font-size: 12px;
  border: none;
  background: transparent;
  color: var(--arl-text-color, #333333);
  opacity: 0.75;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.support-tab-btn:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.15);
}

.support-tab-btn.active {
  background: var(--arl-theme-color, #fa541c);
  color: #ffffff !important;
  opacity: 1;
  font-weight: 500;
  box-shadow: 0 2px 8px rgba(250, 84, 28, 0.25);
}

.tab-icon {
  font-size: 13px;
}

/* 卡片主体 */
.support-card-body {
  padding: 6px 12px 10px;
}

.support-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.fade-in {
  animation: cardFadeIn 0.25s ease-out;
}

@keyframes cardFadeIn {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 二维码容器：保持纯白底板以确保手机与微信 100% 灵敏识别 */
.qrcode-wrapper {
  width: 172px;
  height: 172px;
  padding: 8px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(0, 0, 0, 0.06);
  transition: transform 0.25s ease;
}

.qrcode-wrapper:hover {
  transform: scale(1.02);
}

.qrcode-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

/* 面板描述信息 */
.support-panel-info {
  margin-top: 10px;
  width: 100%;
}

.support-panel-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--arl-text-color, #1e293b);
  margin-bottom: 4px;
}

.highlight-text {
  color: var(--arl-theme-color, #fa541c);
}

.support-panel-desc {
  font-size: 11px;
  line-height: 1.45;
  opacity: 0.7;
  margin: 0 0 8px;
  padding: 0 4px;
}

.support-tip-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  font-size: 11px;
  border-radius: 20px;
  background: rgba(125, 125, 125, 0.08);
  color: var(--arl-text-color);
  opacity: 0.85;
}

/* 微信号复制栏 */
.wechat-copy-box {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 4px 8px;
  margin-bottom: 6px;
  border-radius: 6px;
  background: rgba(125, 125, 125, 0.07);
}

.wechat-label {
  font-size: 12px;
  opacity: 0.75;
}

.wechat-id {
  font-size: 13px;
  font-weight: 600;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: var(--arl-theme-color, #fa541c);
}

.copy-wechat-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  font-size: 11px;
  border: 1px solid var(--arl-theme-color, #fa541c);
  background: transparent;
  color: var(--arl-theme-color, #fa541c);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.copy-wechat-btn:hover {
  background: var(--arl-theme-color, #fa541c);
  color: #ffffff;
}

/* 卡片底部 */
.support-card-footer {
  padding: 8px 10px 4px;
  text-align: center;
  border-top: 1px solid var(--arl-border-color, rgba(0, 0, 0, 0.06));
  font-size: 10px;
  opacity: 0.55;
  line-height: 1.3;
}
</style>
