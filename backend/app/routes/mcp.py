#coding: utf-8

from flask import make_response, request
from flask_restx import Resource, Namespace
from bson import ObjectId
from datetime import datetime, timedelta, timezone
import csv
from functools import wraps
import io
import json
import time
import math
import re
from urllib.parse import urlsplit

from app.utils import get_logger, auth
from app import utils
from app.mcp_security import (
    MCPRequestError, authenticate_mcp_token, authorize_tool,
    consume_mcp_quota, load_mcp_policy, record_mcp_audit, READ_TOOLS, WRITE_TOOLS,
)

ns = Namespace('mcp', description="MCP API 接口")
logger = get_logger()


def csv_literal(value):
    if isinstance(value, str) and value.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def _build_mcp_logs_query(tool_name='', status='', target='', key_id='', time_range=''):
    query = {}
    if tool_name:
        query["tool_name"] = tool_name
    if status:
        if status == 'abnormal':
            query["status"] = {"$in": ["error", "denied"]}
        else:
            query["status"] = status
    if target:
        query["target"] = {"$regex": re.escape(target), "$options": "i"}
    if key_id:
        query["key_id"] = key_id
    if time_range:
        now = datetime.now(timezone.utc)
        if time_range == 'today':
            today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
            query["created_at"] = {"$gte": today_start}
        elif time_range == '24h':
            yesterday = now - timedelta(days=1)
            query["created_at"] = {"$gte": yesterday}
        elif time_range == '7d':
            seven_days_ago = now - timedelta(days=7)
            query["created_at"] = {"$gte": seven_days_ago}
    return query

@ns.route('/task_detail_export')
class MCPTaskDetailExport(Resource):
    @auth
    def get(self):
        """
        MCP专用任务数据导出接口，返回CSV格式
        """
        task_id = request.args.get('task_id', '')
        tab = request.args.get('tab', 'site')
        try:
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 100))
        except ValueError:
            page = 1
            limit = 100
            
        columns_str = request.args.get('columns', '')
        columns = [c.strip() for c in columns_str.split(',') if c.strip()] if columns_str else []

        if not task_id or len(task_id) != 24:
            return {"code": 400, "message": "Invalid task_id"}, 400

        allowed_tabs = ["site", "domain", "ip", "wih", "fileleak", "vuln", "nuclei_result", "cert", "service", "url", "npoc_service", "stat_finger", "cip"]
        if tab not in allowed_tabs:
            return {"code": 400, "message": f"Unsupported tab. Allowed: {allowed_tabs}"}, 400
            
        query = {"task_id": task_id}
        skip = (page - 1) * limit
        
        projection = None
        if tab == "site":
            projection = {"favicon.data": 0, "body": 0, "header": 0, "headers": 0} # 剔除庞大且无用的字段
            
        cursor = utils.conn_db(tab).find(query, projection).skip(skip).limit(limit)
        items = list(cursor)
        
        if not items:
            response = make_response("")
            response.headers['Content-Type'] = 'text/csv'
            return response
            
        flattened_items = []
        for item in items:
            flat_item = {}
            for k, v in item.items():
                if k == '_id':
                    flat_item[k] = str(v)
                elif tab == 'ip' and k == 'port_info' and isinstance(v, list):
                    flat_item['开放端口'] = " ".join([str(p.get('port_id', '')) for p in v if 'port_id' in p])
                elif tab == 'ip' and k == 'geo_city' and isinstance(v, dict):
                    parts = [p for p in [v.get('country_name'), v.get('region_name'), v.get('city')] if p and p not in ('None', 'null', '0')]
                    clean_p: list[str] = []
                    for item_p in parts:
                        if not clean_p or clean_p[-1] != item_p:
                            clean_p.append(item_p)
                    flat_item['geo'] = "/".join(clean_p)
                elif tab == 'ip' and k == 'geo_asn' and isinstance(v, dict):
                    flat_item['as'] = v.get('organization', '')
                elif tab == 'ip' and k == 'os_info' and isinstance(v, dict):
                    flat_item['操作系统'] = v.get('name', '')
                elif tab == 'site' and k == 'finger' and isinstance(v, list):
                    flat_item['finger'] = " ".join([f.get('name', '') for f in v if 'name' in f])
                elif tab == 'cert' and isinstance(v, dict):
                    flat_item[k] = "; ".join([f"{sub_k}:{sub_v}" for sub_k, sub_v in v.items() if sub_v])
                elif isinstance(v, list):
                    flat_item[k] = " ".join([str(i) for i in v])
                elif isinstance(v, dict):
                    # Flatten simple dicts
                    flat_item[k] = "; ".join([f"{sub_k}:{sub_v}" for sub_k, sub_v in v.items() if sub_v and not isinstance(sub_v, (dict, list))])
                else:
                    flat_item[k] = str(v)
            flattened_items.append(flat_item)
            
        if columns:
            headers = columns
        else:
            headers_set: set[str] = set()
            for flat_item in flattened_items:
                headers_set.update(flat_item.keys())
            headers = sorted(list(headers_set))
            
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([csv_literal(value) for value in headers])
        writer.writerows([csv_literal(item.get(key, '')) for key in headers] for item in flattened_items)
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        return response


