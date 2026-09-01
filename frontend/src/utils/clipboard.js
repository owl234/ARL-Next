/**
 * 剪贴板复制工具
 * 优先使用 Clipboard API，兼容非 HTTPS 环境的 execCommand fallback
 *
 * Usage:
 *   import { copyText } from '../utils/clipboard';
 *   const ok = await copyText('some text');
 *   if (ok) message.success('复制成功');
 *
 * @param {string} text 要复制的内容
 * @returns {Promise<boolean>} 是否复制成功
 */
export const copyText = async (text) => {
  if (!text) return false;

  // 优先使用 Clipboard API（仅 HTTPS 安全上下文可用）
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) {
      // Clipboard API 失败，回退到 execCommand
    }
  }

  return fallbackCopy(text);
};

/**
 * 兼容性 fallback：通过不可见 textarea + document.execCommand('copy') 复制
 * 适用于 HTTP 环境或 Clipboard API 被拒绝的场景
 */
const fallbackCopy = (text) => {
  const input = document.createElement('textarea');
  input.value = text;
  input.style.position = 'fixed';
  input.style.opacity = '0';
  input.style.pointerEvents = 'none';
  input.style.left = '-9999px';
  document.body.appendChild(input);
  input.select();
  try {
    return document.execCommand('copy');
  } catch (e) {
    return false;
  } finally {
    document.body.removeChild(input);
  }
};