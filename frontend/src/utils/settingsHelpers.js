/**
 * 系统设置辅助纯函数库：
 * - 代理 URI 一键解析
 * - 安全红线（IP/CIDR/IP段 & 禁扫域名）校验、预设增删与目标命中预检
 * - 基础设施连接串内嵌密码脱敏
 * - 高强度 API Key 生成
 */

const VALID_PROXY_PROTOCOLS = new Set(['socks5h', 'socks5', 'http', 'https']);
const DEFAULT_PROXY_PORTS = {
  socks5h: 1080,
  socks5: 1080,
  http: 80,
  https: 443,
};

/**
 * 解析标准代理 URI（如 socks5h://user:pass@192.0.2.10:1080）。
 * @param {string} raw
 * @returns {{ok: boolean, protocol?: string, host?: string, port?: number, username?: string, password?: string, reason?: string}}
 */
export function parseProxyUri(raw) {
  const input = String(raw || '').trim();
  if (!input) {
    return { ok: false, reason: 'empty' };
  }
  const normalized = input.includes('://') ? input : `http://${input}`;
  let parsed;
  try {
    parsed = new URL(normalized);
  } catch {
    return { ok: false, reason: 'invalid_uri' };
  }

  const protocol = parsed.protocol.replace(/:$/, '').toLowerCase();
  if (!VALID_PROXY_PROTOCOLS.has(protocol)) {
    return { ok: false, reason: 'unsupported_protocol' };
  }

  const host = parsed.hostname ? parsed.hostname.replace(/^\[|\]$/g, '') : '';
  if (!host) {
    return { ok: false, reason: 'missing_host' };
  }

  let port = parsed.port ? Number(parsed.port) : DEFAULT_PROXY_PORTS[protocol];
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    return { ok: false, reason: 'invalid_port' };
  }

  let username = '';
  let password = '';
  try {
    username = parsed.username ? decodeURIComponent(parsed.username) : '';
    password = parsed.password ? decodeURIComponent(parsed.password) : '';
  } catch {
    username = parsed.username || '';
    password = parsed.password || '';
  }

  return {
    ok: true,
    protocol,
    host,
    port,
    username,
    password,
  };
}

function parseIpv4ToBigInt(ip) {
  const parts = ip.split('.');
  if (parts.length !== 4) return null;
  let val = 0n;
  for (const part of parts) {
    if (!/^\d{1,3}$/.test(part)) return null;
    const n = Number(part);
    if (n < 0 || n > 255) return null;
    val = (val << 8n) + BigInt(n);
  }
  return val;
}

function expandIpv6ToGroups(ip) {
  let addr = ip.toLowerCase();
  const zoneIdx = addr.indexOf('%');
  if (zoneIdx !== -1) return null;

  // Handle IPv4-embedded suffix (e.g. ::ffff:192.0.2.128)
  const lastColon = addr.lastIndexOf(':');
  let embeddedIpv4Groups = null;
  if (lastColon !== -1 && addr.slice(lastColon + 1).includes('.')) {
    const ipv4 = parseIpv4ToBigInt(addr.slice(lastColon + 1));
    if (ipv4 === null) return null;
    embeddedIpv4Groups = [
      Number((ipv4 >> 16n) & 0xffffn),
      Number(ipv4 & 0xffffn),
    ];
    addr = addr.slice(0, lastColon);
    if (!addr.includes(':')) addr = `:${addr}`;
  }

  const targetTotalGroups = embeddedIpv4Groups ? 6 : 8;
  const doubleColonParts = addr.split('::');
  if (doubleColonParts.length > 2) return null;

  const parseSegmentList = (seg) => {
    if (!seg) return [];
    const tokens = seg.split(':');
    const nums = [];
    for (const tok of tokens) {
      if (!/^[0-9a-f]{1,4}$/i.test(tok)) return null;
      nums.push(parseInt(tok, 16));
    }
    return nums;
  };

  let groups;
  if (doubleColonParts.length === 2) {
    const left = parseSegmentList(doubleColonParts[0]);
    const right = parseSegmentList(doubleColonParts[1]);
    if (!left || !right) return null;
    const missing = targetTotalGroups - (left.length + right.length);
    if (missing < 1) return null;
    groups = [...left, ...new Array(missing).fill(0), ...right];
  } else {
    const exact = parseSegmentList(addr);
    if (!exact || exact.length !== targetTotalGroups) return null;
    groups = exact;
  }

  if (embeddedIpv4Groups) {
    groups.push(...embeddedIpv4Groups);
  }
  return groups;
}

function parseIpv6ToBigInt(ip) {
  const groups = expandIpv6ToGroups(ip);
  if (!groups) return null;
  // Normalize IPv4-mapped IPv6 (::ffff:0:0/96) to IPv4 just like Python ipaddress.ipv4_mapped
  const isV4Mapped =
    groups[0] === 0 && groups[1] === 0 && groups[2] === 0 &&
    groups[3] === 0 && groups[4] === 0 && groups[5] === 0xffff;
  if (isV4Mapped) {
    const v4 = (BigInt(groups[6]) << 16n) + BigInt(groups[7]);
    return { version: 4, value: v4 };
  }
  let val = 0n;
  for (const g of groups) {
    val = (val << 16n) + BigInt(g);
  }
  return { version: 6, value: val };
}