from app.mcp_asset import build_asset_profile, build_enterprise_profile, _clean_empty


def mcp_readonly(tool_name):
    """Apply the same credential, policy, quota and audit checks to both profiles."""
    def decorate(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            token = request.headers.get('Token') or request.headers.get('Authorization', '')
            user = authenticate_mcp_token(token)
            if not user:
                return {'code': 401, 'message': 'Invalid or expired MCP credential'}, 401
            user['client_ip'] = request.headers.get('X-Real-IP') or request.remote_addr or ''
            arguments = request.args.to_dict()
            target = arguments.get('target', '').strip() or arguments.get('task_id', '').strip()
            started = time.monotonic()
            result, is_error = {}, True
            audit_call = True
            try:
                policy = load_mcp_policy()
                consume_mcp_quota(user, policy)
                authorize_tool(user, tool_name, policy)
                response = func(*args, **kwargs)
                result = response[0] if isinstance(response, tuple) else response
                is_error = result.get('status') in ('error', 'auth_error') or result.get('code', 200) != 200
                return response
            except MCPRequestError as error:
                audit_call = error.audit
                headers = {'Retry-After': str(error.retry_after)} if error.retry_after is not None else {}
                result = {'code': error.status, 'status': 'denied', 'message': str(error)}
                return result, error.status, headers
            except Exception:
                result = {'code': 500, 'message': 'MCP profile lookup failed'}
                raise
            finally:
                if audit_call:
                    record_mcp_audit(user, tool_name, target, arguments, result, is_error,
                                     int((time.monotonic() - started) * 1000))
        return wrapped
    return decorate


@ns.route('/asset_profile')
class MCPAssetProfile(Resource):
    @mcp_readonly('get_asset_profile')
    def get(self):
        target = request.args.get('target', '').strip()
        task_id = request.args.get('task_id', '').strip()
        if not target:
            return {'code': 400, 'message': 'Missing target parameter'}, 400
        return build_asset_profile(target, task_id)


@ns.route('/enterprise_profile')
class MCPEnterpriseProfile(Resource):
    @mcp_readonly('get_enterprise_profile')
    def get(self):
        """
        MCP 企业生态资产画像接口（自适应识别企业、总览指标、核心样本与分维度下钻）
        """
        target = request.args.get('target', '').strip()
        task_id = request.args.get('task_id', '').strip()
        category = request.args.get('category', 'all').strip()
        page = request.args.get('page', 1)
        size = request.args.get('size', 20)

        if not target and not task_id:
            return {"code": 400, "message": "Target or task_id parameter is required"}, 400

        data = build_enterprise_profile(target=target, category=category, page=page, size=size, task_id=task_id)
        return data


@ns.route('/export_server')
class MCPExportServer(Resource):
    @auth
    def post(self):
        return self.get()

    @auth
    def get(self):
        """
        动态导出预置当前用户专属凭据的独立 MCP 客户端脚本 (arl_mcp.py)
        """
        from pathlib import Path
        candidate_paths = [
            Path(__file__).resolve().parent.parent.parent.parent / "mcp-server" / "server.py",
            Path("/code/mcp-server/server.py"),
            Path("/code/frontend/public/mcp/server.py"),
            Path("/code/frontend/dist/mcp/server.py"),
            Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "public" / "mcp" / "server.py",
        ]
        server_path = None
        for p in candidate_paths:
            if p.exists() and p.is_file():
                server_path = p
                break

        if not server_path:
            return {"code": 404, "message": "server.py template not found on server"}, 404

        try:
            content = server_path.read_text(encoding="utf-8")
        except Exception as e:
            return {"code": 500, "message": f"Failed to read template: {str(e)}"}, 500

        # 获取当前用户 Token 与访问 Host
        user_token = (request.headers.get("Token") or "").strip()

        # 探测 Host 优先级：
        # 1. 显式 query 参数 ?host=
        # 2. 浏览器 Origin / Referer 请求头
        # 3. 反向代理头 X-Forwarded-Host / Host 与 X-Forwarded-Proto
        # 4. request.host_url
        export_args = request.get_json(silent=True) if request.method == 'POST' else request.args
        if ((request.method == 'POST' and not isinstance(export_args, dict))
                or (request.method == 'GET' and 'raw_key' in request.args)):
            return {'code': 400, 'message': 'Send dedicated MCP credentials in a POST JSON body'}, 400
        req_host = str(export_args.get("host", "")).strip()
        if req_host:
            host = req_host.rstrip("/")
        else:
            origin = request.headers.get("Origin", "").strip()
            referer = request.headers.get("Referer", "").strip()
            if origin:
                host = origin.rstrip("/")
            elif referer:
                import urllib.parse
                p = urllib.parse.urlparse(referer)
                host = f"{p.scheme}://{p.netloc}".rstrip("/")
            else:
                forwarded_proto = request.headers.get("X-Forwarded-Proto", "").strip() or ("https" if request.is_secure else "http")
                forwarded_host = request.headers.get("X-Forwarded-Host", "").strip() or request.headers.get("Host", "").strip()
                if forwarded_host:
                    host = f"{forwarded_proto}://{forwarded_host}"
                else:
                    host = request.host_url.rstrip("/")

        try:
            parsed = urlsplit(host)
            if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or parsed.path not in ('', '/') or parsed.query or parsed.fragment
                    or any(c in host for c in ('"', "'", '\\', '\r', '\n'))
                    or any(ord(c) <= 32 for c in host)
                    or (parsed.port is not None and not 1 <= parsed.port <= 65535)):
                raise ValueError('Invalid host')
        except ValueError:
            return {'code': 400, 'message': 'Invalid server origin'}, 400

        # Serialize values as Python-compatible JSON string literals, never source.
        raw_key = str(export_args.get("raw_key", "")).strip() if request.method == 'POST' else ''
        if request.method == 'POST' and 'raw_key' in export_args:
            identity = authenticate_mcp_token(raw_key)
            if not identity or identity.get('type') != 'mcp_key' or 'asset:read' not in identity.get('scopes', []):
                return {'code': 400, 'message': 'A complete, active MCP key with asset:read scope is required'}, 400
        effective_token = raw_key or user_token
        if effective_token:
            content = content.replace('DEFAULT_TOKEN = ""', 'DEFAULT_TOKEN = ' + json.dumps(effective_token))
        if host:
            content = content.replace('DEFAULT_HOST = ""', 'DEFAULT_HOST = ' + json.dumps(host))

        response = make_response(content)
        response.headers['Content-Type'] = 'text/x-python; charset=utf-8'
        response.headers['Content-Disposition'] = 'attachment; filename="arl_mcp.py"'
        response.headers['Cache-Control'] = 'private, no-store'
        return response


