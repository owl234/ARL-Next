/** @param {unknown} value */
export function isCompleteMcpKey(value) {
  return typeof value === 'string' && /^arl_mcp_[A-Za-z0-9_-]{32,}$/.test(value.trim());
}

/**
 * @param {string} selectedKeyId
 * @param {string | null} sessionToken
 * @param {Record<string, string>} keySecrets
 */
export function resolveMcpCredential(selectedKeyId, sessionToken, keySecrets) {
  if (selectedKeyId === 'current_session') return sessionToken || '';
  const value = keySecrets[selectedKeyId]?.trim() || '';
  return isCompleteMcpKey(value) ? value : '';
}

/**
 * @param {string} [scriptPath]
 * @param {{ pythonBin?: string }} [options]
 */
export function createStdioServerConfig(scriptPath = '~/Downloads/arl_mcp.py', options = {}) {
  const command = options?.pythonBin === 'python' ? 'python' : 'python3';
  const resolvedPath = (typeof scriptPath === 'string' && scriptPath.trim()) || '~/Downloads/arl_mcp.py';
  // MCP hosts spawn directly without a shell, so Python must expand '~'.
  return {
    command,
    args: ['-c', `import os, runpy; runpy.run_path(os.path.expanduser(${JSON.stringify(resolvedPath)}), run_name='__main__')`],
  };
}

/**
 * Generate client-specific configuration snippets for SSE or Stdio transports.
 * @param {{ client?: string, mode?: string, host?: string, token?: string, scriptPath?: string, pythonBin?: string }} params
 */
export function buildClientConfigSnippet({
  client = 'cursor',
  mode = 'sse',
  host = '',
  token = '',
  scriptPath = '~/Downloads/arl_mcp.py',
  pythonBin = 'python3',
} = {}) {
  const resolvedHost = (host || '').replace(/\/+$/, '');
  const resolvedToken = token || '<YOUR_MCP_KEY>';
  const resolvedPath = (typeof scriptPath === 'string' && scriptPath.trim()) || '~/Downloads/arl_mcp.py';
  const pyCmd = pythonBin === 'python' ? 'python' : 'python3';

  if (client === 'claude_code') {
    if (mode === 'sse') {
      return `claude mcp add -s user --transport sse arl-next "${resolvedHost}/mcp/sse" --header "Authorization: Bearer ${resolvedToken}"`;
    }
    const inlineRunner = `import os, runpy; runpy.run_path(os.path.expanduser(${JSON.stringify(resolvedPath)}), run_name='__main__')`;
    return `claude mcp add -s user arl-next -- ${pyCmd} -c ${JSON.stringify(inlineRunner)}`;
  }

  if (client === 'sdk_env') {
    return [
      `ARL_HOST=${resolvedHost}`,
      `ARL_TOKEN=${resolvedToken}`,
      `MCP_SSE_URL=${resolvedHost}/mcp/sse`,
      `# Stdio runner: ${pyCmd} ${resolvedPath}`,
    ].join('\n');
  }

  if (mode === 'sse') {
    return JSON.stringify({
      mcpServers: {
        'arl-next': {
          url: `${resolvedHost}/mcp/sse`,
          headers: {
            Authorization: `Bearer ${resolvedToken}`,
          },
        },
      },
    }, null, 2);
  }

  return JSON.stringify({
    mcpServers: {
      'arl-next': createStdioServerConfig(resolvedPath, { pythonBin: pyCmd }),
    },
  }, null, 2);
}

export const MCP_TOOL_CATALOG = [
  { name: 'get_asset_profile', scope: 'asset:read', isWrite: false, category: 'recon' },
  { name: 'get_enterprise_profile', scope: 'asset:read', isWrite: false, category: 'recon' },
  { name: 'search_assets', scope: 'asset:read', isWrite: false, category: 'search' },
  { name: 'get_task_status', scope: 'asset:read', isWrite: false, category: 'task' },
  { name: 'create_scan_task', scope: 'task:dispatch', isWrite: true, category: 'dispatch' },
  { name: 'stop_scan_task', scope: 'task:dispatch', isWrite: true, category: 'dispatch' },
];

/**
 * Evaluate effective availability of all 6 MCP tools under current policy and key scopes.
 * @param {{ toolSwitches?: Record<string, boolean>, keyScopes?: string[] | null, isSessionToken?: boolean }} params
 */