function parseIpAddress(raw) {
  const s = String(raw || '').trim();
  if (!s) return null;
  if (s.includes(':')) {
    return parseIpv6ToBigInt(s);
  }
  const v4 = parseIpv4ToBigInt(s);
  if (v4 === null) return null;
  return { version: 4, value: v4 };
}

/**
 * 解析并校验单条黑名单规则（单 IP / CIDR / IP-IP 区间，对齐后端 app/utils/ip.py）。
 * @param {string} rawLine
 * @returns {{valid: boolean, version?: number, first?: bigint, last?: bigint}}
 */
export function parseBlackIpInterval(rawLine) {
  const value = String(rawLine || '').trim();
  if (!value) return { valid: false };

  if (value.includes('-')) {
    const idx = value.indexOf('-');
    const firstStr = value.slice(0, idx).trim();
    let lastStr = value.slice(idx + 1).trim();
    const start = parseIpAddress(firstStr);
    if (!start) return { valid: false };
    if (start.version === 4 && /^\d+$/.test(lastStr)) {
      const dotIdx = firstStr.lastIndexOf('.');
      if (dotIdx === -1) return { valid: false };
      lastStr = `${firstStr.slice(0, dotIdx)}.${lastStr}`;
    }
    const end = parseIpAddress(lastStr);
    if (!end || start.version !== end.version || start.value > end.value) {
      return { valid: false };
    }
    return { valid: true, version: start.version, first: start.value, last: end.value };
  }

  if (value.includes('/')) {
    const parts = value.split('/');
    if (parts.length !== 2) return { valid: false };
    const [ipPart, prefixPart] = parts;
    if (!/^\d+$/.test(prefixPart.trim())) return { valid: false };
    const prefix = Number(prefixPart.trim());
    const addr = ipPart.includes(':') ? parseIpv6ToBigInt(ipPart.trim()) : parseIpAddress(ipPart.trim());
    if (!addr) return { valid: false };
    const maxBits = addr.version === 4 ? 32 : 128;
    if (prefix < 0 || prefix > maxBits) return { valid: false };
    const hostBits = BigInt(maxBits - prefix);
    const mask = prefix === 0 ? 0n : (((1n << BigInt(maxBits)) - 1n) ^ ((1n << hostBits) - 1n));
    const networkAddr = addr.value & mask;
    const broadcastAddr = networkAddr | ((1n << hostBits) - 1n);
    return { valid: true, version: addr.version, first: networkAddr, last: broadcastAddr };
  }

  const single = parseIpAddress(value);
  if (!single) return { valid: false };
  return { valid: true, version: single.version, first: single.value, last: single.value };
}

/**
 * 校验单条禁止扫描域名后缀是否规范。
 * @param {string} rawLine
 * @returns {{valid: boolean, normalized: string}}
 */
export function validateForbiddenDomainLine(rawLine) {
  const cleaned = String(rawLine || '').trim().toLowerCase().replace(/^\.+/, '');
  if (!cleaned) return { valid: false, normalized: '' };
  if (/[\s/\\:*?<>|"'@]/.test(cleaned) || !cleaned.includes('.')) {
    return { valid: false, normalized: cleaned };
  }
  if (!/^[a-z0-9.-]+$/.test(cleaned) || cleaned.endsWith('.')) {
    return { valid: false, normalized: cleaned };
  }
  return { valid: true, normalized: cleaned };
}

/**
 * 统计安全策略文本中的有效条目与格式异常行（供前端行内即时反馈）。
 * @param {string} blackIpsText
 * @param {string} forbiddenDomainsText
 */
export function analyzeSecurityPolicy(blackIpsText, forbiddenDomainsText) {
  const ipLines = String(blackIpsText || '').split('\n');
  const domainLines = String(forbiddenDomainsText || '').split('\n');

  const validIps = [];
  const invalidIps = [];
  ipLines.forEach((raw, idx) => {
    const trimmed = raw.trim();
    if (!trimmed) return;
    const parsed = parseBlackIpInterval(trimmed);
    if (parsed.valid) {
      validIps.push({ line: idx + 1, raw: trimmed, ...parsed });
    } else {
      invalidIps.push({ line: idx + 1, raw: trimmed });
    }
  });

  const validDomains = [];
  const invalidDomains = [];
  domainLines.forEach((raw, idx) => {
    const trimmed = raw.trim();
    if (!trimmed) return;
    const res = validateForbiddenDomainLine(trimmed);
    if (res.valid) {
      validDomains.push({ line: idx + 1, raw: trimmed, normalized: res.normalized });
    } else {
      invalidDomains.push({ line: idx + 1, raw: trimmed });
    }
  });

  return {
    ipCount: validIps.length,
    domainCount: validDomains.length,
    validIps,
    invalidIps,
    validDomains,
    invalidDomains,
  };
}

/**
 * 按行增删安全策略预设条目（去重并保持原有顺序）。
 * @param {string} currentText
 * @param {string[]} presetItems
 * @param {'add' | 'remove'} mode
 * @returns {string}
 */
export function applySecurityPreset(currentText, presetItems, mode = 'add') {
  const lines = String(currentText || '')
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean);
  const presetNorm = new Set((presetItems || []).map((s) => s.trim().toLowerCase()));

  if (mode === 'remove') {
    return lines.filter((item) => !presetNorm.has(item.toLowerCase())).join('\n');
  }

  const seen = new Set(lines.map((s) => s.toLowerCase()));
  const out = [...lines];
  for (const item of presetItems || []) {
    const clean = String(item || '').trim();
    if (clean && !seen.has(clean.toLowerCase())) {
      seen.add(clean.toLowerCase());
      out.push(clean);
    }
  }
  return out.join('\n');
}