@ns.route('/overview')
class MCPOverview(Resource):
    @auth
    def get(self):
        """MCP 治理中心状态大盘与调用统计概览"""
        try:
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
            seven_days_ago = now - timedelta(days=7)

            # 今日调用量
            today_calls = utils.conn_db('mcp_log').count_documents({"created_at": {"$gte": today_start}})
            # 7日累计调用量
            week_calls = utils.conn_db('mcp_log').count_documents({"created_at": {"$gte": seven_days_ago}})
            # 总 Key 数与活跃 Key 数
            total_keys = utils.conn_db('mcp_key').count_documents({})
            active_keys = utils.conn_db('mcp_key').count_documents({"status": "active"})
            # 24小时内异常数
            yesterday = now - timedelta(days=1)
            error_calls = utils.conn_db('mcp_log').count_documents({"created_at": {"$gte": yesterday}, "status": {"$ne": "success"}})

            # 近 7 天趋势聚合
            pipeline_trend = [
                {"$match": {"created_at": {"$gte": seven_days_ago}}},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}
                        },
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"_id": 1}}
            ]
            trend_raw = list(utils.conn_db('mcp_log').aggregate(pipeline_trend))
            trend_map = {item["_id"]: item["count"] for item in trend_raw if "_id" in item}
            trend_dates = []
            for i in range(6, -1, -1):
                d_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
                trend_dates.append({"date": d_str, "count": trend_map.get(d_str, 0)})

            # 热门工具 Top 5
            pipeline_tools = [
                {"$group": {"_id": "$tool_name", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            top_tools = [{"tool": item["_id"], "count": item["count"]} for item in utils.conn_db('mcp_log').aggregate(pipeline_tools) if item.get("_id")]

            return {
                "code": 200,
                "message": "success",
                "data": {
                    "today_calls": today_calls,
                    "week_calls": week_calls,
                    "total_keys": total_keys,
                    "active_keys": active_keys,
                    "error_calls_24h": error_calls,
                    "trend": trend_dates,
                    "top_tools": top_tools,
                    "service_status": "running"
                }
            }
        except Exception as e:
            logger.error(f"MCPOverview error: {e}", exc_info=True)
            return {"code": 500, "message": str(e)}, 500


@ns.route('/keys')
class MCPKeys(Resource):
    @auth
    def get(self):
        """分页获取 MCP API Key 列表"""
        try:
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 10))
            keyword = request.args.get('keyword', '').strip()
        except ValueError:
            page = 1
            size = 10
            keyword = ''
        page, size = min(2_147_483_647, max(1, page)), min(100, max(1, size))

        query = {}
        if keyword:
            query["$or"] = [
                {"name": {"$regex": re.escape(keyword), "$options": "i"}},
                {"key_prefix": {"$regex": re.escape(keyword), "$options": "i"}}
            ]

        total = utils.conn_db('mcp_key').count_documents(query)
        cursor = utils.conn_db('mcp_key').find(query, {"key_hash": 0}).sort("created_at", -1).skip((page - 1) * size).limit(size)
        items = []
        from datetime import datetime
        for doc in cursor:
            created_at = doc.get("created_at")
            if isinstance(created_at, datetime):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
            expire_at = doc.get("expire_at")
            if isinstance(expire_at, datetime):
                expire_at = expire_at.strftime('%Y-%m-%d %H:%M:%S')
            last_used_at = doc.get("last_used_at")
            if isinstance(last_used_at, datetime):
                last_used_at = last_used_at.strftime('%Y-%m-%d %H:%M:%S')

            items.append({
                "id": str(doc["_id"]),
                "name": doc.get("name", ""),
                "key_prefix": doc.get("key_prefix", ""),
                "scopes": doc.get("scopes", ["asset:read"]),
                "status": doc.get("status", "active"),
                "expire_at": expire_at,
                "created_at": created_at,
                "created_by": doc.get("created_by", "admin"),
                "last_used_at": last_used_at,
                "last_ip": doc.get("last_ip")
            })

        return {
            "code": 200,
            "message": "success",
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "size": size
            }
        }

    @auth
    def post(self):
        """创建新的 MCP API Key（仅在创建响应中返回明文密钥）"""
        import secrets
        import hashlib
        from datetime import datetime, timedelta, timezone
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return {'code': 400, 'message': 'Expected a JSON object'}, 400
        name = str(data.get("name", "")).strip()
        if not name:
            return {"code": 400, "message": "Key name is required"}, 400
        if len(name) > 50:
            return {"code": 400, "message": "Key name is too long (max 50 chars)"}, 400

        scopes = data.get("scopes", ["asset:read"])
        if (not isinstance(scopes, list) or not scopes
                or any(scope not in ('asset:read', 'task:dispatch') for scope in scopes)):
            return {'code': 400, 'message': 'Choose valid, nonempty MCP scopes'}, 400

        expire_days = data.get("expire_days", 0)
        expire_at = None
        now = datetime.now(timezone.utc)
        max_days = (datetime.max.replace(tzinfo=timezone.utc) - now).days
        if (type(expire_days) not in (int, float) or expire_days < 0 or expire_days > max_days
                or (isinstance(expire_days, float) and not math.isfinite(expire_days))):
            return {'code': 400, 'message': 'Invalid expire_days'}, 400
        if expire_days > 0:
            expire_at = now + timedelta(days=expire_days)

        # 生成安全随机密钥
        raw_token = secrets.token_urlsafe(24)
        raw_key = f"arl_mcp_{raw_token}"
        key_prefix = raw_key[:12] + "..."
        key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        # 检查当前用户身份
        user_token = request.headers.get("Token", "")
        current_username = "admin"
        try:
            u_doc = utils.conn_db('user').find_one({'token': user_token})
            if u_doc:
                current_username = u_doc.get("username", "admin")
        except Exception:
            pass

        key_doc = {
            "name": name,
            "key_prefix": key_prefix,
            "key_hash": key_hash,
            "scopes": scopes,
            "status": "active",
            "expire_at": expire_at,
            "created_at": datetime.now(timezone.utc),
            "created_by": current_username,
            "last_used_at": None,
            "last_ip": None
        }
        res = utils.conn_db('mcp_key').insert_one(key_doc)

        return {
            "code": 200,
            "message": "Key created successfully",
            "data": {
                "id": str(res.inserted_id),
                "name": name,
                "key_prefix": key_prefix,
                "raw_key": raw_key,
                "scopes": scopes,
                "expire_at": expire_at.strftime('%Y-%m-%d %H:%M:%S') if expire_at else None
            }
        }


