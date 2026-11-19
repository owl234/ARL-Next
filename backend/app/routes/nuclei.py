import os
import io
import re
import yaml
import json
import shutil
import zipfile
import tempfile
import subprocess
import threading
import time
from datetime import datetime
from urllib.parse import quote
import requests

from flask import request, Response, make_response
from flask_restx import fields, Namespace
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app import utils
from app.modules import ErrorMsg
from app.config import Config

ns = Namespace('nuclei', description="Nuclei 模板管理与在线调试")
logger = get_logger()

from app.services.nuclei_template_service import (
    _community_cache,
    _sync_lock,
    get_community_templates_dir,
    get_nuclei_template_version_info,
    update_templates_config_version,
    extract_templates_zip_to_dir,
    parse_and_validate_nuclei_yaml,
    normalize_dry_run_target,
    strip_ansi,
    _extract_nuclei_error_summary,
    load_community_index,
    get_current_sync_doc,
    run_community_sync_worker,
    classify_asm_protocol,
    is_asm_supported_protocol,
    validate_nuclei_templates_batch,
)
from app.services.nuclei_scan import resolve_nuclei_proxy


base_template_search_fields = {
    'template_id': fields.String(description="模板 ID"),
    'name': fields.String(description="漏洞/模板名称"),
    'severity': fields.String(description="危害级别 (critical/high/medium/low/info)"),
    'tag': fields.String(description="标签过滤"),
    'enable': fields.Boolean(description="启用状态"),
}
base_template_search_fields.update(base_query_fields)