export const SECURITY_IP_PRESETS = {
  rfc1918: ['127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16'],
};

export const SECURITY_DOMAIN_PRESETS = {
  govEdu: ['gov.cn', 'edu.cn', 'mil.cn'],
};

/**
 * 在当前草稿规则上对指定目标（IP/CIDR/URL/域名）执行 Dry-Run 拦截检测。
 * @param {string} rawTarget
 * @param {string} blackIpsText
 * @param {string} forbiddenDomainsText
 */
export function testTargetAgainstGuardrails(rawTarget, blackIpsText, forbiddenDomainsText) {
  let target = String(rawTarget || '').trim();
  if (!target) {
    return { status: 'empty', target: '', matchedRule: '' };
  }

  // 若输入为 URL，提取 hostname（移除 scheme/path/端口）
  if (target.includes('://')) {
    try {
      const u = new URL(target);
      target = u.hostname.replace(/^\[|\]$/g, '');
    } catch {
      return { status: 'invalid', target, matchedRule: '' };
    }
  } else if (target.includes('/') && !parseBlackIpInterval(target).valid) {
    target = target.split('/')[0];
  }

  // 如果是 host:port（非纯 IPv6）提取 host
  if (!target.includes('/') && target.includes(':') && target.indexOf(':') === target.lastIndexOf(':')) {
    const [maybeHost, maybePort] = target.split(':');
    if (/^\d+$/.test(maybePort)) {
      target = maybeHost;
    }
  }

  const { validIps, validDomains } = analyzeSecurityPolicy(blackIpsText, forbiddenDomainsText);

  // 1. 先按 IP/CIDR/IP段 匹配（与后端 not_in_black_ips 一致）
  const ipInterval = parseBlackIpInterval(target);
  if (ipInterval.valid) {
    for (const rule of validIps) {
      if (
        ipInterval.version === rule.version &&
        ipInterval.first <= rule.last &&
        rule.first <= ipInterval.last
      ) {
        return { status: 'blocked_ip', target, matchedRule: rule.raw };
      }
    }
    return { status: 'allowed', target, matchedRule: '' };
  }

  // 2. 按域名后缀匹配（与后端 is_forbidden_domain 一致：精确相等或 .suffix 结尾）
  const domainLower = target.toLowerCase().replace(/\.$/, '');
  if (!domainLower || /\s/.test(domainLower) || !domainLower.includes('.')) {
    return { status: 'invalid', target, matchedRule: '' };
  }

  for (const rule of validDomains) {
    const suffix = rule.normalized;
    if (domainLower === suffix || domainLower.endsWith(`.${suffix}`)) {
      return { status: 'blocked_domain', target: domainLower, matchedRule: rule.raw };
    }
  }

  return { status: 'allowed', target: domainLower, matchedRule: '' };
}

/**
 * 脱敏基础设施连接串中的内嵌密码（保留协议、用户名、主机与路径）。
 * @param {string} uri
 * @returns {string}
 */
export function maskConnectionUri(uri) {
  const raw = String(uri || '').trim();
  if (!raw) return '';
  return raw.replace(/^([a-zA-Z][a-zA-Z0-9+.-]*:\/\/[^/:@\s]+):([^@\s]+)@/, '$1:******@');
}

/**
 * 生成高强度随机 API Key（字母+数字，无歧义字符）。
 * @param {number} length
 * @returns {string}
 */
export function generateStrongApiKey(length = 32) {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';
  const out = [];
  if (typeof globalThis.crypto !== 'undefined' && typeof globalThis.crypto.getRandomValues === 'function') {
    const bytes = new Uint8Array(length);
    globalThis.crypto.getRandomValues(bytes);
    for (let i = 0; i < length; i += 1) {
      out.push(alphabet[bytes[i] % alphabet.length]);
    }
  } else {
    for (let i = 0; i < length; i += 1) {
      out.push(alphabet[Math.floor(Math.random() * alphabet.length)]);
    }
  }
  return out.join('');
}