@ns.route('/keys/<string:key_id>/status')
class MCPKeyStatus(Resource):
    @auth
    def post(self, key_id):
        """变更 API Key 状态（启用/停用/吊销）"""
        if not ObjectId.is_valid(key_id):
            return {"code": 400, "message": "Invalid key_id"}, 400

        from datetime import datetime, timezone
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return {'code': 400, 'message': 'Expected a JSON object'}, 400
        new_status = data.get("status")
        if new_status not in ("active", "revoked"):
            return {"code": 400, "message": "Invalid status. Allowed: active, revoked"}, 400

        res = utils.conn_db('mcp_key').update_one(
            {"_id": ObjectId(key_id)},
            {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}}
        )
        if res.matched_count == 0:
            return {"code": 404, "message": "Key not found"}, 404

        return {"code": 200, "message": f"Key status updated to {new_status}"}


@ns.route('/keys/<string:key_id>')
class MCPKeyDelete(Resource):
    @auth
    def delete(self, key_id):
        """删除指定 API Key"""
        if not ObjectId.is_valid(key_id):
            return {"code": 400, "message": "Invalid key_id"}, 400

        res = utils.conn_db('mcp_key').delete_one({"_id": ObjectId(key_id)})
        if res.deleted_count == 0:
            return {"code": 404, "message": "Key not found"}, 404

        return {"code": 200, "message": "Key deleted successfully"}


