const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string' ? value : typeof value === 'number' && Number.isFinite(value) ? String(value) : '';
const number = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
const httpStatus = value => Number.isInteger(value) && value >= 100 && value <= 599 ? value : null;

export const isApiEndpointRecord = record =>
  object(record) && (record.record_type || record.recordType) === 'api_endpoint';

export const PROBE_STATE_KEYS = {
  not_collected: 'notCollected', responded: 'responseReceived', error: 'requestFailed',
  skipped: 'skipped', unknown: 'unknownState',
};

export const PROBE_REASON_KEYS = {
  unsupported_method: 'unsupportedMethod', unresolved_url: 'unresolvedUrl', outside_origin: 'outsideOrigin',
  excluded: 'excluded', site_quota: 'siteQuota', site_budget: 'siteBudget',
  timeout: 'timeout', connection_error: 'connectionError', tls_error: 'tlsError',
  request_error: 'requestError', time_budget: 'timeBudget',
  invalid_redirect: 'invalidRedirect', redirect_loop: 'redirectLoop', redirect_limit: 'redirectLimit',
  head: 'headBody', non_text: 'nonTextBody',
};

export function getWihApiDetails(record) {
  const item = object(record) ? record : {};
  const request = object(item.api_request) ? item.api_request : null;
  const probe = request && object(request.probe) ? request.probe : null;
  const state = !probe ? 'not_collected' : ['responded', 'error', 'skipped'].includes(probe.state) ? probe.state : 'unknown';
  const headers = probe && object(probe.headers) ? Object.entries(probe.headers)
    .filter(([, value]) => typeof value === 'string' || typeof value === 'number' && Number.isFinite(value))
    .map(([key, value]) => `${key}: ${value}`).join('\n') : '';
  const bodySkipped = text(probe?.body_skipped);

  return {
    legacy: !request,
    site: text(item.site), source: text(item.source), content: text(item.content),
    method: text(request?.method), url: text(request?.url), path: text(request?.path),
    client: text(request?.client), line: number(request?.line),
    state, stateKey: PROBE_STATE_KEYS[state], statusCode: httpStatus(probe?.status_code),
    // error 状态中的 url 是尝试目标，不能显示成已经收到响应的地址。
    responseUrl: state === 'responded' ? text(probe?.url) : '',
    lastAttemptUrl: text(probe?.last_attempt_url), checkedAt: text(probe?.checked_at),
    elapsedMs: number(probe?.elapsed_ms), reason: text(probe?.reason), error: text(probe?.error),
    redirectStop: text(probe?.redirect_stop), headers,
    redirects: Array.isArray(probe?.redirects) ? probe.redirects.filter(object).map(hop => ({
      url: text(hop.url), statusCode: httpStatus(hop.status_code),
    })) : [],
    body: typeof probe?.body_preview === 'string' ? probe.body_preview : '',
    bodyCollected: typeof probe?.body_preview === 'string' && !bodySkipped,
    bodyBytes: number(probe?.body_bytes), bodyTruncated: probe?.body_truncated === true,
    bodySkipped, bodyError: text(probe?.body_error),
  };
}
