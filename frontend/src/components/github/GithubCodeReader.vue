<template>
  <div class="gh-code-reader" :class="{ 'is-compact': compact }">
    <div class="gh-code-reader-header">
      <div class="gh-code-legend">
        <span class="legend-chip is-keyword">{{ pageText('pages.githubHighlightKeyword') }}</span>
        <span class="legend-chip is-secret">{{ pageText('pages.githubHighlightSecret') }}</span>
        <span class="legend-chip is-network">{{ pageText('pages.githubHighlightNetwork') }}</span>
      </div>
      <div class="gh-code-actions">
        <a-tooltip :title="pageText('pages.githubCopySnippet')">
          <a-button type="text" size="small" class="gh-reader-btn" @click="handleCopy(content)">
            <template #icon><copy-outlined /></template>
          </a-button>
        </a-tooltip>
        <a-tooltip v-if="htmlUrl" :title="pageText('pages.githubCopyFileUrl')">
          <a-button type="text" size="small" class="gh-reader-btn" @click="handleCopy(htmlUrl)">
            <template #icon><link-outlined /></template>
          </a-button>
        </a-tooltip>
        <a-tooltip v-if="repoFullName" :title="pageText('pages.githubCopyCloneCmd')">
          <a-button type="text" size="small" class="gh-reader-btn" @click="handleCopy(cloneCommand)">
            <template #icon><code-outlined /></template>
          </a-button>
        </a-tooltip>
        <a-tooltip v-if="expandable" :title="pageText('pages.githubExpandSnippet')">
          <a-button type="text" size="small" class="gh-reader-btn" @click="$emit('expand')">
            <template #icon><expand-outlined /></template>
          </a-button>
        </a-tooltip>
      </div>
    </div>

    <div class="gh-code-body" :style="{ maxHeight: maxHeight }">
      <div v-for="line in parsedLines" :key="line.lineNumber" class="gh-code-line">
        <span class="gh-line-num">{{ line.lineNumber }}</span>
        <span class="gh-line-content">
          <template v-for="(tok, idx) in line.tokens" :key="idx">
            <span v-if="tok.kind !== 'plain'" :class="`gh-tok-${tok.kind}`">{{ tok.text }}</span>
            <template v-else>{{ tok.text }}</template>
          </template>
        </span>
      </div>
      <div v-if="!content" class="gh-code-empty">{{ pageText('pages.githubEmptySnippet') }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { message } from 'ant-design-vue';
import { CopyOutlined, LinkOutlined, CodeOutlined, ExpandOutlined } from '@ant-design/icons-vue';
import { copyText } from '../../utils/clipboard';
import { tokenizeCodeSnippet, buildGitCloneCmd } from '../../utils/githubHelpers';

const props = defineProps({
  content: { type: String, default: '' },
  keyword: { type: String, default: '' },
  htmlUrl: { type: String, default: '' },
  repoFullName: { type: String, default: '' },
  maxHeight: { type: String, default: '220px' },
  compact: { type: Boolean, default: false },
  expandable: { type: Boolean, default: true },
});

defineEmits(['expand']);

const { t: pageText } = useI18n({ useScope: 'global' });

const parsedLines = computed(() => tokenizeCodeSnippet(props.content, props.keyword));
const cloneCommand = computed(() => buildGitCloneCmd(props.repoFullName));

const handleCopy = async (text) => {
  if (!text) return;
  try {
    await copyText(text);
    message.success(pageText('pages.copiedToClipboard'));
  } catch {
    message.error(pageText('pages.requestFailed'));
  }
};
</script>

<style scoped>
.gh-code-reader {
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  background: var(--arl-bg-light);
  overflow: hidden;
}

.gh-code-reader-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 8px;
  border-bottom: 1px solid var(--arl-border-color);
  background: var(--arl-bg-card);
}

.gh-code-legend {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.legend-chip {
  font-size: 11px;
  line-height: 1.4;
  padding: 1px 6px;
  border-radius: 4px;
}

.legend-chip.is-keyword {
  background: rgba(250, 173, 20, 0.18);
  color: #d48806;
}

.legend-chip.is-secret {
  background: rgba(255, 77, 79, 0.15);
  color: #cf1322;
}

.legend-chip.is-network {
  background: rgba(24, 144, 255, 0.14);
  color: var(--arl-theme-color);
}

.gh-code-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.gh-reader-btn {
  color: var(--arl-text-secondary);
}

.gh-reader-btn:hover {
  color: var(--arl-theme-color);
}

.gh-code-body {
  overflow-y: auto;
  overflow-x: auto;
  padding: 6px 0;
  font-family: var(--arl-font-mono);
  font-size: 12px;
  line-height: 1.55;
  color: var(--arl-text-color);
}

.gh-code-line {
  display: flex;
  align-items: flex-start;
  padding: 0 10px 0 0;
}

.gh-code-line:hover {
  background: color-mix(in srgb, var(--arl-theme-color) 6%, transparent);
}

.gh-line-num {
  width: 36px;
  flex-shrink: 0;
  text-align: right;
  padding-right: 10px;
  user-select: none;
  color: var(--arl-text-secondary);
  opacity: 0.6;
}

.gh-line-content {
  white-space: pre-wrap;
  word-break: break-word;
  flex: 1;
  min-width: 0;
}

.gh-tok-keyword {
  background: rgba(250, 173, 20, 0.28);
  color: #ad6800;
  border-radius: 3px;
  padding: 0 2px;
  font-weight: 600;
}

.gh-tok-secret {
  background: rgba(255, 77, 79, 0.18);
  color: #cf1322;
  border-radius: 3px;
  padding: 0 2px;
  font-weight: 500;
}

.gh-tok-network {
  background: rgba(24, 144, 255, 0.14);
  color: var(--arl-theme-color);
  border-radius: 3px;
  padding: 0 2px;
}

:global(body.dark-mode) .legend-chip.is-keyword,
:global(body.dark-mode) .gh-tok-keyword {
  color: #ffd666;
}

:global(body.dark-mode) .legend-chip.is-secret,
:global(body.dark-mode) .gh-tok-secret {
  color: #ff7875;
}

.gh-code-empty {
  padding: 10px 14px;
  color: var(--arl-text-secondary);
  font-style: italic;
}
</style>