@ns.route('/logs')
class MCPLogs(Resource):
    @auth
    def get(self):
        """多条件分页查询 MCP 审计日志"""
        try:
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 10))
        except ValueError:
            page = 1
            size = 10
        page, size = min(2_147_483_647, max(1, page)), min(100, max(1, size))

        tool_name = request.args.get('tool_name', '').strip()
        status = request.args.get('status', '').strip()
        target = request.args.get('target', '').strip()
        key_id = request.args.get('key_id', '').strip()
        time_range = request.args.get('time_range', '').strip()

        query = _build_mcp_logs_query(tool_name, status, target, key_id, time_range)

        total = utils.conn_db('mcp_log').count_documents(query)
        cursor = utils.conn_db('mcp_log').find(query).sort("created_at", -1).skip((page - 1) * size).limit(size)

        from datetime import datetime
        items = []
        for doc in cursor:
            created_at = doc.get("created_at")
            if isinstance(created_at, datetime):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')

            items.append({
                "id": str(doc["_id"]),
                "key_id": doc.get("key_id", ""),
                "key_name": doc.get("key_name", ""),
                "client_ip": doc.get("client_ip", ""),
                "tool_name": doc.get("tool_name", ""),
                "target": doc.get("target", ""),
                "params_summary": doc.get("params_summary", ""),
                "status": doc.get("status", "success"),
                "duration_ms": doc.get("duration_ms", 0),
                "summary": doc.get("summary", ""),
                "error_message": doc.get("error_message", ""),
                "created_at": created_at
            })

        return {
            "code": 200,
            "message": "success",
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "size": size
            }
        }