export function evaluateToolAccess({ toolSwitches = {}, keyScopes = null, isSessionToken = true } = {}) {
  const effectiveScopes = isSessionToken || !Array.isArray(keyScopes)
    ? ['asset:read', 'task:dispatch']
    : keyScopes;

  return MCP_TOOL_CATALOG.map((tool) => {
    const policyEnabled = Object.prototype.hasOwnProperty.call(toolSwitches, tool.name)
      ? Boolean(toolSwitches[tool.name])
      : !tool.isWrite;
    const scopeAllowed = effectiveScopes.includes(tool.scope);
    const allowed = policyEnabled && scopeAllowed;
    let reason = 'ok';
    if (!policyEnabled) reason = 'policy_disabled';
    else if (!scopeAllowed) reason = 'missing_scope';
    return {
      ...tool,
      policyEnabled,
      scopeAllowed,
      allowed,
      reason,
    };
  });
}

/**
 * Summarize evaluated MCP tool capabilities into read/write counts and block reasons.
 * @param {Array<{ name: string, scope: string, isWrite: boolean, allowed: boolean, reason: string }>} capabilities
 */
export function summarizeToolCapabilities(capabilities = []) {
  const list = Array.isArray(capabilities) ? capabilities : [];
  const readItems = list.filter(item => !item.isWrite);
  const writeItems = list.filter(item => item.isWrite);
  const missingScopes = [...new Set(
    list.filter(item => item.reason === 'missing_scope' && item.scope).map(item => item.scope)
  )];
  return {
    readItems,
    writeItems,
    readAllowed: readItems.filter(item => item.allowed).length,
    readTotal: readItems.length,
    writeAllowed: writeItems.filter(item => item.allowed).length,
    writeTotal: writeItems.length,
    missingScopes,
    hasMissingScope: missingScopes.length > 0,
    hasPolicyDisabled: list.some(item => item.reason === 'policy_disabled'),
  };
}

const OBJECT_ID_RE = /\b([a-fA-F0-9]{24})\b/;
const IPV4_RE = /^\d{1,3}(?:\.\d{1,3}){3}$/;

/**
 * Derive clickable ARL task/asset navigation targets from an MCP audit log record.
 * @param {{ tool_name?: string, target?: string, summary?: string, params_summary?: string }} record
 */
export function extractAuditPivot(record = {}) {
  const toolName = String(record?.tool_name || '');
  const target = String(record?.target || '').trim();
  const summary = String(record?.summary || '');
  const paramsSummary = String(record?.params_summary || '');

  let taskId = '';
  if (OBJECT_ID_RE.test(target) && ['get_task_status', 'stop_scan_task', 'get_asset_profile', 'get_enterprise_profile'].includes(toolName)) {
    taskId = target.match(OBJECT_ID_RE)[1];
  } else if (OBJECT_ID_RE.test(summary)) {
    taskId = summary.match(OBJECT_ID_RE)[1];
  } else if (OBJECT_ID_RE.test(paramsSummary)) {
    taskId = paramsSummary.match(OBJECT_ID_RE)[1];
  }

  let assetQuery = null;
  if (target && !/^[a-fA-F0-9]{24}$/.test(target)) {
    if (toolName === 'get_asset_profile') {
      if (IPV4_RE.test(target)) {
        assetQuery = { path: '/asset-search', query: { tab: 'ip', ip: target } };
      } else {
        assetQuery = { path: '/asset-search', query: { tab: 'site', site: target } };
      }
    } else if (toolName === 'search_assets') {
      let assetType = 'site';
      try {
        const parsed = JSON.parse(paramsSummary);
        if (parsed && ['site', 'domain', 'ip', 'vuln'].includes(parsed.asset_type)) {
          assetType = parsed.asset_type;
        }
      } catch {
        const match = paramsSummary.match(/"asset_type"\s*:\s*"(site|domain|ip|vuln)"/);
        if (match) assetType = match[1];
      }
      const fieldMap = { site: 'site', domain: 'domain', ip: 'ip', vuln: 'vul_name' };
      assetQuery = { path: '/asset-search', query: { tab: assetType, [fieldMap[assetType]]: target } };
    } else if (toolName === 'get_enterprise_profile' && target.includes('.')) {
      assetQuery = { path: '/asset-search', query: { tab: 'site', site: target } };
    }
  }

  return {
    taskRoute: taskId ? { path: '/taskList/taskDetail', query: { task_id: taskId } } : null,
    taskId,
    assetRoute: assetQuery,
  };
}
