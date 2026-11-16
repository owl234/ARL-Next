import { i18n } from '../i18n/index.js';

const pageText = (key, params) => i18n.global.t(key, params);

/**
 * OSINT 出口运行态术语唯一事实源（全项目唯一口径）
 *
 * 基准词表：
 *   direct_ok 直连 / backup_active 备节点接管 / proxy_active 代理出口
 *   / degraded_blocked 出口冷却 / proxy_unavailable 代理不可用
 */

/** 出口状态 → Ant Design Tag 配色 */
export const PROXY_STATE_COLOR = {
  direct_ok: 'success',
  backup_active: 'warning',
  proxy_active: 'processing',
  degraded_blocked: 'error',
  proxy_unavailable: 'error',
};

/** 出口状态 → 语义等级（用于样式类） */
export const PROXY_STATE_LEVEL = {
  direct_ok: 'ok',
  backup_active: 'warning',
  proxy_active: 'info',
  degraded_blocked: 'danger',
  proxy_unavailable: 'danger',
};

/** 出口状态 → 呼吸脉冲颜色 */
export const PROXY_STATE_PULSE = {
  backup_active: 'orange',
  degraded_blocked: 'red',
  proxy_unavailable: 'red',
};

/**
 * 出口运行态 → 统一展示文案。
 * @param {object|null|undefined} runtime 后端返回的 runtime / proxy 摘要对象
 * @param {object} [options]
 * @param {boolean} [options.withPrefix=false] 是否附带「OSINT 出口: 」前缀
 * @param {number|null} [options.cooldownSecOverride=null] 前端本地倒计时覆盖秒数
 * @returns {string}
 */
export const formatProxyEgressLabel = (
  runtime,
  { withPrefix = false, cooldownSecOverride = null } = {},
) => {
  const rt = runtime || {};
  const state = rt.state || 'direct_ok';
  let statusText = '';

  switch (state) {
    case 'backup_active': {
      const base = pageText('pages.proxyStateBackup');
      const name = rt.active_node_name || rt.active_exit_id;
      statusText = name && name !== '__direct__' ? `${base} · ${name}` : base;
      break;
    }
    case 'proxy_active': {
      const base = pageText('pages.proxyStateProxy');
      const name = rt.active_node_name || rt.active_exit_id;
      statusText = name && name !== '__direct__' ? `${base} · ${name}` : base;
      break;
    }
    case 'degraded_blocked': {
      const sec = cooldownSecOverride != null
        ? cooldownSecOverride
        : Number(rt.cooldown_remaining_sec || 0);
      statusText = pageText('pages.proxyStateCooldown', { sec });
      break;
    }
    case 'proxy_unavailable':
      statusText = pageText('pages.proxyStateUnavailable');
      break;
    default:
      statusText = pageText('pages.proxyStateDirect');
      break;
  }

  return withPrefix
    ? pageText('pages.proxyEgressPrefixed', { status: statusText })
    : statusText;
};

/** 出口状态 → Ant Design Tag 配色 */
export const formatProxyTagColor = (state) => PROXY_STATE_COLOR[state] || 'success';

/** 出口状态 → 卡片/胶囊语义类（is-ok / is-warning / is-info / is-danger） */
export const formatProxyLevelClass = (state) => `is-${PROXY_STATE_LEVEL[state] || 'ok'}`;

/** 出口状态 → 呼吸脉冲颜色（无则空串） */
export const formatProxyPulse = (state) => PROXY_STATE_PULSE[state] || '';