@ns.route('/template/')
class NucleiTemplateList(ARLResource):
    parser = get_arl_parser(base_template_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """自建模板列表分页查询"""
        args = self.parser.parse_args()
        page = int(args.get('page') or 1)
        size = int(args.get('size') or 10)
        order = args.get('order') or '-updated_at'

        query = {}
        if args.get('template_id'):
            query['template_id'] = {'$regex': re.escape(args['template_id'].strip()), '$options': 'i'}
        if args.get('name'):
            query['name'] = {'$regex': re.escape(args['name'].strip()), '$options': 'i'}
        if args.get('severity'):
            query['severity'] = args['severity'].strip().lower()
        if args.get('tag'):
            query['tags'] = {'$in': [args['tag'].strip().lower()]}
        if args.get('enable') is not None:
            query['enable'] = bool(args['enable'])

        col = utils.conn_db('nuclei_template')
        total = col.count_documents(query)

        sort_dir = 1
        sort_key = order
        if order.startswith('-'):
            sort_dir = -1
            sort_key = order[1:]

        items = list(col.find(query).sort(sort_key, sort_dir).skip((page - 1) * size).limit(size))
        for item in items:
            item['_id'] = str(item['_id'])
            # 列表视图省去大体积 content 字段，提高传输性能
            item.pop('content', None)
            item['asm_bucket'] = classify_asm_protocol(item.get('protocol'))
            item['asm_supported'] = is_asm_supported_protocol(item.get('protocol'))

        return utils.build_ret(ErrorMsg.Success, {
            "items": items,
            "total": total,
            "page": page,
            "size": size
        })


@ns.route('/template/detail/')
class NucleiTemplateDetail(ARLResource):

    @auth
    def get(self):
        """获取单个自建模板详情与完整 YAML 源码"""
        template_id = request.args.get('template_id')
        _id = request.args.get('_id')

        query = {}
        if _id:
            try:
                query['_id'] = ObjectId(_id)
            except Exception:
                return utils.build_ret(ErrorMsg.Error, {'error': '无效的 _id'})
        elif template_id:
            query['template_id'] = template_id.strip()
        else:
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少 template_id 或 _id 参数'})

        doc = utils.conn_db('nuclei_template').find_one(query)
        if not doc:
            return utils.build_ret(ErrorMsg.Error, {'error': '未找到指定模板'})

        doc['_id'] = str(doc['_id'])
        return utils.build_ret(ErrorMsg.Success, doc)


@ns.route('/template/create/')
class NucleiTemplateCreate(ARLResource):

    @auth
    def post(self):
        """新建自建 Nuclei 模板"""
        data = request.json
        if not isinstance(data, dict):
            data = {}
        content = data.get('content', '')
        raw_enable = data.get('enable', True)
        if isinstance(raw_enable, str):
            enable = raw_enable.strip().lower() not in ('false', '0', 'no', '')
        else:
            enable = bool(raw_enable)

        is_valid, meta = parse_and_validate_nuclei_yaml(content, run_nuclei_validate=True)
        if not is_valid:
            return utils.build_ret(meta, {})

        col = utils.conn_db('nuclei_template')
        existing = col.find_one({'template_id': meta['template_id']})
        if existing:
            return utils.build_ret(f"模板 ID '{meta['template_id']}' 已存在，请勿重复创建", {})

        now_str = utils.curr_date()
        doc = {
            "template_id": meta['template_id'],
            "name": meta['name'],
            "severity": meta['severity'],
            "tags": meta['tags'],
            "protocol": meta['protocol'],
            "author": meta['author'],
            "description": meta['description'],
            "reference": meta['reference'],
            "content": meta['content'],
            "enable": enable,
            "is_custom": True,
            "created_at": now_str,
            "updated_at": now_str
        }

        try:
            col.insert_one(doc)
        except DuplicateKeyError:
            return utils.build_ret(f"模板 ID '{meta['template_id']}' 已存在，请勿重复创建", {})
        doc['_id'] = str(doc['_id'])
        return utils.build_ret(ErrorMsg.Success, {
            'message': '创建成功',
            'template_id': meta['template_id'],
            'enable': enable,
        })


@ns.route('/template/update/')
class NucleiTemplateUpdate(ARLResource):

    @auth
    def post(self):
        """更新自建 Nuclei 模板源码与元数据"""
        data = request.json
        if not isinstance(data, dict):
            data = {}
        template_id = str(data.get('template_id') or '').strip()
        content = data.get('content', '')

        if not template_id:
            return utils.build_ret('缺少 template_id 参数', {})

        is_valid, meta = parse_and_validate_nuclei_yaml(content, run_nuclei_validate=True)
        if not is_valid:
            return utils.build_ret(meta, {})

        col = utils.conn_db('nuclei_template')
        existing = col.find_one({'template_id': template_id})
        if not existing:
            return utils.build_ret(f"模板 '{template_id}' 不存在", {})

        now_str = utils.curr_date()
        update_fields = {
            "name": meta['name'],
            "severity": meta['severity'],
            "tags": meta['tags'],
            "protocol": meta['protocol'],
            "author": meta['author'],
            "description": meta['description'],
            "reference": meta['reference'],
            "content": meta['content'],
            "updated_at": now_str
        }

        # 若用户在 YAML 中更改了 id 且未与其他模板冲突，允许重命名更新
        new_template_id = meta['template_id']
        if new_template_id != template_id:
            conflict = col.find_one({'template_id': new_template_id, '_id': {'$ne': existing['_id']}})
            if conflict:
                return utils.build_ret(f"新的模板 ID '{new_template_id}' 已被占用", {})
            update_fields['template_id'] = new_template_id

        try:
            col.update_one({'_id': existing['_id']}, {'$set': update_fields})
        except DuplicateKeyError:
            return utils.build_ret(f"新的模板 ID '{new_template_id}' 已被占用", {})
        return utils.build_ret(ErrorMsg.Success, {'message': '更新成功', 'template_id': new_template_id})


@ns.route('/template/delete/')
class NucleiTemplateDelete(ARLResource):

    @auth
    def post(self):
        """批量删除自建模板"""
        data = request.json or {}
        template_ids = data.get('template_ids', [])
        if not template_ids or not isinstance(template_ids, list):
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少要删除的 template_ids 列表'})

        col = utils.conn_db('nuclei_template')
        res = col.delete_many({'template_id': {'$in': template_ids}})
        return utils.build_ret(ErrorMsg.Success, {'delete_cnt': res.deleted_count})


@ns.route('/template/toggle/')
class NucleiTemplateToggle(ARLResource):

    @auth
    def post(self):
        """切换单个模板启用/禁用状态"""
        data = request.json or {}
        template_id = data.get('template_id', '').strip()
        enable = data.get('enable')

        if not template_id or enable is None:
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少 template_id 或 enable 参数'})

        col = utils.conn_db('nuclei_template')
        res = col.update_one({'template_id': template_id}, {'$set': {'enable': bool(enable), 'updated_at': utils.curr_date()}})
        if res.matched_count == 0:
            return utils.build_ret(ErrorMsg.Error, {'error': '未找到指定模板'})

        return utils.build_ret(ErrorMsg.Success, {'message': '状态更新成功'})


@ns.route('/template/batch_toggle/')
class NucleiTemplateBatchToggle(ARLResource):

    @auth
    def post(self):
        """批量切换模板启用/禁用状态"""
        data = request.json or {}
        template_ids = data.get('template_ids', [])
        enable = data.get('enable')

        if not template_ids or not isinstance(template_ids, list) or enable is None:
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少 template_ids 或 enable 参数'})

        col = utils.conn_db('nuclei_template')
        res = col.update_many({'template_id': {'$in': template_ids}}, {'$set': {'enable': bool(enable), 'updated_at': utils.curr_date()}})
        return utils.build_ret(ErrorMsg.Success, {'modified_count': res.modified_count})


@ns.route('/template/import/')
class NucleiTemplateImport(ARLResource):

    @auth
    def post(self):
        """导入 YAML 文件或 ZIP 压缩包 (支持批量)"""
        if 'file' not in request.files:
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少上传文件 (file)'})

        files = request.files.getlist('file')
        if not files:
            return utils.build_ret(ErrorMsg.Error, {'error': '未选择任何文件'})

        success_count = 0
        fail_count = 0
        fail_details = []
        valid_candidates = []
        col = utils.conn_db('nuclei_template')

        def _process_yaml_content(content_str: str, file_display_name: str):
            nonlocal fail_count
            is_valid, meta = parse_and_validate_nuclei_yaml(content_str, run_nuclei_validate=False)
            if not is_valid:
                fail_count += 1
                fail_details.append({"filename": file_display_name, "reason": meta})
                return

            valid_candidates.append({
                "filename": file_display_name,
                "meta": meta,
            })

        for f in files:
            if not f or not f.filename:
                continue
            filename = os.path.basename(f.filename)
            ext = os.path.splitext(filename)[1].lower()

            if ext in ('.yaml', '.yml'):
                try:
                    raw_bytes = f.read(10 * 1024 * 1024)
                    content = raw_bytes.decode('utf-8-sig', errors='replace')
                    _process_yaml_content(content, filename)
                except Exception as e:
                    fail_count += 1
                    fail_details.append({"filename": filename, "reason": f"读取失败: {e}"})
            elif ext == '.zip':
                try:
                    raw_bytes = f.read(50 * 1024 * 1024)
                    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                        for zinfo in z.infolist():
                            if zinfo.is_dir():
                                continue
                            if not zinfo.filename.lower().endswith(('.yaml', '.yml')):
                                continue
                            try:
                                zcontent = z.read(zinfo).decode('utf-8-sig', errors='replace')
                                _process_yaml_content(zcontent, zinfo.filename)
                            except Exception as ze:
                                fail_count += 1
                                fail_details.append({"filename": zinfo.filename, "reason": f"解压读取错误: {ze}"})
                except Exception as e:
                    fail_count += 1
                    fail_details.append({"filename": filename, "reason": f"ZIP 解压失败: {e}"})
            else:
                fail_count += 1
                fail_details.append({"filename": filename, "reason": "不支持的文件类型，仅支持 .yaml、.yml 或包含模板的 .zip 压缩包"})

        passed_entries, semantic_failures = validate_nuclei_templates_batch(valid_candidates)
        if semantic_failures:
            fail_count += len(semantic_failures)
            fail_details.extend(semantic_failures)

        for entry in passed_entries:
            meta = entry["meta"]
            now_str = utils.curr_date()
            doc = {
                "template_id": meta['template_id'],
                "name": meta['name'],
                "severity": meta['severity'],
                "tags": meta['tags'],
                "protocol": meta['protocol'],
                "author": meta['author'],
                "description": meta['description'],
                "reference": meta['reference'],
                "content": meta['content'],
                "enable": True,
                "is_custom": True,
                "updated_at": now_str
            }
            # 存在则覆盖更新，不存在则插入
            col.update_one({'template_id': meta['template_id']}, {'$set': doc, '$setOnInsert': {'created_at': now_str}}, upsert=True)
            success_count += 1

        return utils.build_ret(ErrorMsg.Success, {
            "success_count": success_count,
            "fail_count": fail_count,
            "fail_details": fail_details
        })


@ns.route('/template/export/')
class NucleiTemplateExport(ARLResource):

    @auth
    def get(self):
        """批量导出自建模板为 ZIP 压缩包"""
        template_ids_str = request.args.get('template_ids', '')
        query = {}
        if template_ids_str:
            ids = [x.strip() for x in template_ids_str.split(',') if x.strip()]
            query = {'template_id': {'$in': ids}}

        col = utils.conn_db('nuclei_template')
        docs = list(col.find(query))
        if not docs:
            return utils.build_ret(ErrorMsg.Error, {'error': '没有可导出的模板'})

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            for doc in docs:
                t_id = doc.get('template_id', 'template')
                content = doc.get('content', '')
                z.writestr(f"{t_id}.yaml", content.encode('utf-8'))

        buf.seek(0)
        filename = f"nuclei_custom_templates_{int(time.time())}.zip"
        response = make_response(buf.getvalue())
        response.headers['Content-Type'] = 'application/zip'
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        response.headers["Content-Disposition"] = f"attachment; filename={quote(filename)}"
        return response


def _parse_dry_run_findings(jsonl_path: str, clean_stdout: str, meta: dict):
    """优先从 -jle JSONL 产物解析命中详情，旧版引擎不支持 -jle 时回退到无 ANSI 文本行判定。"""
    findings = []
    if jsonl_path and os.path.exists(jsonl_path):
        try:
            with open(jsonl_path, "r", encoding="utf-8", errors="replace") as jf:
                for raw_line in jf:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except Exception:
                        continue
                    info = item.get("info") if isinstance(item.get("info"), dict) else {}
                    findings.append({
                        "template_id": item.get("template-id") or meta["template_id"],
                        "name": info.get("name") or meta["name"],
                        "severity": str(info.get("severity") or meta["severity"]).lower(),
                        "matched_at": item.get("matched-at") or item.get("url") or item.get("host") or "",
                        "curl_command": item.get("curl-command") or "",
                        "extracted_results": item.get("extracted-results") or [],
                    })
        except Exception as e:
            logger.debug(f"Failed to read dry run jsonl output: {e}")

    if findings:
        return findings

    severity_tokens = ("[critical]", "[high]", "[medium]", "[low]", "[info]", "[unknown]")
    log_prefixes = ("[INF]", "[VER]", "[WRN]", "[ERR]", "[FTL]")
    tid_token = f"[{meta['template_id']}]"
    for line in (clean_stdout or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(log_prefixes):
            continue
        lowered = stripped.lower()
        if tid_token in stripped or any(tok in lowered for tok in severity_tokens):
            parts = stripped.split()
            matched_at = parts[-1] if parts and not parts[-1].startswith("[") else ""
            findings.append({
                "template_id": meta["template_id"],
                "name": meta["name"],
                "severity": meta["severity"],
                "matched_at": matched_at,
                "curl_command": "",
                "extracted_results": [],
            })
    return findings


@ns.route('/template/test/')
class NucleiTemplateTest(ARLResource):

    @auth
    def post(self):
        """
        在线单目标即时发包调试 (Dry Run)
        """
        data = request.json
        if not isinstance(data, dict):
            data = {}
        content = data.get('content', '')
        template_id = str(data.get('template_id') or '').strip()
        raw_target = data.get('target', '')

        # 若未直接传 content，则根据 template_id 查找
        if (not isinstance(content, str) or not content.strip()) and template_id:
            doc = utils.conn_db('nuclei_template').find_one({'template_id': template_id})
            if doc:
                content = doc.get('content', '')

        if not isinstance(content, str) or not content.strip():
            return utils.build_ret('缺少模板内容', {})

        is_valid, meta = parse_and_validate_nuclei_yaml(content, run_nuclei_validate=False)
        if not is_valid:
            return utils.build_ret(f"模板静态校验失败: {meta}", {})

        ok_target, target_or_err = normalize_dry_run_target(raw_target, meta['protocol'])
        if not ok_target:
            return utils.build_ret(target_or_err, {})
        target = target_or_err

        nuclei_bin = shutil.which("nuclei")
        if not nuclei_bin:
            return utils.build_ret('系统未检测到 nuclei 引擎，请确认运行环境中已安装 nuclei', {})

        nuclei_proxy, masked_proxy = resolve_nuclei_proxy([target])
        rand_str = utils.random_choices(8)
        tmp_file = os.path.join(Config.TMP_PATH, f"dryrun_{rand_str}.yaml")
        tmp_jsonl = os.path.join(Config.TMP_PATH, f"dryrun_{rand_str}.jsonl")

        def _build_cmd(with_jle=True):
            cmd_list = [
                nuclei_bin,
                "-duc",
                "-nc",
                "-t", tmp_file,
                "-u", target,
                "-v",
                "-stats=false",
                "-timeout", "10",
            ]
            if with_jle:
                cmd_list.extend(["-jle", tmp_jsonl])
            if nuclei_proxy:
                cmd_list.extend(["-proxy", nuclei_proxy])
            return cmd_list

        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(content)

            cmd = _build_cmd(with_jle=True)
            log_cmd = " ".join(cmd)
            if nuclei_proxy and masked_proxy:
                log_cmd = log_cmd.replace(nuclei_proxy, masked_proxy)
            logger.info(f"Nuclei Dry Run: {log_cmd}")

            t0 = time.time()
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            if proc.returncode != 0 and "-jle" in (proc.stderr or "") and "not defined" in (proc.stderr or ""):
                # 兼容不支持 -jle 的旧版本 Nuclei
                cmd = _build_cmd(with_jle=False)
                proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            elapse = round(time.time() - t0, 2)

            out = strip_ansi(proc.stdout or "")
            err = strip_ansi(proc.stderr or "")
            full_log = (out + ("\n" + err if err else "")).strip()
            if nuclei_proxy and masked_proxy:
                full_log = full_log.replace(nuclei_proxy, masked_proxy)

            if proc.returncode != 0:
                err_summary = _extract_nuclei_error_summary(err or out) or f"退出码 {proc.returncode}"
                ret = utils.build_ret(f"Nuclei 执行失败: {err_summary}", {})
                ret["data"] = {
                    "matched": False,
                    "matched_count": 0,
                    "findings": [],
                    "target": target,
                    "output": full_log,
                    "returncode": proc.returncode,
                    "cost_seconds": elapse,
                }
                return ret

            findings = _parse_dry_run_findings(tmp_jsonl, out, meta)
            matched = len(findings) > 0

            return utils.build_ret(ErrorMsg.Success, {
                "matched": matched,
                "matched_count": len(findings),
                "findings": findings,
                "target": target,
                "output": full_log,
                "returncode": proc.returncode,
                "cost_seconds": elapse
            })
        except subprocess.TimeoutExpired:
            return utils.build_ret('Nuclei 调试探测超时 (超过 30 秒)', {})
        except Exception as e:
            logger.error(f"Nuclei Dry Run exception: {e}")
            return utils.build_ret(f'执行失败: {e}', {})
        finally:
            for p in (tmp_file, tmp_jsonl):
                if os.path.exists(p):
                    try:
                        os.unlink(p)
                    except Exception:
                        pass


@ns.route('/community/')
class NucleiCommunityList(ARLResource):

    @auth
    def get(self):
        """官方社区模板只读检索 (支持误报黑名单状态联动与过滤)"""
        search = request.args.get('search', '').strip().lower()
        severity = request.args.get('severity', '').strip().lower()
        tag = request.args.get('tag', '').strip().lower()
        blacklist_status = request.args.get('blacklist_status', 'all').strip().lower()
        refresh_arg = request.args.get('refresh', '').strip().lower()
        force_refresh = refresh_arg in ['1', 'true', 'yes']
        page = int(request.args.get('page') or 1)
        size = int(request.args.get('size') or 10)

        # 读取黑名单集合映射表 (大小写不敏感匹配)
        bl_col = utils.conn_db('nuclei_blacklist')
        bl_docs = {}
        for d in bl_col.find({}, {'template_id': 1, 'reason': 1}):
            raw_tid = d.get('template_id')
            if raw_tid:
                rs = d.get('reason', '')
                bl_docs[raw_tid] = rs
                bl_docs[raw_tid.lower()] = rs
                bl_docs[raw_tid.upper()] = rs

        templates = load_community_index(force_refresh=force_refresh)
        filtered = templates

        if search:
            filtered = [t for t in filtered if search in t['template_id'].lower() or search in t['name'].lower()]
        if severity:
            filtered = [t for t in filtered if t['severity'].lower() == severity]
        if tag:
            filtered = [t for t in filtered if any(tag in tg for tg in t.get('tags', []))]
        if blacklist_status == 'blacklisted':
            filtered = [t for t in filtered if t['template_id'] in bl_docs or t['template_id'].lower() in bl_docs]
        elif blacklist_status == 'normal':
            filtered = [t for t in filtered if t['template_id'] not in bl_docs and t['template_id'].lower() not in bl_docs]

        total = len(filtered)
        start = (page - 1) * size
        end = start + size
        raw_items = filtered[start:end]

        items = []
        for t in raw_items:
            item = dict(t)
            tid = t['template_id']
            is_bl = tid in bl_docs or tid.lower() in bl_docs
            item['is_blacklisted'] = is_bl
            item['blacklist_reason'] = bl_docs.get(tid) or bl_docs.get(tid.lower()) or ''
            items.append(item)

        return utils.build_ret(ErrorMsg.Success, {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "community_dir": get_community_templates_dir()
        })


@ns.route('/blacklist/')
class NucleiBlacklistList(ARLResource):

    @auth
    def get(self):
        """误报黑名单分页查询"""
        search = request.args.get('search', '').strip()
        severity = request.args.get('severity', '').strip().lower()
        page = int(request.args.get('page') or 1)
        size = int(request.args.get('size') or 10)

        col = utils.conn_db('nuclei_blacklist')
        query = {}
        if search:
            escaped = re.escape(search)
            query['$or'] = [
                {'template_id': {'$regex': escaped, '$options': 'i'}},
                {'name': {'$regex': escaped, '$options': 'i'}},
                {'reason': {'$regex': escaped, '$options': 'i'}}
            ]
        if severity:
            query['severity'] = severity

        total = col.count_documents(query)
        cursor = col.find(query).sort('created_at', -1).skip((page - 1) * size).limit(size)
        items = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            items.append(doc)

        return utils.build_ret(ErrorMsg.Success, {
            'items': items,
            'total': total,
            'page': page,
            'size': size
        })

    @auth
    def post(self):
        """添加模板到误报黑名单"""
        data = request.json or {}
        template_id = data.get('template_id', '').strip()
        if not template_id:
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少 template_id 参数'})

        reason = data.get('reason', '').strip() or '手工标记误报'
        name = data.get('name', '').strip() or template_id
        severity = (data.get('severity') or 'unknown').strip().lower()
        tags = data.get('tags', [])
        source_type = data.get('source_type', 'community')

        col = utils.conn_db('nuclei_blacklist')
        now_str = utils.curr_date()
        doc = {
            'template_id': template_id,
            'name': name,
            'severity': severity,
            'tags': tags,
            'reason': reason,
            'source_type': source_type,
            'updated_at': now_str
        }
        col.update_one(
            {'template_id': template_id},
            {
                '$set': doc,
                '$setOnInsert': {'created_at': now_str}
            },
            upsert=True
        )
        return utils.build_ret(ErrorMsg.Success, {'message': f'模板 {template_id} 已成功加入误报黑名单'})


@ns.route('/blacklist/<string:template_id>/')
class NucleiBlacklistDetail(ARLResource):

    @auth
    def delete(self, template_id):
        """从误报黑名单移除单个模板 (大小写不敏感匹配)"""
        template_id = template_id.strip()
        col = utils.conn_db('nuclei_blacklist')
        res = col.delete_one({'$or': [{'template_id': template_id}, {'template_id': template_id.lower()}, {'template_id': template_id.upper()}]})
        if res.deleted_count == 0:
            return utils.build_ret(ErrorMsg.Error, {'error': f'未在黑名单中找到模板 {template_id}'})
        return utils.build_ret(ErrorMsg.Success, {'message': f'模板 {template_id} 已移出误报黑名单'})


@ns.route('/blacklist/delete/')
class NucleiBlacklistBatchDelete(ARLResource):

    @auth
    def post(self):
        """批量从误报黑名单移除模板 (大小写不敏感匹配)"""
        data = request.json or {}
        template_ids = data.get('template_ids', [])
        if not template_ids or not isinstance(template_ids, list):
            return utils.build_ret(ErrorMsg.Error, {'error': '缺少 template_ids 列表'})

        col = utils.conn_db('nuclei_blacklist')
        query_ids = set()
        for tid in template_ids:
            if tid and isinstance(tid, str):
                t_str = tid.strip()
                query_ids.add(t_str)
                query_ids.add(t_str.lower())
                query_ids.add(t_str.upper())

        res = col.delete_many({'template_id': {'$in': list(query_ids)}})
        return utils.build_ret(ErrorMsg.Success, {'deleted_count': res.deleted_count, 'message': f'已成功移除 {res.deleted_count} 个模板'})


@ns.route('/community/source/')
class NucleiCommunitySource(ARLResource):

    @auth
    def get(self):
        """获取指定社区模板的 YAML 源码"""
        file_path = request.args.get('file_path', '').strip()
        template_id = request.args.get('template_id', '').strip()

        c_dir = get_community_templates_dir()
        if not c_dir or not os.path.isdir(c_dir):
            return utils.build_ret(ErrorMsg.Error, {'error': '未找到官方社区模板目录'})

        target_file = None
        if file_path:
            candidate = os.path.abspath(os.path.join(c_dir, file_path))
            # 严格防止目录遍历攻击 (Path Traversal Protection)
            if candidate.startswith(c_dir) and os.path.isfile(candidate):
                target_file = candidate

        if not target_file and template_id:
            templates = load_community_index()
            for t in templates:
                if t['template_id'] == template_id and t.get('file_path'):
                    cand = os.path.abspath(os.path.join(c_dir, t['file_path']))
                    if cand.startswith(c_dir) and os.path.isfile(cand):
                        target_file = cand
                        break

            # 容错兜底：若索引未命中，在官方目录下进行直接文件查找
            if not target_file:
                for ext in ['.yaml', '.yml']:
                    cand_name = f"{template_id}{ext}"
                    for root, dirs, files in os.walk(c_dir):
                        if cand_name in files:
                            cand = os.path.abspath(os.path.join(root, cand_name))
                            if cand.startswith(c_dir) and os.path.isfile(cand):
                                target_file = cand
                                break
                    if target_file:
                        break

        if not target_file or not os.path.isfile(target_file):
            return utils.build_ret(ErrorMsg.Error, {'error': '找不到该模板文件'})

        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                content = f.read()
            return utils.build_ret(ErrorMsg.Success, {'content': content, 'file_path': file_path or os.path.relpath(target_file, c_dir)})
        except Exception as e:
            return utils.build_ret(ErrorMsg.Error, {'error': f'读取模板失败: {e}'})


# ==============================================================================
# 官方社区模板同步状态机与执行引擎 (实现已下沉至 app.services.nuclei_template_service)
# ==============================================================================


@ns.route('/community/sync_status/')
class NucleiCommunitySyncStatus(ARLResource):

    @auth
    def get(self):
        """获取官方模板最新同步状态与完整日志"""
        data = get_current_sync_doc()
        return utils.build_ret(ErrorMsg.Success, data)


@ns.route('/community/sync/')
class NucleiCommunitySync(ARLResource):

    @auth
    def post(self):
        """触发官方社区模板在线同步 (带状态机与加速通道)"""
        col = utils.conn_db('nuclei_sync_log')
        current = col.find_one({'_id': 'latest_sync'})
        if current and current.get('status') == 'syncing':
            # 防抖防重保护：若上次任务在 5 分钟内启动，拦截重复点击
            st_time = current.get('start_time', '')
            return utils.build_ret("同步任务正在进行中，请勿重复触发", {"status": "syncing", "start_time": st_time})

        t = threading.Thread(target=run_community_sync_worker, kwargs={"mode": "online"}, daemon=True)
        t.start()
        return utils.build_ret(ErrorMsg.Success, {'message': '官方模板库加速同步任务已启动，正在后台拉取中'})


@ns.route('/community/sync_offline/')
class NucleiCommunitySyncOffline(ARLResource):

    @auth
    def post(self):
        """上传官方模板离线全量 ZIP 包覆盖更新"""
        if 'file' not in request.files:
            return utils.build_ret("未上传 ZIP 文件", {})

        file_obj = request.files['file']
        filename = file_obj.filename or ""
        if not filename.lower().endswith('.zip'):
            return utils.build_ret("仅支持上传 .zip 格式的模板压缩包", {})

        temp_zip = os.path.join(Config.TMP_PATH, f"offline_sync_{utils.random_choices(8)}.zip")
        try:
            file_obj.save(temp_zip)
            # 校验 zip 合法性
            with zipfile.ZipFile(temp_zip, 'r') as zf:
                names = zf.namelist()
                has_yaml = any(n.endswith(('.yaml', '.yml')) for n in names)
                if not has_yaml:
                    if os.path.exists(temp_zip):
                        os.unlink(temp_zip)
                    return utils.build_ret("上传的 ZIP 压缩包内未检测到 Nuclei YAML 模板文件", {})

            t = threading.Thread(target=run_community_sync_worker, kwargs={"mode": "offline_zip", "offline_zip_path": temp_zip}, daemon=True)
            t.start()
            return utils.build_ret(ErrorMsg.Success, {'message': '离线模板包已接收，正在后台解压覆盖中'})
        except Exception as e:
            if os.path.exists(temp_zip):
                try:
                    os.unlink(temp_zip)
                except Exception:
                    pass
            return utils.build_ret(f"处理离线包失败: {e}", {})


@ns.route('/stats/')
class NucleiStats(ARLResource):

    @auth
    def get(self):
        """获取 Nuclei 模板与引擎统计概览 (扩展版本与新版就绪感知)"""
        col = utils.conn_db('nuclei_template')
        custom_total = col.count_documents({})
        custom_enabled = col.count_documents({'enable': True})

        community_list = load_community_index()
        community_total = len(community_list)

        # 获取 nuclei 引擎版本
        nuclei_version = "未知"
        try:
            res = subprocess.run(["nuclei", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            combined = (res.stdout or "") + "\n" + (res.stderr or "")
            m = re.search(r'v\d+\.\d+\.\d+', combined)
            if m:
                nuclei_version = m.group(0)
        except Exception:
            pass

        # 获取黑名单屏蔽总数
        bl_col = utils.conn_db('nuclei_blacklist')
        blacklist_total = bl_col.count_documents({})

        # 获取模板版本信息
        ver_info = get_nuclei_template_version_info()
        sync_doc = get_current_sync_doc()

        return utils.build_ret(ErrorMsg.Success, {
            "custom_total": custom_total,
            "custom_enabled": custom_enabled,
            "community_total": community_total,
            "blacklist_total": blacklist_total,
            "nuclei_version": nuclei_version,
            "template_version": ver_info.get("current_version", "未知"),
            "template_latest_version": ver_info.get("latest_version", "未知"),
            "has_template_update": ver_info.get("has_update", False),
            "sync_status": sync_doc.get("status", "idle"),
            "sync_diff_count": sync_doc.get("diff_count", 0),
            "sync_end_time": sync_doc.get("end_time", ""),
            "has_community_dir": bool(get_community_templates_dir())
        })
