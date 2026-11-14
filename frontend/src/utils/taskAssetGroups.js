import { i18n } from '../i18n/index.js';

const taskText = (key, params) => i18n.global.t(key, params);

export function createAssetScopeLoader(request, state, onError = () => {}) {
  let version = 0;
  const load = async (reset = false, search = state.search) => {
    if (!reset && (state.loading || !state.hasMore)) return;
    const current = reset ? ++version : version;
    if (reset) {
      Object.assign(state, { search, page: 1, options: [], hasMore: true });
    }
    const page = state.page;
    state.loading = true;
    try {
      const response = await request.get('/asset_scope/', {
        params: { name: state.search || undefined, page, size: 50, order: '_id' }
      });
      if (current !== version) return;
      if (response.code !== 200 || !Array.isArray(response.items) || !Number.isInteger(response.total)) {
        throw new Error(response.data?.error || response.message || taskText('tasks.invalidAssetGroupResponse'));
      }
      const options = new Map(state.options.map(option => [option.value, option]));
      for (const item of response.items) options.set(item._id, { value: item._id, label: item.name || item._id });
      state.options = [...options.values()];
      state.page = page + 1;
      state.hasMore = page * 50 < response.total;
    } catch (error) {
      if (current === version) onError(error);
    } finally {
      if (current === version) state.loading = false;
    }
  };
  return { load, dispose: () => { version++; } };
}

export function getTaskAssetGroupState(task) {
  const related = task.options?.related_scope_id;
  const id = task.sync_scope_id || related || task.synced_scope_id;
  if (!id) return null;
  const label = task.sync_scope_name || task.related_scope_name || task.synced_scope_name || id;
  if (task.sync_status === 'error') return { id, label, color: 'error', text: taskText('tasks.assetGroupSyncFailed'), error: task.sync_error || taskText('tasks.syncRetryHint') };
  if (task.sync_status === 'running') return { id, label, color: 'processing', text: taskText('tasks.syncRunning') };
  if (task.sync_status === 'waiting') return { id, label, color: 'default', text: taskText('tasks.syncWaiting') };
  if (task.synced_scope_id === id) return { id, label: task.synced_scope_name || label, color: 'success', text: taskText('tasks.syncDone') };
  const terminal = ['done', 'stop', 'error'].includes(task.status);
  return { id, label, color: 'default', text: terminal ? taskText('tasks.syncPending') : taskText('tasks.syncAfterCompletion') };
}

export function hasSyncSummary(record) {
  if (!record) return false;
  if (record.sync_status && record.sync_status !== 'default') return false;
  const s = record.sync_summary;
  if (!s || typeof s !== 'object') return false;
  return Number(s.total_new || 0) > 0 || Number(s.total_update || 0) > 0;
}
