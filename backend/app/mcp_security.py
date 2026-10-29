"""Authentication, tool policy and shared quotas for MCP transports."""

import hashlib
import hmac
import json
import logging
import math
import os
import time
from datetime import UTC, datetime

from bson import ObjectId
from pymongo import ReturnDocument

from app import utils
from app.config import Config

READ_TOOLS = frozenset(('get_asset_profile', 'get_enterprise_profile', 'search_assets', 'get_task_status'))
WRITE_TOOLS = frozenset(('create_scan_task', 'stop_scan_task'))
logger = logging.getLogger('arl_mcp')


class MCPRequestError(Exception):
    def __init__(self, message, status=403, retry_after=None, audit=True):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after
        self.audit = audit


def authenticate_mcp_token(token, config=None):
    config = Config if config is None else config
    if not config.AUTH:
        return {'username': 'anonymous', 'type': 'no_auth', 'key_id': 'none',
                'key_name': 'anonymous', 'scopes': ['asset:read', 'task:dispatch']}
    if not isinstance(token, str) or not token.strip():
        return None
    token = token.strip()
    if token.lower().startswith('bearer '):
        token = token[7:].strip()
    api_key = config.API_KEY
    if isinstance(api_key, str) and api_key and hmac.compare_digest(token.encode(), api_key.encode()):
        return {'username': 'ARL-API', 'type': 'api', 'key_id': 'legacy',
                'key_name': '[System API Key]', 'token': token,
                'scopes': ['asset:read', 'task:dispatch']}
    try:
        if token.startswith('arl_mcp_'):
            key = utils.conn_db('mcp_key').find_one({'key_hash': hashlib.sha256(token.encode()).hexdigest()})
            if not key or key.get('status') != 'active':
                return None
            expires = key.get('expire_at')
            if expires is not None:
                if not isinstance(expires, datetime):
                    return None
                # PyMongo's default codec returns UTC datetimes without tzinfo.
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=UTC)
                if expires <= datetime.now(UTC):
                    return None
            return {'username': key.get('created_by', 'admin'), 'type': 'mcp_key',
                    'key_id': str(key['_id']), 'key_name': key.get('name', 'MCP-Key'),
                    'scopes': key.get('scopes', ['asset:read']), 'token': token}
        user = utils.conn_db('user').find_one({'token': token, 'token_expire_at': {'$gt': datetime.now(UTC)}})
        if user:
            return {'username': user.get('username', 'admin'), 'type': 'user',
                    'key_id': 'legacy', 'key_name': '[Legacy Token]', 'token': token,
                    'scopes': ['asset:read', 'task:dispatch']}
    except Exception:
        logger.warning('MCP credential lookup failed', exc_info=True)
    return None


def load_mcp_policy(dispatch_enabled=None):
    if dispatch_enabled is None:
        dispatch_enabled = os.environ.get('ARL_MCP_ENABLE_DISPATCH', '').lower().strip() in ('true', '1', 'yes')
    try:
        cfg = utils.conn_db('mcp_config').find_one({'_id': 'global'}) or {}
        switches = {name: True for name in READ_TOOLS}
        switches.update({name: bool(dispatch_enabled) for name in WRITE_TOOLS})
        for name, enabled in cfg.get('tool_switches', {}).items():
            if name in switches:
                if type(enabled) is not bool:
                    raise ValueError('Invalid stored MCP switch')
                switches[name] = enabled
        return {'tool_switches': switches,
                'max_search_limit': min(200, max(1, int(cfg.get('max_search_limit', 50)))),
                'rate_limit_per_min': min(1000, max(10, int(cfg.get('rate_limit_per_min', 120))))}
    except Exception as exc:
        raise MCPRequestError('MCP policy is temporarily unavailable', 503) from exc


def authorize_tool(user, name, policy):
    if not isinstance(name, str):
        raise MCPRequestError('Invalid tool name', 400)
    if name not in READ_TOOLS | WRITE_TOOLS:
        raise MCPRequestError(f"Tool '{name}' not found", 404)
    scope = 'task:dispatch' if name in WRITE_TOOLS else 'asset:read'
    if scope not in user.get('scopes', ['asset:read']):
        raise MCPRequestError(f"Permission denied: key lacks '{scope}' scope")
    if not policy['tool_switches'].get(name):
        raise MCPRequestError(f"Tool '{name}' is currently disabled in system settings")


def consume_mcp_quota(user, policy):
    """Atomic per-credential minute bucket, shared by SSE and all REST workers."""
    now = time.time()
    bucket = int(now) // 60
    identity = user.get('token') or user.get('key_id') or 'anonymous'
    digest = hashlib.sha256(identity.encode()).hexdigest()
    try:
        counter = utils.conn_db('mcp_rate_limit').find_one_and_update(
            {'_id': f'{digest}:{bucket}'},
            {'$inc': {'count': 1}, '$setOnInsert': {
                'expire_at': datetime.fromtimestamp((bucket + 2) * 60, UTC)}},
            upsert=True, return_document=ReturnDocument.AFTER,
        )
    except Exception as exc:
        raise MCPRequestError('MCP quota service is temporarily unavailable', 503) from exc
    if counter['count'] > policy['rate_limit_per_min']:
        raise MCPRequestError('MCP per-key rate limit exceeded', 429,
                              retry_after=max(1, math.ceil((bucket + 1) * 60 - now)),
                              audit=counter['count'] == policy['rate_limit_per_min'] + 1)


def record_mcp_audit(user, tool_name, target, args, result, is_error, duration_ms):
    """Both transports write the same audit fields without storing credentials."""
    try:
        status = 'error' if is_error else 'success'
        if is_error and result.get('status') == 'denied':
            status = 'denied'
        summaries = {
            'get_asset_profile': f"状态: {result.get('status', 'ok')}",
            'get_enterprise_profile': f"企业: {result.get('enterprise_name') or target} (状态: {result.get('status', 'ok')})",
            'search_assets': f"命中 {result.get('total', 0)} 条记录",
            'get_task_status': f"任务状态: {result.get('status', 'unknown')}",
            'create_scan_task': f"新任务 ID: {result.get('task_id', '')}",
            'stop_scan_task': f"已请求停止任务: {result.get('task_id', '')}",
        }
        params = json.dumps(args, ensure_ascii=False)
        utils.conn_db('mcp_log').insert_one({
            'key_id': user.get('key_id', 'legacy'), 'key_name': user.get('key_name', '[Legacy Token]'),
            'client_ip': user.get('client_ip', ''), 'tool_name': tool_name, 'target': target,
            'params_summary': params[:200] + '...' if len(params) > 200 else params,
            'status': status, 'duration_ms': duration_ms,
            'summary': '' if is_error else summaries.get(tool_name, ''),
            'error_message': str(result.get('message', '')) if is_error else '',
            'created_at': datetime.now(UTC),
        })
        if user.get('type') == 'mcp_key':
            utils.conn_db('mcp_key').update_one({'_id': ObjectId(user['key_id'])}, {'$set': {
                'last_used_at': datetime.now(UTC), 'last_ip': user.get('client_ip', '')}})
    except Exception:
        logger.warning('Failed to record MCP audit log', exc_info=True)
