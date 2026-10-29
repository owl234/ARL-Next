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

/** @param {string} [scriptPath] */
export function createStdioServerConfig(scriptPath = '~/Downloads/arl_mcp.py') {
  // MCP hosts spawn directly without a shell, so Python must expand '~'.
  return {
    command: 'python3',
    args: ['-c', `import os, runpy; runpy.run_path(os.path.expanduser(${JSON.stringify(scriptPath)}), run_name='__main__')`],
  };
}
