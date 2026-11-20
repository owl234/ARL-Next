import re
from bson import ObjectId
from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from app import utils
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg, AssetScopeType

# 成立“资产组范围”部门，专门管理“地契”
ns = Namespace('asset_scope', description="资产组范围")

logger = get_logger()

# ==========================================
# 表单：新建和查询时用到的基础字段
# ==========================================
base_fields = {
    'name': fields.String(description="资产组名称"),
    'scope': fields.String(description="资产范围"),
    "scope_type": fields.String(description="资产范围类别"),
    "group_id": fields.String(description="集团ID")
}


add_asset_scope_fields = ns.model('addAssetScope', base_fields)

# 查询时多加一个 _id 和 分页字段
base_fields.update({
    "_id": fields.String(description="资产范围 ID")
})

base_fields.update(base_query_fields)


@ns.route('/')
class ARLAssetScope(ARLResource):
    parser = get_arl_parser(base_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组查看
        """
        args = self.parser.parse_args()
        if args.get('group_id') == 'unassigned':
            args['group_id'] = {"$in": [None, ""]}
            
        data = self.build_data(args=args, collection='asset_scope')

        # 历史数据兼容与探测状态统计
        items = data.get("items", [])
        for item in items:
            if "domain_array" not in item or "ip_array" not in item:
                st = item.get("scope_type")
                sa = item.get("scope_array", [])
                if st == AssetScopeType.DOMAIN:
                    item["domain_array"] = sa
                    item["ip_array"] = []
                elif st == AssetScopeType.IP:
                    item["domain_array"] = []
                    item["ip_array"] = sa
                else:
                    d_arr = []
                    i_arr = []
                    for x in sa:
                        if utils.is_valid_domain(x):
                            d_arr.append(x)
                        else:
                            i_arr.append(x)
                    item["domain_array"] = d_arr
                    item["ip_array"] = i_arr

        if items:
            from app.helpers.scope import populate_scopes_domain_stat
            populate_scopes_domain_stat(items)

        if items:
            scope_id_strs = [str(item.get('_id')) for item in items if item.get('_id')]
            synced_task_ids = []
            updating_task_ids = []
            for item in items:
                stid = item.get('synced_icp_task_id')
                if stid:
                    try:
                        synced_task_ids.append(ObjectId(stid))
                    except Exception:
                        pass
                utid = item.get('updating_icp_task_id')
                if utid:
                    try:
                        updating_task_ids.append(ObjectId(utid))
                    except Exception:
                        pass

            task_query = []
            if scope_id_strs:
                task_query.append({"synced_scope_id": {"$in": scope_id_strs}})
            if synced_task_ids:
                task_query.append({"_id": {"$in": synced_task_ids}})
            if updating_task_ids:
                task_query.append({"_id": {"$in": updating_task_ids}})

            if task_query:
                try:
                    tasks = list(utils.conn_db('icp_task').find({"$or": task_query}))
                    task_by_scope = {}
                    task_by_id = {}
                    for t in tasks:
                        task_by_id[str(t['_id'])] = t
                        if t.get('synced_scope_id'):
                            task_by_scope[t.get('synced_scope_id')] = t

                    for item in items:
                        sid_str = str(item.get('_id'))
                        # build_data 返回的 _id 已被序列化为字符串，落库写回时须还原 ObjectId
                        scope_db_id = ObjectId(sid_str) if ObjectId.is_valid(sid_str) else item.get('_id')

                        # 🛡️ 检查并处理测绘更新中任务状态
                        utid = item.get('updating_icp_task_id')
                        if utid and str(utid) in task_by_id:
                            up_t = task_by_id[str(utid)]
                            up_status = up_t.get('status')
                            if up_status == 'done':
                                # 测绘任务已圆满完成，原子晋升为主指针
                                try:
                                    utils.conn_db('asset_scope').update_one(
                                        {'_id': scope_db_id, 'updating_icp_task_id': str(utid)},
                                        {
                                            '$set': {'synced_icp_task_id': str(up_t['_id'])},
                                            '$unset': {
                                                'updating_icp_task_id': '',
                                                'last_update_error': '',
                                                'last_update_error_task_id': '',
                                                'last_update_error_time': ''
                                            }
                                        }
                                    )
                                    item['synced_icp_task_id'] = str(up_t['_id'])
                                    item.pop('updating_icp_task_id', None)
                                    item.pop('last_update_error', None)
                                    item.pop('last_update_error_task_id', None)
                                    item.pop('last_update_error_time', None)
                                except Exception as up_err:
                                    logger.error(f"Failed to promote updating_icp_task_id: {up_err}")
                            elif up_status == 'error':
                                # 测绘任务执行失败，持久化失败摘要并清理更新中指针，保留原主指针
                                err_msg = up_t.get('error_msg') or '测绘任务执行失败'
                                err_time = up_t.get('end_time') or utils.curr_date()
                                try:
                                    utils.conn_db('asset_scope').update_one(
                                        {'_id': scope_db_id, 'updating_icp_task_id': str(utid)},
                                        {
                                            '$set': {
                                                'last_update_error': err_msg,
                                                'last_update_error_task_id': str(up_t['_id']),
                                                'last_update_error_time': err_time
                                            },
                                            '$unset': {'updating_icp_task_id': ''}
                                        }
                                    )
                                    item.pop('updating_icp_task_id', None)
                                    item['update_error_msg'] = err_msg
                                    item['last_update_error'] = err_msg
                                    item['last_update_error_task_id'] = str(up_t['_id'])
                                    item['last_update_error_time'] = err_time
                                except Exception as up_err:
                                    logger.error(f"Failed to clear failed updating_icp_task_id: {up_err}")
                            elif up_status == 'stop':
                                # 用户手动停止更新，直接清理指针并保留原主指针
                                try:
                                    utils.conn_db('asset_scope').update_one(
                                        {'_id': scope_db_id, 'updating_icp_task_id': str(utid)},
                                        {'$unset': {'updating_icp_task_id': ''}}
                                    )
                                    item.pop('updating_icp_task_id', None)
                                except Exception as up_err:
                                    logger.error(f"Failed to clear stopped updating_icp_task_id: {up_err}")
                            else:
                                item['updating_icp_task_id'] = str(up_t['_id'])
                                item['updating_status'] = up_status
                                item['updating_start_time'] = up_t.get('start_time')
                        elif utid:
                            # 关联的更新任务已被删除或无效，自动清理悬空更新指针
                            try:
                                utils.conn_db('asset_scope').update_one(
                                    {'_id': scope_db_id, 'updating_icp_task_id': utid},
                                    {'$unset': {'updating_icp_task_id': ''}}
                                )
                                item.pop('updating_icp_task_id', None)
                            except Exception as up_err:
                                logger.error(f"Failed to clear missing updating_icp_task_id: {up_err}")

                        if item.get('last_update_error') and not item.get('update_error_msg'):
                            item['update_error_msg'] = item['last_update_error']

                        t = None
                        if item.get('synced_icp_task_id') and str(item['synced_icp_task_id']) in task_by_id:
                            t = task_by_id[str(item['synced_icp_task_id'])]
                        elif sid_str in task_by_scope:
                            t = task_by_scope[sid_str]

                        if t:
                            item['synced_icp_task_id'] = str(t['_id'])
                            if t.get('task_type') == 'tyc' or str(t.get('target', '')).startswith('TYC_'):
                                ent_name = t.get('synced_scope_name') or t.get('name', '').replace('企业测绘', '').strip()
                                item['enterprise_name'] = ent_name or t.get('target')
                            else:
                                item['enterprise_name'] = t.get('target') or t.get('name')
                            item['has_increment'] = t.get('has_increment', False)
                except Exception as e:
                    logger.error(f"enrich scope with icp_task failed: {e}")

        return data

    @auth
    @ns.expect(add_asset_scope_fields)
    def post(self):
        """
        资产组添加：创建一个新的地契
        """
        args = self.parse_args(add_asset_scope_fields)
        name = args.pop('name')
        scope = args.pop('scope')
        # scope_type 前端已不再强传，即使传了也仅作为冗余兜底
        scope_type = args.pop('scope_type', "mixed")

        scope_array = re.split(r",|\s", scope)
        scope_array = list(filter(None, scope_array))

        new_scope_array = []
        domain_array = []
        ip_array = []

        # 4. 【核心验证】：智能探测并分流
        for x in scope_array:
            if utils.is_valid_domain(x):
                new_scope_array.append(x)
                domain_array.append(x)
            else:
                transfer = utils.ip.transfer_ip_scope(x)
                if transfer is not None:
                    new_scope_array.append(transfer)
                    ip_array.append(transfer)
                else:
                    return utils.build_ret(ErrorMsg.DomainInvalid, {"scope": x, "error": "非法的域名或IP格式"})

        if not new_scope_array:
            return utils.build_ret(ErrorMsg.DomainInvalid, {"scope": ""})

        # 5. 组装数据，实行“双轨制”存储
        domain_status = {}
        for d in domain_array:
            domain_status[d] = {
                "status": "unprobed",
                "sync_source": "manual",
                "sync_time": utils.curr_date()
            }

        group_id = args.pop('group_id', None)
        group_name = ""
        if group_id:
            try:
                group = utils.conn_db('asset_group').find_one({'_id': ObjectId(group_id)})
                if group:
                    group_name = group.get('name', '')
                else:
                    group_id = ""
            except Exception:
                group_id = ""

        scope_data = {
            "name": name,
            "group_id": group_id,
            "group_name": group_name,
            "scope_type": scope_type,
            "scope": ",".join(new_scope_array),
            "scope_array": new_scope_array,
            "domain_array": domain_array,
            "domain_status": domain_status,
            "ip_array": ip_array,
        }
        try:
            insert_res = utils.conn_db('asset_scope').insert_one(scope_data)
            scope_id = str(insert_res.inserted_id)
            scope_data.pop("_id", None)
            scope_data["scope_id"] = scope_id
            return utils.build_ret(ErrorMsg.Success, scope_data)
        except Exception as e:
            logger.error(f"create asset_scope error, detail={e}")
            return utils.build_ret(ErrorMsg.Error, {"error": "数据库写入异常，请查看服务端日志"})

# ==========================================
# 接口模块：删除相关 (包含部分删除 和 整体销毁)
# ==========================================
delete_task_get_fields = ns.model('DeleteScopeByID',  {
    'scope': fields.String(description="删除资产范围", required=True),
    'scope_id': fields.String(description="资产范围id", required=True)
})


delete_task_post_fields = ns.model('DeleteScope',  {
    'scope_id': fields.List(fields.String(description="删除资产范围", required=True), required=True)
})


@ns.route('/delete/')
class DeleteARLAssetScope(ARLResource):
    parser = get_arl_parser(delete_task_get_fields, location='args')

    _table = 'asset_scope'

    # 接口 A：局部删除 (GET) - 从某个资产组里，剔除一个具体的域名
    @auth
    @ns.expect(parser)
    def get(self):
        """
        针对资产组删除范围
        """
        args = self.parser.parse_args()
        scope = str(args.pop('scope', "")).lower()  # 比如要删 "baidu.com"
        scope_id = str(args.pop('scope_id', "")).lower()# 在 "资产组A" 里面

        scope_data = self.get_scope_data(scope_id)
        if not scope_data:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"scope_id": scope_id})

        query = {'_id': ObjectId(scope_id)}

        # 防御：要删的东西根本不在这里面
        if scope not in scope_data.get("scope_array", []):
            return utils.build_ret(ErrorMsg.NotFoundScope, {"scope_id": scope_id, "scope":scope})

        # 防御：资产组必须保留至少一个资产范围，禁止清空
        if len(scope_data.get("scope_array", [])) <= 1:
            return utils.build_ret(ErrorMsg.DomainInvalid, {"error": "资产组必须保留至少一个资产范围，禁止清空"})

        # 核心：操作 Python 列表剔除元素，并同步剔除子轨道
        scope_data["scope_array"].remove(scope)
        if "domain_array" in scope_data and scope in scope_data["domain_array"]:
            scope_data["domain_array"].remove(scope)
        if "ip_array" in scope_data and scope in scope_data["ip_array"]:
            scope_data["ip_array"].remove(scope)

        # 同步清理 domain_status 监控状态字典
        domain_status = scope_data.get("domain_status", {})
        if isinstance(domain_status, dict):
            domain_status.pop(scope, None)
            scope_data["domain_status"] = domain_status

        scope_data["scope"] = ",".join(scope_data["scope_array"])
        
        update_fields = {
            "scope_array": scope_data["scope_array"],
            "scope": scope_data["scope"]
        }
        if "domain_array" in scope_data:
            update_fields["domain_array"] = scope_data["domain_array"]
        if "ip_array" in scope_data:
            update_fields["ip_array"] = scope_data["ip_array"]
        if "domain_status" in scope_data:
            update_fields["domain_status"] = scope_data["domain_status"]

        try:
            # 先写后清原子顺序：先更新 asset_scope 使存活栅栏立即生效，再执行 L1->L2->L3 级联清理
            utils.conn_db(self._table).update_one(query, {"$set": update_fields})
            from app.services.asset_cascade_service import cascade_remove_scope_targets
            cascade_remove_scope_targets(str(scope_id), [scope])
        except Exception as e:
            logger.error(f"delete asset_scope target error, scope_id={scope_id}, scope={scope}, detail={e}")
            return utils.build_ret(ErrorMsg.Error, {"error": "数据库操作异常，请查看服务端日志"})

        return utils.build_ret(ErrorMsg.Success, {"scope_id": scope_id, "scope": scope})

    def get_scope_data(self, scope_id):
        try:
            query = {'_id': ObjectId(scope_id)}
            scope_data = utils.conn_db(self._table).find_one(query)
            return scope_data
        except Exception:
            return None

    # 接口 B：整体销毁 (POST) - 统一级联清理
    @auth
    @ns.expect(delete_task_post_fields)
    def post(self):
        """
        删除资产组和资产组中的资产（含显式绑定任务与监控级联清理）
        """
        args = self.parse_args(delete_task_post_fields)
        scope_id_list = args.pop('scope_id')

        try:
            from app.services.asset_cascade_service import cascade_delete_scopes
            res = cascade_delete_scopes(scope_id_list)
            if not res.get("ok"):
                return utils.build_ret(res.get("error", ErrorMsg.NotFoundScopeID), res.get("data", {}))
        except Exception as e:
            logger.error(f"batch delete asset_scope error, scope_ids={scope_id_list}, detail={e}")
            return utils.build_ret(ErrorMsg.Error, {"error": "数据库操作异常，请查看服务端日志"})

        return utils.build_ret(ErrorMsg.Success, {
            "scope_id": scope_id_list,
            "deleted_tasks": res.get("deleted_tasks", 0),
            "deleted_schedulers": res.get("deleted_schedulers", 0),
        })


# ==========================================
# 接口：向现有资产组追加新域名 (POST /add/)
# ==========================================
add_scope_fields = ns.model('AddScope',  {
    'scope': fields.String(description="添加资产范围"),
    "scope_id": fields.String(description="添加资产范围")
})


@ns.route('/add/')
class AddARLAssetScope(ARLResource):
    @auth
    @ns.expect(add_scope_fields)
    def post(self):
        """
        添加资产范围(局部追加)
        """
        args = self.parse_args(add_scope_fields)
        scope = str(args.pop('scope', "")).lower()

        scope_id = args.pop('scope_id', "")

        table = 'asset_scope'
        try:
            query = {'_id': ObjectId(scope_id)}
        except Exception:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"scope_id": scope_id})

        scope_data = utils.conn_db(table).find_one(query)
        if not scope_data:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"scope_id": scope_id, "scope": scope})

        # 兜底旧数据
        if "domain_array" not in scope_data:
            st = scope_data.get("scope_type")
            sa = scope_data.get("scope_array", [])
            scope_data["domain_array"] = list(sa) if st == AssetScopeType.DOMAIN else []
            scope_data["ip_array"] = list(sa) if st == AssetScopeType.IP else []

        scope_array = re.split(r",|\s", scope)
        scope_array = list(filter(None, scope_array))
        if not scope_array:
            return utils.build_ret(ErrorMsg.DomainInvalid, {"scope": ""})

        for x in scope_array:
            new_scope = x
            if utils.is_valid_domain(x):
                if new_scope in scope_data.get("scope_array", []):
                    return utils.build_ret(ErrorMsg.ExistScope, {"scope_id": scope_id, "scope": x})
                scope_data["scope_array"].append(new_scope)
                scope_data["domain_array"].append(new_scope)
            else:
                transfer = utils.ip.transfer_ip_scope(x)
                if transfer is not None:
                    new_scope = transfer
                    if new_scope in scope_data.get("scope_array", []):
                        return utils.build_ret(ErrorMsg.ExistScope, {"scope_id": scope_id, "scope": x})
                    scope_data["scope_array"].append(new_scope)
                    scope_data["ip_array"].append(new_scope)
                else:
                    return utils.build_ret(ErrorMsg.DomainInvalid, {"scope": x, "error": "非法的域名或IP格式"})

        domain_status = scope_data.get("domain_status", {})
        if not isinstance(domain_status, dict):
            domain_status = {}
        for d in scope_data.get("domain_array", []):
            if d not in domain_status:
                domain_status[d] = {
                    "status": "unprobed",
                    "sync_source": "manual",
                    "sync_time": utils.curr_date()
                }
        scope_data["domain_status"] = domain_status
        scope_data["scope"] = ",".join(scope_data["scope_array"])
        
        update_fields = {
            "scope_array": scope_data["scope_array"],
            "domain_array": scope_data["domain_array"],
            "ip_array": scope_data["ip_array"],
            "domain_status": scope_data["domain_status"],
            "scope": scope_data["scope"]
        }
        
        try:
            utils.conn_db(table).update_one(query, {"$set": update_fields})
        except Exception as e:
            logger.error(f"add asset_scope error, scope_id={scope_id}, scope={scope}, detail={e}")
            return utils.build_ret(ErrorMsg.Error, {"error": "数据库写入异常，请查看服务端日志"})

        return utils.build_ret(ErrorMsg.Success, {"scope_id": scope_id, "scope": scope})


# ==========================================
# 接口：全量/批量更新资产范围 (POST /update/ 或 /edit/)
# ==========================================
update_scope_fields = ns.model('UpdateScope', {
    '_id': fields.String(description="资产范围 ID"),
    'scope_id': fields.String(description="资产范围 ID（别名兼容）"),
    'name': fields.String(description="资产组名称"),
    'scope': fields.String(description="资产范围（完整新列表）"),
    'group_id': fields.String(description="集团ID")
})


@ns.route('/update/')
@ns.route('/edit/')
class UpdateARLAssetScope(ARLResource):
    @auth
    @ns.expect(update_scope_fields)
    def post(self):
        """
        修改/批量更新资产组范围（含 Diff 计算与级联删除孤儿资产）
        """
        args = self.parse_args(update_scope_fields)
        scope_id = args.pop('_id', None) or args.pop('scope_id', None)
        if not scope_id:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"error": "缺少资产组 ID"})

        table = 'asset_scope'
        try:
            query = {'_id': ObjectId(scope_id)}
        except Exception:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"scope_id": scope_id})

        scope_data = utils.conn_db(table).find_one(query)
        if not scope_data:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"scope_id": scope_id})

        # 兜底旧数据
        if "domain_array" not in scope_data:
            st = scope_data.get("scope_type")
            sa = scope_data.get("scope_array", [])
            scope_data["domain_array"] = list(sa) if st == AssetScopeType.DOMAIN else []
            scope_data["ip_array"] = list(sa) if st == AssetScopeType.IP else []

        update_fields = {}
        old_name = scope_data.get("name")
        removed_scopes = set()
        
        name = args.pop('name', None)
        if name:
            update_fields["name"] = name
            scope_data["name"] = name

        group_id = args.pop('group_id', None)
        if group_id is not None:
            if group_id:
                try:
                    group = utils.conn_db('asset_group').find_one({'_id': ObjectId(group_id)})
                    if group:
                        update_fields["group_id"] = group_id
                        update_fields["group_name"] = group.get('name', '')
                        scope_data["group_id"] = group_id
                        scope_data["group_name"] = group.get('name', '')
                except Exception:
                    pass
            else:
                update_fields["group_id"] = ""
                update_fields["group_name"] = ""
                scope_data["group_id"] = ""
                scope_data["group_name"] = ""

        scope = args.pop('scope', None)
        if scope is not None:
            raw_scope_array = re.split(r",|\s", scope)
            raw_scope_array = list(filter(None, raw_scope_array))

            if not raw_scope_array:
                return utils.build_ret(ErrorMsg.DomainInvalid, {"error": "资产组必须保留至少一个资产范围，禁止清空"})

            new_scope_array = []
            domain_array = []
            ip_array = []

            # 智能探测并去重保留顺序
            seen = set()
            for x in raw_scope_array:
                x = x.strip().lower()
                if not x:
                    continue
                if utils.is_valid_domain(x):
                    item = x
                    if item not in seen:
                        seen.add(item)
                        new_scope_array.append(item)
                        domain_array.append(item)
                else:
                    transfer = utils.ip.transfer_ip_scope(x)
                    if transfer is not None:
                        item = transfer
                        if item not in seen:
                            seen.add(item)
                            new_scope_array.append(item)
                            ip_array.append(item)
                    else:
                        return utils.build_ret(ErrorMsg.DomainInvalid, {"scope": x, "error": "非法的域名或IP格式"})

            if not new_scope_array:
                return utils.build_ret(ErrorMsg.DomainInvalid, {"error": "未包含有效的域名或IP"})

            old_scopes = set(scope_data.get("scope_array", []))
            current_new_scopes = set(new_scope_array)

            removed_scopes = old_scopes - current_new_scopes

            domain_status = scope_data.get("domain_status", {})
            if not isinstance(domain_status, dict):
                domain_status = {}

            for removed in removed_scopes:
                domain_status.pop(removed, None)

            for d in domain_array:
                if d not in domain_status:
                    domain_status[d] = {
                        "status": "unprobed",
                        "sync_source": "manual",
                        "sync_time": utils.curr_date()
                    }

            scope_data["domain_status"] = domain_status
            scope_data["scope_array"] = new_scope_array
            scope_data["domain_array"] = domain_array
            scope_data["ip_array"] = ip_array
            scope_data["scope"] = ",".join(new_scope_array)
            
            update_fields["domain_status"] = domain_status
            update_fields["scope_array"] = new_scope_array
            update_fields["domain_array"] = domain_array
            update_fields["ip_array"] = ip_array
            update_fields["scope"] = scope_data["scope"]

        if update_fields:
            try:
                # 先写后清原子顺序：先落库更新 asset_scope，确保存活栅栏立即拦截已剔除目标
                utils.conn_db(table).update_one(query, {"$set": update_fields})
            except Exception as e:
                logger.error(f"update asset_scope error, scope_id={scope_id}, detail={e}")
                return utils.build_ret(ErrorMsg.Error, {"error": "数据库写入异常，请查看服务端日志"})

            from app.services.asset_cascade_service import (
                _sync_scope_rename_references,
                bump_asset_cache_versions,
                cascade_remove_scope_targets,
            )

            if name and old_name and name != old_name:
                try:
                    _sync_scope_rename_references(str(scope_id), old_name, name)
                except Exception as rename_err:
                    logger.warning(f"sync rename references failed for scope {scope_id}: {rename_err}")

            if removed_scopes:
                try:
                    cascade_remove_scope_targets(str(scope_id), list(removed_scopes))
                except Exception as cascade_err:
                    logger.error(f"cascade_remove_scope_targets error, scope_id={scope_id}, detail={cascade_err}")
                    return utils.build_ret(ErrorMsg.Error, {"error": "目标剔除级联清理异常，请查看服务端日志"})
            else:
                bump_asset_cache_versions()

        # 兼容返回数据
        scope_data["_id"] = str(scope_data.get("_id", scope_id))
        scope_data["scope_id"] = str(scope_id)

        return utils.build_ret(ErrorMsg.Success, scope_data)

# ==========================================
# 接口：批量划转资产组 (POST /batch_move_group/)
# ==========================================
batch_move_fields = ns.model('BatchMoveScope', {
    'scope_ids': fields.List(fields.String(description="资产组ID列表", required=True)),
    'group_id': fields.String(description="目标集团ID", required=True)
})

@ns.route('/batch_move_group/')
class BatchMoveGroupScope(ARLResource):
    @auth
    @ns.expect(batch_move_fields)
    def post(self):
        """
        批量移动资产组至集团
        """
        args = self.parse_args(batch_move_fields)
        scope_ids = args.get('scope_ids', [])
        group_id = args.get('group_id', '')
        
        if not scope_ids or len(scope_ids) > 500:
            return utils.build_ret("参数错误", {"error": "资产组ID列表为空或单次超过500个上限"})
            
        obj_ids = []
        for sid in scope_ids:
            try:
                obj_ids.append(ObjectId(sid))
            except Exception:
                pass
                
        if not obj_ids:
            return utils.build_ret("参数错误", {"error": "无效的资产组ID"})
            
        if group_id and group_id != "unassigned":
            try:
                group_obj_id = ObjectId(group_id)
            except Exception:
                return utils.build_ret("参数错误", {"error": "无效的集团ID"})
                
            group = utils.conn_db('asset_group').find_one({'_id': group_obj_id})
            if not group:
                return utils.build_ret("参数错误", {"error": "集团不存在"})
                
            utils.conn_db('asset_scope').update_many(
                {'_id': {'$in': obj_ids}},
                {'$set': {'group_id': group_id, 'group_name': group.get('name', '')}}
            )
        else:
            utils.conn_db('asset_scope').update_many(
                {'_id': {'$in': obj_ids}},
                {'$unset': {'group_id': "", 'group_name': ""}}
            )
            
        return utils.build_ret(ErrorMsg.Success, {"count": len(obj_ids)})


# ==========================================
# 接口模块：绑定资产组至企业测绘任务 (POST /bind_enterprise/)
# ==========================================
bind_enterprise_fields = ns.model('BindEnterpriseScope', {
    'scope_id': fields.String(description="资产组ID", required=True),
    'task_id': fields.String(description="企业测绘任务ID", required=True)
})

@ns.route('/bind_enterprise/')
class BindEnterpriseScope(ARLResource):
    @auth
    @ns.expect(bind_enterprise_fields)
    def post(self):
        """
        将资产组绑定至企业测绘任务并双向关联
        """
        args = self.parse_args(bind_enterprise_fields)
        scope_id = args.get('scope_id')
        task_id = args.get('task_id')
        try:
            scope_obj_id = ObjectId(scope_id)
            task_obj_id = ObjectId(task_id)
        except Exception:
            return utils.build_ret("参数错误", {"error": "无效的ID格式"})

        task = utils.conn_db('icp_task').find_one({'_id': task_obj_id})
        if not task:
            return utils.build_ret(ErrorMsg.NotFoundTask, {"task_id": task_id})

        scope = utils.conn_db('asset_scope').find_one({'_id': scope_obj_id})
        if not scope:
            return utils.build_ret("参数错误", {"error": "资产组不存在"})

        if task.get('task_type') == 'tyc' or str(task.get('target', '')).startswith('TYC_'):
            ent_name = scope.get('name') or task.get('synced_scope_name') or task.get('name', '').replace('企业测绘', '').strip() or task.get('target')
        else:
            ent_name = task.get('target') or task.get('name')

        # 换绑前清理旧的更新中任务与主指针双向关联，防止旧更新任务完成后回写覆盖新主体
        old_utid = scope.get('updating_icp_task_id')
        if old_utid and str(old_utid) != str(task_obj_id):
            try:
                old_utask = utils.conn_db('icp_task').find_one({'_id': ObjectId(old_utid)})
                if old_utask and old_utask.get('status') in ['waiting', 'running']:
                    utils.conn_db('icp_task').update_one(
                        {'_id': ObjectId(old_utid), 'status': {'$in': ['waiting', 'running']}},
                        {'$set': {'status': 'stop', 'end_time': utils.curr_date()}}
                    )
                    try:
                        from app.routes.icp import _request_recon
                        _request_recon('stop', {'task_id': str(old_utid)})
                    except Exception as stop_err:
                        logger.warning(f"Failed to stop superseded updating task {old_utid}: {stop_err}")
            except Exception as ut_err:
                logger.warning(f"Failed to inspect superseded updating task {old_utid}: {ut_err}")

        old_stid = scope.get('synced_icp_task_id')
        if old_stid and str(old_stid) != str(task_obj_id):
            try:
                utils.conn_db('icp_task').update_one(
                    {'_id': ObjectId(old_stid), 'synced_scope_id': str(scope_obj_id)},
                    {'$unset': {'synced_scope_id': '', 'synced_scope_name': ''}}
                )
            except Exception:
                pass

        utils.conn_db('asset_scope').update_one(
            {'_id': scope_obj_id},
            {
                '$set': {
                    'synced_icp_task_id': str(task_obj_id),
                    'enterprise_name': ent_name
                },
                '$unset': {
                    'updating_icp_task_id': '',
                    'last_update_error': '',
                    'last_update_error_task_id': '',
                    'last_update_error_time': ''
                }
            }
        )
        utils.conn_db('icp_task').update_one(
            {'_id': task_obj_id},
            {'$set': {
                'synced_scope_id': str(scope_obj_id),
                'synced_scope_name': scope.get('name')
            }}
        )
        return utils.build_ret(ErrorMsg.Success, {"scope_id": scope_id, "task_id": task_id})


clear_update_error_fields = ns.model('ClearScopeUpdateError', {
    'scope_id': fields.String(description="资产组ID", required=True)
})


@ns.route('/clear_update_error/')
class ClearScopeUpdateError(ARLResource):
    @auth
    @ns.expect(clear_update_error_fields)
    def post(self):
        """清除资产组最近一次后台主体更新失败提示"""
        args = self.parse_args(clear_update_error_fields)
        scope_id = args.get('scope_id')
        try:
            scope_obj_id = ObjectId(scope_id)
        except Exception:
            return utils.build_ret("参数错误", {"error": "无效的资产组ID格式"})

        utils.conn_db('asset_scope').update_one(
            {'_id': scope_obj_id},
            {'$unset': {
                'last_update_error': '',
                'last_update_error_task_id': '',
                'last_update_error_time': ''
            }}
        )
        return utils.build_ret(ErrorMsg.Success, {"scope_id": scope_id})