@ns.route('/logs/export')
class MCPLogsExport(Resource):
    @auth
    def get(self):
        """导出 MCP 调用审计日志为 CSV"""
        tool_name = request.args.get('tool_name', '').strip()
        status = request.args.get('status', '').strip()
        target = request.args.get('target', '').strip()
        key_id = request.args.get('key_id', '').strip()
        time_range = request.args.get('time_range', '').strip()

        query = _build_mcp_logs_query(tool_name, status, target, key_id, time_range)

        cursor = utils.conn_db('mcp_log').find(query).sort("created_at", -1).limit(5000)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["调用时间", "密钥名称", "来源IP", "工具名称", "查询标的", "执行状态", "耗时(ms)", "返回摘要", "异常信息"])

        from datetime import datetime
        for doc in cursor:
            c_at = doc.get("created_at")
            if isinstance(c_at, datetime):
                c_at = c_at.strftime('%Y-%m-%d %H:%M:%S')
            writer.writerow([
                csv_literal(c_at or ""),
                csv_literal(doc.get("key_name", "")),
                csv_literal(doc.get("client_ip", "")),
                csv_literal(doc.get("tool_name", "")),
                csv_literal(doc.get("target", "")),
                csv_literal(doc.get("status", "")),
                csv_literal(str(doc.get("duration_ms", 0))),
                csv_literal(doc.get("summary", "")),
                csv_literal(doc.get("error_message", ""))
            ])

        response = make_response("\ufeff" + output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = 'attachment; filename="mcp_audit_logs.csv"'
        return response


@ns.route('/config')
class MCPConfig(Resource):
    @auth
    def get(self):
        """获取 MCP 全局配置与工具开关"""
        cfg = utils.conn_db('mcp_config').find_one({"_id": "global"})
        if not cfg:
            cfg = {
                "tool_switches": {
                    "get_asset_profile": True,
                    "get_enterprise_profile": True,
                    "search_assets": True,
                    "get_task_status": True,
                    "create_scan_task": False,
                    "stop_scan_task": False
                },
                "max_search_limit": 50,
                "rate_limit_per_min": 120
            }
        return {
            "code": 200,
            "message": "success",
            "data": {
                "tool_switches": cfg.get("tool_switches", {}),
                "max_search_limit": cfg.get("max_search_limit", 50),
                "rate_limit_per_min": cfg.get("rate_limit_per_min", 120)
            }
        }

    @auth
    def post(self):
        """保存 MCP 全局配置与工具开关"""
        from datetime import datetime
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return {'code': 400, 'message': 'Expected a JSON object'}, 400
        tool_switches = data.get("tool_switches")
        max_search_limit = data.get("max_search_limit")
        rate_limit_per_min = data.get("rate_limit_per_min")

        update_set: dict[str, object] = {"updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        if 'tool_switches' in data:
            if (not isinstance(tool_switches, dict) or any(
                    name not in READ_TOOLS | WRITE_TOOLS or type(value) is not bool
                    for name, value in tool_switches.items())):
                return {'code': 400, 'message': 'Tool switches must be known tools with boolean values'}, 400
            update_set.update({f'tool_switches.{name}': value for name, value in tool_switches.items()})
        for name, value, lower, upper in (('max_search_limit', max_search_limit, 1, 200),
                                         ('rate_limit_per_min', rate_limit_per_min, 10, 1000)):
            if name in data:
                if type(value) is not int or not lower <= value <= upper:
                    return {'code': 400, 'message': f'Invalid {name}'}, 400
                update_set[name] = value

        # Initialize once, then update only supplied fields. Replacing the
        # switch object would erase previously disabled tools on partial saves.
        utils.conn_db('mcp_config').update_one({'_id': 'global'}, {'$setOnInsert': {
            'tool_switches': {name: name in READ_TOOLS for name in READ_TOOLS | WRITE_TOOLS},
            'max_search_limit': 50, 'rate_limit_per_min': 120,
        }}, upsert=True)
        utils.conn_db('mcp_config').update_one(
            {"_id": "global"},
            {"$set": update_set},
            upsert=True
        )
        return {"code": 200, "message": "Configuration saved successfully"}
